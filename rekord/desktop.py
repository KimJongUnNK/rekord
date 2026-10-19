"""Desktop app for Windows/macOS/Linux: the hub runs in-process, the UI in a native webview window -
or, where no webview is available (typical on Linux), in the default browser as an installable PWA."""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.request
import webbrowser


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _is_rekord(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as r:
            return "version" in json.loads(r.read())
    except Exception:  # noqa: BLE001
        return False


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


def _window(url: str, own_hub: bool) -> None:
    """Native window (pywebview) or, where there is none, the browser. Without our own hub there is nothing
    to keep alive after the browser opened."""
    try:
        import webview  # pip install pywebview
    except ImportError:
        webview = None
    if webview is not None:
        try:
            webview.create_window("REKORD", url, width=1320, height=860, min_size=(380, 600))
            webview.start()
            return
        except Exception as e:  # noqa: BLE001 - no GUI backend (e.g. Linux without WebKitGTK/Qt)
            print(f"Kein natives Fenster ({e}) – öffne im Browser.")
    open_url(url)
    if own_hub:
        print(f"REKORD läuft: {url}  – beenden über Einstellungen → „REKORD beenden“ oder Strg+C.")
        while True:
            time.sleep(3600)


def run(port: int = 8765, lan: bool = False, background: bool = False) -> None:
    """background: hub only (started with the computer), the window comes from the next click on the icon."""
    from . import system
    url = f"http://localhost:{port}"
    background = background or os.environ.get("REKORD_HEADLESS") == "1"
    system.ensure_start_menu()
    if _port_open(port) and _is_rekord(port):  # REKORD already runs (window or in the background) → just show it
        if not background:
            _window(url, own_hub=False)
        return

    from .__main__ import serve
    host = "0.0.0.0" if lan else "127.0.0.1"
    threading.Thread(target=serve, args=(host, port, False, False), daemon=True).start()
    _wait(port)
    if background:  # CI smoke test / started with the computer
        while True:
            time.sleep(3600)
    _window(url, own_hub=True)
