"""Background worker: one processing job at a time (CPU bound), events fan out to websocket listeners."""
from __future__ import annotations

import logging
import queue
import threading
import time
import traceback

from . import config, db
from .llm import providers

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


def wants_auto_summary(settings: dict) -> bool:
    """Only queue a summary when an AI is actually set up - no key yet means no failing jobs."""
    return bool(settings.get("auto_summary")) and providers.configured(settings)[0]


def pending() -> int:
    return _q.qsize()


def _run() -> None:
    from . import pipeline, summarize
    while True:
        kind, rid = _q.get()
        try:
            if kind == "process":
                pipeline.process(rid, on_event=emit)
                if wants_auto_summary(config.load()):
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


def wait_idle(timeout: float | None = None) -> bool:
    """Until every queued job is done (False if the timeout ran out first)."""
    end = None if timeout is None else time.monotonic() + timeout
    with _q.all_tasks_done:
        while _q.unfinished_tasks:
            left = None if end is None else end - time.monotonic()
            if left is not None and left <= 0:
                return False
            _q.all_tasks_done.wait(left)
    return True
