"""Tell the AI what to change in a transcript – "Lass den Smalltalk weg", "Schreib Emil statt Emir", "Mach aus den
Ähms ganze Sätze". It answers with changes to single lines (new text, or remove the line); speakers and times stay.
Each change is one step in the transcript's history (Rückgängig / Wiederholen, like in Word). The AI's text is cleaned
of formatting it likes to add (**, #, `, "- "), so the transcript – and the Word export – stays plain text."""
from __future__ import annotations

import json
import logging
import re

from . import db, history, summarize
from .llm import providers

log = logging.getLogger("rekord.transcript_ai")

SYSTEM = """Du bearbeitest das Transkript einer Aufnahme nach der Anweisung des Nutzers.
Jede Zeile hat die Form [id] Name: Text.

Regeln:
- Ändere nur Zeilen, die die Anweisung betrifft. Sprecher und Reihenfolge bleiben, Zeiten gibt es hier nicht.
- Eine Zeile entfernen: ihre id in "loeschen". Eine Zeile ändern: {"id": …, "text": "neuer Text"} in "aendern".
- Erfinde nichts dazu, was nicht gesagt wurde – außer die Anweisung verlangt ausdrücklich eine Umformulierung.
- Reiner Text: keine Formatierung, keine Sternchen, keine Rauten, keine Aufzählungszeichen, keine Anführungszeichen um den Satz.
- Antworte ausschließlich mit JSON: {"aendern": [{"id": 12, "text": "…"}], "loeschen": [7, 8], "hinweis": "ein Satz, was du getan hast"}
- Ist nichts zu tun, gib leere Listen zurück und sag im Hinweis warum."""


class EditError(RuntimeError):
    pass


def _lines(rid: str) -> tuple[list[dict], list[str]]:
    segs = db.spoken_segments(rid)
    sp = {s["id"]: s["name"] for s in db.list_speakers(rid)}
    return segs, [f"[{s['id']}] {sp.get(s['speaker_id'], 'Unbekannt')}: {s['text']}" for s in segs]


def clean(text: str) -> str:
    """Plain text: what an AI adds around a sentence (**bold**, *italics*, `code`, # headings, "- " bullets, quotes)."""
    t = " ".join(str(text or "").split())
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"^\s*(#+|[-*+•]|\d+[.)])\s+", "", t)
    t = t.replace("**", "").replace("__", "")
    if len(t) > 1 and t[0] in "\"„“»" and t[-1] in "\"“”«":
        t = t[1:-1].strip()
    return t


def _parse(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        raise EditError("Die KI hat keine verwertbare Antwort gegeben – Anweisung etwas genauer formulieren.")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise EditError("Die KI hat keine verwertbare Antwort gegeben – nochmal versuchen.") from e


def edit(rid: str, instruction: str, settings: dict) -> dict:
    """Apply the instruction. Returns {"changed": n, "deleted": n, "note": "…"}. Raises EditError / LLMError."""
    instruction = (instruction or "").strip()
    if not instruction:
        raise EditError("Schreib, was die KI ändern soll.")
    if not providers.configured(settings)[0]:
        raise EditError("Keine KI eingerichtet – Einstellungen → KI.")
    segs, lines = _lines(rid)
    if not segs:
        raise EditError("Das Transkript ist leer.")
    by_id = {s["id"]: s for s in segs}
    chunks = summarize._chunks("\n".join(lines), max(4000, int(providers.context_chars(settings) * 0.45)))
    changes: dict[int, str] = {}
    deletes: set[int] = set()
    notes = []
    for part in chunks:
        raw = providers.complete(settings, SYSTEM, [{"role": "user", "content":
                                 f"<anweisung>\n{instruction}\n</anweisung>\n<transkript>\n{part}\n</transkript>"}], 16000)
        data = _parse(raw)
        for c in data.get("aendern") or []:
            try:
                sid = int(c.get("id"))
            except (TypeError, ValueError, AttributeError):
                continue
            text = clean(c.get("text"))
            if sid in by_id and text and text != by_id[sid]["text"]:
                changes[sid] = text
        for d in data.get("loeschen") or []:
            try:
                sid = int(d)
            except (TypeError, ValueError):
                continue
            if sid in by_id:
                deletes.add(sid)
        if data.get("hinweis"):
            notes.append(str(data["hinweis"]).strip())
    if len(deletes) == len(segs) and len(segs) > 3:
        raise EditError("Die KI wollte das ganze Transkript löschen – das macht REKORD nicht. Anweisung genauer formulieren.")
    res = history.change(rid, f"KI: {instruction}"[:120], changes, sorted(deletes))
    note = " ".join(notes)[:400]
    log.info("transcript ai %s: %d changed, %d removed", rid, res["changed"], res["deleted"])
    return {**res, "note": note}
