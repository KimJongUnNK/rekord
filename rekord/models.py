"""Model registry + downloader. All models are open weights from the sherpa-onnx GitHub releases.

Layout under MODELS_DIR:
    whisper-small/          (extracted tarball)
    pyannote-segmentation/  (extracted tarball)
    eres2net-base.onnx
    silero_vad.onnx
"""
from __future__ import annotations

import logging
import os
import shutil
import ssl
import tarfile
import threading
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import config

BASE = os.environ.get("REKORD_MODEL_MIRROR", "https://github.com/k2-fsa/sherpa-onnx/releases/download")


@dataclass
class ModelSpec:
    id: str
    kind: str  # asr | segmentation | embedding | vad
    name: str
    url: str
    size_mb: int
    description: str
    archive_dir: str = ""  # top-level dir inside the tarball
    files: dict = field(default_factory=dict)  # logical name -> relative path


def _whisper(size: str, mb: int, desc: str) -> ModelSpec:
    return ModelSpec(
        id=f"whisper-{size}", kind="asr", name=f"Whisper {size}", size_mb=mb, description=desc,
        url=f"{BASE}/asr-models/sherpa-onnx-whisper-{size}.tar.bz2", archive_dir=f"sherpa-onnx-whisper-{size}",
        files={"encoder": f"{size}-encoder.int8.onnx", "decoder": f"{size}-decoder.int8.onnx", "tokens": f"{size}-tokens.txt"},
    )


REGISTRY: dict[str, ModelSpec] = {m.id: m for m in [
    _whisper("tiny", 116, "Schnellster Test, schwache Qualität"),
    _whisper("base", 208, "Schnell, okay für klare Aufnahmen"),
    _whisper("small", 639, "Guter Standard für Laptops"),
    _whisper("turbo", 564, "large-v3-turbo: beste Qualität/Speed (empfohlen ab 16 GB RAM)"),
    _whisper("distil-large-v3", 529, "Englisch-optimiert, sehr schnell"),
    _whisper("medium", 1931, "Hohe Qualität, langsam"),
    _whisper("large-v3", 1068, "Maximale Genauigkeit, am langsamsten"),
    ModelSpec(id="pyannote-segmentation", kind="segmentation", name="pyannote segmentation 3.0", size_mb=7,
              description="Erkennt Sprecherwechsel (Pflicht für Diarization)",
              url=f"{BASE}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
              archive_dir="sherpa-onnx-pyannote-segmentation-3-0", files={"model": "model.onnx"}),
    ModelSpec(id="eres2net-base", kind="embedding", name="ERes2Net Voiceprint", size_mb=40,
              description="Stimmabdruck für Sprecher-Erkennung (Standard, mehrsprachig robust)",
              url=f"{BASE}/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx",
              files={"model": "eres2net-base.onnx"}),
    ModelSpec(id="campplus", kind="embedding", name="CAM++ Voiceprint (zh/en)", size_mb=28,
              description="Alternative, schneller",
              url=f"{BASE}/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
              files={"model": "campplus.onnx"}),
    ModelSpec(id="wespeaker-resnet34", kind="embedding", name="WeSpeaker ResNet34", size_mb=27,
              description="Alternative, auf VoxCeleb trainiert",
              url=f"{BASE}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx",
              files={"model": "wespeaker-resnet34.onnx"}),
    ModelSpec(id="silero-vad", kind="vad", name="Silero VAD", size_mb=1, description="Sprach-Erkennung für Live-Modus",
              url=f"{BASE}/asr-models/silero_vad.onnx", files={"model": "silero_vad.onnx"}),
]}

ESSENTIAL = ["pyannote-segmentation", "eres2net-base", "silero-vad"]


def needed(settings: dict) -> list[str]:
    """What REKORD needs to transcribe with these settings: speaker models, voiceprint, the chosen speech model."""
    ids = list(ESSENTIAL)
    emb = settings.get("embedding_model")
    if emb in REGISTRY and emb not in ids:
        ids.append(emb)
    if settings.get("asr_engine") != "faster-whisper" and settings.get("asr_model") in REGISTRY:
        ids.append(settings["asr_model"])
    return ids


def missing(settings: dict) -> list[str]:
    return [m for m in needed(settings) if not installed(m)]


def usable_asr(model_id: str) -> str:
    """The speech model to use: the chosen one if it's there – otherwise one that is, rather than failing (the chosen
    one is being loaded meanwhile). Nothing there at all: the chosen one (ensure() then loads it)."""
    if installed(model_id):
        return model_id
    have = [m for m, spec in REGISTRY.items() if spec.kind == "asr" and installed(m)]
    if have:
        log.warning("speech model %s not loaded yet – using %s meanwhile", model_id, have[-1])
        return have[-1]
    return model_id


def friendly(e: BaseException) -> str:
    """A download error in words: no internet, blocked, disk full – instead of a Python exception."""
    import errno
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        return f"Server antwortet mit Fehler {e.code} – später nochmal versuchen."
    if isinstance(e, ssl.SSLError) or "CERTIFICATE" in str(e).upper():
        return "Sichere Verbindung zu github.com nicht möglich (Firewall/Proxy prüft Verbindungen?)."
    if isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return "Keine Verbindung zu github.com – Internet prüfen, dann nochmal „Laden“."
    if isinstance(e, OSError) and e.errno == errno.ENOSPC:
        return "Kein Platz mehr auf dem Laufwerk."
    if isinstance(e, PermissionError):
        return f"Keine Schreibrechte im Modell-Ordner ({config.MODELS_DIR})."
    return str(e) or e.__class__.__name__

def _ssl_context() -> ssl.SSLContext:
    """Bundled CA list (certifi): the packaged app's OpenSSL was built on Debian and would look for
    certificates at Debian paths, which fails on Fedora/Arch/openSUSE. SSL_CERT_FILE still wins."""
    import os
    if os.environ.get("SSL_CERT_FILE"):
        return ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


log = logging.getLogger("rekord.models")
_progress: dict[str, dict] = {}
_plock = threading.Lock()
_dl_locks: dict[str, threading.Lock] = {}


def _dl_lock(model_id: str) -> threading.Lock:
    with _plock:
        return _dl_locks.setdefault(model_id, threading.Lock())


def _extract(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:bz2") as t:
        try:
            t.extractall(dest, filter="data")
        except TypeError:  # Python builds without tarfile filters (< 3.10.12 / 3.11.4)
            for m in t.getmembers():
                if m.name.startswith(("/", "..")) or ".." in Path(m.name).parts or m.issym() or m.islnk():
                    raise RuntimeError(f"unsicherer Pfad im Archiv: {m.name}")
            t.extractall(dest)


def model_dir(spec: ModelSpec) -> Path:
    return config.MODELS_DIR / spec.id if spec.archive_dir else config.MODELS_DIR


def path(model_id: str, key: str = "model") -> Path:
    spec = REGISTRY[model_id]
    return model_dir(spec) / spec.files[key]


def installed(model_id: str) -> bool:
    spec = REGISTRY.get(model_id)
    return bool(spec) and all((model_dir(spec) / f).exists() for f in spec.files.values())


def status() -> list[dict]:
    out = []
    for spec in REGISTRY.values():
        with _plock:
            prog = dict(_progress.get(spec.id, {}))
        out.append({"id": spec.id, "kind": spec.kind, "name": spec.name, "size_mb": spec.size_mb,
                    "description": spec.description, "installed": installed(spec.id), "progress": prog})
    return out


def _set(mid: str, **kw) -> None:
    with _plock:
        _progress.setdefault(mid, {}).update(kw)


def download(model_id: str, on_progress=None) -> None:
    """Blocking download + extract. Progress via status() (and on_progress(fraction)). Concurrent callers wait for the
    same download."""
    with _dl_lock(model_id):
        _download(model_id, on_progress)


def _download(model_id: str, on_progress=None) -> None:
    spec = REGISTRY[model_id]
    if installed(model_id):
        return
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.MODELS_DIR / (Path(spec.url).name + ".part")
    _set(model_id, state="downloading", done=0, total=spec.size_mb * 1024 * 1024, error="")
    try:
        req = urllib.request.Request(spec.url, headers={"User-Agent": "rekord"})
        with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            if total:
                _set(model_id, total=total)
            done = 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                _set(model_id, done=done)
                if on_progress:
                    on_progress(min(1.0, done / (total or spec.size_mb * 1024 * 1024)))
        if spec.archive_dir:
            _set(model_id, state="extracting")
            _extract(tmp, config.MODELS_DIR)
            target = model_dir(spec)
            if target.exists():
                shutil.rmtree(target)
            (config.MODELS_DIR / spec.archive_dir).rename(target)
            tmp.unlink()
            for extra in ("test_wavs",):
                shutil.rmtree(target / extra, ignore_errors=True)
            if spec.kind == "asr":
                for p in target.glob("*.onnx"):
                    if ".int8." not in p.name:
                        p.unlink()
        else:
            tmp.rename(config.MODELS_DIR / spec.files["model"])
        _set(model_id, state="done")
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        _set(model_id, state="error", error=friendly(e))
        raise


def download_async(model_id: str) -> None:
    if installed(model_id) or _dl_lock(model_id).locked():
        return  # there, or already running
    # shown right away – the window asks for the progress immediately after the click, before the thread got going
    _set(model_id, state="downloading", done=0, total=REGISTRY[model_id].size_mb * 1024 * 1024, error="")

    def run():
        try:
            download(model_id)
        except Exception:  # noqa: BLE001 - reported via status
            pass
    threading.Thread(target=run, daemon=True, name=f"dl-{model_id}").start()


def delete(model_id: str) -> None:
    spec = REGISTRY[model_id]
    if spec.archive_dir:
        shutil.rmtree(model_dir(spec), ignore_errors=True)
    else:
        (config.MODELS_DIR / spec.files["model"]).unlink(missing_ok=True)
    with _plock:
        _progress.pop(model_id, None)


def download_missing_async(settings: dict) -> list[str]:
    """Everything REKORD still needs, one after the other in the background. Returns the ids being loaded."""
    todo = missing(settings)
    for mid in todo:  # all show "downloading" at once – honest: they're all on the way
        if not _dl_lock(mid).locked():
            _set(mid, state="downloading", done=0, total=REGISTRY[mid].size_mb * 1024 * 1024, error="")

    def run():
        for mid in todo:
            try:
                download(mid)
            except Exception:  # noqa: BLE001 - reported via status; the next one still loads
                pass
    if todo:
        threading.Thread(target=run, daemon=True, name="dl-missing").start()
    return todo


class Missing(RuntimeError):
    """A model REKORD needs is not there and could not be loaded (no internet …) – said in words."""


def ensure(ids: list[str], on_progress=None) -> None:
    """Load what's missing (blocking). on_progress(name, fraction) while loading. Missing when that fails."""
    for mid in ids:
        if not installed(mid):
            spec = REGISTRY[mid]
            try:
                download(mid, (lambda f, n=spec.name: on_progress(n, f)) if on_progress else None)
            except Exception as e:  # noqa: BLE001
                raise Missing(f"Das Modell „{spec.name}“ ({spec.size_mb} MB) fehlt und ließ sich nicht laden: {friendly(e)} "
                              "Einstellungen → Modelle → Laden.") from e
