"""Checks that docs/ANLEITUNG.md covers every menu item, tab, button and settings field of the REKORD window
(rekord/app/qml – there is no web interface any more).

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
guide = (ROOT / "docs/ANLEITUNG.md").read_text("utf-8")
QML = ROOT / "rekord/app/qml"


def qml(name: str) -> str:
    return (QML / name).read_text("utf-8")


def norm(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"[\s„“\"'…*·]+", " ", s).strip().lower()


G = norm(guide)
groups: dict[str, set[str]] = {}

detail = qml("DetailPage.qml")
groups["Menü (links)"] = set(re.findall(r'label: "([^"]+)", icon:', qml("Sidebar.qml")))
groups["Aufnahme: Reiter"] = set(re.findall(r'"([^"]+)"', detail.split("readonly property var tabs:")[1].split("]")[0]))
groups["Aufnahme: … Menü"] = {m.split(" (")[0].rstrip(" …") for m in re.findall(r'MenuItem \{ text: "([^"]+)"', detail)}
groups["KI-Anbieter"] = set(re.findall(r'\["(?:anthropic|openai|ollama|compatible|none)", "([^"]+)", "', qml("SettingsPage.qml")))
groups["Live"] = {"Wer ist dabei?", "Vorstellungsrunde", "Im Raum", "Mitschrift", "Pause"}
groups["Export"] = set(re.findall(r'k: "\w+", n: "([^"]+)"', qml("ExportView.qml"))) - {"In Zwischenablage"} | {"Zwischenablage"}
groups["Knöpfe"] = {"Datei transkribieren", "Suchen & Ersetzen", "Stimme merken", "zusammenführen", "Mind Map erstellen", "Laden",
                    "Testen", "Auswählen", "Anhängen", "Unterlagen", "Transkription stoppen", "Jetzt benennen"}
groups["Wer ist dabei? / Wer ist das?"] = {"Wie viele sprechen?", "Wer davon ist bekannt?", "Aufnahme starten", "Wer ist das?", "Merken",
                                          "Wer sagt das?", "Zuordnen", "Nicht erkannte Stimme", "Anderer Text", "Stimme speichern",
                                          "Wo findet das Meeting statt?", "Geräusch"}
groups["Einsprechen"] = {"Anderer Text", "Gesprächsidee", "Stimme lernen", "Stimme speichern"}
groups["Speicherort"] = {"Speicherort", "KI-Modelle", "Laufwerk fehlt", "Nochmal prüfen", "Neu auf diesem Computer anfangen", "Umziehen"}

# ---- the REKORD window (Qt Quick)
QML = ROOT / "rekord/app/qml"
settings_qml = (QML / "SettingsPage.qml").read_text("utf-8")
wizard_qml = (QML / "WelcomeWizard.qml").read_text("utf-8")
groups["Fenster: Einstellungen – Bereiche"] = set(re.findall(r'\["\w+", "([^"]+)"\]', settings_qml.split("readonly property var sections:")[1].split("readonly property var langs")[0]))
groups["Fenster: Einstellungen – Felder"] = set(re.findall(r'^\s*label: "([^"]+)"', settings_qml, re.M)) \
    | set(re.findall(r'\["\w+", "([^"]+)", "\w+", "[^"]+", [\d.]+, [\d.]+\]', settings_qml))  # the sliders
groups["Fenster: Einstellungen – Knöpfe"] = {"Pegel testen", "Testen", "Einführung starten", "REKORD beenden",
                                             "Lokal einrichten", "Verwenden", "Alle nicht verwendeten löschen", "Laden & verwenden", "Umziehen"}
groups["Fenster: Einführung"] = set(re.findall(r'"Schritt " \+ \(w\.i \+ 1\) \+ " · ([^"]+)"', wizard_qml)) | {"Erste Aufnahme", "Zur App", "Überspringen"}
groups["Fenster: Fragen & Vorlagen"] = {"Verlauf leeren", "Eigene Vorlage", "Reihenfolge zurücksetzen", "Löschen"}
groups["Fenster: Menüleiste"] = set(re.findall(r'addAction\("([^"]+)"', (ROOT / "rekord/app/tray.py").read_text("utf-8"))) \
    | {"Aufnahme stoppen & speichern"}
groups["Fenster: Laufwerk fehlt"] = set(re.findall(r'text: "([^"]+)"; (?:enabled|iconName)', (QML / "MissingPage.qml").read_text("utf-8"))) \
    | set(re.findall(r'iconName: "\w+"; text: "([^"]+)"', (QML / "MissingPage.qml").read_text("utf-8")))

missing = 0
for name, labels in groups.items():
    labels = {l for l in (norm(x) for x in labels) if l and "${" not in l}  # skip dynamic template strings
    gaps = sorted(l for l in labels if l not in G)
    print(f"{'✔' if not gaps else '✘'} {name}: {len(labels) - len(gaps)}/{len(labels)}" + (f"  fehlt: {gaps}" if gaps else ""))
    missing += len(gaps)
sys.exit(1 if missing else 0)
