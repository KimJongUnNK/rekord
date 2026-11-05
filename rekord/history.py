"""Undo and redo for the transcript, like in Word: every change – typed by hand, Suchen & Ersetzen, the AI – is one
step back (Rückgängig) and forward again (Wiederholen). A new change after undoing drops what could be redone.
Kept with the recording (up to 50 steps), so it survives a restart."""
from __future__ import annotations

from . import db

LIMIT = 50


def _load(rid: str) -> dict:
    h = (db.get_recording(rid) or {}).get("transcript_undo") or {}
    if "undo" not in h:  # nothing yet (or an older single step)
        h = {"undo": [], "redo": []}
    return h


def _save(rid: str, h: dict) -> None:
    h["undo"] = h["undo"][-LIMIT:]
    h["redo"] = h["redo"][-LIMIT:]
    db.update_recording(rid, transcript_undo=h)


def record(rid: str, label: str, texts: dict[int, tuple[str, str]] | None = None, deleted: list[dict] | None = None) -> None:
    """One step: texts {id: (before, after)}, deleted = the removed lines as they were."""
    texts = {sid: ba for sid, ba in (texts or {}).items() if ba[0] != ba[1]}
    if not texts and not deleted:
        return
    h = _load(rid)
    h["undo"].append({"label": label, "texts": [[sid, b, a] for sid, (b, a) in texts.items()], "deleted": deleted or []})
    h["redo"] = []
    _save(rid, h)


def change(rid: str, label: str, new_texts: dict[int, str], delete_ids: list[int] | None = None) -> dict:
    """Apply a change and remember it. Returns {"changed": n, "deleted": n}."""
    segs = {s["id"]: s for s in db.list_segments(rid)}
    texts = {sid: (segs[sid]["text"], t) for sid, t in new_texts.items() if sid in segs and segs[sid]["text"] != t}
    deleted = [segs[sid] for sid in (delete_ids or []) if sid in segs]
    for s in deleted:
        texts.pop(s["id"], None)
    if texts:
        db.set_texts(rid, {sid: a for sid, (_b, a) in texts.items()})
    if deleted:
        db.delete_segments(rid, [s["id"] for s in deleted])
    record(rid, label, texts, deleted)
    return {"changed": len(texts), "deleted": len(deleted)}


def undo(rid: str) -> dict:
    h = _load(rid)
    if not h["undo"]:
        return {"done": False, "label": ""}
    step = h["undo"].pop()
    db.restore_segments(rid, step["deleted"])
    db.set_texts(rid, {sid: before for sid, before, _after in step["texts"]})
    h["redo"].append(step)
    _save(rid, h)
    return {"done": True, "label": step["label"]}


def redo(rid: str) -> dict:
    h = _load(rid)
    if not h["redo"]:
        return {"done": False, "label": ""}
    step = h["redo"].pop()
    db.set_texts(rid, {sid: after for sid, _before, after in step["texts"]})
    db.delete_segments(rid, [s["id"] for s in step["deleted"]])
    h["undo"].append(step)
    _save(rid, h)
    return {"done": True, "label": step["label"]}


def state(rid: str) -> dict:
    h = _load(rid)
    return {"undo": h["undo"][-1]["label"] if h["undo"] else "", "redo": h["redo"][-1]["label"] if h["redo"] else "",
            "undo_count": len(h["undo"]), "redo_count": len(h["redo"])}
