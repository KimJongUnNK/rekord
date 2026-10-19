"""CI: the real in-app update with the packaged app.

An installed "old" REKORD (it pretends to be 1.0.0) finds this build in a local fake release, downloads it,
replaces itself in the same place and restarts: new files, same path, one single REKORD process, leftovers gone.
Then a second start of the same version must not add a second REKORD.
    python scripts/update_smoke.py desktop/dist
"""
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rekord import config, system  # noqa: E402

VER = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text("utf-8"), re.M)[1]
PORT = 8797


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def prepare(dist: Path, tmp: Path):
    """Install a copy like the installer does, and build the release file like the release pipeline does."""
    apps, pub = tmp / "apps", tmp / "pub"
    apps.mkdir()
    pub.mkdir()
    if sys.platform == "darwin":
        name = "REKORD-macOS-AppleSilicon.zip"
        subprocess.run(["ditto", str(dist / "REKORD.app"), str(apps / "REKORD.app")], check=True)
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(dist / "REKORD.app"), str(pub / name)], check=True)
        root = apps / "REKORD.app"
        return root / "Contents/MacOS/REKORD", root, root / "Contents" / "old-marker", name, pub
    if sys.platform == "win32":
        name = "REKORD-Windows-x64.zip"
        shutil.copytree(dist / "REKORD", apps / "REKORD")
        shutil.make_archive(str(pub / name[:-4]), "zip", root_dir=dist, base_dir="REKORD")
        root = apps / "REKORD"
        return root / "REKORD.exe", root, root / "old-marker", name, pub
    name = f"REKORD-{VER}-Linux-x86_64.tar.gz"
    root = apps / "rekord" / "app"
    shutil.copytree(dist / "REKORD", root, symlinks=True)
    with tarfile.open(pub / name, "w:gz") as t:
        t.add(dist / "REKORD", arcname=f"rekord-{VER}/rekord")
    return root / "REKORD", root, root / "old-marker", name, pub


def serve_release(pub: Path, name: str) -> str:
    data = (pub / name).read_bytes()

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(pub), **k)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    (pub / "release.json").write_text(json.dumps({
        "tag_name": f"v{VER}", "html_url": base, "body": "CI-Update",
        "assets": [{"name": name, "browser_download_url": f"{base}/{name}", "size": len(data),
                    "digest": "sha256:" + hashlib.sha256(data).hexdigest()}]}))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    say(f"fake release {VER}: {name} ({len(data) / 2**20:.0f} MB)")
    return f"{base}/release.json"


def api(path: str, method: str = "GET", timeout: float = 10):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, data=b"{}" if method == "POST" else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def wait_version(want: str, timeout: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if api("/api/status", timeout=3)["version"] == want:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


def main() -> int:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "desktop/dist").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="rekord-update-"))
    exe, root, marker, name, pub = prepare(dist, tmp)
    url = serve_release(pub, name)
    (config.pointer_path().parent / "app.json").unlink(missing_ok=True)  # no "newest REKORD" from earlier runs
    env = dict(os.environ, REKORD_TEST_VERSION="1.0.0", REKORD_HEADLESS="1", REKORD_PORT=str(PORT), REKORD_LAN="0",
               REKORD_HOME=str(tmp / "home"), REKORD_UPDATE_URL=url)
    say("start the old REKORD:", exe)
    old = subprocess.Popen([str(exe)], env=env, cwd=str(tmp), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert wait_version("1.0.0", 240), "old REKORD did not start"
        marker.write_text("old")
        u = api("/api/update/check", "POST", timeout=30)
        say("check:", {k: u[k] for k in ("current", "latest", "available", "kind", "can_install", "manual")})
        assert u["available"] and u["can_install"], u
        api("/api/update/install", "POST")
        last = ""
        t0 = time.time()
        while time.time() - t0 < 300:
            try:
                st = api("/api/update", timeout=3)
                line = f"{st['state']} {st['done'] // 2**20}/{st['total'] // 2**20} MB {st['error']}"
                if line != last:
                    say(line)
                    last = line
                assert st["state"] != "error", st["error"]
            except (OSError, ValueError):
                break  # the old one has quit
            time.sleep(0.5)
        assert wait_version(VER, 300), "the new version did not come up"
        say("now running:", VER)
        assert old.wait(timeout=60) == 0, "the old process did not quit"
        assert exe.exists() and not marker.exists(), "the app was not replaced in place"
        procs = system.rekord_processes()
        say("REKORD processes:", procs)
        assert len(procs) == 1, f"expected exactly one REKORD, got {procs}"
        t0 = time.time()
        while (root.parent / ".rekord-update").exists() and time.time() - t0 < 60:
            time.sleep(1)
        assert not (root.parent / ".rekord-update").exists(), "update leftovers were not removed"
        assert api("/api/status")["update"]["just_updated"] == "1.0.0"
        # started again (same version): no second REKORD
        env.pop("REKORD_TEST_VERSION")
        again = subprocess.Popen([str(exe)], env=env, cwd=str(tmp), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert again.wait(timeout=120) == 0
        assert len(system.rekord_processes()) == 1
        say("OK: updated in place, one REKORD")
        return 0
    finally:
        try:
            api("/api/shutdown", "POST")
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
        for pid, _ in system.rekord_processes():
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        if old.poll() is None:
            old.kill()


if __name__ == "__main__":
    sys.exit(main())
