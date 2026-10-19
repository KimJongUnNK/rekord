"""Ollama, managed from inside REKORD: install, start, download models with progress - no terminal needed.

One click ("Lokal einrichten") = setup(): install Ollama if missing → start it → download a model that
fits this computer's RAM → select it. Every step reports progress via setup_state()/pulls()."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from pathlib import Path

import httpx

from .. import system

# what we offer for one-click download (Ollama library tags), smallest first
RECOMMENDED = [
    {"name": "qwen3:1.7b", "size_gb": 1.4, "ram_gb": 4, "note": "Für ältere oder schwache Rechner"},
    {"name": "qwen3:4b", "size_gb": 2.6, "ram_gb": 8, "note": "Schnell, für die meisten Laptops"},
    {"name": "qwen3:8b", "size_gb": 5.2, "ram_gb": 16, "note": "Empfohlen: gute Protokolle, Deutsch top"},
    {"name": "gemma3:12b", "size_gb": 8.1, "ram_gb": 24, "note": "Sehr gute Qualität"},
    {"name": "qwen3:14b", "size_gb": 9.3, "ram_gb": 32, "note": "Beste Qualität, braucht viel RAM"},
]
# preferred when several models are already installed (quality per second on a normal computer)
PREFERRED = ["qwen3:8b", "qwen3:14b", "gemma3:12b", "qwen3:4b", "gemma3:4b", "qwen3:1.7b"]
DOWNLOAD_BASES = ("https://ollama.com/download", "https://github.com/ollama/ollama/releases/latest/download")


def _bases() -> tuple[str, ...]:
    mirror = os.environ.get("REKORD_OLLAMA_DOWNLOAD")  # tests / company mirrors
    return (mirror.rstrip("/"),) if mirror else DOWNLOAD_BASES

_pulls: dict[str, dict] = {}
_setup: dict = {"state": "idle", "step": "", "done": 0, "total": 0, "error": "", "model": ""}
_lock = threading.Lock()


def _base(base_url: str | None) -> str:
    return (base_url or "http://localhost:11434").rstrip("/")


def user_dir() -> Path:
    """Linux: REKORD installs Ollama here (no root needed)."""
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "rekord" / "ollama"


def binary() -> str | None:
    """Where the Ollama program is (the app bundle on macOS, ollama(.exe) elsewhere)."""
    if sys.platform == "darwin":
        for app in ("/Applications/Ollama.app", str(Path.home() / "Applications/Ollama.app")):
            if Path(app).exists():
                return app
    found = shutil.which("ollama")
    if found:
        return found
    if sys.platform == "win32":
        p = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
        if p.exists():
            return str(p)
    for p in (str(user_dir() / "bin/ollama"), "/usr/local/bin/ollama", "/usr/bin/ollama", "/opt/homebrew/bin/ollama"):
        if Path(p).exists():
            return p
    return None


def ram_gb() -> float:
    return system.ram_gb()


def recommended_for(ram: float | None = None) -> str:
    """The model we download by default: good quality, still fast on this much memory."""
    ram = ram_gb() if ram is None else ram
    return "qwen3:8b" if ram >= 14 else "qwen3:4b" if ram >= 7 else "qwen3:1.7b"


def pick_installed(models: list[dict], ram: float | None = None) -> str | None:
    """Best already-downloaded chat model (no embedding models), or None."""
    ram = ram_gb() if ram is None else ram
    chat = [m for m in models if "embed" not in m["name"].lower()]
    names = {m["name"] for m in chat} | {m["name"].removesuffix(":latest") for m in chat}
    for want in PREFERRED:
        if want in names:
            return next(m["name"] for m in chat if m["name"] in (want, want + ":latest"))
    fitting = [m for m in chat if m.get("size_gb", 0) <= ram * 0.6] or chat
    return max(fitting, key=lambda m: m.get("size_gb", 0))["name"] if fitting else None


def status(base_url: str | None = None) -> dict:
    base = _base(base_url)
    ram = ram_gb()
    out = {"installed": binary() is not None, "running": False, "version": "", "models": [],
           "recommended": RECOMMENDED, "default": recommended_for(ram), "ram_gb": ram, "pulls": pulls(),
           "setup": setup_state(), "can_install": _asset() is not None, "download_url": "https://ollama.com/download"}
    try:
        v = httpx.get(f"{base}/api/version", timeout=2).json()
        out["running"], out["installed"] = True, True
        out["version"] = v.get("version", "")
        tags = httpx.get(f"{base}/api/tags", timeout=5).json().get("models", [])
        out["models"] = [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)} for m in tags]
    except (httpx.HTTPError, ValueError):
        pass
    return out


def _running(base_url: str | None) -> bool:
    try:
        return httpx.get(f"{_base(base_url)}/api/version", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def start(base_url: str | None = None, wait: float = 20) -> bool:
    """Start Ollama if it is installed but not running. Returns True once it answers."""
    if _running(base_url):
        return True
    b = binary()
    if not b:
        return False
    env = system.child_env()
    if b.endswith(".app"):
        subprocess.Popen(["open", "-g", "-a", b, "--args", "hidden"], env=env)  # menu bar app, no window
    else:
        subprocess.Popen([b, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **system.hidden())
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(0.5)
        if _running(base_url):
            return True
    return False


# ------------------------------------------------------------------ install Ollama itself

def _asset() -> str | None:
    if sys.platform == "darwin":
        return "Ollama-darwin.zip"
    if sys.platform == "win32":
        return "OllamaSetup.exe"
    if sys.platform.startswith("linux"):
        arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
        return f"ollama-linux-{arch}.tar.zst" if arch else None
    return None


def _download(name: str, dest: Path, progress) -> Path:
    from ..models import _ssl_context
    errors = []
    for base in _bases():
        url = f"{base}/{name}"
        try:
            with httpx.stream("GET", url, follow_redirects=True, verify=_ssl_context(),
                              timeout=httpx.Timeout(60, connect=20), headers={"User-Agent": "rekord"}) as r:
                r.raise_for_status()
                total, done = int(r.headers.get("content-length") or 0), 0
                out = dest / name
                with open(out, "wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        progress(done, total)
                return out
        except httpx.HTTPError as e:
            errors.append(f"{url}: {e}")
    raise RuntimeError("Ollama-Download fehlgeschlagen – Internet prüfen. " + " · ".join(errors)[:300])


def _install_mac(archive: Path) -> None:
    root = Path("/Applications") if os.access("/Applications", os.W_OK) else Path.home() / "Applications"
    root.mkdir(exist_ok=True)
    shutil.rmtree(root / "Ollama.app", ignore_errors=True)
    # ditto keeps the code signature intact (symlinks, permissions) – Python's zipfile would not
    subprocess.run(["ditto", "-x", "-k", str(archive), str(root)], check=True, capture_output=True)


def _install_windows(setup_exe: Path) -> None:
    marker = Path(os.environ.get("LOCALAPPDATA", "")) / "Ollama" / "upgraded"  # tells the Ollama app to start hidden
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    # no pipes: the installer starts the Ollama app at the end, which would keep them open forever
    r = subprocess.run([str(setup_exe), "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800, **system.hidden())
    if r.returncode != 0:
        raise RuntimeError(f"Ollama-Installation fehlgeschlagen (Code {r.returncode})")


def _install_linux(archive: Path) -> None:
    dest = user_dir()
    tmp = dest.with_name("ollama.new")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        import zstandard
        with open(archive, "rb") as f, zstandard.ZstdDecompressor().stream_reader(f) as zr, \
                tarfile.open(fileobj=zr, mode="r|") as t:
            try:
                t.extractall(tmp, filter="data")
            except TypeError:  # Python without tarfile filters
                t.extractall(tmp)  # noqa: S202 - official Ollama archive over HTTPS
    except ImportError:
        if not shutil.which("zstd"):
            raise RuntimeError("Zum Entpacken fehlt zstd (z. B. sudo apt install zstd)") from None
        subprocess.run(["tar", "-I", "zstd", "-xf", str(archive), "-C", str(tmp)], check=True, env=system.child_env())
    if not (tmp / "bin/ollama").exists():
        raise RuntimeError("Unerwarteter Inhalt im Ollama-Paket")
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)


def install(progress=lambda done, total: None) -> None:
    """Download the official Ollama for this system and install it for the current user."""
    name = _asset()
    if not name:
        raise RuntimeError("Für dieses System gibt es kein Ollama-Paket")
    work = Path(tempfile.mkdtemp(prefix="rekord-ollama-"))
    try:
        archive = _download(name, work, progress)
        {"darwin": _install_mac, "win32": _install_windows}.get(sys.platform, _install_linux)(archive)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if not binary():
        raise RuntimeError("Ollama wurde installiert, ist aber nicht auffindbar")


# ------------------------------------------------------------------ models

def pulls() -> dict:
    with _lock:
        return {k: dict(v) for k, v in _pulls.items()}


def _pull_blocking(model: str, base_url: str | None) -> None:
    with _lock:
        _pulls[model] = {"state": "downloading", "done": 0, "total": 0, "status": "startet …", "error": ""}
    try:
        if not start(base_url):
            raise RuntimeError("Ollama ist nicht installiert oder startet nicht")
        with httpx.stream("POST", f"{_base(base_url)}/api/pull", json={"model": model, "stream": True},
                          timeout=httpx.Timeout(None, connect=10)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                d = json.loads(line)
                if d.get("error"):
                    raise RuntimeError(d["error"])
                with _lock:
                    p = _pulls[model]
                    p["status"] = d.get("status", "")
                    if d.get("total"):
                        p["total"], p["done"] = d["total"], d.get("completed", 0)
        with _lock:
            _pulls[model].update(state="done", status="fertig")
    except Exception as e:
        with _lock:
            _pulls[model].update(state="error", error=str(e))
        raise


def pull(model: str, base_url: str | None = None, on_done=None) -> None:
    """Download a model in the background; progress via pulls()."""
    with _lock:
        if _pulls.get(model, {}).get("state") == "downloading":
            return

    def run():
        try:
            _pull_blocking(model, base_url)
        except Exception:  # noqa: BLE001 - reported to the UI via pulls()
            return
        if on_done:
            on_done(model)

    threading.Thread(target=run, daemon=True, name=f"ollama-pull-{model}").start()


# ------------------------------------------------------------------ the one-click chain

def setup_state() -> dict:
    with _lock:
        return dict(_setup)


def _set(**kw) -> None:
    with _lock:
        _setup.update(kw)


def setup(base_url: str | None = None, model: str | None = None, on_ready=None) -> bool:
    """Install → start → download → select, in the background. False if a setup is already running."""
    with _lock:
        if _setup["state"] in ("installing", "starting", "pulling"):
            return False
        _setup.update(state="starting", step="Prüfe Ollama …", done=0, total=0, error="", model=model or "")

    def run():
        try:
            if not binary() and not _running(base_url):
                _set(state="installing", step="Ollama wird heruntergeladen …")
                install(lambda d, t: _set(done=d, total=t))
                _set(step="Ollama wird installiert …", done=0, total=0)
                for _ in range(40 if sys.platform == "win32" else 0):  # the Windows installer starts Ollama itself
                    if _running(base_url):
                        break
                    time.sleep(0.5)
            _set(state="starting", step="Ollama startet …")
            if not start(base_url, wait=60):
                raise RuntimeError("Ollama startet nicht. Einmal den Computer neu starten und nochmal versuchen.")
            have = status(base_url)["models"]
            chosen = model or pick_installed(have) or recommended_for()
            if chosen not in {m["name"] for m in have} | {m["name"].removesuffix(":latest") for m in have}:
                _set(state="pulling", step=f"Lade {chosen} …", model=chosen)
                _pull_blocking(chosen, base_url)
            if on_ready:
                on_ready(chosen)
            _set(state="done", step="Fertig – lokale KI ist bereit.", model=chosen)
        except Exception as e:  # noqa: BLE001 - shown in the UI
            _set(state="error", error=str(e))

    threading.Thread(target=run, daemon=True, name="ollama-setup").start()
    return True
