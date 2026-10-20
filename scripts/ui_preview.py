"""Screenshots of REKORD's native window with demo data – every page, a live recording included, without
microphone or models. Also the UI test: exit code 2 when QML reports warnings.

    QT_QPA_PLATFORM=offscreen python scripts/ui_preview.py <out dir>
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("REKORD_HOME", tempfile.mkdtemp(prefix="rekord-ui-"))

import numpy as np  # noqa: E402

from rekord import config, db, live, pipeline  # noqa: E402


def seed() -> dict:
    config.save({"storage_chosen": True, "welcome_done": True})
    voice = np.ones(192, dtype=np.float32)
    lisa = db.create_profile("Lisa", voice, color="#3B82F6")
    max_ = db.create_profile("Max", voice, color="#22C55E")
    db.create_profile("Prof. Huber", voice, color="#A855F7")
    rec = db.create_recording("Team-Meeting Launch", "", source="live", duration=1834, status="done")
    sl = db.add_speaker(rec["id"], "Lisa", "#3B82F6", lisa)
    sm = db.add_speaker(rec["id"], "Max", "#22C55E", max_)
    su = db.add_speaker(rec["id"], pipeline.UNKNOWN, pipeline.UNKNOWN_COLOR, None)
    conn = db.connect()
    lines = [(sl, 0, 14, "Okay, dann fangen wir an. Wichtigster Punkt heute ist der Launch am Freitag.", None),
             (sm, 14, 31, "Die Landingpage ist fertig, nur die Texte fehlen noch. Die schicke ich bis Mittwoch.", None),
             (su, 31, 40, "Hier ist Tom aus der Rechtsabteilung – brauchen wir dafür noch ein Okay?", 7),
             (sl, 40, 62, "Ja, Max, kannst du das bis Donnerstag klären? Sonst verschieben wir auf Montag.", None),
             (sm, 62, 70, "Mach ich.", None)]
    for sid, a, b, text, voice in lines:
        conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text, voice) VALUES (?,?,?,?,?,?)",
                     (rec["id"], sid, a, b, text, voice))
    conn.commit()
    rng = np.random.default_rng(4)
    import wave
    wav = config.AUDIO_DIR / f"{rec['id']}.wav"
    with wave.open(str(wav), "wb") as w:  # a quiet tone, so the player has something to play
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes((np.sin(np.arange(8000 * 70) / 8000 * 2 * np.pi * 220) * 800).astype("<i2").tobytes())
    db.update_recording(rec["id"], audio_path=str(wav), duration=70, highlights=[22.0, 48.0], notes="Budget nochmal mit Anna klären.",
                        peaks=[round(float(abs(np.sin(i / 7)) * 0.7 + rng.random() * 0.3), 3) for i in range(400)])
    db.add_summary(rec["id"], "mindmap", "Mind Map", "# Launch\n- Termin\n  - Freitag\n  - Plan B: Montag\n- Landingpage\n  - Texte bis Mittwoch\n"
                   "- Recht\n  - Freigabe bis Donnerstag\n  - Tom fragen")
    db.add_chat(rec["id"], "user", "Wer kümmert sich um die Freigabe?")
    db.add_chat(rec["id"], "assistant", "**Max** klärt die Freigabe mit der Rechtsabteilung bis Donnerstag [00:40].")
    db.add_summary(rec["id"], "meeting", "Meeting-Protokoll",
                   "## Entscheidungen\n- Launch bleibt am **Freitag**\n- Rechtliche Freigabe vorher einholen\n\n"
                   "## Aufgaben\n- **Max**: Texte für die Landingpage bis Mittwoch\n- **Max**: Freigabe der Rechtsabteilung bis Donnerstag\n\n"
                   "## Offen\n- Verschiebung auf Montag, falls die Freigabe fehlt")
    p = db.create_recording("VO Statistik – Einheit 4", "", source="live", duration=5410, status="processing")
    db.update_recording(p["id"], stage="Transkription", progress=0.42)
    db.create_recording("Interview Bewerbung.m4a", "", source="import", duration=2280, status="queued")
    e = db.create_recording("Sprachnotiz", "", source="import", duration=12, status="error")
    db.update_recording(e["id"], folder="Privat")
    db.update_recording(rec["id"], folder="Arbeit")
    return {"rid": rec["id"], "lisa": lisa, "max": max_}


class FakeSession:
    """Stands in for live.LiveSession: no models, no microphone – the preview sends the events itself."""
    last: "FakeSession | None" = None

    def __init__(self, emit, title, source, sample_rate, participants, guests, meeting, call_audio):
        self.emit, self.title, self.meeting, self.guests, self.participants = emit, title, meeting, guests, participants
        self.rid = db.create_recording(title, "", source=source, status="recording")["id"]
        self.call, self.notes, self.paused, self._closed, self.fed = None, [], False, False, 0
        FakeSession.last = self

    def feed_pcm16(self, data: bytes) -> None:
        self.fed += len(data) // 2

    def highlight(self) -> float:
        self.emit({"type": "highlight", "t": 1.0})
        return 1.0

    def name_speaker(self, key: int, name: str) -> None:
        self.emit({"type": "speakers", "items": [{"key": key, "name": name, "color": "#F59E0B", "known": True, "talk": 9}]})

    def stop(self) -> str:
        self._closed = True
        db.update_recording(self.rid, status="done", duration=94)
        return self.rid


def hub() -> int:
    """The local hub the window talks to (like in the real app), on a free port."""
    import socket
    import threading

    import uvicorn

    from rekord import jobs
    from rekord.server import app
    jobs.start = lambda: None  # the demo recordings have no audio: nothing to process
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        port = so.getsockname()[1]
    app.state.port, app.state.lan, app.state.auto_download = port, False, False
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(200):
        with socket.socket() as so:
            if so.connect_ex(("127.0.0.1", port)) == 0:
                return port
        time.sleep(0.05)
    raise RuntimeError("hub did not start")


def main(out: Path) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Q_ARG, QCoreApplication, QMetaObject, QObject

    from rekord import app as rapp
    from rekord.app import bridge
    ids = seed()
    live.LiveSession = FakeSession
    bridge.Mic.start = lambda self, device_id="": True
    port = hub()
    w = rapp.build(port, keep_running=False)
    if w is None:
        print("interface did not load")
        return 1
    win, o = w.win, w.objects
    out.mkdir(parents=True, exist_ok=True)
    problems_extra: list[str] = []

    def wait(sec: float) -> None:
        end = time.time() + sec
        while time.time() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)

    def shot(name: str) -> None:
        wait(0.9)
        win.grabWindow().save(str(out / f"{name}.png"))

    def call(obj, fn, *args):
        QMetaObject.invokeMethod(obj, fn, *[Q_ARG("QVariant", a) for a in args])

    shot("library")
    call(win, "openRecording", ids["rid"], 0)
    wait(1.5)
    detail = win.findChild(QObject, "detailPage")
    for i, name in enumerate(["detail", "detail-transcript", "detail-mindmap", "detail-ask", "detail-notes", "detail-export"]):
        detail.setProperty("tab", i)
        shot(name)
    detail.setProperty("tab", 1)
    rec = db.get_recording(ids["rid"])
    sp = {s["name"]: s["id"] for s in db.list_speakers(ids["rid"])}
    call(detail, "editSpeaker", sp["Max"])
    shot("detail-speaker")
    win.findChild(QObject, "speakerDlg").close()
    seg = next(x for x in db.list_segments(ids["rid"]) if x.get("voice") == 7)
    call(detail, "assignLine", seg["id"])
    shot("detail-assign")
    win.findChild(QObject, "assignDlg").close()
    wait(0.4)
    assert rec is not None

    # Personen + Einsprechen (all three ways)
    win.setProperty("page", "people")
    shot("people")
    enroll = win.findChild(QObject, "enrollDlg")
    call(win, "enroll", {"name": "Anna"}, None)
    wait(0.5)
    shot("enroll-read")
    voice = o["voice"]
    voice.start(120)
    wait(0.2)
    speech = (np.sin(np.arange(1600) / 16000 * 2 * np.pi * 180) * 7000).astype("<i2").tobytes()
    for _ in range(300):  # 30 s of "talking"
        voice._on_chunk(speech, 16000)
    wait(0.2)
    shot("enroll-recording")
    voice.stop()
    if not voice.property("path") or voice.property("speech") < 25:
        problems_extra.append(f"voice sample: {voice.property('speech')} s, file {voice.property('path')!r}")
    enroll.setProperty("mode", "free")
    shot("enroll-free")
    enroll.setProperty("mode", "recording")
    wait(0.5)
    call(enroll, "pickRecording", ids["rid"])
    wait(0.8)
    enroll.setProperty("picked", 0)
    shot("enroll-recording-voices")
    enroll.close()
    wait(0.3)
    win.setProperty("page", "live")
    shot("live")
    win.setProperty("whoOpen", True)
    shot("who")
    win.setProperty("whoOpen", False)
    o["live"].start("Team-Meeting Launch", "person", [ids["lisa"], ids["max"]], 3)
    for _ in range(200):
        wait(0.02)
        if o["live"].state == "recording":
            break
    sess = FakeSession.last
    em = o["live"]._event.emit
    em({"type": "speakers", "items": [{"key": 0, "name": "Lisa", "color": "#3B82F6", "known": True, "talk": 42},
                                      {"key": 1, "name": "Max", "color": "#22C55E", "known": True, "talk": 21},
                                      {"key": 2, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR, "known": False,
                                       "talk": 9, "voices": 1}]})
    for t, (name, color, text) in enumerate([("Lisa", "#3B82F6", "Okay, dann fangen wir an. Wichtigster Punkt ist der Launch."),
                                              ("Max", "#22C55E", "Die Landingpage ist fertig, nur die Texte fehlen noch."),
                                              (pipeline.UNKNOWN, pipeline.UNKNOWN_COLOR, "Brauchen wir noch ein Okay von der Rechtsabteilung?"),
                                              ("Lisa", "#3B82F6", "Ja – Max, kannst du das bis Donnerstag klären?")]):
        em({"type": "segment", "key": t % 3, "name": name, "color": color, "known": name != pipeline.UNKNOWN,
            "start": t * 9.0, "end": t * 9.0 + 8, "text": text})
    em({"type": "speaking", "key": 0, "name": "Lisa", "color": "#3B82F6", "known": True})
    tone = (np.sin(np.arange(1600) / 16000 * 2 * np.pi * 220) * 9000).astype("<i2").tobytes()
    for _ in range(12):
        o["live"]._on_chunk(tone, 16000)
        wait(0.03)
    o["live"].highlight()
    shot("live-recording")
    em({"type": "speaking", "key": 2, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR, "known": False})
    shot("live-unknown")
    o["rekord"].setTheme("light")
    shot("live-light")
    o["live"].stop()
    for _ in range(300):
        wait(0.02)
        if o["live"].state == "idle":
            break
    shot("after-stop")
    opened = win.property("page") == "detail" and sess is not None and detail.property("rid") == sess.rid
    win.setProperty("page", "library")
    shot("library-light")
    o["rekord"].setTheme("system")

    # ---- Einstellungen: every section
    win.setProperty("page", "settings")
    settings = win.findChild(QObject, "settingsPage")
    shot("settings")
    for key in ("ai", "asr", "models", "pair", "int", "data"):
        call(settings, "jump", key)
        shot(f"settings-{key}")
    o["rekord"].setAccent("#2D7FF9")  # another accent color, everywhere at once
    call(settings, "jump", "look")
    shot("settings-accent")
    o["rekord"].setAccent("#FF5A1F")

    # ---- the first-start guide, step by step
    wiz = win.findChild(QObject, "welcomeWiz")
    win.setProperty("welcomeOpen", True)
    wait(1.0)
    if not wiz.property("opened"):
        problems_extra.append("welcome: the guide didn't open")
    for i, step in enumerate(wiz.property("steps").toVariant() or []):
        call(wiz, "go", i)
        shot(f"welcome-{step}")
    win.setProperty("welcomeOpen", False)
    o["voice"].discard()

    # ---- the drive with the data is unplugged
    real_missing = config.home_missing
    config.home_missing = lambda: True
    win.setProperty("page", "library")
    o["rekord"].refresh()
    shot("missing")
    if win.property("shownPage") != "missing":
        problems_extra.append("missing drive: the window still shows " + str(win.property("shownPage")))
    config.home_missing = real_missing
    o["rekord"].refresh()
    win.setProperty("page", "library")
    wait(0.5)

    problems = list(w.warnings) + problems_extra
    if sess is None or sess.fed == 0:
        problems.append("live: the microphone audio never reached the session")
    if not opened:
        problems.append("stop: the finished recording didn't open")
    (out / "qml-warnings.txt").write_text("\n".join(problems), encoding="utf-8")
    print(f"UI preview: {len(list(out.glob('*.png')))} screenshots in {out}, {len(problems)} problems")
    for p in problems:
        print("  ", p)
    return 2 if problems else 0


if __name__ == "__main__":
    code = main(Path(sys.argv[1] if len(sys.argv) > 1 else "ui-preview"))
    sys.stdout.flush()
    os._exit(code)  # like the app itself: no teardown of the window's objects in Python's shutdown order
