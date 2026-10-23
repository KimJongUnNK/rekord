"""Paths and persistent settings. Everything lives in one folder (REKORD_HOME) – by default ~/Rekord, or wherever the
user chose (external drive, second SSD, NAS): that choice is kept in a small pointer file outside the folder."""
from __future__ import annotations

import json
import os
import secrets
import threading
from copy import deepcopy
from pathlib import Path

DEFAULT_HOME = Path.home() / "Rekord"


def pointer_path() -> Path:
    """Where the chosen data folder is remembered (must stay on the computer, not on the external drive)."""
    import sys
    if sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "REKORD" / "location.json"


def _home() -> tuple[Path, bool]:
    if os.environ.get("REKORD_HOME"):
        return Path(os.environ["REKORD_HOME"]).expanduser(), False
    try:
        chosen = json.loads(pointer_path().read_text("utf-8")).get("home")
        if chosen:
            return Path(chosen), True
    except (OSError, ValueError):
        pass
    return DEFAULT_HOME, False


HOME, CUSTOM_HOME = _home()
DATA = HOME
AUDIO_DIR = HOME / "audio"
MODELS_DIR = HOME / "models"
INBOX_DIR = HOME / "inbox"
DB_PATH = HOME / "rekord.db"
SETTINGS_PATH = HOME / "settings.json"

DEFAULTS: dict = {
    "language": "",  # "" = auto detect per segment
    "asr_engine": "sherpa",  # sherpa | faster-whisper
    "asr_model": "whisper-small",  # sherpa model id
    "faster_whisper_model": "large-v3-turbo",
    "faster_whisper_device": "auto",
    "embedding_model": "eres2net-base",
    "threads": max(1, min(8, (os.cpu_count() or 4))),
    # analyze with low priority and at most half the cores: the computer stays smooth meanwhile (off = faster)
    "gentle_processing": True,
    "num_speakers": 0,  # 0 = auto
    "cluster_threshold": 0.6,
    "profile_threshold": 0.55,
    "live_profile_threshold": 0.5,
    "live_cluster_threshold": 0.55,
    "live_transcribe": True,
    "vocabulary": [],  # list of {"from": "...", "to": "..."} corrections and hotwords
    "auto_summary": True,
    "default_template": "auto",
    "template_order": [],  # Vorlagen in the user's order of importance (ids); empty = built-in order
    "summary_language": "de",
    "llm": {
        "provider": "anthropic",  # anthropic | openai | ollama | compatible | none
        "anthropic": {"api_key": "", "model": "claude-opus-5-5", "effort": "medium", "fallbacks": True},
        "openai": {"api_key": "", "model": "", "base_url": ""},
        "ollama": {"base_url": "http://localhost:11434", "model": ""},
        "compatible": {"api_key": "", "model": "", "base_url": "http://localhost:1234/v1"},
    },
    "inbox_enabled": True,
    "pair_token": "",
    "devices": [],  # paired devices with their own key (only a hash is stored) – see pairing.py
    "models_dir": "",  # "" = <data folder>/models; otherwise e.g. an external drive (local AI models go into …/ollama)
    "storage_chosen": False,  # first start: no big download before the user picked where REKORD stores things
    "welcome_done": False,
    "update_check": True,  # look for a new REKORD version (GitHub releases) – installing always needs a click
    # the native window: chosen microphone, and who was there last time ("Wer ist dabei?" starts from that)
    "desktop": {"mic": "", "theme": "system", "accent": "#FF5A1F", "keep_awake": True,
                "who": {"meeting": "person", "ids": [], "total": 0}},
}

_lock = threading.RLock()
_cache: dict | None = None


class StorageMissing(RuntimeError):
    pass


def home_missing() -> bool:
    """The chosen folder is on a drive that isn't connected (never create it on the internal disk instead)."""
    return CUSTOM_HOME and not HOME.exists() and not HOME.parent.exists()


def models_missing() -> bool:
    return MODELS_DIR != HOME / "models" and not MODELS_DIR.exists() and not MODELS_DIR.parent.exists()


def ensure_dirs() -> None:
    if home_missing():
        raise StorageMissing(str(HOME))
    for d in (HOME, AUDIO_DIR, INBOX_DIR):
        d.mkdir(parents=True, exist_ok=True)
    if not models_missing():
        MODELS_DIR.mkdir(parents=True, exist_ok=True)


def ollama_models_dir() -> Path | None:
    """Local AI models (Ollama) follow a custom models folder; otherwise Ollama's own default."""
    return MODELS_DIR / "ollama" if MODELS_DIR != HOME / "models" else None


def _merge(base: dict, over: dict) -> dict:
    out = deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    global _cache
    with _lock:
        if _cache is not None:
            return deepcopy(_cache)
        if home_missing():  # drive unplugged: run on defaults, the UI asks to connect it (nothing gets written)
            _cache = _merge(DEFAULTS, {"pair_token": "-", "storage_chosen": True, "welcome_done": True})
            return deepcopy(_cache)
        existed = SETTINGS_PATH.exists()
        stored = {}
        if existed:
            try:
                stored = json.loads(SETTINGS_PATH.read_text("utf-8"))
            except json.JSONDecodeError:
                stored = {}
            # installed before storage choice / welcome existed: don't ask an existing user again
            stored.setdefault("storage_chosen", True)
            stored.setdefault("welcome_done", True)
        s = _merge(DEFAULTS, stored)
        _apply_models_dir(s)
        ensure_dirs()
        if not s.get("pair_token"):
            s["pair_token"] = secrets.token_urlsafe(18)
            SETTINGS_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False), "utf-8")
        _cache = s
        return deepcopy(s)


def _apply_models_dir(s: dict) -> None:
    global MODELS_DIR
    MODELS_DIR = Path(s["models_dir"]).expanduser() if s.get("models_dir") else HOME / "models"


def save(patch: dict) -> dict:
    global _cache
    with _lock:
        s = _merge(load(), patch)
        if home_missing():
            raise StorageMissing(str(HOME))
        SETTINGS_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False), "utf-8")
        _cache = s
        _apply_models_dir(s)
        return deepcopy(s)


def public(s: dict | None = None) -> dict:
    """Settings safe to send to the browser: API keys masked."""
    s = deepcopy(s or load())
    s["devices"] = [{k: d[k] for k in ("id", "name", "created") if k in d} for d in s.get("devices") or []]
    for p in ("anthropic", "openai", "compatible"):
        key = s["llm"][p].get("api_key", "")
        s["llm"][p]["api_key"] = ("••••" + key[-4:]) if key else ""
        s["llm"][p]["has_key"] = bool(key)
    return s


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None
