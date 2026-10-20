"""REKORD's window: a native program built with Qt Quick – no browser, no web view.

The engine (recognition, transcription, processing) runs in this process; the hub for the iPhone app runs next to
it in a background thread. Pages that aren't part of the native app yet open in the previous interface
("klassische Ansicht", its own window) until they are ported."""
from __future__ import annotations

import functools
import logging
import os
import subprocess
import sys
from pathlib import Path

QML_DIR = Path(__file__).with_name("qml")
log = logging.getLogger("rekord.app")


def importable() -> bool:
    try:
        import PySide6.QtMultimedia  # noqa: F401
        import PySide6.QtQuick  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - not installed, or its libraries are missing
        return False


def usable() -> bool:
    """Can this computer show the native window? REKORD_CLASSIC=1 keeps the previous interface.

    On Linux a missing system library (e.g. libxcb-cursor0) makes Qt abort the whole process instead of raising,
    so a quick try runs in a child process first – then REKORD falls back to the previous interface."""
    if os.environ.get("REKORD_CLASSIC") == "1" or not importable():
        return False
    if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM"):
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        return _probe_ok()
    return True


@functools.lru_cache(maxsize=1)
def _probe_ok() -> bool:
    from .. import system
    try:
        r = subprocess.run(system.app_command() + ["--qt-probe"], timeout=30, capture_output=True, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("qt probe: %s", e)
        return False
    if r.returncode != 0:
        log.warning("qt probe failed (%s): %s", r.returncode, (r.stderr or b"")[-600:].decode(errors="replace"))
    return r.returncode == 0


def probe() -> int:
    """Child process of usable(): can Qt open its display here?"""
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication(sys.argv[:1])
    return 0 if app.primaryScreen() is not None else 1


class Window:
    """The running interface: Qt app, QML engine, the window and the objects QML talks to."""

    def __init__(self, app, engine, win, objects: dict, warnings: list[str]):
        self.app, self.engine, self.win, self.objects, self.warnings = app, engine, win, objects, warnings


def build(port: int, keep_running: bool | None = None) -> Window | None:
    """Create the window (shown right away). None if the interface couldn't load."""
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401 - the root object then is a QQuickWindow (grabWindow)

    from . import bridge

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    app.setApplicationName("REKORD")
    app.setApplicationDisplayName("REKORD")
    app.setOrganizationName("REKORD")
    app.setDesktopFileName("rekord")
    app.setQuitOnLastWindowClosed(False)  # Main.qml decides: quit, or keep running for the iPhone (autostart)
    icon = _icon_path()
    if icon:
        app.setWindowIcon(QIcon(str(icon)))

    warnings: list[str] = []
    engine = QQmlApplicationEngine(app)  # first: it's also torn down first, before the objects its pages show
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    state = bridge.AppState(port, keep_running=_keep_running() if keep_running is None else keep_running)
    objects = {"rekord": state, "library": bridge.Library(), "detail": bridge.Detail(), "people": bridge.People(),
               "live": bridge.Live()}
    for o in objects.values():
        o.setParent(app)
    for name, obj in objects.items():
        engine.rootContext().setContextProperty(name, obj)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        log.error("REKORD-Oberfläche lädt nicht: %s", " | ".join(warnings) or "unbekannt")
        return None
    win = engine.rootObjects()[0]
    state.attach(win)
    objects["library"].refresh()
    objects["people"].refresh()
    state.refresh()
    return Window(app, engine, win, objects, warnings)


def run(port: int) -> int:
    """Show the window until it's closed (or REKORD is quit). Returns 0, or 1 if the interface couldn't load
    (the caller then falls back to the previous interface)."""
    from PySide6.QtCore import QTimer

    from .. import desktop
    w = build(port)
    if w is None:
        return 1
    desktop.window_open = True
    desktop.focus_hook = w.objects["rekord"].focusRequested.emit  # a second start brings this window to the front
    selftest = os.environ.get("REKORD_SELFTEST_UI")
    if selftest:
        QTimer.singleShot(400, lambda: _selftest(w.app, w.win, Path(selftest), w.warnings))
    try:
        code = w.app.exec()
    finally:
        desktop.focus_hook = None
        desktop.window_open = False
    if selftest:  # CI: the result is the exit code of the whole program
        sys.stdout.flush()
        os._exit(code)
    return 0


def _keep_running() -> bool:
    """Started with the computer: closing the window keeps REKORD running for the iPhone app."""
    from .. import system
    try:
        return system.autostart_enabled()
    except Exception:  # noqa: BLE001
        return False


def _icon_path() -> Path | None:
    p = Path(__file__).parent.parent / "web" / "icons" / "icon-512.png"
    return p if p.is_file() else None


def _selftest(app, win, out: Path, warnings: list[str]) -> None:
    """CI: walk through the pages of the packaged app, save a screenshot of each, quit (exit code 2 on QML warnings)."""
    from PySide6.QtCore import QTimer
    out.mkdir(parents=True, exist_ok=True)
    steps = [("library", lambda: win.setProperty("page", "library")),
             ("live", lambda: win.setProperty("page", "live")),
             ("who", lambda: win.setProperty("whoOpen", True)),
             ("classic", lambda: (win.setProperty("whoOpen", False), win.setProperty("page", "people")))]

    def shoot(i: int) -> None:
        try:
            win.grabWindow().save(str(out / f"{steps[i][0]}.png"))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"screenshot {steps[i][0]}: {e}")
        step(i + 1)

    def step(i: int) -> None:
        if i < len(steps):
            try:
                steps[i][1]()
            except Exception as e:  # noqa: BLE001
                warnings.append(f"step {steps[i][0]}: {e}")
            QTimer.singleShot(900, lambda: shoot(i))
            return
        (out / "qml-warnings.txt").write_text("\n".join(warnings), encoding="utf-8")
        summary = f"UI selftest: {len(steps)} pages, {len(warnings)} QML warnings"
        (out / "result.txt").write_text(summary, encoding="utf-8")  # the windowed app on Windows has no console
        print(summary, flush=True)
        for w in warnings:
            print("  ", w, flush=True)
        app.exit(2 if warnings else 0)
    step(0)
