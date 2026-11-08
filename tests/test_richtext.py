"""Summaries edited like in Word – bold, italic, colour, marker, size, headings, lists – and copied or exported so
Word shows exactly that: real formatting, no "**" or "#"."""
import io
import os

import pytest

pytest.importorskip("PySide6.QtGui", exc_type=ImportError)

from fastapi.testclient import TestClient  # noqa: E402
from PySide6.QtGui import QGuiApplication, QTextDocument  # noqa: E402

from rekord import db  # noqa: E402
from rekord.app import richtext  # noqa: E402
from rekord.server import app  # noqa: E402


@pytest.fixture(scope="module")
def qt():
    old = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    a = QGuiApplication.instance() or QGuiApplication(["rekord-test"])
    yield a
    if old is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = old


@pytest.fixture(scope="module")
def client():
    app.state.auto_download = False
    with TestClient(app) as c:
        yield c


def _doc(text: str) -> QTextDocument:
    d = QTextDocument()
    d.setPlainText(text)
    return d


def _body(html: str) -> str:
    return html.split("<body", 1)[1].split(">", 1)[1]


# ------------------------------------------------------------------ the toolbar

def test_bold_italic_underline_toggle_on_and_off(qt):
    f, d = richtext.Formatter(), _doc("eins zwei drei")
    f.toggle(d, 0, 4, "bold")
    assert f.state(d, 0, 4)["bold"] and not f.state(d, 5, 9)["bold"]
    f.toggle(d, 0, 4, "bold")
    assert not f.state(d, 0, 4)["bold"]  # second click: off again, like in Word
    f.toggle(d, 5, 9, "italic")
    f.toggle(d, 10, 14, "underline")
    s = f.state(d, 10, 14)
    assert s["underline"] and not s["italic"] and f.state(d, 5, 9)["italic"]
    # Markdown (AI, search, .md) keeps bold/italic, but underline would become stray "_"
    assert f.markdown(d) == "eins *zwei* drei"


def test_no_selection_formats_the_word_at_the_cursor(qt):
    f, d = richtext.Formatter(), _doc("Umsatz steigt deutlich")
    f.toggle(d, 9, 9, "bold")  # cursor inside "steigt"
    assert f.markdown(d) == "Umsatz **steigt** deutlich"


def test_strike_sub_sup_size_font_colour_marker(qt):
    f, d = richtext.Formatter(), _doc("H2O E=mc2 alt neu")
    f.toggle(d, 1, 2, "sub")
    f.toggle(d, 8, 9, "sup")
    f.toggle(d, 10, 13, "strike")
    f.setSize(d, 14, 17, 18)
    f.setFont(d, 14, 17, "Georgia")
    f.setColor(d, 14, 17, "#C00000")
    f.setHighlight(d, 0, 3, "#FFF176")
    s = f.state(d, 14, 17)
    assert s["size"] == 18 and s["font"] == "Georgia"
    assert f.state(d, 1, 2)["sub"] and f.state(d, 8, 9)["sup"] and f.state(d, 10, 13)["strike"]
    h = _body(f.html(d))
    for want in ("vertical-align:sub", "vertical-align:super", "line-through", "font-size:18pt", "Georgia",
                 "#c00000", "#fff176"):
        assert want in h, want


def test_grow_steps_through_the_size_list(qt):
    f, d = richtext.Formatter(), _doc("Text")
    f.setSize(d, 0, 4, 12)
    f.grow(d, 0, 4, 1)
    assert f.state(d, 0, 4)["size"] == 14
    f.grow(d, 0, 4, -1)
    f.grow(d, 0, 4, -1)
    assert f.state(d, 0, 4)["size"] == 11
    f.setSize(d, 0, 4, 72)
    f.grow(d, 0, 4, 1)
    assert f.state(d, 0, 4)["size"] == 72  # the biggest stays the biggest


def test_removing_colour_or_marker_keeps_every_other_format(qt):
    f, d = richtext.Formatter(), _doc("eins zwei drei")
    f.toggle(d, 0, 4, "bold")
    f.toggle(d, 5, 9, "italic")
    f.setColor(d, 0, 14, "#C00000")
    f.setHighlight(d, 0, 14, "#FFF176")
    f.setColor(d, 0, 14, "")
    f.setHighlight(d, 0, 14, "")
    h = _body(f.html(d))
    assert "color" not in h and "background" not in h
    assert f.markdown(d) == "**eins** *zwei* drei"  # bold here, italic there – not one format for all


def test_clear_formatting(qt):
    f, d = richtext.Formatter(), _doc("ganz fett")
    f.toggle(d, 0, 9, "bold")
    f.setColor(d, 0, 9, "#2D7FF9")
    f.clear(d, 0, 9)
    assert f.markdown(d) == "ganz fett" and "color" not in _body(f.html(d))


def test_headings_and_lists(qt):
    f, d = richtext.Formatter(), _doc("Aufgaben\nTexte schreiben\nFreigabe holen")
    f.heading(d, 0, 0, 2)
    assert f.state(d, 0, 0)["heading"] == 2
    f.list(d, 9, 30, "bullet")
    assert f.state(d, 12, 12)["list"] == "bullet"
    md = f.markdown(d)
    assert md.startswith("## Aufgaben") and "- Texte schreiben" in md and "- Freigabe holen" in md
    f.list(d, 9, 30, "bullet")  # second click: list off
    assert f.state(d, 12, 12)["list"] == ""
    f.list(d, 9, 30, "number")
    assert f.state(d, 12, 12)["list"] == "number" and "1." in f.markdown(d)
    f.heading(d, 0, 0, 0)
    assert f.state(d, 0, 0)["heading"] == 0 and not f.markdown(d).startswith("#")


def test_markdown_reads_the_formats_not_the_installed_fonts(qt):
    """Qt's own toMarkdown() asks the system font whether text is bold – on Windows without that font, bold was lost.
    Ours reads the format: same Markdown on every computer, and it reads back into the same Markdown."""
    src = ("## Entscheidungen\n\n- Launch am **Freitag**\n  - Plan *B* ~~nie~~ [Link](https://x.at)\n- Rest\n\n"
           "1. eins\n2. zwei\n\n- [ ] offen\n- [x] erledigt\n\n| Wer | Was |\n|---|---|\n| **Max** | 3 \\* 4 |\n\nEnde")
    d = QTextDocument()
    d.setMarkdown(src)
    f = richtext.Formatter()
    assert f.markdown(d) == src
    t = d.toPlainText()
    f.setFont(d, 0, len(t), "Keine Solche Schrift 123")  # a font nobody has
    f.toggle(d, t.find("Ende"), t.find("Ende") + 4, "underline")
    assert f.markdown(d) == src  # still bold, and underline adds nothing


def test_load_prefers_the_formatted_version(qt):
    f, d = richtext.Formatter(), QTextDocument()
    f.load(d, "# Titel\n- **fett**", "")
    assert d.toPlainText().startswith("Titel") and "**" not in d.toPlainText()  # Markdown shown as formatting
    html = f.html(d)
    f.load(d, "nur Markdown", html)
    assert d.toPlainText().startswith("Titel")
    assert richtext.Formatter().fonts()[0] == "Aptos" and 12 in richtext.Formatter().sizes()


# ------------------------------------------------------------------ copy → Word

def test_copy_puts_real_formatting_on_the_clipboard(qt):
    cb = QGuiApplication.clipboard()
    richtext.copy_rich("# Protokoll\n- **Umsatz** steigt\n- Gewinn *sinkt*")
    m = cb.mimeData()
    if not m.hasHtml():
        pytest.skip("no clipboard on this platform/session")
    h = m.html()
    assert "font-weight:700" in h and "<li" in h and "Umsatz" in h  # Word pastes bold as bold, a list as a list
    assert "**" not in m.text() and "#" not in m.text() and "Umsatz steigt" in m.text()
    assert "<body>" in h  # REKORD's UI font isn't forced on Word


def test_copy_takes_the_edited_version(qt):
    f, d = richtext.Formatter(), _doc("rot und groß")
    f.setColor(d, 0, 3, "#C00000")
    f.setSize(d, 8, 12, 24)
    richtext.copy_rich("rot und groß", f.html(d))
    m = QGuiApplication.clipboard().mimeData()
    if not m.hasHtml():
        pytest.skip("no clipboard on this platform/session")
    assert "#c00000" in m.html() and "font-size:24pt" in m.html() and m.text() == "rot und groß"


def test_quitting_after_copying_doesnt_crash(tmp_path):
    """The clipboard outlives Python at quit: a QMimeData made in Python crashed REKORD on quit (segfault)."""
    import subprocess
    import sys
    code = ("from PySide6.QtGui import QGuiApplication\n"
            "app = QGuiApplication(['t'])\n"
            "from rekord.app import richtext\n"
            "richtext.copy_rich('# T\\n- **fett**')\n"
            "richtext.copy_rich('x', '<p><b>x</b></p>')\n"
            "print('ok')\n")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", REKORD_HOME=str(tmp_path))
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, (r.returncode, r.stderr[-800:])


def test_timestamps_in_the_formatted_view_jump_in_the_audio():
    h = richtext.display_html('<p style="x:1">Start [01:05] und [1:02:03]</p>', "#FF5A1F")
    assert 'href="seek:65"' in h and 'href="seek:3723"' in h and 'style="x:1"' in h


# ------------------------------------------------------------------ saved, undone, exported

def test_edited_summary_is_saved_and_exported_to_word_with_every_format(qt, client):
    docx = pytest.importorskip("docx")
    f, d = richtext.Formatter(), QTextDocument()
    f.load(d, "# Ergebnis\n\nUmsatz steigt stark\n\nPunkt eins\n\nPunkt zwei", "")
    t = d.toPlainText()
    f.toggle(d, t.find("Umsatz"), t.find("Umsatz") + 6, "bold")
    f.toggle(d, t.find("stark"), t.find("stark") + 5, "underline")
    f.setColor(d, t.find("steigt"), t.find("steigt") + 6, "#C00000")
    f.setHighlight(d, t.find("stark"), t.find("stark") + 5, "#FFF176")
    f.list(d, t.find("Punkt eins"), t.find("Punkt zwei") + 3, "bullet")
    rec = db.create_recording("Word", "", source="import")
    sid = db.add_summary(rec["id"], "auto", "Protokoll", "# Ergebnis")
    r = client.patch(f"/api/summaries/{sid}", json={"content": f.markdown(d), "rich": f.html(d)})
    assert r.status_code == 200, r.text
    sm = db.get_summary(sid)
    assert "**Umsatz**" in sm["content"] and "#c00000" in sm["rich"]

    raw = client.get(f"/api/recordings/{rec['id']}/export/docx")
    assert raw.status_code == 200
    doc = docx.Document(io.BytesIO(raw.content))
    runs = {r.text.strip(): r for p in doc.paragraphs for r in p.runs if r.text.strip()}
    assert runs["Umsatz"].bold
    assert str(runs["steigt"].font.color.rgb) == "C00000"
    assert runs["stark"].underline and runs["stark"].font.highlight_color is not None
    styles = {p.text: p.style.name for p in doc.paragraphs}
    assert styles["Punkt eins"].startswith("List Bullet") and styles["Ergebnis"].startswith("Heading")
    assert not any("**" in p.text or p.text.startswith("#") for p in doc.paragraphs)


def test_ai_or_typed_change_drops_the_stale_formatting_and_undo_brings_it_back(client):
    rec = db.create_recording("Undo", "", source="import")
    sid = db.add_summary(rec["id"], "auto", "P", "alt")
    client.patch(f"/api/summaries/{sid}", json={"content": "**neu**", "rich": "<p><b>neu</b></p>"})
    assert db.get_summary(sid)["rich"] == "<p><b>neu</b></p>"
    db.update_summary(sid, "ganz anders", keep_prev=True)  # e.g. the AI rewrote it: the old formatting no longer fits
    sm = db.get_summary(sid)
    assert sm["rich"] is None and sm["prev_rich"] == "<p><b>neu</b></p>"
    assert db.undo_summary(sid)
    sm = db.get_summary(sid)
    assert sm["content"] == "**neu**" and sm["rich"] == "<p><b>neu</b></p>"
    client.patch(f"/api/summaries/{sid}", json={"content": "x", "rich": 5})  # junk isn't stored as formatting
    assert db.get_summary(sid)["rich"] is None


# ------------------------------------------------------------------ PDF export: nothing cut off

def _tag(i: int) -> str:  # Satzbc, Satzbd … – letters, the same in every font
    return "".join("abcdefghij"[int(d)] for d in f"{i:03d}")


def test_pdf_export_keeps_every_line_inside_the_page(qt, tmp_path):
    pytest.importorskip("PySide6.QtPdf", exc_type=ImportError)
    from PySide6.QtCore import QSize
    from rekord.app import api as app_api
    rec = db.create_recording("VO Gewinn- und Verlustrechnung im Betrieb – Teil 1 und 2", "", status="done", duration=9000)
    sid = db.add_speaker(rec["id"], "Wirtschaft und Recht Dozentin", "#FF5A1F")
    conn = db.connect()
    for i in range(80):
        text = "Die Gewinn- und Verlustrechnung zeigt Umsatzerlöse und außerplanmäßige Abschreibungen. " * (1 + i % 3)
        if i % 7 == 0:
            text += "https://www.example.com/ein/sehr/langer/link/ohne/ein/einziges/leerzeichen/der/nicht/passt/" * 2
        conn.execute("INSERT INTO segments (recording_id, speaker_id, start, end, text) VALUES (?,?,?,?,?)",
                     (rec["id"], sid, i * 30.0, i * 30 + 25, f"Satz{_tag(i)} {text}"))
    conn.commit()
    db.add_summary(rec["id"], "lecture", "Lernzettel", "## Formeln\n- Rentabilität: $R = \\frac{G}{K} \\cdot 100$")
    out = tmp_path / "vo.pdf"
    saved = []

    class Api(app_api.Api):
        def __init__(self):  # only what the PDF writer needs
            pass
    a = Api.__new__(Api)
    a.saved = type("S", (), {"emit": lambda self, ok, msg: saved.append((ok, msg))})()
    app_api.Api._write_pdf(a, rec["id"], str(out))
    assert saved and saved[0][0], saved
    from PySide6.QtPdf import QPdfDocument  # the text as a PDF viewer reads it (pdfium) – fonts differ per system
    pdf = QPdfDocument()
    pdf.load(str(out))
    text = " ".join(pdf.getAllText(n).text() for n in range(pdf.pageCount()))
    text = " ".join(text.split())
    assert all(f"Satz{_tag(i)}" in text for i in range(80))  # every line of the transcript is in the PDF
    assert "G / K" in text and "frac" not in text  # formulas readable
    assert f"von {pdf.pageCount()}" in text and pdf.pageCount() >= 3  # footer with page numbers
    # nothing runs over the right margin: the outer strip of every page is blank
    for n in range(pdf.pageCount()):
        img = pdf.render(n, QSize(595, 842))
        ink = [(x, y) for x in range(565, 595) for y in range(0, 842, 2)
               if img.pixelColor(x, y).alpha() > 40 and img.pixelColor(x, y).lightness() < 200]
        assert not ink, f"page {n + 1}: text in the right margin at {ink[:3]}"
        body = [1 for x in range(60, 300) for y in range(100, 700, 4)
                if img.pixelColor(x, y).alpha() > 40 and img.pixelColor(x, y).lightness() < 200]
        assert body, "the check sees no text at all"
