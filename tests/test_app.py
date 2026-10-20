"""The native window (Qt Quick): the bridge to the engine, and every page rendered without QML warnings."""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from rekord import config, db, jobs, live, pipeline  # noqa: E402
from rekord.app import bridge  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qt():
    """One Qt app without a screen. The variable is put back afterwards: other tests start REKORD processes."""
    old = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QGuiApplication.instance() or QGuiApplication(["rekord-test"])
    yield app
    if old is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = old


def pump(cond=lambda: False, timeout: float = 3.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def test_formatting():
    assert bridge.fmt_dur(0) == "0:00" and bridge.fmt_dur(75) == "1:15" and bridge.fmt_dur(3725) == "1:02:05"
    assert bridge.fmt_date(time.time()).startswith("Heute · ")
    assert bridge.fmt_date(time.time() - 86400).startswith("Gestern · ")
    assert bridge.fmt_date(None) == ""


def test_library_lists_searches_and_follows_processing(qt):
    lib = bridge.Library()
    rec = db.create_recording("Budgetrunde Q3", "", source="live", duration=125, status="done")
    other = db.create_recording("Kaffeeplausch", "", source="import", duration=60, status="queued")
    db.update_recording(other["id"], folder="Privat")
    lib.refresh()
    rows = {r["rid"]: r for r in lib.model.items()}
    assert rows[rec["id"]]["durationText"] == "2:05" and rows[other["id"]]["statusText"] == "Wartet …"
    assert "Privat" in lib.folders
    lib.setFolder("Privat")
    assert [r["rid"] for r in lib.model.items()] == [other["id"]]
    lib.setFolder("")
    lib.search("budget")
    assert pump(lambda: [r["rid"] for r in lib.model.items()] == [rec["id"]])
    lib.search("")
    assert pump(lambda: lib.model.count >= 2)
    # processing events arrive on the worker thread and update just that row
    threading.Thread(target=jobs.emit, args=({"type": "progress", "id": other["id"], "stage": "Transkription", "progress": 0.5},)).start()
    assert pump(lambda: next(r for r in lib.model.items() if r["rid"] == other["id"])["statusText"] == "Transkription · 50 %")


def test_import_copies_and_queues(qt, tmp_path, monkeypatch):
    lib = bridge.Library()
    queued, toasts = [], []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    lib.toast.connect(toasts.append)
    (tmp_path / "Interview.m4a").write_bytes(b"\0" * 64)
    (tmp_path / "notizen.txt").write_text("kein Audio")
    n = lib.importFiles([(tmp_path / "Interview.m4a").as_uri(), str(tmp_path / "notizen.txt")])
    assert n == 1 and len(queued) == 1
    rec = db.get_recording(queued[0])
    assert rec["title"] == "Interview" and rec["source"] == "import" and Path(rec["audio_path"]).is_file()
    assert Path(rec["audio_path"]).parent == config.AUDIO_DIR
    assert toasts == ["1 Datei wird verarbeitet", "Nicht unterstützt: notizen.txt"]


class FakeSession:
    made: list = []

    def __init__(self, emit, title, source, sample_rate, participants, guests, meeting, call_audio):
        self.emit, self.title, self.sample_rate = emit, title, sample_rate
        self.participants, self.guests, self.meeting, self.call_audio = participants, guests, meeting, call_audio
        self.rid = db.create_recording(title, "", source=source, status="recording")["id"]
        self.call, self.notes, self.paused, self._closed = None, [], False, False
        self.audio = bytearray()
        self.named = []
        FakeSession.made.append(self)

    def feed_pcm16(self, data):
        self.audio += data

    def highlight(self):
        self.emit({"type": "highlight", "t": 1.0})

    def name_speaker(self, key, name):
        self.named.append((key, name))

    def stop(self):
        self._closed = True
        return self.rid


@pytest.fixture
def fake_live(qt, monkeypatch):
    FakeSession.made = []
    monkeypatch.setattr(live, "LiveSession", FakeSession)
    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": True)
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)
    monkeypatch.setattr(bridge.Live, "callAvailable", property(lambda self: True))
    return bridge.Live()


def test_live_recording_from_start_to_saved(fake_live):
    lv = fake_live
    lisa = db.create_profile("Lisa", np.ones(192, dtype=np.float32), color="#3B82F6")
    finished = []
    lv.finished.connect(finished.append)
    chunk = (np.sin(np.arange(1600) / 16000 * 2 * np.pi * 200) * 8000).astype("<i2").tobytes()
    lv.start("Jour fixe", "online", [lisa], 4)
    assert lv.state == "starting"
    lv._on_chunk(chunk, 16000)  # said while the models load: kept, not lost
    assert pump(lambda: lv.state == "recording")
    s = FakeSession.made[-1]
    assert (s.title, s.meeting, s.participants, s.guests, s.call_audio) == ("Jour fixe", "online", [lisa], 3, True)
    assert config.load()["desktop"]["who"] == {"meeting": "online", "ids": [lisa], "total": 4}
    lv._on_chunk(chunk, 16000)
    assert pump(lambda: len(s.audio) == 2 * len(chunk))
    assert lv.level > 0.1
    # engine events from its own threads
    for ev in ({"type": "speaking", "key": 0, "name": "Lisa", "color": "#3B82F6", "known": True},
               {"type": "segment", "key": 0, "name": "Lisa", "color": "#3B82F6", "known": True, "start": 61, "end": 64, "text": "Hallo zusammen."},
               {"type": "speakers", "items": [{"key": 0, "name": "Lisa", "color": "#3B82F6", "known": True, "talk": 30},
                                              {"key": 3, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR, "known": False, "talk": 10, "voices": 2}]}):
        threading.Thread(target=s.emit, args=(ev,)).start()
    assert pump(lambda: len(lv.roster) == 2 and lv.lines.count == 1)
    assert lv.speaking["name"] == "Lisa"
    assert lv.lines.items()[0]["time"] == "1:01"
    assert [(r["name"], r["share"], r["voices"]) for r in lv.roster] == [("Lisa", 0.75, 0), (pipeline.UNKNOWN, 0.25, 2)]
    lv.nameSpeaker(3, " Tom ")
    assert pump(lambda: s.named == [(3, "Tom")])
    lv.highlight()
    assert pump(lambda: lv.highlights == 1)
    lv.pause()
    assert lv.state == "paused" and s.paused
    t = lv.elapsed
    time.sleep(0.3)
    assert lv.elapsed == t  # the clock stops while paused
    lv.resume()
    assert lv.state == "recording" and not s.paused
    lv.stop()
    assert pump(lambda: finished == [s.rid], timeout=5)
    assert lv.state == "idle" and s._closed and lv.speaking == {}


def test_live_lecture_counts_nobody_and_room_without_call(fake_live, monkeypatch):
    lv = fake_live
    lv.start("VO Statistik", "lecture", [], 0)
    assert pump(lambda: lv.state == "recording")
    s = FakeSession.made[-1]
    assert (s.meeting, s.guests, s.call_audio) == ("lecture", 0, False)
    lv.stop()
    assert pump(lambda: lv.state == "idle", timeout=5)
    lv.start("", "irgendwas", [], 2)  # unknown type → in the room
    assert pump(lambda: lv.state == "recording")
    s = FakeSession.made[-1]
    assert s.meeting == "person" and s.guests == 2 and s.title.startswith("Meeting ")
    assert lv.stopForQuit() is True
    assert pump(lambda: lv.state == "idle", timeout=5)
    assert lv.stopForQuit() is False


def test_live_start_failure_is_shown(fake_live, monkeypatch):
    lv = fake_live

    def broken(*a, **k):
        raise RuntimeError("Modell fehlt")
    monkeypatch.setattr(live, "LiveSession", broken)
    toasts = []
    lv.toast.connect(toasts.append)
    lv.start("x", "person", [], 2)
    assert pump(lambda: lv.state == "idle" and lv.error)
    assert "Modell fehlt" in lv.error and toasts


def test_app_state_theme_and_status(qt):
    st = bridge.AppState(8765)
    st.refresh()
    assert {"ready", "ai", "pending", "update", "live"} <= set(st.status)
    st.setTheme("dark")
    assert st.theme == "dark"
    st.setTheme("nonsense")
    assert st.theme == "system"


def test_focus_from_a_second_start_reaches_the_window(qt):
    from rekord import desktop
    st = bridge.AppState(8765)
    raised = []
    st._raise = lambda: raised.append(1)  # noqa: SLF001
    st.focusRequested.disconnect()
    st.focusRequested.connect(lambda: raised.append(1))
    desktop.window_open, desktop.focus_hook = True, st.focusRequested.emit
    try:
        threading.Thread(target=desktop.focus).start()  # the hub's thread asks
        assert pump(lambda: raised == [1])
    finally:
        desktop.window_open, desktop.focus_hook = False, None


def test_every_page_renders_without_qml_warnings(tmp_path):
    """The whole window with demo data: library, detail, who dialog, a live recording (light + dark), after stop."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", REKORD_HOME=str(tmp_path / "home"))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "ui_preview.py"), str(tmp_path / "shots")], env=env,
                       capture_output=True, text=True, timeout=180)
    report = (tmp_path / "shots" / "qml-warnings.txt")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:] + (report.read_text() if report.exists() else "")
    shots = sorted(p.name for p in (tmp_path / "shots").glob("*.png"))
    assert {"library.png", "detail.png", "who.png", "live-recording.png", "live-light.png", "after-stop.png"} <= set(shots)
    from PIL import Image
    img = Image.open(tmp_path / "shots" / "live-recording.png").convert("RGB")
    assert len(img.resize((64, 40)).getcolors(4096) or []) > 20  # a real picture, not an empty window


def test_window_selftest_mode_quits_with_result(tmp_path):
    """What CI runs against the packaged app: open, walk the pages, screenshot, quit."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", REKORD_HOME=str(tmp_path / "home"),
               REKORD_SELFTEST_UI=str(tmp_path / "shots"))
    code = "import sys; from rekord import app; sys.exit(app.run(8765))"
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "UI selftest: 7 pages, 0 QML warnings" in r.stdout
    assert len(list((tmp_path / "shots").glob("*.png"))) == 7


def test_usable_respects_classic_and_missing_display(qt, monkeypatch):
    from rekord import app
    monkeypatch.setenv("REKORD_CLASSIC", "1")
    assert app.usable() is False
    monkeypatch.delenv("REKORD_CLASSIC")
    if sys.platform.startswith("linux"):
        monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert app.usable() is False  # no screen: the hub runs, the previous interface opens in the browser


def test_microphone_without_qt_multimedia_records_through_the_system(pulse):
    """Linux without libpulse for Qt (or a broken Qt Multimedia): the window still records – via soundcard."""
    code = """
import sys, time
sys.modules["PySide6.QtMultimedia"] = None  # as if it couldn't load
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from rekord.app import bridge
app = QGuiApplication(["t"])
mic, got, errs = bridge.Mic(), [], []
mic.chunk.connect(lambda d, r: got.append((len(d), r)))
mic.failed.connect(errs.append)
assert bridge.Mic.devices() == []
assert mic.start(""), errs
end = time.time() + 12  # the sound system needs a moment to start delivering
while time.time() < end and len(got) < 5:
    QCoreApplication.processEvents(); time.sleep(0.01)
mic.stop()
print("chunks", len(got), set(r for _, r in got), errs)
sys.exit(0 if len(got) >= 5 and {r for _, r in got} == {16000} and not errs else 1)
"""
    env = dict(pulse, QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr[-2000:]


def test_voice_sample_counts_only_speech_and_writes_16k_wav(qt, monkeypatch):
    import wave
    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": True)
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)
    v = bridge.VoiceRecorder()
    done = []
    v.finished.connect(done.append)
    v.start(120)
    assert v.recording
    rate = 48000  # a typical microphone: converted to 16 kHz
    tone = (np.sin(np.arange(rate // 10) / rate * 2 * np.pi * 180) * 8000).astype("<i2").tobytes()
    quiet = np.zeros(rate // 10, dtype="<i2").tobytes()
    for _ in range(50):           # 5 s silence first: background, doesn't count
        v._on_chunk(quiet, rate)
    for _ in range(300):          # 30 s of voice
        v._on_chunk(tone, rate)
    for _ in range(30):           # 3 s pause: only the short hangover counts
        v._on_chunk(quiet, rate)
    assert 29.5 <= v.speech <= 31.0, v.speech
    assert 37.5 <= v.wall <= 38.5
    v.stop()
    assert not v.recording and done == [v.path]
    with wave.open(v.path) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        assert abs(w.getnframes() / 16000 - 38.0) < 0.2
    path = v.path
    v.discard()
    assert v.path == "" and not Path(path).exists() and v.speech == 0


def test_voice_sample_stops_by_itself(qt, monkeypatch):
    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": True)
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)
    v = bridge.VoiceRecorder()
    v.start(2)  # e.g. 120 s for reading, 240 s for free talk
    tone = (np.sin(np.arange(1600) / 16000 * 2 * np.pi * 200) * 8000).astype("<i2").tobytes()
    for _ in range(40):
        v._on_chunk(tone, 16000)
    assert not v.recording and v.path and abs(v.wall - 2.0) < 0.05
    v.discard()


def test_preferences_of_the_window(qt):
    st = bridge.AppState(8765)
    st.setPref("enroll_mode", "free")
    assert st.pref("enroll_mode") == "free" and config.load()["desktop"]["enroll_mode"] == "free"
    assert st.pref("gibts_nicht") is None


def test_accent_color_is_checked_and_kept(qt):
    st = bridge.AppState(8765)
    seen = []
    st.accentChanged.connect(lambda: seen.append(st.accent))
    st.setAccent("#2d7ff9")
    assert st.accent == "#2D7FF9" and config.load()["desktop"]["accent"] == "#2D7FF9" and seen == ["#2D7FF9"]
    for bad in ("red", "#12345", "#GGGGGG", "", "#2D7FF9; rm"):
        st.setAccent(bad)
    assert st.accent == "#2D7FF9" and len(seen) == 1
    st.setAccent("#FF5A1F")


def test_missing_drive_shows_its_path_and_welcome_state(qt, monkeypatch):
    st = bridge.AppState(8765)
    monkeypatch.setattr(config, "home_missing", lambda: True)
    st.refresh()
    assert st.status["storageMissing"] == str(config.HOME)
    monkeypatch.setattr(config, "home_missing", lambda: False)
    config.save({"welcome_done": False})
    st.refresh()
    assert st.status["storageMissing"] == "" and st.status["welcomeDone"] is False
    config.save({"welcome_done": True})


def test_update_that_cant_install_itself_opens_the_settings(qt, monkeypatch):
    from rekord import updater
    st = bridge.AppState(8765)
    went = []
    st.navigate.connect(lambda p, s: went.append((p, s)))
    monkeypatch.setattr(updater, "info", lambda: {"can_install": False})
    st.installUpdate()
    assert went == [("settings", "data")]


def test_voice_level_starts_at_zero_again(qt, monkeypatch):
    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": True)
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)
    v = bridge.VoiceRecorder()
    v.start(60)
    pump(lambda: v.recording)
    loud = (np.sin(np.arange(4800) / 48000 * 2 * np.pi * 200) * 20000).astype("<i2").tobytes()
    v._on_chunk(loud, 48000)  # noqa: SLF001
    assert v.level > 0.2
    v.discard()
    assert v.level == 0.0 and not v.recording


def test_keeping_the_computer_awake(monkeypatch):
    from rekord import system
    started, stopped = [], []

    class Proc:
        def __init__(self, cmd, **kw):
            started.append(cmd)

        def terminate(self):
            stopped.append(1)
    monkeypatch.setattr(system.sys, "platform", "linux")
    monkeypatch.setattr(system.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(system.subprocess, "Popen", Proc)
    assert system.keep_awake(True)
    assert started[0][0] == "systemd-inhibit" and f"--pid={os.getpid()}" in started[0]  # ends with REKORD, even after a crash
    assert system.keep_awake(False) and stopped == [1]
    monkeypatch.setattr(system.sys, "platform", "darwin")
    assert system.keep_awake(True) and started[1][:2] == ["caffeinate", "-i"]
    system.keep_awake(False)
    monkeypatch.setattr(system.shutil, "which", lambda name: None)
    assert system.keep_awake(True) is False  # nothing to keep it awake with: recording works anyway


def test_quitting_ends_the_process_without_python_teardown(monkeypatch):
    from rekord import desktop
    ended = []
    monkeypatch.setattr(desktop.os, "_exit", lambda code: ended.append(code))
    desktop._end()  # noqa: SLF001
    assert ended == [0]
