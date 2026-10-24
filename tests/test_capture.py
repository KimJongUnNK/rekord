"""Online meetings: the call's sound is mixed into the microphone, in step with it (sound only, no picture)."""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from rekord import audio, capture, live

ROOT = Path(__file__).resolve().parent.parent


def test_available_always_answers():
    caps = capture.available()
    assert set(caps) == {"system_audio", "reason"}
    assert caps["system_audio"] or caps["reason"]  # either it works or the UI can say why not


def test_read_follows_the_microphone_clock():
    a = capture.SystemAudio()
    a._push(np.arange(1, 1001, dtype=np.float32))
    a._push(np.arange(1001, 1501, dtype=np.float32))
    first = a.read(700)
    second = a.read(700)  # across the chunk border
    third = a.read(700)  # only 100 left → the rest is silence, never waiting
    assert first[0] == 1 and first[-1] == 700
    assert second[0] == 701 and second[-1] == 1400
    assert third[:100].tolist() == list(range(1401, 1501)) and not third[100:].any()
    assert a.read(10).tolist() == [0.0] * 10
    assert a.received == 1500


def test_drift_guard_drops_old_call_sound():
    a = capture.SystemAudio()
    for _ in range(40):  # 4 s of call sound piled up (mic was slower)
        a._push(np.ones(1600, dtype=np.float32))
    a.read(1)
    assert a._have <= capture.SR * 1.5  # at most 1.5 s behind – old sound is dropped, not played late


def test_nothing_is_kept_after_stop():
    a = capture.SystemAudio()
    a.stop()
    a._push(np.ones(1600, dtype=np.float32))
    assert not a.read(1600).any()


def test_planar_stereo_becomes_mono():
    left, right = np.full(480, 0.2, np.float32), np.full(480, 0.4, np.float32)
    assert np.allclose(capture._mono(np.concatenate([left, right]), 480), 0.3)
    mono = np.linspace(-1, 1, 480, dtype=np.float32)
    assert np.array_equal(capture._mono(mono, 480), mono)


def test_resampler_keeps_duration_across_blocks():
    """The call sound comes in 0.1 s blocks at 48 kHz: one filter across all of them, nothing lost or added."""
    rs = capture._resampler(48000)
    out = np.concatenate([rs(np.zeros(4800, np.float32)) for _ in range(50)] + [rs.flush()])
    assert len(out) == 50 * 1600
    same = capture._resampler(16000)
    assert len(same(np.zeros(4800, np.float32))) == 4800


class _FakeCall:
    def __init__(self, value):
        self.value, self.asked = value, []

    def read(self, n):
        self.asked.append(n)
        return np.full(n, self.value, np.float32)


def _session(call, paused=False):
    s = live.LiveSession.__new__(live.LiveSession)  # no models needed: only the mixing is under test
    s.sr_in, s.call, s.paused, s._fed = 16000, call, paused, []
    s._rs = audio.Resampler(16000)
    s.feed = s._fed.append
    return s


def _pcm(value, n=1600):
    return (np.full(n, value * 32768, np.float32)).astype("<i2").tobytes()


def test_online_mixes_the_call_into_the_microphone():
    call = _FakeCall(0.25)
    s = _session(call)
    s.feed_pcm16(_pcm(0.5))
    assert call.asked == [1600]  # as much call sound as microphone sound
    assert np.allclose(s._fed[0], 0.75, atol=1e-3)
    s.feed_pcm16(_pcm(0.9))
    assert s._fed[1].max() <= 1.0  # loud mic + loud call never overflows


def test_paused_recording_skips_the_call_too():
    call = _FakeCall(0.25)
    s = _session(call, paused=True)
    s.feed_pcm16(_pcm(0.5))
    assert call.asked == [1600]  # read anyway, so nothing piles up during the pause
    assert np.allclose(s._fed[0], 0.5, atol=1e-3)


def test_in_person_is_just_the_microphone():
    s = _session(None)
    s.feed_pcm16(_pcm(0.5))
    assert np.allclose(s._fed[0], 0.5, atol=1e-3)


def test_status_tells_the_ui_what_works():
    from fastapi.testclient import TestClient

    from rekord.server import app
    with TestClient(app) as c:
        caps = c.get("/api/status").json()["capture"]
    assert set(caps) == {"system_audio", "reason"}


# ------------------------------------------------------------------ the real thing (Linux, virtual speaker)

def test_real_call_sound_from_a_virtual_speaker(tmp_path, pulse):
    """A tone plays on the computer's speaker (= the other people in the call) → REKORD hears it at the right pitch."""
    sr, t = 48000, np.arange(48000 * 5) / 48000
    tone = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    with wave.open(str(tmp_path / "tone.wav"), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr), w.writeframes(tone.tobytes())
    probe = f"""
import subprocess, sys, time, numpy as np
sys.path.insert(0, {str(ROOT)!r})
from rekord import capture
a = capture.SystemAudio()
assert a.start(), a.error
p = subprocess.Popen(["paplay", "--device=speakers", {str(tmp_path / "tone.wav")!r}])
got, t0 = [], time.time()
while time.time() - t0 < 3.5:
    time.sleep(0.1)
    got.append(a.read(1600))
a.stop(); p.kill()
x = np.concatenate(got)
loud = np.flatnonzero(np.abs(x) > 0.05)
x = x[loud[0] + 1600:loud[0] + 1600 + 16000] if len(loud) else x[:0]  # 1 s of steady tone, no silence cut out
spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) if len(x) else np.zeros(1)
print(float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0, float(np.argmax(spec) * 16000 / max(len(x), 1)))
"""
    (tmp_path / "probe.py").write_text(probe)
    out = subprocess.run([sys.executable, str(tmp_path / "probe.py")], env=pulse, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    rms, freq = map(float, out.stdout.split())
    assert rms > 0.1, rms  # 0.3 sine → rms ≈ 0.21
    assert abs(freq - 440) < 5, freq  # right pitch = right sample rate after resampling


@pytest.mark.parametrize("chunk", [4800, 4096, 1024, 441])
def test_microphone_audio_is_converted_cleanly_in_any_chunk_size(chunk):
    """48 kHz microphone → 16 kHz in the chunks the system hands over: no click at each border, nothing above 8 kHz
    folds back into the voice. (The old chunk-by-chunk straight lines left errors as loud as the voice.)"""
    sr = 48000
    t = np.arange(sr * 2) / sr
    voice = 0.3 * np.sin(2 * np.pi * 440 * t) + 0.2 * np.sin(2 * np.pi * 1700 * t)
    x = (voice + 0.1 * np.sin(2 * np.pi * 12000 * t)).astype(np.float32)  # hiss above 8 kHz must vanish
    rs = audio.Resampler(sr)
    y = np.concatenate([rs(x[i:i + chunk]) for i in range(0, len(x), chunk)] + [rs.flush()])
    t16 = np.arange(16000 * 2) / 16000
    ref = (0.3 * np.sin(2 * np.pi * 440 * t16) + 0.2 * np.sin(2 * np.pi * 1700 * t16)).astype(np.float32)
    n = min(len(y), len(ref)) - 1000
    snr = max(10 * np.log10(np.sum(ref[500:n] ** 2) / np.sum((y[500 + lag:n + lag] - ref[500:n]) ** 2)) for lag in range(40))
    assert snr > 60, snr
