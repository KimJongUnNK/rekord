"""Where REKORD stores things (data folder, models folder, external drives) + the help texts + headcount clustering."""
import json
import re
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from rekord import config

ROOT = Path(__file__).resolve().parent.parent


def _wait_job():
    from rekord import storage
    for _ in range(200):
        j = storage.job()
        if j["state"] in ("done", "error", "idle"):
            return j
        time.sleep(0.05)
    return storage.job()


def test_drives_always_offer_this_computer():
    from rekord import storage
    ds = storage.drives()
    assert ds and ds[0]["kind"] == "internal" and ds[0]["free_gb"] > 0
    assert all({"path", "name", "kind_label", "free_gb", "writable"} <= set(d) for d in ds)
    assert storage.suggest(str(Path.home()))["home"] == str(config.DEFAULT_HOME)
    t7 = Path("/Volumes/T7")
    assert storage.suggest(str(t7)) == {"home": str(t7 / "Rekord"), "models": str(t7 / "Rekord" / "models")}


def test_pointer_file_decides_the_data_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("REKORD_HOME", raising=False)
    monkeypatch.setattr(config, "pointer_path", lambda: tmp_path / "cfg" / "location.json")
    assert config._home() == (config.DEFAULT_HOME, False)
    from rekord import storage
    storage.set_pointer(tmp_path / "ext" / "Rekord")
    assert config._home() == (tmp_path / "ext" / "Rekord", True)
    storage.set_pointer(config.DEFAULT_HOME)  # back to the default → no pointer at all
    assert not (tmp_path / "cfg" / "location.json").exists()


def test_unplugged_drive_is_detected_not_recreated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path / "gone-drive" / "Rekord")
    monkeypatch.setattr(config, "CUSTOM_HOME", True)
    assert config.home_missing()
    with pytest.raises(config.StorageMissing):
        config.ensure_dirs()
    assert not (tmp_path / "gone-drive").exists()  # nothing created on the internal disk
    monkeypatch.setattr(config, "CUSTOM_HOME", False)
    assert not config.home_missing()


def test_move_models_to_another_drive(tmp_path, monkeypatch):
    from rekord import storage
    from rekord.llm import ollama
    old = config.MODELS_DIR
    (old / "probe").mkdir(parents=True, exist_ok=True)
    (old / "probe" / "model.onnx").write_bytes(b"x" * 4096)
    monkeypatch.setattr(ollama, "stop", lambda: None)
    monkeypatch.setattr(ollama, "apply_models_dir", lambda base=None: None)
    monkeypatch.setattr(storage, "ollama_dir", lambda: tmp_path / "no-ollama")
    target = tmp_path / "T7" / "REKORD-Modelle"
    storage.move_models(str(target), take_ollama=True)
    j = _wait_job()
    assert j["state"] == "done", j
    assert (target / "probe" / "model.onnx").read_bytes() == b"x" * 4096
    assert config.MODELS_DIR == target and config.load()["models_dir"] == str(target)
    assert config.ollama_models_dir() == target / "ollama"
    assert not (old / "probe").exists()
    # and back home
    storage.move_models(str(config.HOME / "models"))
    assert _wait_job()["state"] == "done"
    assert config.load()["models_dir"] == "" and config.ollama_models_dir() is None
    assert (config.HOME / "models" / "probe" / "model.onnx").exists()


def test_move_refuses_while_recording(monkeypatch, tmp_path):
    from rekord import live, storage
    monkeypatch.delenv("REKORD_HOME", raising=False)
    monkeypatch.setattr(live, "active", lambda: [{"id": "x"}])
    with pytest.raises(RuntimeError, match="Aufnahme"):
        storage.move_models(str(tmp_path / "x"))
    with pytest.raises(RuntimeError, match="Aufnahme"):
        storage.move_home(str(tmp_path / "y"))


def test_move_home_copies_db_and_rewrites_audio_paths(tmp_path, monkeypatch):
    from rekord import db, storage
    monkeypatch.delenv("REKORD_HOME", raising=False)
    monkeypatch.setattr(config, "pointer_path", lambda: tmp_path / "cfg" / "location.json")
    restarted = threading.Event()
    monkeypatch.setattr(storage, "schedule_restart", lambda delay=1.5: restarted.set())
    audio_file = config.AUDIO_DIR / "move-test.wav"
    audio_file.write_bytes(b"RIFF....")
    rec = db.create_recording("Umzug", str(audio_file))
    new = tmp_path / "NAS" / "Rekord"
    storage.move_home(str(new))
    j = _wait_job()
    assert j["state"] == "done" and j["restart"], j
    assert restarted.is_set()
    assert json.loads((tmp_path / "cfg" / "location.json").read_text())["home"] == str(new)
    assert (new / "audio" / "move-test.wav").exists() and (config.HOME / "MOVED-TO.txt").exists()
    import sqlite3
    c = sqlite3.connect(new / "rekord.db")
    path = c.execute("SELECT audio_path FROM recordings WHERE id=?", (rec["id"],)).fetchone()[0]
    assert path == str(new / "audio" / "move-test.wav")
    assert json.loads((new / "settings.json").read_text())["storage_chosen"] is True
    (config.HOME / "MOVED-TO.txt").unlink()
    with pytest.raises(RuntimeError, match="alten Datenordner"):
        storage.move_home(str(config.HOME / "inside"))


def test_existing_installs_are_not_asked_again(tmp_path, monkeypatch):
    s = json.loads(config.SETTINGS_PATH.read_text())
    s.pop("storage_chosen", None)
    s.pop("welcome_done", None)
    config.SETTINGS_PATH.write_text(json.dumps(s))
    config.reset_cache()
    loaded = config.load()
    assert loaded["storage_chosen"] is True and loaded["welcome_done"] is True


def test_headcount_caps_live_voices():
    from rekord.engines import voiceprint
    rng = np.random.default_rng(3)
    voices = [voiceprint.normalize(rng.normal(size=192)) for _ in range(4)]
    c = voiceprint.OnlineClusterer([], 0.6, 0.6, max_speakers=2)
    keys = {c.assign(voiceprint.normalize(v + rng.normal(scale=0.05, size=192)))["key"] for v in voices}
    assert len(keys) == 2 and len(c.clusters) == 2  # 4 different-sounding voices, 2 people announced
    free = voiceprint.OnlineClusterer([], 0.6, 0.6)
    assert len({free.assign(v)["key"] for v in voices}) == 4


# ------------------------------------------------------------------ ⓘ help texts

def _tips():
    help_js = (ROOT / "rekord/web/help.js").read_text("utf-8")
    return set(re.findall(r"^\s{2}(\w+): \"", help_js, re.M))


def test_every_tip_used_exists():
    used = set()
    for f in ("app.js", "welcome.js"):
        used |= set(re.findall(r'tip\("(\w+)"\)', (ROOT / "rekord/web" / f).read_text("utf-8")))
    app = (ROOT / "rekord/web/app.js").read_text("utf-8")
    used |= {"noiseSuppression", "echoCancellation", "autoGainControl"}  # tip(k) in the audio-processing loop
    assert "${tip(k)}" in app
    assert used - _tips() == set(), used - _tips()


def test_every_settings_field_has_an_info_tip():
    app = (ROOT / "rekord/web/app.js").read_text("utf-8")
    labels = re.findall(r'class="field"><(?:div class="lbl"|label[^>]*)>(.*?)(?:<span class="hint"|</div>|</label>)', app)
    assert len(labels) > 35
    missing = [l for l in labels if "${tip(" not in l and "${label}" not in l]
    assert not missing, f"Einstellungen ohne ⓘ: {missing}"
