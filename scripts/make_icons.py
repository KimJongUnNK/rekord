"""Generates the app icons. Bold typographic mark: a record dot + 'R'.

Browser icons (web/icons/icon-*, maskable-*) fill the whole square – the browser or phone rounds them itself.
The app icon (Dock, taskbar, window, Linux menus) is the same mark on a rounded square with transparent margin, the
way macOS draws app icons (Apple's grid: 824 of 1024 px, corner radius ~22 %) – a full square looks cut off there."""
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


def app_icon(size, mark: Image.Image | None = None):
    """The mark on a rounded square with transparent margin (smooth edges: drawn 4x, then scaled down)."""
    mark = mark or icon(1024)
    body = round(size * 824 / 1024)
    margin = (size - body) // 2
    big = body * 4
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=round(big * 0.2237), fill=255)
    mask = mask.resize((body, body), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(mark.convert("RGB").resize((body, body), Image.LANCZOS), (margin, margin), mask)
    return out


for s in (192, 512):
    if (OUT / f"icon-{s}.png").exists() and (OUT / f"maskable-{s}.png").exists():
        continue  # the browser icons exist: keep them as they are
    icon(s).save(OUT / f"icon-{s}.png")
    icon(s, True).save(OUT / f"maskable-{s}.png")
if not (OUT / "icon-1024.png").exists():
    icon(180).save(OUT / "apple-touch-icon.png")
    icon(1024).save(OUT / "icon-1024.png")
def tray_icon(size, recording=False):
    """The macOS menu bar wants a template image: black on transparent – macOS paints it in the bar's own colour
    (light or dark, like every other icon there). The dot tells the state: a ring = ready, filled = recording."""
    big = size * 8
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(int(big * 0.9))
    d.text((big * 0.02, big * 0.56), "R", font=f, fill=(0, 0, 0, 255), anchor="lm")
    r = big * 0.17
    cx, cy = big - r - big * 0.02, r + big * 0.04
    if recording:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 255))
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0, 255), width=round(big * 0.075))
    return im.resize((size, size), Image.LANCZOS)


for name, rec in (("tray", False), ("tray-rec", True)):
    tray_icon(22, rec).save(OUT / f"{name}.png")
    tray_icon(44, rec).save(OUT / f"{name}@2x.png")

# the app (keeps the mark exactly as in icon-1024.png when that exists)
mark = Image.open(OUT / "icon-1024.png") if (OUT / "icon-1024.png").exists() else icon(1024)
app_icon(512, mark).save(OUT / "app-512.png")  # the window and the Dock while REKORD runs
app_icon(1024, mark).save(ROOT / "desktop" / "icon.png")  # macOS app (PyInstaller makes the .icns from it)
app_icon(256, mark).save(ROOT / "desktop" / "icon-256.png")  # Linux menus
app_icon(256, mark).save(ROOT / "desktop" / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icons ->", OUT)
