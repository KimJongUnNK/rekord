"""HTTP + WebSocket hub. Serves the PWA (desktop + phone), the REST API and live streaming."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, audio, config, db, export, jobs, live, models, pipeline, summarize, updater
from .engines import asr
from .llm import providers, templates

log = logging.getLogger("rekord.server")
WEB = Path(__file__).parent / "web"
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".webm", ".mp4", ".mov", ".mkv", ".wma", ".amr", ".caf", ".3gp"}


# ------------------------------------------------------------------ lifecycle

def _recover() -> None:
    """A live session that died with the process: its WAV is still there -> process it."""
    for r in db.list_recordings():
        if r["status"] == "recording":
            wav = config.AUDIO_DIR / f"{r['id']}.wav"
            if wav.exists() and wav.stat().st_size > 44 + 32000:
                _fix_wav_header(wav)
                db.update_recording(r["id"], audio_path=str(wav))
                jobs.enqueue(r["id"])
            else:
                db.update_recording(r["id"], status="error", error="Aufnahme abgebrochen")


def _fix_wav_header(path: Path) -> None:
    import struct
    size = path.stat().st_size
    with open(path, "r+b") as f:
        f.seek(4)
        f.write(struct.pack("<I", size - 8))
        f.seek(40)
        f.write(struct.pack("<I", size - 44))


def _inbox_loop(stop: threading.Event) -> None:
    sizes: dict[Path, int] = {}
    while not stop.wait(4):
        if not config.load().get("inbox_enabled", True):
            continue
        try:
            for p in config.INBOX_DIR.iterdir():
                if p.suffix.lower() not in AUDIO_EXT or p.name.startswith("."):
                    continue
                sz = p.stat().st_size
                if sizes.get(p) != sz:  # still being written / synced
                    sizes[p] = sz
                    continue
                sizes.pop(p, None)
                rid = uuid.uuid4().hex[:12]
                dest = config.AUDIO_DIR / f"{rid}{p.suffix.lower()}"
                shutil.move(str(p), dest)
                db.create_recording(p.stem, str(dest), source="inbox", rec_id=rid)
                jobs.enqueue(rid)
                log.info("inbox: %s -> %s", p.name, rid)
        except Exception as e:  # noqa: BLE001
            log.warning("inbox: %s", e)
        finally:
            db.close()


_zc = None


def _advertise(port: int) -> None:
    global _zc
    try:
        from zeroconf import ServiceInfo, Zeroconf
        ips = [socket.inet_aton(ip) for ip in lan_ips()]
        if not ips:
            return
        info = ServiceInfo("_rekord._tcp.local.", f"REKORD {socket.gethostname()}._rekord._tcp.local.",
                           addresses=ips, port=port, properties={"v": __version__})
        _zc = Zeroconf()
        _zc.register_service(info)
    except Exception as e:  # noqa: BLE001
        log.info("bonjour off: %s", e)


def _warmup() -> None:
    """Load the speech models once in the background, so the first live recording starts instantly."""
    from .engines import voiceprint
    s = config.load()
    try:
        if models.installed(s["embedding_model"]):
            voiceprint.get_embedder(s["embedding_model"], 2)
        if s["asr_engine"] != "faster-whisper" and models.installed(s["asr_model"]):
            asr.get_engine(s)
    except Exception as e:  # noqa: BLE001 - loaded on first use instead
        log.info("warmup: %s", e)


def _auto_ai() -> None:
    from .llm import auto
    try:
        auto.autoconfigure()
    except Exception as e:  # noqa: BLE001 - best effort, the UI offers manual setup
        log.info("ai auto: %s", e)


def start_downloads() -> None:
    """Speech models: after the user chose where REKORD stores things (first start), otherwise right away."""
    missing = [m for m in models.ESSENTIAL + [config.load()["asr_model"]] if not models.installed(m)]
    if config.models_missing():
        return

    def prepare():
        for m in missing:
            try:
                models.download(m)
            except Exception as e:  # noqa: BLE001
                log.warning("download %s failed: %s", m, e)
        _warmup()
    threading.Thread(target=prepare, daemon=True, name="models").start()


def _cleanup_moved_home() -> None:
    """After a move at first start (nothing recorded yet) the old, empty default folder goes away."""
    marker = config.HOME / ".remove-old"
    if not marker.exists():
        return
    old = Path(marker.read_text("utf-8").strip())
    if (old / "MOVED-TO.txt").exists() and old != config.HOME:
        shutil.rmtree(old, ignore_errors=True)
    marker.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if config.home_missing():  # external drive not connected: only the UI runs and asks for it
        log.warning("Datenordner nicht gefunden: %s", config.HOME)
        yield
        return
    config.ensure_dirs()
    config.load()
    db.connect()
    _cleanup_moved_home()
    _recover()
    jobs.start()
    stop = threading.Event()
    threading.Thread(target=_inbox_loop, args=(stop,), daemon=True, name="inbox").start()
    port = getattr(app.state, "port", 8765)
    if getattr(app.state, "lan", False):
        threading.Thread(target=_advertise, args=(port,), daemon=True).start()
    cleanup = threading.Timer(10, updater.cleanup)  # leftovers of the last update (the old app version …)
    cleanup.daemon = True
    cleanup.start()
    if getattr(app.state, "auto_download", True):
        threading.Thread(target=updater.background_checks, args=(stop,), daemon=True, name="update-check").start()
        threading.Thread(target=_auto_ai, daemon=True, name="ai-auto").start()
        if config.load()["storage_chosen"]:
            start_downloads()
    yield
    stop.set()
    if _zc:
        _zc.close()


app = FastAPI(title="REKORD", version=__version__, lifespan=lifespan)


# ------------------------------------------------------------------ auth: localhost free, LAN needs the pairing token

def _is_local(host: str | None) -> bool:
    return host in ("127.0.0.1", "::1", "localhost", "testclient", None)


def _token_ok(req_token: str | None) -> bool:
    from . import pairing
    return pairing.token_ok(req_token)


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _color(value):
    """Colors end up in HTML/SVG attributes - only accept #RRGGBB."""
    if value is None:
        return None
    if not isinstance(value, str) or not _HEX.match(value):
        raise HTTPException(400, "Farbe muss #RRGGBB sein")
    return value.upper()


@app.middleware("http")
async def auth(request: Request, call_next):
    """This computer: everything. In the Wi-Fi: only the iPhone app (its key) – and only the API, never the
    interface: on the phone REKORD is the app, not a web page."""
    host = request.client.host if request.client else None
    if _is_local(host):
        return await call_next(request)
    path = request.url.path
    if path == "/api/pair/claim":  # the app trades the 6-digit code for its key
        return await call_next(request)
    if not (path.startswith("/api/") or path.startswith("/ws/")):
        return FileResponse(WEB / "pair.html", status_code=403)
    tok = request.headers.get("x-rekord-token") or request.query_params.get("token")
    if not _token_ok(tok):
        return JSONResponse({"detail": "Nicht gekoppelt – in der REKORD-App mit dem Code vom Computer koppeln"}, status_code=401)
    return await call_next(request)


def _ws_ok(ws: WebSocket) -> bool:
    host = ws.client.host if ws.client else None
    return _is_local(host) or _token_ok(ws.query_params.get("token") or ws.headers.get("x-rekord-token"))


# ------------------------------------------------------------------ static / PWA

app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def sw():
    return FileResponse(WEB / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/icons/{name}")
def icons(name: str):
    p = (WEB / "icons" / name).resolve()
    if p.parent != (WEB / "icons").resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ------------------------------------------------------------------ status & settings

def lan_ips() -> list[str]:
    """This computer's Wi-Fi/LAN addresses – the one with the default route first (QR codes use the first)."""
    primary, ips = None, set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.254.254.254", 1))
        primary = s.getsockname()[0]
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    rest = sorted(ip for ip in ips if not ip.startswith("127.") and ip != primary)
    return ([primary] if primary and not primary.startswith("127.") else []) + rest


@app.get("/api/status")
def status():
    s = config.load()
    return {
        "version": __version__,
        "ready": all(models.installed(m) for m in models.ESSENTIAL) and (
            s["asr_engine"] == "faster-whisper" or models.installed(s["asr_model"])),
        "models": models.status(),
        "provider": s["llm"]["provider"],
        "ai_ready": providers.configured(s)[0],
        "ai_problem": providers.configured(s)[1],
        "provider_name": providers.PROVIDERS.get(s["llm"]["provider"]),
        "model": providers.model_name(s),
        "jobs_pending": jobs.pending(),
        "live": live.active(),
        "faster_whisper": asr.faster_whisper_available(),
        "home": str(config.HOME),
        "inbox": str(config.INBOX_DIR),
        "python": sys.executable,
        "capture": _capture_caps(),
        "window": _desktop_window(),
        "exe": sys.executable if getattr(sys, "frozen", False) else "",
        "update": updater.brief(),
        "storage_missing": str(config.HOME) if config.home_missing() else "",
        "models_missing": str(config.MODELS_DIR) if config.models_missing() else "",
        "storage_chosen": s["storage_chosen"], "welcome_done": s["welcome_done"],
        # packaged app (PyInstaller): the binary itself takes "mcp"; source install: python -m rekord mcp
        "mcp_command": [sys.executable, "mcp"] if getattr(sys, "frozen", False) else [sys.executable, "-m", "rekord", "mcp"],
    }


def _desktop_window() -> bool:
    """Does this process show REKORD's window (a second start brings it to the front instead of opening another)?"""
    mod = sys.modules.get("rekord.desktop")
    return bool(mod and mod.window_open)


_caps: tuple[float, dict] | None = None


def _capture_caps() -> dict:
    """Can this computer record the call sound? Asked once; a "no" is asked again after a minute (sound system started later)."""
    global _caps
    if _caps is None or (not _caps[1]["system_audio"] and time.time() - _caps[0] > 60):
        from . import capture
        try:
            caps = capture.available()
        except Exception as e:  # noqa: BLE001
            caps = {"system_audio": False, "reason": str(e)}
        _caps = (time.time(), caps)
    return _caps[1]


@app.get("/api/settings")
def get_settings():
    return config.public() | {"providers": providers.PROVIDERS}


@app.put("/api/settings")
async def put_settings(request: Request):
    patch = await request.json()
    patch.pop("pair_token", None)
    patch.pop("devices", None)
    for p in ("anthropic", "openai", "compatible"):
        k = patch.get("llm", {}).get(p, {})
        if isinstance(k.get("api_key"), str) and k["api_key"].startswith("••••"):
            k.pop("api_key")
        k.pop("has_key", None)
    patch.pop("providers", None)
    s = config.save(patch)
    asr._sherpa.cache_clear()
    asr._faster.cache_clear()
    for p in ("openai", "compatible"):  # key or server entered, no model yet → pick one (no "Laden → auswählen")
        changed = patch.get("llm", {}).get(p, {})
        if (changed.get("api_key") or changed.get("base_url")) and not s["llm"][p].get("model"):
            m = await asyncio.to_thread(providers.fill_model, s, p)
            if m:
                config.save({"llm": {p: {"model": m}}})
    return config.public()


@app.post("/api/shutdown")
def shutdown(request: Request):
    """Quit the hub (needed when it runs in the background without a window). Only from this computer."""
    if not _is_local(request.client.host if request.client else None):
        raise HTTPException(403, "Nur am Computer selbst möglich")
    if live.active():
        raise HTTPException(409, "Es läuft gerade eine Live-Aufnahme")
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"ok": True}


@app.post("/api/window/focus")
def window_focus(request: Request):
    """REKORD was started a second time: bring the open window to the front instead of opening another one."""
    _local_only(request)
    from . import desktop
    if not desktop.focus():
        raise HTTPException(404, "Kein Fenster offen")
    return {"ok": True}


# ------------------------------------------------------------------ updates (the new version replaces the old one)

@app.get("/api/update")
def update_info():
    return updater.info()


@app.post("/api/update/check")
async def update_check():
    return await asyncio.to_thread(updater.check, True)


@app.post("/api/update/install")
def update_install(request: Request):
    _local_only(request)
    try:
        updater.install()
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return updater.info()


@app.post("/api/settings/rotate-token")
def rotate_token(request: Request):
    """„Alle Geräte trennen“: every paired device has to pair again."""
    from . import pairing
    _local_only(request)
    pairing.disconnect_all()
    return {"ok": True}


@app.post("/api/pair/claim")
async def pair_claim(request: Request):
    """A device enters the 6-digit code → it gets its own key (open endpoint, rate limited)."""
    from . import pairing
    b = await request.json()
    try:
        token = pairing.claim(str(b.get("code", "")), request.client.host if request.client else "?",
                              b.get("name") or pairing.device_name(request.headers.get("user-agent", "")))
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    return {"token": token}


@app.post("/api/pair/code")
def pair_new_code(request: Request):
    from . import pairing
    _local_only(request)
    return pairing.new_code()


@app.delete("/api/pair/devices/{device_id}")
def pair_remove(device_id: str, request: Request):
    from . import pairing
    _local_only(request)
    if not pairing.remove(device_id):
        raise HTTPException(404)
    return {"ok": True}


@app.get("/api/models")
def get_models():
    return models.status()


@app.post("/api/models/{mid}/download")
def dl_model(mid: str):
    if mid not in models.REGISTRY:
        raise HTTPException(404)
    models.download_async(mid)
    return {"ok": True}


@app.delete("/api/models/{mid}")
def del_model(mid: str):
    if mid not in models.REGISTRY:
        raise HTTPException(404)
    models.delete(mid)
    return {"ok": True}


@app.get("/api/llm/models")
def llm_models(provider: str):
    try:
        return {"models": providers.list_models(config.load(), provider)}
    except providers.LLMError as e:
        return {"models": [], "error": str(e)}


@app.get("/api/ollama")
def ollama_status():
    from .llm import ollama
    return ollama.status(config.load()["llm"]["ollama"].get("base_url"))


@app.post("/api/ollama/start")
async def ollama_start():
    from .llm import ollama
    ok = await asyncio.to_thread(ollama.start, config.load()["llm"]["ollama"].get("base_url"))
    return {"ok": ok}


@app.post("/api/ollama/pull")
async def ollama_pull(request: Request):
    from .llm import ollama
    b = await request.json()
    model = b["model"].strip()
    if not re.match(r"^[\w.\-/:]+$", model):
        raise HTTPException(400, "Ungültiger Modellname")
    use = bool(b.get("use"))

    def done(m: str):  # "laden & verwenden", or the first local model → use it right away
        s = config.load()
        if use:
            _use_ollama(m)
        elif s["llm"]["provider"] == "ollama" and not s["llm"]["ollama"].get("model"):
            config.save({"llm": {"ollama": {"model": m}}})
    ollama.pull(model, config.load()["llm"]["ollama"].get("base_url"), on_done=done)
    return {"ok": True}


@app.post("/api/ollama/best")
async def ollama_best(request: Request):
    """„Bestes Modell verwenden“: the strongest model this computer runs well – downloaded if needed, then used."""
    from .llm import ollama
    _local_only(request)
    base = config.load()["llm"]["ollama"].get("base_url")
    st = await asyncio.to_thread(ollama.status, base)
    best = st["best"]
    if best in {m["name"] for m in st["models"]} | {m["name"].removesuffix(":latest") for m in st["models"]}:
        _use_ollama(best)
        return {"model": best, "pulling": False}
    ollama.pull(best, base, on_done=_use_ollama)
    return {"model": best, "pulling": True}


def _use_ollama(model: str) -> None:
    config.save({"llm": {"provider": "ollama", "ollama": {"model": model}}})


@app.delete("/api/ollama/models/{name:path}")
async def ollama_delete(name: str, request: Request):
    """Remove a downloaded local model; if it was the one in use, switch to another one that is there."""
    from .llm import ollama
    _local_only(request)
    if not re.match(r"^[\w.\-/:]+$", name):
        raise HTTPException(400, "Ungültiger Modellname")
    base = config.load()["llm"]["ollama"].get("base_url")
    try:
        await asyncio.to_thread(ollama.delete, name, base)
    except (RuntimeError, httpx.HTTPError) as e:
        raise HTTPException(400, str(e))
    s = config.load()
    if s["llm"]["ollama"].get("model") == name:
        left = (await asyncio.to_thread(ollama.status, base))["models"]
        config.save({"llm": {"ollama": {"model": ollama.pick_installed(left) or ""}}})
    return {"ok": True, "model": config.load()["llm"]["ollama"].get("model", "")}


@app.post("/api/ollama/setup")
async def ollama_setup(request: Request):
    """One click: install Ollama if needed, start it, download a model that fits this computer, use it."""
    from .llm import ollama
    body = await request.json() if int(request.headers.get("content-length") or 0) else {}
    model = (body.get("model") or "").strip() or None
    if model and not re.match(r"^[\w.\-/:]+$", model):
        raise HTTPException(400, "Ungültiger Modellname")
    if not _is_local(request.client.host if request.client else None) and not ollama.binary():
        raise HTTPException(403, "Ollama kann nur am Computer selbst installiert werden")
    config.save({"llm": {"provider": "ollama"}})
    ollama.setup(config.load()["llm"]["ollama"].get("base_url"), model, on_ready=_use_ollama)
    return ollama.setup_state()


@app.post("/api/llm/test")
def llm_test():
    t0 = time.time()
    try:
        out = providers.test(config.load())
        return {"ok": True, "reply": out, "ms": int((time.time() - t0) * 1000)}
    except providers.LLMError as e:
        return {"ok": False, "error": str(e)}


# ------------------------------------------------------------------ one-click integrations (only on this computer)

def _local_only(request: Request) -> None:
    if not _is_local(request.client.host if request.client else None):
        raise HTTPException(403, "Nur am Computer selbst möglich")


@app.get("/api/integrations")
async def integrations_status():
    from . import integrations, system
    desktop, code, fw = await asyncio.gather(asyncio.to_thread(integrations.claude_desktop),
                                             asyncio.to_thread(integrations.claude_code),
                                             asyncio.to_thread(system.firewall))
    ok, why = system.autostart_supported()
    return {"claude_desktop": desktop, "claude_code": code, "firewall": fw, "platform": sys.platform,
            "autostart": {"supported": ok, "reason": why, "enabled": system.autostart_enabled()}}


def _run_integration(fn, *args):
    try:
        return fn(*args)
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/integrations/claude-desktop")
async def connect_desktop(request: Request):
    from . import integrations
    _local_only(request)
    return await asyncio.to_thread(_run_integration, integrations.connect_claude_desktop)


@app.post("/api/integrations/claude-desktop/restart")
async def restart_desktop(request: Request):
    from . import integrations
    _local_only(request)
    return {"ok": await asyncio.to_thread(_run_integration, integrations.restart_claude_desktop)}


@app.post("/api/integrations/claude-code")
async def connect_code(request: Request):
    from . import integrations
    _local_only(request)
    return await asyncio.to_thread(_run_integration, integrations.connect_claude_code)


@app.post("/api/integrations/firewall")
async def open_firewall(request: Request):
    from . import system
    _local_only(request)
    return await asyncio.to_thread(_run_integration, system.open_firewall)


@app.post("/api/integrations/autostart")
async def autostart(request: Request):
    from . import system
    _local_only(request)
    on = bool((await request.json()).get("enabled"))
    return {"enabled": await asyncio.to_thread(_run_integration, system.set_autostart, on)}


# ------------------------------------------------------------------ storage: where data and models live

@app.get("/api/storage")
async def storage_info(request: Request):
    from . import storage
    out = storage.info()
    if _is_local(request.client.host if request.client else None):
        out["drives"] = await asyncio.to_thread(storage.drives)
        out["usage"] = await asyncio.to_thread(storage.usage)
        out["suggest"] = {d["path"]: storage.suggest(d["path"]) for d in out["drives"]}
    return out


@app.post("/api/storage/choose")
async def storage_choose(request: Request):
    """First start (before any big download): where should REKORD keep everything? Same folder → just go."""
    from . import storage
    _local_only(request)
    b = await request.json()
    home = Path(b.get("home") or config.HOME).expanduser()
    models_dir = (b.get("models") or "").strip()
    try:
        if home.resolve() != config.HOME.resolve():
            if not home.is_absolute():
                raise RuntimeError("Bitte einen vollständigen Pfad angeben.")
            fresh = not db.list_recordings()
            if models_dir:
                config.save({"models_dir": models_dir if Path(models_dir) != home / "models" else ""})
            out = await asyncio.to_thread(storage.move_home, str(home))
            if fresh:
                (home / ".remove-old").parent.mkdir(parents=True, exist_ok=True)
                (home / ".remove-old").write_text(str(config.HOME), "utf-8")
            return out
        patch = {"storage_chosen": True}
        if models_dir and Path(models_dir).expanduser() != config.MODELS_DIR:
            if not Path(models_dir).is_absolute():
                raise RuntimeError("Bitte einen vollständigen Pfad angeben.")
            Path(models_dir).expanduser().mkdir(parents=True, exist_ok=True)
            patch["models_dir"] = "" if Path(models_dir).expanduser() == config.HOME / "models" else models_dir
        config.save(patch)
        if getattr(app.state, "auto_download", True):
            start_downloads()
        return storage.job()
    except (RuntimeError, OSError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/storage/move")
async def storage_move(request: Request):
    """Later: move the data folder (ends with a restart) or the models folder (incl. local AI models)."""
    from . import storage
    _local_only(request)
    b = await request.json()
    target = (b.get("target") or "").strip()
    if not target or not Path(target).expanduser().is_absolute():
        raise HTTPException(400, "Bitte einen vollständigen Ordnerpfad angeben.")
    try:
        if b.get("what") == "models":
            return await asyncio.to_thread(storage.move_models, target, bool(b.get("ollama", True)))
        return await asyncio.to_thread(storage.move_home, target)
    except (RuntimeError, OSError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/storage/missing")
async def storage_missing(request: Request):
    """Drive is back → restart into it; or give up on it and start fresh on this computer."""
    from . import storage
    _local_only(request)
    action = (await request.json()).get("action")
    if action == "forget":
        storage.forget_missing_home()
        return {"ok": True}
    if config.HOME.exists() or config.HOME.parent.exists():
        storage.schedule_restart(0.5)
        return {"ok": True, "found": True}
    return {"ok": True, "found": False}


@app.get("/api/pair")
def pair(request: Request):
    """For "iPhone & Geräte": the QR code for the iPhone app, the 6-digit code, the paired devices."""
    import qrcode
    import qrcode.image.svg

    from . import pairing
    s = config.load()
    port = getattr(app.state, "port", None) or request.url.port or 8765
    urls = [f"http://{ip}:{port}" for ip in lan_ips()]
    payload = json.dumps({"rekord": 1, "urls": urls, "token": s["pair_token"]})
    img = qrcode.make(payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO()
    img.save(buf)
    qr = qrcode.QRCode(border=0)  # the same code as rows of 0/1 – the desktop window draws it itself
    qr.add_data(payload)
    qr.make(fit=True)
    rows = ["".join("1" if c else "0" for c in row) for row in qr.get_matrix()]
    return {"urls": urls, "qr_app": buf.getvalue().decode(), "qr_rows": rows, "code": pairing.current_code(),
            "devices": pairing.devices(), "lan": bool(getattr(app.state, "lan", False))}


# ------------------------------------------------------------------ recordings

def _full(rid: str) -> dict:
    rec = db.get_recording(rid)
    if rec is None:
        raise HTTPException(404, "Aufnahme nicht gefunden")
    rec["speakers"] = db.list_speakers(rid)
    rec["segments"] = db.list_segments(rid)
    rec["summaries"] = db.list_summaries(rid)
    return rec


@app.get("/api/recordings")
def recordings(q: str = "", folder: str | None = None):
    return {"items": db.list_recordings(q=q, folder=folder), "folders": db.folders()}


@app.post("/api/recordings")
async def upload(files: list[UploadFile] = File(...), title: str = Form(""), highlights: str = Form("[]"),
                 source: str = Form("import"), folder: str = Form(""), participants: str = Form("")):
    out = []
    for f in files:
        ext = Path(f.filename or "a.webm").suffix.lower() or ".webm"
        if ext not in AUDIO_EXT:
            raise HTTPException(400, f"Format {ext} nicht unterstützt")
        rid = uuid.uuid4().hex[:12]
        dest = config.AUDIO_DIR / f"{rid}{ext}"
        with open(dest, "wb") as w:
            while chunk := await f.read(1 << 20):
                w.write(chunk)
        name = title if (title and len(files) == 1) else Path(f.filename or "Aufnahme").stem
        rec = db.create_recording(name or time.strftime("Aufnahme %d.%m.%Y %H:%M"), str(dest), source=source,
                                  highlights=json.loads(highlights or "[]"), rec_id=rid)
        if folder:
            db.update_recording(rid, folder=folder)
        if participants:
            db.update_recording(rid, participants=json.loads(participants))
        jobs.enqueue(rid)
        out.append(rec)
    return {"items": out}


@app.get("/api/recordings/{rid}")
def recording(rid: str):
    return _full(rid)


@app.patch("/api/recordings/{rid}")
async def patch_recording(rid: str, request: Request):
    body = await request.json()
    if "title" in body:
        body["title_locked"] = 1
    rec = db.update_recording(rid, **body)
    if rec is None:
        raise HTTPException(404)
    return rec


@app.delete("/api/recordings/{rid}")
def delete_recording(rid: str):
    rec = db.get_recording(rid)
    if rec is None:
        raise HTTPException(404)
    if rec.get("audio_path"):
        Path(rec["audio_path"]).unlink(missing_ok=True)
    db.delete_recording(rid)
    return {"ok": True}


@app.post("/api/recordings/{rid}/reprocess")
def reprocess(rid: str):
    if db.get_recording(rid) is None:
        raise HTTPException(404)
    jobs.enqueue(rid)
    return {"ok": True}


@app.get("/api/recordings/{rid}/audio")
def rec_audio(rid: str):
    rec = db.get_recording(rid)
    if rec is None or not rec.get("audio_path") or not Path(rec["audio_path"]).exists():
        raise HTTPException(404)
    return FileResponse(rec["audio_path"])


@app.get("/api/recordings/{rid}/export/{fmt}")
def export_rec(rid: str, fmt: str):
    if fmt not in export.FORMATS or db.get_recording(rid) is None:
        raise HTTPException(404)
    mime, fn = export.FORMATS[fmt]
    try:
        data = fn(rid)
    except ImportError:
        raise HTTPException(400, "DOCX braucht: pip install python-docx")
    title = "".join(c for c in db.get_recording(rid)["title"] if c.isalnum() or c in " -_").strip() or rid
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{title}.{fmt}"'})


@app.post("/api/recordings/{rid}/find_replace")
async def find_replace(rid: str, request: Request):
    b = await request.json()
    n = db.find_replace(rid, b["find"], b.get("replace", ""))
    if b.get("speakers"):
        for sp in db.list_speakers(rid):
            if sp["name"] == b["find"]:
                db.update_speaker(sp["id"], name=b.get("replace", ""))
                n += 1
    return {"changed": n}


@app.patch("/api/segments/{sid}")
async def patch_segment(sid: int, request: Request):
    b = await request.json()
    db.update_segment(sid, text=b.get("text"), speaker_id=b.get("speaker_id"))
    return {"ok": True}


@app.post("/api/segments/{sid}/assign")
async def assign_segment(sid: int, request: Request):
    """"Wer sagt das?" – move one line to a person; with remember its audio trains that voice."""
    b = await request.json()
    name = (b.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Name fehlt")
    try:
        return await asyncio.to_thread(pipeline.assign_segment, sid, name, bool(b.get("remember", True)), bool(b.get("whole_voice")))
    except KeyError:
        raise HTTPException(404)


@app.patch("/api/speakers/{sid}")
async def patch_speaker(sid: int, request: Request):
    b = await request.json()
    sp = db.get_speaker(sid)
    if sp is None:
        raise HTTPException(404)
    name = (b.get("name") or sp["name"]).strip()
    if b.get("remember"):
        try:
            prof = await asyncio.to_thread(pipeline.remember_speaker, sp["recording_id"], sid, name)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"ok": True, "profile": prof}
    db.update_speaker(sid, name=name, **({"color": _color(b["color"])} if b.get("color") else {}))
    return {"ok": True}


@app.post("/api/recordings/{rid}/speakers/merge")
async def merge(rid: str, request: Request):
    b = await request.json()
    db.merge_speakers(rid, int(b["source"]), int(b["target"]))
    return {"ok": True}


@app.post("/api/recordings/{rid}/reidentify")
async def reidentify(rid: str):
    return {"renamed": await asyncio.to_thread(pipeline.reidentify, rid)}


# ------------------------------------------------------------------ people (voice profiles)

@app.get("/api/profiles")
def profiles():
    return {"items": db.list_profiles()}


@app.patch("/api/profiles/{pid}")
async def patch_profile(pid: int, request: Request):
    b = await request.json()
    color = _color(b.get("color"))
    name = (b.get("name") or "").strip() or None
    db.update_profile(pid, name=name, color=color)
    if color:
        with db.tx() as c:
            c.execute("UPDATE speakers SET color=? WHERE profile_id=?", (color, pid))
    return db.get_profile(pid)


@app.delete("/api/profiles/{pid}")
def delete_profile(pid: int):
    db.delete_profile(pid)
    return {"ok": True}


@app.post("/api/profiles/enroll")
async def enroll(name: str = Form(...), file: UploadFile = File(...), mode: str = Form("read")):
    """mode "read" = the person read their text, "free" = someone just talked (other voices in between are left out)."""
    ext = Path(file.filename or "a.webm").suffix or ".webm"
    tmp = config.HOME / f"enroll-{uuid.uuid4().hex[:6]}{ext}"
    tmp.write_bytes(await file.read())
    try:
        prof = await asyncio.to_thread(pipeline.enroll_from_audio, name.strip(), str(tmp), "free" if mode == "free" else "read")
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp.unlink(missing_ok=True)
    return prof


@app.get("/api/recordings/{rid}/voices")
def recording_voices(rid: str):
    """Every voice of a recording – "Aus einer Aufnahme lernen" picks one of them."""
    if db.get_recording(rid) is None:
        raise HTTPException(404)
    return {"items": pipeline.recording_voices(rid)}


@app.post("/api/profiles/learn")
async def learn_voice(request: Request):
    """Learn a voice from a recording as a person: {recording_id, speaker_id, voice, name}."""
    b = await request.json()
    try:
        prof = await asyncio.to_thread(pipeline.learn_voice, str(b["recording_id"]), int(b["speaker_id"]),
                                       None if b.get("voice") is None else int(b["voice"]), str(b.get("name", "")))
    except (KeyError, StopIteration) as e:
        raise HTTPException(404, "Stimme nicht gefunden") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return prof


# ------------------------------------------------------------------ templates & summaries

@app.get("/api/templates")
def get_templates():
    return {"items": templates.all_templates()}


@app.post("/api/templates")
async def save_template(request: Request):
    b = await request.json()
    if b.get("id") in templates.BY_ID:
        b["id"] = None  # editing a built-in creates a custom copy
    tid = db.save_template(b.get("id"), b["name"], b["prompt"], b.get("category") or "Eigene", b.get("description", ""))
    return templates.get(tid)


@app.delete("/api/templates/{tid}")
def del_template(tid: str):
    db.delete_template(tid)
    return {"ok": True}


ERR = "\u0000ERROR:"


def _stream_text(gen_factory, on_done=None):
    """Run a blocking LLM generator in a thread, forward chunks to the client as they arrive."""
    async def agen():
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        done = object()

        def work():
            out = []
            try:
                for d in gen_factory():
                    out.append(d)
                    loop.call_soon_threadsafe(q.put_nowait, d)
                if on_done:
                    on_done("".join(out))
            except Exception as e:  # noqa: BLE001
                loop.call_soon_threadsafe(q.put_nowait, f"{ERR}{e}")
            finally:
                db.close()
                loop.call_soon_threadsafe(q.put_nowait, done)

        threading.Thread(target=work, daemon=True).start()
        while (item := await q.get()) is not done:
            yield item
    return StreamingResponse(agen(), media_type="text/plain; charset=utf-8", headers={"X-Accel-Buffering": "no"})


ANALYZING = ("Die Aufnahme wird gerade noch genau ausgewertet – erst danach ist das Transkript vollständig. "
             "Die Zusammenfassung lässt sich vormerken und entsteht dann automatisch.")


@app.post("/api/recordings/{rid}/summaries/later")
async def summarize_rec_later(rid: str, request: Request):
    """Summarize as soon as the full analysis is done (asked for while it still runs)."""
    b = await request.json()
    tid = b.get("template_id", "auto")
    templates.get(tid)  # unknown template → 500 like the direct way
    if db.get_recording(rid) is None:
        raise HTTPException(404, "Aufnahme nicht gefunden")
    return {"ok": True, "queued": jobs.summarize_later(rid, tid)}


@app.post("/api/recordings/{rid}/summaries")
async def summarize_rec(rid: str, request: Request):
    b = await request.json()
    tid = b.get("template_id", "auto")
    tpl = templates.get(tid)
    rec = db.get_recording(rid)
    if rec is not None and rec.get("status") in ("queued", "processing", "recording"):
        # the live transcript has gaps; a summary of it wouldn't match what was said
        raise HTTPException(409, ANALYZING)
    s = config.load()

    def save(content: str):
        content = content.strip()
        if content:
            db.add_summary(rid, tid, tpl["name"], content, s["llm"]["provider"], providers.model_name(s))
            summarize.maybe_title(rid, content)
    return _stream_text(lambda: summarize.generate_stream(rid, tid), save)


@app.patch("/api/summaries/{sid}")
async def patch_summary(sid: int, request: Request):
    db.update_summary(sid, (await request.json())["content"])
    return {"ok": True}


@app.delete("/api/summaries/{sid}")
def del_summary(sid: int):
    db.delete_summary(sid)
    return {"ok": True}


@app.post("/api/recordings/{rid}/ask")
async def ask_rec(rid: str, request: Request):
    q = (await request.json())["question"]
    return _stream_text(lambda: summarize.ask_recording_stream(rid, q))


@app.get("/api/chat/{scope}")
def chat(scope: str):
    return {"items": db.list_chat(scope)}


@app.delete("/api/chat/{scope}")
def clear_chat(scope: str):
    db.clear_chat(scope)
    return {"ok": True}


@app.post("/api/ask")
async def ask_all(request: Request):
    q = (await request.json())["question"]
    return _stream_text(lambda: summarize.ask_all_stream(q))


@app.get("/api/search")
def search(q: str):
    return {"items": db.search_segments(q, limit=60)}


# ------------------------------------------------------------------ websockets

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    if not _ws_ok(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def listener(ev):
        loop.call_soon_threadsafe(q.put_nowait, ev)
    jobs.subscribe(listener)
    try:
        while True:
            ev = await q.get()
            await ws.send_json(ev)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        jobs.unsubscribe(listener)


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    if not _ws_ok(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    loop = asyncio.get_running_loop()
    out: asyncio.Queue = asyncio.Queue()
    sess: live.LiveSession | None = None

    def emit(ev):
        loop.call_soon_threadsafe(out.put_nowait, ev)

    async def sender():
        while True:
            ev = await out.get()
            await ws.send_json(ev)
            if ev.get("type") == "stopped":
                return

    send_task = asyncio.create_task(sender())
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if sess is not None:
                    data = msg["bytes"]
                    await asyncio.to_thread(sess.feed_pcm16, data)
                continue
            ctl = json.loads(msg.get("text") or "{}")
            kind = ctl.get("type")
            if kind == "start" and sess is None:
                # the call sound of THIS computer: only for the app/browser on the computer itself
                here = _is_local(ws.client.host if ws.client else None)
                try:
                    sess = await asyncio.to_thread(live.LiveSession, emit, ctl.get("title", ""), ctl.get("source", "live"),
                                                   int(ctl.get("sample_rate", 16000)), ctl.get("participants") or [],
                                                   int(ctl.get("guests", 0) or 0), ctl.get("meeting") or "person",
                                                   here and bool(ctl.get("call_audio")))
                except Exception as e:  # noqa: BLE001
                    await ws.send_json({"type": "error", "error": f"Live-Start fehlgeschlagen: {e}"})
                    continue
                live.register(sess)
                emit({"type": "started", "id": sess.rid, "title": sess.title,
                      "call_audio": sess.call is not None, "notes": sess.notes})
                emit({"type": "speakers", "items": []})
            elif sess is None:
                continue
            elif kind == "highlight":
                sess.highlight()
            elif kind == "name_speaker":
                await asyncio.to_thread(sess.name_speaker, int(ctl["key"]), ctl.get("name", ""))
            elif kind == "pause":
                sess.paused = True
                emit({"type": "paused"})
            elif kind == "resume":
                sess.paused = False
                emit({"type": "resumed"})
            elif kind == "stop":
                await asyncio.to_thread(sess.stop)
                break
    except WebSocketDisconnect:
        pass
    finally:
        if sess is not None:
            if not sess._closed:
                await asyncio.to_thread(sess.stop)  # connection lost: keep what we have
            live.unregister(sess.rid)
        try:
            await asyncio.wait_for(send_task, timeout=5)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            send_task.cancel()
        try:
            await ws.close()
        except RuntimeError:
            pass
