"""Background worker: one processing job at a time (CPU bound), events fan out to websocket listeners.

The analysis itself runs in its own process (`rekord --process-job <id>`): with lower priority than every app you
use – the computer stays smooth while REKORD works – and its memory (~1 GB of speech models) is given back as soon
as it's done. Summaries talk to an AI over the network and stay in this process."""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
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
_child: subprocess.Popen | None = None


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
                if os.environ.get("REKORD_JOBS_INPROCESS") == "1":  # tests that patch the pipeline
                    pipeline.process(rid, on_event=emit)
                else:
                    _process_isolated(rid)
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


def _process_isolated(rid: str) -> None:
    """One recording in its own process. Progress comes through the database (the child writes it anyway)."""
    global _child
    from . import system
    s = config.load()
    gentle = s.get("gentle_processing", True) is not False
    threads = system.processing_threads(int(s.get("threads", 4)), gentle)
    env = system.child_env()
    env.update({k: str(threads) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")})
    env.update(REKORD_JOB_THREADS=str(threads), REKORD_JOB_PARENT=str(os.getpid()), REKORD_JOB_GENTLE="1" if gentle else "0")
    cmd = system.app_command() + ["--process-job", rid]
    if gentle:
        cmd = system.in_background(cmd)
    kw = {"creationflags": 0x08000000} if sys.platform == "win32" else {}  # no console window
    db.update_recording(rid, status="processing", stage="Startet", progress=0, error="")
    emit({"type": "progress", "id": rid, "stage": "Startet", "progress": 0.0})
    _child = proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, **kw)
    last = None
    code = None
    while code is None:
        try:
            code = proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass
        r = db.get_recording(rid) or {}
        now = (r.get("stage"), r.get("progress"))
        if r.get("status") == "processing" and now != last:
            last = now
            emit({"type": "progress", "id": rid, "stage": now[0], "progress": float(now[1] or 0)})
    _child = None
    r = db.get_recording(rid) or {}
    if r.get("status") == "done":
        emit({"type": "done", "id": rid})
        return
    raise RuntimeError(r.get("error") if r.get("status") == "error" and r.get("error")
                       else f"Die Auswertung wurde unterbrochen (Code {code}).")


def stop_child() -> None:
    """REKORD quits: the running analysis ends with it (the recording continues at the next start)."""
    p = _child
    if p is not None and p.poll() is None:
        try:
            p.kill()
        except OSError:
            pass


def child_main(rid: str) -> int:
    """`rekord --process-job <id>`: analyze one recording, then end (see _process_isolated)."""
    from . import system
    if os.environ.get("REKORD_JOB_GENTLE") == "1":
        system.lower_priority()  # before anything starts threads: they inherit it
    parent = int(os.environ.get("REKORD_JOB_PARENT") or 0)

    def watch() -> None:  # REKORD is gone (crash, force quit): don't keep working for nobody
        while system.pid_alive(parent):
            time.sleep(2)
        os._exit(3)
    if parent:
        threading.Thread(target=watch, daemon=True, name="watch-parent").start()
    try:
        from . import pipeline  # loads the speech engine: if that fails, the recording says so
        pipeline.process(rid)
        return 0
    except Exception as e:  # noqa: BLE001
        log.error("job %s failed: %s", rid, traceback.format_exc())
        db.update_recording(rid, status="error", stage="", error=str(e) or e.__class__.__name__)
        return 1


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
