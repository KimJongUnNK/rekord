"""CLI: python -m rekord [serve|desktop|process|models|mcp|enroll]"""
from __future__ import annotations

import argparse
import logging
import socket
import sys
import webbrowser


def _free(host: str, port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def serve(host: str, port: int, open_browser: bool = False, auto_download: bool = True) -> None:
    import os
    import time

    import uvicorn
    if os.environ.pop("REKORD_RESTARTING", None) == "1":  # restarted into a new data folder: old process is ending
        open_browser = False
        for _ in range(75):
            if _free(host, port):
                break
            time.sleep(0.2)

    from .server import app, lan_ips
    app.state.port = port
    app.state.lan = host not in ("127.0.0.1", "localhost")
    app.state.auto_download = auto_download
    cfg = uvicorn.Config(app, host=host, port=port, log_level="warning", ws_max_size=16 * 1024 * 1024)
    print(f"\n  REKORD läuft:  http://localhost:{port}")
    if app.state.lan:
        for ip in lan_ips():
            print(f"  Im WLAN:       http://{ip}:{port}   (für die iPhone-App: Einstellungen → iPhone & Geräte)")
    print()
    if open_browser:
        import threading
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.Server(cfg).run()


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--qt-probe"]:  # can REKORD's native window start on this computer? (see app.usable)
        from .app import probe
        sys.exit(probe())
    from .system import ensure_output
    ensure_output()  # started without a console (pythonw, windowed app): log to a file instead of crashing
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="rekord", description="REKORD – lokaler KI-Notizrekorder")
    sub = p.add_subparsers(dest="cmd")
    sv = sub.add_parser("serve", help="Hub starten (Standard)")
    sv.add_argument("--host", default="127.0.0.1", help="0.0.0.0 = im WLAN erreichbar (für iPhone)")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--no-browser", action="store_true")
    sv.add_argument("--no-download", action="store_true", help="Modelle nicht automatisch laden")
    dk = sub.add_parser("desktop", help="Als Desktop-App-Fenster starten (pywebview)")
    dk.add_argument("--lan", action="store_true", help="Zusätzlich im WLAN erreichbar machen")
    dk.add_argument("--port", type=int, default=8765)
    pr = sub.add_parser("process", help="Datei(en) direkt verarbeiten und Markdown ausgeben")
    pr.add_argument("files", nargs="+")
    pr.add_argument("--summary", default="", help="Template-ID für Zusammenfassung, z.B. meeting")
    md = sub.add_parser("models", help="Modelle verwalten")
    md.add_argument("action", choices=["list", "download", "delete"])
    md.add_argument("ids", nargs="*")
    en = sub.add_parser("enroll", help="Stimmprofil aus Sprachprobe anlegen")
    en.add_argument("name")
    en.add_argument("file")
    sub.add_parser("mcp", help="MCP-Server (stdio) für Claude Desktop / Claude Code")
    a = p.parse_args(argv)

    if a.cmd in (None, "serve"):
        if a.cmd is None:
            a = sv.parse_args([])
        serve(a.host, a.port, not a.no_browser, not a.no_download)
    elif a.cmd == "desktop":
        from .desktop import run
        run(a.port, a.lan)
    elif a.cmd == "process":
        from pathlib import Path

        from . import db, export, pipeline, summarize
        for f in a.files:
            rec = db.create_recording(Path(f).stem, str(Path(f).resolve()))
            pipeline.process(rec["id"], on_event=lambda e: print(f"  {e.get('stage', '')} {e.get('progress', 0):.0%}",
                                                                  end="\r", file=sys.stderr))
            if a.summary:
                summarize.generate(rec["id"], a.summary)
            print(export.markdown(rec["id"]))
    elif a.cmd == "models":
        from . import models
        if a.action == "list":
            for m in models.status():
                print(f"{'✔' if m['installed'] else ' '} {m['id']:<24} {m['size_mb']:>5} MB  {m['description']}")
        elif a.action == "download":
            for mid in a.ids or models.ESSENTIAL + ["whisper-small"]:
                print("lade", mid, "…")
                models.download(mid)
        else:
            for mid in a.ids:
                models.delete(mid)
    elif a.cmd == "enroll":
        from . import pipeline
        print(pipeline.enroll_from_audio(a.name, a.file))
    elif a.cmd == "mcp":
        logging.getLogger().setLevel(logging.WARNING)
        from .mcp_server import run
        run()


if __name__ == "__main__":
    main()
