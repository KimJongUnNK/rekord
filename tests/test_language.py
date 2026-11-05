"""Language: detected once per recording (per short sentence Whisper guesses English and writes English), "Gemischt"
for per-sentence detection, and English-only models never used for German. No models needed."""
import numpy as np

from rekord import live, models
from rekord.engines import asr


def test_english_only_models_are_never_used_for_german(monkeypatch):
    monkeypatch.setattr(models, "installed", lambda m: m == "whisper-small")
    s = {"asr_engine": "sherpa", "asr_model": "whisper-distil-large-v3", "language": "de"}
    assert models.for_language(s)["asr_model"] == "whisper-small"  # a multilingual one that's there
    assert models.for_language({**s, "language": ""})["asr_model"] == "whisper-small"  # auto: could be anything
    assert models.for_language({**s, "language": "en"})["asr_model"] == "whisper-distil-large-v3"  # English: fine
    monkeypatch.setattr(models, "installed", lambda m: False)
    assert models.for_language(s)["asr_model"] == "whisper-turbo"  # nothing there: turbo gets loaded
    monkeypatch.setattr(models, "faster_whisper_available", lambda: True)
    fw = {"asr_engine": "faster-whisper", "faster_whisper_model": "distil-large-v3", "language": "de", "asr_model": "whisper-small"}
    assert models.for_language(fw)["faster_whisper_model"] == "large-v3-turbo"
    assert models.needed(fw)[-1] == "fw:large-v3-turbo"


def test_mixed_means_per_sentence_for_the_engine():
    assert asr.whisper_language({"language": "mixed"}) == ""
    assert asr.whisper_language({"language": "de"}) == "de"
    assert asr.whisper_language({"language": ""}) == ""


def test_language_is_detected_once_from_the_longest_turns(monkeypatch):
    calls = []

    class Fake:
        def transcribe_clip(self, clip):
            calls.append(len(clip) / asr.SR)
            # long clips are clearly German; a short "Okay." would be guessed English
            return "…", "<|de|>" if len(clip) / asr.SR > 3 else "<|en|>"
    monkeypatch.setattr(asr, "get_engine", lambda s: Fake())
    samples = np.zeros(asr.SR * 120, dtype=np.float32)
    turns = [(0, 1.0, 0), (1, 13, 1), (13, 14, 0), (14, 44, 1), (44, 45.2, 0), (50, 58, 2)]
    assert asr.detect_language(samples, turns, {"language": ""}) == "de"
    assert calls[0] == asr.MAX_CHUNK  # the longest first (cut to the 30 s window)
    assert len(calls) == 3  # turns under 1.5 s don't count


def test_live_settles_on_a_language(monkeypatch):
    made = []
    monkeypatch.setattr(asr, "get_engine", lambda s: made.append(s["language"]) or object())
    sess = live.LiveSession.__new__(live.LiveSession)
    sess.s, sess.rid, sess._langs, sess._lang_locked = {"language": "", "threads": 4}, "x", {}, False
    sess.engine = "auto"
    sess._note_language("<|de|>", 6)
    sess._note_language("<|en|>", 1)  # a short "Okay." guessed English
    sess._note_language("<|de|>", 5)
    assert not made  # 12 s: not yet sure
    sess._note_language("<|de|>", 4)
    assert made == ["de"] and sess._lang_locked
    sess._note_language("<|en|>", 30)
    assert made == ["de"]  # stays
    fixed = live.LiveSession.__new__(live.LiveSession)
    fixed.s, fixed._langs, fixed._lang_locked = {"language": "de"}, {}, True
    fixed._note_language("<|en|>", 30)
    assert fixed._langs == {}
