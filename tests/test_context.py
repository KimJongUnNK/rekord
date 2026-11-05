"""Unterlagen: reading documents, finding their terms, correcting the transcript (locally, and with a local AI only),
switching corrections off, the cloud lock, summaries with the documents, and stopping an analysis. No models needed."""
import subprocess
import sys
import time

import pytest

from rekord import config, context, db, jobs
from rekord.llm import providers
import media  # noqa: E402 - tests/ is on the path (pytest rootdir)

AGENDA = """Agenda – Projekt-Kickoff Coffee Club Dornbirn
Teilnehmer: Emil Boenke, Lukas Hämmerle, Sarah Fitz (Röstwerk Vorarlberg)
1. Rückblick: Umsatz Q3, Espresso-Blend
2. Kassensystem: Umstieg von Orderbird auf SumUp POS, Anbindung an Zapier und Notion
3. Lieferant: Kaffeerösterei Dinzler, Vertrag bis 31.12.
4. Marketing: Instagram-Kampagne, Event im Spielboden Dornbirn
Emil Boenke übernimmt die Abstimmung mit Dinzler. Sarah Fitz klärt SumUp. Der Kubernetes-Cluster betrifft uns nicht.
"""

TRANSCRIPT = ["Also Emil Bönke hat gesagt, wir wechseln von Order Bird auf SumUp.",
              "Das läuft dann über Sapir in Notion rein.",
              "Mit Dinzla müssen wir den Vertrag verlängern.",
              "Lukas Hemmerle war in der Rösterei.",
              "Kuberneetes brauchen wir nicht. Der Vortrag war gut, das Konzept auch, die Strategiepapiere kommen morgen."]


def _rec(lines, status="done"):
    rec = db.create_recording("Kickoff", "", status=status)
    sid = db.add_speaker(rec["id"], "Emil", "#FF5A1F")
    conn = db.connect()
    for i, t in enumerate(lines):
        cur = conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text) VALUES (?,?,?,?,?)",
                           (rec["id"], sid, i * 5.0, i * 5.0 + 4, t))
        conn.execute("INSERT INTO segments_fts(text,recording_id,segment_id) VALUES(?,?,?)", (t, rec["id"], cur.lastrowid))
    conn.commit()
    return rec["id"]


def _texts(rid):
    return [s["text"] for s in db.list_segments(rid)]


NO_AI = {"llm": {"provider": "none"}}


def _settings(**kw):
    s = config.load()
    s.update(kw)
    return s


# ------------------------------------------------------------------ reading

def test_reads_every_document_format(tmp_path):
    rid = _rec(["x"])
    files = {
        "a.docx": media.docx(tmp_path / "a.docx", ["Vertrag mit Röstwerk Vorarlberg", "Ansprechpartner: Emil Boenke"]),
        "b.pptx": media.pptx(tmp_path / "b.pptx", [["Kickoff", "SumUp POS"], ["Zapier & Notion"]], notes={2: "Dinzler anrufen"}),
        "c.xlsx": media.xlsx(tmp_path / "c.xlsx", ["Orderbird", "Kaffeerösterei Dinzler"]),
        "d.odt": media.odt(tmp_path / "d.odt", ["Spielboden Dornbirn"]),
        "e.pdf": media.pdf_text(tmp_path / "e.pdf", ["Agenda Kickoff", "Teilnehmer: Lukas Hämmerle, Sarah Fitz"]),
    }
    (tmp_path / "f.md").write_text("# Notizen\nInstagram-Kampagne mit Beeni", "utf-8")
    files["f.md"] = tmp_path / "f.md"
    (tmp_path / "g.html").write_text("<html><head><style>x{}</style></head><body><p>Webflow &amp; Co</p></body></html>", "utf-8")
    files["g.html"] = tmp_path / "g.html"
    (tmp_path / "h.rtf").write_text(r"{\rtf1\ansi{\fonttbl\f0 Arial;}\f0 Kaffeer\'f6sterei Dinzler\par}", "utf-8")
    files["h.rtf"] = tmp_path / "h.rtf"
    for p in files.values():
        context.add(rid, p)
    names = [d["name"] for d in context.items(rid)]
    assert sorted(names) == sorted(files)
    t = {n: context.text_of(rid, n) for n in names}
    assert "Emil Boenke" in t["a.docx"]
    assert "Folie 1" in t["b.pptx"] and "SumUp POS" in t["b.pptx"] and "Notizen: Dinzler anrufen" in t["b.pptx"]
    assert "Kaffeerösterei Dinzler" in t["c.xlsx"]
    assert "Spielboden Dornbirn" in t["d.odt"]
    assert "Lukas Hämmerle" in t["e.pdf"]
    assert "Beeni" in t["f.md"]
    assert t["g.html"].strip() == "Webflow & Co"
    assert "Kaffeerösterei Dinzler" in t["h.rtf"]
    pdf = next(d for d in context.items(rid) if d["name"] == "e.pdf")
    assert pdf["pages"] == 1 and pdf["words"] > 3 and not pdf["needs_ai"]


def test_same_name_twice_and_unsupported(tmp_path):
    rid = _rec(["x"])
    (tmp_path / "agenda.txt").write_text("eins", "utf-8")
    context.add(rid, tmp_path / "agenda.txt")
    second = context.add(rid, tmp_path / "agenda.txt")
    assert second["name"] == "agenda (2).txt"
    (tmp_path / "alt.doc").write_bytes(b"\xd0\xcf")
    with pytest.raises(context.Unsupported, match="als PDF oder DOCX"):
        context.add(rid, tmp_path / "alt.doc")
    (tmp_path / "x.exe").write_bytes(b"MZ")
    with pytest.raises(context.Unsupported):
        context.add(rid, tmp_path / "x.exe")
    assert context.remove(rid, "agenda.txt") and not context.remove(rid, "agenda.txt")
    assert context.path(rid, "../../rekord.db") is None
    assert [d["name"] for d in context.items(rid)] == ["agenda (2).txt"]


def test_scanned_pdf_is_recognised_and_its_pages_found(tmp_path):
    jpg = media.jpeg(320, 180)
    p = media.pdf_scan(tmp_path / "scan.pdf", jpg, 320, 180)
    rid = _rec(["x"])
    d = context.add(rid, p)
    assert d["needs_ai"] and d["kind"] == "pdf"
    pages = list(context._pdf_page_images(p))
    assert len(pages) == 1 and pages[0][0][:2] == b"\xff\xd8" and pages[0][1] == ".jpg"
    pics = context._pictures(context.items(rid)[0])
    assert len(pics) == 1 and pics[0][:2] == b"\xff\xd8"


@pytest.mark.skipif(sys.platform == "darwin", reason="the Mac reads pictures itself")
def test_pictures_without_a_local_ai_say_what_would_read_them(tmp_path):
    (tmp_path / "board.jpg").write_bytes(media.jpeg())
    rid = _rec(["x"])
    context.add(rid, tmp_path / "board.jpg")
    context.run(rid, _settings(**NO_AI))
    d = context.items(rid)[0]
    assert d["needs_ai"] and "lokale KI" in d["note"]


def test_pictures_read_by_a_local_ai(tmp_path, monkeypatch):
    if sys.platform == "darwin":
        monkeypatch.setattr(context, "mac_ocr", lambda p: "")  # as if macOS found no text: the local AI next
    (tmp_path / "board.png").write_bytes(media.jpeg())  # a JPEG with .png ending: FFmpeg doesn't mind
    rid = _rec(["Die Zahlen von Röstwerk"])
    context.add(rid, tmp_path / "board.png")
    seen = []

    def read(settings, data, mime, prompt, max_tokens=4000):
        seen.append((data[:2], mime))
        return "Whiteboard: Röstwerk Vorarlberg, Kaffeerösterei Dinzler"
    monkeypatch.setattr(providers, "read_image", read)
    monkeypatch.setattr(providers, "complete", lambda *a, **k: '{"korrekturen": []}')
    s = _settings(llm={"provider": "ollama", "ollama": {"base_url": "http://localhost:11434", "model": "qwen2.5vl"}})
    context.run(rid, s)
    d = context.items(rid)[0]
    assert seen == [(b"\xff\xd8", "image/jpeg")]
    assert not d["needs_ai"] and d["via"] == "lokale KI" and "Dinzler" in context.text_of(rid, d["name"])


def test_pictures_never_go_to_a_cloud_ai(tmp_path, monkeypatch):
    if sys.platform == "darwin":
        monkeypatch.setattr(context, "mac_ocr", lambda p: "")
    (tmp_path / "board.jpg").write_bytes(media.jpeg())
    rid = _rec(["x"])
    context.add(rid, tmp_path / "board.jpg")
    monkeypatch.setattr(providers, "read_image", lambda *a, **k: pytest.fail("a picture went to the cloud"))
    monkeypatch.setattr(providers, "complete", lambda *a, **k: pytest.fail("Unterlagen went to the cloud"))
    context.run(rid, _settings(llm={"provider": "anthropic", "anthropic": {"api_key": "sk-test", "model": "claude-opus-5-5"}}))
    assert "Cloud" in context.items(rid)[0]["note"]


# ------------------------------------------------------------------ terms and local corrections

def test_terms_are_the_rare_words():
    t = context.terms(AGENDA, 60)
    low = [x.lower() for x in t]
    for want in ("boenke", "dinzler", "zapier", "sumup", "orderbird", "hämmerle", "kubernetes"):
        assert want in low, (want, t)
    for common in ("vertrag", "abstimmung", "agenda", "teilnehmer", "marketing"):
        assert common not in low, (common, t)
    assert "Emil Boenke" in t  # a name as a pair


def test_local_corrections_by_spelling_and_sound():
    t = context.terms(AGENDA)
    fixes = context.find_local(TRANSCRIPT, t, context.doc_words(AGENDA))
    pairs = {(f["from"], f["to"]) for f in fixes}
    assert ("Emil Bönke", "Emil Boenke") in pairs or ("Bönke", "Boenke") in pairs
    assert ("Order Bird", "Orderbird") in pairs
    assert ("Sapir", "Zapier") in pairs
    assert ("Dinzla", "Dinzler") in pairs
    assert any(t == "Lukas Hämmerle" or t == "Hämmerle" for _, t in pairs)
    assert any(f == "Kuberneetes" for f, _ in pairs)
    froms = {f for f, _ in pairs}
    assert not froms & {"Vortrag", "Konzept", "Strategiepapiere", "Notion", "SumUp", "Rösterei"}, pairs
    fixed = [context.apply_fixes(x, fixes) for x in TRANSCRIPT]
    assert "Emil Boenke" in fixed[0] and "Orderbird" in fixed[0]
    assert "Zapier" in fixed[1] and "Dinzler" in fixed[2]
    assert "Der Vortrag war gut, das Konzept auch, die Strategiepapiere kommen morgen." in fixed[4]


def test_phonetic():
    assert context.phonetic("Meier") == context.phonetic("Mayer") == context.phonetic("Maier")
    assert context.phonetic("Zapier") == context.phonetic("Sapir")
    assert context.phonetic("Vertrag") == context.phonetic("Vortrag")  # sounds alike – that's why real words are protected
    assert context._same_sound(context.phonetic("Dinzla"), context.phonetic("Dinzler"))


def test_apply_fixes_keeps_word_boundaries():
    fx = [{"from": "Sapir", "to": "Zapier"}]
    assert context.apply_fixes("Sapir, Sapiro und Sapir.", fx) == "Zapier, Sapiro und Zapier."
    assert context.apply_fixes("Sapir", [{"from": "Sapir", "to": "Zapier", "off": True}]) == "Sapir"


# ------------------------------------------------------------------ the whole step on a recording

def _agenda(tmp_path):
    p = tmp_path / "Agenda.txt"
    p.write_text(AGENDA, "utf-8")
    return p


def test_run_corrects_and_everything_can_be_undone(tmp_path):
    rid = _rec(TRANSCRIPT)
    context.add(rid, _agenda(tmp_path))
    r = context.run(rid, _settings(**NO_AI))
    assert r["fixes"] >= 5 and r["changed"] >= 4
    t = _texts(rid)
    assert "Zapier" in t[1] and "Dinzler" in t[2]
    segs = db.list_segments(rid)
    assert segs[1]["orig"] == TRANSCRIPT[1]  # what the recognizer wrote, kept
    assert db.search_segments("Zapier", rid=rid)  # the search finds the corrected word
    fixes = db.get_recording(rid)["context_fixes"]
    assert all(f["by"] == "lokal" and f["count"] >= 1 for f in fixes)

    # one off → only that line goes back; it stays off when matching again
    context.toggle(rid, "Sapir", "Zapier", False)
    assert _texts(rid)[1] == TRANSCRIPT[1] and "Dinzler" in _texts(rid)[2]
    context.run(rid, _settings(**NO_AI))
    assert _texts(rid)[1] == TRANSCRIPT[1]
    assert any(f["from"] == "Sapir" and f["off"] for f in db.get_recording(rid)["context_fixes"])
    context.toggle(rid, "Sapir", "Zapier", True)
    assert "Zapier" in _texts(rid)[1]

    # your own edit wins: undo leaves that line alone
    db.update_segment(segs[2]["id"], text="Mit der Rösterei Dinzler reden wir.")
    context.undo_all(rid)
    t = _texts(rid)
    assert t[1] == TRANSCRIPT[1] and t[0] == TRANSCRIPT[0] and t[2] == "Mit der Rösterei Dinzler reden wir."
    assert all(f["off"] for f in db.get_recording(rid)["context_fixes"])


def test_removing_the_document_takes_its_corrections_along(tmp_path):
    rid = _rec(TRANSCRIPT)
    context.add(rid, _agenda(tmp_path))
    context.run(rid, _settings(**NO_AI))
    assert "Zapier" in _texts(rid)[1]
    context.remove(rid, "Agenda.txt")
    jobs._context(rid, always=True)
    assert _texts(rid) == TRANSCRIPT
    assert db.get_recording(rid)["context_fixes"] == []


def test_ai_may_only_correct_to_words_from_the_documents(tmp_path, monkeypatch):
    rid = _rec(TRANSCRIPT + ["Die Fitz-Bohne ist von Sarah Fits."])
    context.add(rid, _agenda(tmp_path))
    asked = []

    def complete(settings, system, messages, max_tokens=32000):
        asked.append(messages[0]["content"])
        return """Klar: {"korrekturen": [
            {"falsch": "Sarah Fits", "richtig": "Sarah Fitz"},
            {"falsch": "Bohne", "richtig": "Kaffeebohne"},
            {"falsch": "Gibtsnicht", "richtig": "Zapier"},
            {"falsch": "Vertrag", "richtig": "Dinzler"}]}"""
    monkeypatch.setattr(providers, "complete", complete)
    s = _settings(llm={"provider": "ollama", "ollama": {"base_url": "http://127.0.0.1:11434", "model": "qwen3:8b"}})
    context.run(rid, s)
    fixes = {(f["from"], f["to"]): f for f in db.get_recording(rid)["context_fixes"]}
    assert ("Sarah Fits", "Sarah Fitz") in fixes and fixes[("Sarah Fits", "Sarah Fitz")]["by"] == "KI"
    assert ("Bohne", "Kaffeebohne") not in fixes      # not in the documents: the AI's own idea
    assert ("Gibtsnicht", "Zapier") not in fixes      # not in the transcript
    assert ("Vertrag", "Dinzler") not in fixes        # "Vertrag" is in the documents: a real word
    assert "Sarah Fitz." in _texts(rid)[-1]
    assert "<begriffe>" in asked[0] and "Dinzler" in asked[0] and "<transkript>" in asked[0]


def test_cloud_ai_never_sees_the_documents_unless_allowed(tmp_path, monkeypatch):
    rid = _rec(TRANSCRIPT)
    context.add(rid, _agenda(tmp_path))
    cloud = {"llm": {"provider": "anthropic", "anthropic": {"api_key": "sk-test", "model": "claude-opus-5-5"}}}
    monkeypatch.setattr(providers, "complete", lambda *a, **k: pytest.fail("Unterlagen went to the cloud"))
    r = context.run(rid, _settings(**cloud))
    assert r["fixes"] >= 5 and "Cloud" in r["note"]  # the local matching still did its job
    calls = []
    monkeypatch.setattr(providers, "complete", lambda *a, **k: calls.append(1) or '{"korrekturen": []}')
    context.run(rid, _settings(context_cloud=True, **cloud))
    assert calls


def test_is_local():
    def loc(p, url=""):
        cfg = {"base_url": url, "model": "m", "api_key": "k"}
        return providers.is_local({"llm": {"provider": p, p: cfg}})
    assert loc("ollama") and loc("ollama", "http://localhost:11434") and loc("ollama", "http://192.168.1.20:11434")
    assert loc("compatible", "http://127.0.0.1:1234/v1") and loc("compatible", "http://mac-studio.local:1234/v1")
    assert not loc("compatible", "https://openrouter.ai/api/v1") and not loc("ollama", "https://ollama.example.com")
    assert not loc("anthropic") and not loc("openai")
    assert loc("openai", "http://10.0.0.5:8000/v1")


def test_summary_and_questions_see_the_documents_only_with_a_local_ai(tmp_path, monkeypatch):
    from rekord import summarize
    rid = _rec(TRANSCRIPT)
    context.add(rid, _agenda(tmp_path))
    seen = []

    def stream(settings, system, messages, max_tokens=32000):
        seen.append((system, messages[-1]["content"]))
        yield "ok"
    monkeypatch.setattr(providers, "stream", stream)
    local = _settings(llm={"provider": "ollama", "ollama": {"base_url": "http://localhost:11434", "model": "qwen3:8b"}})
    cloud = _settings(llm={"provider": "anthropic", "anthropic": {"api_key": "sk", "model": "claude-opus-5-5"}})
    for s, has in ((local, True), (cloud, False), ({**cloud, "context_cloud": True}, True)):
        monkeypatch.setattr(config, "load", lambda s=s: s)
        seen.clear()
        list(summarize.generate_stream(rid, "meeting"))
        system, user = seen[0]
        assert ('<dokument name="Agenda.txt">' in user) is has
        assert ("Unterlagen" in system) is has
        seen.clear()
        list(summarize.ask_recording_stream(rid, "Wer klärt SumUp?"))
        assert ("<unterlagen>" in seen[0][0]) is has


def test_prompt_block_shares_the_budget():
    rid = _rec(["x"])
    d = context.folder(rid)
    d.mkdir(parents=True)
    for name, text in (("a.txt", "A" * 50_000), ("b.txt", "kurz")):
        (d / name).write_text(text, "utf-8")
        context._store(rid, name, {"kind": "text", "text": text})
    block = context.prompt_block(rid, 10_000)
    assert block.startswith("<unterlagen>") and "kurz" in block and "[…gekürzt]" in block and len(block) < 10_000


def test_hint_for_engines_that_take_one(tmp_path):
    rid = _rec(["x"])
    context.add(rid, _agenda(tmp_path))
    h = context.hint(rid)
    assert "Boenke" in h and "Zapier" in h and len(h) <= 800
    assert context.hint(_rec(["y"])) == ""


def test_live_fixer_reads_documents_added_while_recording(tmp_path):
    rid = _rec([])
    fix = context.LiveFixer(rid, config.load())
    assert fix("Das läuft über Sapir.") == "Das läuft über Sapir."
    context.add(rid, _agenda(tmp_path))
    fix._checked = 0
    assert fix("Das läuft über Sapir.") == "Das läuft über Zapier."


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS' own text recognition")
def test_mac_reads_text_on_a_picture(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1000, 260), "white")
    ImageDraw.Draw(img).text((40, 80), "Kaffeerösterei Dinzler", fill="black", font=ImageFont.load_default(size=72))
    img.save(tmp_path / "board.png")
    text = context.mac_ocr(tmp_path / "board.png")
    assert "Dinzler" in text, text


# ------------------------------------------------------------------ stopping an analysis

def test_cancel_a_waiting_analysis():
    rid = _rec([], status="queued")
    events = []
    jobs.subscribe(events.append)
    try:
        assert jobs.cancel(rid)
    finally:
        jobs.unsubscribe(events.append)
    rec = db.get_recording(rid)
    assert rec["status"] == "error" and rec["error"] == jobs.CANCELLED
    assert {"type": "cancelled", "id": rid} in events
    assert not jobs.cancel(rid)  # nothing left to stop
    jobs.enqueue(rid)  # „Nochmal“
    assert not jobs.is_cancelled(rid) and db.get_recording(rid)["status"] == "queued"
    db.update_recording(rid, status="done")


def test_cancel_ends_the_running_analysis_process(monkeypatch):
    rid = _rec([], status="processing")
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    monkeypatch.setattr(jobs, "_child", proc)
    monkeypatch.setattr(jobs, "_current", rid)
    t0 = time.time()
    assert jobs.cancel(rid)
    assert proc.poll() is not None and time.time() - t0 < 5
    assert db.get_recording(rid)["error"] == jobs.CANCELLED


def test_cancelled_analysis_in_process_stops_at_the_next_step(monkeypatch):
    from rekord import pipeline
    rid = _rec([], status="processing")
    jobs._cancelled.add(rid)
    try:
        monkeypatch.setattr(pipeline.audio, "load", lambda p: pytest.fail("should have stopped before loading"))
        db.update_recording(rid, audio_path="/nonexistent.wav")
        with pytest.raises(RuntimeError, match="Abgebrochen"):
            pipeline.process(rid)
    finally:
        jobs._cancelled.discard(rid)
        db.update_recording(rid, status="error", error=jobs.CANCELLED)  # nothing left for a later worker to pick up
