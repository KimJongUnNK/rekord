"""CI: the packaged REKORD opens its native window (the real way: double-click → hub + window), walks through the
pages, saves a screenshot of each and quits. Fails when the window doesn't come up or QML reports problems.

    python scripts/window_smoke.py <REKORD binary> <screenshot dir>
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main(binary: str, out: str) -> int:
    shots = Path(out).resolve()
    shots.mkdir(parents=True, exist_ok=True)
    home = tempfile.mkdtemp(prefix="rekord-window-")
    env = dict(os.environ, REKORD_HOME=home, REKORD_PORT="8797", REKORD_LAN="0", REKORD_SELFTEST_UI=str(shots))
    env.pop("REKORD_HEADLESS", None)
    try:
        r = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=300, errors="replace")
    except subprocess.TimeoutExpired as e:
        print("TIMEOUT – the window never finished its round", (e.stdout or "")[-3000:] if isinstance(e.stdout, str) else "")
        return 1
    log = (r.stdout or "") + (r.stderr or "")
    applog = Path(home) / "rekord.log"  # windowed app without a console (Windows) logs here
    for cand in (applog, *Path(home).glob("**/rekord.log")):
        if cand.is_file():
            log += "\n--- rekord.log\n" + cand.read_text(errors="replace")
            break
    result = shots / "result.txt"
    if result.exists():
        log += "\n" + result.read_text()
    print(log[-4000:])
    pngs = sorted(p.name for p in shots.glob("*.png"))
    print("exit code:", r.returncode, "| screenshots:", ", ".join(pngs) or "none")
    warn = shots / "qml-warnings.txt"
    if warn.exists() and warn.read_text().strip():
        print("QML problems:\n" + warn.read_text())
    if "QML warnings" not in log:
        print("FAIL: the native window did not start (REKORD fell back to the previous interface or crashed)")
        return 1
    if r.returncode != 0 or len(pngs) < 5:
        print("FAIL")
        return 1
    print("OK – native window shown, pages rendered")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "window-shots"))
