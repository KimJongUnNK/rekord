"""Online meetings: the call's sound – what Teams, Zoom, Meet … play on this computer, i.e. the other people.

Windows = WASAPI loopback, Linux = PulseAudio/PipeWire monitor (both via `soundcard`), macOS = ScreenCaptureKit
(macOS 13+, asks once for "Bildschirm- & Systemaudioaufnahme"; only the sound is used, no picture is kept).
If the call sound can't be captured, the recording continues with the microphone and the UI says why."""
from __future__ import annotations

import logging
import platform
import sys
import threading
from collections import deque

import numpy as np

log = logging.getLogger("rekord.capture")
SR = 16000


def _resampler(sr_in: int):
    from .audio import Resampler
    return Resampler(sr_in, SR)  # one per stream: the filter runs across the blocks


def _mac_version() -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in platform.mac_ver()[0].split(".")[:2])
    except ValueError:
        return (0,)


def _soundcard():
    """`soundcard` connects to the sound system on import; its program-name guess breaks under `python -c`."""
    if sys.argv[:1] == ["-c"] and len(sys.argv) < 2:
        sys.argv.append("rekord")
    import soundcard
    return soundcard


def available() -> dict:
    """What this computer can capture for online meetings (cheap check, nothing is started)."""
    out = {"system_audio": False, "reason": ""}
    if sys.platform == "darwin":
        if _mac_version() < (13,):
            out["reason"] = "Call-Ton braucht macOS 13 oder neuer."
            return out
        try:
            import ScreenCaptureKit  # noqa: F401 - availability check
            out["system_audio"] = True
        except ImportError:
            out["reason"] = "ScreenCaptureKit fehlt in dieser Installation."
        return out
    try:
        _soundcard()  # availability check (connects to the sound system)
        out["system_audio"] = True
    except Exception as e:  # noqa: BLE001 - e.g. no PulseAudio/PipeWire on Linux
        out["reason"] = ("Call-Ton braucht PulseAudio oder PipeWire (mit pipewire-pulse)." if sys.platform.startswith("linux")
                         else f"Call-Ton nicht verfügbar: {e}")
    return out


# ------------------------------------------------------------------ call sound

class SystemAudio:
    """The computer's output as 16 kHz mono, read in step with the microphone."""

    def __init__(self):
        self._buf: deque[np.ndarray] = deque()
        self._have = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self.error = ""
        self.exc: BaseException | None = None  # the underlying exception (tests/CI tell setup problems from bugs)
        self._mac = None
        self.started = False
        self.received = 0  # samples that really came from the system (diagnostics, CI)

    # the mic drives the clock: each mic chunk takes the same number of call samples
    def read(self, n: int) -> np.ndarray:
        out = np.zeros(n, dtype=np.float32)
        with self._lock:
            # drift guard: never more than 1.5 s behind (dropped) – an empty buffer just means silence
            while self._have > SR * 1.5 and self._buf:
                self._have -= len(self._buf.popleft())
            got = 0
            while got < n and self._buf:
                chunk = self._buf[0]
                take = min(n - got, len(chunk))
                out[got:got + take] = chunk[:take]
                got += take
                if take == len(chunk):
                    self._buf.popleft()
                else:
                    self._buf[0] = chunk[take:]
                self._have -= take
        return out

    def _push(self, x: np.ndarray) -> None:
        if self._stop.is_set() or not len(x):
            return
        with self._lock:
            self._buf.append(x)
            self._have += len(x)
            self.received += len(x)

    def start(self, timeout: float = 8) -> bool:
        target = self._run_mac if sys.platform == "darwin" else self._run_soundcard
        threading.Thread(target=target, daemon=True, name="call-audio").start()
        self._ready.wait(timeout)
        if not self.started and not self.error:
            self.error = "Call-Ton startet nicht (keine Rückmeldung vom System)."
        return self.started

    def stop(self) -> None:
        self._stop.set()
        if self._mac is not None:
            try:
                self._mac.stop()
            except Exception:  # noqa: BLE001
                pass

    def _fail(self, msg: str, exc: BaseException | None = None) -> None:
        self.error = msg
        self.exc = exc
        log.warning("call audio: %s", msg)
        self._ready.set()

    # Windows (WASAPI loopback) + Linux (monitor of the default output)
    def _run_soundcard(self) -> None:
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.ole32.CoInitializeEx(None, 0)  # this thread talks to COM (MTA)
            sc = _soundcard()
            spk = sc.default_speaker()
            mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
            rate = 48000
            rs = _resampler(rate)
            with mic.recorder(samplerate=rate, channels=1, blocksize=rate // 10) as rec:
                self.started = True
                self._ready.set()
                while not self._stop.is_set():
                    data = rec.record(numframes=rate // 10)
                    mono = data.mean(axis=1) if data.ndim > 1 else data
                    self._push(rs(np.nan_to_num(mono)))
        except Exception as e:  # noqa: BLE001
            self._fail(f"Call-Ton nicht verfügbar: {e}", e)

    # macOS: ScreenCaptureKit, our own sound excluded
    def _run_mac(self) -> None:
        try:
            self._mac = MacCapture(on_audio=self._push)
            self._mac.start()
            self.started = True
            self._ready.set()
        except Exception as e:  # noqa: BLE001
            self._fail(str(e), e)


# ------------------------------------------------------------------ macOS: ScreenCaptureKit

_OUTPUT_CLASS = None


def _mono(x: np.ndarray, frames: int) -> np.ndarray:
    """ScreenCaptureKit delivers float32, one channel after the other (planar) – average them to mono."""
    if frames > 0 and len(x) >= 2 * frames:
        ch = len(x) // frames
        return x[:ch * frames].reshape(ch, frames).mean(axis=0)
    return x


def output_class():
    """The ObjC object ScreenCaptureKit hands the sound to. An ObjC class can be defined only once per process,
    so it's built once and reused for every recording."""
    global _OUTPUT_CLASS
    if _OUTPUT_CLASS is not None:
        return _OUTPUT_CLASS
    import CoreMedia as CM
    import objc
    import ScreenCaptureKit as SCK
    from Foundation import NSObject

    try:  # the protocol gives pyobjc the right signature (the sample buffer + an NSInteger kind)
        protos, typed = [objc.protocolNamed("SCStreamOutput")], (lambda f: f)
    except Exception:  # noqa: BLE001
        protos, typed = [], objc.typedSelector(b"v@:@^{opaqueCMSampleBuffer=}q")

    class RekordCallAudioOutput(NSObject, protocols=protos):
        @typed
        def stream_didOutputSampleBuffer_ofType_(self, stream, sbuf, kind):  # noqa: N802 - ObjC selector
            if kind != SCK.SCStreamOutputTypeAudio:
                return
            fn = getattr(self, "on_audio", None)
            if fn is None:
                return
            try:
                blk = CM.CMSampleBufferGetDataBuffer(sbuf)
                n = CM.CMBlockBufferGetDataLength(blk)
                status, data = CM.CMBlockBufferCopyDataBytes(blk, 0, n, None)
                if status == 0 and data:
                    x = _mono(np.frombuffer(bytes(data), dtype=np.float32), int(CM.CMSampleBufferGetNumSamples(sbuf)))
                    fn(x)  # 48 kHz – MacCapture converts it (one filter across the whole call)
            except Exception as e:  # noqa: BLE001
                log.debug("sck audio: %s", e)

    _OUTPUT_CLASS = RekordCallAudioOutput
    return _OUTPUT_CLASS


class MacCapture:
    """An SCStream for the call sound. ScreenCaptureKit always delivers a picture too: the smallest possible, ignored."""
    PERMISSION = ("macOS erlaubt die Aufnahme noch nicht: Systemeinstellungen → Datenschutz & Sicherheit → "
                  "Bildschirm- & Systemaudioaufnahme → REKORD einschalten, dann REKORD neu starten.")

    def __init__(self, on_audio):
        self.on_audio = on_audio
        self.stream = None
        self._out = None

    def _wait(self, starter, what: str, timeout: float = 15):
        done, box = threading.Event(), {}

        def handler(*args):
            box["args"] = args
            done.set()
        starter(handler)
        if not done.wait(timeout):
            raise RuntimeError(f"{what}: keine Antwort von macOS")
        return box["args"]

    def start(self) -> None:
        import CoreMedia as CM
        import dispatch
        import ScreenCaptureKit as SCK

        content, err = self._wait(SCK.SCShareableContent.getShareableContentWithCompletionHandler_, "Bildschirm-Inhalte")
        if err is not None or content is None or not content.displays():
            raise RuntimeError(self.PERMISSION)
        display = content.displays()[0]
        filt = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, [])
        cfg = SCK.SCStreamConfiguration.alloc().init()
        cfg.setCapturesAudio_(True)
        cfg.setExcludesCurrentProcessAudio_(True)
        cfg.setSampleRate_(48000)
        cfg.setChannelCount_(1)
        cfg.setWidth_(2)  # only the sound is used: the smallest possible picture, once per second
        cfg.setHeight_(2)
        cfg.setMinimumFrameInterval_(CM.CMTimeMake(1, 1))
        self._out = output_class().alloc().init()
        rs = _resampler(48000)
        self._out.on_audio = lambda x: self.on_audio(rs(x))
        self.stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(filt, cfg, None)
        queue = dispatch.dispatch_queue_create(b"app.rekord.capture", None)
        for kind in (SCK.SCStreamOutputTypeAudio, SCK.SCStreamOutputTypeScreen):
            ok, err = self.stream.addStreamOutput_type_sampleHandlerQueue_error_(self._out, kind, queue, None)
            if not ok:
                raise RuntimeError(f"ScreenCaptureKit: {err}")
        (err,) = self._wait(self.stream.startCaptureWithCompletionHandler_, "Aufnahme-Start")
        if err is not None:
            raise RuntimeError(self.PERMISSION if "permission" in str(err).lower() or "declined" in str(err).lower()
                               else f"ScreenCaptureKit: {err}")

    def stop(self) -> None:
        if self._out is not None:
            self._out.on_audio = None
        if self.stream is not None:
            self._wait(self.stream.stopCaptureWithCompletionHandler_, "Aufnahme-Stopp", timeout=10)
            self.stream = None
