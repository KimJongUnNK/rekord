"""Generates the app icons (PWA, iOS, desktop). Bold typographic mark: a record dot + 'R'."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "rekord" / "web" / "icons"
OUT.mkdir(parents=True, exist_ok=True)
BG, FG, ACC = (11, 11, 12), (246, 245, 242), (255, 90, 31)


def font(size):
    for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Black.ttf",
              "C:/Windows/Fonts/arialbd.ttf"]:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def icon(size, maskable=False):
    im = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(im)
    pad = size * (0.2 if maskable else 0.12)
    inner = size - 2 * pad
    f = font(int(inner * 0.78))
    d.text((pad + inner * 0.02, pad + inner * 0.5), "R", font=f, fill=FG, anchor="lm")
    r = inner * 0.16
    cx, cy = pad + inner - r * 1.05, pad + r * 1.25
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACC)
    return im


for s in (192, 512):
    icon(s).save(OUT / f"icon-{s}.png")
    icon(s, True).save(OUT / f"maskable-{s}.png")
icon(180).save(OUT / "apple-touch-icon.png")
icon(1024).save(OUT / "icon-1024.png")
icon(256).save(ROOT / "desktop" / "icon.png")
icon(256).save(ROOT / "desktop" / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
print("icons ->", OUT)
