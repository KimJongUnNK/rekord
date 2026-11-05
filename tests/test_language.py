"""Language: "Automatisch" per sentence, but short sentences (where Whisper guesses English for "Ja, passt.") get the
recording's main language; English-only models never used for German. No models needed."""
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


def test_old_mixed_setting_means_automatic():
    assert asr.whisper_language({"language": "mixed"}) == ""
    assert asr.whisper_language({"language": "de"}) == "de"


def _seg(a, b, lang, text="x"):
    return {"start": a, "end": b, "lang": f"<|{lang}|>", "text": text, "label": 0}


def test_main_language_comes_from_the_longer_sentences():
    segs = [_seg(0, 1, "en"), _seg(1, 9, "de"), _seg(9, 10, "en"), _seg(10, 16, "en"), _seg(16, 30, "de")]
    assert asr.main_language(segs) == "de"  # 22 s German vs 6 s English among the long ones
    assert asr.main_language([_seg(0, 1, "fr"), _seg(1, 2, "fr"), _seg(2, 3, "de")]) == "fr"  # none long: all count
    assert asr.main_language([]) == ""


def test_short_sentences_get_the_main_language_long_ones_keep_theirs(monkeypatch):
    used = []

    class Main:
        def transcribe_clip(self, clip):
            return "Ja, passt.", "<|de|>"
    monkeypatch.setattr(asr, "get_engine", lambda s: used.append(s["language"]) or Main())
    segs = [_seg(0, 9, "de", "Heute geht es ums Budget."),
            _seg(9, 10.5, "en", "Yes, fits."),                          # short, guessed English → German
            _seg(11, 19, "en", "The headliner confirmed the date."),   # long English: a real English sentence
            _seg(19, 30, "de", "Gut, dann machen wir das so.")]
    n = asr.fix_short_languages(segs, np.zeros(asr.SR * 31, dtype=np.float32), {"language": ""})
    assert n == 1 and used == ["de"]
    assert segs[1]["text"] == "Ja, passt." and segs[1]["lang"] == "de"
    assert segs[2]["text"] == "The headliner confirmed the date."  # mixed meetings stay mixed


def test_live_short_sentences_use_the_main_language(monkeypatch):
    made = []
    monkeypatch.setattr(asr, "get_engine", lambda s: made.append(s["language"]) or object())
    sess = live.LiveSession.__new__(live.LiveSession)
    sess.s, sess.rid, sess._langs, sess._main = {"language": "", "threads": 4}, "x", {}, None
    sess._note_language("<|de|>", 6)
    sess._note_language("<|en|>", 5)
    assert not made  # 11 s: not yet sure
    sess._note_language("<|de|>", 6)
    assert made == ["de"] and sess._main is not None  # 12 of 17 s German
    sess._note_language("<|en|>", 30)
    assert made == ["de"]  # decided
    fixed = live.LiveSession.__new__(live.LiveSession)
    fixed.s, fixed._langs, fixed._main = {"language": "de"}, {}, None
    fixed._note_language("<|en|>", 30)
    assert fixed._langs == {} and fixed._main is None  # a fixed language needs none of this


def test_ollama_errors_in_words():
    from rekord.llm import providers
    m = providers.ollama_error(500, '{"error":"model requires more system memory (21.3 GiB) than is available (9.1 GiB)"}', "qwen3:30b")
    assert "21.3 GiB" in m and "kleineres Modell" in m and "qwen3:30b" in m
    assert "zu alt" in providers.ollama_error(500, '{"error":"unknown model architecture: qwen3"}', "x")
    assert "abgestürzt" in providers.ollama_error(500, '{"error":"llama runner process has terminated: exit status 2"}', "x")
    assert "neu starten" in providers.ollama_error(500, "Internal Server Error", "x")
