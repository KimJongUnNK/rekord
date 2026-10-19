"""Live meetings: stream audio in, get 'who is speaking now' + near-live transcript out.

Client -> server: binary frames of 16-bit little-endian mono PCM (any sample rate, announced in 'start'),
                  JSON control: {"type":"start","sample_rate":16000,"title":"..."} | {"type":"highlight"}
                  | {"type":"name_speaker","key":0,"name":"Lisa"} | {"type":"pause"} | {"type":"resume"} | {"type":"stop"}
Server -> client: {"type":"speaking","key","name","color","score","t"}   ~ every 0.5 s while someone talks
                  {"type":"silence","t"}
                  {"type":"segment","key","name","color","start","end","text"}
                  {"type":"speakers","items":[...]}    session roster
                  {"type":"level","rms"}               input level meter
                  {"type":"stopped","id"}              recording saved, full-quality processing queued
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

import numpy as np

from . import audio, config, db, jobs, models, pipeline
from .audio import SR
from .engines import asr, voiceprint

log = logging.getLogger("rekord.live")

WIN = 512  # silero window at 16 kHz
SPEAKING_EVERY = 0.5
SPEAKING_WINDOW = 1.6


def resample(x: np.ndarray, sr_in: int, sr_out: int = SR) -> np.ndarray:
    if sr_in == sr_out or len(x) == 0:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
    return np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x).astype(np.float32)


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
        if self.participants:  # only compare against the people who are actually in the room
            profiles = [p for p in profiles if p["id"] in self.participants]
        self.cluster = voiceprint.OnlineClusterer(profiles, float(self.s["live_profile_threshold"]),
                                                  float(self.s["live_cluster_threshold"]),
                                                  closed_set=bool(self.participants) and self.guests == 0,
                                                  max_speakers=len(self.participants) + self.guests)
        self.engine = None
        if self.s.get("live_transcribe", True):
            try:
                self.engine = asr.get_engine(self.s)
            except Exception as e:  # noqa: BLE001 - live works without words, too
                log.warning("live ASR unavailable: %s", e)
        self.title = title or time.strftime("Meeting %d.%m.%Y %H:%M")
        self.rec = db.create_recording(self.title, "", source=source, status="recording")
        self.rid = self.rec["id"]
        self.meeting = "online" if meeting == "online" else "person"
        if self.participants or self.guests or self.meeting == "online":
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
        self._work: "queue.Queue[tuple | None]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True, name=f"live-{self.rid}")
        self._worker.start()
        self._closed = False
        self._last_probe: dict | None = None
        self._lock = threading.RLock()  # clusters/segments are touched by the worker and by name_speaker()
        self._unclear_before = False

    # ------------------------------------------------------------ input
    def feed_pcm16(self, data: bytes) -> None:
        x = resample(np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0, self.sr_in)
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
                self._work.put(("speaking", self.ring[-int(SR * SPEAKING_WINDOW):].copy(), self.t))
            else:
                self.emit({"type": "silence", "t": round(self.t, 2)})

    def _drain_vad(self) -> None:
        while not self.vad.empty():
            seg = self.vad.front
            start = seg.start / SR
            samples = np.array(seg.samples, dtype=np.float32)
            self.vad.pop()
            self._work.put(("segment", samples, start))

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
        self._work.put(None)
        self._worker.join(timeout=120)
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
    def _run(self) -> None:
        while True:
            item = self._work.get()
            if item is None:
                break
            kind, samples, t = item
            try:
                if kind == "speaking":
                    if self._work.qsize() > 6:  # falling behind: skip stale 'speaking' probes
                        continue
                    e = self.embedder.embed(samples)
                    if e is not None:
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
                else:
                    self._segment(samples, t)
            except Exception as ex:  # noqa: BLE001
                log.exception("live worker: %s", ex)
        db.close()

    def _segment(self, samples: np.ndarray, start: float) -> None:
        end = start + len(samples) / SR
        e = self.embedder.embed(samples)
        with self._lock:
            if e is None:
                if not self.cluster.clusters:
                    return
                r = {"key": self.segments[-1]["key"] if self.segments else self.cluster.clusters[-1]["key"],
                     "profile_id": None, "name": None, "color": None, "score": 0, "new": False}
            else:
                r = self.cluster.assign(e)
                if r["new"]:
                    self._roster()
        text = ""
        if self.engine is not None:
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
        return {"key": key, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR, "known": False}

    def _roster(self) -> None:
        items = []
        heard = {c["profile"]["id"] for c in self.cluster.clusters if c["profile"]}
        talk = lambda k: sum(s["end"] - s["start"] for s in self.segments if s["key"] == k)  # noqa: E731
        unknown = [c for c in self.cluster.clusters if not c["profile"]]
        for c in self.cluster.clusters:
            if c["profile"]:
                items.append({**self._label({"key": c["key"]}), "talk": round(talk(c["key"]), 1)})
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
        for k in keys:
            c = next(c for c in self.cluster.clusters if c["key"] == k)
            if not c["profile"]:
                unknown.append(c)
                continue
            speakers.append({"label": k, "name": c["profile"]["name"], "color": c["profile"]["color"], "profile_id": c["profile"]["id"],
                             "match_score": round(float(c.get("pscore", 0)), 3), "embedding": c["emb"]})
        if unknown:
            speakers.append({"label": pipeline.UNKNOWN_LABEL, "name": pipeline.UNKNOWN, "color": pipeline.UNKNOWN_COLOR,
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
