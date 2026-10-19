"""Desktop app for Windows/macOS/Linux: the hub runs in-process, the UI in a native webview window -
or, where no webview is available (typical on Linux), in the default browser as an installable PWA."""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _status(port: int) -> dict | None:
    """The REKORD hub on this port (its /api/status), or None."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=3) as r:
            d = json.loads(r.read())
            return d if "version" in d else None
    except Exception:  # noqa: BLE001
        return None


def _post(port: int, path: str, body: dict | None = None) -> int:
    """POST to the local hub → HTTP status (0 = not reachable)."""
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return 0


def _wait(port: int, timeout: float = 30) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout and not _port_open(port):
        time.sleep(0.2)


def open_url(url: str) -> None:
    """Open the browser. In the packaged Linux app, child processes must not inherit our bundled
    libraries (LD_LIBRARY_PATH), or system tools like kde-open/xdg-open crash on the old libstdc++."""
    import subprocess
    import sys

    from .system import child_env
    if sys.platform.startswith("linux") and getattr(sys, "frozen", False):
        try:
            subprocess.Popen(["xdg-open", url], env=child_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            pass
    webbrowser.open(url)


def _wait_free(port: int, timeout: float = 15) -> None:
    """After a restart (new data folder) the old process still holds the port for a moment."""
    t0 = time.time()
    while time.time() - t0 < timeout and _port_open(port):
        time.sleep(0.2)


# ------------------------------------------------------------------ one REKORD, one window

window_open = False  # this process shows the hub's window (the hub can bring it to the front)


def focus() -> bool:
    """Bring this process's window to the front (a second start of REKORD asks for this instead of opening another)."""
    if not window_open:
        return False
    try:
        import webview
        for w in webview.windows:
            w.restore()
            w.show()
            w.on_top = True
            w.on_top = False
        return bool(webview.windows)
    except Exception:  # noqa: BLE001
        return False


def _allow_focus() -> None:
    if sys.platform == "win32":  # Windows only lets the foreground app hand the focus on
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except Exception:  # noqa: BLE001
            pass


def _show(url: str, port: int, info: dict) -> None:
    """REKORD already runs: bring its window to the front, or open a window for it (hub in the background)."""
    if info.get("window"):
        _allow_focus()
        if _post(port, "/api/window/focus") == 200:
            return
    _window(url, own_hub=False, port=port)


def _take_over(port: int) -> bool:
    """We're the newer version: the old one quits (False while it records – it must not lose a recording)."""
    code = _post(port, "/api/shutdown")
    if code == 409:
        return False
    _wait_free(port, 20)
    from . import system
    system.stop_other_instances()  # leftover windows of the old version
    _wait_free(port, 10)
    return True


def _start_hub(host: str, port: int) -> None:
    """This process becomes REKORD: the newest version on this computer, with the hub in a background thread."""
    from . import system, updater
    from .__main__ import serve
    updater.remember_install()
    system.ensure_start_menu()
    threading.Thread(target=serve, args=(host, port, False, False), daemon=True).start()
    _wait(port)


def _watch(port: int, host: str, take_over: bool) -> None:
    """A window without its own hub: follows the hub. Hub updated → the new version shows itself and this old
    window closes. Hub gone for good → close. take_over: an older hub was recording when we started – as soon as
    the recording is finished we take its place (the page reloads into the new version by itself)."""
    global window_open
    from . import __version__, updater
    gone = 0
    while True:
        time.sleep(3)
        info = _status(port)
        if info is None:
            gone += 3
            if gone >= 30:
                os._exit(0)
            continue
        gone = 0
        theirs = str(info.get("version", "0"))
        if take_over and updater.newer(__version__, theirs):
            if not info.get("live") and _take_over(port):
                _start_hub(host, port)
                window_open = threading.current_thread() is not threading.main_thread()  # a window runs on the main thread
                return
        elif updater.newer(theirs, __version__):
            exe = info.get("exe")
            if exe and os.path.exists(exe):  # the newer REKORD opens its own window …
                import subprocess

                from . import system
                subprocess.Popen([exe], env=system.child_env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, **system.hidden())
            os._exit(0)  # … and this old one closes


def _window(url: str, own_hub: bool, restarted: bool = False, port: int = 8765, host: str = "127.0.0.1",
            take_over: bool = False) -> None:
    """Native window (pywebview) or, where there is none, the browser. Without our own hub there is nothing
    to keep alive after the browser opened."""
    global window_open
    try:
        import webview  # pip install pywebview
    except ImportError:
        webview = None
    if webview is not None:
        try:
            webview.create_window("REKORD", url, width=1320, height=860, min_size=(380, 600))
            from . import config
            if own_hub:
                window_open = True
            else:
                threading.Thread(target=_watch, args=(port, host, take_over), daemon=True, name="watch-hub").start()
            # not private: otherwise the window forgets this device's settings (theme, accent, mic …) on every start
            webview.start(private_mode=False, storage_path=str(config.pointer_path().parent / "webview"))
            window_open = False
            return
        except Exception as e:  # noqa: BLE001 - no GUI backend (e.g. Linux without WebKitGTK/Qt)
            window_open = False
            print(f"Kein natives Fenster ({e}) – öffne im Browser.")
    if not restarted:  # the open browser tab reconnects by itself
        open_url(url)
    if take_over:  # browser mode: wait here until the old version has finished recording, then take over
        _watch(port, host, take_over=True)
        own_hub = True
    if own_hub:
        print(f"REKORD läuft: {url}  – beenden über Einstellungen → „REKORD beenden“ oder Strg+C.")
        while True:
            time.sleep(3600)


def run(port: int = 8765, lan: bool = False, background: bool = False) -> None:
    """background: hub only (started with the computer), the window comes from the next click on the icon.

    Never two REKORDs: an older copy hands over to the newest installed one; if REKORD already runs, its window
    comes to the front; if an older version runs, it quits and this one takes its place."""
    from . import __version__, system, updater
    system.ensure_output()  # double-click on Windows: no console – the server would crash setting up its logs
    url = f"http://localhost:{port}"
    host = "0.0.0.0" if lan else "127.0.0.1"
    background = background or os.environ.get("REKORD_HEADLESS") == "1"
    restarted = os.environ.get("REKORD_RESTARTING") == "1"
    os.environ.pop("REKORD_RESTARTING", None)  # not for programs we start later
    if restarted:
        _wait_free(port)
    elif updater.hand_over_to_newest(sys.argv[1:]):
        return
    info = _status(port) if _port_open(port) else None
    if info is not None and not updater.newer(__version__, str(info.get("version", "0"))):
        if not background:  # the same (or a newer) version runs → just show it
            _show(url, port, info)
        return
    if info is not None and not _take_over(port):
        # the old version is recording right now: never cut that off – take over as soon as it's finished
        print(f"REKORD {info.get('version')} nimmt gerade auf – {__version__} übernimmt danach.")
        if not background:
            _window(url, own_hub=False, port=port, host=host, take_over=True)
            return
        _watch(port, host, take_over=True)
    else:
        _start_hub(host, port)
    if background:  # CI smoke test / started with the computer
        while True:
            time.sleep(3600)
    _window(url, own_hub=True, restarted=restarted, port=port, host=host)
