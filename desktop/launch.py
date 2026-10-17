"""Entry point for the packaged desktop app (PyInstaller). Window + hub in one process."""
import os
import sys

from rekord.desktop import run

if __name__ == "__main__":
    run(port=int(os.environ.get("REKORD_PORT", "8765")), lan="--lan" in sys.argv or os.environ.get("REKORD_LAN") == "1")
