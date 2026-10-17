"""The user guide must cover every UI element and its links must resolve (GitHub anchor rules)."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _slug(heading: str) -> str:  # GitHub: lowercase, drop punctuation (keep - and _), spaces → -
    return re.sub(r"\s", "-", re.sub(r"[^\w\- ]", "", heading.strip().lower()))


def test_guide_covers_every_menu_item_tab_and_setting():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/check_guide.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_doc_anchors_resolve():
    for doc in ("docs/ANLEITUNG.md", "README.md"):
        text = (ROOT / doc).read_text("utf-8")
        own = {_slug(h) for h in re.findall(r"^#{1,4} (.+)$", text, re.M)}
        for link, anchor in re.findall(r"\]\(([^)#\s]*)#([^)\s]+)\)", text):
            if link.startswith("http"):
                continue
            target = own if not link else {_slug(h) for h in re.findall(r"^#{1,4} (.+)$", (ROOT / Path(doc).parent / link).read_text("utf-8"), re.M)}
            assert anchor in target, f"{doc}: #{anchor} → {link or 'self'}"
