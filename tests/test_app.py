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
    assert toasts[0] == "1 Datei wird verarbeitet" and toasts[1].startswith("Kein Ton gefunden: notizen.txt")


def test_import_mp3_and_mp4_from_downloads(qt, tmp_path, monkeypatch):
    """MP3 and MP4 (a video: only its sound counts) are real recordings – decodable and queued for transcription."""
    import av

    from rekord import audio
    lib = bridge.Library()
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    x = (audio.load(Path(__file__).parent / "fixtures" / "meeting1.wav")[:16000 * 3] * 32767).astype(np.int16)
    for name, fmt, codec in (("Sprachnachricht.mp3", "mp3", "libmp3lame"), ("Zoom Aufzeichnung.mp4", "mp4", "aac")):
        with av.open(str(tmp_path / name), "w", format=fmt) as out:
            st = out.add_stream(codec, rate=16000)
            st.layout = "mono"
            fr = av.AudioFrame.from_ndarray(x.reshape(1, -1), format="s16", layout="mono")
            fr.sample_rate = 16000
            for pk in [*st.encode(fr), *st.encode(None)]:
                out.mux(pk)
    assert lib.importFiles([(tmp_path / "Sprachnachricht.mp3").as_uri(), (tmp_path / "Zoom Aufzeichnung.mp4").as_uri()]) == 2
    recs = [db.get_recording(r) for r in queued]
    assert [r["title"] for r in recs] == ["Sprachnachricht", "Zoom Aufzeichnung"]
    for r in recs:
        assert 2.9 < len(audio.load(r["audio_path"])) / 16000 < 3.2  # the pipeline reads it like any recording


def test_import_says_why_a_file_cant_be_read(qt, tmp_path, monkeypatch):
    """macOS refusing the Downloads folder (or a file that's gone) must not end the import silently."""
    import shutil
    import sys
    lib = bridge.Library()
    queued, toasts = [], []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    lib.toast.connect(toasts.append)
    (tmp_path / "ok.mp3").write_bytes(b"\0" * 64)
    (tmp_path / "gesperrt.mp4").write_bytes(b"\0" * 64)
    real = shutil.copyfile

    def copy(src, dst):
        if Path(src).name == "gesperrt.mp4":
            raise PermissionError(1, "Operation not permitted")
        return real(src, dst)
    monkeypatch.setattr(bridge.shutil, "copyfile", copy)
    monkeypatch.setattr(sys, "platform", "darwin")
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    before = set(config.AUDIO_DIR.iterdir())
    assert lib.importFiles([str(tmp_path / "gesperrt.mp4"), str(tmp_path / "ok.mp3"), str(tmp_path / "weg.mp3")]) == 1
    assert len(queued) == 1  # the readable one goes through
    assert any("Kein Zugriff auf gesperrt.mp4, weg.mp3" in t and "Dateien und Ordner" in t for t in toasts), toasts
    new = set(config.AUDIO_DIR.iterdir()) - before
    assert [p.suffix for p in new] == [".mp3"]  # only the readable one – no half-copied leftovers


def test_paste_imports_files_copied_in_finder_or_explorer(qt, tmp_path, monkeypatch):
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QGuiApplication
    lib = bridge.Library()
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    (tmp_path / "Podcast.mp3").write_bytes(b"\0" * 64)
    cb = QGuiApplication.clipboard()
    data = QMimeData()
    data.setUrls([QUrl.fromLocalFile(str(tmp_path / "Podcast.mp3"))])
    cb.setMimeData(data)
    if not cb.mimeData().urls():
        pytest.skip("no clipboard on this platform/session")
    assert lib.pasteFiles() == 1 and db.get_recording(queued[0])["title"] == "Podcast"
    cb.setText(str(tmp_path / "Podcast.mp3"))  # "Als Pfad kopieren" (Windows) / ⌥⌘C (Mac)
    assert lib.pasteFiles() == 1 and len(queued) == 2
    cb.setText("nur ein Satz, keine Datei")
    assert lib.pasteFiles() == 0 and len(queued) == 2  # ordinary text: nothing happens


def test_append_files_to_an_open_recording(qt, tmp_path, monkeypatch):
    from rekord import pipeline
    lib = bridge.Library()
    added, queued, toasts = [], [], []
    monkeypatch.setattr(pipeline, "append_files", lambda rid, paths: added.append((rid, [Path(p).name for p in paths])) or 95.0)
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    lib.toast.connect(toasts.append)
    rec = db.create_recording("Workshop", "", source="import")
    (tmp_path / "Teil 2.mp4").write_bytes(b"\0")
    (tmp_path / "liste.pdf").write_bytes(b"\0")
    db.update_recording(rec["id"], status="processing")
    assert lib.appendFiles(rec["id"], [str(tmp_path / "Teil 2.mp4")]) == 0  # not while it's being analysed
    assert "sobald" in toasts[-1] and added == []
    db.update_recording(rec["id"], status="done")
    assert lib.appendFiles(rec["id"], [(tmp_path / "Teil 2.mp4").as_uri(), str(tmp_path / "liste.pdf")]) == 1
    assert pump(lambda: queued == [rec["id"]])
    assert added == [(rec["id"], ["Teil 2.mp4"])]
    assert any("Kein Ton gefunden: liste.pdf" in t for t in toasts)
    assert pump(lambda: any("Angehängt (+1:35)" in t and "neu transkribiert" in t for t in toasts)), toasts


def test_append_failure_is_said_not_swallowed(qt, tmp_path, monkeypatch):
    from rekord import pipeline
    lib = bridge.Library()
    toasts = []
    lib.toast.connect(toasts.append)

    def broken(rid, paths):
        raise ValueError("Datei enthält keine Audiospur")
    monkeypatch.setattr(pipeline, "append_files", broken)
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": pytest.fail("must not reprocess"))
    rec = db.create_recording("X", "", source="import")
    db.update_recording(rec["id"], status="done")
    (tmp_path / "leer.mp4").write_bytes(b"\0")
    assert lib.appendFiles(rec["id"], [str(tmp_path / "leer.mp4")]) == 1
    assert pump(lambda: any("Anhängen fehlgeschlagen: Datei enthält keine Audiospur" in t for t in toasts)), toasts


def test_one_imported_file_is_opened_right_away(qt, tmp_path, monkeypatch):
    """Fewer steps: after importing one file the window opens its recording – lastImportedId names it."""
    lib = bridge.Library()
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": None)
    (tmp_path / "a.mp3").write_bytes(b"\0")
    (tmp_path / "b.mp3").write_bytes(b"\0")
    assert lib.importFiles([str(tmp_path / "a.mp3")]) == 1
    rid = lib.lastImportedId()
    assert rid and db.get_recording(rid)["title"] == "a"
    assert lib.importFiles([str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")]) == 2
    assert lib.lastImportedId() == ""  # several: the list shows them
    assert lib.importFiles([str(tmp_path / "notiz.txt")]) == 0 and lib.lastImportedId() == ""
    import shutil
    shutil.copy(Path(__file__).parent / "fixtures" / "meeting1.wav", tmp_path / "Diktat.dss2")  # any ending, sound inside
    assert lib.importFiles([str(tmp_path / "Diktat.dss2")]) == 1 and lib.lastImportedId()


def test_import_dialog_opens_in_downloads(qt):
    url = bridge.Library().downloadsUrl
    assert url == "" or url.startswith("file://")


class FakeSession:
    made: list = []

    def __init__(self, emit, title, source, sample_rate, participants, guests, meeting, call_audio, mic=True):
        self.emit, self.title, self.sample_rate = emit, title, sample_rate
        self.participants, self.guests, self.meeting, self.call_audio = participants, guests, meeting, call_audio
        self.mic = mic or not (meeting == "online" and call_audio)  # like LiveSession: off only online with call sound
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
    yield bridge.Live()
    live._sessions.clear()  # a test that failed mid-recording must not leave its session to the next ones


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
    assert config.load()["desktop"]["who"] == {"meeting": "online", "ids": [lisa], "total": 4, "mic": True}
    assert lv.micOn and s.mic
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
    # the events come from separate threads – their order isn't guaranteed, so wait for this one too
    assert pump(lambda: lv.speaking.get("name") == "Lisa"), lv.speaking
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


def test_live_online_only_the_call_without_microphone(fake_live, monkeypatch):
    """Online, "Nur Call-Ton": the microphone is never opened (no permission, no stall/silence warnings) – the
    session gets mic=False and the meter follows the call's sound."""
    lv = fake_live
    opened = []
    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": opened.append(device_id) or True)
    asked = []
    monkeypatch.setattr(bridge.Live, "_with_mic_permission", lambda self, then: (asked.append(1), then()))
    lv.start("Webinar", "online", [], 3, False)
    assert pump(lambda: lv.state == "recording")
    s = FakeSession.made[-1]
    assert (s.meeting, s.call_audio, s.mic) == ("online", True, False)
    assert opened == [] and asked == [] and not lv.micOn  # not opened, not even asked for
    assert config.load()["desktop"]["who"]["mic"] is False  # the next "Wer ist dabei?" starts from that
    for rms in (0.1, 0.1, 0.1):
        threading.Thread(target=s.emit, args=({"type": "level", "rms": rms, "t": 1.0},)).start()
    assert pump(lambda: lv.level > 0.3)
    lv._last_chunk = time.monotonic() - 60  # no microphone chunks ever: that's expected, not a stalled microphone
    lv._quiet_from = time.monotonic() - 60
    lv._check()
    assert opened == [] and lv.micWarning == ""
    lv.setMic("usb-mic")  # choosing a microphone meanwhile doesn't switch one on
    assert opened == [] and config.load()["desktop"]["mic"] == "usb-mic"
    lv.stop()
    assert pump(lambda: lv.state == "idle", timeout=5)
    # next time with the microphone again: it's opened as before
    lv.start("Jour fixe", "online", [], 3, True)
    assert pump(lambda: lv.state == "recording")
    assert opened == ["usb-mic"] and asked == [1] and lv.micOn and FakeSession.made[-1].mic
    lv.stop()
    assert pump(lambda: lv.state == "idle", timeout=5)


def test_live_microphone_choice_only_counts_online_with_call_sound(fake_live, monkeypatch):
    lv = fake_live
    lv.start("Raum", "person", [], 2, False)  # in the room the microphone is all there is
    assert pump(lambda: lv.state == "recording")
    assert lv.micOn and FakeSession.made[-1].mic
    lv.stop()
    assert pump(lambda: lv.state == "idle", timeout=5)
    monkeypatch.setattr(bridge.Live, "callAvailable", property(lambda self: False))
    lv.start("Call", "online", [], 2, False)  # no call sound on this computer: the microphone has to hear it
    assert pump(lambda: lv.state == "recording")
    assert lv.micOn and FakeSession.made[-1].call_audio is False
    lv.stop()
    assert pump(lambda: lv.state == "idle", timeout=5)


def test_live_call_only_failure_is_shown(fake_live, monkeypatch):
    def broken(*a, **kw):
        raise RuntimeError("Call-Ton nicht verfügbar – ohne Mikrofon gibt es nichts aufzunehmen.")
    monkeypatch.setattr(live, "LiveSession", broken)
    toasts = []
    fake_live.toast.connect(toasts.append)
    fake_live.start("x", "online", [], 2, False)
    assert pump(lambda: fake_live.state == "idle" and toasts)
    assert "ohne Mikrofon" in fake_live.error


def test_mac_refusal_comes_with_buttons_that_fix_it(fake_live, monkeypatch):
    """macOS refuses although the switch may show "on": the page names which permission and offers to open exactly
    that switch or to reset it – no "go to … → … → …" text alone."""
    import sys

    from rekord import capture, system
    lv = fake_live
    opened, resets = [], []
    monkeypatch.setattr(system, "mac_open_privacy", lambda s: opened.append(s) or True)
    monkeypatch.setattr(system, "mac_reset_permissions", lambda: resets.append(1) or True)
    monkeypatch.setattr(sys, "platform", "darwin")
    assert lv.isMac and lv.macBlocked == ""
    lv._notes = capture.MacCapture.PERMISSION  # recording with the microphone, but no call sound
    assert lv.macBlocked == "ScreenCapture"
    lv.openMacPrivacy(lv.macBlocked)
    assert opened == ["ScreenCapture"]
    lv._notes, lv._error = "", "Live-Start fehlgeschlagen: " + capture.MacCapture.PERMISSION + " – ohne Mikrofon …"
    assert lv.macBlocked == "ScreenCapture"  # "Nur Call-Ton" couldn't start
    lv._error = "macOS lässt REKORD nicht ans Mikrofon. …"
    assert lv.macBlocked == "Microphone"
    toasts = []
    lv.toast.connect(toasts.append)
    lv.resetMacPermissions()
    assert resets == [1] and lv.error == "" and lv.macBlocked == "" and "erlaube" in toasts[-1]
    monkeypatch.setattr(sys, "platform", "win32")
    lv._error = "macOS lässt REKORD nicht ans Mikrofon."
    assert lv.macBlocked == ""  # only on a Mac


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
    assert "UI selftest: 8 pages, 0 QML warnings" in r.stdout
    assert len(list((tmp_path / "shots").glob("*.png"))) == 8


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
    for _ in range(2):  # the resampler holds a few samples back at the very start of a stream
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


def test_tray_says_what_rekord_does():
    from rekord.app import tray
    assert tray.describe("recording", "12:34", False) == "REKORD – nimmt auf · 12:34"
    assert tray.describe("paused", "0:05", True) == "REKORD – pausiert · 0:05"
    assert tray.describe("idle", "0:00", True) == "REKORD – läuft im Hintergrund"
    assert tray.describe("idle", "0:00", False) == "REKORD"


def test_no_tray_without_widgets_or_system_tray(qt):
    from PySide6.QtCore import QObject
    from rekord.app import tray
    t = tray.Tray(qt, QObject(), bridge.AppState(8765), QObject(), QObject())  # this test app has no widgets
    assert not t.available
    t.update()  # harmless without a tray


TRAY_SCRIPT = r'''
import os, sys, json
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QObject, Property, Signal, Slot, QCoreApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtQml import QQmlApplicationEngine
app = QApplication([])
QSystemTrayIcon.isSystemTrayAvailable = staticmethod(lambda: True)  # offscreen has no tray: pretend
from rekord.app import tray, bridge

class FakeLive(QObject):
    changed = Signal()
    def __init__(self):
        super().__init__(); self._s = "idle"; self.stopped = 0
    @Property(str, notify=changed)
    def state(self): return self._s
    @Property(str, notify=changed)
    def elapsedText(self): return "1:02"
    @Slot()
    def stop(self): self.stopped += 1

class FakeApi(QObject):
    event = Signal("QVariantMap")

engine = QQmlApplicationEngine()
engine.loadData(b"""import QtQuick
Window { visible: false; property var calls: []
  function startRecording() { calls = calls.concat(["record"]) }
  function quitApp() { calls = calls.concat(["quit"]) }
  function openRecording(rid, t) { calls = calls.concat(["open:" + rid]) } }""")
win = engine.rootObjects()[0]
state, live, api = bridge.AppState(8765), FakeLive(), FakeApi()
shown = []
state.focusRequested.connect(lambda: shown.append(1))
t = tray.Tray(app, win, state, live, api)
out = {"available": t.available, "tip_hidden": t._tray.toolTip(), "rec_text": t._rec.text()}
t._record()                       # idle → window + "Wer ist dabei?"
live._s = "recording"; live.changed.emit()
out["tip_rec"] = t._tray.toolTip(); out["rec_text2"] = t._rec.text()
t._record()                       # recording → stop & save
t._quit()                         # while recording: window first, then the question
messages = []
t._tray.showMessage = lambda title, text: messages.append([title, text])
from rekord import db
rid = db.create_recording("Budgetrunde", "", status="done")["id"]
api.event.emit({"type": "done", "id": rid})
api.event.emit({"type": "progress", "id": rid})
for _ in range(20): QCoreApplication.processEvents()
t._message_clicked()
for _ in range(20): QCoreApplication.processEvents()
out.update(calls=win.property("calls").toVariant() if hasattr(win.property("calls"), "toVariant") else win.property("calls"),
           shown=len(shown), stopped=live.stopped, messages=messages)
print("RESULT" + json.dumps(out))
sys.stdout.flush(); os._exit(0)
'''


def test_tray_menu_and_notification(tmp_path):
    env = dict(os.environ, REKORD_HOME=str(tmp_path / "home"))
    r = subprocess.run([sys.executable, "-c", TRAY_SCRIPT], env=env, capture_output=True, text=True, timeout=60, cwd=ROOT)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, r.stdout[-2000:] + r.stderr[-2000:]
    import json
    out = json.loads(line[6:])
    assert out["available"] and out["tip_hidden"] == "REKORD – läuft im Hintergrund" and out["rec_text"] == "Aufnehmen"
    assert out["tip_rec"] == "REKORD – nimmt auf · 1:02" and out["rec_text2"] == "Aufnahme stoppen & speichern"
    assert out["stopped"] == 1
    assert out["calls"][:2] == ["record", "quit"] and out["calls"][2].startswith("open:")
    assert out["messages"] == [["Fertig ausgewertet", "„Budgetrunde“ – Transkript und Sprecher sind da."]]  # only "done", not progress
    assert out["shown"] >= 3  # record, quit while recording, the clicked message


def test_quitting_ends_the_process_without_python_teardown(monkeypatch):
    from rekord import desktop
    ended = []
    monkeypatch.setattr(desktop.os, "_exit", lambda code: ended.append(code))
    desktop._end()  # noqa: SLF001
    assert ended == [0]


def test_microphone_takes_the_channel_with_the_voice(qt):
    """Several input channels: the loudest one, not the mean (which thins the voice out or even cancels it)."""
    m = bridge.Mic()
    voice = np.sin(np.arange(1600) / 16000 * 2 * np.pi * 300).astype(np.float32) * 0.5
    quiet = np.zeros(1600, np.float32)
    four = np.stack([quiet, voice, quiet, quiet], axis=1)  # an interface: the microphone on input 2
    out = m._voice_channel(four)  # noqa: SLF001
    assert np.allclose(out, voice)
    m2 = bridge.Mic()
    inverted = np.stack([voice, -voice * 0.9], axis=1)  # opposite phase: the mean would be almost silent
    assert np.sqrt(np.mean(m2._voice_channel(inverted) ** 2)) > 0.3  # noqa: SLF001


def test_bluetooth_microphone_gets_a_hint():
    mics = [{"id": "a", "name": "AirPods von Emil", "default": True}, {"id": "b", "name": "MacBook Pro-Mikrofon", "default": False},
            {"id": "c", "name": "Logitech USB Headset", "default": False}]
    assert "Telefonqualität" in bridge.mic_hint("a", mics) and "AirPods" in bridge.mic_hint("a", mics)
    assert bridge.mic_hint("", mics)  # the system default is the AirPods
    assert bridge.mic_hint("b", mics) == "" and bridge.mic_hint("c", mics) == ""


def test_live_restarts_a_stalled_microphone_and_warns_about_silence(qt, monkeypatch):
    started = []
    monkeypatch.setattr(bridge.Mic, "start", lambda self, device_id="": started.append(device_id) or True)
    monkeypatch.setattr(bridge.Mic, "stop", lambda self: None)
    lv = bridge.Live()
    toasts = []
    lv.toast.connect(toasts.append)
    lv._state = "recording"  # noqa: SLF001 - the watch only, no engine
    lv._last_chunk = time.monotonic() - 5  # noqa: SLF001 - nothing for 5 s (AirPods taken out)
    lv._check()  # noqa: SLF001
    assert started and any("ausgesetzt" in t for t in toasts)
    zero = np.zeros(1600, "<i2").tobytes()
    lv._on_chunk(zero, 16000)  # noqa: SLF001
    lv._quiet_from -= 7  # noqa: SLF001 - digital silence for 7 s
    lv._check()  # noqa: SLF001
    assert "kein Ton" in lv.micWarning
    voice = (np.sin(np.arange(1600) / 16000 * 2 * np.pi * 300) * 8000).astype("<i2").tobytes()
    lv._on_chunk(voice, 16000)  # noqa: SLF001
    lv._check()  # noqa: SLF001
    assert lv.micWarning == ""
    started.clear()
    lv.setMic("usb-mic")  # switching during the recording: right away
    assert started == ["usb-mic"] and any("gewechselt" in t for t in toasts)
    lv._state = "idle"  # noqa: SLF001
    lv.setMic("")


def test_playback_uses_the_current_output_device(qt):
    from rekord.app import api as api_mod
    p = api_mod.Player()
    if not p.available:
        pytest.skip("no Qt Multimedia here")
    followed = []
    p._follow_output = lambda: followed.append(1)  # noqa: SLF001
    p.toggle()
    p.seekPlay(1.0)
    p.playRange(0.0, 2.0)
    assert len(followed) == 3
    p.stop()
