# REKORD.

**Lokaler KI-Notizrekorder.** Er nimmt Meetings auf, erkennt **live, wer gerade spricht**, transkribiert, schreibt Protokoll, To-dos und Mind Map und beantwortet Fragen über alle deine Gespräche.
Das ist die Plaud-Note-Pro-Idee, nur ohne Cloud-Zwang, ohne Abo und ohne Minutenlimit. Bei der KI hast du die Wahl: **Claude**, **ChatGPT** oder **100 % lokal** (Ollama/LM Studio).

| Live: wer spricht gerade | Zusammenfassung | Mind Map | iPhone |
|---|---|---|---|
| ![](docs/04-live-running.png) | ![](docs/20-summary-dark.png) | ![](docs/21-mindmap.png) | ![](docs/13-mobile-detail.png) |

## Loslegen

**Mac & Linux** (Terminal):
```
curl -fsSL https://github.com/KimJongUnNK/rekord/releases/latest/download/install.sh | sh
```
**Windows** (PowerShell):
```
irm https://github.com/KimJongUnNK/rekord/releases/latest/download/install.ps1 | iex
```
Oder klassisch: **[Download](https://github.com/KimJongUnNK/rekord/releases/latest)** · **[Schritt-für-Schritt-Anleitung](docs/ANLEITUNG.md)** (Installation, iPhone, KI, jeder Menüpunkt erklärt)

In ~5 Minuten startklar: Sprachmodelle, lokale KI, Claude-Desktop-Anbindung und iPhone-Zertifikat richtet REKORD per Klick selbst ein. Danach läuft alles offline.

---

## Was es kann

| | Plaud Note Pro | **REKORD** |
|---|---|---|
| Aufnahme | eigene Hardware | iPhone, Mac, Windows, jedes Mikro (USB, Headset, AirPods, Konferenz-Speaker) |
| Transkription | Cloud | **lokal** (Whisper bis large-v3 / turbo, ~99 Sprachen, Sprache pro Satz) |
| Sprecher | „Speaker 1/2" + manuell benennen | **Erkennt Personen an der Stimme**, live und über alle Meetings hinweg |
| Live im Meeting | – | **Großanzeige „wer spricht"**, Redeanteile, Live-Mitschrift |
| Teilnehmer vorab wählen | – | **„Wer ist dabei?"** + Gäste-Anzahl → geschlossene Runde, kaum Verwechslungen |
| Stimmen anlernen | – | **Vorstellungsrunde**: jede Person spricht 10–15 s ein |
| Zusammenfassungen | Templates, Cloud-KI | 31 Vorlagen + eigene, mehrere Blickwinkel pro Gespräch, **deine KI** |
| „Ask Plaud" | ja | **Fragen** pro Aufnahme und über alle Aufnahmen, mit klickbaren Quellen [mm:ss] |
| Mind Map | ja | ja (SVG/PNG-Export) |
| Highlight-Knopf | Hardware-Taste | ★-Button, Taste `H`, Live Activity, Siri, Action Button |
| Call-Aufnahme | Vibrationssensor | Mikro + Systemton (Zoom/Teams/Meet-Tab) am Computer |
| Export | PDF, Word, TXT … | Markdown, Word, TXT, SRT, VTT, JSON, PDF, Audio |
| Claude-Anbindung | – | **MCP-Server**: Claude Desktop/Claude Code liest deine Bibliothek, läuft mit normalem Claude-Abo |
| Lockscreen | – | **Live Activity + Dynamic Island** (aktueller Sprecher), Sperrbildschirm-Widgets, Kontrollzentrum-Button |
| Datenschutz | Cloud | Audio und Stimmabdrücke verlassen nie dein Gerät. Keine Telemetrie, kein Konto. |
| Kosten | Gerät + Abo | 0 € (lokal) bzw. nur API-Kosten deiner KI |

---

## Architektur

```
 iPhone (native App / PWA)          Mac / Windows / Linux  – „Hub"
 ┌──────────────────────┐   WLAN   ┌───────────────────────────────────────────────┐
 │ Mikro → 16 kHz PCM   │ ───────► │ Live:  VAD → Stimmabdruck → Person? → Whisper │
 │ Live Activity        │ ◄─────── │        („Lisa spricht", Mitschrift)            │
 │ Widgets · Siri       │  Events  │ Danach: pyannote-Segmentierung → Feintrennung │
 └──────────────────────┘          │        → Personen-Abgleich → Whisper → KI     │
 Browser (PWA) ───────────────────►│ SQLite + FTS5 · Audio · Modelle · ~/Rekord    │
 Claude Desktop ── MCP ───────────►│                                               │
                                   └──────────────┬────────────────────────────────┘
                                                  │ nur Text
                                    Claude API · OpenAI API · Ollama · LM Studio
```

Die gesamte Sprachverarbeitung läuft über **sherpa-onnx** (ONNX Runtime, CPU, kein PyTorch, keine GPU nötig) und damit identisch auf Windows, macOS (Intel + Apple Silicon) und Linux.
Modelle (alle offen, von GitHub): Whisper int8 (tiny → large-v3/turbo), pyannote segmentation 3.0, ERes2Net-Voiceprint, Silero VAD.
Optional: `faster-whisper` für NVIDIA-GPUs.

---

## Personen erkennen: so wird's präzise
1. **Einmal anlernen.** Dafür gibt's drei Wege:
   - *Personen → Person einsprechen*: 15 s vorlesen.
   - *Live → Vorstellungsrunde*: Handy reihum, jede Person stellt sich kurz vor.
   - Im Meeting die **unbekannte Stimme antippen** und den Namen eingeben. Ab diesem Satz wird die Person erkannt.
   - Oder nach dem Meeting im Transkript den Sprecher umbenennen und „Stimme merken" anhaken.
2. **Vor dem Meeting „Wer ist dabei?" wählen.** REKORD vergleicht dann nur mit diesen Leuten. Mit 0 Gästen ist es eine *geschlossene Runde*, und jede Stimme geht an die ähnlichste anwesende Person.
3. Jeder Stimmabdruck wird mit jedem Meeting besser, weil er als laufender Mittelwert über alle bestätigten Aufnahmen gebildet wird.
4. Feintuning unter *Einstellungen → Sprecher-Erkennung*: Schwellen, feste Sprecherzahl, Modell.

Nach der Aufnahme läuft ein zweiter, gründlicher Durchgang: Segmentierung, Feintrennung schneller Sprecherwechsel, Abgleich und Transkription mit dem großen Modell. Live ist schnell, das Ergebnis danach ist genau.

---

## Bedienung
Jeder Menüpunkt, jeder Reiter und jede Einstellung ist in der **[Anleitung, Abschnitt 6](docs/ANLEITUNG.md#6-das-menü-jeder-punkt-erklärt)** erklärt.
Kurz: **Leertaste** startet/stoppt im Live-Modus, **H** markiert einen Moment (★). ★-Stellen gewichtet die KI stärker.

## Daten
Alles liegt in `~/Rekord` (änderbar per `REKORD_HOME`): `rekord.db` (SQLite), `audio/`, `models/`, `inbox/`, `settings.json`. Für ein Backup kopierst du diesen Ordner.
Im WLAN ist jeder Zugriff außer von localhost durch einen **Kopplungs-Code** geschützt, und das Rotieren des Codes trennt alle Geräte.

## Entwicklung

**Aus dem Quellcode starten** (Python 3.10+):
```bash
git clone https://github.com/KimJongUnNK/rekord && cd rekord
./start.sh --host 0.0.0.0        # macOS/Linux · Windows: .\start.ps1 --host 0.0.0.0
```

**CLI:** `rekord serve` · `rekord process datei.m4a --summary meeting` · `rekord models list|download` · `rekord enroll "Lisa" probe.m4a` · `rekord mcp`

**iOS-App selbst bauen** (Mac + Xcode): `brew install xcodegen && cd ios && xcodegen generate && open Rekord.xcodeproj`. Dann bei *Signing & Capabilities* dein Team wählen.
Ist die Bundle-ID `app.rekord.ios` vergeben, Prefix und App Group (`group.app.rekord.shared`) in beiden Targets ändern.

**Desktop-Pakete:** `pyinstaller desktop/rekord.spec`. Linux-Pakete: `packaging/linux/build.sh`. Ein Push auf den Branch `release` baut alles und veröffentlicht das Release.

**Tests:**
```bash
pip install -e ".[all,dev]"
pytest -m "not models"                                   # Unit- + API-Tests, Sekunden
python scripts/make_test_audio.py && pytest -m models    # End-to-End mit echten Modellen
```
Die Unit-Tests prüfen unter anderem die exakte Claude-API-Anfrage (gegen einen lokalen Nachbau der Anthropic-API) und den MCP-Server per echtem Protokoll-Handshake.
Die End-to-End-Tests erzeugen Meetings mit mehreren Sprechern über offene TTS-Stimmen. Sie prüfen die Diarization, die Wiedererkennung von Personen über zwei Meetings, die Live-Erkennung in Echtzeit und die geschlossene Runde.

## Grenzen (ehrlich)
- Überlappendes Sprechen (zwei gleichzeitig) wird dem dominanteren Sprecher zugeordnet.
- Sehr ähnliche Stimmen ohne Anlernen können verwechselt werden. Abhilfe: anlernen und Teilnehmer wählen.
- Das Live-Transkript nutzt das gewählte Modell auf kurzen Schnipseln. Das genaue Transkript entsteht im zweiten Durchgang.
- Die iOS-App braucht zum Bauen einen Mac mit Xcode. Live Activities laufen ab iOS 18.
- Linux-Pakete gibt's für x86_64. ARM-Boards (Raspberry Pi) und musl-Distros (Alpine) laufen aus dem Quellcode.

MIT-Lizenz · © 2026 Emil Boenke
