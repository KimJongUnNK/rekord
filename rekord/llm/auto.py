"""AI without setup: on start, use what is already on this computer (Ollama, LM Studio, API keys in the
environment) and fill in obvious gaps (a key without a model). Never overrides a working choice or "Aus"."""
from __future__ import annotations

import logging
import os

import httpx

from .. import config
from . import ollama, providers

log = logging.getLogger("rekord.ai")
LOCAL_SERVERS = ("http://localhost:1234/v1", "http://localhost:8080/v1")  # LM Studio, llama.cpp


def _save(patch: dict, what: str) -> str:
    config.save({"llm": patch})
    log.info("KI automatisch eingerichtet: %s", what)
    return what


def autoconfigure() -> str | None:
    """Returns what was set up, or None if nothing changed."""
    s = config.load()
    p, cfg = providers.active(s)
    if p == "none" or providers.configured(s)[0]:
        return None
    # the user started setting something up → finish that instead of switching
    if p in ("openai", "compatible") and (cfg.get("api_key") or (p == "compatible" and cfg.get("base_url") not in (None, "", *LOCAL_SERVERS))):
        m = providers.fill_model(s, p)
        return _save({p: {"model": m}}, f"{p} · {m}") if m else None

    base = s["llm"]["ollama"].get("base_url")
    if ollama.binary() and ollama.start(base, wait=15):
        m = ollama.pick_installed(ollama.status(base)["models"])
        if m:
            return _save({"provider": "ollama", "ollama": {"model": m}}, f"Ollama · {m}")
    for url in LOCAL_SERVERS:
        try:
            names = [d["id"] for d in httpx.get(f"{url}/models", timeout=1.5).json().get("data", [])]
        except (httpx.HTTPError, ValueError, KeyError, AttributeError):
            continue
        m = providers.default_model("compatible", names)
        if m:
            return _save({"provider": "compatible", "compatible": {"base_url": url, "model": m}}, f"{url} · {m}")
    if os.environ.get("OPENAI_API_KEY"):
        m = providers.fill_model(s, "openai")
        if m:
            return _save({"provider": "openai", "openai": {"model": m}}, f"ChatGPT · {m}")
    return None
