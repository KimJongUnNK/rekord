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
from functools import lru_cache
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
    _whisper("distil-large-v3", 529, "Nur Englisch – andere Sprachen kommen als englische Übersetzung raus"),
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


# faster-whisper (CTranslate2) speech models: from Hugging Face, in REKORD's model folder. Ids "fw:<size>".
FW_PREFIX = "fw:"
FW = {  # size → (repository, name, MB, description)
    "large-v3-turbo": ("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "faster-whisper turbo", 1620,
                       "Beste Qualität pro Sekunde – mit NVIDIA-Grafikkarte sehr schnell"),
    "large-v3": ("Systran/faster-whisper-large-v3", "faster-whisper large-v3", 3090, "Maximale Genauigkeit, braucht viel Zeit ohne GPU"),
    "distil-large-v3": ("Systran/faster-distil-whisper-large-v3", "faster-whisper distil-large-v3", 1510,
                        "Nur Englisch – andere Sprachen kommen als englische Übersetzung raus"),
    "medium": ("Systran/faster-whisper-medium", "faster-whisper medium", 1530, "Hohe Qualität"),
    "small": ("Systran/faster-whisper-small", "faster-whisper small", 484, "Guter Standard für Laptops"),
    "base": ("Systran/faster-whisper-base", "faster-whisper base", 145, "Schnell, okay für klare Aufnahmen"),
    "tiny": ("Systran/faster-whisper-tiny", "faster-whisper tiny", 75, "Schnellster Test, schwache Qualität"),
}
_FW_FILES = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]


def _fw_size(model_id: str) -> str | None:
    if model_id.startswith(FW_PREFIX) and model_id[len(FW_PREFIX):] in FW:
        return model_id[len(FW_PREFIX):]
    return None


def fw_root() -> Path:
    return config.MODELS_DIR / "faster-whisper"


def _fw_repo_dir(size: str) -> Path:
    return fw_root() / ("models--" + FW[size][0].replace("/", "--"))


def fw_path(size: str) -> Path | None:
    """The folder of a loaded faster-whisper model (what WhisperModel opens) – None if it isn't (completely) there."""
    snaps = _fw_repo_dir(size) / "snapshots"
    if not snaps.is_dir():
        return None
    for d in sorted(snaps.iterdir()):
        if (d / "model.bin").exists() and (d / "config.json").exists() and (d / "tokenizer.json").exists():
            return d
    return None


def known(model_id: str) -> bool:
    return model_id in REGISTRY or _fw_size(model_id) is not None


def name(model_id: str) -> str:
    size = _fw_size(model_id)
    return FW[size][1] if size else REGISTRY[model_id].name


def size_mb(model_id: str) -> int:
    size = _fw_size(model_id)
    return FW[size][2] if size else REGISTRY[model_id].size_mb


@lru_cache(maxsize=1)
def faster_whisper_available() -> bool:
    """faster-whisper is an optional extra (pip install faster-whisper) – not part of the finished apps."""
    import importlib.util
    return importlib.util.find_spec("faster_whisper") is not None


def engine(settings: dict) -> str:
    """The speech engine that actually runs: faster-whisper only if it's chosen AND installed – otherwise Whisper ONNX,
    so a choice that can't work never breaks a transcription."""
    if settings.get("asr_engine") == "faster-whisper" and faster_whisper_available():
        return "faster-whisper"
    return "sherpa"


def _hardware() -> dict:
    """Memory, processor cores and graphics of this computer – read once."""
    from .llm import ollama
    hw = dict(ollama.hardware())
    hw["cores"] = os.cpu_count() or 4
    if faster_whisper_available():
        from .engines import asr
        hw["cuda"] = asr.cuda_devices() > 0
    else:
        hw["cuda"] = False
    return hw


def recommend_asr(hw: dict | None = None) -> dict:
    """The speech model that fits this computer: as accurate as it can be while a one-hour recording is still done
    in reasonable time. NVIDIA card (and faster-whisper there): turbo on the card. Otherwise Whisper ONNX on the
    processor – turbo from 16 GB and 8 cores (Apple M chips, newer PCs), small for usual laptops, base below."""
    hw = _hardware() if hw is None else hw
    ram, cores = float(hw.get("ram_gb") or 8), int(hw.get("cores") or 4)
    if ram >= 15 and cores >= 8:
        onnx = "whisper-turbo"
    elif ram >= 7 and cores >= 4:
        onnx = "whisper-small"
    else:
        onnx = "whisper-base"
    out = {"asr_engine": "sherpa", "asr_model": onnx, "faster_whisper_model": "large-v3-turbo"}
    gpu = (" · Apple-Chip" if hw.get("gpu") == "apple" else
           " · NVIDIA-Grafikkarte" if hw.get("cuda") or hw.get("gpu") == "nvidia" else "")
    label = f"{ram:.0f} GB RAM · {cores} Kerne{gpu}"
    if hw.get("cuda") and faster_whisper_available():
        vram = float(hw.get("vram_gb") or 0)
        out.update(asr_engine="faster-whisper", faster_whisper_model="large-v3-turbo" if vram == 0 or vram >= 4 else "small")
        out["model"] = FW_PREFIX + out["faster_whisper_model"]
    else:
        out["model"] = onnx
    out["name"], out["label"] = name(out["model"]), label
    return out


def apply_recommended(force: bool = False) -> dict | None:
    """Automatic model choice (the default): set what fits this computer. A model the user picked stays
    (asr_auto is then off). Returns the recommendation when something changed."""
    s = config.load()
    if not (force or s.get("asr_auto", True)):
        return None
    rec = recommend_asr()
    patch = {k: rec[k] for k in ("asr_engine", "asr_model", "faster_whisper_model") if s.get(k) != rec[k]}
    if force:
        patch["asr_auto"] = True
    if patch:
        config.save(patch)
        log.info("speech model for this computer (%s): %s", rec["label"], rec["name"])
        return rec
    return None


ENGLISH_ONLY = {"whisper-distil-large-v3", FW_PREFIX + "distil-large-v3"}
_MULTILINGUAL = ["whisper-turbo", "whisper-small", "whisper-medium", "whisper-large-v3", "whisper-base", "whisper-tiny"]


def for_language(settings: dict) -> dict:
    """An English-only model can't write German: it translates. Is one chosen and the language isn't English, use a
    multilingual one instead – one that's there, else turbo (loaded like any missing model)."""
    lang = settings.get("language") or ""
    if lang == "en":
        return settings
    s = dict(settings)
    if engine(s) == "faster-whisper" and FW_PREFIX + (s.get("faster_whisper_model") or "") in ENGLISH_ONLY:
        log.warning("faster-whisper %s only writes English – using large-v3-turbo", s["faster_whisper_model"])
        s["faster_whisper_model"] = "large-v3-turbo"
    if s.get("asr_model") in ENGLISH_ONLY:
        alt = next((m for m in _MULTILINGUAL if m in REGISTRY and installed(m)), "whisper-turbo")
        log.warning("%s only writes English – using %s", s["asr_model"], alt)
        s["asr_model"] = alt
    return s


def needed(settings: dict) -> list[str]:
    settings = for_language(settings)
    """What REKORD needs to transcribe with these settings: speaker models, voiceprint, the chosen speech model."""
    ids = list(ESSENTIAL)
    emb = settings.get("embedding_model")
    if emb in REGISTRY and emb not in ids:
        ids.append(emb)
    if engine(settings) == "sherpa" and settings.get("asr_model") in REGISTRY:
        ids.append(settings["asr_model"])
    elif engine(settings) == "faster-whisper" and settings.get("faster_whisper_model") in FW:
        ids.append(FW_PREFIX + settings["faster_whisper_model"])
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


def friendly(e: BaseException, host: str = "github.com") -> str:
    """A download error in words: no internet, blocked, disk full – instead of a Python exception."""
    import errno
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        return f"Server antwortet mit Fehler {e.code} – später nochmal versuchen."
    if isinstance(e, ssl.SSLError) or "CERTIFICATE" in str(e).upper():
        return f"Sichere Verbindung zu {host} nicht möglich (Firewall/Proxy prüft Verbindungen?)."
    offline = isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError)) or e.__class__.__name__ in (
        "ConnectError", "ConnectTimeout", "LocalEntryNotFoundError", "OfflineModeIsEnabled") or "connection" in str(e).lower() \
        or "Proxy" in e.__class__.__name__
    if offline:
        return f"Keine Verbindung zu {host} – Internet prüfen, dann nochmal „Laden“."
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
    size = _fw_size(model_id)
    if size:
        return fw_path(size) is not None
    spec = REGISTRY.get(model_id)
    return bool(spec) and all((model_dir(spec) / f).exists() for f in spec.files.values())


def status() -> list[dict]:
    out = []
    for spec in REGISTRY.values():
        with _plock:
            prog = dict(_progress.get(spec.id, {}))
        out.append({"id": spec.id, "kind": spec.kind, "name": spec.name, "size_mb": spec.size_mb,
                    "description": spec.description, "installed": installed(spec.id), "progress": prog})
    if faster_whisper_available():  # the faster-whisper engine's own models
        for size, (_repo, nm, mb, desc) in FW.items():
            mid = FW_PREFIX + size
            with _plock:
                prog = dict(_progress.get(mid, {}))
            out.append({"id": mid, "kind": "asr-fw", "name": nm, "size_mb": mb, "description": desc,
                        "installed": installed(mid), "progress": prog})
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
    if _fw_size(model_id):
        return _fw_download(model_id, on_progress)
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


def _fw_download(model_id: str, on_progress=None) -> None:
    """A faster-whisper model from Hugging Face (only the files the engine needs). Progress: the bytes on disk."""
    size = _fw_size(model_id)
    if fw_path(size):
        return
    repo, _nm, mb, _d = FW[size]
    total = mb * 1024 * 1024
    _set(model_id, state="downloading", done=0, total=total, error="")
    fw_root().mkdir(parents=True, exist_ok=True)
    stop = threading.Event()

    def watch():  # Hugging Face reports no progress we can use: count what has arrived
        while not stop.wait(0.7):
            d = _fw_repo_dir(size)
            done = sum(f.stat().st_size for f in d.rglob("*") if f.is_file() and not f.is_symlink()) if d.is_dir() else 0
            _set(model_id, done=min(done, total))
            if on_progress:
                on_progress(min(1.0, done / total))
    t = threading.Thread(target=watch, daemon=True, name=f"dl-watch-{size}")
    t.start()
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo, cache_dir=str(fw_root()), allow_patterns=_FW_FILES)
        if not fw_path(size):
            raise RuntimeError("Download unvollständig – nochmal „Laden“.")
        _set(model_id, state="done", done=total)
    except Exception as e:  # noqa: BLE001
        _set(model_id, state="error", error=friendly(e, "huggingface.co"))
        raise
    finally:
        stop.set()


def download_async(model_id: str) -> None:
    if installed(model_id) or _dl_lock(model_id).locked():
        return  # there, or already running
    # shown right away – the window asks for the progress immediately after the click, before the thread got going
    _set(model_id, state="downloading", done=0, total=size_mb(model_id) * 1024 * 1024, error="")

    def run():
        try:
            download(model_id)
        except Exception:  # noqa: BLE001 - reported via status
            pass
    threading.Thread(target=run, daemon=True, name=f"dl-{model_id}").start()


def delete(model_id: str) -> None:
    size = _fw_size(model_id)
    if size:
        shutil.rmtree(_fw_repo_dir(size), ignore_errors=True)
        with _plock:
            _progress.pop(model_id, None)
        return
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
            _set(mid, state="downloading", done=0, total=size_mb(mid) * 1024 * 1024, error="")

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
            nm, mb = name(mid), size_mb(mid)
            try:
                download(mid, (lambda f, n=nm: on_progress(n, f)) if on_progress else None)
            except Exception as e:  # noqa: BLE001
                why = friendly(e, "huggingface.co" if _fw_size(mid) else "github.com")
                raise Missing(f"Das Modell „{nm}“ ({mb} MB) fehlt und ließ sich nicht laden: {why} "
                              "Einstellungen → Modelle → Laden.") from e
