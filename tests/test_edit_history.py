"""Transcript editing like in Word: every change (by hand, Suchen & Ersetzen, the AI) undo- and redoable; the AI's text
plain; and the Word export without Markdown leftovers (no ** or | or - [ ]). No models needed."""
import io

import pytest
from fastapi.testclient import TestClient

from rekord import config, db, export, history, transcript_ai
from rekord.llm import providers
from rekord.server import app


@pytest.fixture(scope="module")
def client():
    app.state.auto_download = False
    with TestClient(app) as c:
        yield c


def _rec(lines):
    rec = db.create_recording("Kickoff", "", status="done")
    db.replace_transcript(rec["id"], [{"label": 0, "name": "Emil", "color": "#FF5A1F"}],
                          [{"start": i * 5.0, "end": i * 5.0 + 4, "label": 0, "text": t} for i, t in enumerate(lines)])
    return rec["id"]


def _texts(rid):
    return [s["text"] for s in db.list_segments(rid)]


def test_undo_and_redo_many_steps_like_word():
    rid = _rec(["Hallo zusammen.", "Ähm, also das Wetter.", "Budget bis Freitag."])
    ids = [s["id"] for s in db.list_segments(rid)]
    history.change(rid, "Text bearbeitet", {ids[0]: "Hallo alle."})
    history.change(rid, "KI: Smalltalk weg", {}, [ids[1]])
    history.change(rid, "Ersetzen", {ids[2]: "Budget bis Montag."})
    assert _texts(rid) == ["Hallo alle.", "Budget bis Montag."]
    assert history.state(rid)["undo"] == "Ersetzen" and history.state(rid)["undo_count"] == 3
    assert history.undo(rid)["label"] == "Ersetzen"
    assert history.undo(rid)["label"] == "KI: Smalltalk weg"
    assert _texts(rid) == ["Hallo alle.", "Ähm, also das Wetter.", "Budget bis Freitag."]  # the removed line is back, in place
    assert history.redo(rid)["label"] == "KI: Smalltalk weg"
    assert _texts(rid) == ["Hallo alle.", "Budget bis Freitag."]
    history.change(rid, "Text bearbeitet", {ids[0]: "Servus."})  # a new change: what could be redone is gone
    assert history.state(rid)["redo"] == "" and not history.redo(rid)["done"]
    while history.undo(rid)["done"]:
        pass
    assert _texts(rid) == ["Hallo zusammen.", "Ähm, also das Wetter.", "Budget bis Freitag."]
    assert db.search_segments("Wetter", rid=rid)  # restored lines are found by the search again


def test_ai_edit_plain_text_and_safety(monkeypatch):
    rid = _rec(["Hallo zusammen, wie war das Wochenende?", "Gut. Also, zum Budget: 5000 Euro.", "Emir macht das bis Freitag."])
    ids = [s["id"] for s in db.list_segments(rid)]
    asked = []

    def complete(settings, system, messages, max_tokens=32000):
        asked.append(messages[0]["content"])
        return ('Hier: {"aendern": [{"id": %d, "text": "**Emil** macht das bis *Freitag*."}, {"id": 999, "text": "x"}],'
                ' "loeschen": [%d], "hinweis": "Smalltalk entfernt, Name korrigiert."}' % (ids[2], ids[0]))
    monkeypatch.setattr(providers, "complete", complete)
    s = {**config.load(), "llm": {"provider": "ollama", "ollama": {"base_url": "http://localhost:11434", "model": "qwen3:8b"}}}
    r = transcript_ai.edit(rid, "Lass den Smalltalk weg und schreib Emil statt Emir", s)
    assert r == {"changed": 1, "deleted": 1, "note": "Smalltalk entfernt, Name korrigiert."}
    assert _texts(rid) == ["Gut. Also, zum Budget: 5000 Euro.", "Emil macht das bis Freitag."]  # no ** or * left
    assert f"[{ids[2]}] Emil: Emir macht das" in asked[0] and "<anweisung>" in asked[0]
    assert history.undo(rid)["done"] and len(_texts(rid)) == 3

    monkeypatch.setattr(providers, "complete", lambda *a, **k: '{"aendern": [], "loeschen": [%s]}' % ",".join(map(str, ids)))
    rid2 = _rec(["a", "b", "c", "d"])
    ids2 = [x["id"] for x in db.list_segments(rid2)]
    monkeypatch.setattr(providers, "complete", lambda *a, **k: '{"loeschen": [%s]}' % ",".join(map(str, ids2)))
    with pytest.raises(transcript_ai.EditError, match="ganze Transkript"):
        transcript_ai.edit(rid2, "alles weg", s)
    with pytest.raises(transcript_ai.EditError):
        transcript_ai.edit(rid2, "  ", s)


def test_clean_removes_what_an_ai_adds():
    assert transcript_ai.clean("**Emil** macht *das*.") == "Emil macht das."
    assert transcript_ai.clean("- Budget bis Freitag") == "Budget bis Freitag"
    assert transcript_ai.clean("„Ja, passt.“") == "Ja, passt."
    assert transcript_ai.clean("3 * 4 = 12") == "3 * 4 = 12"  # a real asterisk stays


def test_api_hand_edit_find_replace_and_history(client):
    rid = _rec(["Wir treffen Emir.", "Emir zahlt."])
    ids = [s["id"] for s in db.list_segments(rid)]
    client.patch(f"/api/segments/{ids[0]}", json={"text": "Wir treffen Emil."})
    client.post(f"/api/recordings/{rid}/find_replace", json={"find": "Emir", "replace": "Emil"})
    h = client.get(f"/api/recordings/{rid}/transcript/history").json()
    assert h["undo_count"] == 2 and h["undo"].startswith("Ersetzen")
    assert client.get(f"/api/recordings/{rid}").json()["history"]["undo_count"] == 2
    r = client.post(f"/api/recordings/{rid}/transcript/undo").json()
    assert r["done"] and _texts(rid) == ["Wir treffen Emil.", "Emir zahlt."] and r["redo"].startswith("Ersetzen")
    client.post(f"/api/recordings/{rid}/transcript/undo")
    assert _texts(rid) == ["Wir treffen Emir.", "Emir zahlt."]
    client.post(f"/api/recordings/{rid}/transcript/redo")
    assert _texts(rid)[0] == "Wir treffen Emil."
    assert client.post(f"/api/recordings/{rid}/transcript/ai", json={"instruction": "x"}).status_code in (200, 400)


def test_word_export_has_no_markdown_leftovers():
    from docx import Document
    rid = _rec(["**Emil**: Budget passt.", "Gut."])
    db.add_summary(rid, "meeting", "Protokoll",
                   "# Kickoff\n\n## Entscheidungen\n- **Budget**: 5000 €, *verbindlich* [03:12]\n  - Detail mit `Code`\n"
                   "1. Erster Punkt\n\n## To-dos\n- [ ] Lisa: Angebot einholen\n- [x] Max: Raum buchen\n\n"
                   "| Wer | Was |\n|---|---|\n| **Emil** | Technik |\n\n> Zitat vom Kunden\n\n---\nMehr siehe [Link](https://x.y) und [[abc@12:34]].")
    doc = Document(io.BytesIO(export.docx(rid)))
    text = "\n".join(p.text for p in doc.paragraphs)
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    for bad in ("**", "- [", "|", "##", "`", "](", "[["):
        assert bad not in text, (bad, text)
    assert "☐ Lisa: Angebot einholen" in text and "☑ Max: Raum buchen" in text
    assert "Budget: 5000 €, verbindlich [03:12]" in text and "Mehr siehe Link und 12:34." in text
    assert cells == ["Wer", "Was", "Emil", "Technik"]
    bold = [r.text for p in doc.paragraphs for r in p.runs if r.bold]
    assert "Budget" in bold
    assert any(p.style.name == "List Bullet" for p in doc.paragraphs) and any(p.style.name == "Quote" for p in doc.paragraphs)
    assert "Emil: Budget passt." in text  # stray ** in the transcript gone too


def test_ai_edit_of_a_long_transcript_streams_progress_and_never_times_out(client, monkeypatch):
    """Like "Ändern" for summaries: a long lecture on a local model takes minutes – a plain request gave up after
    2 minutes. The stream shows "Teil 2 von 5 …" and ends with the result."""
    rid = _rec([f"Satz {i}: Die Abschreibung verteilt die Anschaffungskosten über die Nutzungsdauer, ähm, genau."
                for i in range(600)])
    first = db.list_segments(rid)[0]["id"]
    monkeypatch.setattr(providers, "context_chars", lambda s: 20000)
    monkeypatch.setattr(providers, "configured", lambda s: (True, ""))
    calls = []

    def complete(settings, system, messages, max_tokens=32000):
        calls.append(1)
        return '{"aendern": [{"id": %d, "text": "Satz 0: Die Abschreibung verteilt die Kosten."}]}' % first if len(calls) == 1 else "{}"
    monkeypatch.setattr(providers, "complete", complete)
    body = client.post(f"/api/recordings/{rid}/transcript/ai/stream", json={"instruction": "Ähms raus"}).text
    from rekord import summarize
    statuses = [summarize.status_text(m) for m in __import__("re").findall("\u0001[^\u0002]*\u0002", body)]
    assert len(calls) > 2 and len(statuses) == len(calls) and statuses[0].endswith(f"Teil 1 von {len(calls)} …")
    import json
    result = json.loads(__import__("re").sub("\u0001[^\u0002]*\u0002", "", body))
    assert result["changed"] == 1 and _texts(rid)[0] == "Satz 0: Die Abschreibung verteilt die Kosten."
    assert "Schreib, was" in client.post(f"/api/recordings/{rid}/transcript/ai/stream", json={"instruction": " "}).text
