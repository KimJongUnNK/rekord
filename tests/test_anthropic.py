"""Claude provider: the exact request the Anthropic SDK sends, against a local stand-in for api.anthropic.com."""
import json
import threading
import time

import pytest

from rekord import config
from rekord.llm import providers


@pytest.fixture(scope="module")
def fake_anthropic(monkeypatch_module=None):
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse

    app = FastAPI()
    seen: dict = {}

    @app.get("/v1/models")
    def models():
        return {"data": [{"type": "model", "id": "claude-opus-5-5", "display_name": "Claude Opus 5.5", "created_at": "2026-01-01T00:00:00Z"}],
                "has_more": False, "first_id": "claude-opus-5-5", "last_id": "claude-opus-5-5"}

    @app.post("/v1/messages")
    async def messages(req: Request):
        body = await req.json()
        seen["body"], seen["headers"] = body, dict(req.headers)
        if body.get("model") == "refuse":
            stop = "refusal"
        else:
            stop = "end_turn"

        def ev(name, data):
            return f"event: {name}\ndata: {json.dumps(data)}\n\n"

        def gen():
            yield ev("message_start", {"type": "message_start", "message": {
                "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"], "content": [],
                "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 0}}})
            yield ev("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
            for piece in ["# Protokoll\n", "- [ ] Rider — **Emil**"]:
                yield ev("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": piece}})
            yield ev("content_block_stop", {"type": "content_block_stop", "index": 0})
            yield ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                       "usage": {"output_tokens": 12}})
            yield ev("message_stop", {"type": "message_stop"})
        # SDK 1.x sends the key as x-api-key, 2.x as "Authorization: Bearer …" – the API takes both
        key = req.headers.get("x-api-key") or req.headers.get("authorization", "").removeprefix("Bearer ")
        if key != "sk-ant-test":
            return JSONResponse({"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}, status_code=401)
        return StreamingResponse(gen(), media_type="text/event-stream")

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=9312, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    import os
    old = os.environ.get("ANTHROPIC_BASE_URL")
    os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9312"
    yield seen
    server.should_exit = True
    if old is None:
        os.environ.pop("ANTHROPIC_BASE_URL", None)
    else:
        os.environ["ANTHROPIC_BASE_URL"] = old


def _settings(**cfg):
    s = config.load()
    s["llm"]["provider"] = "anthropic"
    s["llm"]["anthropic"].update({"api_key": "sk-ant-test", "model": "claude-opus-5-5", "effort": "medium", "fallbacks": True} | cfg)
    return s


def test_claude_request_shape_and_streaming(fake_anthropic):
    out = providers.complete(_settings(), "SYSTEM", [{"role": "user", "content": "Transkript"}])
    assert out == "# Protokoll\n- [ ] Rider — **Emil**"
    body, headers = fake_anthropic["body"], fake_anthropic["headers"]
    assert body["model"] == "claude-opus-5-5" and body["stream"] is True
    assert body["system"] == "SYSTEM" and body["messages"][0]["content"] == "Transkript"
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", "")


def test_claude_without_fallbacks_sends_no_beta(fake_anthropic):
    providers.complete(_settings(fallbacks=False, model="claude-haiku-5-5", effort="low"), "S", [{"role": "user", "content": "x"}])
    body, headers = fake_anthropic["body"], fake_anthropic["headers"]
    assert "fallbacks" not in body and "anthropic-beta" not in headers
    assert body["output_config"] == {"effort": "low"}


def test_claude_errors_are_friendly(fake_anthropic):
    with pytest.raises(providers.LLMError, match="API-Key ungültig"):
        providers.complete(_settings(api_key="wrong"), "S", [{"role": "user", "content": "x"}])
    with pytest.raises(providers.LLMError, match="abgelehnt"):
        providers.complete(_settings(model="refuse", fallbacks=False), "S", [{"role": "user", "content": "x"}])


def test_claude_model_list(fake_anthropic):
    assert providers.list_models(_settings(), "anthropic")[0] == "claude-opus-5-5"


def test_configured_check(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    s = _settings(api_key="")
    assert providers.configured(s) == (False, "Claude: API-Key fehlt")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert providers.configured(s)[0]
    s["llm"]["provider"] = "none"
    assert not providers.configured(s)[0]
