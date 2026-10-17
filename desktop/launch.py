"""Entry point for the packaged desktop app (PyInstaller). Window + hub in one process."""
import os
import sys

from rekord.desktop import run

if __name__ == "__main__":
    # packaged app: reachable in the Wi-Fi by default so the iPhone can pair (protected by the pairing code);
    # REKORD_LAN=0 or --local keeps it on this computer only
    lan = "--local" not in sys.argv and os.environ.get("REKORD_LAN", "1") != "0"
    run(port=int(os.environ.get("REKORD_PORT", "8765")), lan=lan)
