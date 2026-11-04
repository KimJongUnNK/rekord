"""Test media made on the fly: a 'presentation' video (three slides with a moving pointer) with sound."""
from pathlib import Path

import av
import numpy as np

FIX = Path(__file__).parent / "fixtures"
SLIDES = [(230, 60, 40), (40, 120, 230), (40, 200, 90)]  # red and blue are equally bright in grey on purpose


def slides_video(path, seconds_per_slide=5, fps=10, sound=True):
    from rekord import audio
    n = len(SLIDES) * seconds_per_slide * fps
    with av.open(str(path), "w", format="mp4") as out:
        vs = out.add_stream("mpeg4", rate=fps)
        vs.width, vs.height, vs.pix_fmt = 320, 180, "yuv420p"
        vs.options = {"g": str(fps)}  # a key frame every second
        if sound:
            a = out.add_stream("aac", rate=16000)
            a.layout = "mono"
        for i in range(n):
            img = np.zeros((180, 320, 3), np.uint8)
            img[:] = SLIDES[i // (seconds_per_slide * fps)]
            x = 40 + (i % (seconds_per_slide * fps)) * 2
            img[60:120, x:x + 40] = 255  # a pointer moving across – must not count as a new slide
            f = av.VideoFrame.from_ndarray(img, format="rgb24")
            f.pts = i
            for pk in vs.encode(f):
                out.mux(pk)
        for pk in vs.encode(None):
            out.mux(pk)
        if sound:
            x = audio.load(FIX / "meeting1.wav")[:16000 * len(SLIDES) * seconds_per_slide]
            fr = av.AudioFrame.from_ndarray((x * 32767).astype(np.int16).reshape(1, -1), format="s16", layout="mono")
            fr.sample_rate = 16000
            for pk in [*a.encode(fr), *a.encode(None)]:
                out.mux(pk)
    return Path(path)
