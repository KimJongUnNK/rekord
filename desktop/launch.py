"""Entry point for the packaged desktop app (PyInstaller).

No arguments (double-click, app menu)  → hub + window/browser.
With a subcommand → the normal CLI, e.g.  `rekord mcp`, `rekord serve --host 0.0.0.0`, `rekord models list`.
"""
import os
import sys

from rekord.__main__ import main as cli
from rekord.desktop import run

COMMANDS = {"serve", "desktop", "process", "models", "enroll", "mcp", "-h", "--help"}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in COMMANDS:
        cli(sys.argv[1:])
    else:
        # packaged app: reachable in the Wi-Fi by default so the iPhone can pair (protected by the pairing code);
        # REKORD_LAN=0 or --local keeps it on this computer only
        lan = "--local" not in sys.argv and os.environ.get("REKORD_LAN", "1") != "0"
        run(port=int(os.environ.get("REKORD_PORT", "8765")), lan=lan)
