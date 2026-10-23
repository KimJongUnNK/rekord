"""Full processing of one recording: decode -> diarize -> voiceprints -> identify people -> transcribe -> save."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import numpy as np

from . import audio, config, db
from .engines import asr, voiceprint
from .engines.diarize import clean_turns, diarize, refine_turns

log = logging.getLogger("rekord.pipeline")


UNKNOWN = "Nicht erkannte Stimme"  # all voices REKORD doesn't know are collected here – never "Sprecher 1, 2, 3"
UNKNOWN_LABEL = 999
UNKNOWN_COLOR = "#8A877F"
LECTURER, AUDIENCE = "Vortragende Person", "Publikum"  # „Vorlesung“: one main voice, everyone else collected
LECTURER_LABEL = 998
LECTURER_COLOR = "#FF5A1F"


def speaker_name(i: int) -> str:  # older recordings / live keys
    return f"Sprecher {i + 1}"


def process(rid: str, on_event=None) -> dict:
    s = config.load()
    if os.environ.get("REKORD_JOB_THREADS"):  # in the analysis process: the thread budget it was started with
        s = {**s, "threads": int(os.environ["REKORD_JOB_THREADS"])}
    rec = db.get_recording(rid)
    if rec is None:
        raise KeyError(rid)
    t0 = time.time()

    last = {"name": "", "p": -1.0, "t": 0.0}

    def stage(name: str, p: float) -> None:
        # the engines report very often (diarization: every half second of audio) – a database write and a
        # redraw each time cost more than they tell: a new step, or ≥1 % more and ≥0.5 s later
        now = time.monotonic()
        if name == last["name"] and (p - last["p"] < 0.01 or now - last["t"] < 0.5):
            return
        last.update(name=name, p=p, t=now)
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
    # headcount from "Wer ist dabei?" (known people + new ones) beats the global setting
    n_spk = (len(part_ids) + guests) if (part_ids or guests) else int(s.get("num_speakers") or 0)
    if part.get("meeting") == "lecture":
        n_spk = 0  # a lecture hall: nobody counts the audience
    turns = diarize(samples, s["embedding_model"], n_spk, float(s["cluster_threshold"]),
                    int(s["threads"]), progress=lambda p: stage("Sprecher trennen", 0.05 + 0.3 * p))
    if not turns and duration > 1:
        turns = [(0.0, duration, 0)]  # single speaker fallback (e.g. no clear speech boundaries)

    # 2. voiceprint per speaker + match against known people
    stage("Personen erkennen", 0.36)
    emb = voiceprint.get_embedder(s["embedding_model"], 2)
    turns = refine_turns(samples, turns, emb, hop=0.5 if duration < 900 else 1.0)
    by_label, speaker_embs = _voiceprints(samples, turns, emb)
    if not n_spk and len(speaker_embs) > 1:  # one person split into two "speakers"? → merge near-identical voices
        merged = merge_similar_speakers(turns, speaker_embs, float(s.get("merge_threshold", MERGE_THRESHOLD)))
        if merged != turns:
            turns = clean_turns(merged)
            by_label, speaker_embs = _voiceprints(samples, turns, emb)
    profiles = [p for p in db.list_profiles(with_embedding=True) if p["embedding"] is not None]
    threshold = float(s["profile_threshold"])
    if part_ids:  # announced participants: compare only against them; with no guests it is a closed set
        profiles = [p for p in profiles if p["id"] in part_ids]
        if guests == 0 and part.get("meeting") != "lecture":
            threshold = min(threshold, voiceprint.OnlineClusterer.CLOSED_SET_FLOOR + 0.1)
    matches = voiceprint.match_profiles(speaker_embs, profiles, threshold)

    speakers = []
    unknown = [lbl for lbl in sorted(by_label) if lbl not in matches]
    lecture = part.get("meeting") == "lecture"
    lecturer = None
    if lecture and unknown and not any(_talk_time(turns, lbl) > max((_talk_time(turns, u) for u in unknown), default=0)
                                       for lbl in matches):
        # nobody known talks more than the loudest unknown voice → that one is the person giving the lecture
        lecturer = max(unknown, key=lambda lbl: _talk_time(turns, lbl))
        unknown = [lbl for lbl in unknown if lbl != lecturer]
        speakers.append({"label": LECTURER_LABEL, "name": LECTURER, "color": LECTURER_COLOR, "profile_id": None,
                         "match_score": 0, "embedding": speaker_embs.get(lecturer)})
    for lbl in sorted(by_label):
        if lbl in matches:
            p, score = matches[lbl]
            speakers.append({"label": lbl, "name": p["name"], "color": p["color"], "profile_id": p["id"],
                             "match_score": round(score, 3), "embedding": speaker_embs.get(lbl)})
    if unknown:  # one entry for everything not recognized; its voiceprint only if it is a single person
        speakers.append({"label": UNKNOWN_LABEL, "name": AUDIENCE if lecture else UNKNOWN, "color": UNKNOWN_COLOR,
                         "profile_id": None, "match_score": 0,
                         "embedding": speaker_embs.get(unknown[0]) if len(unknown) == 1 else None, "voices": len(unknown)})

    # 3. words
    stage("Transkribieren", 0.4)
    engine = asr.get_engine(s)
    segs = engine.transcribe_turns(samples, turns, progress=lambda p: stage("Transkribieren", 0.4 + 0.55 * p))
    for seg in segs:
        seg["text"] = asr.apply_vocabulary(seg["text"], s.get("vocabulary", []))
    langs = [x.get("lang") for x in segs if x.get("lang")]
    language = max(set(langs), key=langs.count) if langs else (s.get("language") or "")

    # unknown voices → the one bucket; each line keeps which voice it was, so naming one line can name them all
    for seg in segs:
        if seg["label"] in unknown:
            seg["voice"], seg["label"] = seg["label"], UNKNOWN_LABEL
        elif lecturer is not None and seg["label"] == lecturer:
            seg["label"] = LECTURER_LABEL

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


# Voiceprints of the same person (two halves of their turns) score 0.7–0.9, different people mostly below 0.4.
MERGE_THRESHOLD = 0.65


def _voiceprints(samples, turns, emb):
    by_label: dict[int, list[tuple[float, float]]] = {}
    for a, b, spk in turns:
        by_label.setdefault(spk, []).append((a, b))
    return by_label, {lbl: e for lbl, ts in by_label.items() if (e := emb.embed_turns(samples, ts)) is not None}


def merge_similar_speakers(turns: list[tuple[float, float, int]], embs: dict[int, np.ndarray],
                           threshold: float = MERGE_THRESHOLD) -> list[tuple[float, float, int]]:
    """Clustering sometimes splits one voice into two speakers. Merge the most similar pair while their
    voiceprints are clearly the same person (weighted by speaking time, so the bigger cluster dominates)."""
    embs = dict(embs)
    talk = {k: sum(b - a for a, b, s in turns if s == k) for k in embs}
    while len(embs) > 1:
        score, keep, drop = max((voiceprint.cosine(embs[a], embs[b]), a, b) for a in embs for b in embs if a < b)
        if score < threshold:
            break
        if talk[drop] > talk[keep]:
            keep, drop = drop, keep
        w = talk[keep] / ((talk[keep] + talk[drop]) or 1)
        embs[keep] = voiceprint.normalize(w * embs[keep] + (1 - w) * embs[drop])
        talk[keep] += talk.pop(drop)
        del embs[drop]
        turns = [(a, b, keep if s == drop else s) for a, b, s in turns]
        log.info("merged speaker %d into %d (voiceprint similarity %.2f)", drop, keep, score)
    return turns


def assign_segment(seg_id: int, name: str, remember: bool = True, whole_voice: bool = False) -> dict:
    """"Wer sagt das?" for a transcript line: move it – or, with whole_voice, every line of that unknown voice – to a
    person (created if needed). With remember, that audio also trains the person's voiceprint."""
    name = name.strip()
    row = db.connect().execute("SELECT * FROM segments WHERE id=?", (seg_id,)).fetchone()
    if row is None or not name:
        raise KeyError(seg_id)
    seg = dict(row)
    rid, old = seg["recording_id"], seg["speaker_id"]
    lines = [seg]
    if whole_voice and seg.get("voice") is not None:
        lines = [x for x in db.list_segments(rid) if x["speaker_id"] == old and x.get("voice") == seg["voice"]]
    profile = next((p for p in db.list_profiles(with_embedding=True) if p["name"].lower() == name.lower()), None)
    target = next((x for x in db.list_speakers(rid) if x["name"].lower() == name.lower() and x["id"] != old), None)
    if target is None:
        color = profile["color"] if profile else db.PALETTE[len(db.list_speakers(rid)) % len(db.PALETTE)]
        tid = db.add_speaker(rid, profile["name"] if profile else name, color, profile["id"] if profile else None)
    else:
        tid = target["id"]
    for x in lines:
        db.update_segment(x["id"], speaker_id=tid)
    rec = db.get_recording(rid)
    samples = audio.load(rec["audio_path"]) if rec and rec.get("audio_path") and Path(rec["audio_path"]).exists() else None
    emb = voiceprint.get_embedder(config.load()["embedding_model"], 2)
    if remember and samples is not None:
        e = emb.embed_turns(samples, [(x["start"], x["end"]) for x in lines])
        if e is not None:
            if profile is not None and len(profile["embedding"]) == len(e):
                db.update_profile(profile["id"], embedding=voiceprint.update_mean(profile["embedding"], profile["samples"], e),
                                  samples=profile["samples"] + 1)
            else:
                profile = db.get_profile(db.create_profile(name, e))
            db.update_speaker(tid, profile_id=profile["id"], color=profile["color"], name=profile["name"], embedding=e)
    if old is not None:
        _recount_bucket(old, samples, emb)
        db.delete_speaker_if_unused(old)
    return {"speaker_id": tid, "profile_id": profile["id"] if profile else None, "moved": len(lines)}


def _recount_bucket(sid: int, samples, emb) -> None:
    """After lines left the "Nicht erkannte Stimme" bucket: how many voices are still in it? One left → it gets its own
    voiceprint again, so "Wer ist das? → Merken" works for it."""
    sp = db.get_speaker(sid)
    if sp is None or sp["name"] not in (UNKNOWN, AUDIENCE):
        return
    rest = [x for x in db.list_segments(sp["recording_id"]) if x["speaker_id"] == sid]
    voices = {x.get("voice") for x in rest if x.get("voice") is not None}
    e = emb.embed_turns(samples, [(x["start"], x["end"]) for x in rest]) if len(voices) <= 1 and samples is not None and rest else None
    db.update_speaker(sid, voices=max(1, len(voices)), embedding=e)


def remember_speaker(rid: str, speaker_id: int, name: str) -> dict:
    """Rename a speaker and store/merge their voiceprint as a profile -> recognized automatically from now on."""
    sp = db.get_speaker(speaker_id, with_embedding=True)
    if sp is None or sp["recording_id"] != rid:
        raise KeyError(speaker_id)
    if (sp.get("voices") or 1) > 1:
        raise ValueError(f"In „{sp['name']}“ stecken mehrere Personen. Tippe im Transkript bei einem Satz auf den Namen "
                         "und wähle, wer das ist – so lernt REKORD jede Stimme einzeln.")
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


ENROLL_MIN_SECONDS = 8.0  # hard floor; the app asks for ~45 s (a text per person)


def _talk_time(turns: list, label: int) -> float:
    return sum(b - a for a, b, lbl in turns if lbl == label)


def enroll_from_audio(name: str, path: str, mode: str = "read") -> dict:
    """Create/extend a voice profile from a sample of one person.

    mode "read": the person read their text alone (30–60 s) – a sample with several voices is refused.
    mode "free": someone just talked (e.g. a lecturer, anything they like) – other voices that come up in between
    (a question from the room, a cough) are left out and only the main voice is learned.
    Returns the profile plus "quality": seconds of speech, how consistent the voice was, seconds left out."""
    s = config.load()
    samples = audio.load(path)
    windows = _speech_windows(samples, win=3.0)
    speech = sum(b - a for a, b in windows)
    if speech < ENROLL_MIN_SECONDS:
        raise ValueError(f"Zu kurz ({speech:.0f} s Sprache). " + ("Die Person noch etwas länger reden lassen."
                         if mode == "free" else "Bitte den ganzen Text vorlesen – mindestens 20 Sekunden."))
    emb = voiceprint.get_embedder(s["embedding_model"], 2)
    pairs = [((a, b), v) for a, b in windows if (v := emb.embed(samples[int(a * audio.SR):int(b * audio.SR)])) is not None]
    if not pairs:
        raise ValueError("Probe zu kurz oder zu leise")
    left_out = 0.0
    if mode == "free" and len(pairs) >= 3:
        main = _main_voice(pairs)
        left_out = sum(b - a for (a, b), _ in pairs) - sum(b - a for (a, b), _ in main)
        if sum(b - a for (a, b), _ in main) < ENROLL_MIN_SECONDS:
            raise ValueError("Keine Stimme war lange genug zu hören. Die eine Person länger reden lassen – "
                             "am besten mit dem Mikro in ihrer Nähe.")
        pairs = main
    vecs = [v for _, v in pairs]
    speech = sum(b - a for (a, b), _ in pairs)
    mean = voiceprint.normalize(np.mean(vecs, axis=0))
    sims = sorted(voiceprint.cosine(v, mean) for v in vecs)
    # how alike the windows are: one steady voice ~0.85–0.95, several people or heavy noise far below
    consistency = sims[len(sims) // 4]
    if consistency < 0.65 and len(vecs) >= 4:
        raise ValueError("Die Probe klingt nach mehreren Stimmen oder starkem Störgeräusch. " + (
            "Die Person länger allein reden lassen, das Mikro näher zu ihr." if mode == "free"
            else "Bitte allein und in ruhiger Umgebung nochmal vorlesen – oder „Einfach reden lassen“ wählen."))
    keep = [v for v in vecs if voiceprint.cosine(v, mean) >= 0.5] or vecs  # coughs, laughs, a door: left out
    e = voiceprint.normalize(np.mean(keep, axis=0))
    weight = 2 + int(speech // 20)  # a long sample counts more than a short naming in a meeting
    existing = next((p for p in db.list_profiles(with_embedding=True) if p["name"].lower() == name.lower()), None)
    if existing is not None and len(existing["embedding"]) == len(e):
        db.update_profile(existing["id"], embedding=voiceprint.update_mean(existing["embedding"], existing["samples"], e, weight),
                          samples=existing["samples"] + weight)
        prof = db.get_profile(existing["id"])
    else:
        prof = db.get_profile(db.create_profile(name, e, samples=weight))
    return {**prof, "quality": {"seconds": round(speech, 1), "consistency": round(float(consistency), 2),
                                "left_out": round(left_out, 1)}}


def _main_voice(pairs: list, threshold: float = 0.6) -> list:
    """The voice that talks most in a free sample: windows grouped by voice, the biggest group wins."""
    groups: list[list] = []
    for w, v in pairs:
        best, score = None, threshold
        for g in groups:
            c = voiceprint.cosine(v, voiceprint.normalize(np.mean([x for _, x in g], axis=0)))
            if c >= score:
                best, score = g, c
        if best is None:
            groups.append([(w, v)])
        else:
            best.append((w, v))
    return max(groups, key=lambda g: sum(b - a for (a, b), _ in g))


def recording_voices(rid: str) -> list[dict]:
    """Every voice in a recording, to learn one of them as a person ("Aus einer Aufnahme lernen").
    A bucket of unknown voices is split voice by voice."""
    segs = db.list_segments(rid)
    out = []
    for sp in db.list_speakers(rid):
        lines = [x for x in segs if x["speaker_id"] == sp["id"]]
        groups: dict = {}
        for x in lines:
            groups.setdefault(x.get("voice") if sp["name"] in (UNKNOWN, AUDIENCE) else None, []).append(x)
        for voice, ls in sorted(groups.items(), key=lambda kv: kv[1][0]["start"]):
            longest = sorted(ls, key=lambda x: x["end"] - x["start"], reverse=True)[:3]
            out.append({"speaker_id": sp["id"], "voice": voice if len(groups) > 1 else None, "name": sp["name"],
                        "known": sp.get("profile_id") is not None, "color": sp["color"],
                        "seconds": round(sum(x["end"] - x["start"] for x in ls), 1), "lines": len(ls),
                        "first": round(ls[0]["start"], 1), "text": (ls[0].get("text") or "")[:120],
                        "samples": [[round(x["start"], 2), round(x["end"], 2)] for x in longest]})
    return [v for v in out if v["seconds"] > 0]


def learn_voice(rid: str, speaker_id: int, voice: int | None, name: str) -> dict:
    """Learn one voice of a recording as a person (the lecturer from a lecture, someone from a call)."""
    name = name.strip()
    if not name:
        raise ValueError("Namen eingeben")
    if voice is not None:
        seg = next((x for x in db.list_segments(rid) if x["speaker_id"] == speaker_id and x.get("voice") == voice), None)
        if seg is None:
            raise KeyError(speaker_id)
        assign_segment(seg["id"], name, remember=True, whole_voice=True)
    else:
        remember_speaker(rid, speaker_id, name)
    return next(p for p in db.list_profiles() if p["name"].lower() == name.lower())


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
