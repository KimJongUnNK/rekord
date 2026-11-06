"""Exports: Markdown, plain text, SRT, WebVTT, JSON, DOCX (if python-docx installed)."""
from __future__ import annotations

import datetime as dt
import io
import re
import json

from . import db
from .summarize import fmt_time


def _ts(t: float, sep: str) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}{sep}{ms % 1000:03d}"


def _data(rid: str):
    rec = db.get_recording(rid)
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid) if s["name"] != db.NOISE}
    segs = db.spoken_segments(rid)  # "Geräusch" lines stay out
    return rec, sp, segs


def markdown(rid: str, with_summary: bool = True) -> str:
    rec, sp, segs = _data(rid)
    date = dt.datetime.fromtimestamp(rec["created_at"]).strftime("%d.%m.%Y %H:%M")
    out = [f"# {rec['title']}", "", f"*{date} · {fmt_time(rec['duration'] or 0)} · {', '.join(dict.fromkeys(sp.values()))}*", ""]
    if with_summary:
        for s in db.list_summaries(rid):
            out += [f"## {s['title']}", "", s["content"], ""]
    if rec.get("notes"):
        out += ["## Notizen", "", rec["notes"], ""]
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


def docx(rid: str) -> bytes:
    from docx import Document  # optional dependency
    rec, sp, segs = _data(rid)
    d = Document()
    d.add_heading(rec["title"], 0)
    for s in db.list_summaries(rid):
        d.add_heading(s["title"], 1)
        _md_to_docx(d, s["content"])
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
