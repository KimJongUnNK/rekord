"""The window's way to the engine: the local API (requests, streamed AI text, uploads, files), Markdown, texts."""
import json
import os
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtQuick", exc_type=ImportError)

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from rekord import db  # noqa: E402
from rekord.app import api as api_mod  # noqa: E402
from rekord.app import md, texts  # noqa: E402


@pytest.fixture(scope="module")
def qt():
    old = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QGuiApplication.instance() or QGuiApplication(["rekord-test"])
    yield app
    if old is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = old


def pump(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        QCoreApplication.processEvents()
        time.sleep(0.01)
    return cond()


def collect(a):
    got = {}
    a.reply.connect(lambda i, ok, status, data: got.__setitem__(i, (ok, status, data)))
    return got


def test_requests_answers_and_errors(qt, hub):
    a = api_mod.Api(hub)
    got = collect(a)
    rec = db.create_recording("API-Test", "", status="done")
    i1 = a.request("GET", f"/api/recordings/{rec['id']}", None)
    assert pump(lambda: i1 in got)  # requests run in parallel – one after the other here
    i2 = a.request("PATCH", f"/api/recordings/{rec['id']}", {"title": "Umbenannt", "notes": "Notiz"})
    i3 = a.request("GET", "/api/recordings/gibtsnicht", None)
    assert pump(lambda: {i2, i3} <= set(got))
    ok, status, data = got[i1]
    assert ok and status == 200 and data["title"] == "API-Test" and data["segments"] == []
    assert got[i2][0] and db.get_recording(rec["id"])["title"] == "Umbenannt" and db.get_recording(rec["id"])["title_locked"] == 1
    assert got[i3] == (False, 404, "Aufnahme nicht gefunden")


def test_unreachable_hub_is_a_readable_error(qt):
    a = api_mod.Api(1)  # nothing listens on port 1
    got = collect(a)
    i = a.request("GET", "/api/status", None)
    assert pump(lambda: i in got)
    assert got[i][0] is False and "REKORD antwortet nicht" in got[i][2]


def test_streamed_ai_text_arrives_in_pieces(qt, hub, monkeypatch):
    from rekord import summarize

    def fake(rid, tid):
        for part in ["## Ergebnis\n", "- Launch am ", "**Freitag**"]:
            time.sleep(0.1)
            yield part
    monkeypatch.setattr(summarize, "generate_stream", fake)
    monkeypatch.setattr(summarize, "maybe_title", lambda rid, content: None)
    rec = db.create_recording("Stream", "", status="done")
    a = api_mod.Api(hub)
    got, chunks = collect(a), []
    a.chunk.connect(lambda i, t: chunks.append(t))
    i = a.stream(f"/api/recordings/{rec['id']}/summaries", {"template_id": "meeting"})
    assert pump(lambda: i in got)
    assert got[i] == (True, 200, "## Ergebnis\n- Launch am **Freitag**")
    assert len(chunks) >= 2 and chunks[-1].endswith("**Freitag**")
    assert [s["content"] for s in db.list_summaries(rec["id"])] == ["## Ergebnis\n- Launch am **Freitag**"]


def test_streamed_error_marker_becomes_a_failure(qt, hub, monkeypatch):
    from rekord import summarize

    def broken(rid, q):
        yield "Ich "
        raise RuntimeError("Kein API-Key")
    monkeypatch.setattr(summarize, "ask_recording_stream", broken)
    rec = db.create_recording("Frage", "", status="done")
    a = api_mod.Api(hub)
    got = collect(a)
    i = a.stream(f"/api/recordings/{rec['id']}/ask", {"question": "Was?"})
    assert pump(lambda: i in got)
    assert got[i] == (False, 200, "Kein API-Key")


def test_upload_and_job_events(qt, hub, tmp_path, monkeypatch):
    from rekord import jobs, pipeline
    seen = []
    monkeypatch.setattr(pipeline, "enroll_from_audio", lambda name, path, mode="read": seen.append((name, Path(path).read_bytes(), mode)) or {"id": 1, "name": name, "quality": {"seconds": 40}})
    f = tmp_path / "probe.wav"
    f.write_bytes(b"RIFF-demo")
    a = api_mod.Api(hub)
    got, events = collect(a), []
    a.event.connect(events.append)
    i = a.upload("/api/profiles/enroll", f.as_uri(), json.dumps({"name": "Anna", "mode": "free"}))
    assert pump(lambda: i in got)
    assert got[i][0] and got[i][2]["name"] == "Anna" and seen == [("Anna", b"RIFF-demo", "free")]
    threading.Thread(target=jobs.emit, args=({"type": "progress", "id": "x1", "progress": 0.5},)).start()
    assert pump(lambda: any(e.get("id") == "x1" for e in events))


def test_export_files_and_pdf(qt, tmp_path):
    rec = db.create_recording("Export Test", "", status="done")
    sid = db.add_speaker(rec["id"], "Anna", "#3B82F6", None)
    conn = db.connect()
    conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text) VALUES (?,?,?,?,?)", (rec["id"], sid, 0, 4, "Hallo Welt."))
    conn.commit()
    db.add_summary(rec["id"], "meeting", "Protokoll", "## Punkte\n- [ ] Anna: Angebot [00:02]")
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"audio")
    db.update_recording(rec["id"], audio_path=str(audio))
    a = api_mod.Api(1)
    msgs = []
    a.saved.connect(lambda ok, m: msgs.append((ok, m)))
    for fmt in ("md", "txt", "srt", "json", "audio", "pdf"):
        a.saveExport(rec["id"], fmt, (tmp_path / f"out.{fmt}").as_uri())
    assert pump(lambda: len(msgs) == 6, 20), msgs
    assert all(ok for ok, _ in msgs), msgs
    assert "Hallo Welt." in (tmp_path / "out.md").read_text() and "Anna" in (tmp_path / "out.srt").read_text()
    assert (tmp_path / "out.audio").read_bytes() == b"audio"
    assert (tmp_path / "out.pdf").read_bytes()[:5] == b"%PDF-"
    assert "Hallo Welt." in a.exportText(rec["id"])


def test_values_from_qml_become_plain_json(qt):
    """Qt 6.9 (the Linux build) passes nested JS arrays/objects as QJSValue – the API must still send JSON."""
    import json

    from PySide6.QtQml import QJSEngine

    from rekord.app.api import plain
    e = QJSEngine()
    v = e.evaluate('({template_order: ["meeting", "todo"], deep: [1, {b: [true, null, "x"]}], n: 2.5})')
    out = plain(v)
    assert json.loads(json.dumps(out)) == {"template_order": ["meeting", "todo"], "deep": [1, {"b": [True, None, "x"]}], "n": 2.5}
    assert plain({"a": e.evaluate("[1, 2]")}) == {"a": [1, 2]} and plain("text") == "text" and plain(None) is None


def test_markdown_for_the_window():
    h = md.render("# Titel\n## Aufgaben\n- [ ] **Max**: Texte [12:34]\n- [x] erledigt\n1. eins\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
                  "Quelle [[abcdef12@1:02]] und [Link](https://rekord.app) <script>")
    assert '<a href="task:2"' in h and "☐" in h and "☑" in h and "<s>erledigt</s>" in h
    assert '<a href="seek:754">12:34</a>' in h and '<a href="rec:abcdef12:62">1:02</a>' in h
    assert "<ol><li>eins</li></ol>" in h and "<table" in h and '<a href="https://rekord.app">Link</a>' in h
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert md.toggle_task("- [ ] a\n- [x] b", 0) == "- [x] a\n- [x] b"
    assert md.toggle_task("- [ ] a\n- [x] b", 1) == "- [ ] a\n- [ ] b"
    assert "seek:" not in md.render("Zeit [01:00]", links=False)
    # in the window: links in the accent color (rich text doesn't follow the window's palette)
    tinted = md.render("Zeit [01:00] · [x](https://rekord.app)\n- [ ] to-do", link_color="#2d7ff9")
    assert tinted.count('style="color:#2d7ff9;text-decoration:none" href=') == 2 and "text-decoration:none;color:#2d7ff9" in tinted


def test_mind_map_layout_and_svg():
    src = "# Launch\n- Termin\n  - Freitag\n  - Montag\n- Recht"
    t = md.outline(src)
    assert t["text"] == "Launch" and [c["text"] for c in t["children"]] == ["Termin", "Recht"]
    m = md.mindmap(src)
    assert len(m["nodes"]) == 5 and len(m["edges"]) == 4 and m["width"] > 0 and m["height"] > 0
    assert {n["depth"] for n in m["nodes"]} == {0, 1, 2}
    svg = md.mindmap_svg(src)
    assert svg.startswith("<svg") and svg.count("<text") == 5 and "Freitag" in svg


def test_help_texts_and_reading_texts():
    t = texts.tips()
    assert len(t) > 60 and "theme" in t and "<b>" in t["theme"]
    a, b = texts.reading_text("Emil"), texts.reading_text("Emil", 1)
    assert a.startswith("Hallo, ich heiße Emil.") and a.endswith("zehn.") and a != b
    assert a.split(". ", 1)[1] == texts.reading_text("emil ").split(". ", 1)[1]  # same person → same sentences
    assert texts.reading_text("Tom", lang="en").startswith("Hi, my name is Tom.")
    assert texts.talk_idea("de") in texts.TALK_IDEAS["de"]


def test_player_without_a_sound_card_still_answers(qt, tmp_path):
    p = api_mod.Player()
    p.load(str(tmp_path / "fehlt.m4a"))
    p.seek(12)
    p.nextRate()
    assert p.rate == 1.25
    p.playRange(1, 30)
    pump(lambda: False, 0.3)
    p.stop()
    assert isinstance(p.available, bool)
