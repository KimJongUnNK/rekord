"""Real updates: the new version replaces the installed one and restarts in its place – never two REKORDs.

- In-app update: the right file from the latest GitHub release is downloaded and swapped in where REKORD is
  installed (mac .app, Windows folder, AppImage, Linux user install; deb/rpm/pacman through the package manager,
  which asks for the password once). Then the new version starts and the old one quits.
- A newer REKORD that's started while an older one runs takes over (the old one quits, see desktop.run).
- An older copy that's started (old shortcut, a copy in Downloads …) hands over to the newest installed REKORD.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from . import __version__, config, system

log = logging.getLogger("rekord.updater")
REPO = "KimJongUnNK/rekord"
CHECK_EVERY = 6 * 3600
WORK = ".rekord-update"  # next to the installed app (same drive → the swap is a rename)
INSTALLER = "curl -fsSL https://github.com/KimJongUnNK/rekord/releases/latest/download/install.sh | sh"
INSTALLER_WIN = "irm https://github.com/KimJongUnNK/rekord/releases/latest/download/install.ps1 | iex"

_lock = threading.Lock()
_state: dict = {"state": "idle", "done": 0, "total": 0, "error": "", "latest": None, "checked": 0.0, "check_error": ""}
_just_updated = ""


# ------------------------------------------------------------------ versions

def version_tuple(v: str) -> tuple[int, ...]:
    out = []
    for part in str(v).strip().lstrip("vV").split("."):
        digits = ""
        for ch in part:
            if not ch.isdigit():
                break
            digits += ch
        out.append(int(digits or 0))
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return tuple(out)


def newer(a: str, b: str) -> bool:
    """Is version a newer than version b?"""
    return version_tuple(a) > version_tuple(b)


# ------------------------------------------------------------------ what is installed where

def _exe() -> Path:
    return Path(sys.executable).resolve()


def install_kind() -> str:
    """mac-app · windows · appimage · linux-user · deb · rpm · pacman · aur · source"""
    if not system.frozen():
        return "source"
    exe = _exe()
    if sys.platform == "darwin":
        return "mac-app" if exe.parent.name == "MacOS" and exe.parents[2].suffix == ".app" else "unknown"
    if sys.platform == "win32":
        return "windows"
    if os.environ.get("APPIMAGE"):
        return "appimage"
    if str(exe).startswith("/opt/rekord/"):
        return _package_owner(str(exe))
    return "linux-user"


@functools.lru_cache(maxsize=4)
def _package_owner(exe: str) -> str:
    """Which package manager installed /opt/rekord (asked once – the UI polls while an update runs)."""
    if Path("/var/lib/dpkg/info/rekord.list").exists():
        return "deb"
    if shutil.which("pacman"):
        r = system.run(["pacman", "-Qqo", exe], timeout=15)
        if r.returncode == 0:
            return "aur" if "rekord-bin" in r.stdout else "pacman"
    if shutil.which("rpm") and system.run(["rpm", "-qf", exe], timeout=15).returncode == 0:
        return "rpm"
    return "unknown"


def app_root(kind: str | None = None) -> Path | None:
    """What an update replaces: the .app bundle, the program folder or the AppImage file."""
    kind = kind or install_kind()
    exe = _exe()
    if kind == "mac-app":
        return exe.parents[2]
    if kind in ("windows", "linux-user", "deb", "rpm", "pacman", "aur"):
        return exe.parent
    if kind == "appimage":
        return Path(os.environ["APPIMAGE"]).resolve()
    return None


def asset_name(kind: str, v: str) -> str | None:
    return {"mac-app": "REKORD-macOS-AppleSilicon.zip", "windows": "REKORD-Windows-x64.zip",
            "appimage": f"REKORD-{v}-x86_64.AppImage", "linux-user": f"REKORD-{v}-Linux-x86_64.tar.gz",
            "deb": f"rekord_{v}_amd64.deb", "rpm": f"rekord-{v}-1.x86_64.rpm",
            "pacman": f"rekord-{v}-1-x86_64.pkg.tar.zst"}.get(kind)


def _manual(kind: str) -> str:
    if kind == "source":
        return "Aus dem Quellcode installiert: im REKORD-Ordner `git pull` und `pip install -e .`, dann REKORD neu starten."
    if kind == "aur":
        return "Über das AUR installiert: mit deinem AUR-Helfer aktualisieren, z. B. `yay -Syu rekord-bin`."
    if sys.platform == "win32":
        return f"In PowerShell: `{INSTALLER_WIN}`"
    return f"Im Terminal: `{INSTALLER}`"


def _can_install(kind: str, latest: dict | None) -> tuple[bool, str]:
    if kind in ("source", "aur", "unknown"):
        return False, _manual(kind)
    if "/AppTranslocation/" in str(_exe()):
        return False, "Zuerst REKORD in den Ordner Programme ziehen, von dort starten – dann geht das Update mit einem Klick."
    if latest and asset_name(kind, latest["version"]) not in latest["assets"]:
        return False, f"Für dieses System gibt es in Version {latest['version']} noch keine Datei. " + _manual(kind)
    if kind in ("deb", "rpm", "pacman"):
        if not shutil.which("pkexec") or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False, "Das Update braucht dein Passwort, aber hier gibt es keinen Passwort-Dialog. " + _manual(kind)
        return True, ""
    root = app_root(kind)
    if root is None or not os.access(root.parent, os.W_OK):
        return False, f"Kein Schreibrecht für {root.parent if root else '?'}. " + _manual(kind)
    return True, ""


# ------------------------------------------------------------------ check

def api_url() -> str:
    return os.environ.get("REKORD_UPDATE_URL") or f"https://api.github.com/repos/{REPO}/releases/latest"


def _set(**kw) -> None:
    with _lock:
        _state.update(kw)


def check(force: bool = False) -> dict:
    """Ask GitHub for the latest release (at most every 6 hours unless forced)."""
    with _lock:
        fresh = _state["latest"] is not None and time.time() - _state["checked"] < CHECK_EVERY
    if force or not fresh:
        import httpx

        from .models import _ssl_context
        try:
            r = httpx.get(api_url(), headers={"Accept": "application/vnd.github+json", "User-Agent": "rekord"},
                          timeout=15, follow_redirects=True, verify=_ssl_context())
            r.raise_for_status()
            d = r.json()
            latest = {"version": str(d["tag_name"]).lstrip("vV"), "notes": (d.get("body") or "")[:8000],
                      "page": d.get("html_url") or f"https://github.com/{REPO}/releases/latest",
                      "assets": {a["name"]: {"url": a["browser_download_url"], "size": int(a.get("size") or 0),
                                             "digest": a.get("digest") or ""} for a in d.get("assets") or []}}
            _set(latest=latest, checked=time.time(), check_error="")
        except Exception as e:  # noqa: BLE001 - offline, rate limit …
            _set(check_error=f"Keine Verbindung zu GitHub: {e}"[:300], checked=time.time())
    return info()


def info() -> dict:
    with _lock:
        st = dict(_state)
    latest, kind = st["latest"], install_kind()
    available = bool(latest) and newer(latest["version"], __version__)
    can, why = _can_install(kind, latest) if available else (False, "")
    return {"current": __version__, "latest": latest["version"] if latest else None, "available": available,
            "notes": latest["notes"] if latest and available else "", "page": latest["page"] if latest else "",
            "kind": kind, "can_install": can, "manual": why, "state": st["state"], "done": st["done"],
            "total": st["total"], "error": st["error"], "check_error": st["check_error"], "checked": st["checked"],
            "just_updated": _just_updated}


def brief() -> dict:
    """For /api/status (no network)."""
    with _lock:
        latest, state = _state["latest"], _state["state"]
    return {"available": bool(latest) and newer(latest["version"], __version__),
            "latest": latest["version"] if latest else None, "state": state, "just_updated": _just_updated}


def background_checks(stop: threading.Event) -> None:
    """Look for a new version shortly after the start and then every 6 hours (Einstellungen → Updates)."""
    if stop.wait(20):
        return
    while True:
        if config.load().get("update_check", True):
            check()
        if stop.wait(CHECK_EVERY):
            return


# ------------------------------------------------------------------ install

def install() -> None:
    """Download + swap in the background; progress via info(). Raises with a readable reason if it can't."""
    from . import live
    if live.active():
        raise RuntimeError("Gerade läuft eine Aufnahme – erst beenden, dann aktualisieren.")
    with _lock:
        if _state["state"] in ("downloading", "installing", "restarting"):
            return
    inf = info()
    if not inf["available"]:
        raise RuntimeError("REKORD ist schon auf dem neuesten Stand." if inf["latest"] else "Erst nach Updates suchen.")
    if not inf["can_install"]:
        raise RuntimeError(inf["manual"])
    with _lock:
        latest = _state["latest"]
    _set(state="downloading", done=0, total=0, error="")
    threading.Thread(target=_install, args=(inf["kind"], latest), daemon=True, name="update").start()


def _install(kind: str, latest: dict) -> None:
    try:
        v = latest["version"]
        asset = latest["assets"][asset_name(kind, v)]
        root = app_root(kind)
        if kind in ("deb", "rpm", "pacman"):
            work = Path(tempfile.mkdtemp(prefix="rekord-update-"))
            os.chmod(work, 0o755)  # the package manager runs as another user (apt: _apt) and must read the file
        else:
            work = root.parent / WORK
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True)
        file = _download(asset, work / asset_name(kind, v))
        _set(state="installing")
        cmd = APPLY[kind](file, root, work, v)
        (config.HOME / "updated.json").write_text(json.dumps({"from": __version__, "to": v}), "utf-8")
        _set(state="restarting")
        time.sleep(0.8)  # let the UI see "restarting"
        _relaunch(cmd)
    except Exception as e:  # noqa: BLE001
        log.exception("update failed")
        _set(state="error", error=str(e)[:500])


def _download(asset: dict, dest: Path) -> Path:
    import httpx

    from .models import _ssl_context
    _set(total=asset.get("size") or 0, done=0)
    h = hashlib.sha256()
    with httpx.stream("GET", asset["url"], follow_redirects=True, verify=_ssl_context(),
                      timeout=httpx.Timeout(60, connect=20), headers={"User-Agent": "rekord"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0) or asset.get("size") or 0
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                _set(done=done, total=total)
    if asset.get("size") and done != asset["size"]:
        raise RuntimeError(f"Download unvollständig ({done} von {asset['size']} Bytes) – nochmal versuchen.")
    digest = asset.get("digest") or ""
    if digest.startswith("sha256:") and digest[7:] != h.hexdigest():
        raise RuntimeError("Download beschädigt (Prüfsumme stimmt nicht) – nochmal versuchen.")
    return dest


def _swap(root: Path, new: Path, work: Path) -> None:
    """Old app aside (deleted at the next start), new app in its place – two renames on the same drive."""
    old = work / ("old" + root.suffix)
    os.rename(root, old)
    try:
        os.rename(new, root)
    except OSError:
        os.rename(old, root)
        raise


def _apply_mac(file: Path, root: Path, work: Path, v: str) -> list[str]:
    staging = work / "new"
    staging.mkdir()
    # ditto keeps the app's signature, symlinks and permissions intact – Python's zipfile would not
    r = system.run(["ditto", "-x", "-k", str(file), str(staging)], timeout=900)
    new = staging / "REKORD.app"
    if r.returncode != 0 or not (new / "Contents/MacOS/REKORD").exists():
        raise RuntimeError(f"Entpacken fehlgeschlagen: {r.stderr.strip()[:200]}")
    system.run(["xattr", "-dr", "com.apple.quarantine", str(new)], timeout=60)
    try:
        _swap(root, new, work)
    except PermissionError as e:
        raise RuntimeError("macOS hat das Ersetzen blockiert: Systemeinstellungen → Datenschutz & Sicherheit → "
                           "App-Verwaltung → REKORD erlauben, dann nochmal aktualisieren.") from e
    return [str(root / "Contents/MacOS/REKORD")]


def _apply_linux_user(file: Path, root: Path, work: Path, v: str) -> list[str]:
    staging = work / "new"
    staging.mkdir()
    with tarfile.open(file) as t:
        if hasattr(tarfile, "data_filter"):
            t.extractall(staging, filter="data")
        else:
            t.extractall(staging)  # noqa: S202 - our own release file, size/sha checked
    new = staging / f"rekord-{v}" / "rekord"
    if not (new / "REKORD").exists():
        raise RuntimeError("Download enthält kein REKORD – nochmal versuchen.")
    _swap(root, new, work)
    return [str(root / "REKORD")]


def _apply_appimage(file: Path, root: Path, work: Path, v: str) -> list[str]:
    os.chmod(file, 0o755)
    os.replace(file, root)  # the running AppImage keeps its (now unlinked) file
    return [str(root)]


def _apply_package(kind: str):
    def apply(file: Path, root: Path, work: Path, v: str) -> list[str]:
        os.chmod(file, 0o644)
        if kind == "deb":
            cmd = ["apt-get", "install", "-y", str(file)] if shutil.which("apt-get") else ["dpkg", "-i", str(file)]
        elif kind == "rpm":
            cmd = (["dnf", "install", "-y", str(file)] if shutil.which("dnf")
                   else ["zypper", "--non-interactive", "install", "--allow-unsigned-rpm", str(file)] if shutil.which("zypper")
                   else ["rpm", "-U", str(file)])
        else:
            cmd = ["pacman", "-U", "--noconfirm", str(file)]
        r = system.run(["pkexec", *cmd], timeout=1800)  # the system's password dialog
        shutil.rmtree(work, ignore_errors=True)
        if r.returncode in (126, 127):
            raise RuntimeError("Passwort-Abfrage abgebrochen – Update nicht installiert.")
        if r.returncode != 0:
            raise RuntimeError(f"Paket-Installation fehlgeschlagen: {(r.stderr or r.stdout).strip()[-300:]}")
        return [str(root / "REKORD")]
    return apply


def _apply_windows(file: Path, root: Path, work: Path, v: str) -> list[str]:
    """A running .exe can't be replaced: a small PowerShell script waits until REKORD has quit, swaps the
    folders, starts the new version – and starts the old one again if Windows still blocks a file."""
    staging = work / "new"
    with zipfile.ZipFile(file) as z:
        z.extractall(staging)
    new = staging / "REKORD"
    if not (new / "REKORD.exe").exists():
        raise RuntimeError("Download enthält kein REKORD.exe – nochmal versuchen.")
    args = " ".join(f"'{a}'" for a in _keep_args())
    q = lambda p: str(p).replace("'", "''")  # noqa: E731 - PowerShell single-quote escaping
    script = work / "swap.ps1"
    script.write_text(f"""$ErrorActionPreference = 'Continue'
$dir = '{q(root)}'; $new = '{q(new)}'; $old = '{q(work / "old")}'; $log = '{q(work / "swap.log")}'
try {{ Wait-Process -Id {os.getpid()} -Timeout 60 -ErrorAction SilentlyContinue }} catch {{}}
# every REKORD from this folder must be closed (also "REKORD mcp" for Claude Desktop) - files in use can't be moved
Get-Process REKORD -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like "$dir\\*" }} | Stop-Process -Force -ErrorAction SilentlyContinue
# files may stay locked for a moment (virus scanner, Explorer): try for up to 20 s
function Retry($block) {{ for ($i = 0; $i -lt 40; $i++) {{ try {{ & $block; return $true }} catch {{ Start-Sleep -Milliseconds 500 }} }}; return $false }}
if (Retry {{ Move-Item -LiteralPath $dir -Destination $old -ErrorAction Stop }}) {{
  if (-not (Retry {{ Move-Item -LiteralPath $new -Destination $dir -ErrorAction Stop }})) {{
    Retry {{ Move-Item -LiteralPath $old -Destination $dir -ErrorAction Stop }} | Out-Null
    "Der neue Ordner konnte nicht an seinen Platz." | Out-File -FilePath $log -Encoding utf8
  }}
}} else {{ "Windows hat REKORD-Dateien noch benutzt." | Out-File -FilePath $log -Encoding utf8 }}
$env:REKORD_RESTARTING = '1'
Start-Process -FilePath (Join-Path $dir 'REKORD.exe') -WorkingDirectory $env:USERPROFILE {('-ArgumentList ' + args) if args else ''}
""", "utf-8-sig")
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script)]


APPLY = {"mac-app": _apply_mac, "windows": _apply_windows, "appimage": _apply_appimage, "linux-user": _apply_linux_user,
         "deb": _apply_package("deb"), "rpm": _apply_package("rpm"), "pacman": _apply_package("pacman")}


def _keep_args() -> list[str]:
    return [a for a in sys.argv[1:] if a in ("--background", "--local")]


def _relaunch(cmd: list[str]) -> None:
    """Start the new version (it waits until our port is free), then quit."""
    env = system.child_env()
    env["REKORD_RESTARTING"] = "1"
    env.pop("REKORD_TEST_VERSION", None)
    if cmd[0].lower().startswith("powershell"):
        kw = {"creationflags": 0x08000000 | 0x00000200}  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP: outlives us
    else:
        kw = system.hidden()
        cmd = cmd + _keep_args()
    # never start inside the app folder: on Windows a process "sitting" in a folder keeps it from being swapped
    subprocess.Popen(cmd, env=env, cwd=str(Path.home()), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True, **kw)
    os._exit(0)


# ------------------------------------------------------------------ after the start of a (new) version

def cleanup() -> None:
    """Leftovers of the last update (old app version, download), did the swap work, and "updated to X" once."""
    global _just_updated
    with _lock:
        if _state["state"] in ("downloading", "installing", "restarting"):
            return  # an update is on its way right now – its files are not leftovers
    marker = config.HOME / "updated.json"
    try:
        d = json.loads(marker.read_text("utf-8"))
        if d.get("to") == __version__:
            _just_updated = d.get("from", "")
        marker.unlink()
    except (OSError, ValueError):
        pass
    root = app_root()
    if root is None:
        return
    work = root.parent / WORK
    if not work.exists():
        return
    try:
        msg = (work / "swap.log").read_text("utf-8-sig").strip()
        if msg:
            _set(state="error", error=f"Update nicht installiert: {msg} REKORD neu starten und nochmal versuchen.")
    except OSError:
        pass
    shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------ the newest installed REKORD (old copies hand over)

def _registry() -> Path:
    return config.pointer_path().parent / "app.json"


def registered() -> dict:
    try:
        return json.loads(_registry().read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def remember_install() -> None:
    """This is the newest REKORD on this computer: old copies, the Start menu and "start with the computer"
    point here from now on."""
    if not system.frozen():
        return
    reg = registered()
    exe = str(_exe())
    if reg.get("exe") and Path(reg["exe"]).exists() and newer(reg.get("version", "0"), __version__):
        return  # a newer one is installed elsewhere
    if reg.get("exe") != exe or reg.get("version") != __version__:
        try:
            _registry().parent.mkdir(parents=True, exist_ok=True)
            _registry().write_text(json.dumps({"version": __version__, "exe": exe}), "utf-8")
        except OSError:
            pass
    try:
        if system.autostart_enabled():
            system.set_autostart(True)  # "start with the computer" must start this version, not an old copy
    except Exception:  # noqa: BLE001
        pass


def hand_over_to_newest(args: list[str]) -> bool:
    """An older copy was started: start the newest installed REKORD instead. True = handed over, quit."""
    if not system.frozen():
        return False
    reg = registered()
    exe = reg.get("exe")
    if not exe or not newer(reg.get("version", "0"), __version__) or not Path(exe).exists():
        return False
    if Path(exe).resolve() == _exe():
        return False
    log.info("REKORD %s is installed at %s – starting that instead of %s", reg["version"], exe, __version__)
    subprocess.Popen([exe, *args], env=system.child_env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **system.hidden())
    return True
