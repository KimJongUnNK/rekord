"""CI smoke test for the online-meeting call sound on the real OS (Windows WASAPI, macOS ScreenCaptureKit, Linux Pulse).

CI machines have no speakers and no screen-recording permission, so "not available" is fine – what must not happen
is a programming error (wrong API name, wrong arguments). Exit 1 only for those.
    python scripts/capture_smoke.py [seconds]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rekord import capture  # noqa: E402

BUGS = (AttributeError, TypeError, NameError, ImportError)
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 2

caps = capture.available()
print("available:", caps)
if sys.platform == "darwin":
    # the pyobjc names the capture uses must exist, even without permission
    import CoreMedia as CM
    import dispatch
    import ScreenCaptureKit as SCK
    for mod, names in ((SCK, ["SCShareableContent", "SCContentFilter", "SCStreamConfiguration", "SCStream",
                              "SCStreamOutputTypeAudio", "SCStreamOutputTypeScreen"]),
                       (CM, ["CMSampleBufferGetDataBuffer", "CMBlockBufferGetDataLength", "CMBlockBufferCopyDataBytes", "CMSampleBufferGetNumSamples", "CMTimeMake"]),
                       (dispatch, ["dispatch_queue_create"])):
        missing = [n for n in names if not hasattr(mod, n)]
        assert not missing, f"{mod.__name__}: {missing}"
    cfg = SCK.SCStreamConfiguration.alloc().init()
    for sel in ("setCapturesAudio_", "setExcludesCurrentProcessAudio_", "setSampleRate_", "setChannelCount_",
                "setWidth_", "setHeight_", "setMinimumFrameInterval_"):
        assert hasattr(cfg, sel), sel
    cls = capture.output_class()
    assert capture.output_class() is cls  # defined once per process – a second recording must not redefine it
    sig = cls.stream_didOutputSampleBuffer_ofType_.signature
    print("output signature:", sig)
    assert sig.endswith((b"q", b"Q", b"l", b"L")), sig  # the kind arrives as an integer, not as an object pointer
    out = cls.alloc().init()
    out.on_audio = print
    assert out.on_audio is print
    print("pyobjc API: ok")
if not caps["system_audio"]:
    print("no call sound here:", caps["reason"])
    sys.exit(0)

call = capture.SystemAudio()
ok = call.start(timeout=20)
print("started:", ok, "|", call.error or "-", "|", type(call.exc).__name__ if call.exc else "-")
if ok:
    got = 0
    t0 = time.time()
    while time.time() - t0 < secs:
        time.sleep(0.1)
        got += len(call.read(1600))
    print(f"read {got / capture.SR:.1f} s, received from the system {call.received / capture.SR:.1f} s")
    if sys.platform == "darwin":  # ScreenCaptureKit delivers sound buffers (also silence): proves the decoding path
        assert call.received > 0, "ScreenCaptureKit started but delivered no sound"
call.stop()
if call.exc is not None and isinstance(call.exc, BUGS) and "permission" not in str(call.exc).lower():
    import traceback
    traceback.print_exception(call.exc)
    print("BUG: capture failed with a programming error")
    sys.exit(1)
print("OK")
