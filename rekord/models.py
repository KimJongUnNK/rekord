"""Model registry + downloader. All models are open weights from the sherpa-onnx GitHub releases.

Layout under MODELS_DIR:
    whisper-small/          (extracted tarball)
    pyannote-segmentation/  (extracted tarball)
    eres2net-base.onnx
    silero_vad.onnx
"""
from __future__ import annotations

import os
import shutil
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
    ModelSpec("pyannote-segmentation", "segmentation", "pyannote segmentation 3.0", 7,
              "Erkennt Sprecherwechsel (Pflicht für Diarization)",
              f"{BASE}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
              archive_dir="sherpa-onnx-pyannote-segmentation-3-0", files={"model": "model.onnx"}),
    ModelSpec("eres2net-base", "embedding", "ERes2Net Voiceprint", 40,
              "Stimmabdruck für Sprecher-Erkennung (Standard, mehrsprachig robust)",
              f"{BASE}/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx",
              files={"model": "eres2net-base.onnx"}),
    ModelSpec("campplus", "embedding", "CAM++ Voiceprint (zh/en)", 28,
              "Alternative, schneller",
              f"{BASE}/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
              files={"model": "campplus.onnx"}),
    ModelSpec("wespeaker-resnet34", "embedding", "WeSpeaker ResNet34", 27,
              "Alternative, auf VoxCeleb trainiert",
              f"{BASE}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx",
              files={"model": "wespeaker-resnet34.onnx"}),
    ModelSpec("silero-vad", "vad", "Silero VAD", 1, "Sprach-Erkennung für Live-Modus",
              f"{BASE}/asr-models/silero_vad.onnx", files={"model": "silero_vad.onnx"}),
]}

ESSENTIAL = ["pyannote-segmentation", "eres2net-base", "silero-vad"]

_progress: dict[str, dict] = {}
_plock = threading.Lock()


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


def download(model_id: str) -> None:
    """Blocking download + extract. Progress via status()."""
    spec = REGISTRY[model_id]
    if installed(model_id):
        return
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = config.MODELS_DIR / (Path(spec.url).name + ".part")
    _set(model_id, state="downloading", done=0, total=spec.size_mb * 1024 * 1024, error="")
    try:
        req = urllib.request.Request(spec.url, headers={"User-Agent": "rekord"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            if total:
                _set(model_id, total=total)
            done = 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                _set(model_id, done=done)
        if spec.archive_dir:
            _set(model_id, state="extracting")
            with tarfile.open(tmp, "r:bz2") as t:
                t.extractall(config.MODELS_DIR, filter="data")
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
        _set(model_id, state="error", error=str(e))
        raise


def download_async(model_id: str) -> None:
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


def ensure(ids: list[str]) -> None:
    for mid in ids:
        if not installed(mid):
            download(mid)
