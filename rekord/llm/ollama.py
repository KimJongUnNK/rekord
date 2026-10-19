"""Ollama, managed from inside REKORD: detect, start, download models with progress - no terminal needed."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

# what we offer for one-click download (Ollama library tags), smallest first
RECOMMENDED = [
    {"name": "qwen3:4b", "size_gb": 2.6, "ram_gb": 8, "note": "Schnell, für die meisten Laptops"},
    {"name": "qwen3:8b", "size_gb": 5.2, "ram_gb": 16, "note": "Empfohlen: gute Protokolle, Deutsch top"},
    {"name": "gemma3:12b", "size_gb": 8.1, "ram_gb": 24, "note": "Sehr gute Qualität"},
    {"name": "qwen3:14b", "size_gb": 9.3, "ram_gb": 32, "note": "Beste Qualität, braucht viel RAM"},
]

_pulls: dict[str, dict] = {}
_lock = threading.Lock()


def _base(base_url: str | None) -> str:
    return (base_url or "http://localhost:11434").rstrip("/")


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
    for p in ("/usr/local/bin/ollama", "/usr/bin/ollama", "/opt/homebrew/bin/ollama"):
        if Path(p).exists():
            return p
    return None


def status(base_url: str | None = None) -> dict:
    base = _base(base_url)
    out = {"installed": binary() is not None, "running": False, "version": "", "models": [],
           "recommended": RECOMMENDED, "pulls": pulls(), "download_url": "https://ollama.com/download"}
    try:
        v = httpx.get(f"{base}/api/version", timeout=2).json()
        out["running"], out["installed"] = True, True
        out["version"] = v.get("version", "")
        tags = httpx.get(f"{base}/api/tags", timeout=5).json().get("models", [])
        out["models"] = [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)} for m in tags]
    except (httpx.HTTPError, ValueError):
        pass
    return out


def start(base_url: str | None = None) -> bool:
    """Start Ollama if it is installed but not running. Returns True once it answers."""
    if status(base_url)["running"]:
        return True
    b = binary()
    if not b:
        return False
    env = {k: v for k, v in os.environ.items() if k not in ("LD_LIBRARY_PATH",)}
    if "LD_LIBRARY_PATH_ORIG" in os.environ:  # packaged Linux app: give Ollama the system libraries
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH_ORIG"]
    if b.endswith(".app"):
        subprocess.Popen(["open", "-a", b], env=env)
    else:
        flags = {"creationflags": 0x08000000} if sys.platform == "win32" else {"start_new_session": True}  # no console window
        subprocess.Popen([b, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
    for _ in range(40):
        time.sleep(0.5)
        if status(base_url)["running"]:
            return True
    return False


def pulls() -> dict:
    with _lock:
        return {k: dict(v) for k, v in _pulls.items()}


def pull(model: str, base_url: str | None = None, on_done=None) -> None:
    """Download a model in the background; progress via pulls()."""
    with _lock:
        if _pulls.get(model, {}).get("state") == "downloading":
            return
        _pulls[model] = {"state": "downloading", "done": 0, "total": 0, "status": "startet …", "error": ""}

    def run():
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
            if on_done:
                on_done(model)
        except Exception as e:  # noqa: BLE001 - reported to the UI
            with _lock:
                _pulls[model].update(state="error", error=str(e))

    threading.Thread(target=run, daemon=True, name=f"ollama-pull-{model}").start()
