"""Updates replace the installed app, and there is never more than one REKORD running."""
import hashlib
import http.server
import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import pytest

from rekord import __version__, config, desktop, system, updater

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    """A tiny local web server: the fake GitHub (release + files) or a fake running REKORD hub."""

    def __init__(self, routes):
        self.routes, self.hits = routes, []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _answer(self):
                outer.hits.append((self.command, self.path))
                code, body = outer.routes.get((self.command, self.path), (404, b"{}"))
                if callable(body):
                    code, body = body()
                if isinstance(body, (dict, list)):
                    body = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _answer

        self.port = _free_port()
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(updater, "_state", {"state": "idle", "done": 0, "total": 0, "error": "", "latest": None,
                                            "checked": 0.0, "check_error": ""})
    monkeypatch.setattr(updater, "_just_updated", "")


def _release(server_url, files: dict[str, bytes], version="9.9.9", digests=True):
    return {"tag_name": f"v{version}", "html_url": "https://example.invalid/r", "body": "## Neu\n- alles besser",
            "assets": [{"name": n, "browser_download_url": f"{server_url}/dl/{n}", "size": len(b),
                        "digest": ("sha256:" + hashlib.sha256(b).hexdigest()) if digests else None}
                       for n, b in files.items()]}


def _github(files, **kw):
    srv = _Server({})
    srv.routes[("GET", "/release")] = (200, _release(srv.url, files, **kw))
    for n, b in files.items():
        srv.routes[("GET", f"/dl/{n}")] = (200, b)
    return srv


def _wait_for(cond, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout and not cond():
        time.sleep(0.05)
    return cond()


def _wait_state(*states, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = updater.info()["state"]
        if st in states:
            return st
        time.sleep(0.05)
    return updater.info()["state"]


# ------------------------------------------------------------------ versions + what's installed

def test_versions_compare_like_humans():
    assert updater.newer("1.0.10", "1.0.9")
    assert updater.newer("v1.1", "1.0.99")
    assert not updater.newer("1.0", "1.0.0") and not updater.newer("1.0.0", "1.0")
    assert not updater.newer("1.0.7", "1.0.8")
    assert updater.version_tuple("2.0.0rc1") == (2,)


def test_source_checkout_never_swaps_itself():
    assert updater.install_kind() == "source"
    assert updater.app_root() is None
    can, why = updater._can_install("source", None)
    assert not can and "git pull" in why


def test_every_release_file_is_known():
    v = "1.2.3"
    names = {k: updater.asset_name(k, v) for k in ("mac-app", "windows", "appimage", "linux-user", "deb", "rpm", "pacman")}
    assert names == {"mac-app": "REKORD-macOS-AppleSilicon.zip", "windows": "REKORD-Windows-x64.zip",
                     "appimage": "REKORD-1.2.3-x86_64.AppImage", "linux-user": "REKORD-1.2.3-Linux-x86_64.tar.gz",
                     "deb": "rekord_1.2.3_amd64.deb", "rpm": "rekord-1.2.3-1.x86_64.rpm",
                     "pacman": "rekord-1.2.3-1-x86_64.pkg.tar.zst"}
    # …and they are exactly what the release pipeline publishes
    build = (ROOT / "packaging/linux/build.sh").read_text("utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text("utf-8")
    for k, n in names.items():
        templ = n.replace(v, "${VER}")
        assert templ in build or n in release, (k, n)


# ------------------------------------------------------------------ check

def test_check_finds_a_newer_version(monkeypatch):
    srv = _github({"REKORD-9.9.9-Linux-x86_64.tar.gz": b"x"})
    monkeypatch.setenv("REKORD_UPDATE_URL", srv.url + "/release")
    try:
        u = updater.check(force=True)
    finally:
        srv.stop()
    assert u["available"] and u["latest"] == "9.9.9" and u["current"] == __version__
    assert "alles besser" in u["notes"]
    assert not u["can_install"] and "git pull" in u["manual"]  # tests run from source
    assert updater.brief() == {"available": True, "latest": "9.9.9", "state": "idle", "just_updated": ""}


def test_check_offline_says_why(monkeypatch):
    monkeypatch.setenv("REKORD_UPDATE_URL", f"http://127.0.0.1:{_free_port()}/nothing")
    u = updater.check(force=True)
    assert not u["available"] and "GitHub" in u["check_error"]


def test_no_update_offered_when_current(monkeypatch):
    srv = _github({}, version=__version__)
    monkeypatch.setenv("REKORD_UPDATE_URL", srv.url + "/release")
    try:
        assert not updater.check(force=True)["available"]
    finally:
        srv.stop()


# ------------------------------------------------------------------ install: the real swap (Linux user install, AppImage)

@pytest.fixture
def installed(tmp_path, monkeypatch):
    """Pretend to be the packaged app, installed for this user in tmp/…/rekord/app."""
    app = tmp_path / "share" / "rekord" / "app"
    app.mkdir(parents=True)
    (app / "REKORD").write_text("old")
    (app / "_internal").mkdir()
    (app / "_internal" / "old-only.txt").write_text("old")
    monkeypatch.setattr(system, "frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "linux")  # the same swap on every CI machine
    monkeypatch.setattr(sys, "executable", str(app / "REKORD"))
    monkeypatch.delenv("APPIMAGE", raising=False)
    started = []
    monkeypatch.setattr(updater, "_relaunch", lambda cmd: started.append(cmd))
    return app, started


def _tarball(v="9.9.9"):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in ((f"rekord-{v}/rekord/REKORD", b"new"), (f"rekord-{v}/rekord/_internal/new-only.txt", b"new"),
                           (f"rekord-{v}/install.sh", b"#!/bin/sh")):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_update_replaces_the_installed_app(installed, monkeypatch):
    app, started = installed
    assert updater.install_kind() == "linux-user" and updater.app_root() == app
    srv = _github({"REKORD-9.9.9-Linux-x86_64.tar.gz": _tarball()})
    monkeypatch.setenv("REKORD_UPDATE_URL", srv.url + "/release")
    try:
        u = updater.check(force=True)
        assert u["can_install"], u
        updater.install()
        assert _wait_state("restarting", "error") == "restarting", updater.info()["error"]
    finally:
        srv.stop()
    # the same place now holds the new version – no second app next to it
    assert (app / "REKORD").read_text() == "new"
    assert (app / "_internal" / "new-only.txt").exists() and not (app / "_internal" / "old-only.txt").exists()
    assert _wait_for(lambda: started) and started == [[str(app / "REKORD")]]
    assert [p.name for p in app.parent.iterdir() if p.name not in ("app", updater.WORK)] == []
    assert json.loads((config.HOME / "updated.json").read_text()) == {"from": __version__, "to": "9.9.9"}
    updater.cleanup()  # while the update is on its way nothing is cleaned up
    assert (app.parent / updater.WORK).exists() and (config.HOME / "updated.json").exists()
    # the new version starts (fresh process): leftovers go, "updated" is shown once
    monkeypatch.setattr(updater, "__version__", "9.9.9")
    updater._state["state"] = "idle"
    updater.cleanup()
    assert not (app.parent / updater.WORK).exists()
    assert updater.info()["just_updated"] == __version__
    assert not (config.HOME / "updated.json").exists()


def test_broken_download_keeps_the_old_app(installed, monkeypatch):
    app, started = installed
    good = _tarball()
    srv = _github({"REKORD-9.9.9-Linux-x86_64.tar.gz": good})
    srv.routes[("GET", "/dl/REKORD-9.9.9-Linux-x86_64.tar.gz")] = (200, good[:-10] + b"0123456789")  # same size, other bytes
    monkeypatch.setenv("REKORD_UPDATE_URL", srv.url + "/release")
    try:
        updater.check(force=True)
        updater.install()
        assert _wait_state("restarting", "error") == "error"
    finally:
        srv.stop()
    assert "Prüfsumme" in updater.info()["error"]
    assert (app / "REKORD").read_text() == "old" and not started


def test_no_update_during_a_recording(installed, monkeypatch):
    from rekord import live
    srv = _github({"REKORD-9.9.9-Linux-x86_64.tar.gz": _tarball()})
    monkeypatch.setenv("REKORD_UPDATE_URL", srv.url + "/release")
    monkeypatch.setattr(live, "active", lambda: [{"id": "rec"}])
    try:
        updater.check(force=True)
        with pytest.raises(RuntimeError, match="Aufnahme"):
            updater.install()
    finally:
        srv.stop()


def test_appimage_is_replaced_in_place(tmp_path, monkeypatch):
    img = tmp_path / "Apps" / "REKORD.AppImage"
    img.parent.mkdir()
    img.write_bytes(b"old")
    monkeypatch.setattr(system, "frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "mnt" / "usr/lib/rekord/REKORD"))
    monkeypatch.setenv("APPIMAGE", str(img))
    started = []
    monkeypatch.setattr(updater, "_relaunch", lambda cmd: started.append(cmd))
    srv = _github({"REKORD-9.9.9-x86_64.AppImage": b"new-appimage"})
    monkeypatch.setenv("REKORD_UPDATE_URL", srv.url + "/release")
    try:
        assert updater.install_kind() == "appimage"
        updater.check(force=True)
        updater.install()
        assert _wait_state("restarting", "error") == "restarting", updater.info()["error"]
    finally:
        srv.stop()
    assert img.read_bytes() == b"new-appimage" and os.access(img, os.X_OK)
    assert _wait_for(lambda: started) and started == [[str(img)]]


def test_windows_swap_script(tmp_path, monkeypatch):
    """Windows can't replace a running .exe: the script waits for REKORD to quit, swaps, restarts – or restarts
    the old one if a file is still in use."""
    root = tmp_path / "Programs" / "REKORD"
    root.mkdir(parents=True)
    work = root.parent / updater.WORK
    work.mkdir()
    z = work / "REKORD-Windows-x64.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("REKORD/REKORD.exe", b"MZ")
    monkeypatch.setattr(sys, "argv", ["REKORD.exe", "--background"])
    cmd = updater._apply_windows(z, root, work, "9.9.9")
    assert cmd[0] == "powershell.exe" and cmd[-1] == str(work / "swap.ps1")
    ps = (work / "swap.ps1").read_text("utf-8-sig")
    assert f"Wait-Process -Id {os.getpid()}" in ps
    assert "Stop-Process" in ps and "Move-Item -LiteralPath $dir -Destination $old" in ps
    assert "Move-Item -LiteralPath $old -Destination $dir" in ps  # roll back if the new one can't move in
    assert ps.count("Retry {") == 3  # locked files (virus scanner) get 20 s
    assert "Start-Process -FilePath (Join-Path $dir 'REKORD.exe')" in ps and "'--background'" in ps
    assert (work / "new" / "REKORD" / "REKORD.exe").exists()


def test_failed_windows_swap_is_reported(tmp_path, monkeypatch, installed):
    app, _ = installed
    work = app.parent / updater.WORK
    work.mkdir()
    (work / "swap.log").write_text("Windows hat REKORD-Dateien noch benutzt.", "utf-8")
    updater.cleanup()
    u = updater.info()
    assert u["state"] == "error" and "noch benutzt" in u["error"] and not work.exists()


# ------------------------------------------------------------------ old copies hand over to the newest one

def test_old_copy_starts_the_newest_installed(tmp_path, monkeypatch, installed):
    app, _ = installed
    monkeypatch.setattr(config, "pointer_path", lambda: tmp_path / "cfg" / "location.json")
    monkeypatch.setattr(system, "autostart_enabled", lambda: False)
    updater.remember_install()
    assert updater.registered() == {"version": __version__, "exe": str(app / "REKORD")}
    newest = tmp_path / "elsewhere" / "REKORD"
    newest.parent.mkdir()
    newest.write_text("newest")
    (tmp_path / "cfg" / "app.json").write_text(json.dumps({"version": "9.9.9", "exe": str(newest)}))
    updater.remember_install()  # an older one doesn't overwrite the newest
    assert updater.registered()["exe"] == str(newest)
    spawned = []

    class Popen:
        def __init__(self, cmd, **kw):
            spawned.append(cmd)
    monkeypatch.setattr(updater.subprocess, "Popen", Popen)
    assert updater.hand_over_to_newest(["--background"]) is True
    assert spawned == [[str(newest), "--background"]]
    newest.unlink()  # newest removed → no hand-over, this one runs
    assert updater.hand_over_to_newest([]) is False


def test_autostart_follows_the_newest(tmp_path, monkeypatch, installed):
    monkeypatch.setattr(config, "pointer_path", lambda: tmp_path / "cfg" / "location.json")
    calls = []
    monkeypatch.setattr(system, "autostart_enabled", lambda: True)
    monkeypatch.setattr(system, "set_autostart", lambda on: calls.append(on))
    updater.remember_install()
    assert calls == [True]


# ------------------------------------------------------------------ one REKORD at a time (desktop start)

def _hub(version, live=(), window=False, shutdown_code=200):
    srv = _Server({})
    focus = []

    def shutdown():
        if shutdown_code == 200:
            threading.Timer(0.2, srv.stop).start()
        return shutdown_code, {"ok": shutdown_code == 200}

    def status():
        return 200, {"version": version, "live": list(srv.live), "window": window, "exe": ""}

    def do_focus():
        focus.append(1)
        return 200, {"ok": True}
    srv.live = list(live)
    srv.routes.update({("GET", "/api/status"): (200, status), ("POST", "/api/shutdown"): (200, shutdown),
                       ("POST", "/api/window/focus"): (200, do_focus)})
    srv.focus = focus
    return srv


def test_second_start_brings_the_window_to_the_front(monkeypatch):
    hub = _hub(__version__, window=True)
    opened = []
    monkeypatch.setattr(desktop, "_window", lambda *a, **k: opened.append(k))
    try:
        desktop._show("http://x", hub.port, desktop._status(hub.port))
    finally:
        hub.stop()
    assert hub.focus == [1] and opened == []  # no second window


def test_hub_without_window_gets_one(monkeypatch):
    hub = _hub(__version__, window=False)
    opened = []
    monkeypatch.setattr(desktop, "_window", lambda *a, **k: opened.append(k))
    try:
        desktop._show("http://x", hub.port, desktop._status(hub.port))
    finally:
        hub.stop()
    assert hub.focus == [] and opened and opened[0]["own_hub"] is False


def test_newer_version_takes_over_from_an_old_one():
    hub = _hub("1.0.0")
    assert desktop._take_over(hub.port) is True
    assert desktop._status(hub.port) is None and not desktop._port_open(hub.port)


def test_an_old_version_that_records_is_never_cut_off(monkeypatch):
    hub = _hub("1.0.0", live=[{"id": "r1"}], shutdown_code=409)
    started = []
    monkeypatch.setattr(desktop, "_start_hub", lambda host, port: started.append(port))
    real_sleep = time.sleep
    monkeypatch.setattr(desktop.time, "sleep", lambda s: real_sleep(0.05 if s == 3 else s))  # the watcher looks every 3 s
    try:
        assert desktop._take_over(hub.port) is False
        polls = []

        def status():  # the recording ends after a few looks
            polls.append(1)
            if len(polls) > 2:
                hub.live.clear()
                hub.routes[("POST", "/api/shutdown")] = (200, lambda: (threading.Timer(0.2, hub.stop).start(), (200, {}))[1])
            return 200, {"version": "1.0.0", "live": list(hub.live), "window": False, "exe": ""}
        hub.routes[("GET", "/api/status")] = (200, status)
        desktop._watch(hub.port, "127.0.0.1", take_over=True)
    finally:
        try:
            hub.stop()
        except Exception:  # noqa: BLE001
            pass
    assert started == [hub.port] and len(polls) >= 3


def _start(port, home, version=None, timeout=60):
    env = dict(os.environ, REKORD_HOME=str(home), REKORD_HEADLESS="1", REKORD_UPDATE_URL="http://127.0.0.1:9/none")
    env.pop("REKORD_TEST_VERSION", None)
    if version:
        env["REKORD_TEST_VERSION"] = version
    code = f"import sys; sys.path.insert(0, {str(ROOT)!r}); from rekord.desktop import run; run({port}, background=True)"
    return subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_version(port, want, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = desktop._status(port)
        if st and st["version"] == want:
            return True
        time.sleep(0.3)
    return False


def test_real_hubs_never_run_twice(tmp_path):
    """Real processes: an old REKORD runs, the new one starts → the old one quits, the new one serves.
    Starting it again, or starting the old one again, doesn't add a second REKORD."""
    port = _free_port()
    old = _start(port, tmp_path / "home", version="1.0.0")
    procs = [old]
    try:
        assert _wait_version(port, "1.0.0"), "old hub did not start"
        new = _start(port, tmp_path / "home")
        procs.append(new)
        assert _wait_version(port, __version__), "new version did not take over"
        assert old.wait(timeout=30) == 0  # the old one quit by itself
        again = _start(port, tmp_path / "home")
        procs.append(again)
        assert again.wait(timeout=30) == 0  # same version runs → nothing new
        stale = _start(port, tmp_path / "home", version="1.0.0")
        procs.append(stale)
        assert stale.wait(timeout=30) == 0  # an older one leaves the newer one alone
        assert new.poll() is None and desktop._status(port)["version"] == __version__
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
                p.wait()


def test_starts_without_a_console(tmp_path):
    """Double-click on Windows: the app has no console (stdout/stderr are None). The web server used to crash
    setting up its logs – the hub must come up anyway and write its output to rekord.log."""
    port = _free_port()
    env = dict(os.environ, REKORD_HOME=str(tmp_path / "home"), REKORD_UPDATE_URL="http://127.0.0.1:9/none",
               HOME=str(tmp_path), USERPROFILE=str(tmp_path), APPDATA=str(tmp_path / "appdata"),
               XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    env.pop("REKORD_TEST_VERSION", None)
    code = (f"import sys; sys.path.insert(0, {str(ROOT)!r}); sys.stdout = None; sys.stderr = None\n"
            f"from rekord.desktop import run; run({port}, background=True)")
    p = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert _wait_version(port, __version__), "hub did not come up without a console"
        assert list(tmp_path.rglob("rekord.log")), "no log file"
    finally:
        p.kill()
        p.wait()
