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
