"""CLI: python -m rekord [serve|desktop|process|models|mcp|enroll]"""
from __future__ import annotations

import argparse
import logging
import sys
import webbrowser


def _tls(host_names: list[str]):
    """Self-signed cert so phones can use the mic via the browser over Wi-Fi (Safari needs HTTPS)."""
    import datetime as dt
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    from . import config
    d = config.HOME / "tls"
    d.mkdir(exist_ok=True)
    crt, key = d / "rekord.crt", d / "rekord.key"
    if crt.exists() and key.exists():
        return str(crt), str(key)
    k = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "REKORD local hub")])
    alt = [x509.DNSName("localhost")]
    for h in host_names:
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(h)))
        except ValueError:
            alt.append(x509.DNSName(h))
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(k, hashes.SHA256()))
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()))
    return str(crt), str(key)


def serve(host: str, port: int, https: bool, open_browser: bool, auto_download: bool = True) -> None:
    import uvicorn

    from .server import app, lan_ips
    app.state.port = port
    app.state.lan = host not in ("127.0.0.1", "localhost")
    app.state.auto_download = auto_download
    ssl = {}
    if https:
        crt, key = _tls(lan_ips())
        ssl = {"ssl_certfile": crt, "ssl_keyfile": key}
    scheme = "https" if https else "http"
    print(f"\n  REKORD läuft:  {scheme}://localhost:{port}")
    if app.state.lan:
        for ip in lan_ips():
            print(f"  Im WLAN:       {scheme}://{ip}:{port}   (iPhone: Einstellungen → Gerät koppeln)")
    print()
    if open_browser:
        import threading
        threading.Timer(1.2, lambda: webbrowser.open(f"{scheme}://localhost:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="warning", ws_max_size=16 * 1024 * 1024, **ssl)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="rekord", description="REKORD – lokaler KI-Notizrekorder")
    sub = p.add_subparsers(dest="cmd")
    sv = sub.add_parser("serve", help="Hub starten (Standard)")
    sv.add_argument("--host", default="127.0.0.1", help="0.0.0.0 = im WLAN erreichbar (für iPhone)")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--https", action="store_true", help="Selbstsigniertes Zertifikat (Mikrofon im Handy-Browser)")
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
        serve(a.host, a.port, a.https, not a.no_browser, not a.no_download)
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
