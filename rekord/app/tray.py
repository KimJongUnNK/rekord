"""REKORD in the menu bar / notification area: shows that it's running (also in the background, started with the
computer) and whether it records, brings the window back, starts or stops a recording, quits – and says so when a
recording is fully worked out while you're in another program."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject, Slot

from .. import db

log = logging.getLogger("rekord.app")


def describe(state: str, elapsed: str, hidden: bool) -> str:
    """The tooltip: what REKORD is doing right now."""
    if state == "recording":
        return f"REKORD – nimmt auf · {elapsed}"
    if state == "paused":
        return f"REKORD – pausiert · {elapsed}"
    if state in ("starting", "stopping"):
        return "REKORD – einen Moment …"
    return "REKORD – läuft im Hintergrund" if hidden else "REKORD"


class Tray(QObject):
    def __init__(self, app, win, state, live, api, icon: Path | None = None, parent=None):
        super().__init__(parent)
        self._win, self._state, self._live = win, state, live
        self._tray = None
        self._last_rid = ""
        try:
            from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
        except ImportError:  # Qt without widgets: no tray, everything else works
            return
        if not isinstance(app, QApplication) or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        from PySide6.QtGui import QIcon
        self._tray = QSystemTrayIcon(QIcon(str(icon)) if icon else app.windowIcon(), self)
        self._menu = QMenu()
        self._menu.addAction("REKORD öffnen", self.show_window)
        self._rec = self._menu.addAction("Aufnehmen", self._record)
        self._menu.addSeparator()
        self._menu.addAction("REKORD beenden", self._quit)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._activated)
        self._tray.messageClicked.connect(self._message_clicked)
        win.visibleChanged.connect(self.update)
        live.changed.connect(self.update)
        api.event.connect(self._on_event)
        self.update()
        self._tray.show()

    @property
    def available(self) -> bool:
        return self._tray is not None

    @Slot()
    def update(self, *_) -> None:
        if self._tray is None:
            return
        st = self._live.property("state")
        self._tray.setToolTip(describe(st, self._live.property("elapsedText"), not self._win.isVisible()))
        self._rec.setText("Aufnahme stoppen & speichern" if st in ("recording", "paused") else "Aufnehmen")
        self._rec.setEnabled(st in ("idle", "recording", "paused"))

    @Slot()
    def show_window(self) -> None:
        self._state.focusRequested.emit()

    def _activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def _record(self) -> None:
        if self._live.property("state") in ("recording", "paused"):
            self._live.stop()
            return
        self.show_window()
        QMetaObject.invokeMethod(self._win, "startRecording")  # "Wer ist dabei?" first, as always

    def _quit(self) -> None:
        if self._live.property("state") != "idle":
            self.show_window()  # asks first: the recording is saved before REKORD ends
        QMetaObject.invokeMethod(self._win, "quitApp")

    def _on_event(self, ev: dict) -> None:
        if self._tray is None or ev.get("type") != "done" or self._win.isActive():
            return
        rec = db.get_recording(ev.get("id", "")) or {}
        self._last_rid = rec.get("id", "")
        self._tray.showMessage("Fertig ausgewertet", f"„{rec.get('title') or 'Aufnahme'}“ – Transkript und Sprecher sind da.")

    def _message_clicked(self) -> None:
        self.show_window()
        if self._last_rid:
            from PySide6.QtCore import Q_ARG
            QMetaObject.invokeMethod(self._win, "openRecording", Q_ARG("QVariant", self._last_rid), Q_ARG("QVariant", 0))
