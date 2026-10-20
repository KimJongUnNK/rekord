"""One-click setup: local AI (install → start → download → select), AI autodetect, default models,
Claude Desktop/Code connection, HTTPS certificates for phone browsers."""
import http.server
import io
import json
import os
import signal
import socket
import sys
import tarfile
import threading
import time
from pathlib import Path

import pytest

from rekord import config


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ------------------------------------------------------------------ local AI, end to end (Linux install path)

@pytest.fixture
def fake_ollama_release(tmp_path, monkeypatch):
    """Serves ollama-linux-<arch>.tar.zst whose bin/ollama is our fake server."""
    zstandard = pytest.importorskip("zstandard")
    from rekord.llm import ollama
    port = _free_port()
    script = (f"#!{sys.executable}\nimport runpy, sys\nsys.argv[0] = 'ollama'\n"
              f"runpy.run_path({str(Path(__file__).with_name('fake_ollama.py'))!r}, run_name='__main__')\n").encode()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as t:
        for name, data, mode in (("bin/ollama", script, 0o755), ("lib/ollama/libfake.so", b"\0", 0o644)):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            t.addfile(info, io.BytesIO(data))
    www = tmp_path / "www"
    www.mkdir()
    (www / ollama._asset()).write_bytes(zstandard.ZstdCompressor().compress(raw.getvalue()))

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(www), **kw)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("REKORD_OLLAMA_DOWNLOAD", f"http://127.0.0.1:{srv.server_address[1]}")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("OLLAMA_HOST", f"127.0.0.1:{port}")
    monkeypatch.setenv("FAKE_OLLAMA_PIDFILE", str(tmp_path / "ollama.pid"))
    monkeypatch.setattr(ollama.shutil, "which", lambda name: None)  # pretend nothing is installed
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()
    pid = tmp_path / "ollama.pid"
    if pid.exists():
        try:
            os.kill(int(pid.read_text()), signal.SIGTERM)
        except OSError:
            pass


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux install path (macOS/Windows: CI job ollama-real)")
def test_local_ai_one_click_installs_starts_downloads_and_selects(fake_ollama_release, monkeypatch):
    from rekord.llm import ollama, providers
    base = fake_ollama_release
    monkeypatch.setattr(ollama, "ram_gb", lambda: 16.0)
    monkeypatch.setattr(ollama, "hardware", lambda: {"ram_gb": 16.0, "gpu": None, "vram_gb": 0, "label": "16 GB RAM"})
    assert ollama.binary() is None
    ready = []
    assert ollama.setup(base, on_ready=ready.append)
    assert not ollama.setup(base)  # second click while running: ignored
    for _ in range(300):
        st = ollama.setup_state()
        if st["state"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert st["state"] == "done", st
    assert ready == ["qwen3:8b"] and st["model"] == "qwen3:8b"
    assert ollama.binary() == str(ollama.user_dir() / "bin/ollama")
    assert (ollama.user_dir() / "lib/ollama/libfake.so").exists()
    assert ollama.pulls()["qwen3:8b"]["state"] == "done"
    s = config.load()
    s["llm"]["provider"], s["llm"]["ollama"] = "ollama", {"base_url": base, "model": "qwen3:8b"}
    assert providers.complete(s, "sys", [{"role": "user", "content": "hi"}]) == "OK qwen3:8b"  # <think> stripped
    # already installed + model there → setup only selects
    ready.clear()
    assert ollama.setup(base, on_ready=ready.append)
    for _ in range(100):
        if ollama.setup_state()["state"] == "done":
            break
        time.sleep(0.1)
    assert ready == ["qwen3:8b"]
    ollama.delete("qwen3:8b", base)  # the "Löschen" button
    assert ollama.status(base)["models"] == [] and "qwen3:8b" not in ollama.pulls()
    with pytest.raises(RuntimeError, match="nicht"):
        ollama.delete("qwen3:8b", base)


def test_recommended_model_fits_ram():
    from rekord.llm import ollama
    apple = lambda ram: {"ram_gb": ram, "gpu": "apple", "vram_gb": ram * 0.7}  # noqa: E731
    cpu = lambda ram: {"ram_gb": ram, "gpu": None, "vram_gb": 0}  # noqa: E731
    nvidia = lambda ram, vram: {"ram_gb": ram, "gpu": "nvidia", "vram_gb": vram}  # noqa: E731
    # more memory → a better model; the best one for this computer, not the same for everyone
    assert ollama.recommended_for(hw=apple(64)) == "qwen3:30b"
    assert ollama.recommended_for(hw=apple(32)) == "qwen3:30b"
    assert ollama.recommended_for(hw=apple(24)) == "qwen3:14b"
    assert ollama.recommended_for(hw=apple(15.6)) == "qwen3:8b"  # "16 GB" machines report a bit less
    assert ollama.recommended_for(hw=apple(7.7)) == "qwen3:4b"
    assert ollama.recommended_for(hw=apple(4)) == "qwen3:1.7b"
    # without a graphics chip dense mid-size models crawl – the 30b one (3b active) is still fine
    assert ollama.recommended_for(hw=cpu(24)) == "qwen3:8b"
    assert ollama.recommended_for(hw=cpu(32)) == "qwen3:30b"
    assert ollama.recommended_for(hw=nvidia(24, 12)) == "qwen3:14b"
    assert ollama.recommended_for(hw=nvidia(24, 6)) == "qwen3:8b"  # 9.3 GB model doesn't fit 6 GB of video memory
    hw = ollama.hardware()
    assert hw["ram_gb"] > 0.5 and "GB RAM" in hw["label"]
    models = [{"name": "nomic-embed-text:latest", "size_gb": 0.3}, {"name": "mistral:latest", "size_gb": 4.1},
              {"name": "llama3.1:70b", "size_gb": 40}]
    assert ollama.pick_installed(models, 16) == "mistral:latest"  # no embeddings, nothing too big
    assert ollama.pick_installed(models + [{"name": "qwen3:8b", "size_gb": 5.2}], 16) == "qwen3:8b"
    assert ollama.pick_installed([], 16) is None
    assert ollama.system.ram_gb() > 0.5


def test_openai_default_model_is_newest_full_gpt():
    from rekord.llm.providers import default_model
    names = ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-2025-04-14", "gpt-5", "gpt-5-mini", "gpt-5.5", "gpt-5.5-pro",
             "gpt-5.5-2026-05-01", "o3", "gpt-5-codex", "gpt-realtime", "chatgpt-4o-latest", "gpt-5-chat-latest", "gpt-image-1"]
    assert default_model("openai", names) == "gpt-5.5"
    assert default_model("openai", ["gpt-4o", "gpt-3.5-turbo-0125"]) == "gpt-4o"
    assert default_model("compatible", ["text-embedding-nomic", "llama-3.2-3b"]) == "llama-3.2-3b"
    assert default_model("openai", []) is None


def test_autoconfigure_uses_ollama_already_on_the_computer(monkeypatch):
    from rekord.llm import auto, ollama
    config.save({"llm": {"provider": "anthropic", "anthropic": {"api_key": ""}}})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(ollama, "binary", lambda: "/usr/bin/ollama")
    monkeypatch.setattr(ollama, "start", lambda base=None, wait=20: True)
    monkeypatch.setattr(ollama, "status", lambda base=None: {"models": [{"name": "qwen3:4b", "size_gb": 2.6}]})
    monkeypatch.setattr(ollama, "ram_gb", lambda: 16.0)
    assert auto.autoconfigure() == "Ollama · qwen3:4b"
    s = config.load()
    assert s["llm"]["provider"] == "ollama" and s["llm"]["ollama"]["model"] == "qwen3:4b"
    assert auto.autoconfigure() is None  # working setup: never touched again


def test_autoconfigure_respects_off_and_working_keys(monkeypatch):
    from rekord.llm import auto, ollama
    monkeypatch.setattr(ollama, "binary", lambda: "/usr/bin/ollama")
    monkeypatch.setattr(ollama, "start", lambda base=None, wait=20: True)
    monkeypatch.setattr(ollama, "status", lambda base=None: {"models": [{"name": "qwen3:4b", "size_gb": 2.6}]})
    config.save({"llm": {"provider": "none"}})
    assert auto.autoconfigure() is None and config.load()["llm"]["provider"] == "none"
    config.save({"llm": {"provider": "anthropic", "anthropic": {"api_key": "sk-ant-x"}}})
    assert auto.autoconfigure() is None and config.load()["llm"]["provider"] == "anthropic"
    config.save({"llm": {"provider": "anthropic", "anthropic": {"api_key": ""}}})


# ------------------------------------------------------------------ Claude Desktop / Claude Code

def test_connect_claude_desktop_merges_config(tmp_path, monkeypatch):
    from rekord import integrations
    d = tmp_path / "Claude"
    d.mkdir()
    cfg = d / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "globalShortcut": "Ctrl+Space"}))
    monkeypatch.setattr(integrations, "_desktop_dirs", lambda: [d])
    monkeypatch.setattr(integrations, "_desktop_running", lambda: False)
    monkeypatch.setattr(integrations, "_desktop_app", lambda: None)
    assert integrations.claude_desktop()["connected"] is False
    r = integrations.connect_claude_desktop()
    data = json.loads(cfg.read_text())
    assert r["paths"] == [str(cfg)]
    assert data["mcpServers"]["other"] == {"command": "x"} and data["globalShortcut"] == "Ctrl+Space"
    entry = data["mcpServers"]["rekord"]
    assert entry["args"][-1] == "mcp" and entry["env"]["REKORD_HOME"] == str(config.HOME)
    assert (d / "claude_desktop_config.json.bak").exists()
    assert integrations.claude_desktop()["connected"] is True
    cfg.write_text("{ broken")
    with pytest.raises(RuntimeError, match="kein gültiges JSON"):
        integrations.connect_claude_desktop()


def test_connect_claude_code_uses_cli(tmp_path, monkeypatch):
    from rekord import integrations
    calls = tmp_path / "calls.txt"
    cli = tmp_path / "claude"
    cli.write_text(f"#!/bin/sh\necho \"$@\" >> {calls}\n[ \"$2\" = get ] && grep -q add-json {calls} && exit 0\n[ \"$2\" = get ] && exit 1\nexit 0\n")
    cli.chmod(0o755)
    if sys.platform == "win32":
        pytest.skip("shell stub")
    monkeypatch.setattr(integrations, "_claude_cli", lambda: str(cli))
    assert integrations.claude_code() == {"installed": True, "connected": False}
    assert integrations.connect_claude_code() == {"ok": True}
    lines = calls.read_text().splitlines()
    added = next(line for line in lines if "add-json" in line)
    assert added.startswith("mcp add-json --scope user rekord {")
    assert json.loads(added.split("rekord ", 1)[1])["args"][-1] == "mcp"
    assert integrations.claude_code()["connected"] is True


# ------------------------------------------------------------------ HTTPS for phone browsers

