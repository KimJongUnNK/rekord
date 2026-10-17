"""HTTP + WebSocket hub. Serves the PWA (desktop + phone), the REST API and live streaming."""
from __future__ import annotations

import asyncio
import hmac
import io
import json
import logging
import os
import re
import shutil
import socket
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, audio, config, db, export, jobs, live, models, pipeline, summarize
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    config.load()
    db.connect()
    _recover()
    jobs.start()
    stop = threading.Event()
    threading.Thread(target=_inbox_loop, args=(stop,), daemon=True, name="inbox").start()
    port = getattr(app.state, "port", 8765)
    if getattr(app.state, "lan", False):
        threading.Thread(target=_advertise, args=(port,), daemon=True).start()
    missing = [m for m in models.ESSENTIAL + [config.load()["asr_model"]] if not models.installed(m)]
    if missing and getattr(app.state, "auto_download", True):
        def dl():
            for m in missing:
                try:
                    models.download(m)
                except Exception as e:  # noqa: BLE001
                    log.warning("download %s failed: %s", m, e)
        threading.Thread(target=dl, daemon=True, name="models").start()
    yield
    stop.set()
    if _zc:
        _zc.close()


app = FastAPI(title="REKORD", version=__version__, lifespan=lifespan)


# ------------------------------------------------------------------ auth: localhost free, LAN needs the pairing token

def _is_local(host: str | None) -> bool:
    return host in ("127.0.0.1", "::1", "localhost", "testclient", None)


def _token_ok(req_token: str | None) -> bool:
    return bool(req_token) and hmac.compare_digest(req_token.encode(), config.load()["pair_token"].encode())


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
    host = request.client.host if request.client else None
    path = request.url.path
    open_paths = path in ("/manifest.webmanifest", "/sw.js", "/pair") or path.startswith("/static/") or path.startswith("/icons/")
    tok = request.headers.get("x-rekord-token") or request.query_params.get("token") or request.cookies.get("rekord_token")
    if not _is_local(host) and not open_paths and not _token_ok(tok):
        if path == "/" or not path.startswith("/api"):
            return FileResponse(WEB / "pair.html")
        return JSONResponse({"detail": "Pairing-Token fehlt"}, status_code=401)
    resp = await call_next(request)
    if request.query_params.get("token") and _token_ok(request.query_params.get("token")):
        resp.set_cookie("rekord_token", request.query_params["token"], max_age=3600 * 24 * 365, httponly=True, samesite="lax")
    return resp


def _ws_ok(ws: WebSocket) -> bool:
    host = ws.client.host if ws.client else None
    return _is_local(host) or _token_ok(ws.query_params.get("token") or ws.headers.get("x-rekord-token")
                                        or ws.cookies.get("rekord_token"))


# ------------------------------------------------------------------ static / PWA

app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


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
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.254.254.254", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


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
    }


@app.get("/api/settings")
def get_settings():
    return config.public() | {"providers": providers.PROVIDERS}


@app.put("/api/settings")
async def put_settings(request: Request):
    patch = await request.json()
    patch.pop("pair_token", None)
    for p in ("anthropic", "openai", "compatible"):
        k = patch.get("llm", {}).get(p, {})
        if isinstance(k.get("api_key"), str) and k["api_key"].startswith("••••"):
            k.pop("api_key")
        k.pop("has_key", None)
    patch.pop("providers", None)
    config.save(patch)
    asr._sherpa.cache_clear()
    asr._faster.cache_clear()
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


@app.post("/api/settings/rotate-token")
def rotate_token():
    import secrets
    config.save({"pair_token": secrets.token_urlsafe(18)})
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


@app.post("/api/llm/test")
def llm_test():
    t0 = time.time()
    try:
        out = providers.test(config.load())
        return {"ok": True, "reply": out, "ms": int((time.time() - t0) * 1000)}
    except providers.LLMError as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/pair")
def pair(request: Request):
    import qrcode
    import qrcode.image.svg
    s = config.load()
    scheme = request.url.scheme
    port = request.url.port or (443 if scheme == "https" else 80)
    urls = [f"{scheme}://{ip}:{port}" for ip in lan_ips()]
    payload = json.dumps({"rekord": 1, "urls": urls, "token": s["pair_token"]})
    img = qrcode.make(payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO()
    img.save(buf)
    web_url = f"{urls[0]}/?token={s['pair_token']}" if urls else ""
    img2 = qrcode.make(web_url or "about:blank", image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf2 = io.BytesIO()
    img2.save(buf2)
    return {"urls": urls, "token": s["pair_token"], "qr_app": buf.getvalue().decode(), "qr_web": buf2.getvalue().decode(),
            "web_url": web_url, "lan": bool(getattr(app.state, "lan", False))}


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
async def enroll(name: str = Form(...), file: UploadFile = File(...)):
    ext = Path(file.filename or "a.webm").suffix or ".webm"
    tmp = config.HOME / f"enroll-{uuid.uuid4().hex[:6]}{ext}"
    tmp.write_bytes(await file.read())
    try:
        prof = await asyncio.to_thread(pipeline.enroll_from_audio, name.strip(), str(tmp))
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp.unlink(missing_ok=True)
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


@app.post("/api/recordings/{rid}/summaries")
async def summarize_rec(rid: str, request: Request):
    b = await request.json()
    tid = b.get("template_id", "auto")
    tpl = templates.get(tid)
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
                try:
                    sess = await asyncio.to_thread(live.LiveSession, emit, ctl.get("title", ""), ctl.get("source", "live"),
                                                   int(ctl.get("sample_rate", 16000)), ctl.get("participants") or [],
                                                   int(ctl.get("guests", 0) or 0))
                except Exception as e:  # noqa: BLE001
                    await ws.send_json({"type": "error", "error": f"Live-Start fehlgeschlagen: {e}"})
                    continue
                live.register(sess)
                emit({"type": "started", "id": sess.rid, "title": sess.title})
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
