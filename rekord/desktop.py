"""Native desktop window for Windows/macOS/Linux: the hub runs in-process, the UI in a system webview."""
from __future__ import annotations

import os
import socket
import threading
import time


def _wait(port: int, timeout: float = 30) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)


def run(port: int = 8765, lan: bool = False) -> None:
    from .__main__ import serve
    host = "0.0.0.0" if lan else "127.0.0.1"
    threading.Thread(target=serve, args=(host, port, False, False), daemon=True).start()
    _wait(port)
    if os.environ.get("REKORD_HEADLESS") == "1":  # CI smoke test / server-only mode
        while True:
            time.sleep(3600)
    try:
        import webview  # pip install pywebview
    except ImportError:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
        print("pywebview fehlt – REKORD läuft im Browser. Strg+C zum Beenden.")
        while True:
            time.sleep(3600)
    webview.create_window("REKORD", f"http://localhost:{port}", width=1320, height=860, min_size=(380, 600))
    webview.start()
