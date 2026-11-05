"""HTTP API + auth tests (FastAPI TestClient). No models needed."""
import io
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from rekord import config, db
from rekord.server import app


@pytest.fixture(scope="module")
def client():
    app.state.auto_download = False
    with TestClient(app) as c:
        yield c


def _wav(seconds=1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes((np.sin(np.arange(int(16000 * seconds)) / 8) * 3000).astype("<i2").tobytes())
    return buf.getvalue()


def test_index_and_pwa_assets(client):
    assert "REKORD" in client.get("/").text
    assert client.get("/manifest.webmanifest").json()["short_name"] == "REKORD"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/icons/icon-192.png").headers["content-type"] == "image/png"
    assert client.get("/icons/../server.py").status_code == 404


def test_status_and_settings(client):
    st = client.get("/api/status").json()
    assert st["version"] and "models" in st
    r = client.put("/api/settings", json={"language": "de", "llm": {"openai": {"api_key": "sk-test-9876"}}})
    assert r.json()["llm"]["openai"]["api_key"] == "••••9876"
    # masked value sent back must not overwrite the real key
    client.put("/api/settings", json={"llm": {"openai": {"api_key": "••••9876", "model": "x"}}})
    assert config.load()["llm"]["openai"]["api_key"] == "sk-test-9876"


def test_upload_list_patch_delete(client, monkeypatch):
    from rekord import jobs
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    r = client.post("/api/recordings", files={"files": ("call.wav", _wav(), "audio/wav")},
                    data={"title": "Call mit Lisa", "participants": '{"ids": [], "guests": 2}'})
    rid = r.json()["items"][0]["id"]
    assert queued == [rid]
    assert db.get_recording(rid)["participants"]["guests"] == 2
    assert any(x["id"] == rid for x in client.get("/api/recordings").json()["items"])
    client.patch(f"/api/recordings/{rid}", json={"title": "Neu", "folder": "Voltage"})
    full = client.get(f"/api/recordings/{rid}").json()
    assert full["title"] == "Neu" and full["title_locked"] == 1 and full["folder"] == "Voltage"
    assert client.get(f"/api/recordings/{rid}/audio").status_code == 200
    assert client.get(f"/api/recordings/{rid}/export/md").status_code == 200
    assert client.post("/api/recordings", files={"files": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 400
    assert client.delete(f"/api/recordings/{rid}").json()["ok"]
    assert client.get(f"/api/recordings/{rid}").status_code == 404


def test_templates_api(client):
    items = client.get("/api/templates").json()["items"]
    assert len(items) >= 30
    t = client.post("/api/templates", json={"id": "meeting", "name": "Mein Protokoll", "prompt": "## X"}).json()
    assert t["id"].startswith("custom-")  # editing a built-in creates a copy
    client.delete(f"/api/templates/{t['id']}")


def test_colors_are_validated(client):
    pid = db.create_profile("Farbtest", __import__("numpy").ones(3, dtype="float32"))
    assert client.patch(f"/api/profiles/{pid}", json={"color": '"><script>alert(1)</script>'}).status_code == 400
    assert client.patch(f"/api/profiles/{pid}", json={"color": "#14b8a6"}).json()["color"] == "#14B8A6"
    db.delete_profile(pid)


def test_status_reports_missing_ai(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config.save({"llm": {"provider": "anthropic", "anthropic": {"api_key": ""}}})
    st = client.get("/api/status").json()
    assert st["ai_ready"] is False and "API-Key" in st["ai_problem"]


def test_pairing_qr_and_code(client):
    p = client.get("/api/pair").json()
    assert p["qr_app"].lstrip().startswith("<?xml") and "token" not in p and "qr_web" not in p
    assert len(p["code"]["code"]) == 6 and p["code"]["code"].isdigit() and p["code"]["expires"] > 0
    # the same code as a matrix for the desktop window, which draws it itself: square, only 0/1
    rows = p["qr_rows"]
    assert len(rows) >= 21 and all(len(r) == len(rows) and set(r) <= {"0", "1"} for r in rows)
    assert rows[0][:7] == "1111111" and rows[6][:7] == "1111111"  # a finder pattern in the corner


def test_lan_is_only_for_the_iphone_app(client):
    """In the Wi-Fi there is no web interface at all – only the paired app may use the API."""
    lan = TestClient(app, client=("192.168.1.50", 5000))
    assert lan.get("/api/status").status_code == 401
    tok = config.load()["pair_token"]
    for path in ("/", "/static/app.js", f"/?token={tok}", "/manifest.webmanifest", "/setup", "/rekord.mobileconfig"):
        r = lan.get(path, headers={"X-Rekord-Token": tok})
        assert r.status_code == 403 and "REKORD-App" in r.text, path  # no web version on the phone
    assert lan.get("/api/status", headers={"X-Rekord-Token": tok}).status_code == 200
    assert lan.get(f"/api/status?token={tok}").status_code == 200  # the app's audio player uses the query form
    fresh = TestClient(app, client=("192.168.1.51", 5000))
    with pytest.raises(Exception):
        with fresh.websocket_connect("/ws/events"):
            pass
    with lan.websocket_connect(f"/ws/events?token={tok}"):
        pass


def test_six_digit_code_pairs_a_device_with_its_own_key(client):
    from rekord import pairing
    code = client.get("/api/pair").json()["code"]["code"]
    phone = TestClient(app, client=("192.168.1.90", 5000))
    r = phone.post("/api/pair/claim", json={"code": code[:3] + " " + code[3:], "name": "Emils iPhone"})
    assert r.status_code == 200
    key = r.json()["token"]
    assert key != config.load()["pair_token"] and len(key) > 20
    assert phone.get("/api/status", headers={"X-Rekord-Token": key}).status_code == 200
    devs = client.get("/api/pair").json()["devices"]
    dev = next(d for d in devs if d["name"] == "Emils iPhone")
    assert "hash" not in dev and "hash" not in str(client.get("/api/settings").json()["devices"])
    assert key not in (config.SETTINGS_PATH.read_text("utf-8"))  # only a hash is stored
    assert phone.delete(f"/api/pair/devices/{dev['id']}", headers={"X-Rekord-Token": key}).status_code == 403  # only at the computer
    assert client.delete(f"/api/pair/devices/{dev['id']}").json()["ok"]
    assert phone.get("/api/status", headers={"X-Rekord-Token": key}).status_code == 401
    pairing._tries.clear()


def test_wrong_codes_lock_out_and_burn_the_code(client):
    from rekord import pairing
    pairing._tries.clear()
    code = pairing.new_code()["code"]
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    guesser = TestClient(app, client=("192.168.1.91", 5000))
    for _ in range(pairing.MAX_TRIES):
        assert guesser.post("/api/pair/claim", json={"code": wrong}).status_code == 403
    r = guesser.post("/api/pair/claim", json={"code": code})  # even the right code: locked for a minute
    assert r.status_code == 403 and "Versuche" in r.json()["detail"]
    others = [TestClient(app, client=(f"10.0.0.{i}", 5000)) for i in range(10)]
    for i in range(pairing.MAX_TOTAL_FAILS):
        others[i % 10].post("/api/pair/claim", json={"code": wrong})
    assert pairing.current_code()["code"] != code  # many guesses from many devices: the code is replaced
    pairing._tries.clear()


def test_code_runs_out(monkeypatch):
    from rekord import pairing
    pairing._tries.clear()
    code = pairing.new_code()["code"]
    real = pairing.time.time
    monkeypatch.setattr(pairing.time, "time", lambda: real() + pairing.CODE_TTL + 1)
    with pytest.raises(PermissionError, match="abgelaufen"):
        pairing.claim(code, "1.2.3.4")
    pairing._tries.clear()


def test_disconnect_all(client):
    from rekord import pairing
    code = pairing.new_code()["code"]
    key = pairing.claim(code, "1.2.3.5", "Altes Handy")
    old = config.load()["pair_token"]
    lan = TestClient(app, client=("192.168.1.92", 5000))
    assert lan.post("/api/settings/rotate-token", headers={"X-Rekord-Token": key}).status_code == 403
    assert client.post("/api/settings/rotate-token").json()["ok"]
    assert config.load()["pair_token"] != old and config.load()["devices"] == []
    assert not pairing.token_ok(key) and not pairing.token_ok(old)


def test_shutdown_only_from_this_computer(client, monkeypatch):
    lan = TestClient(app, client=("192.168.1.60", 5000))
    tok = config.load()["pair_token"]
    assert lan.post("/api/shutdown", headers={"X-Rekord-Token": tok}).status_code == 403
    import rekord.server as srv
    fired = []
    monkeypatch.setattr(srv.threading, "Timer", lambda d, fn: type("T", (), {"start": lambda self: fired.append(d)})())
    assert client.post("/api/shutdown").json()["ok"] and fired == [0.5]


def test_mcp_command_matches_install_type(client, monkeypatch):
    import sys as _sys
    assert client.get("/api/status").json()["mcp_command"][1:] == ["-m", "rekord", "mcp"]
    monkeypatch.setattr(_sys, "frozen", True, raising=False)
    assert client.get("/api/status").json()["mcp_command"][1:] == ["mcp"]  # packaged app takes the subcommand directly


def test_one_click_endpoints_only_on_this_computer(client, monkeypatch):
    from rekord import integrations, system
    from rekord.llm import ollama
    tok = config.load()["pair_token"]
    lan = TestClient(app, client=("192.168.1.80", 5000), headers={"X-Rekord-Token": tok})
    for path in ("/api/integrations/claude-desktop", "/api/integrations/claude-code", "/api/integrations/firewall"):
        assert lan.post(path).status_code == 403
    assert lan.post("/api/integrations/autostart", json={"enabled": True}).status_code == 403
    monkeypatch.setattr(ollama, "binary", lambda: None)
    assert lan.post("/api/ollama/setup", json={}).status_code == 403  # installing software: only at the computer
    monkeypatch.setattr(integrations, "claude_desktop", lambda: {"installed": True, "connected": False})
    monkeypatch.setattr(integrations, "claude_code", lambda: {"installed": False, "connected": False})
    monkeypatch.setattr(system, "firewall", lambda: {"tool": None, "open": None, "can_fix": False})
    st = client.get("/api/integrations").json()
    assert st["claude_desktop"]["installed"] and st["autostart"]["supported"] is False  # source install
    monkeypatch.setattr(integrations, "connect_claude_desktop", lambda: (_ for _ in ()).throw(RuntimeError("kaputt")))
    r = client.post("/api/integrations/claude-desktop")
    assert r.status_code == 400 and r.json()["detail"] == "kaputt"


def test_local_setup_endpoint_starts_chain_and_selects(client, monkeypatch):
    from rekord.llm import ollama
    started = {}

    def fake_setup(base, model, on_ready):
        started.update(base=base, model=model)
        on_ready("qwen3:4b")
        return True
    monkeypatch.setattr(ollama, "setup", fake_setup)
    assert client.post("/api/ollama/setup", json={}).status_code == 200
    s = config.load()
    assert s["llm"]["provider"] == "ollama" and s["llm"]["ollama"]["model"] == "qwen3:4b" and started["model"] is None
    assert client.post("/api/ollama/setup", json={"model": "bad name;rm"}).status_code == 400
    config.save({"llm": {"provider": "anthropic", "ollama": {"model": ""}}})


def test_openai_key_fills_model(client, monkeypatch):
    from rekord.llm import providers
    monkeypatch.setattr(providers, "list_models", lambda s, p: ["gpt-4o", "gpt-5.5", "gpt-5.5-mini"])
    client.put("/api/settings", json={"llm": {"provider": "openai", "openai": {"api_key": "sk-test", "model": ""}}})
    s = config.load()
    assert s["llm"]["openai"]["model"] == "gpt-5.5"
    config.save({"llm": {"provider": "anthropic", "openai": {"api_key": "", "model": ""}}})


def test_delete_local_model_switches_to_another(client, monkeypatch):
    from rekord.llm import ollama
    gone = []
    monkeypatch.setattr(ollama, "delete", lambda m, base=None: gone.append(m))
    monkeypatch.setattr(ollama, "status", lambda base=None: {"models": [{"name": "qwen3:4b", "size_gb": 2.6}]})
    config.save({"llm": {"provider": "ollama", "ollama": {"model": "qwen3:8b"}}})
    r = client.delete("/api/ollama/models/qwen3:8b")
    assert r.status_code == 200 and gone == ["qwen3:8b"] and r.json()["model"] == "qwen3:4b"
    tok = config.load()["pair_token"]
    lan = TestClient(app, client=("192.168.1.90", 5000), headers={"X-Rekord-Token": tok})
    assert lan.delete("/api/ollama/models/qwen3:4b").status_code == 403  # deleting: only at the computer
    config.save({"llm": {"provider": "anthropic", "ollama": {"model": ""}}})


def test_storage_info_and_first_start_choice(client, monkeypatch):
    import rekord.server as srv
    s = client.get("/api/storage").json()
    assert s["home"] == str(config.HOME) and s["drives"] and "usage" in s
    started = []
    monkeypatch.setattr(srv, "start_downloads", lambda: started.append(1))
    # set and restored by hand: monkeypatch's undo on starlette 1.x's State fails at teardown (KeyError 'auto_download')
    before = getattr(app.state, "auto_download", False)
    app.state.auto_download = True
    try:
        config.save({"storage_chosen": False})
        assert client.get("/api/status").json()["storage_chosen"] is False
        r = client.post("/api/storage/choose", json={"home": str(config.HOME)})  # keep the default → go
        assert r.status_code == 200 and started == [1] and config.load()["storage_chosen"] is True
        assert client.post("/api/storage/move", json={"what": "models", "target": "relativ/pfad"}).status_code == 400
    finally:
        app.state.auto_download = before


def test_best_local_model_and_load_and_use(client, monkeypatch):
    """„Bestes Modell laden & verwenden“ and „Anderes Modell“: download, then switch to it automatically."""
    import socket
    import threading
    import time

    import uvicorn

    from rekord.llm import ollama
    from tests import fake_ollama
    fake_ollama.have[:] = ["qwen3:8b"]
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(fake_ollama.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(50):
        if srv.started:
            break
        time.sleep(0.1)
    base = f"http://127.0.0.1:{port}"
    config.save({"llm": {"provider": "ollama", "ollama": {"base_url": base, "model": "qwen3:8b"}}})
    monkeypatch.setattr(ollama, "hardware", lambda: {"ram_gb": 32.0, "gpu": "apple", "vram_gb": 22.4, "label": "32 GB RAM · Apple-Chip"})
    monkeypatch.setattr(ollama, "ram_gb", lambda: 32.0)

    def wait_model(want):
        for _ in range(100):
            if config.load()["llm"]["ollama"]["model"] == want:
                return True
            time.sleep(0.05)
        return False
    try:
        st = client.get("/api/ollama").json()
        assert st["best"] == "qwen3:30b" and st["hardware"]["label"].startswith("32 GB")
        assert next(r for r in st["recommended"] if r["name"] == "qwen3:32b")["fits"] is False  # needs 48 GB
        r = client.post("/api/ollama/best").json()
        assert r == {"model": "qwen3:30b", "pulling": True}
        assert wait_model("qwen3:30b")  # downloaded, then used without another click
        assert client.post("/api/ollama/best").json() == {"model": "qwen3:30b", "pulling": False}
        assert client.post("/api/ollama/pull", json={"model": "mistral:latest", "use": True}).json()["ok"]
        assert wait_model("mistral:latest") and config.load()["llm"]["provider"] == "ollama"
        lan = TestClient(app, client=("192.168.1.99", 5000), headers={"X-Rekord-Token": config.load()["pair_token"]})
        assert lan.post("/api/ollama/best").status_code == 403  # downloading gigabytes: only at the computer
    finally:
        srv.should_exit = True
        config.save({"llm": {"provider": "anthropic", "ollama": {"base_url": "http://localhost:11434", "model": ""}}})


def test_templates_in_my_order(client):
    """Vorlagen: dragged to the top = first everywhere (picker, iPhone app); unknown ids don't break anything."""
    default = [t["id"] for t in client.get("/api/templates").json()["items"]]
    tid = client.post("/api/templates", json={"name": "Mein Board-Meeting", "prompt": "# Board", "category": "Eigene"}).json()["id"]
    client.put("/api/settings", json={"template_order": [tid, "lecture", "gone-template", "sales"]})
    ids = [t["id"] for t in client.get("/api/templates").json()["items"]]
    assert ids[:3] == [tid, "lecture", "sales"]
    assert ids[3:] == [i for i in default if i not in ("lecture", "sales")]  # the rest keeps its order
    client.put("/api/settings", json={"template_order": []})
    assert [t["id"] for t in client.get("/api/templates").json()["items"]][: len(default)] == default
    client.delete(f"/api/templates/{tid}")


def test_local_ai_gets_a_fitting_context_and_lets_go_of_the_memory(monkeypatch):
    import socket
    import threading
    import time

    import uvicorn

    from rekord.llm import providers
    from tests import fake_ollama
    fake_ollama.have[:] = ["qwen3:8b"]
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(fake_ollama.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(50):
        if srv.started:
            break
        time.sleep(0.1)
    try:
        s = {**config.load(), "llm": {**config.load()["llm"], "provider": "ollama",
                                     "ollama": {"base_url": f"http://127.0.0.1:{port}", "model": "qwen3:8b", "num_ctx": 32768}}}
        assert "".join(providers.stream(s, "Fasse zusammen.", [{"role": "user", "content": "Kurzes Gespräch."}])) == "OK qwen3:8b"
        body = fake_ollama.seen[-1]
        assert body["options"]["num_ctx"] == 8192 and body["keep_alive"] == providers.OLLAMA_KEEP_ALIVE
    finally:
        srv.should_exit = True


def test_analysis_runs_in_its_own_process_and_reports_errors(client, tmp_path):
    """The heavy work happens in `rekord --process-job` (low priority, memory back afterwards); its errors arrive here."""
    from rekord import jobs
    jobs.start()
    events = []
    jobs.subscribe(events.append)
    try:
        rid = db.create_recording("Kaputt", str(tmp_path / "gibts-nicht.m4a"))["id"]
        jobs.enqueue(rid)
        assert jobs.wait_idle(180)
    finally:
        jobs.unsubscribe(events.append)
    rec = db.get_recording(rid)
    mine = [e for e in events if e.get("id") == rid]
    assert rec["status"] == "error" and rec["error"] and "Code" not in rec["error"]  # the child's own message
    assert any(e.get("stage") == "Startet" for e in mine) and mine[-1]["type"] == "error"


def test_no_summary_of_the_half_finished_transcript(client, monkeypatch):
    """While the full analysis runs, the transcript is only the live one (with gaps): summarizing waits for it."""
    from rekord import jobs, pipeline, summarize
    rid = db.create_recording("Läuft noch", "/nirgends.m4a", status="processing")["id"]
    r = client.post(f"/api/recordings/{rid}/summaries", json={"template_id": "meeting"})
    assert r.status_code == 409 and "vormerken" in r.json()["detail"]
    assert client.post(f"/api/recordings/{rid}/summaries/later", json={"template_id": "meeting"}).json() == {"ok": True, "queued": True}
    order = []
    monkeypatch.setenv("REKORD_JOBS_INPROCESS", "1")
    monkeypatch.setattr(pipeline, "process", lambda r_, on_event=None: (order.append("analysis"), db.update_recording(r_, status="done")))
    monkeypatch.setattr(summarize, "generate", lambda r_, tid: order.append(f"summary:{tid}"))
    jobs.start()
    jobs.enqueue(rid)
    assert jobs.wait_idle(60)
    assert order == ["analysis", "summary:meeting"]  # on the complete transcript


def test_live_socket_passes_the_microphone_choice(client, monkeypatch):
    """Online "Nur Call-Ton" from the browser on this computer: the hub records the call without the microphone.
    From another device (iPhone) the call sound of THIS computer isn't offered – there the microphone stays on."""
    from rekord import live
    made = []

    class Fake:
        def __init__(self, emit, title, source, sr, participants, guests, meeting, call_audio, mic=True):
            self.emit, self.call_audio = emit, call_audio
            self.mic = mic or not call_audio
            self.call = object() if call_audio else None
            self.rid, self.title, self.notes, self.paused, self._closed = f"r{len(made)}", title, [], False, False
            made.append(self)

        def stop(self):
            self._closed = True
            self.emit({"type": "stopped", "id": self.rid})
            return self.rid

    monkeypatch.setattr(live, "LiveSession", Fake)

    def started(c, path, **ctl):
        with c.websocket_connect(path) as ws:
            ws.send_json({"type": "start", "sample_rate": 16000, "title": "Webinar", "meeting": "online", **ctl})
            ev = ws.receive_json()
            assert ev["type"] == "started", ev
            ws.send_json({"type": "stop"})
            return ev

    ev = started(client, "/ws/live", call_audio=True, mic=False)
    assert (made[-1].call_audio, made[-1].mic) == (True, False) and ev["mic"] is False and ev["call_audio"] is True
    ev = started(client, "/ws/live", call_audio=True)  # old clients: microphone on, as before
    assert made[-1].mic is True and ev["mic"] is True
    tok = config.load()["pair_token"]
    phone = TestClient(app, client=("192.168.1.77", 5000))
    ev = started(phone, f"/ws/live?token={tok}", call_audio=True, mic=False)
    assert (made[-1].call_audio, made[-1].mic) == (False, True) and ev["call_audio"] is False


def test_append_files_over_the_api(client, monkeypatch):
    from rekord import jobs
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append(rid))
    r = client.post("/api/recordings", files=[("files", ("teil1.wav", _wav(2.0), "audio/wav"))], data={"title": "Workshop"})
    rid = r.json()["items"][0]["id"]
    queued.clear()
    r = client.post(f"/api/recordings/{rid}/append", files=[("files", ("teil2.wav", _wav(1.5), "audio/wav"))])
    assert r.status_code == 200, r.text
    assert 1.4 < r.json()["added"] < 1.6 and 4.3 < r.json()["duration"] < 4.7  # 2 s + 1 s pause + 1.5 s
    assert queued == [rid]  # analysed again as a whole
    assert client.post(f"/api/recordings/{rid}/append", files=[("files", ("notiz.txt", b"x", "text/plain"))]).status_code == 400
    assert client.post("/api/recordings/gibtsnicht/append", files=[("files", ("a.wav", _wav(1), "audio/wav"))]).status_code == 404


def test_any_format_upload_and_video_stills_in_the_recording(client, monkeypatch, tmp_path):
    import sys
    from pathlib import Path

    from rekord import frames, jobs
    sys.path.insert(0, str(Path(__file__).parent))
    from media import slides_video
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": None)
    # an unknown ending with sound inside: accepted; without sound: refused
    r = client.post("/api/recordings", files=[("files", ("memo.weird", _wav(1.0), "application/octet-stream"))])
    assert r.status_code == 200, r.text
    r = client.post("/api/recordings", files=[("files", ("notiz.weird", b"kein ton", "application/octet-stream"))])
    assert r.status_code == 400 and "Kein Ton" in r.json()["detail"]
    # a video: its stills come with the recording, each with its line
    vid = slides_video(tmp_path / "call.mp4").read_bytes()
    rid = client.post("/api/recordings", files=[("files", ("call.mp4", vid, "video/mp4"))]).json()["items"][0]["id"]
    rec = db.get_recording(rid)
    assert frames.extract(rec["audio_path"], rid) == 3
    full = client.get(f"/api/recordings/{rid}").json()
    assert [f["t"] for f in full["frames"]] == [0.0, 5.0, 10.0] and full["frames"][0]["file"].startswith("file://")
    img = client.get(full["frames"][1]["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content[:2] == b"\xff\xd8"
    assert client.get(f"/api/recordings/{rid}/frames/..%2F..%2Fconfig.json").status_code == 404
    assert client.get(f"/api/recordings/{rid}/frames/x.jpg").status_code == 404
    client.delete(f"/api/recordings/{rid}")
    assert not frames.folder(rid).exists()  # gone with the recording


def test_documents_api(client, monkeypatch, tmp_path):
    """Unterlagen over the hub (the browser and the iPhone app): add, list, open, remove, switch corrections."""
    import media
    from rekord import jobs
    matched = []
    monkeypatch.setattr(jobs, "enqueue_context", matched.append)
    rec = db.create_recording("Kickoff", "", status="done")
    rid = rec["id"]
    sid = db.add_speaker(rid, "Emil", "#FF5A1F")
    db.replace_transcript(rid, [{"label": 0, "name": "Emil", "color": "#FF5A1F"}],
                          [{"start": 0, "end": 3, "label": 0, "text": "Das läuft über Sapir."}])
    del sid
    docx = media.docx(tmp_path / "Agenda.docx", ["Kassensystem: SumUp mit Zapier und Notion", "Zapier-Konto: Emil Boenke"])
    r = client.post(f"/api/recordings/{rid}/documents", files=[
        ("files", ("Agenda.docx", docx.read_bytes(), "application/octet-stream")),
        ("files", ("alt.ppt", b"\xd0\xcf", "application/octet-stream"))])
    assert r.status_code == 200
    body = r.json()
    assert [d["name"] for d in body["items"]] == ["Agenda.docx"] and "als PDF oder PPTX" in body["errors"][0]
    assert matched == [rid]
    full = client.get(f"/api/recordings/{rid}").json()
    assert full["documents"][0]["url"].endswith("/documents/Agenda.docx") and full["documents"][0]["words"] > 5
    assert client.get(full["documents"][0]["url"]).content == docx.read_bytes()
    assert client.get(f"/api/recordings/{rid}/documents/..%2Frekord.db").status_code == 404

    from rekord import context
    context.run(rid, {**config.load(), "llm": {"provider": "none"}})
    assert client.get(f"/api/recordings/{rid}").json()["segments"][0]["text"] == "Das läuft über Zapier."
    fixes = client.get(f"/api/recordings/{rid}/documents").json()["fixes"]
    assert fixes[0]["from"] == "Sapir" and fixes[0]["to"] == "Zapier"
    client.post(f"/api/recordings/{rid}/fixes", json={"from": "Sapir", "to": "Zapier", "on": False})
    assert client.get(f"/api/recordings/{rid}").json()["segments"][0]["text"] == "Das läuft über Sapir."
    client.post(f"/api/recordings/{rid}/fixes", json={"from": "Sapir", "to": "Zapier", "on": True})
    assert client.post(f"/api/recordings/{rid}/fixes/undo").json()["restored"] == 1
    assert client.post(f"/api/recordings/{rid}/fixes/rerun").json()["ok"]
    assert client.delete(f"/api/recordings/{rid}/documents/Agenda.docx").json()["items"] == []
    assert client.delete(f"/api/recordings/{rid}/documents/Agenda.docx").status_code == 404
    db.update_recording(rid, status="processing")
    assert client.post(f"/api/recordings/{rid}/fixes/rerun").status_code == 409
    only_bad = client.post(f"/api/recordings/{rid}/documents", files={"files": ("x.doc", b"\xd0", "application/octet-stream")})
    assert only_bad.status_code == 400
    db.update_recording(rid, status="done")


def test_upload_audio_with_its_documents(client, monkeypatch, tmp_path):
    from rekord import context, jobs
    queued = []
    monkeypatch.setattr(jobs, "enqueue", lambda rid, kind="process": queued.append((rid, [d["name"] for d in context.items(rid)])))
    r = client.post("/api/recordings", files=[("files", ("call.wav", _wav(), "audio/wav")),
                                              ("files", ("Agenda.txt", "Teilnehmer: Emil Boenke".encode(), "text/plain"))])
    rid = r.json()["items"][0]["id"]
    assert len(r.json()["items"]) == 1 and queued == [(rid, ["Agenda.txt"])]  # analysed with its Unterlagen already there
    only_docs = client.post("/api/recordings", files={"files": ("Agenda.txt", b"x", "text/plain")})
    assert only_docs.status_code == 400 and "Unterlagen" in only_docs.json()["detail"]


def test_cancel_and_delete_while_analysing(client, monkeypatch):
    from rekord import jobs
    rec = db.create_recording("Falsche Datei", "", status="processing")
    assert client.post(f"/api/recordings/{rec['id']}/cancel").json()["ok"]
    assert db.get_recording(rec["id"])["error"] == jobs.CANCELLED
    assert not client.post(f"/api/recordings/{rec['id']}/cancel").json()["ok"]
    rec2 = db.create_recording("Noch eine falsche", "", status="queued")
    stopped = []
    real = jobs.cancel
    monkeypatch.setattr(jobs, "cancel", lambda rid, wait=5.0: stopped.append(rid) or real(rid, wait))
    assert client.delete(f"/api/recordings/{rec2['id']}").json()["ok"]
    assert stopped == [rec2["id"]] and db.get_recording(rec2["id"]) is None
