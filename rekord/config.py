"""Paths and persistent settings. Everything lives in one folder (REKORD_HOME)."""
from __future__ import annotations

import json
import os
import secrets
import threading
from copy import deepcopy
from pathlib import Path

HOME = Path(os.environ.get("REKORD_HOME", Path.home() / "Rekord")).expanduser()
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
    "num_speakers": 0,  # 0 = auto
    "cluster_threshold": 0.6,
    "profile_threshold": 0.55,
    "live_profile_threshold": 0.5,
    "live_cluster_threshold": 0.55,
    "live_transcribe": True,
    "vocabulary": [],  # list of {"from": "...", "to": "..."} corrections and hotwords
    "auto_summary": True,
    "default_template": "auto",
    "summary_language": "de",
    "llm": {
        "provider": "anthropic",  # anthropic | openai | ollama | compatible | none
        "anthropic": {"api_key": "", "model": "claude-opus-5-5", "effort": "medium", "fallbacks": True},
        "openai": {"api_key": "", "model": "", "base_url": ""},
        "ollama": {"base_url": "http://localhost:11434", "model": "llama3.1"},
        "compatible": {"api_key": "", "model": "", "base_url": "http://localhost:1234/v1"},
    },
    "inbox_enabled": True,
    "pair_token": "",
}

_lock = threading.RLock()
_cache: dict | None = None


def ensure_dirs() -> None:
    for d in (HOME, AUDIO_DIR, MODELS_DIR, INBOX_DIR):
        d.mkdir(parents=True, exist_ok=True)


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
        ensure_dirs()
        stored = {}
        if SETTINGS_PATH.exists():
            try:
                stored = json.loads(SETTINGS_PATH.read_text("utf-8"))
            except json.JSONDecodeError:
                stored = {}
        s = _merge(DEFAULTS, stored)
        if not s.get("pair_token"):
            s["pair_token"] = secrets.token_urlsafe(18)
            SETTINGS_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False), "utf-8")
        _cache = s
        return deepcopy(s)


def save(patch: dict) -> dict:
    global _cache
    with _lock:
        s = _merge(load(), patch)
        SETTINGS_PATH.write_text(json.dumps(s, indent=2, ensure_ascii=False), "utf-8")
        _cache = s
        return deepcopy(s)


def public(s: dict | None = None) -> dict:
    """Settings safe to send to the browser: API keys masked."""
    s = deepcopy(s or load())
    for p in ("anthropic", "openai", "compatible"):
        key = s["llm"][p].get("api_key", "")
        s["llm"][p]["api_key"] = ("••••" + key[-4:]) if key else ""
        s["llm"][p]["has_key"] = bool(key)
    return s


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None
