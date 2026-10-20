"""The bridge between REKORD's engine and the Qt Quick interface – in the same process, no web server, no browser.

QML sees: `rekord` (app state), `library` (recordings), `detail` (one recording), `people`, `live`. Engine events
arrive on worker threads and are handed to the UI thread through queued Qt signals."""
from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import (Property, QAbstractListModel, QByteArray, QModelIndex, QObject, Qt, QTimer, QUrl, Signal,
                            Slot)

from .. import __version__, config, db, jobs, live

log = logging.getLogger("rekord.app")
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".webm", ".ogg", ".opus", ".flac", ".aac", ".mp4", ".mov", ".mkv", ".caf", ".amr", ".3gp"}
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def fmt_dur(sec: float | None) -> str:
    s = int(sec or 0)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def fmt_date(ts: float | None) -> str:
    if not ts:
        return ""
    d = datetime.fromtimestamp(ts)
    today = datetime.now().date()
    day = "Heute" if d.date() == today else "Gestern" if (today - d.date()).days == 1 else f"{WEEKDAYS[d.weekday()]} {d:%d.%m.}"
    return f"{day} · {d:%H:%M}"


class ListModel(QAbstractListModel):
    """A list of dicts for QML ListView: every key named in `roles` is a role."""

    def __init__(self, roles: list[str], parent=None):
        super().__init__(parent)
        self._roles = {Qt.UserRole + i: r.encode() for i, r in enumerate(roles)}
        self._by_name = {r: Qt.UserRole + i for i, r in enumerate(roles)}
        self._items: list[dict] = []

    countChanged = Signal()

    def roleNames(self):  # noqa: N802 - Qt API
        return {k: QByteArray(v) for k, v in self._roles.items()}

    def rowCount(self, parent=QModelIndex()):  # noqa: N802, B008 - Qt API
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        name = self._roles.get(role)
        return self._items[index.row()].get(name.decode()) if name else None

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()
        self.countChanged.emit()

    def append(self, item: dict) -> None:
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append(item)
        self.endInsertRows()
        self.countChanged.emit()

    def update_where(self, key: str, value, changes: dict) -> bool:
        for i, it in enumerate(self._items):
            if it.get(key) == value:
                it.update(changes)
                idx = self.index(i)
                self.dataChanged.emit(idx, idx, [self._by_name[k] for k in changes if k in self._by_name])
                return True
        return False

    def items(self) -> list[dict]:
        return list(self._items)

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._items)

    @Slot(int, result="QVariantMap")
    def get(self, row: int) -> dict:
        return dict(self._items[row]) if 0 <= row < len(self._items) else {}


# ------------------------------------------------------------------ recordings

REC_ROLES = ["rid", "title", "dateText", "durationText", "status", "statusText", "progress", "folder", "speakers", "source"]


def _rec_row(r: dict) -> dict:
    st = r.get("status") or ""
    pr = float(r.get("progress") or 0)
    text = {"queued": "Wartet …", "recording": "● Nimmt auf", "error": "Fehler"}.get(st, "")
    if st == "processing":
        text = f"{r.get('stage') or 'Verarbeitet'} · {round(pr * 100)} %"
    return {"rid": r["id"], "title": r.get("title") or "Ohne Titel", "dateText": fmt_date(r.get("created_at")),
            "durationText": fmt_dur(r.get("duration")), "status": st, "statusText": text, "progress": pr,
            "folder": r.get("folder") or "", "source": r.get("source") or "",
            "speakers": [{"name": s["name"], "color": s["color"]} for s in (r.get("speakers") or [])][:6]}


class Library(QObject):
    """Aufnahmen: list, search, folders, import – kept current by the processing events."""
    changed = Signal()
    toast = Signal(str)
    _job = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = ListModel(REC_ROLES, self)
        self._query, self._folder, self._folders = "", "", []
        self._job.connect(self._apply_job, Qt.QueuedConnection)
        jobs.subscribe(self._job.emit)  # worker thread → UI thread
        self._debounce = QTimer(self, singleShot=True, interval=250)
        self._debounce.timeout.connect(self.refresh)

    @Property(QObject, constant=True)
    def model(self):
        return self._model

    @Property("QStringList", notify=changed)
    def folders(self):
        return self._folders

    @Property(str, notify=changed)
    def folder(self):
        return self._folder

    @Property(str, notify=changed)
    def query(self):
        return self._query

    @Slot()
    def refresh(self) -> None:
        try:
            items = db.list_recordings(q=self._query, folder=self._folder or None)
            self._folders = db.folders()
        except Exception as e:  # noqa: BLE001 - e.g. data drive missing
            log.warning("library: %s", e)
            items = []
        self._model.set_items([_rec_row(r) for r in items])
        self.changed.emit()

    @Slot(str)
    def search(self, q: str) -> None:
        self._query = q.strip()
        self._debounce.start()

    @Slot(str)
    def setFolder(self, folder: str) -> None:  # noqa: N802 - QML API
        self._folder = folder
        self.refresh()

    @Slot("QVariantList", result=int)
    def importFiles(self, urls) -> int:  # noqa: N802 - QML API
        """Audio/video files (from the file dialog or dropped on the window) → recordings, processed in the background."""
        n, skipped = 0, []
        for u in urls:
            p = Path(QUrl(u).toLocalFile() if not isinstance(u, QUrl) else u.toLocalFile()) if "://" in str(u) or isinstance(u, QUrl) else Path(str(u))
            ext = p.suffix.lower()
            if not p.is_file() or ext not in AUDIO_EXT:
                skipped.append(p.name)
                continue
            rid = uuid.uuid4().hex[:12]
            dest = config.AUDIO_DIR / f"{rid}{ext}"
            shutil.copyfile(p, dest)
            db.create_recording(p.stem, str(dest), source="import", rec_id=rid)
            jobs.enqueue(rid)
            n += 1
        if n:
            self.toast.emit(f"{n} {'Datei wird' if n == 1 else 'Dateien werden'} verarbeitet")
        if skipped:
            self.toast.emit("Nicht unterstützt: " + ", ".join(skipped[:3]))
        self.refresh()
        return n

    @Slot(object)
    def _apply_job(self, ev: dict) -> None:
        if ev.get("type") == "progress" and ev.get("id"):
            st = f"{ev.get('stage') or 'Verarbeitet'} · {round(float(ev.get('progress') or 0) * 100)} %"
            if self._model.update_where("rid", ev["id"], {"status": "processing", "statusText": st,
                                                          "progress": float(ev.get("progress") or 0)}):
                return
        self.refresh()


# ------------------------------------------------------------------ one recording (read-only in Etappe 1)

class Detail(QObject):
    changed = Signal()
    _job = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._job.connect(self._apply_job, Qt.QueuedConnection)
        jobs.subscribe(self._job.emit)
        self._reload = QTimer(self, singleShot=True, interval=400)
        self._reload.timeout.connect(lambda: self.load(self.rid) if self.rid else None)
        self._rec: dict = {}
        self._lines = ListModel(["time", "name", "color", "text"], self)
        self._speakers: list[dict] = []
        self._summaries: list[dict] = []

    @Slot(str)
    def load(self, rid: str) -> None:
        rec = db.get_recording(rid) or {}
        self._rec = rec
        speakers = {s["id"]: s for s in db.list_speakers(rid)} if rec else {}
        segs = db.list_segments(rid) if rec else []
        talk: dict = {}
        for s in segs:
            talk[s["speaker_id"]] = talk.get(s["speaker_id"], 0) + (s["end"] - s["start"])
        total = sum(talk.values()) or 1
        self._speakers = [{"name": sp["name"], "color": sp["color"], "share": round(talk.get(sid, 0) / total, 3)}
                          for sid, sp in speakers.items()]
        self._speakers.sort(key=lambda x: -x["share"])
        self._lines.set_items([{"time": fmt_dur(s["start"]), "name": speakers.get(s["speaker_id"], {}).get("name", ""),
                                "color": speakers.get(s["speaker_id"], {}).get("color", "#8A877F"), "text": s["text"]}
                               for s in segs])
        self._summaries = [{"title": x["title"], "content": x["content"]} for x in (db.list_summaries(rid) if rec else [])
                           if x.get("template_id") != "mindmap"]
        self.changed.emit()

    @Slot(object)
    def _apply_job(self, ev: dict) -> None:
        """The open recording is being processed or summarized: show the new state (at most every 0.4 s)."""
        if ev.get("id") and ev.get("id") == self.rid and not self._reload.isActive():
            self._reload.start()

    @Property(str, notify=changed)
    def rid(self):
        return self._rec.get("id", "")

    @Property(str, notify=changed)
    def title(self):
        return self._rec.get("title", "")

    @Property(str, notify=changed)
    def meta(self):
        r = self._rec
        if not r:
            return ""
        bits = [fmt_date(r.get("created_at")), fmt_dur(r.get("duration"))]
        if r.get("status") in ("queued", "processing"):
            bits.append(f"{r.get('stage') or 'wird verarbeitet'} {round(float(r.get('progress') or 0) * 100)} %")
        return " · ".join(b for b in bits if b)

    @Property(str, notify=changed)
    def status(self):
        return self._rec.get("status", "")

    @Property("QVariantList", notify=changed)
    def speakers(self):
        return self._speakers

    @Property("QVariantList", notify=changed)
    def summaries(self):
        return self._summaries

    @Property(QObject, constant=True)
    def lines(self):
        return self._lines


# ------------------------------------------------------------------ people (for "Wer ist dabei?")

class People(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []

    @Slot()
    def refresh(self) -> None:
        try:
            self._items = [{"id": p["id"], "name": p["name"], "color": p["color"]} for p in db.list_profiles()]
        except Exception:  # noqa: BLE001
            self._items = []
        self.changed.emit()

    @Property("QVariantList", notify=changed)
    def items(self):
        return self._items


# ------------------------------------------------------------------ microphone (native, Qt Multimedia)

class Mic(QObject):
    """The microphone through Qt Multimedia: 16-bit PCM chunks + a level for the meter."""
    chunk = Signal(bytes, int)  # pcm16 mono, sample rate
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._src = None
        self._io = None
        self._fmt = None

    @staticmethod
    def devices() -> list[dict]:
        from PySide6.QtMultimedia import QMediaDevices
        default = QMediaDevices.defaultAudioInput()
        return [{"id": bytes(d.id()).decode(errors="replace"), "name": d.description(), "default": d == default}
                for d in QMediaDevices.audioInputs()]

    def start(self, device_id: str = "") -> bool:
        from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
        devs = QMediaDevices.audioInputs()
        dev = next((d for d in devs if bytes(d.id()).decode(errors="replace") == device_id), None) or QMediaDevices.defaultAudioInput()
        if dev.isNull():
            self.failed.emit("Kein Mikrofon gefunden.")
            return False
        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)
        if not dev.isFormatSupported(fmt):
            fmt = dev.preferredFormat()
        self._fmt = fmt
        self._src = QAudioSource(dev, fmt, self)
        self._src.setBufferSize(fmt.bytesForDuration(200_000))
        self._io = self._src.start()
        if self._io is None:
            self.failed.emit("Mikrofon lässt sich nicht öffnen.")
            return False
        self._io.readyRead.connect(self._read)
        return True

    def _read(self) -> None:
        from PySide6.QtMultimedia import QAudioFormat
        data = bytes(self._io.readAll().data())
        if not data:
            return
        f = self._fmt
        ch = max(1, f.channelCount())
        kind = f.sampleFormat()
        if kind == QAudioFormat.Int16:
            x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
        elif kind == QAudioFormat.Int32:
            x = np.frombuffer(data, dtype="<i4").astype(np.float32) / 2**31
        elif kind == QAudioFormat.Float:
            x = np.frombuffer(data, dtype="<f4")
        else:  # UInt8
            x = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128) / 128.0
        if ch > 1:
            x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
        self.chunk.emit((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes(), f.sampleRate())

    def stop(self) -> None:
        if self._src is not None:
            self._src.stop()
            self._src.deleteLater()
        self._src = self._io = None


# ------------------------------------------------------------------ live recording

MEETINGS = {"person": "person", "online": "online", "lecture": "lecture"}


class Live(QObject):
    """A live recording: native microphone → LiveSession (speaker recognition, transcript) → this page."""
    changed = Signal()
    levelChanged = Signal()
    micsChanged = Signal()
    finished = Signal(str)   # recording id once stopped (processing continues in the background)
    toast = Signal(str)
    _event = Signal(object)  # from the engine's threads
    _ready = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "idle"
        self._sess = None
        self._mic = Mic(self)
        self._mic.chunk.connect(self._on_chunk)
        self._mic.failed.connect(self._mic_failed)
        self._lines = ListModel(["time", "name", "color", "text", "known"], self)
        self._roster: list[dict] = []
        self._speaking: dict = {}
        self._level = 0.0
        self._t0 = 0.0
        self._paused_at = 0.0
        self._paused_total = 0.0
        self._title = ""
        self._meeting = "person"
        self._notes = ""
        self._error = ""
        self._call = False
        self._highlights = 0
        self._q: "queue.Queue" = queue.Queue()
        self._pending: list[tuple[bytes, int]] = []  # audio before the engine is ready (first start loads models)
        self._level_at = 0.0
        self._mics: list[dict] = []
        self._event.connect(self._on_event, Qt.QueuedConnection)
        self._ready.connect(self._on_ready, Qt.QueuedConnection)
        self._tick = QTimer(self, interval=250)
        self._tick.timeout.connect(self.changed.emit)
        self._feeder = threading.Thread(target=self._feed_loop, daemon=True, name="live-feed")
        self._feeder.start()

    # ---------- properties for the page
    @Property(str, notify=changed)
    def state(self):
        return self._state

    @Property(float, notify=changed)
    def elapsed(self):
        if self._state in ("idle", "starting"):
            return 0.0
        end = self._paused_at or time.time()
        return max(0.0, end - self._t0 - self._paused_total)

    @Property(str, notify=changed)
    def elapsedText(self):  # noqa: N802 - QML API
        return fmt_dur(self.elapsed)

    @Property(float, notify=levelChanged)
    def level(self):
        return self._level

    @Property("QVariantMap", notify=changed)
    def speaking(self):
        return self._speaking

    @Property("QVariantList", notify=changed)
    def roster(self):
        return self._roster

    @Property(QObject, constant=True)
    def lines(self):
        return self._lines

    @Property(str, notify=changed)
    def title(self):
        return self._title

    @Property(str, notify=changed)
    def meeting(self):
        return self._meeting

    @Property(str, notify=changed)
    def notes(self):
        return self._notes

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(bool, notify=changed)
    def callAudio(self):  # noqa: N802 - QML API
        return self._call

    @Property(int, notify=changed)
    def highlights(self):
        return self._highlights

    @Property("QVariantList", notify=micsChanged)
    def mics(self):
        return self._mics

    @Property(str, notify=micsChanged)
    def mic(self):
        return config.load()["desktop"]["mic"]

    @Slot()
    def refreshMics(self) -> None:  # noqa: N802 - QML API
        try:
            self._mics = Mic.devices()
        except Exception as e:  # noqa: BLE001
            log.warning("mics: %s", e)
            self._mics = []
        self.micsChanged.emit()

    @Slot(str)
    def setMic(self, device_id: str) -> None:  # noqa: N802 - QML API
        config.save({"desktop": {"mic": device_id}})
        self.micsChanged.emit()

    @Property("QVariantMap", notify=changed)
    def lastWho(self):  # noqa: N802 - QML API
        return dict(config.load()["desktop"]["who"])

    @Property(bool, constant=True)
    def callAvailable(self):  # noqa: N802 - QML API
        from .. import capture
        try:
            return bool(capture.available()["system_audio"])
        except Exception:  # noqa: BLE001
            return False

    # ---------- control
    @Slot(str, str, "QVariantList", int)
    def start(self, title: str, meeting: str, participants, total: int) -> None:
        """total: how many people are there (known ones included) – the rest are new voices. Not asked in a lecture."""
        if self._state != "idle":
            return
        self._title = title.strip() or time.strftime("Meeting %d.%m.%Y %H:%M")
        self._meeting = MEETINGS.get(meeting, "person")
        ids = [int(x) for x in (participants or [])]
        total = max(int(total or 0), len(ids))
        guests = 0 if self._meeting == "lecture" else max(0, total - len(ids))
        try:  # the next "Wer ist dabei?" starts from this
            config.save({"desktop": {"who": {"meeting": self._meeting, "ids": ids, "total": total}}})
        except Exception:  # noqa: BLE001 - e.g. data drive missing
            pass
        self._lines.set_items([])
        self._roster, self._speaking, self._notes, self._error, self._highlights = [], {}, "", "", 0
        self._pending, self._level = [], 0.0
        self._state = "starting"
        self.changed.emit()
        self._with_mic_permission(lambda: self._begin(ids, guests))

    def _with_mic_permission(self, then) -> None:
        """macOS asks once whether REKORD may use the microphone (Windows/Linux: always allowed here)."""
        try:
            from PySide6.QtCore import QCoreApplication, QMicrophonePermission
            app, perm = QCoreApplication.instance(), QMicrophonePermission()
            st = app.checkPermission(perm)
        except Exception:  # noqa: BLE001 - Qt without the permission API
            then()
            return
        if st == Qt.PermissionStatus.Granted:
            then()
        elif st == Qt.PermissionStatus.Denied:
            self._fail("Mikrofon ist gesperrt – Systemeinstellungen → Datenschutz & Sicherheit → Mikrofon → REKORD erlauben.")
        else:
            app.requestPermission(perm, self, lambda *_: then() if app.checkPermission(perm) == Qt.PermissionStatus.Granted
                                  else self._fail("Ohne Mikrofon kann REKORD nicht aufnehmen."))

    def _fail(self, msg: str) -> None:
        self._mic.stop()
        self._state, self._error = "idle", msg
        self.toast.emit(msg)
        self.changed.emit()

    def _begin(self, ids: list[int], guests: int) -> None:
        call = self._meeting == "online" and self.callAvailable
        if not self._mic.start(config.load()["desktop"]["mic"]):
            self._state = "idle"
            self.changed.emit()
            return

        def make():
            try:
                # always 16 kHz: the feeder converts whatever rate the microphone delivers (often 44.1/48 kHz)
                sess = live.LiveSession(self._event.emit, self._title, "live", live.SR, ids, guests, self._meeting, call)
                live.register(sess)
                self._ready.emit(sess, "")
            except Exception as e:  # noqa: BLE001
                log.exception("live start")
                self._ready.emit(None, str(e))
        threading.Thread(target=make, daemon=True, name="live-start").start()

    @Slot(object, str)
    def _on_ready(self, sess, err: str) -> None:
        if sess is None:
            self._fail(f"Live-Start fehlgeschlagen: {err}")
            return
        self._sess = sess
        self._call = sess.call is not None
        self._notes = " ".join(n for n in sess.notes if n)
        for item in self._pending:  # what was said while the models loaded
            self._q.put(item)
        self._pending = []
        self._t0, self._paused_at, self._paused_total = time.time(), 0.0, 0.0
        self._state = "recording"
        self._tick.start()
        self.changed.emit()

    @Slot()
    def pause(self) -> None:
        if self._state == "recording" and self._sess:
            self._sess.paused = True
            self._paused_at = time.time()
            self._state = "paused"
            self.changed.emit()

    @Slot()
    def resume(self) -> None:
        if self._state == "paused" and self._sess:
            self._sess.paused = False
            self._paused_total += time.time() - self._paused_at
            self._paused_at = 0.0
            self._state = "recording"
            self.changed.emit()

    @Slot()
    def highlight(self) -> None:
        if self._sess and self._state == "recording":
            self._sess.highlight()

    @Slot(int, str)
    def nameSpeaker(self, key: int, name: str) -> None:  # noqa: N802 - QML API
        if self._sess and name.strip():
            threading.Thread(target=self._sess.name_speaker, args=(key, name.strip()), daemon=True).start()
            self.toast.emit(f"{name.strip()}: Stimme gemerkt ✓")

    @Slot()
    def stop(self) -> None:
        if self._state not in ("recording", "paused") or self._sess is None:
            return
        self._mic.stop()
        self._tick.stop()
        self._state = "stopping"
        self.changed.emit()
        sess, done = self._sess, threading.Event()
        self._q.put(("__flush__", done))

        def finish():
            done.wait(10)
            try:
                rid = sess.stop()
            finally:
                live.unregister(sess.rid)
            self._event.emit({"type": "__finished__", "id": rid})
        threading.Thread(target=finish, daemon=True, name="live-stop").start()

    # ---------- audio path
    @Slot(bytes, int)
    def _on_chunk(self, data: bytes, rate: int) -> None:
        if self._state == "starting":
            self._pending.append((data, rate))
        elif self._state == "recording":
            self._q.put((data, rate))
        x = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
        if len(x):
            self._level = 0.6 * self._level + 0.4 * min(1.0, float(np.sqrt(np.mean(x ** 2))) * 6)
            now = time.monotonic()
            if now - self._level_at >= 0.033:  # ~30 updates a second are plenty for the animation
                self._level_at = now
                self.levelChanged.emit()

    def _feed_loop(self) -> None:
        while True:
            item = self._q.get()
            if item[0] == "__flush__":
                item[1].set()
                continue
            sess = self._sess
            if sess is not None and not sess._closed:
                try:
                    data, rate = item
                    if rate != live.SR:
                        x = live.resample(np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0, rate, live.SR)
                        data = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
                    sess.feed_pcm16(data)
                except Exception as e:  # noqa: BLE001
                    log.warning("live feed: %s", e)

    @Slot(str)
    def _mic_failed(self, msg: str) -> None:
        self._error = msg
        self.toast.emit(msg)
        self.changed.emit()

    @Slot(result=bool)
    def stopForQuit(self) -> bool:  # noqa: N802 - QML API
        """Closing the window while recording: save the recording first (True = wait for `finished`)."""
        if self._state in ("recording", "paused"):
            self.stop()
            return True
        return self._state == "stopping"

    # ---------- engine events
    @Slot(object)
    def _on_event(self, ev: dict) -> None:
        kind = ev.get("type")
        if kind == "segment" and ev.get("text"):
            self._lines.append({"time": fmt_dur(ev.get("start")), "name": ev.get("name", ""), "color": ev.get("color", "#8A877F"),
                                "text": ev["text"], "known": bool(ev.get("known"))})
        elif kind == "speaking":
            self._speaking = {"name": ev.get("name", ""), "color": ev.get("color", "#8A877F"), "known": bool(ev.get("known")),
                              "key": ev.get("key") if ev.get("key") is not None else -1}
        elif kind == "silence":
            self._speaking = {}
        elif kind == "speakers":
            total = sum(float(i.get("talk") or 0) for i in ev.get("items", [])) or 1
            self._roster = [{"name": i.get("name", ""), "color": i.get("color", "#8A877F"), "known": bool(i.get("known")),
                             "key": i.get("key") if i.get("key") is not None else -1, "share": float(i.get("talk") or 0) / total,
                             "waiting": bool(i.get("waiting")), "voices": int(i.get("voices") or 0)} for i in ev.get("items", [])]
        elif kind == "highlight":
            self._highlights += 1
            self.toast.emit("★ Moment markiert")
        elif kind == "__finished__":
            self._sess = None
            self._state = "idle"
            self._speaking, self._level = {}, 0.0
            self.levelChanged.emit()
            self.finished.emit(ev["id"])
        self.changed.emit()


# ------------------------------------------------------------------ the app itself

class AppState(QObject):
    """Version, readiness, AI, updates, the window itself, and where pages that aren't native yet are opened."""
    changed = Signal()
    focusRequested = Signal()
    toast = Signal(str)

    def __init__(self, port: int, keep_running: bool = False, parent=None):
        super().__init__(parent)
        self._port = port
        self._keep = keep_running
        self._status: dict = {}
        self._win = None
        self.focusRequested.connect(self._raise, Qt.QueuedConnection)  # asked from the hub's thread
        self._timer = QTimer(self, interval=4000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def attach(self, win) -> None:
        self._win = win

    @Slot()
    def _raise(self) -> None:
        w = self._win
        if w is None:
            return
        from PySide6.QtGui import QWindow
        if w.visibility() == QWindow.Minimized:
            w.showNormal()
        w.show()
        w.raise_()
        w.requestActivate()

    @Property(str, constant=True)
    def version(self):
        return __version__

    @Property(int, constant=True)
    def port(self):
        return self._port

    @Property(bool, constant=True)
    def keepRunning(self):  # noqa: N802 - QML API
        return self._keep

    themeChanged = Signal()

    @Property(str, notify=themeChanged)
    def theme(self):
        return config.load()["desktop"].get("theme", "system")

    @Slot(str)
    def setTheme(self, mode: str) -> None:  # noqa: N802 - QML API
        config.save({"desktop": {"theme": mode if mode in ("system", "light", "dark") else "system"}})
        self.themeChanged.emit()

    @Property("QVariantMap", notify=changed)
    def status(self):
        return self._status

    @Slot()
    def refresh(self) -> None:
        from .. import models, updater
        from ..llm import providers
        try:
            s = config.load()
            ready = all(models.installed(m) for m in models.ESSENTIAL) and (
                s["asr_engine"] == "faster-whisper" or models.installed(s["asr_model"]))
            dl = next((m for m in models.status() if (m.get("progress") or {}).get("state") == "downloading"), None)
            ok, problem = providers.configured(s)
            up = updater.info()
            self._status = {
                "ready": ready,
                "downloading": f"{dl['name']} {round(dl['progress']['done'] / max(1, dl['progress']['total']) * 100)} %" if dl else "",
                "ai": f"{providers.PROVIDERS.get(s['llm']['provider'], '')}" + (f" · {providers.model_name(s)}" if providers.model_name(s) else "") if ok else "",
                "aiProblem": "" if ok else problem, "live": bool(live.active()), "pending": jobs.pending(),
                "storageMissing": config.home_missing(), "welcomeDone": bool(s.get("welcome_done")),
                "update": up["latest"] if up["available"] else "", "updateState": up["state"],
                "updateProgress": up["done"] / up["total"] if up.get("total") else 0.0, "updateError": up.get("error") or ""}
        except Exception as e:  # noqa: BLE001
            self._status = {"ready": False, "error": str(e)}
        self.changed.emit()

    @Slot()
    def installUpdate(self) -> None:  # noqa: N802 - QML API
        """Download + swap in the new version; REKORD restarts by itself. Where it can't (e.g. a system package),
        the settings explain how."""
        from .. import updater
        if not updater.info().get("can_install"):
            self.openClassic("settings?s=data")
            return

        def go():
            try:
                updater.install()
            except Exception as e:  # noqa: BLE001
                self.toast.emit(str(e))
        threading.Thread(target=go, daemon=True, name="update").start()
        self.toast.emit("Update wird geladen – REKORD startet danach neu.")
        QTimer.singleShot(300, self.refresh)

    @Slot()
    def quit(self) -> None:
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.quit()

    @Slot(str)
    def openClassic(self, page: str = "") -> None:  # noqa: N802 - QML API
        """Pages that aren't part of the new app yet open in the previous interface, in its own window."""
        import subprocess

        from .. import system
        url = f"http://localhost:{self._port}/#/{page}" if page else f"http://localhost:{self._port}/"
        try:
            subprocess.Popen(system.app_command() + ["--classic", url], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **system.hidden())
        except OSError as e:
            self.toast.emit(f"Klassische Ansicht startet nicht: {e}")
