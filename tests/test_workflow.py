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

    def stream(settings, system, messages, max_tokens=0):
        seen.append((system, messages[0]["content"]))
        yield from ["```markdown\n# GuV\n", "– Umsatz steigt\n– Gewinn sinkt\n```"]
    monkeypatch.setattr(providers, "stream", stream)
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


def test_ai_change_on_a_long_lecture_streams_progress_and_never_times_out(client, monkeypatch):
    """Emil: 2 h 43 min lecture, qwen3:8b, "Ändern" did nothing – the plain request gave up after 120 s while the
    transcript was still being condensed. Now it's a stream: progress first, then the new text, then saved."""
    rid = _long_lecture(1800)
    sid = db.add_summary(rid, "lecture", "Lernzettel", "# GuV\n## Prüfungsrelevant\n- **Abschreibung**, z. B.,.")
    settings = {"llm": {"provider": "ollama", "ollama": {"model": "qwen3:8b", "num_ctx": 32768}},
                "summary_language": "de", "timestamps": "ask"}
    monkeypatch.setattr(summarize.config, "load", lambda: settings)
    calls = []

    def stream(s, system, messages, max_tokens=0):  # like qwen3 through Ollama: thinks first, writes in small pieces
        calls.append(max_tokens)
        if max_tokens == summarize.MAP_TOKENS:
            yield "- Abschreibung verteilt Kosten über die Nutzungsdauer [01:00]"
            return
        yield from ["# GuV\n## Prüfungs", "relevant\n- **Abschreibung**, z. B. lineare ", "Abschreibung über 5 Jahre"]
    monkeypatch.setattr(providers, "stream", stream)
    monkeypatch.setattr(providers, "complete", lambda s, sy, m, mt=0: "".join(stream(s, sy, m, mt)))
    summarize._MAP_CACHE.clear()
    db.connect().execute("DELETE FROM condensed"); db.connect().commit()
    r = client.post(f"/api/summaries/{sid}/ai/stream", json={"instruction": "Bei Prüfungsrelevant Beispiele einfügen"})
    assert r.status_code == 200
    body = r.text
    assert summarize.STATUS in body and "Teil 1 von" in body and "Die KI ändert" in body  # the bar has something to show
    assert body.index("Die KI ändert") < body.index("# GuV")  # progress first, then the new version as it's written
    sm = db.get_summary(sid)
    assert "lineare Abschreibung über 5 Jahre" in sm["content"] and "z. B.,." in sm["prev"]  # saved, Rückgängig works
    # the condensed pieces survive a restart: the next change only makes the final call
    summarize._MAP_CACHE.clear()
    calls.clear()
    client.post(f"/api/summaries/{sid}/ai/stream", json={"instruction": "noch kürzer bitte"})
    assert calls and all(c != summarize.MAP_TOKENS for c in calls)


def test_ai_change_that_changes_nothing_or_returns_nothing_says_so(client, monkeypatch):
    rec = db.create_recording("Kurz", "", source="import")
    sid = db.add_summary(rec["id"], "auto", "Auto", "# Kurz\n- eins")
    answers = iter(["# Kurz\n- eins", "<think>hm</think>"])
    monkeypatch.setattr(providers, "stream", lambda s, sy, m, mt=0: iter([next(answers)]))
    body = client.post(f"/api/summaries/{sid}/ai/stream", json={"instruction": "kürzer"}).text
    assert "nichts geändert" in body  # an error the window shows – never silence
    body = client.post(f"/api/summaries/{sid}/ai/stream", json={"instruction": "kürzer"}).text
    assert "nichts zurückgegeben" in body
    assert db.get_summary(sid)["content"] == "# Kurz\n- eins"


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


# ------------------------------------------------------------------ the AI knows file names, Unterlagen – and the user's rules

def test_the_ai_knows_file_names_and_unterlagen_and_follows_the_users_rules(client, monkeypatch, tmp_path):
    from rekord import config, context
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": None)
    r = client.post("/api/recordings", files=[("files", ("VO GuV 03.11.wav", _wav(1.0), "audio/wav"))])
    rid = r.json()["items"][0]["id"]
    assert db.get_recording(rid)["files"] == ["VO GuV 03.11.wav"]
    doc = tmp_path / "Skript Kapitel 4.txt"
    doc.write_text("Abschreibung, Umsatzerlöse", encoding="utf-8")
    context.add(rid, doc, name="Skript Kapitel 4.txt")
    before = config.load()["llm"]
    config.save({"ai_instructions": "Antworte ohne Emojis, maximal drei Sätze.",  # a local AI: may see the Unterlagen
                 "llm": {"provider": "ollama", "ollama": {"base_url": "http://localhost:11434", "model": "qwen3:8b"}}})
    seen = []

    def stream(settings, system, messages, max_tokens=0):
        seen.append(system)
        yield "ok"
    monkeypatch.setattr(providers, "stream", stream)
    try:
        assert "".join(summarize.ask_recording_stream(rid, "Wie heißt die Datei?")) == "ok"
        assert "VO GuV 03.11.wav" in seen[0] and "Skript Kapitel 4.txt" in seen[0] and rid in seen[0]
        assert "ohne Emojis, maximal drei Sätze" in seen[0]
        assert "".join(summarize.ask_all_stream("Welche Datei war die GuV-Vorlesung?")) == "ok"
        assert "VO GuV 03.11.wav" in seen[1] and "Skript Kapitel 4.txt" in seen[1] and "ohne Emojis" in seen[1]
    finally:
        config.save({"ai_instructions": "", "llm": before})
    assert "ohne Emojis" not in summarize.system_prompt(config.load(), db.get_recording(rid))


def test_appended_and_merged_recordings_keep_their_file_names(client, monkeypatch):
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": None)
    a = _rec_with_audio("Teil 1", 1.0, 1)
    b = _rec_with_audio("Teil 2", 1.0, 2)
    db.add_files(a["id"], ["Teil 1.m4a"])
    db.add_files(b["id"], ["Teil 2.m4a"])
    m = client.post("/api/recordings/merge", json={"ids": [a["id"], b["id"]]}).json()
    assert db.get_recording(m["id"])["files"] == ["Teil 1.m4a", "Teil 2.m4a"]
    live = _rec_with_audio("Live Montag", 1.0, 3)  # no file behind it: its title stands for it
    client.post(f"/api/recordings/{a['id']}/append-recordings", json={"ids": [live["id"]]})
    assert db.get_recording(a["id"])["files"] == ["Teil 1.m4a", "Live Montag"]


# ------------------------------------------------------------------ timestamps only when asked

def test_timestamps_only_when_asked():
    s = {"timestamps": "ask"}
    assert not summarize.wants_times(s, "Was ist eine Abschreibung?")
    assert summarize.wants_times(s, "An welcher Stelle erklärt sie das?") and summarize.wants_times(s, "mit Zeitstempel bitte")
    assert summarize.wants_times({"timestamps": "always"}, "Was ist eine Abschreibung?")
    text = "Umsatz steigt [01:58]. Gewinn sinkt (1:02:03), siehe [[ab12cd34ef56@03:11]] und [Folie 3]."
    assert summarize.strip_times(text) == "Umsatz steigt. Gewinn sinkt, siehe und [Folie 3]."
    # streamed in tiny pieces: a timestamp torn apart is still caught, other brackets stay
    pieces = [text[i:i + 3] for i in range(0, len(text), 3)]
    assert "".join(summarize.strip_times_stream(iter(pieces))) == summarize.strip_times(text)


def test_answers_and_summaries_come_without_timestamps_unless_asked(client, monkeypatch):
    from rekord import config
    rec = db.create_recording("GuV", "", source="import")
    seg_rec = rec["id"]
    seen = []

    def stream(settings, system, messages, max_tokens=0):
        seen.append(system)
        yield from ["Umsatz ist die Leistungs", "größe [01", ":58]."]
    monkeypatch.setattr(providers, "stream", stream)
    config.save({"timestamps": "ask"})
    assert "".join(summarize.ask_recording_stream(seg_rec, "Was ist Umsatz?")) == "Umsatz ist die Leistungsgröße."
    assert "KEINE Zeitstempel" in seen[-1]
    assert "".join(summarize.ask_recording_stream(seg_rec, "An welcher Stelle sagt sie das?")).endswith("[01:58].")
    assert "Belege wichtige Aussagen mit Zeitstempeln" in seen[-1]
    assert "".join(summarize.ask_all_stream("Was ist Umsatz?")) == "Umsatz ist die Leistungsgröße."
    try:
        config.save({"timestamps": "always"})
        assert "".join(summarize.ask_all_stream("Was ist Umsatz?")).endswith("[01:58].")
    finally:
        config.save({"timestamps": "ask"})


# ------------------------------------------------------------------ long lectures on a small local model

def _long_lecture(lines: int) -> str:
    rec = db.create_recording("VO 2h43", "", status="done")
    sid = db.add_speaker(rec["id"], "Dozentin", "#FF5A1F")
    conn = db.connect()
    for i in range(lines):
        conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text) VALUES (?,?,?,?,?)",
                     (rec["id"], sid, i * 5.0, i * 5.0 + 4, f"Satz {i}: Die Abschreibung verteilt die Anschaffungskosten "
                                                           f"über die Nutzungsdauer, das ist prüfungsrelevant."))
    conn.commit()
    return rec["id"]


def test_a_long_lecture_is_condensed_in_small_pieces_with_progress_and_remembered(monkeypatch):
    from rekord.app import api as app_api
    rid = _long_lecture(1800)  # ~2.5 h of speech: far more than an 8B model's context
    settings = {"llm": {"provider": "ollama", "ollama": {"model": "qwen3:8b", "num_ctx": 32768}},
                "summary_language": "de", "timestamps": "ask"}
    monkeypatch.setattr(summarize.config, "load", lambda: settings)
    calls = []

    def stream(s, system, messages, max_tokens=0):
        calls.append((len(messages[-1]["content"]), max_tokens))
        yield "- Abschreibung verteilt Kosten [01:00]" if max_tokens == summarize.MAP_TOKENS else "# GuV\nFertig."
    monkeypatch.setattr(providers, "stream", stream)
    summarize._MAP_CACHE.clear()
    db.connect().execute("DELETE FROM condensed"); db.connect().commit()  # as if never condensed before (they're kept across restarts)
    out = list(summarize.generate_stream(rid, "lecture"))
    states = [o for o in out if summarize.is_status(o)]
    pieces = [c for c in calls if c[1] == summarize.MAP_TOKENS]
    assert len(pieces) >= 6 and all(n <= summarize.MAP_CHARS + 300 for n, _ in pieces)  # small pieces, short notes
    labels = [summarize.status_text(x) for x in states]
    assert labels[0] == "Transkript wird vorbereitet …" and "Teil 1 von" in labels[1]
    assert len(states) == len(pieces) + 3  # vorbereiten, je Teil, verdichtet, KI liest
    from rekord.app.api import progress_of
    values = [progress_of(x)[0] for x in states]
    assert values == sorted(values) and 0 < values[0] < values[-1] < 0.8  # the bar only moves forward
    assert "".join(o for o in out if not summarize.is_status(o)) == "# GuV\nFertig."
    # again (after a "timed out", or the next question): the pieces are remembered – only the final call is made
    calls.clear()
    assert "".join(summarize.ask_recording_stream(rid, "Was ist prüfungsrelevant?")).endswith("Fertig.")
    assert [c for c in calls if c[1] == summarize.MAP_TOKENS] == [] and len(calls) == 1
    # what the window shows while waiting – and that statuses never end up in a saved summary
    assert app_api.shown(summarize.status("Teil 2 von 7 wird verdichtet …", 0.3)) == "*Teil 2 von 7 wird verdichtet …*"
    assert app_api.shown(summarize.status("x") + "# GuV") == "# GuV"
    res = summarize.generate(rid, "lecture")
    assert res["content"] == "# GuV\nFertig." and "\u0001" not in db.get_summary(res["id"])["content"]


def test_ollama_silence_is_long_enough_and_explained(monkeypatch):
    import httpx
    from rekord.llm import ollama as ol
    assert providers.OLLAMA_SILENCE >= 1800
    monkeypatch.setattr(ol, "start", lambda base: True)

    def silent(*a, **k):
        raise httpx.ReadTimeout("timed out")
    monkeypatch.setattr(httpx, "stream", silent)
    with pytest.raises(providers.LLMError) as e:
        list(providers._ollama({"model": "qwen3:8b"}, "s", [{"role": "user", "content": "x"}], 100))
    assert "30 Minuten" in str(e.value) and "gemerkt" in str(e.value)


def test_progress_bar_while_summarizing():
    from rekord.app.api import progress_of
    assert progress_of("Eine normale Antwort im Chat.") == (-1.0, "")  # no bar for plain answers
    start = summarize.status("Die KI liest das Transkript …", 0.08)
    assert progress_of(start) == (0.08, "Die KI liest das Transkript …")
    half = progress_of(start + "x" * 1750)
    assert half[1] == "Die KI schreibt …" and 0.5 < half[0] < 0.6
    assert progress_of(start + "x" * 99999)[0] == 0.97  # never 100 % before it's really done
    after_pieces = summarize.status("Alles verdichtet", 0.72) + summarize.status("liest", 0.74) + "x"
    assert progress_of(after_pieces)[0] > 0.74


# ------------------------------------------------------------------ formulas readable everywhere

def test_latex_from_the_ai_becomes_readable_formulas():
    from rekord import formulas
    t = formulas.to_text
    assert t(r"Rentabilität: $R = \frac{G}{K} \cdot 100\,\%$") == "Rentabilität: R = G / K · 100 %"
    assert t(r"- **AfA**: $AfA = \frac{AK - RW}{n}$") == "- **AfA**: AfA = (AK − RW) / n"
    assert t(r"$$\text{Gewinn} = \text{Umsatz} - \text{Kosten}$$") == "Gewinn = Umsatz − Kosten"
    assert t(r"C_0 = \sum_{t=1}^{n} \frac{CF_t}{(1+i)^t} - I_0") == "C₀ = Σₜ₌₁ⁿ CFₜ / (1+i)ᵗ − I₀"
    assert t(r"\Delta K = K_{fix} + k_v \times x") == "ΔK = K_fix + kᵥ × x"
    assert t(r"\sqrt{a^2+b^2}, \sqrt[3]{x}, E = mc^2, x^-1") == "√(a²+b²), ∛x, E = mc², x⁻¹"
    assert t(r"\( a \leq b \) und \[ \alpha \approx 0{,}05 \]") == "a ≤ b und α ≈ 0,05"
    assert t(r"$CR = \frac{K\ddot{a}ufe}{Besuche} \cdot 100\,\%$") == "CR = Käufe / Besuche · 100 %"
    # left alone: money, file names, code, words with underscores, text without formulas
    for same in ("Preis $5 und $10", "Datei VO_GuV_03.m4a", "Code `x^2` bleibt", "snake_case", "Gewinn = Umsatz − Kosten"):
        assert t(same) == same


def test_formulas_are_readable_in_the_window_in_word_and_in_saved_summaries(client, monkeypatch):
    docx = pytest.importorskip("docx")
    from rekord.app import md as app_md
    from rekord.app import richtext
    src = "## Definitionen & Formeln\n- Rentabilität: $R = \\frac{G}{K} \\cdot 100$"
    assert "R = G / K · 100" in app_md.render(src) and "\\frac" not in app_md.render(src)  # old summaries too
    assert "R = G / K · 100" in richtext.plain(src)  # copy for Word: clean text …
    assert "\\frac" not in richtext.markdown_to_html(src)  # … and formatted
    rec = db.create_recording("BWL", "", source="import")
    db.add_summary(rec["id"], "lecture", "Lernzettel", src)
    raw = client.get(f"/api/recordings/{rec['id']}/export/docx")
    text = "\n".join(p.text for p in docx.Document(io.BytesIO(raw.content)).paragraphs)
    assert "R = G / K · 100" in text and "\\" not in text and "$" not in text
    assert "R = G / K · 100" in client.get(f"/api/recordings/{rec['id']}/export/md").text
    # a new summary: the AI is told how to write formulas, and what it writes anyway is saved readable
    seen = []

    def stream(settings, system, messages, max_tokens=0):
        seen.append(system)
        yield "Gewinn: $G = U - K$"
    monkeypatch.setattr(providers, "stream", stream)
    real = summarize.config.load()
    monkeypatch.setattr(summarize.config, "load", lambda: {**real, "llm": {"provider": "ollama", "ollama": {"model": "x"}}})
    res = summarize.generate(_long_lecture(3), "lecture")
    assert db.get_summary(res["id"])["content"] == "Gewinn: G = U − K"
    assert "KEIN LaTeX" in seen[-1]


# ------------------------------------------------------------------ Einstellungen → KI-Verhalten: one block, every AI call

def test_ai_preferences_reach_every_ai_call_exactly_once(client, monkeypatch):
    rec = db.create_recording("Pref", "", status="done")
    spk = db.add_speaker(rec["id"], "Dozentin", "#FF5A1F")
    conn = db.connect()
    conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text) VALUES (?,?,?,?,?)",
                 (rec["id"], spk, 0, 4, "Die Abschreibung verteilt Kosten über die Nutzungsdauer."))
    conn.commit()
    sid = db.add_summary(rec["id"], "auto", "Auto", "# Pref\n- Abschreibung")
    settings = {"llm": {"provider": "ollama", "ollama": {"model": "qwen3:8b"}}, "summary_language": "de",
                "timestamps": "ask", "ai_instructions": "Sag immer Servus am Ende.",
                "ai_prefs": {"length": "short", "tone": "friendly", "examples": True, "emojis": False}}
    monkeypatch.setattr(summarize.config, "load", lambda: settings)
    systems = []

    def stream(s, system, messages, max_tokens=0):
        systems.append(system)
        yield "# Pref 🚀\n- Abschreibung, z. B. [00:01].\n- Kurz ✅ und gut"
    monkeypatch.setattr(providers, "stream", stream)
    list(summarize.generate_stream(rec["id"], "auto"))
    list(summarize.edit_summary_stream(sid, "noch kürzer"))
    list(summarize.ask_recording_stream(rec["id"], "Was ist wichtig?"))
    list(summarize.ask_all_stream("Was ist wichtig?"))
    assert len(systems) == 4
    for system in systems:  # summary, AI change, question, question across all recordings
        assert system.count("Verhaltensregeln des Nutzers – immer einhalten") == 1, system[-800:]
        assert summarize.PREFS_LENGTH["short"] in system and summarize.PREFS_TONE["friendly"] in system
        assert "Keine Emojis" in system and "Sag immer Servus am Ende." in system and "z. B." in system
        assert system.count("KEINE Zeitstempel") <= 1 and system.count("Formelschrift") == 1  # said once, not three times
    # and what can be checked afterwards is checked: no emojis, no empty "z. B." left by the removed timestamp
    saved = db.get_summary(sid)["content"]
    assert "🚀" not in saved and "✅" not in saved and "z. B." not in saved and "Abschreibung." in saved
    answer = db.list_chat(rec["id"])[-1]["content"]
    assert "🚀" not in answer and "z. B.," not in answer
    settings["ai_prefs"]["emojis"] = True
    assert "🚀" in summarize.finish("Los 🚀", settings)


def test_empty_example_words_are_cleaned_and_real_examples_stay():
    f = summarize.fix_dangling
    assert f("- **SI-Basisgrößen** wurden mehrfach betont, z. B.,.") == "- **SI-Basisgrößen** wurden mehrfach betont."
    assert f("- **Rekuperation** ist ein Prüfungsgegenstand, z. B..") == "- **Rekuperation** ist ein Prüfungsgegenstand."
    assert f("- Wichtig (z. B. ).") == "- Wichtig."
    assert f("- Kosten, e.g.,") == "- Kosten."
    keep = "- Abschreibung, z. B. lineare Abschreibung über 5 Jahre."
    assert f(keep) == keep and f("Ende...") == "Ende..."
    # normal sentences, function calls, paths and code are never touched
    for text in ("We will see.", "Das dauert etwa.", "Rufe print() auf.", "Pfad: ../daten/x.txt",
                 "```\nf(), x..y, z. B.,.\n```", "Code: `print()` und `a, z. B.,.`", "Version 1..3 fehlt"):
        assert f(text) == text, text
    assert summarize.finish(summarize.strip_times("- **Ladung** ist zentral, z. B. [12:34]."), {}) == "- **Ladung** ist zentral."
    # streamed in pieces: an example that is still on its way is never cut off
    pieces = ["- Abschreibung, z. B.", " lineare Abschreibung [01:02] über 5 Jahre."]
    streamed = "".join(summarize.strip_times_stream(iter(pieces)))
    assert summarize.finish(streamed, {}) == "- Abschreibung, z. B. lineare Abschreibung über 5 Jahre."
    from rekord.llm import templates
    lecture = templates.get("lecture")["prompt"]
    assert "konkrete Beispiel" in lecture  # the template asks for the example, it doesn't leave a "z. B." to copy


def test_a_summary_written_in_the_window_is_finished_like_everywhere_else(client, monkeypatch):
    """The window's path (POST /api/recordings/{id}/summaries) saves through server.save – it must clean the same
    way: no empty "z. B." left by a removed timestamp, no emojis unless allowed, readable formulas."""
    rec = db.create_recording("Fenster", "", status="done")
    spk = db.add_speaker(rec["id"], "Dozentin", "#FF5A1F")
    conn = db.connect()
    conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text) VALUES (?,?,?,?,?)",
                 (rec["id"], spk, 0, 4, "Die Ladung ist zentral."))
    conn.commit()
    settings = {"llm": {"provider": "ollama", "ollama": {"model": "qwen3:8b"}}, "summary_language": "de",
                "timestamps": "ask", "ai_prefs": {"emojis": False}}
    monkeypatch.setattr(summarize.config, "load", lambda: settings)
    from rekord import server
    monkeypatch.setattr(server.config, "load", lambda: settings)
    monkeypatch.setattr(providers, "stream", lambda s, sy, m, mt=0: iter(
        ["# Ladung 🚀\n## Prüfungsrelevant\n- **Ladung** ist zentral, z. B. [00:01].\n- $Q = I \\cdot t$"]))
    r = client.post(f"/api/recordings/{rec['id']}/summaries", json={"template_id": "lecture"})
    assert r.status_code == 200
    saved = [x for x in db.list_summaries(rec["id"]) if x["template_id"] == "lecture"][-1]["content"]
    assert "🚀" not in saved and "z. B." not in saved and "- **Ladung** ist zentral." in saved
    assert "Q = I · t" in saved and "$" not in saved
