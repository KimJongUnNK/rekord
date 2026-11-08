"""Exports: Markdown, plain text, SRT, WebVTT, JSON, DOCX (if python-docx installed)."""
from __future__ import annotations

import datetime as dt
import io
import re
import json

from . import db, formulas
from .summarize import fmt_time


def _ts(t: float, sep: str) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}{sep}{ms % 1000:03d}"


def _data(rid: str):
    rec = db.get_recording(rid)
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid) if s["name"] != db.NOISE}
    segs = db.spoken_segments(rid)  # "Geräusch" lines stay out
    return rec, sp, segs


def markdown(rid: str, with_summary: bool = True, with_transcript: bool = True) -> str:
    """The recording as Markdown. with_transcript=False: only what was written up (summaries, mind map, notes) –
    the PDF of a 3-hour lecture is then a few pages instead of 45. Nothing written up yet: the transcript comes
    anyway, an empty document helps nobody."""
    rec, sp, segs = _data(rid)
    date = dt.datetime.fromtimestamp(rec["created_at"]).strftime("%d.%m.%Y %H:%M")
    out = [f"# {rec['title']}", "", f"*{date} · {fmt_time(rec['duration'] or 0)} · {', '.join(dict.fromkeys(sp.values()))}*", ""]
    written = False
    if with_summary:
        for s in db.list_summaries(rid):
            out += [f"## {s['title']}", "", formulas.to_text(s["content"]), ""]
            written = True
    if rec.get("notes"):
        out += ["## Notizen", "", formulas.to_text(rec["notes"]), ""]
        written = True
    if with_transcript or not written:
        out += ["## Transkript", ""]
        for s in segs:
            out.append(f"**{sp.get(s['speaker_id'], '?')}** [{fmt_time(s['start'])}]: {s['text']}  ")
    return "\n".join(out) + "\n"


def text(rid: str) -> str:
    _, sp, segs = _data(rid)
    return "\n".join(f"[{fmt_time(s['start'])}] {sp.get(s['speaker_id'], '?')}: {s['text']}" for s in segs) + "\n"


def srt(rid: str) -> str:
    _, sp, segs = _data(rid)
    return "\n".join(f"{i}\n{_ts(s['start'], ',')} --> {_ts(s['end'], ',')}\n{sp.get(s['speaker_id'], '?')}: {s['text']}\n"
                     for i, s in enumerate(segs, 1))


def vtt(rid: str) -> str:
    _, sp, segs = _data(rid)
    return "WEBVTT\n\n" + "\n".join(f"{_ts(s['start'], '.')} --> {_ts(s['end'], '.')}\n<v {sp.get(s['speaker_id'], '?')}>{s['text']}\n"
                                    for s in segs)


def as_json(rid: str) -> str:
    rec, sp, segs = _data(rid)
    return json.dumps({"recording": rec | {"peaks": None}, "speakers": db.list_speakers(rid),
                       "segments": [s | {"speaker": sp.get(s["speaker_id"])} for s in segs],
                       "summaries": db.list_summaries(rid)}, ensure_ascii=False, indent=2)


_INLINE = re.compile(r"(\*\*|__)(.+?)\1|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])"
                     r"|`([^`]+)`|\[\[[^\]@]+@(\d[\d:]*)\]\]|\[([^\]]+)\]\([^)]*\)")


def _runs(p, text: str, bold: bool = False) -> None:
    """Markdown inline → Word runs: **bold**, *italics*, `code`, [text](link) → text, [[id@12:34]] → 12:34.
    Whatever stays unmatched loses its stray asterisks – nothing like ** ends up in the document."""
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            p.add_run(_strip_marks(text[pos:m.start()])).bold = bold or None
        if m.group(2) is not None:
            _runs(p, m.group(2), bold=True)
        elif m.group(3) is not None or m.group(4) is not None:
            r = p.add_run(_strip_marks(m.group(3) or m.group(4)))
            r.italic, r.bold = True, bold or None
        elif m.group(5) is not None:
            r = p.add_run(m.group(5))
            r.font.name, r.bold = "Consolas", bold or None
        elif m.group(6) is not None:
            p.add_run(m.group(6)).bold = bold or None
        elif m.group(7) is not None:
            p.add_run(_strip_marks(m.group(7))).bold = bold or None
        pos = m.end()
    if pos < len(text):
        p.add_run(_strip_marks(text[pos:])).bold = bold or None


def _strip_marks(t: str) -> str:
    return t.replace("**", "").replace("__", "").replace("`", "")


def _md_to_docx(d, md: str, level: int = 2) -> None:
    """A summary (Markdown from the AI) as a proper Word document: headings, bullet and numbered lists (nested), to-dos
    as ☐/☑, tables as Word tables, quotes – no #, *, |, - [ ] left over."""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        st = line.strip()
        if not st or re.fullmatch(r"[-*_]{3,}", st):
            i += 1
            continue
        if st.startswith("|"):  # a table: header | --- | rows
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                cols = max(len(r) for r in rows)
                t = d.add_table(rows=len(rows), cols=cols)
                t.style = "Table Grid"
                for r, cells in enumerate(rows):
                    for c in range(cols):
                        cell = t.cell(r, c)
                        cell.text = ""
                        _runs(cell.paragraphs[0], cells[c] if c < len(cells) else "", bold=r == 0)
            continue
        m = re.match(r"(#{1,6})\s+(.*)", st)
        if m:
            d.add_heading(_strip_marks(re.sub(r"\*\*|__", "", m.group(2))).strip(), min(9, level + len(m.group(1)) - 1))
            i += 1
            continue
        indent = (len(line) - len(line.lstrip())) // 2
        m = re.match(r"[-*+•]\s+\[( |x|X)\]\s+(.*)", st)
        if m:
            p = d.add_paragraph(style="List Bullet" if indent == 0 else "List Bullet 2")
            p.add_run("☑ " if m.group(1).lower() == "x" else "☐ ")
            _runs(p, m.group(2))
            i += 1
            continue
        m = re.match(r"[-*+•]\s+(.*)", st)
        if m:
            p = d.add_paragraph(style="List Bullet" if indent == 0 else "List Bullet 2")
            _runs(p, m.group(1))
            i += 1
            continue
        m = re.match(r"\d+[.)]\s+(.*)", st)
        if m:
            p = d.add_paragraph(style="List Number" if indent == 0 else "List Number 2")
            _runs(p, m.group(1))
            i += 1
            continue
        if st.startswith(">"):
            p = d.add_paragraph(style="Quote")
            _runs(p, st.lstrip("> ").strip())
            i += 1
            continue
        _runs(d.add_paragraph(), st)
        i += 1


def _css(style: str) -> dict:
    out = {}
    for part in (style or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip().strip("'\"")
    return out


def _html_to_docx(d, html: str) -> None:
    """A summary formatted in REKORD's editor (Qt rich text HTML) → Word, format by format: bold, italic, underline,
    strikethrough, sub/superscript, font, size, colour, highlight, headings, bullet/numbered lists (nested), tables."""
    from html.parser import HTMLParser

    from docx.enum.text import WD_COLOR_INDEX
    from docx.shared import Pt, RGBColor

    def rgb(v: str):
        m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (v or "").strip())
        return RGBColor.from_string(m[1].upper()) if m else None

    def marker(v: str):
        """Word highlights come in a fixed set of colours: the one of the same colour family (by hue)."""
        import colorsys
        m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (v or "").strip())
        if not m:
            return None
        h, light, sat = colorsys.rgb_to_hls(*(int(m[1][i:i + 2], 16) / 255 for i in (0, 2, 4)))
        if sat < 0.25:
            return WD_COLOR_INDEX.GRAY_25 if light > 0.5 else WD_COLOR_INDEX.GRAY_50
        deg = h * 360
        for top, col in ((15, WD_COLOR_INDEX.RED), (75, WD_COLOR_INDEX.YELLOW), (165, WD_COLOR_INDEX.BRIGHT_GREEN),
                         (200, WD_COLOR_INDEX.TURQUOISE), (255, WD_COLOR_INDEX.BLUE), (290, WD_COLOR_INDEX.VIOLET),
                         (345, WD_COLOR_INDEX.PINK), (361, WD_COLOR_INDEX.RED)):
            if deg < top:
                return col
        return WD_COLOR_INDEX.YELLOW

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.fmt = [{}]          # inherited run formats
            self.lists = []          # "ul" / "ol" stack
            self.para = None
            self.table = None        # rows of cells (each a list of paragraphs' text runs)
            self.cell = None
            self.skip = 0            # inside <head>/<style>

        def _push(self, extra):
            self.fmt.append({**self.fmt[-1], **extra})

        def _new_para(self, tag):
            if self.cell is not None:
                return
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.para = d.add_heading("", min(int(tag[1]) + 1, 9))
            elif tag == "li" and self.lists:
                depth = len(self.lists)
                style = ("List Number" if self.lists[-1] == "ol" else "List Bullet") + (f" {min(depth, 3)}" if depth > 1 else "")
                try:
                    self.para = d.add_paragraph(style=style)
                except KeyError:
                    self.para = d.add_paragraph(style="List Number" if self.lists[-1] == "ol" else "List Bullet")
            else:
                self.para = d.add_paragraph()

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag in ("head", "style", "title"):
                self.skip += 1
                return
            css = _css(a.get("style", "")) if tag != "body" else {}  # the editor's base font isn't a format: Word's own stays
            f = {}
            if tag in ("b", "strong") or css.get("font-weight", "") in ("600", "700", "800", "900", "bold"):
                f["bold"] = True
            if css.get("font-weight", "") in ("400", "normal"):
                f["bold"] = False
            if tag in ("i", "em") or css.get("font-style") == "italic":
                f["italic"] = True
            deco = css.get("text-decoration", "")
            if tag == "u" or "underline" in deco:
                f["underline"] = True
            if tag in ("s", "strike", "del") or "line-through" in deco:
                f["strike"] = True
            va = css.get("vertical-align", "")
            if tag == "sub" or va == "sub":
                f["sub"] = True
            if tag == "sup" or va == "super":
                f["sup"] = True
            if css.get("color"):
                f["color"] = css["color"]
            if css.get("background-color") and tag not in ("table", "td", "tr", "body"):
                f["mark"] = css["background-color"]
            size = re.fullmatch(r"([\d.]+)pt", css.get("font-size", ""))
            if size:
                f["size"] = float(size[1])
            if css.get("font-family"):
                f["font"] = css["font-family"].split(",")[0].strip("'\" ")
            if tag in ("ul", "ol"):
                self.lists.append(tag)
            elif tag in ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
                self._new_para(tag)
            elif tag == "br" and self.para is not None:
                self.para.add_run().add_break()
            elif tag == "table":
                self.table = []
            elif tag == "tr" and self.table is not None:
                self.table.append([])
            elif tag in ("td", "th") and self.table is not None:
                self.cell = []
                self.table[-1].append(self.cell)
            if tag not in ("br", "img", "meta", "hr"):
                self._push(f)

        def handle_endtag(self, tag):
            if tag in ("head", "style", "title"):
                self.skip = max(0, self.skip - 1)
                return
            if tag in ("ul", "ol") and self.lists:
                self.lists.pop()
            elif tag in ("td", "th"):
                self.cell = None
            elif tag == "table" and self.table:
                rows = [r for r in self.table if r]
                cols = max(len(r) for r in rows) if rows else 0
                if cols:
                    t = d.add_table(rows=len(rows), cols=cols)
                    t.style = "Table Grid"
                    for i, r in enumerate(rows):
                        for j, runs in enumerate(r):
                            cp = t.cell(i, j).paragraphs[0]
                            for text, fm in runs:
                                self._run(cp, text, fm)
                self.table = None
            if tag not in ("br", "img", "meta", "hr") and len(self.fmt) > 1:
                self.fmt.pop()

        def _run(self, para, text, fm):
            r = para.add_run(text)
            if fm.get("bold") is not None:
                r.bold = fm["bold"]
            r.italic = fm.get("italic") or None
            r.underline = fm.get("underline") or None
            if fm.get("strike"):
                r.font.strike = True
            if fm.get("sub"):
                r.font.subscript = True
            if fm.get("sup"):
                r.font.superscript = True
            if rgb(fm.get("color", "")):
                r.font.color.rgb = rgb(fm["color"])
            if fm.get("mark") and marker(fm["mark"]):
                r.font.highlight_color = marker(fm["mark"])
            if fm.get("size"):
                r.font.size = Pt(fm["size"])
            if fm.get("font"):
                r.font.name = fm["font"]

        def handle_data(self, data):
            if self.skip or not data:
                return
            if self.cell is not None:
                if data.strip():
                    self.cell.append((data, dict(self.fmt[-1])))
                return
            if self.para is None:
                if not data.strip():
                    return
                self.para = d.add_paragraph()
            if not data.strip() and "\n" in data:  # line breaks between tags in the HTML, not text
                return
            text = data.replace("\n", " ")
            self._run(self.para, text.rstrip() if data.endswith("\n") else text, self.fmt[-1])

    P().feed(html or "")


def docx(rid: str) -> bytes:
    from docx import Document  # optional dependency
    rec, sp, segs = _data(rid)
    d = Document()
    d.add_heading(rec["title"], 0)
    for s in db.list_summaries(rid):
        d.add_heading(s["title"], 1)
        if s.get("rich"):
            _html_to_docx(d, s["rich"])  # formatted in the editor: every format as it is
        else:
            _md_to_docx(d, formulas.to_text(s["content"]))
    d.add_heading("Transkript", 1)
    for s in segs:
        p = d.add_paragraph()
        p.add_run(f"{sp.get(s['speaker_id'], '?')} [{fmt_time(s['start'])}]: ").bold = True
        p.add_run(_strip_marks(s["text"]))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


FORMATS = {
    "md": ("text/markdown", markdown),
    "txt": ("text/plain", text),
    "srt": ("application/x-subrip", srt),
    "vtt": ("text/vtt", vtt),
    "json": ("application/json", as_json),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx),
}
