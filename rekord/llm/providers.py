"""Bring your own brain: Claude (Anthropic API), ChatGPT (OpenAI API), Ollama (100 % local) or any
OpenAI-compatible server (LM Studio, llama.cpp, Jan, vLLM, OpenRouter, Groq ...)."""
from __future__ import annotations

import json
import os
import re
from typing import Iterator

import httpx

PROVIDERS = {
    "anthropic": "Claude (Anthropic API)",
    "openai": "ChatGPT (OpenAI API)",
    "ollama": "Ollama (lokal)",
    "compatible": "OpenAI-kompatibel (LM Studio, llama.cpp, OpenRouter ...)",
    "none": "Keine KI (nur Transkription)",
}

ANTHROPIC_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"]
_ADAPTIVE = ("opus-4-6", "opus-4-7", "opus-4-8", "opus-5", "sonnet-4-6", "sonnet-5", "fable", "haiku-5", "mythos")
_FALLBACK_OK = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")


class LLMError(RuntimeError):
    pass


def active(settings: dict) -> tuple[str, dict]:
    p = settings["llm"]["provider"]
    return p, settings["llm"].get(p, {})


def configured(settings: dict) -> tuple[bool, str]:
    """Is the chosen AI usable at all? (cheap check, no network) -> (ok, reason)"""
    p, cfg = active(settings)
    if p == "none":
        return False, "Keine KI gewählt"
    if p == "anthropic" and not (cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False, "Claude: API-Key fehlt"
    if p == "openai":
        if not (cfg.get("api_key") or os.environ.get("OPENAI_API_KEY")):
            return False, "ChatGPT: API-Key fehlt"
        if not cfg.get("model"):
            return False, "ChatGPT: Modell fehlt"
    if p == "compatible" and not (cfg.get("base_url") and cfg.get("model")):
        return False, "Server-Adresse oder Modell fehlt"
    if p == "ollama" and not cfg.get("model"):
        return False, "Ollama: Modell fehlt"
    return True, ""


def model_name(settings: dict) -> str:
    p, cfg = active(settings)
    return cfg.get("model", "") if p != "none" else ""


def context_chars(settings: dict) -> int:
    """How much transcript we may send in one request (rough chars, ~3.5 chars/token)."""
    p, cfg = active(settings)
    if p == "ollama":
        return int(cfg.get("num_ctx", 32768) * 3.5 * 0.6)
    if p == "compatible":
        return int(cfg.get("context_tokens", 32768) * 3.5 * 0.6)
    return 600_000  # Claude / GPT: long context


def stream(settings: dict, system: str, messages: list[dict], max_tokens: int = 32000) -> Iterator[str]:
    p, cfg = active(settings)
    if p == "none":
        raise LLMError("Keine KI konfiguriert. Einstellungen → KI.")
    if p == "anthropic":
        yield from _anthropic(cfg, system, messages, max_tokens)
    elif p == "ollama":
        yield from _ollama(cfg, system, messages)
    elif p in ("openai", "compatible"):
        yield from _openai(cfg, system, messages, max_tokens, compatible=p == "compatible")
    else:
        raise LLMError(f"Unbekannter Anbieter {p}")


def complete(settings: dict, system: str, messages: list[dict], max_tokens: int = 32000) -> str:
    return "".join(stream(settings, system, messages, max_tokens))


# ------------------------------------------------------------------ Anthropic

def _anthropic(cfg: dict, system: str, messages: list[dict], max_tokens: int) -> Iterator[str]:
    import anthropic
    client = anthropic.Anthropic(api_key=cfg.get("api_key") or None)  # empty -> env var / `ant auth login` profile
    model = cfg.get("model") or "claude-opus-5-5"
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
    if any(x in model for x in _ADAPTIVE):
        kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": cfg.get("effort") or "medium"}
    betas = []
    if cfg.get("fallbacks", True) and model in _FALLBACK_OK:
        betas.append("server-side-fallback-2026-07-01")
        kwargs["fallbacks"] = "default"
    try:
        if betas:
            kwargs["betas"] = betas
        with client.beta.messages.stream(**kwargs) as st:
            yield from st.text_stream
            final = st.get_final_message()
        if final.stop_reason == "refusal":
            raise LLMError("Claude hat die Anfrage abgelehnt.")
    except anthropic.AuthenticationError as e:
        raise LLMError("Anthropic API-Key ungültig.") from e
    except anthropic.NotFoundError as e:
        raise LLMError(f"Modell {model} nicht gefunden.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Anthropic Rate-Limit erreicht – kurz warten.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic Fehler {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Keine Verbindung zu api.anthropic.com.") from e


# ------------------------------------------------------------------ OpenAI + compatible

def _openai(cfg: dict, system: str, messages: list[dict], max_tokens: int, compatible: bool) -> Iterator[str]:
    import openai
    base = cfg.get("base_url") or None
    client = openai.OpenAI(api_key=cfg.get("api_key") or ("not-needed" if compatible else None), base_url=base)
    model = cfg.get("model")
    if not model:
        raise LLMError("Kein Modell gewählt (Einstellungen → KI → Modell).")
    msgs = [{"role": "system", "content": system}] + messages
    try:
        kw = {"max_completion_tokens": max_tokens} if not compatible else {"max_tokens": max_tokens}
        resp = client.chat.completions.create(model=model, messages=msgs, stream=True, **kw)
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except openai.AuthenticationError as e:
        raise LLMError("API-Key ungültig.") from e
    except openai.NotFoundError as e:
        raise LLMError(f"Modell {model} nicht gefunden.") from e
    except openai.RateLimitError as e:
        raise LLMError("Rate-Limit / Guthaben aufgebraucht.") from e
    except openai.APIConnectionError as e:
        raise LLMError(f"Keine Verbindung zu {base or 'api.openai.com'}.") from e
    except openai.APIStatusError as e:
        raise LLMError(f"Fehler {e.status_code}: {e.message}") from e


# ------------------------------------------------------------------ Ollama (native API: lets us raise num_ctx)

# A local model reserves memory for its whole context window up front (qwen3:8b: ~4.5 GB for 32k tokens, on top of
# the model) – on a 16 GB Mac that's swapping, and the whole computer stutters. So: only as much as this request needs.
OLLAMA_KEEP_ALIVE = "2m"  # and give the memory back soon after (Ollama's own default keeps it for 5 minutes)


def fit_context(system: str, messages: list[dict], limit: int = 32768) -> int:
    """Context window for one request: prompt (~3 chars per token, generous) + room for the answer, rounded up to a
    power of two, between 4096 and the configured limit."""
    chars = len(system) + sum(len(str(m.get("content", ""))) for m in messages)
    need = chars // 3 + 4096
    ctx = 4096
    while ctx < need and ctx < limit:
        ctx *= 2
    return max(2048, min(ctx, limit))


def _ollama(cfg: dict, system: str, messages: list[dict]) -> Iterator[str]:
    from . import ollama
    base = (cfg.get("base_url") or "http://localhost:11434").rstrip("/")
    try:
        started = ollama.start(base)  # installed but not running → start it, like a user would
    except RuntimeError as e:  # e.g. the drive with the models is not connected
        raise LLMError(str(e)) from e
    if not started:
        raise LLMError("Ollama ist nicht installiert. Einstellungen → KI → Lokal → „Ollama herunterladen“.")
    model = cfg.get("model")
    if not model:
        raise LLMError("Kein lokales Modell gewählt. Einstellungen → KI → Lokal → Modell laden.")
    body = {"model": model, "stream": True, "think": False,
            "messages": [{"role": "system", "content": system}] + messages,
            "options": {"num_ctx": fit_context(system, messages, int(cfg.get("num_ctx", 32768)))},
            "keep_alive": OLLAMA_KEEP_ALIVE}
    try:
        with httpx.stream("POST", f"{base}/api/chat", json=body, timeout=httpx.Timeout(600, connect=5)) as r:
            if r.status_code == 404:
                raise LLMError(f"Modell „{model}“ ist nicht geladen. Einstellungen → KI → Lokal → Laden.")
            if r.status_code == 400 and body.get("think") is False:  # older Ollama without the think flag
                r.close()
                body.pop("think")
                yield from _strip_think(_ollama_raw(base, body))
                return
            r.raise_for_status()
            yield from _strip_think(_ollama_lines(r))
    except httpx.ConnectError as e:
        raise LLMError(f"Ollama antwortet nicht auf {base}.") from e


def _ollama_raw(base: str, body: dict) -> Iterator[str]:
    with httpx.stream("POST", f"{base}/api/chat", json=body, timeout=httpx.Timeout(600, connect=5)) as r:
        r.raise_for_status()
        yield from _ollama_lines(r)


def _ollama_lines(r) -> Iterator[str]:
    for line in r.iter_lines():
        if not line:
            continue
        d = json.loads(line)
        if d.get("error"):
            raise LLMError(f"Ollama: {d['error']}")
        if (c := d.get("message", {}).get("content")):
            yield c


def _strip_think(chunks: Iterator[str]) -> Iterator[str]:
    """Some local models wrap their reasoning in <think>…</think>; never show that in a summary.
    Works on a stream: tag halves split across chunks are held back until they are decided."""
    def partial(text: str, tag: str) -> int:  # length of the longest suffix of text that starts tag
        return next((k for k in range(min(len(tag) - 1, len(text)), 0, -1) if tag.startswith(text[-k:])), 0)

    buf, inside = "", False
    for c in chunks:
        buf += c
        while buf:
            tag = "</think>" if inside else "<think>"
            pos = buf.find(tag)
            if pos >= 0:
                if not inside and pos:
                    yield buf[:pos]
                buf, inside = buf[pos + len(tag):], not inside
                if not inside:
                    buf = buf.lstrip()
                continue
            hold = partial(buf, tag)
            if not inside and len(buf) > hold:
                yield buf[:len(buf) - hold]
            buf = buf[len(buf) - hold:]
            break
    if buf and not inside:
        yield buf


# ------------------------------------------------------------------ discovery & test

def list_models(settings: dict, provider: str) -> list[str]:
    cfg = settings["llm"].get(provider, {})
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=cfg.get("api_key") or None)
            ids = [m.id for m in client.models.list(limit=100)]
            return sorted(set(ids), key=lambda m: (m not in ANTHROPIC_MODELS, m)) or ANTHROPIC_MODELS
        if provider == "ollama":
            base = (cfg.get("base_url") or "http://localhost:11434").rstrip("/")
            return [m["name"] for m in httpx.get(f"{base}/api/tags", timeout=5).json().get("models", [])]
        if provider in ("openai", "compatible"):
            import openai
            client = openai.OpenAI(api_key=cfg.get("api_key") or "not-needed", base_url=cfg.get("base_url") or None,
                                   timeout=15, max_retries=1)
            ids = sorted(m.id for m in client.models.list())
            if provider == "openai":
                ids = [i for i in ids if i.startswith(("gpt", "o", "chatgpt"))
                       and not any(x in i for x in ("audio", "realtime", "tts", "transcribe", "image", "embedding", "search"))]
            return ids
    except Exception as e:  # noqa: BLE001
        if provider == "anthropic":
            return ANTHROPIC_MODELS
        raise LLMError(str(e)) from e
    return []


_NOT_CHAT = ("audio", "realtime", "tts", "transcribe", "image", "search", "embed", "instruct", "mini", "nano", "codex",
             "dall", "whisper", "moderation", "babbage", "davinci", "oss", "preview", "chat-latest", "computer-use",
             "research", "-pro")


def default_model(provider: str, names: list[str]) -> str | None:
    """A sensible model when the user hasn't picked one: newest full GPT, or the first chat model of a server."""
    if provider == "openai":
        cands = [n for n in names if n.startswith("gpt-") and not any(x in n for x in _NOT_CHAT)
                 and not re.search(r"\d{4}-\d{2}-\d{2}|-\d{4}$", n)]

        def version(n: str):
            m = re.match(r"gpt-(\d+)(?:\.(\d+))?", n)
            return (int(m[1]), int(m[2] or 0), -len(n)) if m else (0, 0, 0)
        return max(cands, key=version) if cands else next((n for n in names if n.startswith("gpt-")), None)
    chat = [n for n in names if "embed" not in n.lower()]
    return chat[0] if chat else None


def fill_model(settings: dict, provider: str) -> str | None:
    """Key or server set but no model yet → pick one, so "Laden → auswählen" is not needed."""
    try:
        return default_model(provider, list_models(settings, provider))
    except LLMError:
        return None


def test(settings: dict) -> str:
    out = complete(settings, "Antworte mit genau einem Wort.", [{"role": "user", "content": "Sag 'bereit'."}], 2000)
    return out.strip()[:200]
