"""CI: the packaged REKORD analyzes in its own low-priority process (`REKORD --process-job <id>`), the way the
window starts it – on macOS through taskpolicy (utility QoS). Without models: the recording points to a missing file,
so the analysis process must start, lower its priority, load the speech engine (sherpa-onnx with its native
libraries), fail cleanly on the file, write the error into the database and end.

    python scripts/job_smoke.py <REKORD binary>
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main(binary: str) -> int:
    home = tempfile.mkdtemp(prefix="rekord-job-")
    os.environ["REKORD_HOME"] = home
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from rekord import db, system
    rid = db.create_recording("Smoke", str(Path(home) / "gibts-nicht.m4a"))["id"]
    db.close()
    cmd = system.in_background([str(Path(binary).resolve()), "--process-job", rid])
    print("command:", " ".join(cmd))
    env = dict(os.environ, REKORD_JOB_GENTLE="1", REKORD_JOB_THREADS="2", REKORD_JOB_PARENT=str(os.getpid()))
    t0 = time.time()
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180, errors="replace")
    took = time.time() - t0
    rec = db.get_recording(rid)
    print(f"exit code {r.returncode} after {took:.1f}s · status {rec['status']} · error: {rec['error']}")
    # the file error comes after the speech engine loaded – an engine that can't load would be the error instead
    if r.returncode != 1 or rec["status"] != "error" or "gibts-nicht" not in (rec["error"] or ""):
        print("FAIL\n" + (r.stdout + r.stderr)[-3000:])
        return 1
    print("OK – analysis process started, speech engine loaded, failed cleanly on the file, reported back")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
