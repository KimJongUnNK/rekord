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
             (sm, 14, 31, "Die Landingpage in Web Flow ist fertig, nur die Texte fehlen noch. Die schicke ich bis Mittwoch.", None),
             (su, 31, 40, "Hier ist Tom aus der Rechtsabteilung – brauchen wir dafür noch ein Okay?", 7),
             (sl, 40, 62, "Ja, Max, kannst du das bis Donnerstag mit Frau Bruger klären? Sonst verschieben wir auf Montag.", None),
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
    # it was a screen-shared call: stills from the video next to the lines (two "slides")
    from rekord import frames
    import av
    for t, (title, colour) in ((0.0, ("LAUNCH", (255, 90, 31))), (14.5, ("LANDINGPAGE", (59, 130, 246)))):
        img = np.zeros((360, 640, 3), np.uint8)
        img[:] = (24, 24, 27)
        img[40:70, 40:40 + 22 * len(title)] = colour  # a title bar
        img[110:300, 40:600] = (52, 52, 58)  # the slide's content area
        img[130:150, 60:400] = (200, 200, 205)
        img[170:190, 60:520] = (150, 150, 155)
        img[210:230, 60:360] = (150, 150, 155)
        frames.folder(rec["id"]).mkdir(parents=True, exist_ok=True)
        (frames.folder(rec["id"]) / frames._name(t)).write_bytes(frames._jpeg(av.VideoFrame.from_ndarray(img, format="rgb24")))
    db.add_summary(rec["id"], "mindmap", "Mind Map", "# Launch\n- Termin\n  - Freitag\n  - Plan B: Montag\n- Landingpage\n  - Texte bis Mittwoch\n"
                   "- Recht\n  - Freigabe bis Donnerstag\n  - Tom fragen")
    db.add_chat(rec["id"], "user", "Wer kümmert sich um die Freigabe?")
    db.add_chat(rec["id"], "assistant", "**Max** klärt die Freigabe mit der Rechtsabteilung bis Donnerstag [00:40].")
    db.add_summary(rec["id"], "meeting", "Meeting-Protokoll",
                   "## Entscheidungen\n- Launch bleibt am **Freitag**\n- Rechtliche Freigabe vorher einholen\n\n"
                   "## Aufgaben\n- **Max**: Texte für die Landingpage bis Mittwoch\n- **Max**: Freigabe der Rechtsabteilung bis Donnerstag\n\n"
                   "## Offen\n- Verschiebung auf Montag, falls die Freigabe fehlt")
    # Unterlagen: the agenda (names and terms → corrected in the transcript) and a whiteboard photo nobody could read yet
    from rekord import context
    import tempfile as _tf
    tmp = Path(_tf.mkdtemp())
    (tmp / "Agenda Launch.md").write_text("# Launch-Meeting\n\nTeilnehmer: Lisa Berger, Max Huber, Tom (Recht)\n\n"
                                          "1. Landingpage in Webflow – Texte, Bilder\n2. Rechtliche Freigabe: Frau Brugger (Rechtsabteilung)\n"
                                          "3. Termin: Freitag, Plan B Montag\n\nWebflow-Projekt: launch-2026. Ansprechpartnerin Recht: Frau Brugger.\n", "utf-8")
    (tmp / "Whiteboard.jpg").write_bytes(frames._jpeg(av.VideoFrame.from_ndarray(np.full((360, 640, 3), 230, np.uint8), format="rgb24")))
    context.add(rec["id"], tmp / "Agenda Launch.md")
    context.add(rec["id"], tmp / "Whiteboard.jpg")
    context.run(rec["id"], {**config.load(), "llm": {"provider": "none"}}, use_ai=False)
    p = db.create_recording("VO Statistik – Einheit 4", "", source="live", duration=5410, status="processing")
    db.update_recording(p["id"], stage="Transkription", progress=0.42)
    db.create_recording("Interview Bewerbung.m4a", "", source="import", duration=2280, status="queued")
    e = db.create_recording("Sprachnotiz", "", source="import", duration=12, status="error")
    db.update_recording(e["id"], folder="Privat")
    db.update_recording(rec["id"], folder="Arbeit")
    return {"rid": rec["id"], "lisa": lisa, "max": max_, "processing": p["id"]}


class FakeSession:
    """Stands in for live.LiveSession: no models, no microphone – the preview sends the events itself."""
    last: "FakeSession | None" = None

    def __init__(self, emit, title, source, sample_rate, participants, guests, meeting, call_audio, mic=True):
        self.emit, self.title, self.meeting, self.guests, self.participants = emit, title, meeting, guests, participants
        self.mic = mic
        self.rid = db.create_recording(title, "", source=source, status="recording")["id"]
        self.call, self.notes, self.paused, self._closed, self.fed = None, [], False, False, 0
        if meeting == "online" and call_audio:
            self.call = object()  # the call's sound "runs" (the badge on the live page)
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
    from rekord import capture
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

    def wait_for(cond, sec: float) -> bool:
        end = time.time() + sec
        while time.time() < end:
            QCoreApplication.processEvents()
            if cond():
                return True
            time.sleep(0.02)
        return cond()

    def shot(name: str) -> None:
        wait(0.9)
        win.grabWindow().save(str(out / f"{name}.png"))

    def call(obj, fn, *args):
        QMetaObject.invokeMethod(obj, fn, *[Q_ARG("QVariant", a) for a in args])

    def find(root, name: str):
        """findChild misses Repeater delegates and popups (only visual parents) – walk both trees."""
        import shiboken6
        from PySide6.QtQuick import QQuickItem
        seen, todo = set(), [root]
        while todo:
            obj = todo.pop()
            key = shiboken6.getCppPointer(obj)[0] if obj is not None else None
            if obj is None or key in seen:
                continue
            seen.add(key)
            if obj.objectName() == name:
                return obj
            todo.extend(obj.children())
            if isinstance(obj, QQuickItem):
                todo.extend(obj.childItems())
            ci = obj.property("contentItem") if obj.metaObject().indexOfProperty("contentItem") >= 0 else None
            if isinstance(ci, QObject):
                todo.append(ci)
        return None

    shot("library")
    # several at once: Auswählen → tick two → "2 löschen" → confirm – both gone, the rest stays
    junk = [db.create_recording(f"Falsche Datei {i}", "", source="import")["id"] for i in (1, 2)]
    for j in junk:
        db.update_recording(j, status="done")
    o["library"].refresh()
    wait(0.4)
    libp = win.findChild(QObject, "libraryPage")
    libp.setProperty("selecting", True)
    for j in junk:
        call(libp, "togglePick", j)
    wait(0.3)
    shot("library-select")
    merge_btn = find(libp, "mergePicked")
    if merge_btn is None or not merge_btn.property("visible") or not merge_btn.property("enabled") \
            or merge_btn.property("text") != "2 zusammenführen":
        problems_extra.append("library: no usable '2 zusammenführen' with two recordings ticked")
    before = len(db.list_recordings())
    call(libp, "deletePicked")
    wait(0.3)
    call(win.findChild(QObject, "confirmDlg"), "accept")
    if not wait_for(lambda: all(db.get_recording(j) is None for j in junk), 4) or len(db.list_recordings()) != before - 2:
        problems_extra.append("library: 'Auswählen → löschen' didn't delete exactly the ticked recordings")
    if not wait_for(lambda: not libp.property("selecting"), 4):  # ends when the hub's answer is back (async)
        problems_extra.append("library: still selecting after deleting")
    lm = win.findChild(QObject, "loadModelsButton")
    if lm is None or not lm.property("visible") or lm.property("text") != "Jetzt laden":
        problems_extra.append("library: no 'Jetzt laden' for the missing speech models")
    # a file from outside, the short way: one pick → its recording is open (no searching the list)
    side_file = win.findChild(QObject, "fileButton")
    if side_file is None or not side_file.property("visible"):
        problems_extra.append("sidebar: no visible 'Datei transkribieren' button")
    import tempfile
    from PySide6.QtCore import QUrl
    ext = Path(tempfile.mkdtemp()) / "Sprachmemo Kunde.mp3"
    ext.write_bytes(b"\0" * 64)
    QMetaObject.invokeMethod(win, "importUrls", Q_ARG("QVariant", [QUrl.fromLocalFile(str(ext)).toString()]))
    wait(0.8)
    shot("import-opens-recording")
    opened_rid = win.findChild(QObject, "detailPage").property("rid")
    if win.property("page") != "detail" or not opened_rid or db.get_recording(opened_rid)["title"] != "Sprachmemo Kunde":
        problems_extra.append(f"import: the imported file's recording didn't open (page {win.property('page')})")
    call(win, "openRecording", ids["rid"], 0)
    wait(1.5)
    detail = win.findChild(QObject, "detailPage")
    append_btn = detail.findChild(QObject, "appendButton")
    if append_btn is None or not append_btn.property("visible") or not append_btn.property("enabled"):
        problems_extra.append("detail: no usable 'Anhängen' button on a finished recording")
    docs_btn = detail.findChild(QObject, "docsButton")
    if docs_btn is None or not docs_btn.property("visible") or not docs_btn.property("enabled"):
        problems_extra.append("detail: no usable 'Unterlagen' button")
    for i, name in enumerate(["detail", "detail-transcript", "detail-mindmap", "detail-ask", "detail-notes", "detail-docs", "detail-export"]):
        detail.setProperty("tab", i)
        shot(name)
    # the bar while summarizing (long lecture on a local model: "Teil 3 von 9 …")
    sv = find(detail, "summaryProgress")
    view = sv
    while view is not None and view.property("streamTitle") is None:
        view = view.parent()
    if sv is None or view is None:
        problems_extra.append("summary: no progress bar while summarizing")
    else:
        view.setProperty("streamTitle", "Vorlesung / Lernzettel")
        view.setProperty("progressLabel", "Lange Aufnahme – Teil 3 von 9 wird verdichtet …")
        view.setProperty("progress", 0.27)
        view.setProperty("streamText", "*Lange Aufnahme – Teil 3 von 9 wird verdichtet …*")
        view.setProperty("busy", True)
        detail.setProperty("tab", 0)
        wait(0.4)
        if not sv.property("visible"):
            problems_extra.append("summary: the progress bar isn't shown while summarizing")
        shot("summary-progress")
        view.setProperty("busy", False)
        view.setProperty("streamText", "")
        wait(0.2)
    # a summary edited like in Word: select a word, B, save → stored with its formats, Markdown gets "**"
    detail.setProperty("tab", 0)
    wait(0.4)
    edit_btn = find(detail, "summaryEdit")
    if edit_btn is None:
        problems_extra.append("summary: no 'Bearbeiten' button")
    else:
        QMetaObject.invokeMethod(edit_btn, "clicked")
        wait(0.6)
        rich = find(detail, "richEditor")
        area = find(rich, "richArea") if rich else None
        if area is None or not rich.property("opened"):
            problems_extra.append("summary: the editor with the toolbar didn't open")
        else:
            from PySide6.QtGui import QTextDocument
            sid = next(x["id"] for x in db.list_summaries(ids["rid"]) if x["template_id"] != "mindmap")
            probe = QTextDocument()
            probe.setMarkdown(db.get_summary(sid)["content"])  # what the editor loaded
            start = probe.toPlainText().find("Launch")
            QMetaObject.invokeMethod(area, "select", Q_ARG(int, start), Q_ARG(int, start + 6))
            wait(0.2)
            QMetaObject.invokeMethod(find(rich, "richBold"), "clicked")
            wait(0.3)
            shot("summary-rich-editor")
            QMetaObject.invokeMethod(find(rich, "richSave"), "clicked")
            if not wait_for(lambda: (db.get_summary(sid) or {}).get("rich"), 4):
                problems_extra.append("summary: the formatted version wasn't saved")
            else:
                sm = db.get_summary(sid)
                if "**Launch**" not in sm["content"] or "Launch bleibt" in sm["content"]:
                    problems_extra.append(f"summary: bold didn't stick (md {sm['content'][:80]!r})")
            wait(0.5)
            shot("summary-rich-saved")
    # "Wer ist das? → Später" must never lose the way back: one line stays, "Jetzt benennen" opens it again
    naming = detail.findChild(QObject, "namingCard")
    now = naming.findChild(QObject, "namingNow") if naming else None
    if naming is None or not naming.property("visible") or naming.property("later"):
        problems_extra.append("naming: 'Wer ist das?' not shown for the unknown voice")
    else:
        call(naming, "setLater", True)
        wait(0.3)
        shot("detail-naming-later")
        if not naming.property("visible") or now is None or not now.property("visible"):
            problems_extra.append("naming: after 'Später' there is no way back to name the voice")
        call(naming, "setLater", False)
        wait(0.3)
        if naming.property("later"):
            problems_extra.append("naming: 'Jetzt benennen' didn't open the card again")
    # "Audio anhängen" (part 2 of a lecture) gives the recording a new, longer file: the player must take it –
    # it kept the first file, so it stopped at part 1's end and jumped back to the start
    old_audio = db.get_recording(ids["rid"])["audio_path"]
    longer = config.AUDIO_DIR / f"{ids['rid']}-appended.wav"
    import wave
    with wave.open(str(longer), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes((np.sin(np.arange(8000 * 100) / 8000 * 2 * np.pi * 220) * 800).astype("<i2").tobytes())
    db.update_recording(ids["rid"], audio_path=str(longer), duration=100)
    call(detail, "reload")
    if not wait_for(lambda: detail.property("loadedAudio") == str(longer) and o["player"].duration > 90, 4):
        problems_extra.append(f"player: still on the old file after appending ({detail.property('loadedAudio')!r}, "
                              f"{o['player'].duration:.0f} s)")
    o["player"].seek(95)
    wait(0.3)
    if o["player"].available and o["player"].position < 90:
        problems_extra.append(f"player: seeking into the appended part jumps back ({o['player'].position:.0f} s)")
    db.update_recording(ids["rid"], audio_path=old_audio, duration=70)
    call(detail, "reload")
    wait(0.5)
    # "Anhängen → Aufnahmen aus REKORD": several recordings picked from a list, like Unterlagen
    other = db.create_recording("VO Teil 2", str(longer), source="import", duration=100, status="done")
    picker = find(detail, "recordingPicker")
    if picker is None:
        problems_extra.append("append: no list to pick recordings from")
    else:
        call(picker, "show")
        def listed():
            v = picker.property("items")
            v = v.toVariant() if hasattr(v, "toVariant") else v
            return any(x.get("id") == other["id"] for x in (v or []))
        if not wait_for(listed, 4):
            problems_extra.append("append: the picker doesn't list the other finished recordings")
        call(picker, "pick", [other["id"]])
        wait(0.3)
        ok = find(picker, "pickerOk")
        if ok is None or not ok.property("enabled") or ok.property("text") != "Anhängen":
            problems_extra.append("append: picking a recording doesn't enable 'Anhängen'")
        shot("detail-append-recordings")
        picker.close()
        wait(0.3)
    db.delete_recording(other["id"])
    fixes = db.get_recording(ids["rid"]).get("context_fixes") or []
    if not any(f["to"] == "Webflow" for f in fixes) or not any(f["to"] == "Brugger" or f["to"].endswith("Brugger") for f in fixes):
        problems_extra.append(f"Unterlagen: expected Webflow/Brugger corrections, got {fixes}")
    detail.setProperty("tab", 1)
    rec = db.get_recording(ids["rid"])
    sp = {s["name"]: s["id"] for s in db.list_speakers(ids["rid"])}
    call(detail, "editSpeaker", sp["Max"])
    shot("detail-speaker")
    win.findChild(QObject, "speakerDlg").close()
    seg = next(x for x in db.list_segments(ids["rid"]) if x.get("voice") == 7)
    call(detail, "assignLine", seg["id"])
    shot("detail-assign")
    an = win.findChild(QObject, "assignDlg")
    nb = an.findChild(QObject, "assignNoise") if an else None
    if nb is None or not nb.property("visible"):
        problems_extra.append("assign: no 'Ist ein Geräusch' button")
    win.findChild(QObject, "assignDlg").close()
    wait(0.4)
    assert rec is not None
    # still being analysed (e.g. the wrong file): stop it right there, or delete it
    call(win, "openRecording", ids["processing"], 0)
    wait(1.2)
    shot("detail-processing")
    # transcribing: a stop button right next to "Datei transkribieren", from every page
    o["library"].refresh()
    wait(0.3)
    sj, ss = win.findChild(QObject, "sideJob"), win.findChild(QObject, "sideStop")
    if sj is None or not sj.property("visible") or ss is None or not ss.property("visible"):
        problems_extra.append("sidebar: no stop button while a file is being transcribed")
    for name in ("cancelButton", "cancelDeleteButton"):
        b = win.findChild(QObject, "detailPage").findChild(QObject, name)
        if b is None or not b.property("visible"):
            problems_extra.append(f"detail: no visible {name} while the recording is being analysed")

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
    # a Mac where macOS refuses although the switch shows "on": the buttons that fix it, in the message itself
    import sys as _sys
    real_platform, _sys.platform = _sys.platform, "darwin"
    o["live"]._error = "Live-Start fehlgeschlagen: " + capture.MacCapture.PERMISSION
    o["live"].changed.emit()
    shot("live-mac-blocked")
    if o["live"].macBlocked != "ScreenCapture":
        problems_extra.append("live: macOS refusal without the buttons that fix it")
    _sys.platform = real_platform
    o["live"]._error = ""
    o["live"].changed.emit()
    win.setProperty("whoOpen", True)
    shot("who")
    who = win.findChild(QObject, "whoDlg")
    who.setProperty("meeting", "online")
    who.setProperty("withMic", True)
    shot("who-online")
    who.setProperty("withMic", False)
    shot("who-online-call-only")
    if o["live"].callAvailable and not who.property("callOnly"):
        problems_extra.append("who: 'Nur Call-Ton' was picked but the dialog doesn't know")
    who.setProperty("meeting", "person")
    who.setProperty("withMic", True)
    # Unterlagen before the start: the agenda waits in the dialog and goes to the recording once it runs
    agenda = Path(tempfile.mkdtemp()) / "Agenda Launch.txt"
    agenda.write_text("Launch: Webflow, Frau Brugger (Recht)", "utf-8")
    o["live"].addDocs([QUrl.fromLocalFile(str(agenda)).toString()])
    shot("who-docs")
    if list(o["live"].docs) != [agenda.name]:
        problems_extra.append(f"who: Unterlagen before the start not kept: {list(o['live'].docs)}")
    win.setProperty("whoOpen", False)
    o["live"].start("Team-Meeting Launch", "person", [ids["lisa"], ids["max"]], 3)
    for _ in range(200):
        wait(0.02)
        if o["live"].state == "recording":
            break
    sess = FakeSession.last
    from rekord import context as _ctx
    for _ in range(100):
        wait(0.02)
        if _ctx.items(sess.rid):
            break
    if [d["name"] for d in _ctx.items(sess.rid)] != [agenda.name] or list(o["live"].docs):
        problems_extra.append(f"live: the Unterlagen didn't go to the recording ({_ctx.items(sess.rid)})")
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
    mic = {"chunk": tone}
    from PySide6.QtCore import QTimer
    feed = QTimer()  # like a real microphone: a chunk every 100 ms for as long as it records
    feed.timeout.connect(lambda: o["live"]._on_chunk(mic["chunk"], 16000))
    feed.start(100)
    wait(0.4)
    o["live"].highlight()
    shot("live-recording")
    em({"type": "speaking", "key": 2, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR, "known": False})
    shot("live-unknown")
    mic["chunk"] = np.zeros(1600, "<i2").tobytes()  # muted: only digital silence arrives
    wait(0.3)
    o["live"]._quiet_from -= 7
    o["live"]._check()
    shot("live-mic-warning")
    if "kein Ton" not in o["live"].micWarning:
        problems_extra.append("live: no warning while the microphone delivers silence")
    mic["chunk"] = tone
    wait(0.3)
    o["rekord"].setTheme("light")
    shot("live-light")
    feed.stop()
    o["live"].stop()
    for _ in range(300):
        wait(0.02)
        if o["live"].state == "idle":
            break
    shot("after-stop")
    opened = win.property("page") == "detail" and sess is not None and detail.property("rid") == sess.rid
    if o["live"].callAvailable:  # online, "Nur Call-Ton": the microphone stays closed, the badge says so
        o["live"].start("Webinar Q3-Zahlen", "online", [], 2, False)
        for _ in range(200):
            wait(0.02)
            if o["live"].state == "recording":
                break
        o["live"]._event.emit({"type": "level", "rms": 0.08, "t": 1.0})
        win.setProperty("page", "live")
        shot("live-call-only")
        if o["live"].micOn or not o["live"].callAudio:
            problems_extra.append("live: 'Nur Call-Ton' recording still uses the microphone")
        o["live"].stop()
        for _ in range(300):
            wait(0.02)
            if o["live"].state == "idle":
                break
    win.setProperty("page", "library")
    shot("library-light")
    o["rekord"].setTheme("system")

    # ---- Einstellungen: every section
    win.setProperty("page", "settings")
    settings = win.findChild(QObject, "settingsPage")
    shot("settings")
    # "Anweisungen an die KI": the field is there, "Vorschlag einsetzen" fills and saves it
    sug = find(settings, "aiInstructionsSuggest")
    if sug is None or find(settings, "aiInstructions") is None:
        problems_extra.append("settings: no 'Anweisungen an die KI'")
    else:
        QMetaObject.invokeMethod(sug, "clicked")
        if not wait_for(lambda: "Antworte direkt" in (config.load().get("ai_instructions") or ""), 4):
            problems_extra.append("settings: 'Vorschlag einsetzen' didn't save the instructions")
        call(settings, "jump", "ai")
        shot("settings-ai-instructions")
        config.save({"ai_instructions": ""})
    ts = find(settings, "timestampsSelect")
    if ts is None or ts.property("value") != "ask":
        problems_extra.append(f"settings: 'Zeitstempel' should default to 'Nur wenn ich danach frage' ({ts and ts.property('value')!r})")
    for key in ("ai", "asr", "models", "int", "data"):
        call(settings, "jump", key)
        shot(f"settings-{key}")
        if key == "asr":  # a long drop-down (the languages): the list must show several entries and scroll
            lang = settings.findChild(QObject, "langSelect")
            if lang is None:
                problems_extra.append("select: no language drop-down found")
            else:
                call(lang, "openList")
                wait(0.5)
                shot("settings-select-open")
                h, ch = lang.property("listHeight"), lang.property("listContentHeight")
                if h < 38 * 5 or ch <= h:
                    problems_extra.append(f"select: the list doesn't show several entries and scroll (height {h}, content {ch})")
                call(lang, "closeList")
    # both engines selectable: faster-whisper chosen → its models, where it runs, a load button
    config.save({"asr_engine": "faster-whisper", "faster_whisper_model": "large-v3-turbo"})
    call(settings, "load")
    wait(1.0)
    call(settings, "jump", "asr")
    shot("settings-asr-faster-whisper")
    eng = settings.findChild(QObject, "engineSelect")
    from rekord import models as _m
    if _m.faster_whisper_available() and (eng is None or eng.property("value") != "faster-whisper"):
        problems_extra.append(f"settings: faster-whisper not selectable (value {eng.property('value') if eng else None})")
    config.save({"asr_engine": "sherpa"})
    call(settings, "load")
    wait(1.0)
    call(settings, "jump", "asr")
    # no speech model loaded in the preview: a load button where the model is chosen, and "everything" under Modelle
    for name in ("asrLoad", "loadMissing"):
        b = settings.findChild(QObject, name)
        if b is None or not b.property("visible"):
            problems_extra.append(f"settings: no visible {name} although models are missing")
    o["rekord"].setAccent("#2D7FF9")  # another accent color, everywhere at once
    call(settings, "jump", "look")
    shot("settings-accent")
    o["rekord"].setAccent("#FF5A1F")

    # ---- Fragen (über alle Aufnahmen)
    db.add_chat("global", "user", "Was hat Max zugesagt?")
    db.add_chat("global", "assistant", f"**Max** schickt die Texte für die Landingpage bis Mittwoch [[{ids['rid']}@00:14]] und klärt "
                                       f"die Freigabe bis Donnerstag [[{ids['rid']}@00:40]].")
    win.setProperty("page", "ask")
    shot("ask")

    # ---- Vorlagen: list, move one to the top (saved as the new order), the editor
    from rekord.llm import templates as tmod
    win.setProperty("page", "templates")
    tpl = win.findChild(QObject, "templatesPage")
    shot("templates")
    before = [t["id"] for t in tmod.all_templates()]
    call(tpl, "move", 2, 0)
    wait(1.2)
    order = config.load().get("template_order") or []
    if order[:3] != [before[2], before[0], before[1]]:
        problems_extra.append(f"templates: the new order wasn't saved ({order[:3]})")
    shot("templates-moved")
    call(tpl, "openEditor", 0)
    shot("template-editor")
    call(win.findChild(QObject, "templateDialog"), "close")
    config.save({"template_order": []})

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
