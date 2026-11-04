"""Stills from videos for the transcript: where the picture changes clearly (next slide, screen share, new scene) one
frame is kept, so reading the transcript shows what was on screen when it was said.

Only key frames are decoded (fast, also for long recordings); a change is measured on a tiny colour copy as the share of
clearly changed pixels, so noise, a mouse pointer or small movements don't count – a new slide does. Stored as JPEG next to the recording – encoded with FFmpeg's own
MJPEG encoder (PyAV), no extra image library. Everything stays on this computer."""
from __future__ import annotations

import logging
import re
import shutil
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from . import config

log = logging.getLogger("rekord.frames")

WIDTH = 640           # stored width (height follows the video); plenty for a slide, ~40–80 KB each
MAX_FRAMES = 120      # per video – a long webinar stays readable
MIN_GAP = 2.0         # seconds between two stills at least (longer videos: spread over the whole length)
PIXEL = 28            # colour difference (0–255, strongest channel) at which a pixel of a 64×36 copy counts as changed …
CHANGE = 0.18         # … and the share of changed pixels that makes a new picture (a slide: most; a pointer: few)
_NAME = re.compile(r"^f(\d{10})\.jpg$")


def folder(rid: str) -> Path:
    return config.HOME / "frames" / rid


def _name(t: float) -> str:
    return f"f{int(round(t * 1000)):010d}.jpg"


def _jpeg(frame) -> bytes:
    """One still as JPEG (FFmpeg's MJPEG encoder – a fresh one per picture, it takes one frame and is done)."""
    w = WIDTH if frame.width >= WIDTH else frame.width - frame.width % 2
    h = max(2, int(round(frame.height * w / frame.width / 2)) * 2)
    img = frame.reformat(width=w, height=h, format="yuvj420p")
    enc = av.CodecContext.create("mjpeg", "w")
    enc.width, enc.height, enc.pix_fmt = w, h, "yuvj420p"
    enc.time_base = Fraction(1, 25)
    enc.options = {"q:v": "4"}
    img.pts = 0
    return b"".join(bytes(p) for p in [*enc.encode(img), *enc.encode(None)])


def extract(src: str | Path, rid: str, offset: float = 0.0) -> int:
    """Stills from the video track of `src` into the recording's folder, at their time in the recording (`offset`
    for a part appended later). Returns how many were kept; 0 for audio-only files."""
    try:
        c = av.open(str(src))
    except Exception as e:  # noqa: BLE001 - not readable as media
        log.warning("frames %s: %s", src, e)
        return 0
    with c:
        from .audio import _cover_art
        vs = next((s for s in c.streams if s.type == "video" and not _cover_art(s)), None)
        if vs is None:
            return 0
        duration = float(c.duration / av.time_base) if c.duration else 0.0
        gap = max(MIN_GAP, duration / MAX_FRAMES) if duration else MIN_GAP
        vs.codec_context.skip_frame = "NONKEY"  # key frames only: fast, and they're the clean ones
        out = folder(rid)
        out.mkdir(parents=True, exist_ok=True)
        last, last_t, kept = None, -1e9, 0
        try:
            for frame in c.decode(vs):
                if frame.time is None:
                    continue
                t = float(frame.time)
                # in colour: two slides can be equally bright in grey and still look nothing alike
                small = frame.reformat(width=64, height=36, format="rgb24").to_ndarray().astype(np.int16)
                changed = last is None or float((np.abs(small - last).max(axis=2) > PIXEL).mean()) > CHANGE
                if not changed or t - last_t < gap:
                    continue
                (out / _name(offset + t)).write_bytes(_jpeg(frame))
                last, last_t, kept = small, t, kept + 1
                if kept >= MAX_FRAMES:
                    break
        except Exception as e:  # noqa: BLE001 - a damaged end of file: keep what's there
            log.warning("frames %s after %d stills: %s", src, kept, e)
    log.info("frames: %d stills from %s (%s)", kept, Path(src).name, rid)
    return kept


def has(rid: str) -> bool:
    d = folder(rid)
    return d.is_dir() and any(_NAME.match(p.name) for p in d.iterdir())


def items(rid: str) -> list[dict]:
    """[{t, file, path}] in time order."""
    d = folder(rid)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.iterdir()):
        m = _NAME.match(p.name)
        if m:
            out.append({"t": int(m[1]) / 1000, "file": p.name, "path": str(p)})
    return out


def attach(rid: str, segments: list[dict]) -> list[dict]:
    """Each still with the transcript line it belongs to: the one spoken while it was on screen (or the next one)."""
    frames = items(rid)
    if not segments:
        return [{**f, "seg": None} for f in frames]
    segs = sorted(segments, key=lambda s: s["start"])
    out, i = [], 0
    for f in frames:
        while i < len(segs) - 1 and segs[i]["end"] < f["t"]:
            i += 1
        out.append({**f, "seg": segs[i]["id"]})
    return out


def remove(rid: str) -> None:
    shutil.rmtree(folder(rid), ignore_errors=True)
