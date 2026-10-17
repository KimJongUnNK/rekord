"""Speech-to-text engines.

sherpa      - Whisper (tiny..large-v3/turbo) as int8 ONNX. Runs everywhere (Win/Mac/Linux, x86/ARM), no GPU, no torch.
faster-whisper - optional (pip install faster-whisper). CTranslate2, word timestamps, hotwords, CUDA if present.
"""
from __future__ import annotations

import threading
from functools import lru_cache
from typing import Callable

import numpy as np

from .. import models
from ..audio import SR

MAX_CHUNK = 28.0  # whisper window is 30 s


def split_long(a: float, b: float, samples: np.ndarray, max_len: float = MAX_CHUNK) -> list[tuple[float, float]]:
    """Split a turn longer than whisper's window at the quietest point near the limit."""
    out = []
    while b - a > max_len:
        lo, hi = a + max_len * 0.6, a + max_len
        seg = samples[int(lo * SR):int(hi * SR)]
        if len(seg) > SR // 10:
            win = SR // 20
            usable = len(seg) // win * win
            energy = np.abs(seg[:usable]).reshape(-1, win).mean(axis=1)
            cut = lo + (int(np.argmin(energy)) * win + win // 2) / SR
        else:
            cut = hi
        out.append((a, cut))
        a = cut
    out.append((a, b))
    return out


class SherpaWhisper:
    name = "sherpa"
    word_timestamps = False

    def __init__(self, model_id: str = "whisper-small", language: str = "", threads: int = 4):
        import sherpa_onnx
        models.ensure([model_id])
        self.rec = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(models.path(model_id, "encoder")), decoder=str(models.path(model_id, "decoder")),
            tokens=str(models.path(model_id, "tokens")), language=language or "", task="transcribe",
            num_threads=threads, tail_paddings=-1)
        self.model_id = model_id
        self._lock = threading.Lock()

    def transcribe_clip(self, clip: np.ndarray) -> tuple[str, str]:
        with self._lock:
            s = self.rec.create_stream()
            s.accept_waveform(SR, np.ascontiguousarray(clip, dtype=np.float32))
            self.rec.decode_stream(s)
            return s.result.text.strip(), getattr(s.result, "lang", "") or ""

    def transcribe_turns(self, samples: np.ndarray, turns: list[tuple[float, float, int]],
                         progress: Callable[[float], None] | None = None) -> list[dict]:
        jobs = []
        for a, b, spk in turns:
            for ca, cb in split_long(a, b, samples):
                jobs.append((ca, cb, spk))
        out = []
        total = sum(b - a for a, b, _ in jobs) or 1
        done = 0.0
        batch = 4
        for i in range(0, len(jobs), batch):
            chunk = jobs[i:i + batch]
            with self._lock:
                streams = []
                for a, b, _ in chunk:
                    s = self.rec.create_stream()
                    s.accept_waveform(SR, np.ascontiguousarray(samples[int(a * SR):int(b * SR)], dtype=np.float32))
                    streams.append(s)
                self.rec.decode_streams(streams)
            for (a, b, spk), s in zip(chunk, streams):
                text = clean_text(s.result.text)
                if text:
                    out.append({"start": a, "end": b, "label": spk, "text": text, "lang": getattr(s.result, "lang", "")})
                done += b - a
            if progress:
                progress(done / total)
        return merge_chunks(out)


class FasterWhisper:
    name = "faster-whisper"
    word_timestamps = True

    def __init__(self, model: str = "large-v3-turbo", language: str = "", device: str = "auto", hotwords: str = ""):
        from faster_whisper import WhisperModel  # optional dependency
        compute = "int8" if device in ("cpu", "auto") else "float16"
        self.model = WhisperModel(model, device=device, compute_type=compute, download_root=str(models.config.MODELS_DIR / "faster-whisper"))
        self.language = language or None
        self.hotwords = hotwords or None
        self.model_id = f"faster-whisper:{model}"

    def words(self, samples: np.ndarray, progress: Callable[[float], None] | None = None) -> tuple[list[dict], str]:
        segs, info = self.model.transcribe(samples, language=self.language, word_timestamps=True, vad_filter=True,
                                           hotwords=self.hotwords, condition_on_previous_text=False)
        dur = len(samples) / SR or 1
        words = []
        for seg in segs:
            for w in seg.words or []:
                words.append({"start": w.start, "end": w.end, "word": w.word})
            if progress:
                progress(min(1.0, seg.end / dur))
        return words, info.language

    def transcribe_clip(self, clip: np.ndarray) -> tuple[str, str]:
        segs, info = self.model.transcribe(clip, language=self.language, hotwords=self.hotwords)
        return clean_text(" ".join(s.text for s in segs)), info.language

    def transcribe_turns(self, samples: np.ndarray, turns: list[tuple[float, float, int]],
                         progress: Callable[[float], None] | None = None) -> list[dict]:
        words, lang = self.words(samples, progress)
        return assign_words(words, turns, lang)


def assign_words(words: list[dict], turns: list[tuple[float, float, int]], lang: str = "") -> list[dict]:
    """Give every word the speaker whose turn overlaps it most; consecutive same-speaker words form a segment."""
    out: list[dict] = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        best, best_ov = None, 0.0
        for a, b, spk in turns:
            ov = min(b, w["end"]) - max(a, w["start"])
            if ov > best_ov:
                best, best_ov = spk, ov
        if best is None:  # word in a gap: nearest turn
            if not turns:
                best = 0
            else:
                best = min(turns, key=lambda t: min(abs(mid - t[0]), abs(mid - t[1])))[2]
        if out and out[-1]["label"] == best and w["start"] - out[-1]["end"] < 1.5:
            out[-1]["text"] += w["word"]
            out[-1]["end"] = w["end"]
        else:
            out.append({"start": w["start"], "end": w["end"], "label": best, "text": w["word"], "lang": lang})
    for s in out:
        s["text"] = clean_text(s["text"])
    return [s for s in out if s["text"]]


HALLUCINATIONS = {"untertitel im auftrag des zdf", "untertitelung des zdf", "vielen dank fürs zuschauen",
                  "thanks for watching", "thank you for watching", "subtitles by the amara.org community",
                  "untertitel der amara.org-community", "copyright wdr", "swr 2020"}


def clean_text(t: str) -> str:
    t = " ".join(t.split()).strip()
    low = t.lower().strip(" .!")
    if not low or any(low.startswith(h) for h in HALLUCINATIONS):
        return ""
    if set(low) <= set(".… -"):
        return ""
    return t


def merge_chunks(segs: list[dict]) -> list[dict]:
    """Rejoin pieces of one turn that were split for the 30 s window."""
    out: list[dict] = []
    for s in segs:
        if out and out[-1]["label"] == s["label"] and abs(out[-1]["end"] - s["start"]) < 0.05:
            out[-1]["text"] += " " + s["text"]
            out[-1]["end"] = s["end"]
        else:
            out.append(dict(s))
    return out


def apply_vocabulary(text: str, vocab: list[dict]) -> str:
    import re
    for v in vocab or []:
        src, dst = (v.get("from") or "").strip(), (v.get("to") or "").strip()
        if src and dst:
            text = re.sub(rf"(?<!\w){re.escape(src)}(?!\w)", dst, text, flags=re.IGNORECASE)
    return text


@lru_cache(maxsize=2)
def _sherpa(model_id: str, language: str, threads: int) -> SherpaWhisper:
    return SherpaWhisper(model_id, language, threads)


@lru_cache(maxsize=1)
def _faster(model: str, language: str, device: str, hotwords: str) -> FasterWhisper:
    return FasterWhisper(model, language, device, hotwords)


def get_engine(settings: dict):
    if settings.get("asr_engine") == "faster-whisper":
        hot = " ".join(v.get("to", "") for v in settings.get("vocabulary", []) if v.get("to"))
        return _faster(settings["faster_whisper_model"], settings.get("language", ""),
                       settings.get("faster_whisper_device", "auto"), hot)
    return _sherpa(settings["asr_model"], settings.get("language", ""), int(settings.get("threads", 4)))


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
