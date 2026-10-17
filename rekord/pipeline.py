"""Full processing of one recording: decode -> diarize -> voiceprints -> identify people -> transcribe -> save."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from . import audio, config, db
from .engines import asr, voiceprint
from .engines.diarize import diarize, refine_turns

log = logging.getLogger("rekord.pipeline")


def speaker_name(i: int) -> str:
    return f"Sprecher {i + 1}"


def process(rid: str, on_event=None) -> dict:
    s = config.load()
    rec = db.get_recording(rid)
    if rec is None:
        raise KeyError(rid)
    t0 = time.time()

    def stage(name: str, p: float) -> None:
        db.update_recording(rid, status="processing", stage=name, progress=round(p, 3))
        if on_event:
            on_event({"type": "progress", "id": rid, "stage": name, "progress": p})

    stage("Audio laden", 0.01)
    samples = audio.load(rec["audio_path"])
    duration = len(samples) / audio.SR
    db.update_recording(rid, duration=duration, peaks=audio.peaks(samples))

    # 1. who spoke when
    stage("Sprecher trennen", 0.05)
    part = rec.get("participants") or {}
    part_ids = [int(x) for x in part.get("ids", [])]
    guests = int(part.get("guests", 0) or 0)
    n_spk = int(s.get("num_speakers") or 0) or ((len(part_ids) + guests) if part_ids else 0)
    turns = diarize(samples, s["embedding_model"], n_spk, float(s["cluster_threshold"]),
                    int(s["threads"]), progress=lambda p: stage("Sprecher trennen", 0.05 + 0.3 * p))
    if not turns and duration > 1:
        turns = [(0.0, duration, 0)]  # single speaker fallback (e.g. no clear speech boundaries)

    # 2. voiceprint per speaker + match against known people
    stage("Personen erkennen", 0.36)
    emb = voiceprint.get_embedder(s["embedding_model"], 2)
    turns = refine_turns(samples, turns, emb, hop=0.5 if duration < 900 else 1.0)
    by_label: dict[int, list[tuple[float, float]]] = {}
    for a, b, spk in turns:
        by_label.setdefault(spk, []).append((a, b))
    speaker_embs = {lbl: e for lbl, ts in by_label.items() if (e := emb.embed_turns(samples, ts)) is not None}
    profiles = [p for p in db.list_profiles(with_embedding=True) if p["embedding"] is not None]
    threshold = float(s["profile_threshold"])
    if part_ids:  # announced participants: compare only against them; with no guests it is a closed set
        profiles = [p for p in profiles if p["id"] in part_ids]
        if guests == 0:
            threshold = min(threshold, voiceprint.OnlineClusterer.CLOSED_SET_FLOOR + 0.1)
    matches = voiceprint.match_profiles(speaker_embs, profiles, threshold)

    speakers = []
    unknown = 0
    for lbl in sorted(by_label):
        if lbl in matches:
            p, score = matches[lbl]
            speakers.append({"label": lbl, "name": p["name"], "color": p["color"], "profile_id": p["id"],
                             "match_score": round(score, 3), "embedding": speaker_embs.get(lbl)})
        else:
            speakers.append({"label": lbl, "name": speaker_name(unknown), "color": db.PALETTE[(len(profiles) + unknown) % len(db.PALETTE)],
                             "profile_id": None, "match_score": 0, "embedding": speaker_embs.get(lbl)})
            unknown += 1

    # 3. words
    stage("Transkribieren", 0.4)
    engine = asr.get_engine(s)
    segs = engine.transcribe_turns(samples, turns, progress=lambda p: stage("Transkribieren", 0.4 + 0.55 * p))
    for seg in segs:
        seg["text"] = asr.apply_vocabulary(seg["text"], s.get("vocabulary", []))
    langs = [x.get("lang") for x in segs if x.get("lang")]
    language = max(set(langs), key=langs.count) if langs else (s.get("language") or "")

    # drop speakers that ended up without words
    used = {x["label"] for x in segs}
    speakers = [sp for sp in speakers if sp["label"] in used] or speakers[:1]

    db.replace_transcript(rid, speakers, segs)
    db.update_recording(rid, status="done", stage="", progress=1.0, error="", language=language)
    log.info("processed %s: %.0fs audio in %.1fs, %d speakers, %d segments", rid, duration, time.time() - t0,
             len(speakers), len(segs))
    if on_event:
        on_event({"type": "done", "id": rid})
    return {"duration": duration, "speakers": len(speakers), "segments": len(segs), "seconds": time.time() - t0}


def remember_speaker(rid: str, speaker_id: int, name: str) -> dict:
    """Rename a speaker and store/merge their voiceprint as a profile -> recognized automatically from now on."""
    sp = db.get_speaker(speaker_id, with_embedding=True)
    if sp is None or sp["recording_id"] != rid:
        raise KeyError(speaker_id)
    e = sp.get("embedding")
    if e is None:
        e = _embedding_from_segments(rid, speaker_id)
    if e is None:
        raise ValueError("Zu wenig Sprache für einen Stimmabdruck (mind. ~1 Sekunde)")
    # Only ever merge into the profile of the person the user named. If REKORD had matched this voice to
    # someone else ("Lisa") and the user corrects it ("Anna"), Lisa's voiceprint must stay untouched.
    existing = next((p for p in db.list_profiles(with_embedding=True) if p["name"].lower() == name.lower()), None)
    if existing is not None:
        merged = voiceprint.update_mean(existing["embedding"], existing["samples"], e) \
            if len(existing["embedding"]) == len(e) else e
        db.update_profile(existing["id"], name=name, embedding=merged, samples=existing["samples"] + 1)
        pid, color = existing["id"], existing["color"]
    else:
        pid = db.create_profile(name, e)
        color = db.get_profile(pid)["color"]
    db.update_speaker(speaker_id, name=name, profile_id=pid, color=color, match_score=1.0)
    return db.get_profile(pid)


def _embedding_from_segments(rid: str, speaker_id: int) -> np.ndarray | None:
    s = config.load()
    rec = db.get_recording(rid)
    turns = [(x["start"], x["end"]) for x in db.list_segments(rid) if x["speaker_id"] == speaker_id]
    if not turns or not rec or not Path(rec["audio_path"]).exists():
        return None
    samples = audio.load(rec["audio_path"])
    return voiceprint.get_embedder(s["embedding_model"], 2).embed_turns(samples, turns)


def enroll_from_audio(name: str, path: str) -> dict:
    """Create/extend a voice profile from a clean sample of one person (e.g. 10-30 s)."""
    s = config.load()
    samples = audio.load(path)
    e = voiceprint.get_embedder(s["embedding_model"], 2).embed_turns(samples, _speech_windows(samples))
    if e is None:
        raise ValueError("Probe zu kurz oder zu leise")
    existing = next((p for p in db.list_profiles(with_embedding=True) if p["name"].lower() == name.lower()), None)
    if existing is not None and len(existing["embedding"]) == len(e):
        db.update_profile(existing["id"], embedding=voiceprint.update_mean(existing["embedding"], existing["samples"], e, 2),
                          samples=existing["samples"] + 2)
        return db.get_profile(existing["id"])
    return db.get_profile(db.create_profile(name, e, samples=2))


def _speech_windows(samples: np.ndarray, win: float = 4.0) -> list[tuple[float, float]]:
    dur = len(samples) / audio.SR
    rms_floor = float(np.sqrt(np.mean(samples ** 2))) * 0.3 if len(samples) else 0
    out = []
    t = 0.0
    while t < dur:
        b = min(dur, t + win)
        seg = samples[int(t * audio.SR):int(b * audio.SR)]
        if len(seg) and float(np.sqrt(np.mean(seg ** 2))) > rms_floor:
            out.append((t, b))
        t = b
    return out or [(0.0, dur)]


def reidentify(rid: str) -> int:
    """Re-run profile matching for an existing recording (e.g. after enrolling new people). Returns #renamed."""
    s = config.load()
    sps = [x for x in db.list_speakers(rid, with_embedding=True) if x.get("embedding") is not None]
    profiles = db.list_profiles(with_embedding=True)
    matches = voiceprint.match_profiles({x["id"]: x["embedding"] for x in sps}, profiles, float(s["profile_threshold"]))
    for sid, (p, score) in matches.items():
        db.update_speaker(sid, name=p["name"], color=p["color"], profile_id=p["id"], match_score=round(score, 3))
    return len(matches)
