"""Speaker diarization: who spoke when (pyannote segmentation + voiceprint clustering, all ONNX)."""
from __future__ import annotations

from typing import Callable

import numpy as np
import sherpa_onnx

from .. import models


def diarize(samples: np.ndarray, embedding_model: str = "eres2net-base", num_speakers: int = 0,
            threshold: float = 0.6, threads: int = 4,
            progress: Callable[[float], None] | None = None) -> list[tuple[float, float, int]]:
    models.ensure(["pyannote-segmentation", embedding_model])
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(models.path("pyannote-segmentation"))),
            num_threads=threads),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(models.path(embedding_model)), num_threads=threads),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_speakers if num_speakers > 0 else -1,
                                                    threshold=threshold),
        min_duration_on=0.3,
        min_duration_off=0.2,
    )
    if not cfg.validate():
        raise RuntimeError("Diarization-Konfiguration ungültig")
    sd = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    if len(samples) < sd.sample_rate:  # < 1s
        return []

    def cb(done: int, total: int) -> int:
        if progress and total:
            progress(done / total)
        return 0

    result = sd.process(np.ascontiguousarray(samples, dtype=np.float32), callback=cb).sort_by_start_time()
    return clean_turns([(float(s.start), float(s.end), int(s.speaker)) for s in result])


def clean_turns(turns: list[tuple[float, float, int]], merge_gap: float = 0.8,
                min_len: float = 0.4) -> list[tuple[float, float, int]]:
    """Resolve overlaps, drop blips, merge same-speaker turns separated by short pauses, relabel 0..n by first appearance."""
    turns = sorted(turns)
    out: list[list] = []
    for a, b, spk in turns:
        if out and a < out[-1][1]:  # overlap: the later, different speaker starts where the previous ends
            if spk == out[-1][2]:
                out[-1][1] = max(out[-1][1], b)
                continue
            if b <= out[-1][1]:  # fully contained interjection -> keep the longer speaker
                if b - a < min_len * 2:
                    continue
                prev_end = out[-1][1]
                out[-1][1] = a
                out.append([a, b, spk])
                out.append([b, prev_end, out[-2][2]])
                continue
            a = out[-1][1]
        if b - a < min_len:
            continue
        if out and out[-1][2] == spk and a - out[-1][1] <= merge_gap:
            out[-1][1] = b
        else:
            out.append([a, b, spk])
    out = [t for t in out if t[1] - t[0] >= min_len]
    # merge again after removals
    merged: list[list] = []
    for t in out:
        if merged and merged[-1][2] == t[2] and t[0] - merged[-1][1] <= merge_gap:
            merged[-1][1] = t[1]
        else:
            merged.append(list(t))
    relabel: dict[int, int] = {}
    for t in merged:
        relabel.setdefault(t[2], len(relabel))
    return [(round(a, 3), round(b, 3), relabel[s]) for a, b, s in merged]


def refine_turns(samples: np.ndarray, turns: list[tuple[float, float, int]], embedder, win: float = 1.5,
                 hop: float = 0.5, margin: float = 0.04) -> list[tuple[float, float, int]]:
    """Second pass: catches speaker changes the segmenter glued together (fast turn-taking without pauses).
    Slides a short window through each long turn and re-splits where another speaker's voiceprint clearly fits better."""
    from ..audio import SR
    from .voiceprint import normalize
    by: dict[int, list] = {}
    for a, b, s in turns:
        by.setdefault(s, []).append((a, b))
    if len(by) < 2:
        return turns
    cents = {s: e for s, ts in by.items() if (e := embedder.embed_turns(samples, ts)) is not None}
    if len(cents) < 2:
        return turns
    labels = list(cents)
    C = np.stack([normalize(cents[s]) for s in labels])
    out: list[tuple[float, float, int]] = []
    for a, b, s in turns:
        if b - a < 2 * win + hop or s not in cents:
            out.append((a, b, s))
            continue
        times, assign = [], []
        t = a
        while t + win <= b + 1e-6:
            e = embedder.embed(samples[int(t * SR):int((t + win) * SR)])
            if e is not None:
                sims = C @ e
                own = sims[labels.index(s)]
                j = int(np.argmax(sims))
                assign.append(labels[j] if sims[j] - own > margin else s)
                times.append(t + win / 2)
            t += hop
        # smooth: require 3 consecutive windows (~2.5 s of speech) before switching
        runs: list[list] = []
        for tm, lab in zip(times, assign):
            if runs and runs[-1][2] == lab:
                runs[-1][1] = tm
            else:
                runs.append([tm, tm, lab])
        stable = [r for r in runs if r[2] == s or round((r[1] - r[0]) / hop) + 1 >= 3]
        if all(r[2] == s for r in stable):
            out.append((a, b, s))
            continue
        merged: list[list] = []
        for r in stable:
            if merged and merged[-1][2] == r[2]:
                merged[-1][1] = r[1]
            else:
                merged.append(list(r))
        cur = a
        for i, r in enumerate(merged):
            end = b if i == len(merged) - 1 else (r[1] + merged[i + 1][0]) / 2
            out.append((round(cur, 3), round(end, 3), r[2]))
            cur = end
    return clean_turns(out)
