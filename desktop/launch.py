"""Entry point for the packaged desktop app (PyInstaller).

No arguments (double-click, app menu)  → hub + REKORD's window.  --background → hub only.
With a subcommand → the normal CLI, e.g.  `rekord mcp`, `rekord serve --host 0.0.0.0`, `rekord models list`.
Internal: --classic <url> (a page of the previous interface), --qt-probe (can the native window start here?).
"""
import os
import sys

from rekord.__main__ import main as cli
from rekord.desktop import run

COMMANDS = {"serve", "desktop", "process", "models", "enroll", "mcp", "-h", "--help", "--classic", "--qt-probe"}

if __name__ == "__main__":
    from rekord.system import ensure_output
    ensure_output()  # windowed app without a console (double-click on Windows) → rekord.log instead of a crash
    if len(sys.argv) > 1 and sys.argv[1] in COMMANDS:
        cli(sys.argv[1:])
    else:
        # packaged app: reachable in the Wi-Fi by default so the iPhone can pair (protected by the pairing code);
        # REKORD_LAN=0 or --local keeps it on this computer only
        lan = "--local" not in sys.argv and os.environ.get("REKORD_LAN", "1") != "0"
        # --background: started with the computer (Einstellungen → Speicher → Mit dem Computer starten)
        run(port=int(os.environ.get("REKORD_PORT", "8765")), lan=lan, background="--background" in sys.argv)
