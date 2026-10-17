"""Audio I/O via PyAV (bundled FFmpeg, no system install needed)."""
from __future__ import annotations

import wave
from pathlib import Path

import av
import numpy as np

SR = 16000


def load(path: str | Path, sr: int = SR) -> np.ndarray:
    """Decode any audio/video file to mono float32 at `sr`."""
    chunks = []
    with av.open(str(path)) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("Datei enthält keine Audiospur")
        resampler = av.AudioResampler(format="flt", layout="mono", rate=sr)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.ascontiguousarray(np.concatenate(chunks).astype(np.float32))


def write_wav(path: str | Path, samples: np.ndarray, sr: int = SR) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def encode_m4a(samples: np.ndarray, path: str | Path, sr: int = SR, bitrate: int = 48000) -> None:
    """Compact storage (~20 MB / 1h at 48 kbit AAC)."""
    with av.open(str(path), "w", format="mp4") as out:
        st = out.add_stream("aac", rate=sr)
        st.bit_rate = bitrate
        st.layout = "mono"
        pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
        step = 1024 * 16
        for i in range(0, len(pcm), step):
            fr = av.AudioFrame.from_ndarray(pcm[i:i + step].reshape(1, -1), format="s16", layout="mono")
            fr.sample_rate = sr
            for pkt in st.encode(fr):
                out.mux(pkt)
        for pkt in st.encode(None):
            out.mux(pkt)


def peaks(samples: np.ndarray, n: int = 800) -> list[float]:
    """Downsampled waveform envelope for the UI (0..1)."""
    if len(samples) == 0:
        return []
    n = max(1, min(n, len(samples)))
    usable = len(samples) // n * n
    blocks = np.abs(samples[:usable]).reshape(n, -1).max(axis=1)
    m = float(blocks.max()) or 1.0
    return [round(float(v / m), 3) for v in blocks]


class WavAppender:
    """Incrementally write 16-bit mono PCM (used by live sessions)."""

    def __init__(self, path: str | Path, sr: int = SR):
        self.path = Path(path)
        self._w = wave.open(str(self.path), "wb")
        self._w.setnchannels(1)
        self._w.setsampwidth(2)
        self._w.setframerate(sr)
        self.frames = 0
        self.sr = sr

    def write_float(self, samples: np.ndarray) -> None:
        pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
        self._w.writeframes(pcm.tobytes())
        self.frames += len(pcm)

    def close(self) -> None:
        self._w.close()

    @property
    def seconds(self) -> float:
        return self.frames / self.sr
