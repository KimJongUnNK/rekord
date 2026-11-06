"""The app icon: a rounded square with transparent margin (Dock, taskbar, window, Linux menus) – a full square looked
cut off in the macOS Dock. The browser icons stay full squares (the browser rounds them itself)."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def _rounded(path: Path, size: int) -> None:
    im = Image.open(path).convert("RGBA")
    assert im.size == (size, size)
    w = im.size[0]
    assert im.getpixel((2, 2))[3] == 0 and im.getpixel((w - 3, w - 3))[3] == 0  # transparent corners
    margin = round(w * 100 / 1024)
    assert im.getpixel((margin + 2, margin + 2))[3] == 0  # the body's corner is rounded, not square
    assert im.getpixel((w // 2, margin + 4))[3] == 255 and im.getpixel((w // 2, w // 2))[3] == 255  # the body itself


def test_app_icons_are_rounded():
    _rounded(ROOT / "rekord" / "web" / "icons" / "app-512.png", 512)
    _rounded(ROOT / "desktop" / "icon.png", 1024)
    _rounded(ROOT / "desktop" / "icon-256.png", 256)
    ico = Image.open(ROOT / "desktop" / "icon.ico")
    assert {(16, 16), (32, 32), (256, 256)} <= set(ico.info["sizes"])


def test_window_uses_the_rounded_icon():
    from rekord.app import _icon_path
    assert _icon_path().name == "app-512.png"
    build = (ROOT / "packaging" / "linux" / "build.sh").read_text()
    assert "desktop/icon-256.png" in build and "icons/app-512.png" in build


def test_browser_icons_stay_full_squares():
    im = Image.open(ROOT / "rekord" / "web" / "icons" / "icon-512.png").convert("RGBA")
    assert im.getpixel((2, 2))[3] == 255


def test_menu_bar_icon_is_a_template_on_the_mac(monkeypatch):
    """macOS menu bar: black on transparent, drawn by macOS in the bar's colour – not the coloured app icon."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication(["rekord-test"])
    from rekord.app import tray
    for name in ("tray", "tray@2x", "tray-rec", "tray-rec@2x"):
        im = Image.open(tray.ICONS / f"{name}.png").convert("RGBA")
        colours = {px[:3] for px in im.getdata() if px[3] > 0}
        assert colours <= {(0, 0, 0)} and im.getpixel((0, im.size[1] - 1))[3] == 0  # only black, transparent around
    monkeypatch.setattr(tray.sys, "platform", "darwin")
    icon = tray.menu_bar_icon()
    assert icon is not None and icon.isMask() and not icon.isNull()
    assert tray.menu_bar_icon(recording=True).isMask()
    monkeypatch.setattr(tray.sys, "platform", "win32")
    assert tray.menu_bar_icon() is None  # Windows/Linux keep the coloured icon
