"""Speech models: one click loads them (with progress right away), a missing one never stops the work if another is
there, and a failed download says in words why. No network: the download itself is faked."""
import threading
import urllib.error

import pytest

from rekord import config, models
from rekord.engines import asr


@pytest.fixture
def no_models(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path / "models")
    models._progress.clear()
    yield tmp_path / "models"
    models._progress.clear()


def test_needed_and_missing(no_models):
    s = {"asr_engine": "sherpa", "asr_model": "whisper-small", "embedding_model": "campplus"}
    assert models.needed(s) == models.ESSENTIAL + ["campplus", "whisper-small"]
    assert models.missing(s) == models.needed(s)
    assert "whisper-small" not in models.needed({**s, "asr_engine": "faster-whisper"})


def test_progress_shows_right_after_the_click(no_models, monkeypatch):
    """The window asks for the progress immediately – before the download thread got going. It must already say so."""
    gate = threading.Event()
    monkeypatch.setattr(models, "download", lambda mid, on_progress=None: gate.wait(5))
    models.download_async("whisper-tiny")
    st = next(m for m in models.status() if m["id"] == "whisper-tiny")
    assert st["progress"]["state"] == "downloading" and st["progress"]["total"] > 0
    gate.set()


def test_load_everything_missing_in_one_go(no_models, monkeypatch):
    loaded = []
    monkeypatch.setattr(models, "download", lambda mid, on_progress=None: loaded.append(mid))
    s = {"asr_engine": "sherpa", "asr_model": "whisper-base", "embedding_model": "eres2net-base"}
    todo = models.download_missing_async(s)
    assert todo == models.ESSENTIAL + ["whisper-base"]
    for _ in range(100):
        if len(loaded) == len(todo):
            break
        threading.Event().wait(0.02)
    assert loaded == todo


def test_failed_download_says_why(no_models, monkeypatch):
    def offline(*a, **k):
        raise urllib.error.URLError("nodename nor servname provided")
    monkeypatch.setattr(models.urllib.request, "urlopen", offline)
    with pytest.raises(models.Missing) as e:
        models.ensure(["whisper-tiny"])
    assert "Whisper tiny" in str(e.value) and "Keine Verbindung" in str(e.value) and "Einstellungen → Modelle" in str(e.value)
    st = next(m for m in models.status() if m["id"] == "whisper-tiny")
    assert st["progress"]["state"] == "error" and "Keine Verbindung" in st["progress"]["error"]
    assert not list(no_models.glob("*.part"))  # nothing half-loaded left behind


def test_friendly_errors():
    import errno
    assert "Platz" in models.friendly(OSError(errno.ENOSPC, "No space left on device"))
    assert "404" in models.friendly(urllib.error.HTTPError("u", 404, "Not Found", {}, None))
    assert "Verbindung" in models.friendly(TimeoutError())


def test_a_missing_speech_model_falls_back_to_one_that_is_there(no_models):
    assert models.usable_asr("whisper-small") == "whisper-small"  # nothing there: the chosen one (gets loaded)
    spec = models.REGISTRY["whisper-base"]
    d = models.model_dir(spec)
    d.mkdir(parents=True)
    for f in spec.files.values():
        (d / f).write_bytes(b"x")
    assert models.usable_asr("whisper-small") == "whisper-base"  # chosen one not loaded yet: use what's there
    assert models.usable_asr("whisper-base") == "whisper-base"


def test_engine_uses_the_fallback(no_models, monkeypatch):
    made = []
    monkeypatch.setattr(asr, "_sherpa", lambda mid, lang, thr: made.append(mid) or object())
    monkeypatch.setattr(models, "usable_asr", lambda mid: "whisper-base")
    asr.get_engine({"asr_engine": "sherpa", "asr_model": "whisper-small", "language": "", "threads": 2})
    assert made == ["whisper-base"]


def test_api_loads_what_is_missing(monkeypatch):
    from fastapi.testclient import TestClient

    from rekord.server import app
    calls = []
    monkeypatch.setattr(models, "download_missing_async", lambda s: calls.append(1) or ["whisper-small"])
    app.state.auto_download = False
    with TestClient(app) as c:
        assert c.post("/api/models/download-missing").json() == {"ok": True, "loading": ["whisper-small"]}
        assert "missing" in c.get("/api/status").json()
    assert calls == [1]
