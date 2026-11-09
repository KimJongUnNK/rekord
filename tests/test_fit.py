"""Fits the computer and the recording: the speech model REKORD picks for this machine, and quiet recordings made
louder before transcribing (the stored file stays as it is)."""
import numpy as np
import pytest

from rekord import audio, config, models

SR = audio.SR


def _speech(amp: float, seconds: float = 6.0) -> np.ndarray:
    """Talk-like: 1 s of tone, 0.5 s pause, repeated."""
    t = np.arange(int(SR * seconds)) / SR
    on = (t % 1.5) < 1.0
    return (np.sin(2 * np.pi * 220 * t) * amp * on).astype(np.float32)


# ------------------------------------------------------------------ louder

def test_quiet_recording_is_lifted_to_speech_level():
    x = _speech(0.01)  # a phone at the back of the room
    y, gain = audio.boost(x)
    assert gain > 5 and y.dtype == np.float32 and len(y) == len(x)
    assert abs(audio.speech_level(y) - audio.SPEECH_LEVEL) < 0.02
    assert x.max() == pytest.approx(0.01, abs=1e-4)  # the original stays untouched


def test_loud_enough_stays_as_it_is():
    x = _speech(0.3)
    y, gain = audio.boost(x)
    assert gain == 1.0 and y is x  # never made quieter, nothing copied


def test_silence_and_whisper_quiet_are_capped():
    silent = np.zeros(SR * 3, np.float32)
    assert audio.boost(silent) == (silent, 1.0)
    barely = _speech(0.0005)
    _, gain = audio.boost(barely)
    assert gain == pytest.approx(audio.MAX_GAIN)  # at most +30 dB: more would only lift the noise


def test_peaks_are_limited_not_clipped():
    x = _speech(0.02)
    x[SR // 2] = 0.2  # a cough: 10x louder than the speech
    y, gain = audio.boost(x)
    assert gain > 1 and np.abs(y).max() <= 1.0
    assert np.abs(y).max() > 0.9  # still the loudest moment, just softly limited


def test_the_analysis_hears_the_louder_audio_the_file_stays(monkeypatch, tmp_path):
    from rekord import db, pipeline

    class Seen(Exception):
        pass
    heard = {}

    def diarize(samples, *a, **k):
        heard["level"] = audio.speech_level(samples)
        raise Seen
    wav = tmp_path / "leise.wav"
    audio.write_wav(wav, _speech(0.01))
    rec = db.create_recording("Leise Vorlesung", "", source="import")
    db.update_recording(rec["id"], audio_path=str(wav))
    monkeypatch.setattr(models, "ensure", lambda *a, **k: None)
    monkeypatch.setattr(models, "usable_asr", lambda m: m)
    monkeypatch.setattr(pipeline, "diarize", diarize)
    stages = []
    real_update = db.update_recording
    monkeypatch.setattr(db, "update_recording", lambda rid, **kw: (stages.append(kw.get("stage")), real_update(rid, **kw))[1])
    with pytest.raises(Seen):
        pipeline.process(rec["id"])
    assert abs(heard["level"] - audio.SPEECH_LEVEL) < 0.02  # speaker separation and Whisper get speech level
    assert audio.speech_level(audio.load(wav)) < 0.02  # the stored recording is untouched
    assert any(st and st.startswith("Lautstärke angepasst: +") and st.endswith(" dB") for st in stages)  # shown in the progress
    # Einstellungen → Transkription → off: the analysis hears the recording as it is
    monkeypatch.setattr(pipeline.config, "load", lambda: config.DEFAULTS | {"boost_quiet": False})
    with pytest.raises(Seen):
        pipeline.process(rec["id"])
    assert heard["level"] < 0.02
    db.update_recording(rec["id"], status="done")


def test_the_live_text_hears_the_louder_audio_too():
    """Every way to a transcript lifts a quiet room: the analysis after Stopp (import, drag-in, inbox folder,
    appending, merging, transcribing again and the CLI all go through pipeline.process) – and the live text."""
    import threading

    from rekord import live
    heard = []

    class Eng:
        def transcribe_clip(self, clip):
            heard.append(audio.speech_level(clip))
            return "hallo", "de"
    s = live.LiveSession.__new__(live.LiveSession)
    s.s, s.engine, s._main, s._lock, s.segments = {"vocabulary": []}, Eng(), None, threading.Lock(), []
    s._fix, s.emit, s._label = (lambda t: t), (lambda ev: None), (lambda r: {"name": "A"})
    s._note_language = lambda lang, sec: None
    quiet = _speech(0.01)
    s._segment([{"start": 0.0, "samples": quiet}], {})
    assert heard and abs(heard[-1] - audio.SPEECH_LEVEL) < 0.02
    s.s["boost_quiet"] = False
    s._segment([{"start": 0.0, "samples": quiet}], {})
    assert heard[-1] < 0.02


# ------------------------------------------------------------------ the model for this computer

@pytest.mark.parametrize("hw, model", [
    ({"ram_gb": 16, "cores": 10, "gpu": "apple"}, "whisper-turbo"),     # MacBook Air/Pro M-chip
    ({"ram_gb": 32, "cores": 16, "gpu": None}, "whisper-turbo"),        # strong PC without NVIDIA
    ({"ram_gb": 8, "cores": 8, "gpu": "apple"}, "whisper-small"),       # 8-GB Mac
    ({"ram_gb": 16, "cores": 4, "gpu": None}, "whisper-small"),         # older laptop, much RAM, few cores
    ({"ram_gb": 4, "cores": 2, "gpu": None}, "whisper-base"),           # weak machine
])
def test_recommended_speech_model(hw, model, monkeypatch):
    monkeypatch.setattr(models, "faster_whisper_available", lambda: False)
    r = models.recommend_asr({**hw, "cuda": False})
    assert r["asr_engine"] == "sherpa" and r["asr_model"] == model and r["model"] == model
    assert f"{hw['ram_gb']} GB RAM · {hw['cores']} Kerne" in r["label"] and r["name"] == models.name(model)


def test_nvidia_card_gets_faster_whisper_on_the_card(monkeypatch):
    monkeypatch.setattr(models, "faster_whisper_available", lambda: True)
    r = models.recommend_asr({"ram_gb": 32, "cores": 12, "gpu": "nvidia", "vram_gb": 8, "cuda": True})
    assert r["asr_engine"] == "faster-whisper" and r["faster_whisper_model"] == "large-v3-turbo"
    assert "NVIDIA" in r["label"] and r["model"] == "fw:large-v3-turbo"
    small = models.recommend_asr({"ram_gb": 16, "cores": 8, "gpu": "nvidia", "vram_gb": 3, "cuda": True})
    assert small["faster_whisper_model"] == "small"  # a 3-GB card can't hold turbo
    monkeypatch.setattr(models, "faster_whisper_available", lambda: False)
    assert models.recommend_asr({"ram_gb": 32, "cores": 12, "gpu": "nvidia", "vram_gb": 8, "cuda": True})["asr_engine"] == "sherpa"


def test_applied_automatically_until_the_user_picks(monkeypatch):
    rec = {"asr_engine": "sherpa", "asr_model": "whisper-turbo", "faster_whisper_model": "large-v3-turbo",
           "model": "whisper-turbo", "name": "Whisper turbo", "label": "16 GB RAM · 10 Kerne · Apple-Chip"}
    monkeypatch.setattr(models, "recommend_asr", lambda hw=None: rec)
    config.save({"asr_auto": True, "asr_model": "whisper-small"})
    assert models.apply_recommended() == rec and config.load()["asr_model"] == "whisper-turbo"
    assert models.apply_recommended() is None  # already set: nothing to do
    config.save({"asr_auto": False, "asr_model": "whisper-base"})
    assert models.apply_recommended() is None and config.load()["asr_model"] == "whisper-base"  # the user's pick stays
    config.save({"asr_auto": True, "asr_model": "whisper-small"})


def test_settings_api_picking_by_hand_turns_auto_off(monkeypatch):
    from fastapi.testclient import TestClient

    from rekord.server import app
    rec = {"asr_engine": "sherpa", "asr_model": "whisper-turbo", "faster_whisper_model": "large-v3-turbo",
           "model": "whisper-turbo", "name": "Whisper turbo", "label": "16 GB RAM · 10 Kerne"}
    monkeypatch.setattr(models, "recommend_asr", lambda hw=None: rec)
    started = []
    monkeypatch.setattr(models, "download_async", started.append)
    monkeypatch.setattr(models, "installed", lambda mid: False)
    app.state.auto_download = False
    with TestClient(app) as client:
        _api_checks(client, started)
    config.save({"asr_model": "whisper-small"})


def _api_checks(client, started):
    s = client.put("/api/settings", json={"asr_model": "whisper-base"}).json()
    assert s["asr_model"] == "whisper-base" and s["asr_auto"] is False
    s = client.put("/api/settings", json={"asr_auto": True}).json()
    assert s["asr_auto"] is True and s["asr_model"] == "whisper-turbo"
    assert started == ["whisper-turbo"]  # the model that fits is loaded right away
    assert "asr_recommended" in client.get("/api/status").json()
