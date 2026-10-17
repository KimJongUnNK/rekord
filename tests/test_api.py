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


def test_pairing_qr(client):
    p = client.get("/api/pair").json()
    assert p["token"] == config.load()["pair_token"] and p["qr_app"].lstrip().startswith("<?xml")


def test_lan_requires_token(client):
    lan = TestClient(app, client=("192.168.1.50", 5000))
    assert lan.get("/api/status").status_code == 401
    assert "koppeln" in lan.get("/").text.lower()
    tok = config.load()["pair_token"]
    assert lan.get("/api/status", headers={"X-Rekord-Token": tok}).status_code == 200
    r = lan.get(f"/?token={tok}")
    assert r.status_code == 200 and "rekord_token" in r.headers.get("set-cookie", "")
    assert lan.get("/manifest.webmanifest").status_code == 200  # PWA assets stay public
    fresh = TestClient(app, client=("192.168.1.51", 5000))  # no cookie, no token
    with pytest.raises(Exception):
        with fresh.websocket_connect("/ws/events"):
            pass
    with lan.websocket_connect("/ws/events"):  # paired via cookie → allowed
        pass


def test_shutdown_only_from_this_computer(client, monkeypatch):
    lan = TestClient(app, client=("192.168.1.60", 5000))
    tok = config.load()["pair_token"]
    assert lan.post("/api/shutdown", headers={"X-Rekord-Token": tok}).status_code == 403
    import rekord.server as srv
    fired = []
    monkeypatch.setattr(srv.threading, "Timer", lambda d, fn: type("T", (), {"start": lambda self: fired.append(d)})())
    assert client.post("/api/shutdown").json()["ok"] and fired == [0.5]
