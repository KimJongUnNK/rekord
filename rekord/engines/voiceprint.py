"""Speaker embeddings ("voiceprints") + matching against saved voice profiles."""
from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np
import sherpa_onnx

from .. import models
from ..audio import SR

MIN_SECONDS = 0.8


def normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(normalize(a), normalize(b)))


class Embedder:
    def __init__(self, model_id: str = "eres2net-base", threads: int = 2):
        models.ensure([model_id])
        cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(models.path(model_id)), num_threads=threads)
        self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
        self.model_id = model_id
        self._lock = threading.Lock()

    def embed(self, samples: np.ndarray) -> np.ndarray | None:
        if len(samples) < SR * MIN_SECONDS:
            return None
        with self._lock:
            s = self.extractor.create_stream()
            s.accept_waveform(SR, np.ascontiguousarray(samples, dtype=np.float32))
            s.input_finished()
            if not self.extractor.is_ready(s):
                return None
            return normalize(np.array(self.extractor.compute(s), dtype=np.float32))

    def embed_turns(self, samples: np.ndarray, turns: list[tuple[float, float]], max_turns: int = 12,
                    max_len: float = 8.0) -> np.ndarray | None:
        """Mean voiceprint of a speaker from their longest turns."""
        turns = sorted(turns, key=lambda t: t[1] - t[0], reverse=True)[:max_turns]
        vecs, weights = [], []
        for a, b in turns:
            b = min(b, a + max_len)
            v = self.embed(samples[int(a * SR):int(b * SR)])
            if v is not None:
                vecs.append(v)
                weights.append(b - a)
        if not vecs:
            return None
        return normalize(np.average(np.stack(vecs), axis=0, weights=weights))


@lru_cache(maxsize=4)
def get_embedder(model_id: str, threads: int = 2) -> Embedder:
    return Embedder(model_id, threads)


def match_profiles(speaker_embs: dict[int, np.ndarray], profiles: list[dict], threshold: float) -> dict[int, tuple[dict, float]]:
    """Assign each diarized speaker to at most one profile (and each profile to at most one speaker).
    Greedy on descending similarity - optimal enough for the handful of speakers in a meeting."""
    pairs = []
    for label, emb in speaker_embs.items():
        for p in profiles:
            if p.get("embedding") is None or len(p["embedding"]) != len(emb):
                continue
            pairs.append((cosine(emb, p["embedding"]), label, p))
    pairs.sort(key=lambda x: x[0], reverse=True)
    out: dict[int, tuple[dict, float]] = {}
    used: set[int] = set()
    for score, label, p in pairs:
        if score < threshold:
            break
        if label in out or p["id"] in used:
            continue
        out[label] = (p, score)
        used.add(p["id"])
    return out


def update_mean(old: np.ndarray, n: int, new: np.ndarray, weight: int = 1) -> np.ndarray:
    """Running average of normalized embeddings (profile gets better with each meeting)."""
    return normalize((old * n + new * weight) / (n + weight))


class OnlineClusterer:
    """Live: assigns each new voice window to a known profile, an existing session speaker or a new one."""

    CLOSED_SET_FLOOR = 0.2

    def __init__(self, profiles: list[dict], profile_threshold: float, cluster_threshold: float,
                 closed_set: bool = False):
        """closed_set: everyone in the room is a known participant (no guests) -> always pick the closest of them."""
        self.profiles = [p for p in profiles if p.get("embedding") is not None]
        self.pthr = profile_threshold
        self.cthr = cluster_threshold
        self.closed_set = closed_set and bool(self.profiles)
        self.clusters: list[dict] = []  # {key, emb, n, profile}

    def _best_profile(self, emb: np.ndarray) -> tuple[dict | None, float]:
        best, score = None, -1.0
        for p in self.profiles:
            if len(p["embedding"]) != len(emb):
                continue
            s = cosine(emb, p["embedding"])
            if s > score:
                best, score = p, s
        return best, score

    def assign(self, emb: np.ndarray, update: bool = True) -> dict:
        """Returns {key, profile_id, name?, score, new}. key is stable within the session."""
        # 1) existing session cluster
        best_c, best_cs = None, -1.0
        for c in self.clusters:
            s = cosine(emb, c["emb"])
            if s > best_cs:
                best_c, best_cs = c, s
        prof, ps = self._best_profile(emb)
        if self.closed_set and prof is not None and ps >= self.CLOSED_SET_FLOOR:
            ps = max(ps, self.pthr)  # only participants can be speaking: the closest one wins
        if best_c is not None and best_cs >= self.cthr and not (self.closed_set and best_c["profile"] and prof
                                                                and best_c["profile"]["id"] != prof["id"]):
            if update:
                best_c["emb"] = update_mean(best_c["emb"], best_c["n"], emb)
                best_c["n"] += 1
                # late identification: cluster started unknown, now matches a profile clearly
                if best_c["profile"] is None:
                    p2, s2 = self._best_profile(best_c["emb"])
                    if p2 is not None and s2 >= self.pthr and not self._profile_taken(p2["id"], best_c):
                        best_c["profile"], best_c["pscore"] = p2, s2
            return self._out(best_c, best_cs, False)
        # 2) profile match opens a cluster for that person
        if prof is not None and ps >= self.pthr:
            existing = next((c for c in self.clusters if c["profile"] and c["profile"]["id"] == prof["id"]), None)
            if existing is not None:
                if update:
                    existing["emb"] = update_mean(existing["emb"], existing["n"], emb)
                    existing["n"] += 1
                return self._out(existing, ps, False)
            c = {"key": len(self.clusters), "emb": emb, "n": 1, "profile": prof, "pscore": ps}
        else:
            c = {"key": len(self.clusters), "emb": emb, "n": 1, "profile": None, "pscore": 0.0}
        if not update:  # probe only: report the matching person without opening a cluster
            known = prof is not None and ps >= self.pthr
            return {"key": None, "profile_id": prof["id"] if known else None, "name": prof["name"] if known else None,
                    "color": prof["color"] if known else None, "score": round(float(max(ps, best_cs)), 3), "new": not known}
        self.clusters.append(c)
        return self._out(c, c["pscore"] or 1.0, True)

    def _profile_taken(self, pid: int, me: dict) -> bool:
        return any(c is not me and c["profile"] and c["profile"]["id"] == pid for c in self.clusters)

    @staticmethod
    def _out(c: dict, score: float, new: bool) -> dict:
        return {"key": c["key"], "profile_id": c["profile"]["id"] if c["profile"] else None,
                "name": c["profile"]["name"] if c["profile"] else None,
                "color": c["profile"]["color"] if c["profile"] else None, "score": round(float(score), 3), "new": new}
