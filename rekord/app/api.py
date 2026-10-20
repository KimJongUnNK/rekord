"""REKORD's window talks to the engine through the same local API the iPhone app uses – in this process, on this
computer only (127.0.0.1, nothing leaves it). One place for all logic: what the window does, the iPhone app does too.

QML calls `api.request(method, path, body)` / `api.stream(path, body)` and gets the answer as a signal (Main.qml
turns that into callbacks). Everything blocking runs on worker threads; the window never waits."""
from __future__ import annotations

import itertools
import json
import logging
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from PySide6.QtCore import Property, QObject, QTimer, QUrl, Qt, Signal, Slot

from .. import jobs

log = logging.getLogger("rekord.app")
ERR = "\u0000ERROR:"


def _detail(r: httpx.Response) -> str:
    try:
        d = r.json().get("detail")
        if isinstance(d, str):
            return d
        if d:
            return json.dumps(d, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        pass
    return f"{r.status_code} {r.reason_phrase}"


def plain(v):
    """QML values → plain JSON data. Older Qt (6.9, the Linux build) hands nested JS arrays and objects over as
    QJSValue – json can't write those. Must run on the window's thread, before work goes to a worker."""
    from PySide6.QtQml import QJSValue
    if isinstance(v, QJSValue):
        v = v.toVariant()
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v


class Api(QObject):
    reply = Signal(int, bool, int, "QVariant")  # id, ok, HTTP status, data (JSON) – or the error text
    chunk = Signal(int, str)                     # id, text so far (summaries, answers – while the AI writes)
    event = Signal("QVariantMap")                # processing events: progress, done, summary_done …

    def __init__(self, port: int, parent=None):
        super().__init__(parent)
        self.base = f"http://127.0.0.1:{port}"
        self._ids = itertools.count(1)
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="api")
        self._client = httpx.Client(base_url=self.base, timeout=httpx.Timeout(120, connect=5))
        self._stop: set[int] = set()
        self._pdf.connect(self._write_pdf, Qt.QueuedConnection)
        jobs.subscribe(self._on_job)

    def _on_job(self, ev: dict) -> None:
        self.event.emit(dict(ev))  # worker thread → QML (queued)

    @Property(str, constant=True)
    def baseUrl(self):  # noqa: N802 - QML API
        return self.base

    @Slot(str, str, "QVariant", result=int)
    def request(self, method: str, path: str, body=None) -> int:
        rid = next(self._ids)
        self._pool.submit(self._do, rid, method.upper(), path, plain(body))
        return rid

    def _do(self, rid: int, method: str, path: str, body) -> None:
        try:
            kw = {"json": body} if body is not None and method in ("POST", "PUT", "PATCH") else {}
            r = self._client.request(method, path, **kw)
            if r.status_code >= 400:
                self.reply.emit(rid, False, r.status_code, _detail(r))
                return
            ct = r.headers.get("content-type", "")
            self.reply.emit(rid, True, r.status_code, r.json() if "json" in ct else r.text)
        except httpx.HTTPError as e:
            self.reply.emit(rid, False, 0, f"REKORD antwortet nicht ({e.__class__.__name__}).")
        except Exception as e:  # noqa: BLE001
            log.exception("api %s %s", method, path)
            self.reply.emit(rid, False, 0, str(e))

    @Slot(str, "QVariant", result=int)
    def stream(self, path: str, body=None) -> int:
        """POST that answers with text as it's written (summaries, questions)."""
        rid = next(self._ids)
        self._pool.submit(self._do_stream, rid, path, plain(body))
        return rid

    @Slot(int)
    def cancel(self, rid: int) -> None:
        self._stop.add(rid)

    def _do_stream(self, rid: int, path: str, body) -> None:
        text, last = "", 0.0
        try:
            with self._client.stream("POST", path, json=body or {}, timeout=httpx.Timeout(None, connect=5)) as r:
                if r.status_code >= 400:
                    r.read()
                    self.reply.emit(rid, False, r.status_code, _detail(r))
                    return
                for part in r.iter_text():
                    if rid in self._stop:
                        break
                    text += part
                    at = text.find(ERR)
                    if at >= 0:
                        self.reply.emit(rid, False, 200, text[at + len(ERR):].strip() or "Fehler")
                        return
                    now = time.monotonic()
                    if now - last > 0.06:  # ~15 updates a second are smooth enough
                        last = now
                        self.chunk.emit(rid, text)
            self.chunk.emit(rid, text)
            self.reply.emit(rid, True, 200, text)
        except httpx.HTTPError as e:
            self.reply.emit(rid, False, 0, f"REKORD antwortet nicht ({e.__class__.__name__}).")
        finally:
            self._stop.discard(rid)

    @Slot(str, str, str, result=int)
    def upload(self, path: str, file_path: str, fields_json: str = "{}") -> int:
        """multipart POST with one file (e.g. a voice sample) – returns like request()."""
        rid = next(self._ids)

        def go():
            try:
                p = Path(QUrl(file_path).toLocalFile() if "://" in file_path else file_path)
                with open(p, "rb") as f:
                    r = self._client.post(path, data=json.loads(fields_json or "{}"),
                                          files={"file": (p.name, f, "application/octet-stream")},
                                          timeout=httpx.Timeout(600, connect=5))
                if r.status_code >= 400:
                    self.reply.emit(rid, False, r.status_code, _detail(r))
                else:
                    self.reply.emit(rid, True, r.status_code, r.json())
            except Exception as e:  # noqa: BLE001
                self.reply.emit(rid, False, 0, str(e))
        self._pool.submit(go)
        return rid

    # ---------------------------------------------------------------- files & clipboard (not part of the API)
    saved = Signal(bool, str)  # ok, message

    @Slot(str, str, str)
    def saveExport(self, rid: str, fmt: str, url: str) -> None:  # noqa: N802 - QML API
        """Export (md, docx, txt, srt, vtt, json, pdf, audio) into the file the user picked."""
        dest = Path(QUrl(url).toLocalFile() if "://" in url else url)

        def go():
            try:
                from .. import db, export
                if fmt == "audio":
                    rec = db.get_recording(rid) or {}
                    shutil.copyfile(rec["audio_path"], dest)
                elif fmt == "pdf":
                    self._pdf.emit(rid, str(dest))  # QTextDocument wants the UI thread
                    return
                else:
                    data = export.FORMATS[fmt][1](rid)
                    dest.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
                self.saved.emit(True, f"Gespeichert: {dest.name}")
            except ImportError:
                self.saved.emit(False, "Word-Export braucht python-docx.")
            except Exception as e:  # noqa: BLE001
                self.saved.emit(False, f"Speichern fehlgeschlagen: {e}")
        self._pool.submit(go)

    _pdf = Signal(str, str)

    @Slot(str, str)
    def _write_pdf(self, rid: str, dest: str) -> None:
        try:
            from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument

            from .. import db, export
            from . import md
            html = md.render(export.markdown(rid), links=False)
            title = (db.get_recording(rid) or {}).get("title", "REKORD")
            doc = QTextDocument()
            doc.setDefaultStyleSheet("body{font-family:sans-serif;font-size:10pt} h1{font-size:18pt} h2{font-size:14pt} "
                                     "h3{font-size:12pt} table{border-collapse:collapse} td,th{border:1px solid #999;padding:3px}")
            doc.setHtml(f"<h1>{md.esc(title)}</h1>{html}")
            w = QPdfWriter(dest)
            w.setPageSize(QPageSize(QPageSize.A4))
            w.setTitle(title)
            doc.print_(w)
            self.saved.emit(True, f"Gespeichert: {Path(dest).name}")
        except Exception as e:  # noqa: BLE001
            self.saved.emit(False, f"PDF fehlgeschlagen: {e}")

    @Slot(str)
    def copyText(self, text: str) -> None:  # noqa: N802 - QML API
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(text)

    @Slot(str, result=str)
    def exportText(self, rid: str) -> str:  # noqa: N802 - QML API
        from .. import export
        return export.markdown(rid)

    @Slot(str)
    def openUrl(self, url: str) -> None:  # noqa: N802 - QML API
        """Links to websites (Key erstellen, Anleitung …) in the normal browser."""
        from .. import desktop
        threading.Thread(target=desktop.open_url, args=(url,), daemon=True).start()

    @Slot(str)
    def reveal(self, path: str) -> None:
        """Show a folder in Finder/Explorer/Files."""
        import subprocess
        import sys

        from .. import system
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", path])
            else:
                subprocess.Popen(["xdg-open", path], env=system.child_env())
        except OSError as e:
            self.saved.emit(False, str(e))


class Player(QObject):
    """Plays a recording (Qt Multimedia). Without it (rare Linux setups) the rest of the window still works."""
    changed = Signal()
    tick = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._p = self._out = None
        self._until = None
        self._rate = 1.0
        self._error = ""
        self._timer = QTimer(self, interval=60)
        self._timer.timeout.connect(self._poll)
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._p = QMediaPlayer(self)
            self._out = QAudioOutput(self)
            self._p.setAudioOutput(self._out)
            self._p.playbackStateChanged.connect(self._state)
            self._p.durationChanged.connect(lambda *_: self.changed.emit())
            self._p.errorOccurred.connect(lambda *_: self._fail(self._p.errorString()))
        except Exception as e:  # noqa: BLE001
            self._error = f"Wiedergabe nicht verfügbar: {e}"

    def _fail(self, msg: str) -> None:
        self._error = msg
        self.changed.emit()

    @Property(bool, notify=changed)
    def available(self):
        return self._p is not None

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(bool, notify=changed)
    def playing(self):
        if self._p is None:
            return False
        from PySide6.QtMultimedia import QMediaPlayer
        return self._p.playbackState() == QMediaPlayer.PlayingState

    @Property(float, notify=tick)
    def position(self):
        return (self._p.position() / 1000.0) if self._p is not None else 0.0

    @Property(float, notify=changed)
    def duration(self):
        return (self._p.duration() / 1000.0) if self._p is not None else 0.0

    @Property(float, notify=changed)
    def rate(self):
        return self._rate

    @Slot(str)
    def load(self, path: str) -> None:
        self._until = None
        self._error = ""
        if self._p is None:
            self.changed.emit()
            return
        self._p.stop()
        self._p.setSource(QUrl.fromLocalFile(path) if path else QUrl())
        self._p.setPlaybackRate(self._rate)
        self.changed.emit()
        self.tick.emit()

    @Slot()
    def toggle(self) -> None:
        if self._p is None:
            return
        if self.playing:
            self._p.pause()
        else:
            self._until = None
            self._p.play()

    @Slot()
    def pause(self) -> None:
        if self._p is not None:
            self._p.pause()

    @Slot(float)
    def seek(self, sec: float) -> None:
        if self._p is None:
            return
        self._p.setPosition(int(max(0.0, sec) * 1000))
        self.tick.emit()

    @Slot(float)
    def seekPlay(self, sec: float) -> None:  # noqa: N802 - QML API
        self._until = None
        self.seek(sec)
        if self._p is not None and not self.playing:
            self._p.play()

    @Slot(float, float)
    def playRange(self, start: float, end: float) -> None:  # noqa: N802 - QML API
        """Listen to one voice: from start, stop at end (at most 8 s)."""
        if self._p is None:
            return
        self.seek(start)
        self._until = min(end, start + 8)
        self._p.play()

    @Slot(float)
    def skip(self, delta: float) -> None:
        self.seek(self.position + delta)

    @Slot()
    def nextRate(self) -> None:  # noqa: N802 - QML API
        rates = [1.0, 1.25, 1.5, 1.75, 2.0]
        self._rate = rates[(rates.index(self._rate) + 1) % len(rates)] if self._rate in rates else 1.0
        if self._p is not None:
            self._p.setPlaybackRate(self._rate)
        self.changed.emit()

    @Slot()
    def stop(self) -> None:
        if self._p is not None:
            self._p.stop()

    def _state(self, *_):
        if self.playing:
            self._timer.start()
        else:
            self._timer.stop()
        self.changed.emit()
        self.tick.emit()

    def _poll(self) -> None:
        if self._until is not None and self.position >= self._until:
            self._until = None
            self._p.pause()
        self.tick.emit()
