"""Ollama, managed from inside REKORD: install, start, download models with progress - no terminal needed.

One click ("Lokal einrichten") = setup(): install Ollama if missing → start it → download a model that
fits this computer's RAM → select it. Every step reports progress via setup_state()/pulls()."""
from __future__ import annotations

import functools
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

# what we offer for one-click download (Ollama library tags), smallest first. ram_gb: memory the computer
# needs so the model runs comfortably next to REKORD's speech models.
RECOMMENDED = [
    {"name": "qwen3:1.7b", "size_gb": 1.4, "ram_gb": 4, "note": "Für ältere oder schwache Rechner"},
    {"name": "qwen3:4b", "size_gb": 2.5, "ram_gb": 8, "note": "Schnell, für die meisten Laptops"},
    {"name": "qwen3:8b", "size_gb": 5.2, "ram_gb": 14, "note": "Gute Protokolle, Deutsch top"},
    {"name": "gemma3:12b", "size_gb": 8.1, "ram_gb": 20, "note": "Sehr gute Qualität, stark in Deutsch"},
    {"name": "qwen3:14b", "size_gb": 9.3, "ram_gb": 24, "note": "Sehr gute Qualität"},
    {"name": "qwen3:30b", "size_gb": 19.0, "ram_gb": 32, "note": "Top-Qualität und trotzdem flott (rechnet nur mit einem Teil des Modells)"},
    {"name": "qwen3:32b", "size_gb": 20.0, "ram_gb": 48, "note": "Maximale Qualität, aber langsam"},
]
CATALOG = {m["name"]: m for m in RECOMMENDED}
# the automatic choice, best first: the first one this computer can run well wins
BEST_ORDER = ["qwen3:30b", "qwen3:14b", "gemma3:12b", "qwen3:8b", "qwen3:4b", "qwen3:1.7b"]
# dense mid-size models crawl without a graphics chip; the 30b one only computes ~3b per word, so CPUs manage it
NEEDS_GPU = {"qwen3:14b", "gemma3:12b", "qwen3:32b"}
# preferred when several models are already installed (quality per second on a normal computer)
PREFERRED = ["qwen3:30b", "qwen3:14b", "gemma3:12b", "qwen3:8b", "qwen3:4b", "gemma3:4b", "qwen3:1.7b"]
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


@functools.lru_cache(maxsize=1)
def hardware() -> dict:
    """What this computer has for local AI: memory and a graphics chip that speeds models up."""
    ram = ram_gb()
    hw = {"ram_gb": ram, "gpu": None, "vram_gb": 0.0}
    if sys.platform == "darwin" and platform.machine() == "arm64":
        hw.update(gpu="apple", vram_gb=round(ram * 0.7, 1))  # Apple chips share the memory with the graphics part
    elif shutil.which("nvidia-smi"):
        r = system.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], timeout=10)
        try:
            vram = max(float(x) for x in r.stdout.split()) / 1024
            if vram >= 4:
                hw.update(gpu="nvidia", vram_gb=round(vram, 1))
        except ValueError:
            pass
    hw["label"] = (f"{ram:.0f} GB RAM" + (" · Apple-Chip" if hw["gpu"] == "apple" else
                   f" · NVIDIA-Grafik {hw['vram_gb']:.0f} GB" if hw["gpu"] == "nvidia" else " · ohne Grafikchip"))
    return hw


def _runs_well(name: str, hw: dict) -> bool:
    m = CATALOG[name]
    if hw["ram_gb"] < m["ram_gb"] * 0.95:  # "16 GB" machines report a bit less
        return False
    if name in NEEDS_GPU and not (hw["gpu"] == "apple" or (hw["gpu"] == "nvidia" and hw["vram_gb"] >= m["size_gb"] * 1.1)):
        return False
    return True


def recommended_for(ram: float | None = None, hw: dict | None = None) -> str:
    """The best model this computer runs well: as good as possible, still fast enough for a protocol."""
    if hw is None:
        hw = dict(hardware()) if ram is None else {"ram_gb": ram, "gpu": "apple", "vram_gb": ram * 0.7}
    return next((n for n in BEST_ORDER if _runs_well(n, hw)), "qwen3:1.7b")


def pick_installed(models: list[dict], ram: float | None = None) -> str | None:
    """Best already-downloaded chat model (no embedding models), or None."""
    ram = ram_gb() if ram is None else ram
    chat = [m for m in models if "embed" not in m["name"].lower()]
    fits = lambda m: m.get("size_gb", 0) <= ram * 0.6  # noqa: E731
    names = {m["name"]: m for m in chat} | {m["name"].removesuffix(":latest"): m for m in chat}
    for want in PREFERRED:
        if want in names and fits(names[want]):
            return names[want]["name"]
    fitting = [m for m in chat if fits(m)] or chat
    return max(fitting, key=lambda m: m.get("size_gb", 0))["name"] if fitting else None


def status(base_url: str | None = None) -> dict:
    base = _base(base_url)
    ram = ram_gb()
    hw = hardware()
    best = recommended_for(hw=hw)
    out = {"installed": binary() is not None, "running": False, "version": "", "models": [],
           "recommended": [{**m, "fits": _runs_well(m["name"], hw), "best": m["name"] == best} for m in RECOMMENDED],
           "default": best, "best": best, "hardware": hw, "ram_gb": ram, "pulls": pulls(),
           "setup": setup_state(), "can_install": _asset() is not None, "download_url": "https://ollama.com/download",
           "service": system_service()}
    try:
        v = httpx.get(f"{base}/api/version", timeout=2).json()
        out["running"], out["installed"] = True, True
        out["version"] = v.get("version", "")
        tags = httpx.get(f"{base}/api/tags", timeout=5).json().get("models", [])
        out["models"] = [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1),
                          "fits": m.get("size", 0) / 1e9 <= ram * 0.6} for m in tags]
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
    from .. import config
    if config.models_missing():
        raise RuntimeError(f"Das Laufwerk mit den KI-Modellen fehlt ({config.MODELS_DIR}). Bitte anschließen.")
    env = system.child_env()
    if (d := config.ollama_models_dir()) is not None:  # models on the chosen drive/folder
        d.mkdir(parents=True, exist_ok=True)
        env["OLLAMA_MODELS"] = str(d)
    # half the memory for the context window (8-bit cache, needs flash attention) – unless you set it yourself
    env.setdefault("OLLAMA_FLASH_ATTENTION", "1")
    env.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
    # macOS: the server inside the app bundle, not the menu bar app – on its first start the app asks for an admin
    # password (CLI symlink) and only then starts serving
    exe = str(Path(b) / "Contents/Resources/ollama") if b.endswith(".app") else b
    subprocess.Popen([exe, "serve"], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **system.hidden())
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(0.5)
        if _running(base_url):
            return True
    return False


def stop() -> None:
    """End a running Ollama (ours or the user's app) – e.g. before its models move to another drive."""
    if sys.platform == "win32":
        for exe in ("ollama app.exe", "ollama.exe"):
            system._run(["taskkill", "/F", "/IM", exe])
    else:
        if sys.platform == "darwin":
            system._run(["osascript", "-e", 'tell application "Ollama" to quit'])
        system._run(["pkill", "-f", "ollama serve"])
        system._run(["pkill", "-x", "ollama"])
    for _ in range(20):
        if not _running(None):
            return
        time.sleep(0.5)


def apply_models_dir(base_url: str | None = None) -> None:
    """Make every way Ollama starts use the chosen models folder, then restart it if it was running."""
    from .. import config
    d = config.ollama_models_dir()
    if sys.platform == "win32":  # the Ollama tray app reads the user environment
        if d is not None:
            system._run(["setx", "OLLAMA_MODELS", str(d)])
        else:
            system._run(["reg", "delete", r"HKCU\Environment", "/v", "OLLAMA_MODELS", "/f"])
    elif sys.platform == "darwin":  # GUI apps started later in this login session
        system._run(["launchctl", "setenv", "OLLAMA_MODELS", str(d)] if d is not None else ["launchctl", "unsetenv", "OLLAMA_MODELS"])
    if _running(base_url):
        stop()
        start(base_url)


def system_service() -> bool:
    """Linux: Ollama installed by its own script runs as a system service (as user "ollama") – our folder choice can't
    reach it; the UI explains how to set OLLAMA_MODELS there."""
    if not sys.platform.startswith("linux") or not shutil.which("systemctl"):
        return False
    r = system._run(["systemctl", "is-active", "ollama"])
    return bool(r and r.stdout.strip() == "active")


def delete(model: str, base_url: str | None = None) -> None:
    r = httpx.request("DELETE", f"{_base(base_url)}/api/delete", json={"model": model}, timeout=60)
    if r.status_code == 404:
        raise RuntimeError(f"{model} ist nicht (mehr) da.")
    r.raise_for_status()
    with _lock:
        _pulls.pop(model, None)


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
