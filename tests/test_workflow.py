"""Workflow: one transcript from several files, a mind map with branches and lines (even from a small local model),
and telling the AI what to change in a summary – with Rückgängig."""
import io
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from rekord import db, jobs, summarize
from rekord.app import md
from rekord.llm import providers
from rekord.server import app


@pytest.fixture(scope="module")
def client():
    app.state.auto_download = False
    with TestClient(app) as c:
        yield c


def _wav(seconds: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)  # noqa: E702
        w.writeframes((np.sin(np.arange(int(16000 * seconds)) / 8) * 3000).astype("<i2").tobytes())
    return buf.getvalue()


# ------------------------------------------------------------------ several files → one transcript

def test_several_files_become_one_recording(client, monkeypatch):
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    files = [("files", ("VO Statistik Teil 2.wav", _wav(1.5), "audio/wav")),
             ("files", ("VO Statistik Teil 1.wav", _wav(2.0), "audio/wav"))]
    before = len(db.list_recordings())
    r = client.post("/api/recordings", files=files, data={"combine": "true"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1 and len(db.list_recordings()) == before + 1
    rec = db.get_recording(items[0]["id"])
    assert rec["title"] == "VO Statistik"  # "Teil 1" off: it's all the parts
    assert 4.3 < rec["duration"] < 4.7  # 2 s (Teil 1 first) + 1 s pause + 1.5 s
    assert queued == [rec["id"]]  # transcribed once, as a whole


def test_without_combine_each_file_stays_its_own(client, monkeypatch):
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": None)
    files = [("files", ("a.wav", _wav(1.0), "audio/wav")), ("files", ("b.wav", _wav(1.0), "audio/wav"))]
    assert len(client.post("/api/recordings", files=files).json()["items"]) == 2


# ------------------------------------------------------------------ mind map

def test_mind_map_understands_any_indentation():
    four = "- Thema\n    - Ast A\n        - eins\n        - zwei\n    - Ast B\n        - drei"
    t = md.outline(four)
    assert t["text"] == "Thema" and [c["text"] for c in t["children"]] == ["Ast A", "Ast B"]
    assert [len(c["children"]) for c in t["children"]] == [2, 1] and not md.is_flat(four)
    fenced = "<think>überlegen …</think>\n```markdown\n- T\n\t- A\n\t\t- x\n```"
    t = md.outline(fenced)
    assert t["text"] == "T" and t["children"][0]["children"][0]["text"] == "x"


def test_a_flat_list_is_recognised_and_its_first_line_is_the_topic():
    flat = "- Gewinn- und Verlustrechnung\n" + "\n".join(f"- Punkt {i}" for i in range(15))
    assert md.is_flat(flat)
    assert md.outline(flat)["text"] == "Gewinn- und Verlustrechnung"


def test_texts_are_not_cut_off_and_every_branch_has_a_line():
    src = "- Gewinner- und Verlustrechnung im Betrieb\n  - Jahresüberschuss und Feldbetrag\n    - Leistungsgröße und Erfolgsgröße\n  - B\n    - c"
    m = md.mindmap(src)
    texts = [n["text"] for n in m["nodes"]]
    assert "Gewinner- und Verlustrechnung im Betrieb" in texts and "Jahresüberschuss und Feldbetrag" in texts
    assert not any(t.endswith("…") for t in texts)
    assert len(m["edges"]) == len(m["nodes"]) - 1  # one line to every node but the centre
    centre = next(n for n in m["nodes"] if n["depth"] == 0)
    assert centre["w"] > len("Gewinner- und Verlustrechnung im Betrieb") * 8  # the centre grows with its text
    assert all(e["x2"] > e["x1"] for e in m["edges"]) and m["width"] > max(n["x"] for n in m["nodes"])


def test_a_flat_mind_map_is_sorted_into_branches(monkeypatch):
    flat = "- GuV\n- Umsatz\n- Rabatte\n- Abschreibung\n- Sonderabschreibung"
    asked = []

    def complete(settings, system, messages, max_tokens=0):
        asked.append(messages[0]["content"])
        return "- GuV\n  - Erlöse\n    - Umsatz\n    - Rabatte\n  - Aufwand\n    - Abschreibung\n    - Sonderabschreibung"
    monkeypatch.setattr(providers, "complete", complete)
    fixed = summarize.finish_mindmap({}, flat)
    assert asked == [flat] and not md.is_flat(fixed) and "Erlöse" in fixed
    nested = "- A\n  - B\n    - c"
    assert summarize.finish_mindmap({}, nested) == nested and len(asked) == 1  # already fine: no second call


# ------------------------------------------------------------------ "Sag der KI, was sie ändern soll" for summaries

def test_summary_changed_by_the_ai_and_back(client, monkeypatch):
    rec = db.create_recording("GuV", "", source="import")
    sid = db.add_summary(rec["id"], "auto", "Auto", "# GuV\n- **Umsatz** steigt\n- **Gewinn** sinkt")
    seen = []

    def complete(settings, system, messages, max_tokens=0):
        seen.append((system, messages[0]["content"]))
        return "```markdown\n# GuV\n– Umsatz steigt\n– Gewinn sinkt\n```"
    monkeypatch.setattr(providers, "complete", complete)
    r = client.post(f"/api/summaries/{sid}/ai", json={"instruction": "keine Sternchen, Gedankenstriche statt Punkte"})
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "# GuV\n– Umsatz steigt\n– Gewinn sinkt"  # code fence gone
    assert "keine Sternchen" in seen[0][1] and "**Umsatz**" in seen[0][1] and "Zeichen" in seen[0][0]
    sm = db.get_summary(sid)
    assert "**" not in sm["content"] and "**Umsatz**" in sm["prev"]
    assert client.post(f"/api/summaries/{sid}/undo").json()["content"].startswith("# GuV\n- **Umsatz**")
    assert client.post(f"/api/summaries/{sid}/undo").json()["content"].startswith("# GuV\n– Umsatz")  # and forth again
    assert client.post(f"/api/summaries/{sid}/ai", json={"instruction": " "}).status_code == 400
    assert client.post("/api/summaries/999999/ai", json={"instruction": "x"}).status_code == 404


def test_mind_map_svg_for_the_browser(client):
    rec = db.create_recording("MM", "", source="import")
    sid = db.add_summary(rec["id"], "mindmap", "Mind Map", "- Thema\n  - Ast\n    - Punkt")
    r = client.get(f"/api/summaries/{sid}/mindmap.svg?fg=%23111&fg2=%23555&bg=javascript:alert(1)")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert "<path" in r.text and "Punkt" in r.text and "javascript" not in r.text  # lines there, colours checked


# ------------------------------------------------------------------ several finished recordings → one

def _rec_with_audio(title: str, seconds: float, created: float, **fields):
    from rekord import config
    rec = db.create_recording(title, "", source="import")
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    p = config.AUDIO_DIR / f"{rec['id']}.wav"
    p.write_bytes(_wav(seconds))
    db.update_recording(rec["id"], audio_path=str(p), status="done", duration=seconds, **fields)
    with db.tx() as c:
        c.execute("UPDATE recordings SET created_at=? WHERE id=?", (created, rec["id"]))
    return db.get_recording(rec["id"])


def test_three_recordings_become_one_bigger_picture(client, monkeypatch, tmp_path):
    from rekord import context
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    c = _rec_with_audio("GuV Teil 3", 1.0, 3000, notes="Klausurrelevant")
    a = _rec_with_audio("GuV Teil 1", 2.0, 1000, highlights=[0.5], participants=["Dozentin"])
    b = _rec_with_audio("GuV Teil 2", 1.5, 2000, highlights=[1.0], participants=["Dozentin", "Emil"])
    doc = tmp_path / "Folien.txt"
    doc.write_text("Gewinn- und Verlustrechnung, Abschreibung", encoding="utf-8")
    context.add(b["id"], doc, name="Folien.txt")
    r = client.post("/api/recordings/merge", json={"ids": [c["id"], a["id"], b["id"]]})
    assert r.status_code == 200, r.text
    m = db.get_recording(r.json()["id"])
    assert m["title"] == "GuV" and queued == [m["id"]]  # transcribed once, as a whole
    assert 6.3 < m["duration"] < 6.7  # 2 + 1 + 1.5 + 1 + 1 – oldest first, pauses between
    assert m["highlights"] == [0.5, 4.0]  # Teil 2's star moved behind Teil 1 (2 s) + pause (1 s)
    assert m["participants"] == ["Dozentin", "Emil"] and "## GuV Teil 3\nKlausurrelevant" in m["notes"]
    assert [d["name"] for d in context.items(m["id"])] == ["Folien.txt"]
    assert all(db.get_recording(x["id"]) for x in (a, b, c))  # the originals stay


def test_merging_needs_two_finished_recordings(client, monkeypatch):
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": None)
    a = _rec_with_audio("Eins", 1.0, 1)
    assert client.post("/api/recordings/merge", json={"ids": [a["id"]]}).status_code == 400
    b = _rec_with_audio("Zwei", 1.0, 2)
    db.update_recording(b["id"], status="processing")
    r = client.post("/api/recordings/merge", json={"ids": [a["id"], b["id"]]})
    assert r.status_code == 400 and "Läuft noch" in r.json()["detail"]
    db.update_recording(b["id"], status="done")
    r = client.post("/api/recordings/merge", json={"ids": [a["id"], b["id"]], "title": "Woche 3"})
    assert r.status_code == 200 and r.json()["title"] == "Woche 3"


def test_merged_title():
    from rekord import pipeline
    assert pipeline.merged_title(["VO Statistik Teil 1", "VO Statistik Teil 2"]) == "VO Statistik"
    assert pipeline.merged_title(["Montag", "Dienstag", "Mittwoch"]) == "Montag + 2 weitere"


def test_recordings_picked_from_the_list_are_appended(client, monkeypatch):
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    main = _rec_with_audio("VO Teil 1", 2.0, 10, highlights=[1.0])
    p3 = _rec_with_audio("VO Teil 3", 1.0, 30, highlights=[0.5])
    p2 = _rec_with_audio("VO Teil 2", 1.0, 20, notes="Formel S. 12")
    r = client.post(f"/api/recordings/{main['id']}/append-recordings", json={"ids": [p3["id"], p2["id"], main["id"]]})
    assert r.status_code == 200, r.text
    m = db.get_recording(main["id"])
    assert 5.8 < m["duration"] < 6.2 and queued == [main["id"]]  # 2 + 1 + 1 + 1 + 1, itself skipped
    assert m["highlights"] == [1.0, 5.5]  # Teil 3 starts at 2 + 1 + 1 + 1 = 5 s
    assert "## VO Teil 2\nFormel S. 12" in m["notes"]
    assert db.get_recording(p2["id"]) and db.get_recording(p3["id"])  # they stay
    assert client.post("/api/recordings/nope/append-recordings", json={"ids": [p2["id"]]}).status_code == 404
    assert client.post(f"/api/recordings/{main['id']}/append-recordings", json={"ids": []}).status_code == 400
