"""A tiny stand-in for the Ollama server (version, tags, pull with progress, chat) – used by the tests and
packaged as a fake `ollama` binary to test the one-click installer without downloading gigabytes."""
import json
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
have = [m for m in os.environ.get("FAKE_OLLAMA_MODELS", "").split(",") if m]


@app.get("/api/version")
def version():
    return {"version": "0.99.0-fake"}


@app.get("/api/tags")
def tags():
    return {"models": [{"name": n, "size": 2.6e9} for n in have]}


@app.post("/api/pull")
async def pull(r: Request):
    m = (await r.json())["model"]

    def g():
        for i in range(0, 101, 25):
            yield json.dumps({"status": "pulling", "total": 1000, "completed": i * 10}) + "\n"
            time.sleep(0.05)
        have.append(m)
        yield json.dumps({"status": "success"}) + "\n"
    return StreamingResponse(g())


@app.post("/api/chat")
async def chat(r: Request):
    b = await r.json()

    def g():
        for part in ["<think>hmm", "</think>", f"OK {b['model']}"]:
            yield json.dumps({"message": {"content": part}}) + "\n"
        yield json.dumps({"done": True}) + "\n"
    return StreamingResponse(g())


if __name__ == "__main__":  # `ollama serve`
    import uvicorn
    host, _, port = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").rpartition(":")
    if os.environ.get("FAKE_OLLAMA_PIDFILE"):
        open(os.environ["FAKE_OLLAMA_PIDFILE"], "w").write(str(os.getpid()))
    if len(sys.argv) > 1 and sys.argv[1] != "serve":
        sys.exit(0)
    uvicorn.run(app, host=host or "127.0.0.1", port=int(port), log_level="warning")
