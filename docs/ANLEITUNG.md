# REKORD einrichten

**So funktioniert's:** REKORD läuft auf deinem **Computer** (Mac oder Windows). Dort wird aufgenommen, transkribiert und erkannt, wer spricht.
Das **iPhone ist optional**: Es verbindet sich übers WLAN mit dem Computer.

⏱ ca. 10 Minuten · einmalig ~700 MB Download · danach läuft alles offline

| | |
|---|---|
| **1** | [Mac](#1-mac) |
| **2** | [Windows](#2-windows) |
| **3** | [iPhone](#3-iphone-optional) *(optional)* |
| **4** | [KI verbinden](#4-ki-verbinden) *(für Zusammenfassungen)* |
| **5** | [Erste Aufnahme](#5-erste-aufnahme) |
| **6** | [Das Menü: jeder Punkt erklärt](#6-das-menü-jeder-punkt-erklärt) |
| ? | [Wenn was nicht klappt](#wenn-was-nicht-klappt) |

---

## 1. Mac

> **Brauchst du:** einen Mac mit Apple-Chip (M1 oder neuer).
> Prüfen: Apfel-Menü  → *Über diesen Mac* → bei „Chip“ steht *Apple M…*

**① Laden**
[**REKORD-macOS-AppleSilicon.zip**](https://github.com/KimJongUnNK/rekord/releases/latest/download/REKORD-macOS-AppleSilicon.zip)

**② Installieren**
Zip öffnen (Safari entpackt meist schon selbst) → **REKORD** in den Ordner **Programme** ziehen.

**③ Beim ersten Mal öffnen**
1. REKORD doppelklicken. macOS meldet *„Apple konnte nicht überprüfen …“* → **Fertig** klicken.
2. **Systemeinstellungen** → **Datenschutz & Sicherheit** → ganz nach unten scrollen.
3. Bei *„REKORD wurde blockiert“* auf **Dennoch öffnen** → Passwort oder Touch ID.

Das ist nur einmal nötig, danach startet REKORD ganz normal.

**④ Erlauben**
- *Mikrofon* → **Erlauben**
- *Geräte im lokalen Netzwerk finden* → **Erlauben** (damit das iPhone den Mac findet)

**⑤ Kurz warten**
Beim ersten Start lädt REKORD die Sprachmodelle. Den Fortschritt siehst du unten links. Steht dort **„Bereit · lokal“**, kann's losgehen.

---

## 2. Windows

> **Brauchst du:** Windows 10 oder 11 (64-Bit).

**① Laden**
[**REKORD-Windows-x64.zip**](https://github.com/KimJongUnNK/rekord/releases/latest/download/REKORD-Windows-x64.zip)

**② Entpacken**
Rechtsklick auf die Zip → **Alle extrahieren…** → z. B. nach `Dokumente\REKORD`.

**③ Beim ersten Mal öffnen**
Im entpackten Ordner **REKORD.exe** doppelklicken.
Blaues Fenster *„Der Computer wurde durch Windows geschützt“* → **Weitere Informationen** → **Trotzdem ausführen**.

**④ Erlauben**
- Firewall-Fenster: Haken bei **Private Netzwerke** → **Zugriff zulassen** (damit das iPhone den PC findet)
- Mikrofon-Abfrage → **Zulassen**

**⑤ Kurz warten**
Die Sprachmodelle werden geladen. Steht unten links **„Bereit · lokal“**, ist alles fertig.

**Tipp:** Rechtsklick auf REKORD.exe → **An „Start“ anheften**. Dann findest du REKORD im Startmenü.

---

## 3. iPhone (optional)

> **Voraussetzung:** REKORD ist am Computer offen und beide sind im **selben WLAN**.

**Welcher Weg?**

| | **A · Web-App** | **B · iPhone-App** |
|---|:---:|:---:|
| Einrichten | 1 Minute | ca. 15 Minuten |
| Aufnahmen ansehen, anhören, Fragen stellen | ✓ | ✓ |
| **Mit dem iPhone aufnehmen** + live sehen, wer spricht | – | ✓ |
| Sperrbildschirm-Widget, Dynamic Island | – | ✓ |
| Du brauchst | nichts | Kabel + Computer + Apple-ID |

### Weg A · Web-App

1. Am Computer in REKORD: **Einstellungen** → **iPhone & Geräte**.
2. iPhone-Kamera auf den **rechten** QR-Code („Im Browser“) halten → Link öffnen.
3. In Safari: **Teilen** → **Zum Home-Bildschirm** → **Hinzufügen**.

### Weg B · iPhone-App *(Beta)*

**Einmalig am Computer vorbereiten**
1. **Sideloadly** installieren: [sideloadly.io](https://sideloadly.io)
   *Windows:* zusätzlich **iTunes** und **iCloud** von apple.com installieren, nicht aus dem Microsoft Store.
2. [**REKORD-iOS-unsigned.ipa**](https://github.com/KimJongUnNK/rekord/releases/latest/download/REKORD-iOS-unsigned.ipa) laden.

**App aufs iPhone bringen**

3. iPhone per Kabel anschließen → am iPhone **„Diesem Computer vertrauen“**.
4. Sideloadly öffnen → die **.ipa** ins Fenster ziehen → deine **Apple-ID** eingeben → **Start**.

**Am iPhone freischalten**

5. **Einstellungen** → **Datenschutz & Sicherheit** → **Entwicklermodus** → an. Das iPhone startet neu, danach **Aktivieren** tippen.
6. **Einstellungen** → **Allgemein** → **VPN & Geräteverwaltung** → deine Apple-ID → **Vertrauen**.

**Verbinden**

7. REKORD am iPhone öffnen → **QR-Code scannen**. Am Computer: *Einstellungen → iPhone & Geräte*, **linker** Code.

**Extras**
- **Sperrbildschirm:** lange drücken → *Anpassen* → *Sperrbildschirm* → Widgets → **REKORD**
- **Kontrollzentrum:** öffnen → **+** oben links → *Steuerelement hinzufügen* → **REKORD**
- **Action Button:** *Einstellungen → Action Button → Kurzbefehl* → **REKORD Aufnahme starten**

> Mit einer **kostenlosen Apple-ID** läuft die App 7 Tage. Danach in Sideloadly einfach nochmal **Start** drücken. Deine Daten bleiben erhalten.

---

## 4. KI verbinden

Transkript und Sprecher-Erkennung gehen **ohne KI**. Für Protokoll, To-dos, Mind Map und Fragen brauchst du eine.
Alles läuft unter **Einstellungen → KI**.

| | So geht's | Kosten |
|---|---|---|
| **Claude** | [console.anthropic.com](https://console.anthropic.com) → *API Keys* → *Create Key* → Key bei **Claude** einfügen → **Testen** | pro Nutzung, meist Cent-Beträge pro Meeting |
| **ChatGPT** | [platform.openai.com](https://platform.openai.com/api-keys) → *Create new secret key* → Key bei **ChatGPT** einfügen → Modell **Laden** → auswählen → **Testen** | pro Nutzung. Das ChatGPT-Plus-Abo zählt **nicht**. |
| **Lokal** | [ollama.com](https://ollama.com) installieren → Terminal: `ollama pull qwen3:8b` → bei **Lokal** Modell **Laden** → auswählen | **gratis**, nichts verlässt den Computer. Braucht ~8 GB freien Arbeitsspeicher. |

**Mit deinem Claude-Abo statt API-Key (Claude Desktop):**
REKORD → *Einstellungen → Claude Desktop (MCP)* → **Kopieren** →
Claude Desktop → *Einstellungen → Entwickler → Konfiguration bearbeiten* → einfügen, speichern → Claude neu starten.
Danach kannst du Claude direkt fragen: *„Was haben wir im letzten Meeting entschieden?“*

---

## 5. Erste Aufnahme

1. **Leute einmal anlernen:** *Personen* → **Person einsprechen** → 15 Sekunden vorlesen. Ab dann erkennt REKORD die Person mit Namen.
2. **Vor dem Meeting:** *Live* → bei **„Wer ist dabei?“** die Leute antippen.
3. **Roter Knopf** startet die Aufnahme. Taucht eine unbekannte Stimme auf, tippst du sie an und gibst den Namen ein.
4. **Stopp:** Das fertige Protokoll kommt ein paar Minuten später, alles auf deinem Computer.

---

## 6. Das Menü: jeder Punkt erklärt

So sieht die Leiste aus: am Computer links, am Handy unten. Dort heißt *Einstellungen* kurz **Optionen**.

| Menü | Wofür |
|---|---|
| [**Aufnahmen**](#aufnahmen) | alle Gespräche, suchen, importieren, öffnen |
| [**Live**](#live) | aufnehmen und live sehen, wer spricht |
| [**Fragen**](#fragen) | Fragen über alle Aufnahmen auf einmal |
| [**Personen**](#personen) | die Stimmen, die REKORD kennt |
| [**Vorlagen**](#vorlagen) | Formate für Zusammenfassungen |
| [**Einstellungen**](#einstellungen) | Aussehen, Mikrofon, KI, iPhone … |

Der **rote Knopf** unten rechts (in Aufnahmen, Fragen, Personen und Vorlagen) springt direkt zur Aufnahme.

### Aufnahmen
- **Suchen:** findet Titel *und* alles, was gesagt wurde.
- **Importieren:** Audio- oder Videodateien wählen oder einfach ins Fenster ziehen (Sprachmemos, Zoom, Diktiergerät).
- **Ordner:** erscheinen oben als Filter, sobald eine Aufnahme einen Ordner hat (vergibst du unter *Notizen*).
- Eine Aufnahme anklicken öffnet sie:
  - **Titel** antippen zum Umbenennen.
  - **Player:** Wellenform und farbige Sprecher-Leiste anklicken zum Springen, **±15 s**, Tempo **1×–2×**. ★ markiert deine Highlights.
  - **Sprecher-Karten:** antippen → Namen ändern, **Stimme merken** (wird künftig erkannt) oder mit einem doppelt erkannten Sprecher **zusammenführen**.
  - Darunter die Reiter:

| Reiter | Was du dort machst |
|---|---|
| **Zusammenfassung** | Vorlage wählen → **Zusammenfassen**. Mehrere Vorlagen geben mehrere Blickwinkel. To-do-Häkchen sind klickbar, Zeitstempel springen ins Audio. Kopieren, bearbeiten, löschen. |
| **Transkript** | Text antippen zum Korrigieren · **Suchen & Ersetzen**, auch Sprechernamen, optional dauerhaft ins Vokabular · Zeit anklicken springt hin · *Mitscrollen* beim Abspielen |
| **Mind Map** | **Mind Map erstellen** · als **SVG** oder **PNG** speichern |
| **Fragen** | Chat nur über diese Aufnahme, z. B. *„Wer hat was zugesagt?“* |
| **Notizen** | eigene Notizen (fließen in Zusammenfassungen ein) · **Ordner** vergeben |
| **Export** | Markdown, Word, Text, Untertitel als SRT oder WebVTT, JSON, Zwischenablage, PDF (übers Drucken), Original-Audio |

  - **„…“ oben rechts:** *Neu verarbeiten* (z. B. nach Modellwechsel) · *Personen neu erkennen* (nach dem Anlernen neuer Leute) · *Umbenennen* · *Löschen*

### Live
- Oben: **Mikrofon** oder **Mikro + Call-Ton**. Mit Call-Ton nimmst du am Computer auch Zoom, Teams oder Meet mit auf (Chrome/Edge).
- **Titel** eingeben (optional).
- **Wer ist dabei?** Leute antippen. **+ Gäste** für Unbekannte. **Vorstellungsrunde** lässt neue Leute 10–15 s einsprechen.
- **Roter Knopf** (oder **Leertaste**) startet und stoppt · **★** (oder Taste **H**) markiert einen wichtigen Moment · **Pause**.
- Mitte: **wer gerade spricht**, groß und in der Farbe der Person.
- Rechts *Im Raum*: alle Stimmen mit Redeanteil. Eine **unbekannte Stimme antippen** → Namen eingeben → ab sofort erkannt.
- *Mitschrift*: das Transkript, live.

### Fragen
Ein Chat über **alle** Aufnahmen: *„Was hat Lisa letzte Woche zum Budget gesagt?“* Die Antworten haben anklickbare Quellen, die direkt an die Stelle in der Aufnahme springen. **Verlauf leeren** oben rechts.

### Personen
- **Person einsprechen:** Namen eingeben, 15 s vorlesen oder eine Datei mit nur dieser Person wählen.
- **Stift-Symbol:** Namen oder Farbe ändern, oder **Stimmabdruck löschen**.
- Jede Bestätigung („Stimme merken“) verbessert den Stimmabdruck.

### Vorlagen
31 fertige Formate in Kategorien (Business, Vertrieb, Events, Medien, HR, Bildung, Kreativ, Persönlich, Recht, Analyse).
- Vorlage anklicken → ansehen. **Speichern** legt eine eigene Kopie an, die du anpassen kannst.
- **Eigene Vorlage:** Namen, Kategorie, Kurzbeschreibung und den Text schreiben, was die KI liefern soll.

### Einstellungen
Oben gibt's Sprung-Knöpfe zu den Bereichen. *Darstellung* und *Audio & Mikrofon* gelten **nur für dieses Gerät**, alles andere für den ganzen Computer.

| Bereich | Felder (so heißen sie in der App) |
|---|---|
| **Darstellung** | **Erscheinungsbild** System / Hell / Dunkel · **Akzentfarbe** (9 fertige oder eigene) · **Dichte** Luftig / Kompakt |
| **Audio & Mikrofon** | **Mikrofon** wählen + *Pegel testen* · **Standard-Quelle** Mikrofon oder Mikro + Call-Ton · **Audio-Verarbeitung**: Rauschunterdrückung, Echo-Unterdrückung, automatische Lautstärke · **Live-Erkennung** an/aus (aus spart Akku) · **Bildschirm wach halten** |
| **KI** | Anbieter wählen: Claude, ChatGPT, Lokal, Kompatibel, Aus · **API-Key** · **Modell** (*Laden* holt die Liste) · Claude: **Denkaufwand**, **Ausweichmodell** · Lokal/Kompatibel: **Ollama-Adresse** bzw. **Server-Adresse**, **Kontextlänge** · **Verbindung** → *Testen* · **Sprache der Zusammenfassungen** · **Automatisch zusammenfassen** + Standard-Vorlage |
| **Transkription** | **Sprache** (fest eingestellt = genauer, *Automatisch* für gemischte Meetings) · **Engine** · **Modell** (*small* = Standard, *turbo* = beste Qualität) · **CPU-Threads** · **Vokabular** für Namen, die falsch erkannt werden |
| **Sprecher-Erkennung** | **Personen-Erkennung (Aufnahmen)** und **Personen-Erkennung (live)**: wie streng (höher = weniger Verwechslungen) · **Sprecher trennen**: erscheint eine Person doppelt, runterdrehen · **Anzahl Sprecher**: wenn bekannt, fest einstellen · **Stimmabdruck-Modell** |
| **Modelle** | Sprachmodelle *Laden* oder *Entfernen* |
| **iPhone & Geräte** | **QR-Codes** (links iPhone-App, rechts Browser) · **Adresse** · **Kopplungs-Code** *Neu erzeugen* (trennt alle gekoppelten Geräte) |
| **Claude Desktop (MCP)** | fertige Konfiguration zum **Kopieren** für Claude Desktop und den Befehl für Claude Code |
| **Speicher & Datenschutz** | **Datenordner** (dort liegt alles) · **Eingangsordner**: Dateien, die hier landen, werden automatisch verarbeitet · **Was verlässt das Gerät?** · **Version** · **Beenden** → *REKORD beenden* |

**In der iPhone-App** gibt's die Reiter *Live*, *Aufnahmen*, *Personen* und *Einstellungen* (Theme, Akzentfarbe, Mikrofon, KI, Hub). *Fragen über alle* und *Vorlagen* laufen über die Web-App oder den Computer.

---

## Wenn was nicht klappt

| Problem | Lösung |
|---|---|
| **Mac:** *„REKORD ist beschädigt“* | Terminal öffnen, `xattr -dr com.apple.quarantine /Applications/REKORD.app` eingeben, REKORD nochmal öffnen |
| **Kein Mikrofon im App-Fenster** | Im Browser **http://localhost:8765** öffnen, dort geht's immer. Mac: *Systemeinstellungen → Datenschutz & Sicherheit → Mikrofon* → REKORD an |
| **iPhone findet den Computer nicht** | Gleiches WLAN? (Gäste-WLANs trennen Geräte.) Ist REKORD am Computer offen? Windows: Firewall „Private Netzwerke“ erlaubt? |
| **„Modelle werden geladen“ geht nicht weiter** | Internet prüfen → *Einstellungen → Modelle* → **Laden** |
| **Zusammenfassung zeigt Fehler** | *Einstellungen → KI* → **Testen**. Key richtig kopiert? Guthaben auf dem API-Konto? |
| **Falsche Person erkannt** | Im Transkript auf den Namen tippen → richtigen Namen eingeben, *Stimme merken* bleibt an |
| **REKORD beenden** | Fenster schließen. Läuft es im Browser: *Einstellungen* → ganz unten **REKORD beenden** |
| **Backup** | Den Ordner **Rekord** in deinem Benutzerordner kopieren. Da liegt alles drin. |

---

## Linux

Für jede Distro gibt's ein passendes Paket. Alle Dateien liegen auf der [Release-Seite](https://github.com/KimJongUnNK/rekord/releases/latest):

| Distro | Befehl |
|---|---|
| **Jede** (AppImage) | `chmod +x REKORD-*.AppImage && ./REKORD-*.AppImage` |
| Debian, Ubuntu, Mint, Pop!_OS | `sudo apt install ./rekord_*_amd64.deb` |
| Fedora, RHEL/Alma/Rocky 9 | `sudo dnf install ./rekord-*.x86_64.rpm` |
| openSUSE | `sudo zypper in ./rekord-*.x86_64.rpm` |
| Arch, Manjaro, EndeavourOS | `sudo pacman -U rekord-*.pkg.tar.zst` |
| Ohne root | `tar xzf REKORD-*-Linux-x86_64.tar.gz && ./rekord-*/install.sh` |

REKORD öffnet sich unter Linux im Browser. Fürs iPhone den Port freigeben: `sudo ufw allow 8765/tcp`.
