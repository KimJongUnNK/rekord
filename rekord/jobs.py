"""Background worker: one processing job at a time (CPU bound), events fan out to websocket listeners."""
from __future__ import annotations

import logging
import queue
import threading
import traceback

from . import config, db

log = logging.getLogger("rekord.jobs")

_q: "queue.Queue[tuple[str, str]]" = queue.Queue()
_listeners: list = []
_llock = threading.Lock()
_started = False


def subscribe(fn) -> None:
    with _llock:
        _listeners.append(fn)


def unsubscribe(fn) -> None:
    with _llock:
        if fn in _listeners:
            _listeners.remove(fn)


def emit(ev: dict) -> None:
    with _llock:
        ls = list(_listeners)
    for fn in ls:
        try:
            fn(ev)
        except Exception:  # noqa: BLE001
            pass


def enqueue(rid: str, kind: str = "process") -> None:
    if kind == "process":
        db.update_recording(rid, status="queued", stage="Warteschlange", progress=0, error="")
    _q.put((kind, rid))
    emit({"type": "queued", "id": rid})


def pending() -> int:
    return _q.qsize()


def _run() -> None:
    from . import pipeline, summarize
    while True:
        kind, rid = _q.get()
        try:
            if kind == "process":
                pipeline.process(rid, on_event=emit)
                s = config.load()
                if s.get("auto_summary") and s["llm"]["provider"] != "none":
                    _q.put(("summary", rid))
            elif kind == "summary":
                emit({"type": "summary_started", "id": rid})
                summarize.auto_summary(rid)
                emit({"type": "summary_done", "id": rid})
        except Exception as e:  # noqa: BLE001
            log.error("job %s %s failed: %s", kind, rid, traceback.format_exc())
            if kind == "process":
                db.update_recording(rid, status="error", stage="", error=str(e))
            emit({"type": "error", "id": rid, "kind": kind, "error": str(e)})
        finally:
            db.close()  # thread-local connection hygiene
            _q.task_done()


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_run, daemon=True, name="rekord-worker").start()
    # recover unfinished work after a restart
    for r in db.list_recordings():
        if r["status"] in ("queued", "processing"):
            enqueue(r["id"])


def wait_idle() -> None:
    _q.join()
