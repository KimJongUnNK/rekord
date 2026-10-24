"""Live meetings: stream audio in, get 'who is speaking now' + near-live transcript out.

Client -> server: binary frames of 16-bit little-endian mono PCM (any sample rate, announced in 'start'),
                  JSON control: {"type":"start","sample_rate":16000,"title":"..."} | {"type":"highlight"}
                  | {"type":"name_speaker","key":0,"name":"Lisa"} | {"type":"pause"} | {"type":"resume"} | {"type":"stop"}
Server -> client: {"type":"speaking","key","name","color","score","t"}   ~ every 0.5 s while someone talks
                  {"type":"silence","t"}
                  {"type":"segment","key","name","color","start","end","text"}
                  {"type":"gap","start","end"}        the live text skipped this (a slow computer) – after Stopp it's complete
                  {"type":"speakers","items":[...]}    session roster
                  {"type":"level","rms"}               input level meter
                  {"type":"stopped","id"}              recording saved, full-quality processing queued
"""
from __future__ import annotations

import collections
import logging
import threading
import time

import numpy as np

from . import audio, config, db, jobs, models, pipeline
from .audio import SR
from .engines import asr, voiceprint

log = logging.getLogger("rekord.live")

WIN = 512  # silero window at 16 kHz
SPEAKING_EVERY = 0.5
SPEAKING_WINDOW = 1.6
QUIET_AFTER = 1.2  # "nobody speaks" only after this much real quiet – not in every breath between two words
MERGE_MAX = 10.0  # behind with the transcript: short lines of one speaker in one go (saves whisper's fixed cost)
LAG_MAX = 20.0  # the live transcript never lags more than this: further behind, its preview skips to now


resample = audio.resample  # a whole signal; streams use audio.Resampler


class LiveSession:
    def __init__(self, emit, title: str = "", source: str = "live", sample_rate: int = SR,
                 participants: list[int] | None = None, guests: int = 0, meeting: str = "person",
                 call_audio: bool = False):
        """meeting="online": with call_audio the computer's sound (the other people in Teams/Zoom/Meet) is mixed
        into the microphone – sound only, no picture."""
        import sherpa_onnx
        self.s = config.load()
        self.emit = emit
        self.sr_in = int(sample_rate)
        self._rs = audio.Resampler(self.sr_in)  # one filter across all chunks of this stream
        models.ensure(["silero-vad", self.s["embedding_model"]])
        vcfg = sherpa_onnx.VadModelConfig(
            silero_vad=sherpa_onnx.SileroVadModelConfig(model=str(models.path("silero-vad")), threshold=0.5,
                                                        min_silence_duration=0.35, min_speech_duration=0.25,
                                                        max_speech_duration=12.0, window_size=WIN),
            sample_rate=SR, num_threads=1)
        self.vad = sherpa_onnx.VoiceActivityDetector(vcfg, buffer_size_in_seconds=120)
        self.embedder = voiceprint.get_embedder(self.s["embedding_model"], 2)
        profiles = db.list_profiles(with_embedding=True)
        self.participants = [int(x) for x in (participants or [])]
        self.guests = max(0, int(guests or 0))
        self.meeting = meeting if meeting in ("online", "lecture") else "person"
        lecture = self.meeting == "lecture"
        if self.participants:  # only compare against the people who are actually in the room
            profiles = [p for p in profiles if p["id"] in self.participants]
        # a lecture hall: nobody counts the audience – no closed set, no headcount cap
        self.cluster = voiceprint.OnlineClusterer(profiles, float(self.s["live_profile_threshold"]),
                                                  float(self.s["live_cluster_threshold"]),
                                                  closed_set=bool(self.participants) and self.guests == 0 and not lecture,
                                                  max_speakers=0 if lecture else len(self.participants) + self.guests)
        self.engine = None
        if self.s.get("live_transcribe", True):
            try:
                from . import system  # short clips: half the cores are plenty – the rest stays with the apps in front
                self.engine = asr.get_engine({**self.s, "threads": system.processing_threads(self.s["threads"], True)})
            except Exception as e:  # noqa: BLE001 - live works without words, too
                log.warning("live ASR unavailable: %s", e)
        self.title = title or time.strftime("Meeting %d.%m.%Y %H:%M")
        self.rec = db.create_recording(self.title, "", source=source, status="recording")
        self.rid = self.rec["id"]
        if self.participants or self.guests or self.meeting != "person":
            db.update_recording(self.rid, participants={"ids": self.participants, "guests": self.guests, "meeting": self.meeting})
        self.call = None
        self.notes: list[str] = []
        if self.meeting == "online" and call_audio:
            from . import capture
            self.call = capture.SystemAudio()
            if not self.call.start():
                self.notes.append(self.call.error)
                self.call = None

        self.wav_path = config.AUDIO_DIR / f"{self.rid}.wav"
        self.wav = audio.WavAppender(self.wav_path)
        self.ring = np.zeros(0, dtype=np.float32)
        self.pending = np.zeros(0, dtype=np.float32)
        self.t = 0.0  # seconds of audio received
        self.last_speaking = 0.0
        self.paused = False
        self.highlights: list[float] = []
        self.segments: list[dict] = []
        self.names: dict[int, str] = {}  # key -> manual name for unknown voices
        # two workers: "who speaks now" must never wait behind the transcript of the last sentence
        self._segs: collections.deque = collections.deque()  # finished speech pieces for the transcript, in order
        self._segs_cv = threading.Condition()
        self._probe = None  # only the newest "who speaks now" sample counts
        self._probe_cv = threading.Condition()
        self._quiet_since: float | None = None
        self._closed = False
        self._worker = threading.Thread(target=self._run, daemon=True, name=f"live-{self.rid}")
        self._prober = threading.Thread(target=self._run_probes, daemon=True, name=f"live-who-{self.rid}")
        self._worker.start()
        self._prober.start()
        self._last_probe: dict | None = None
        self._lock = threading.RLock()  # clusters/segments are touched by the worker and by name_speaker()
        self._unclear_before = False

    # ------------------------------------------------------------ input
    def feed_pcm16(self, data: bytes) -> None:
        x = self._rs(np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0)
        if self.call is not None:  # online: the others in the call, in step with the microphone
            call = self.call.read(len(x))
            if not self.paused:
                x = np.clip(x + call, -1.0, 1.0)
        self.feed(x)

    def feed(self, x: np.ndarray) -> None:
        if self.paused or self._closed or len(x) == 0:
            return
        self.wav.write_float(x)
        self.ring = np.concatenate([self.ring, x])[-int(SR * 4):]
        self.pending = np.concatenate([self.pending, x])
        n = len(self.pending) // WIN * WIN
        if n:
            self.vad.accept_waveform(self.pending[:n])
            self.pending = self.pending[n:]
        prev_t = self.t
        self.t += len(x) / SR
        if int(self.t * 4) != int(prev_t * 4):
            self.emit({"type": "level", "rms": round(float(np.sqrt(np.mean(x ** 2))), 4), "t": round(self.t, 2)})
        self._drain_vad()
        if self.t - self.last_speaking >= SPEAKING_EVERY:
            self.last_speaking = self.t
            if self.vad.is_speech_detected():
                self._quiet_since = None
                with self._probe_cv:
                    self._probe = (self.ring[-int(SR * SPEAKING_WINDOW):].copy(), self.t)
                    self._probe_cv.notify()
            else:
                if self._quiet_since is None:
                    self._quiet_since = self.t
                if self.t - self._quiet_since >= QUIET_AFTER:
                    self.emit({"type": "silence", "t": round(self.t, 2)})

    def _drain_vad(self) -> None:
        while not self.vad.empty():
            seg = self.vad.front
            start = seg.start / SR
            samples = np.array(seg.samples, dtype=np.float32)
            self.vad.pop()
            with self._segs_cv:
                self._segs.append({"samples": samples, "start": start})
                self._segs_cv.notify()

    # ------------------------------------------------------------ control
    def highlight(self) -> float:
        self.highlights.append(round(self.t, 2))
        self.emit({"type": "highlight", "t": round(self.t, 2)})
        return self.t

    def name_speaker(self, key: int, name: str) -> None:
        """Name an unknown live voice. Creates a voice profile immediately -> recognized now and in future meetings."""
        with self._lock:
            self._name_speaker(key, name)

    def _name_speaker(self, key: int, name: str) -> None:
        c = next((c for c in self.cluster.clusters if c["key"] == key), None)
        if c is None or not name.strip():
            return
        name = name.strip()
        existing = next((p for p in db.list_profiles(with_embedding=True) if p["name"].lower() == name.lower()), None)
        if existing and len(existing["embedding"]) == len(c["emb"]):
            db.update_profile(existing["id"], embedding=voiceprint.update_mean(existing["embedding"], existing["samples"], c["emb"]),
                              samples=existing["samples"] + 1)
            prof = db.get_profile(existing["id"], with_embedding=True)
        else:
            prof = db.get_profile(db.create_profile(name, c["emb"]), with_embedding=True)
        c["profile"] = prof
        self.cluster.profiles = [p for p in self.cluster.profiles if p["id"] != prof["id"]] + [prof]
        if self.participants and prof["id"] not in self.participants:
            self.participants.append(prof["id"])
            self.guests = max(0, self.guests - 1)
            db.update_recording(self.rid, participants={"ids": self.participants, "guests": self.guests})
        for seg in self.segments:
            if seg["key"] == key:
                seg["name"], seg["color"] = prof["name"], prof["color"]
        self._roster()

    def stop(self) -> str:
        if self._closed:
            return self.rid
        self._closed = True
        if self.call is not None:
            self.call.stop()
        self.vad.flush()
        self._drain_vad()
        with self._segs_cv:
            self._segs.append(None)
            self._segs_cv.notify()
        with self._probe_cv:
            self._probe_cv.notify()
        self._worker.join(timeout=120)
        self._prober.join(timeout=5)
        self.wav.close()
        duration = self.wav.seconds
        final = self.wav_path
        peaks = []
        try:  # compact storage
            m4a = config.AUDIO_DIR / f"{self.rid}.m4a"
            samples = audio.load(self.wav_path)
            peaks = audio.peaks(samples)
            audio.encode_m4a(samples, m4a)
            final = m4a
            self.wav_path.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            log.warning("m4a encode failed, keeping wav: %s", e)
        db.update_recording(self.rid, audio_path=str(final), duration=duration, highlights=self.highlights, peaks=peaks)
        # keep the live transcript right away; the offline pass then upgrades it (better diarization + model)
        with self._lock:
            self._save_live_transcript()
        if duration >= 1.0:
            jobs.enqueue(self.rid)
        else:
            db.update_recording(self.rid, status="done")
        self.emit({"type": "stopped", "id": self.rid, "duration": duration})
        return self.rid

    # ------------------------------------------------------------ worker
    def _run_probes(self) -> None:
        """Who speaks right now – every half second while someone talks, independent of the transcript."""
        while True:
            with self._probe_cv:
                while self._probe is None and not self._closed:
                    self._probe_cv.wait()
                if self._probe is None:
                    break
                samples, t = self._probe
                self._probe = None
            try:
                e = self.embedder.embed(samples)
                if e is None:
                    continue
                with self._lock:
                    r = self.cluster.assign(e, update=False)
                    lab = self._label(r)
                # smoothing: a single unclear probe (overlap, cough, turn boundary) keeps the last speaker
                unclear = lab["key"] is None and not lab["known"]
                if unclear and self._last_probe is not None and not self._unclear_before:
                    lab = self._last_probe
                self._unclear_before = unclear
                if not unclear:
                    self._last_probe = lab
                self.emit({"type": "speaking", **lab, "score": r["score"], "t": round(t, 2)})
            except Exception as ex:  # noqa: BLE001
                log.exception("live probe: %s", ex)

    def _next_seg(self) -> dict | None:
        with self._segs_cv:
            while not self._segs:
                self._segs_cv.wait()
            return self._segs.popleft()

    def _run(self) -> None:
        """The live transcript. In step with the talk: piece by piece. Behind (a slow computer, many short pieces):
        the waiting pieces of the same speaker together – one transcription instead of many."""
        while True:
            item = self._next_seg()
            if item is None:
                break
            try:
                if self.t - (item["start"] + len(item["samples"]) / SR) > LAG_MAX and self.engine is not None:
                    self._catch_up(item)
                    continue
                group = [item]
                r = self._who(item)
                while True:
                    with self._segs_cv:
                        nxt = self._segs[0] if self._segs else None
                    if nxt is None or sum(len(g["samples"]) for g in group) / SR + len(nxt["samples"]) / SR > MERGE_MAX:
                        break
                    if self._who(nxt).get("key") != r.get("key") or r.get("key") is None:
                        break
                    group.append(self._next_seg())
                self._segment(group, r)
            except Exception as ex:  # noqa: BLE001
                log.exception("live worker: %s", ex)
        db.close()

    def _catch_up(self, first: dict) -> None:
        """Far behind (a slow computer): who spoke still counts, but the text of what's waiting is skipped – the
        preview continues with what is said now. After Stopp the full analysis transcribes everything."""
        skipped = [first]
        with self._segs_cv:
            while self._segs and self._segs[0] is not None and \
                    self.t - (self._segs[0]["start"] + len(self._segs[0]["samples"]) / SR) > LAG_MAX / 2:
                skipped.append(self._segs.popleft())
        for it in skipped:
            r = self._who(it)
            if r.get("skip"):
                continue
            with self._lock:
                self.segments.append({"start": round(it["start"], 2), "text": "", **self._label(r),
                                      "end": round(it["start"] + len(it["samples"]) / SR, 2)})
        self.emit({"type": "gap", "start": round(first["start"], 2),
                   "end": round(skipped[-1]["start"] + len(skipped[-1]["samples"]) / SR, 2)})

    def _who(self, item: dict) -> dict:
        """Whose voice a speech piece is (assigned once, also when it was looked at for grouping)."""
        if "r" in item:
            return item["r"]
        e = self.embedder.embed(item["samples"])
        with self._lock:
            if e is None:
                if not self.cluster.clusters:
                    item["r"] = {"key": None, "skip": True}
                    return item["r"]
                r = {"key": self.segments[-1]["key"] if self.segments else self.cluster.clusters[-1]["key"],
                     "profile_id": None, "name": None, "color": None, "score": 0, "new": False}
            else:
                r = self.cluster.assign(e)
                if r["new"]:
                    self._roster()
        item["r"] = r
        return r

    def _segment(self, group: list[dict], r: dict) -> None:
        if r.get("skip"):
            return
        start = group[0]["start"]
        end = group[-1]["start"] + len(group[-1]["samples"]) / SR
        text = ""
        if self.engine is not None:
            samples = np.concatenate([g["samples"] for g in group])
            clips = asr.split_long(0, len(samples) / SR, samples)
            parts = [self.engine.transcribe_clip(samples[int(a * SR):int(b * SR)])[0] for a, b in clips]
            text = asr.apply_vocabulary(asr.clean_text(" ".join(parts)), self.s.get("vocabulary", []))
        with self._lock:
            seg = {"start": round(start, 2), "end": round(end, 2), "text": text, **self._label(r)}
            self.segments.append(seg)
        self.emit({"type": "segment", **seg})

    def _label(self, r: dict) -> dict:
        key = r.get("key")
        if key is None:
            if r.get("name"):
                return {"key": None, "name": r["name"], "color": r["color"], "known": True, "profile_id": r.get("profile_id")}
            return {"key": None, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR, "known": False}
        c = next(c for c in self.cluster.clusters if c["key"] == key)
        if c["profile"]:
            return {"key": key, "name": c["profile"]["name"], "color": c["profile"]["color"], "known": True}
        if self.meeting == "lecture":  # the unknown voice that talks most gives the lecture, the others are the audience
            if key == self._lecturer(key):
                return {"key": key, "name": pipeline.LECTURER, "color": pipeline.LECTURER_COLOR, "known": False}
            return {"key": key, "name": pipeline.AUDIENCE, "color": pipeline.UNKNOWN_COLOR, "known": False}
        return {"key": key, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR, "known": False}

    def _lecturer(self, current=None):
        """Key of the unknown voice with the most talking time so far (in a lecture: the lecturer)."""
        unknown = [c["key"] for c in self.cluster.clusters if not c["profile"]]
        if not unknown:
            return None
        known_max = max((sum(s["end"] - s["start"] for s in self.segments if s.get("known") and s["key"] == c["key"])
                         for c in self.cluster.clusters if c["profile"]), default=0)
        talk = {k: sum(s["end"] - s["start"] for s in self.segments if s["key"] == k) for k in unknown}
        best = max(unknown, key=lambda k: (talk[k], k == current))
        return best if talk[best] >= known_max or not known_max else None

    def _roster(self) -> None:
        items = []
        heard = {c["profile"]["id"] for c in self.cluster.clusters if c["profile"]}
        talk = lambda k: sum(s["end"] - s["start"] for s in self.segments if s["key"] == k)  # noqa: E731
        unknown = [c for c in self.cluster.clusters if not c["profile"]]
        for c in self.cluster.clusters:
            if c["profile"]:
                items.append({**self._label({"key": c["key"]}), "talk": round(talk(c["key"]), 1)})
        if self.meeting == "lecture" and unknown and (lk := self._lecturer()) is not None:
            items.append({**self._label({"key": lk}), "talk": round(talk(lk), 1)})
            unknown = [c for c in unknown if c["key"] != lk]
        if unknown:  # one entry; tapping it names the voice heard last
            last = next((s["key"] for s in reversed(self.segments) if s["key"] in {c["key"] for c in unknown}), unknown[-1]["key"])
            items.append({**self._label({"key": last}), "talk": round(sum(talk(c["key"]) for c in unknown), 1), "voices": len(unknown)})
        for p in self.cluster.profiles:  # announced participants who haven't spoken yet
            if self.participants and p["id"] in self.participants and p["id"] not in heard:
                items.append({"key": None, "name": p["name"], "color": p["color"], "known": True, "talk": 0, "waiting": True})
        self.emit({"type": "speakers", "items": items})

    def _save_live_transcript(self) -> None:
        keys = sorted({s["key"] for s in self.segments if s["key"] is not None})
        speakers, unknown = [], []
        lk = self._lecturer() if self.meeting == "lecture" else None
        for k in keys:
            c = next(c for c in self.cluster.clusters if c["key"] == k)
            if not c["profile"] and k == lk:
                speakers.append({"label": k, "name": pipeline.LECTURER, "color": pipeline.LECTURER_COLOR, "embedding": c["emb"]})
                continue
            if not c["profile"]:
                unknown.append(c)
                continue
            speakers.append({"label": k, "name": c["profile"]["name"], "color": c["profile"]["color"], "profile_id": c["profile"]["id"],
                             "match_score": round(float(c.get("pscore", 0)), 3), "embedding": c["emb"]})
        if unknown:
            speakers.append({"label": pipeline.UNKNOWN_LABEL, "name": pipeline.AUDIENCE if lk is not None else pipeline.UNKNOWN,
                             "color": pipeline.UNKNOWN_COLOR,
                             "embedding": unknown[0]["emb"] if len(unknown) == 1 else None, "voices": len(unknown)})
        gone = {c["key"] for c in unknown}
        segs = [{"start": s["start"], "end": s["end"], "label": pipeline.UNKNOWN_LABEL if s["key"] in gone else s["key"], "text": s["text"],
                 "voice": s["key"] if s["key"] in gone else None} for s in self.segments if s["text"]]
        db.replace_transcript(self.rid, speakers, segs)


_sessions: dict[str, LiveSession] = {}


def register(sess: LiveSession) -> None:
    _sessions[sess.rid] = sess


def unregister(rid: str) -> None:
    _sessions.pop(rid, None)


def active() -> list[dict]:
    return [{"id": s.rid, "title": s.title, "t": round(s.t, 1), "paused": s.paused} for s in _sessions.values()]


def get(rid: str) -> LiveSession | None:
    return _sessions.get(rid)
