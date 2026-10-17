"""Checks that docs/ANLEITUNG.md covers every menu item, tab, button and settings field of the web app.

Labels are pulled from the UI source, so new UI elements show up here until the guide mentions them.
Run: python scripts/check_guide.py   (exit code 1 = gaps)
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
app = (ROOT / "rekord/web/app.js").read_text("utf-8")
index = (ROOT / "rekord/web/index.html").read_text("utf-8")
guide = (ROOT / "docs/ANLEITUNG.md").read_text("utf-8")


def norm(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"[\s„“\"'…*·]+", " ", s).strip().lower()


G = norm(guide)
groups: dict[str, set[str]] = {}

groups["Menü (links)"] = set(re.findall(r'data-nav="\w+"><svg.*?</svg><span[^>]*>([^<]+)</span>', index))
groups["Einstellungen: Bereiche"] = set(re.findall(r'\["\w+", "([^"]+)"\]', app.split("const sections = [")[1].split("];")[0]))
groups["Aufnahme: Reiter"] = set(re.findall(r'<button data-tab="\w+">([^<]+)</button>', app))
groups["Aufnahme: … Menü"] = {m.split(" (")[0] for m in re.findall(r'<button class="btn(?: danger)?" value="(?:reprocess|reid|title|delete)">([^<]+)</button>', app)}
groups["Einstellungen: Felder"] = {re.split(r"<span class=\"hint\">", m)[0] for m in re.findall(r'class="field"><(?:div class="lbl"|label[^>]*)>(.*?)</(?:div|label)>', app)}
groups["Einstellungen: Auswahl"] = set(re.findall(r'\["(?:system|light|dark|comfortable|compact|mic|mic\+system)", "([^"]+)"\]', app))
groups["KI-Anbieter"] = set(re.findall(r'\["(?:anthropic|openai|ollama|compatible|none)", "([^"]+)", "', app))
groups["Live"] = {"Wer ist dabei?", "Gäste", "Vorstellungsrunde", "Im Raum", "Mitschrift", "Pause"}
groups["Export"] = set(re.findall(r'\["(?:md|docx|txt|srt|vtt|json)", "([^"]+)"', app)) | {"Zwischenablage", "PDF", "Audio"}
groups["Knöpfe"] = set(re.findall(r'id="(?:enroll|new|clr|gen|frep|mmgen|mcp-copy|quit|ltest|mic-test)"[^>]*>([^<]+)<', app))
groups["Knöpfe"] |= {"Importieren", "Suchen & Ersetzen", "Stimme merken", "zusammenführen", "Mind Map erstellen", "Laden", "Testen"}
pc = app[app.index("const provCfg = () => {"):app.index('$$("#prov .prov")')]
groups["KI: Felder je Anbieter"] = set(re.findall(r'<label for="\w+">([^<]+)<span', pc)) | set(re.findall(r'keyField\("([^"]+)"', pc)) \
    | set(re.findall(r'class="lbl">([^<]+)<', pc))

missing = 0
for name, labels in groups.items():
    labels = {l for l in (norm(x) for x in labels) if l and "${" not in l}  # skip dynamic template strings
    gaps = sorted(l for l in labels if l not in G)
    print(f"{'✔' if not gaps else '✘'} {name}: {len(labels) - len(gaps)}/{len(labels)}" + (f"  fehlt: {gaps}" if gaps else ""))
    missing += len(gaps)
sys.exit(1 if missing else 0)
