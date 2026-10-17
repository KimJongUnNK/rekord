# REKORD.

**Lokaler KI-Notizrekorder.** Er nimmt Meetings auf, erkennt **live, wer gerade spricht**, transkribiert, schreibt Protokoll, To-dos und Mind Map und beantwortet Fragen über alle deine Gespräche.
Das ist die Plaud-Note-Pro-Idee, nur ohne Cloud-Zwang, ohne Abo und ohne Minutenlimit. Bei der KI hast du die Wahl: **Claude**, **ChatGPT** oder **100 % lokal** (Ollama/LM Studio).

| Live: wer spricht gerade | Zusammenfassung | Mind Map | iPhone |
|---|---|---|---|
| ![](docs/04-live-running.png) | ![](docs/20-summary-dark.png) | ![](docs/21-mindmap.png) | ![](docs/13-mobile-detail.png) |

## Download

**[→ Neueste Version](https://github.com/KimJongUnNK/rekord/releases/latest)**: Windows (`.zip` → `REKORD.exe`), Mac mit Apple-Chip (`.zip` → `REKORD.app`), Linux (alle Distros, siehe unten), iPhone (`.ipa` zum Sideloaden).
Entpacken, starten, fertig. Beim ersten Start werden die Sprachmodelle geladen (~700 MB), danach läuft alles offline.
Die Apps sind nicht signiert, deshalb beim ersten Öffnen: Windows *Weitere Informationen → Trotzdem ausführen*, Mac *Rechtsklick → Öffnen*.

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

## Installation

### Linux
Jede Distro, x86_64. Gebaut auf Debian 11, läuft auf allem ab Debian 11 / Ubuntu 20.04 / Fedora / openSUSE / Arch. Jedes Release wird automatisch auf Debian, Ubuntu, Fedora, openSUSE Tumbleweed und Arch installiert und gestartet.

| Distro | Datei | Installieren |
|---|---|---|
| **Alle** | `REKORD-<ver>-x86_64.AppImage` | `chmod +x REKORD-*.AppImage && ./REKORD-*.AppImage` |
| Debian, Ubuntu, Mint, Pop!_OS, Zorin, elementary | `rekord_<ver>_amd64.deb` | `sudo apt install ./rekord_*_amd64.deb` |
| Fedora, RHEL/Alma/Rocky 9, openSUSE | `rekord-<ver>-1.x86_64.rpm` | `sudo dnf install ./rekord-*.rpm` · `sudo zypper in ./rekord-*.rpm` |
| Arch, Manjaro, EndeavourOS, CachyOS | `rekord-<ver>-1-x86_64.pkg.tar.zst` | `sudo pacman -U rekord-*.pkg.tar.zst` (oder `PKGBUILD` → `makepkg -si`) |
| Alles andere, ohne root | `REKORD-<ver>-Linux-x86_64.tar.gz` | `tar xzf REKORD-*.tar.gz && ./rekord-*/install.sh` |

Danach liegt REKORD im App-Menü. Im Terminal geht `rekord` (öffnet REKORD im Browser), `rekord mcp` (für Claude Code) oder `rekord serve --host 0.0.0.0`.
Unter Linux öffnet sich REKORD im Standard-Browser, und Chrome/Edge/Brave bieten dort „Installieren“ als eigenes App-Fenster an. Beenden geht über *Einstellungen → REKORD beenden*.
Fürs iPhone im WLAN muss Port 8765 in der Firewall offen sein, z. B. `sudo ufw allow 8765/tcp`.

Lieber aus dem Quellcode (für Entwickler):

### Windows
```powershell
winget install -e --id Python.Python.3.12
git clone https://github.com/KimJongUnNK/rekord; cd rekord
.\start.ps1                      # nur dieser PC
.\start.ps1 --host 0.0.0.0       # + iPhone im WLAN
```

### macOS
```bash
git clone https://github.com/KimJongUnNK/rekord && cd rekord
./start.sh --host 0.0.0.0        # oder start.command im Finder doppelklicken
```

Der erste Start richtet eine venv ein und lädt die Basismodelle (~700 MB mit Whisper small). Danach öffnet sich `http://localhost:8765`.
Im Browser über **Installieren** (Chrome/Edge) bzw. **Teilen → Zum Dock** (Safari) wird REKORD eine eigene App.

**Desktop-App mit eigenem Fenster:** `pip install -e ".[desktop]"` und dann `python -m rekord desktop --lan`.
Fertige `.app`/`.exe`: `pyinstaller desktop/rekord.spec`. Die CI baut beides automatisch (siehe `.github/workflows/ci.yml` → Artifacts).

### iPhone
**Variante A: Native App (empfohlen, mit Lockscreen)**
1. Mac mit Xcode: `brew install xcodegen && cd ios && xcodegen generate && open Rekord.xcodeproj`
2. Unter *Signing & Capabilities* dein Team wählen. Ist die Bundle-ID `app.rekord.ios` vergeben, Prefix und App Group (`group.app.rekord.shared`) in beiden Targets ändern.
3. Auf dein iPhone spielen, die App öffnen und **QR scannen** (Hub: *Einstellungen → iPhone & Geräte*). Alternativ wird der Hub per Bonjour im WLAN automatisch gefunden.
4. Sperrbildschirm bearbeiten → Widgets → REKORD. Im Kontrollzentrum gibt's „REKORD Aufnahme". Den Action Button belegst du über den Kurzbefehl „REKORD Aufnahme starten".

Mit einer kostenlosen Apple-ID läuft die App 7 Tage und wird dann neu signiert. Mit dem Developer-Programm (99 €/Jahr) gibt's TestFlight und den App Store.

**Variante B: PWA (ohne Mac, ohne Xcode)**
Hub mit `--host 0.0.0.0 --https` starten, den Web-QR scannen, dem Zertifikat einmal vertrauen und dann *Teilen → Zum Home-Bildschirm*. Damit hast du alles außer Live Activity und Widgets.
Tipp für echte Zertifikate ohne Warnung: [Tailscale](https://tailscale.com) + `tailscale serve 8765`.

---

## KI verbinden
*Einstellungen → KI*, oder in der iOS-App unter *Einstellungen*.

| Anbieter | Was du brauchst | Hinweis |
|---|---|---|
| **Claude** | API-Key von console.anthropic.com | Standard `claude-opus-5-5`, günstig `claude-haiku-5-5`. Denkaufwand und Ausweichmodell sind einstellbar. |
| **ChatGPT** | API-Key von platform.openai.com | Plus-Abo ≠ API-Guthaben. Modelle per „Laden" aus deinem Account. |
| **Lokal** | [Ollama](https://ollama.com), z. B. `ollama pull qwen3:8b` | Nichts verlässt dein Netzwerk. Lange Meetings werden automatisch abschnittsweise verdichtet. |
| **Kompatibel** | LM Studio, llama.cpp, Jan, vLLM, OpenRouter, Groq … | Jede OpenAI-kompatible URL |

### Claude Desktop / Claude Code (MCP, ohne API-Key)
Unter *Einstellungen → Claude Desktop (MCP)* steht der fertige Konfig-Block zum Kopieren. Claude bekommt die Werkzeuge `list_recordings`, `get_transcript`, `search_transcripts`, `list_people` und `save_summary`.
```bash
claude mcp add rekord -- python -m rekord mcp
```

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

## Bedienung (Kurzfassung)
- **Leertaste** startet und stoppt im Live-Modus, **H** markiert einen Moment (★). ★-Stellen gewichtet die KI stärker.
- **Eingangsordner** `~/Rekord/inbox`: Was hier landet (iCloud-/Dropbox-Sync vom Handy, Diktiergerät), wird automatisch verarbeitet.
- **Vokabular**: falsch erkannte Namen dauerhaft korrigieren („Beni" → „Beeni"), auch direkt aus *Suchen & Ersetzen*.
- **Pro Gerät einstellbar**: Mikrofon, Rausch-/Echo-Unterdrückung, Auto-Pegel, Quelle (Mikro / Mikro + Call-Ton), Hell/Dunkel/System, Akzentfarbe, Dichte.
- **CLI**: `python -m rekord process datei.m4a --summary meeting` · `python -m rekord models list|download` · `python -m rekord enroll "Lisa" probe.m4a`

## Daten
Alles liegt in `~/Rekord` (änderbar per `REKORD_HOME`): `rekord.db` (SQLite), `audio/`, `models/`, `inbox/`, `settings.json`. Für ein Backup kopierst du diesen Ordner.
Im WLAN ist jeder Zugriff außer von localhost durch einen **Kopplungs-Code** geschützt, und das Rotieren des Codes trennt alle Geräte.

## Entwicklung
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
