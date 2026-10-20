"""Checks that docs/ANLEITUNG.md covers every menu item, tab, button and settings field – of the REKORD window
(rekord/app/qml) and of the previous interface (rekord/web, still used where the window can't start).

Labels are pulled from the UI source, so new UI elements show up here until the guide mentions them.
Run: python scripts/check_guide.py   (exit code 1 = gaps)
"""
import html
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles (cp1252) can't print ✔/✘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
app = (ROOT / "rekord/web/app.js").read_text("utf-8")
app = re.sub(r'\$\{tip\("?[\w.]+"?\)\}', "", app)  # the ⓘ next to a label is not part of its name
index = (ROOT / "rekord/web/index.html").read_text("utf-8")
guide = (ROOT / "docs/ANLEITUNG.md").read_text("utf-8")


def norm(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"[\s„“\"'…*·]+", " ", s).strip().lower()


G = norm(guide)
groups: dict[str, set[str]] = {}

groups["Menü (links)"] = set(re.findall(r'data-nav="\w+"[^>]*><svg.*?</svg><span[^>]*>([^<]+)</span>', index))
groups["Einstellungen: Bereiche"] = set(re.findall(r'\["\w+", "([^"]+)"\]', app.split("const sections = [")[1].split("];")[0]))
groups["Aufnahme: Reiter"] = set(re.findall(r'<button data-tab="\w+"[^>]*>([^<]+)</button>', app))
groups["Aufnahme: … Menü"] = {m.split(" (")[0] for m in re.findall(r'<button class="btn(?: danger)?" value="(?:reprocess|reid|title|delete)">([^<]+)</button>', app)}
groups["Einstellungen: Felder"] = {re.split(r"<span class=\"hint\">", m)[0] for m in re.findall(r'class="field"><(?:div class="lbl"|label[^>]*)>(.*?)</(?:div|label)>', app)}
groups["Einstellungen: Auswahl"] = set(re.findall(r'\["(?:system|light|dark|comfortable|compact|mic|mic\+system|lecture)", "([^"]+)"[,\]]', app))
groups["KI-Anbieter"] = set(re.findall(r'\["(?:anthropic|openai|ollama|compatible|none)", "([^"]+)", "', app))
groups["Live"] = {"Wer ist dabei?", "Gäste", "Vorstellungsrunde", "Im Raum", "Mitschrift", "Pause"} \
    | set(re.findall(r'<button data-m="[^"]+"[^>]*>([^<]+)</button>', app))
groups["Export"] = set(re.findall(r'\["(?:md|docx|txt|srt|vtt|json)", "([^"]+)"', app)) | {"Zwischenablage", "PDF", "Audio"}
groups["Knöpfe"] = set(re.findall(r'id="(?:enroll|new|clr|gen|frep|mmgen|mcp-copy|quit|ltest|mic-test|oll-setup|cd-connect|cc-connect'
                                  r'|cd-restart|fw-open|key-get)"[^>]*>([^<]+)<', app))
groups["Knöpfe"] |= {"Importieren", "Suchen & Ersetzen", "Stimme merken", "zusammenführen", "Mind Map erstellen", "Laden", "Testen"}
pc = app[app.index("const provCfg = () => {"):app.index('$$("#prov .prov")')]
groups["KI: Felder je Anbieter"] = set(re.findall(r'<label for="\w+">([^<]+)<span', pc)) | set(re.findall(r'keyField\("([^"]+)"', pc)) \
    | set(re.findall(r'class="lbl">([^<]+)<', pc))

groups["Erster Start"] = set(re.findall(r'data-ob="\w+"><b>([^<]+)</b>', app)) | set(re.findall(r'data-ob="none"[^>]*>([^<]+)<', app))
welcome_js = (ROOT / "rekord/web/welcome.js").read_text("utf-8")
groups["Einführung (erster Start)"] = set(re.findall(r'Schritt \$\{i \+ 1\} · ([^<]+)</div>', welcome_js)) | {"Erste Aufnahme", "Zur App", "Überspringen"}
groups["Wer ist dabei? / Wer ist das?"] = {"Wie viele sprechen?", "Wer davon ist bekannt?", "Aufnahme starten", "Wer ist das?", "Merken",
                                          "Wer sagt das?", "Zuordnen", "Nicht erkannte Stimme", "Anderer Text", "Stimme speichern"} \
    | set(re.findall(r'data-v="[^"]+">([^<]+)</button>', re.search(r'id="w-meet".*?</div>', app, re.S)[0])) \
    | {"Wo findet das Meeting statt?"}
groups["Einsprechen"] = set(re.findall(r'<button type="button" data-m="\w+">([^<]+)</button>', app.split("async function enrollDialog")[1])) \
    | {"Anderer Text", "Gesprächsidee", "Stimme lernen", "Stimme speichern"}
groups["Koppeln"] = {"Kopplungs-Code", "Neuer Code", "Gekoppelte Geräte", "Trennen", "Alle Geräte trennen", "QR-Code scannen"}
groups["Speicherort"] = {"Speicherort", "KI-Modelle", "Laufwerk fehlt", "Nochmal prüfen", "Neu auf diesem Computer anfangen", "Umziehen"}

# ---- the REKORD window (Qt Quick)
QML = ROOT / "rekord/app/qml"
settings_qml = (QML / "SettingsPage.qml").read_text("utf-8")
wizard_qml = (QML / "WelcomeWizard.qml").read_text("utf-8")
groups["Fenster: Einstellungen – Bereiche"] = set(re.findall(r'\["\w+", "([^"]+)"\]', settings_qml.split("readonly property var sections:")[1].split("readonly property var langs")[0]))
groups["Fenster: Einstellungen – Felder"] = set(re.findall(r'^\s*label: "([^"]+)"', settings_qml, re.M)) \
    | set(re.findall(r'\["\w+", "([^"]+)", "\w+", "[^"]+", [\d.]+, [\d.]+\]', settings_qml))  # the sliders
groups["Fenster: Einstellungen – Knöpfe"] = {"Pegel testen", "Testen", "Neuer Code", "Alle Geräte trennen", "Einführung starten", "REKORD beenden",
                                             "Lokal einrichten", "Verwenden", "Alle nicht verwendeten löschen", "Laden & verwenden", "Umziehen"}
groups["Fenster: Einführung"] = set(re.findall(r'"Schritt " \+ \(w\.i \+ 1\) \+ " · ([^"]+)"', wizard_qml)) | {"Erste Aufnahme", "Zur App", "Überspringen"}
groups["Fenster: Laufwerk fehlt"] = set(re.findall(r'text: "([^"]+)"; (?:enabled|iconName)', (QML / "MissingPage.qml").read_text("utf-8"))) \
    | set(re.findall(r'iconName: "\w+"; text: "([^"]+)"', (QML / "MissingPage.qml").read_text("utf-8")))

missing = 0
for name, labels in groups.items():
    labels = {l for l in (norm(x) for x in labels) if l and "${" not in l}  # skip dynamic template strings
    gaps = sorted(l for l in labels if l not in G)
    print(f"{'✔' if not gaps else '✘'} {name}: {len(labels) - len(gaps)}/{len(labels)}" + (f"  fehlt: {gaps}" if gaps else ""))
    missing += len(gaps)
sys.exit(1 if missing else 0)
