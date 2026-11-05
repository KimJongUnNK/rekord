# REKORD einrichten

**So funktioniert's:** REKORD läuft auf deinem **Computer** (Mac oder Windows). Dort wird aufgenommen, transkribiert und erkannt, wer spricht.
Das **iPhone ist optional**: Es verbindet sich übers WLAN mit dem Computer.

⏱ ca. 5 Minuten · einmalig ~700 MB Download · danach läuft alles offline

> **Beim ersten Start führt dich REKORD durch alles:** Speicherort → Aussehen → Sprache → Mikrofon → KI → deine Stimme → iPhone. Siehe [Erster Start](#erster-start-die-einführung).
> Überall, wo ein kleines **ⓘ** steht: Maus drüber (am Handy antippen) – dort steht, was der Punkt macht.
>
> **Was REKORD selbst erledigt:** Sprachmodelle laden · lokale KI (Ollama) installieren und das passende Modell wählen ·
> vorhandene KI erkennen (Ollama, LM Studio) · Modell für ChatGPT wählen · Claude Desktop/Claude Code verbinden ·
> Startmenü-Eintrag (Windows) · Firewall freigeben (Linux).
> **Was nur du machen kannst:** einen API-Key kopieren (nur für Claude/ChatGPT) und Apple/Windows einmal sagen, dass du REKORD öffnen willst.

| | |
|---|---|
| **1** | [Mac](#1-mac) |
| **2** | [Windows](#2-windows) |
| **3** | [iPhone](#3-iphone-optional) *(optional)* |
| **→** | [Erster Start: die Einführung](#erster-start-die-einführung) |
| **4** | [KI verbinden](#4-ki-verbinden) *(für Zusammenfassungen)* |
| **5** | [Erste Aufnahme](#5-erste-aufnahme) |
| **6** | [Das Menü: jeder Punkt erklärt](#6-das-menü-jeder-punkt-erklärt) |
| ↻ | [Updates](#updates) |
| ? | [Wenn was nicht klappt](#wenn-was-nicht-klappt) |

---

## 1. Mac

> **Brauchst du:** einen Mac mit Apple-Chip (M1 oder neuer).
> Prüfen: Apfel-Menü  → *Über diesen Mac* → bei „Chip“ steht *Apple M…*

**① Installieren – am schnellsten mit einer Zeile**
**Terminal** öffnen (⌘ + Leertaste → „Terminal“), diese Zeile einfügen, **Enter**:

```
curl -fsSL https://github.com/KimJongUnNK/rekord/releases/latest/download/install.sh | sh
```

REKORD landet in **Programme** und startet sofort. Keine Sicherheitswarnung, kein Freischalten. Updates danach mit einem Klick in der App, siehe [Updates](#updates).

<details><summary><b>Lieber ohne Terminal?</b> (Download + einmal freischalten)</summary>

1. [**REKORD-macOS-AppleSilicon.zip**](https://github.com/KimJongUnNK/rekord/releases/latest/download/REKORD-macOS-AppleSilicon.zip) laden, öffnen → **REKORD** in **Programme** ziehen.
2. REKORD doppelklicken. macOS meldet *„Apple konnte nicht überprüfen …“* → **Fertig**.
3. **Systemeinstellungen** → **Datenschutz & Sicherheit** → ganz unten bei *„REKORD wurde blockiert“* → **Dennoch öffnen** → Passwort oder Touch ID.

Nur einmal nötig, danach startet REKORD ganz normal.
</details>

**② Erlauben**
- *Mikrofon* → **Erlauben**
- *Geräte im lokalen Netzwerk finden* → **Erlauben** (damit das iPhone den Mac findet)

**③ Kurz warten**
Beim ersten Start lädt REKORD die Sprachmodelle. Den Fortschritt siehst du unten links. Steht dort **„Bereit · lokal“**, kann's losgehen.

---

## 2. Windows

> **Brauchst du:** Windows 10 oder 11 (64-Bit).

**① Installieren – am schnellsten mit einer Zeile**
Start → **PowerShell** öffnen, diese Zeile einfügen, **Enter**:

```
irm https://github.com/KimJongUnNK/rekord/releases/latest/download/install.ps1 | iex
```

REKORD wird installiert (ohne Admin), bekommt einen Eintrag im **Startmenü** und auf dem **Desktop** und startet. Kein blaues Warnfenster. Updates danach mit einem Klick in der App, siehe [Updates](#updates).

<details><summary><b>Lieber ohne PowerShell?</b> (Zip + einmal freischalten)</summary>

1. [**REKORD-Windows-x64.zip**](https://github.com/KimJongUnNK/rekord/releases/latest/download/REKORD-Windows-x64.zip) laden → Rechtsklick → **Alle extrahieren…**
2. Im Ordner **REKORD.exe** doppelklicken. Blaues Fenster *„Der Computer wurde durch Windows geschützt“* → **Weitere Informationen** → **Trotzdem ausführen**.

Den Startmenü-Eintrag legt REKORD beim ersten Start selbst an.
</details>

**② Erlauben**
- Firewall-Fenster: Haken bei **Private Netzwerke** → **Zugriff zulassen** (damit das iPhone den PC findet)
- Mikrofon-Abfrage → **Zulassen**

**③ Kurz warten**
Die Sprachmodelle werden geladen. Steht unten links **„Bereit · lokal“**, ist alles fertig.

---

## 3. iPhone (optional)

Am iPhone gibt es REKORD als **echte App**, eine Web-Version im Browser gibt es nicht. Mit der App nimmst du am iPhone auf und siehst live, wer spricht – auch bei gesperrtem Bildschirm, mit Sperrbildschirm-Widget und Dynamic Island. Alles landet am Computer.

> **Voraussetzung:** REKORD ist am Computer offen und beide sind im **selben WLAN**.

### App aufs iPhone bringen

**Mit Xcode (Mac):** `brew install xcodegen && cd ios && xcodegen generate && open Rekord.xcodeproj` → bei *Signing & Capabilities* dein Team wählen → iPhone anschließen → **Run**.

**Oder mit Sideloadly (Mac oder Windows):**
1. **Sideloadly** installieren: [sideloadly.io](https://sideloadly.io)
   *Windows:* zusätzlich **iTunes** und **iCloud** von apple.com installieren, nicht aus dem Microsoft Store.
2. [**REKORD-iOS-unsigned.ipa**](https://github.com/KimJongUnNK/rekord/releases/latest/download/REKORD-iOS-unsigned.ipa) laden.
3. iPhone per Kabel anschließen → am iPhone **„Diesem Computer vertrauen“**.
4. Sideloadly öffnen → die **.ipa** ins Fenster ziehen → deine **Apple-ID** eingeben → **Start**.

**Am iPhone freischalten**

5. **Einstellungen** → **Datenschutz & Sicherheit** → **Entwicklermodus** → an. Das iPhone startet neu, danach **Aktivieren** tippen.
6. **Einstellungen** → **Allgemein** → **VPN & Geräteverwaltung** → deine Apple-ID → **Vertrauen**.

> Mit einer **kostenlosen Apple-ID** läuft die App 7 Tage. Danach einfach nochmal installieren. Deine Daten bleiben erhalten.

### Koppeln

Am Computer: *Einstellungen → iPhone & Geräte*. Dort stehen ein **QR-Code** und ein **6-stelliger Code** (z. B. `482 913`).

- REKORD am iPhone öffnen → **QR-Code scannen** – fertig.
- Oder: Computer unter *Im WLAN gefunden* antippen (oder die Adresse eintippen) → den **6-stelligen Code** eingeben → **Koppeln**.

Der Code gilt 10 Minuten und nur zum Koppeln: Das iPhone bekommt dabei einen eigenen Schlüssel. Nach 5 falschen Versuchen ist 1 Minute Pause. Unter **Gekoppelte Geräte** trennst du einzelne iPhones, **Alle Geräte trennen** sperrt alle aus (z. B. wenn ein Handy verloren ging).

**Extras**
- **Sperrbildschirm:** lange drücken → *Anpassen* → *Sperrbildschirm* → Widgets → **REKORD**
- **Kontrollzentrum:** öffnen → **+** oben links → *Steuerelement hinzufügen* → **REKORD**
- **Action Button:** *Einstellungen → Action Button → Kurzbefehl* → **REKORD Aufnahme starten**

---

## Erster Start: die Einführung

Beim ersten Öffnen erscheint die Einführung. Jeder Schritt lässt sich **Überspringen** und später in den Einstellungen ändern;
*Einstellungen → Speicher & Datenschutz → Hilfe → Einführung starten* zeigt sie nochmal.

| Schritt | Was passiert |
|---|---|
| **Willkommen** | Was REKORD kann, in drei Sätzen. |
| **Speicherort** | **Wo soll REKORD speichern?** Laufwerk antippen – eingebaut, externe Festplatte (USB/Thunderbolt), zweite SSD (NVMe) oder Netzlaufwerk (NAS) – oder einen Ordner eintragen. *KI-Modelle im selben Ordner* abwählen, um die großen Modelle woanders hinzulegen. Erst danach lädt REKORD etwas herunter. Liegt der Ort woanders, zieht REKORD kurz um und startet neu. |
| **Aussehen** | Hell/Dunkel und Akzentfarbe – du siehst es sofort. |
| **Sprache** | **Sprache in den Meetings** (fest eingestellt = am genauesten, *Automatisch* für gemischte Runden) und **Protokolle schreiben auf** (Deutsch, Englisch oder wie im Gespräch). Bei Englisch bekommt man zum Einsprechen auch einen englischen Text. |
| **Mikrofon** | Mikrofon wählen, etwas sagen – der Balken muss ausschlagen. |
| **KI** | **Lokal · gratis** (ein Klick, läuft im Hintergrund weiter), **Claude** oder **ChatGPT** (Key einfügen, wird sofort getestet) oder *Erstmal ohne*. |
| **Deine Stimme** | Namen eingeben → **Jetzt einsprechen** → deinen Text vorlesen (siehe unten). Ab dann steht in jedem Meeting dein Name. |
| **iPhone** | Mit der REKORD-App am iPhone den QR-Code scannen oder den 6-stelligen Code eingeben (siehe [Koppeln](#koppeln)). |
| **Fertig** | Übersicht, was eingerichtet ist · **Erste Aufnahme** oder **Zur App**. |

**Einsprechen – drei Wege.** Oben im Fenster wählst du, wie REKORD die Stimme lernen soll:

| Weg | So geht's |
|---|---|
| **Text vorlesen** | REKORD erstellt für jeden Namen einen eigenen Text (ca. 45 Sekunden, mit Zahlen, Fragen, unterschiedlichen Lauten). *Anderer Text* tauscht ihn aus. Am genauesten. |
| **Einfach reden lassen** | Kein Text: Die Person redet über irgendwas – oder du lässt jemanden reden, der sowieso spricht, z. B. den Prof am Anfang der Vorlesung (Mikro in seine Richtung). *💬 Gesprächsidee* gibt ein Thema, wenn nichts einfällt. Kurze Zwischenrufe anderer lässt REKORD weg. |
| **Aus Aufnahme lernen** | Aufnahme wählen → Stimme anhören (▶) → auswählen → **Stimme lernen**. Gut für Leute, die man nicht bitten kann, etwas einzusprechen. |

Gezählt werden nur Sekunden, in denen wirklich gesprochen wird: mindestens 25, ideal ~45. Danach **Stimme speichern** – REKORD prüft, ob es wirklich eine Stimme war, und zeigt die Qualität an.

---

## 4. KI verbinden

Transkript und Sprecher-Erkennung gehen **ohne KI**. Für Protokoll, To-dos, Mind Map und Fragen brauchst du eine.
Ohne KI zeigt REKORD unter *Aufnahmen* die Karte **„Protokolle, To-dos, Mind Map – verbinde eine KI“** – dort einfach antippen (*Später* blendet sie aus). Jederzeit: **Einstellungen → KI**.
Ist auf dem Computer schon Ollama oder LM Studio mit einem Modell, nimmt REKORD das automatisch.

| | So geht's | Kosten |
|---|---|---|
| **Lokal · gratis** | **Lokal einrichten** antippen. REKORD installiert Ollama selbst, lädt das Modell, das zu deinem Arbeitsspeicher passt, und verwendet es. Fortschritt wird angezeigt, du kannst nebenbei weiterarbeiten. | **gratis**, nichts verlässt den Computer. REKORD erkennt RAM und Grafikchip und nimmt das beste Modell, das darauf flott läuft: z. B. *qwen3:4b* bei 8 GB, *qwen3:8b* bei 16 GB, *qwen3:14b* bei 24 GB (Apple-Chip/Grafikkarte), *qwen3:30b* ab 32 GB. |
| **Claude** | **Key erstellen ↗** → bei Anthropic anmelden → *Create Key* → Key kopieren → ins Feld einfügen. REKORD testet sofort. | pro Nutzung, meist Cent-Beträge pro Meeting |
| **ChatGPT** | **Key erstellen ↗** → *Create new secret key* → kopieren → einfügen. Das Modell wählt REKORD selbst, getestet wird sofort. | pro Nutzung. Das ChatGPT-Plus-Abo zählt **nicht**. |

**Mit deinem Claude-Abo statt API-Key (Claude Desktop):**
REKORD → *Einstellungen → Claude Desktop (MCP)* → **Mit Claude Desktop verbinden** → **Claude neu starten**.
Danach kannst du Claude direkt fragen: *„Was haben wir im letzten Meeting entschieden?“* Für Claude im Terminal: **Mit Claude Code verbinden**.

---

## 5. Erste Aufnahme

1. **Leute einmal anlernen:** *Personen* → **Person einsprechen** → Text vorlesen, einfach reden lassen oder aus einer Aufnahme lernen (siehe [Einsprechen](#erster-start-die-einführung)). Ab dann erkennt REKORD die Person mit Namen.
2. **Roter Knopf** → REKORD fragt **„Wer ist dabei?“** – das ist Pflicht, sonst startet keine Aufnahme:
   - **Wo findet das Meeting statt?** – **Vor Ort**, **Online (Teams, Zoom, Meet …)** oder **Vorlesung**. Bei Online nimmt REKORD den Ton des Calls mit auf – und fragt **Dein Mikrofon auch aufnehmen?**: **Call + mein Mikro** oder **Nur Call-Ton**. Bei Vorlesung musst du nicht mitzählen (siehe unten).
   - **Wie viele sprechen?** – dich mitgezählt (Zahl antippen oder **−/+**).
   - **Wer davon ist bekannt?** – die Leute antippen, die REKORD schon kennt.
   - Alle anderen zählen als neu. Am besten gleich **„… jetzt einsprechen“** – jede neue Person liest ihren Text, dann ist sie ab sofort bekannt.
   - **Unterlagen** (optional): **PDF, Folien, Dokumente …** – Agenda, Folien, Teilnehmerliste. Namen und Fachbegriffe daraus schreibt REKORD richtig, schon in der Live-Mitschrift (siehe [Unterlagen](#unterlagen-namen-und-begriffe-richtig)).
   - **Aufnahme starten**.
3. Während der Aufnahme siehst du, wer spricht. Stimmen, die REKORD nicht kennt, heißen **„Nicht erkannte Stimme“** – nie „Sprecher 1, 2, 3“. Transkribiert wird trotzdem alles.
4. **Stopp:** Ein paar Minuten später ist das Protokoll fertig. Gab es unbekannte Stimmen, fragt REKORD oben **„Wer ist das?“**: anhören (▶), Namen eingeben, **Merken** – ab der nächsten Aufnahme werden sie erkannt.
   Hat sich jemand vorgestellt („Hier ist Emil …“), steht der Name schon drin.

---

## Das REKORD-Fenster

REKORD ist am Computer ein **echtes Programm** – kein Browser, keine Webseite im Fenster. Es startet schnell, reagiert direkt und ist durchgehend animiert. Ab Version 1.3 ist **alles** im REKORD-Fenster. Die iPhone-App ist ebenfalls eine echte App.

| Bereich | Was geht |
|---|---|
| **Aufnahmen** | Liste mit Sprecher-Punkten und Fortschritt der Auswertung – **■** daneben stoppt sie (z. B. die falsche Datei) · **Suchen** (auch im Gesagten) · **Ordner** als Filter · **Importieren**, Dateien ins Fenster ziehen oder im Finder/Explorer kopieren und mit **⌘ V** / **Strg + V** einfügen |
| **Aufnahme ansehen** | **Unterlagen** (oben rechts): PDF, Word, PowerPoint, Excel, Text oder Fotos zur Aufnahme – Namen und Begriffe daraus werden im Transkript richtig geschrieben · läuft die Auswertung noch: **Stoppen** oder **Löschen** direkt in der Fortschrittsanzeige · **Player** mit Wellenform, farbiger Sprecher-Leiste und ★, **−15/+15**, Tempo **1×–2×** · **Titel** anklicken zum Umbenennen · **Sprecher** antippen: umbenennen, **Stimme merken**, zusammenführen · **Wer ist das?** für unbekannte Stimmen (anhören, Namen, **Merken**) · Reiter **Zusammenfassung** (Vorlage wählen, KI schreibt live mit; läuft die genaue Auswertung noch, heißt der Knopf **Nach der Auswertung** und merkt die Vorlage vor – das Protokoll entsteht dann automatisch aus dem vollständigen Transkript; To-dos abhaken, Zeitstempel springen ins Audio, kopieren, bearbeiten, löschen), **Transkript** (Text direkt korrigieren, Namen antippen → **Wer sagt das?**, suchen, **Suchen & Ersetzen**, **Mitscrollen**), **Mind Map** (erstellen, als SVG/PNG speichern), **Fragen** (Chat nur über diese Aufnahme), **Notizen** und **Ordner**, **Unterlagen** (Dateien, Korrekturen einzeln zurücknehmen, **Alle rückgängig**, **Neu abgleichen**), **Export** (Markdown, Word, PDF, Text, SRT, WebVTT, JSON, Audio, Zwischenablage) · **•••**: **Dateien anhängen …**, **Unterlagen hinzufügen …**, **Auswertung stoppen**, neu verarbeiten, Personen neu erkennen, umbenennen, löschen · Datei auf eine offene Aufnahme ziehen → **Anhängen** oder **Als neue Aufnahme** |
| **Live** | großer Aufnahmeknopf · **Mikrofon** wählen (darunter) · **Wer ist dabei?** mit **Vor Ort**, **Online** und **Vorlesung** · groß in der Farbe der Person, wer gerade spricht · Redeanteile · **Nicht erkannte Stimme** antippen → Namen eingeben → **Merken** · **Mitschrift** live · **Markieren**, **Pause**, **Stopp & speichern** · kommt vom Mikrofon kein Ton an, sagt REKORD das und lässt dich **während der Aufnahme das Mikrofon wechseln**; setzt es aus (AirPods raus, USB abgesteckt), startet REKORD es von selbst neu · bei einem Bluetooth-Mikrofon (AirPods …) ein Hinweis zur Klangqualität |
| **Personen** | alle bekannten Stimmen mit Aufnahmen und Stimmproben · **Person einsprechen** mit drei Wegen: **Text vorlesen** (eigener Text pro Name, **↻ Anderer Text**), **Einfach reden lassen** (**💬 Gesprächsidee**), **Aus Aufnahme lernen** (Aufnahme wählen, Stimme anhören ▶, auswählen, **Stimme lernen**) · Sekundenzähler zählt nur echte Sprache (mind. 25, ideal ~45 s) · **…oder eine Datei mit nur dieser Person** · Stift-Symbol: Name, Farbe, **Stimmabdruck löschen** · bei **Wer ist dabei?** gleich **Neue Person jetzt einsprechen** |
| **Fragen** | ein Chat über **alle** Aufnahmen: „Was hat Lisa zum Budget gesagt?“ – die Antwort nennt, wer es wann gesagt hat, ein Klick auf die Zeit öffnet die Aufnahme genau dort · Vorschläge zum Antippen · **Verlauf leeren** · ohne KI zeigt die Seite, wie du eine verbindest |
| **Vorlagen** | alle Formate für Zusammenfassungen · am **⠿-Griff ziehen** oder mit **⤒ ↑ ↓** sortieren – oben steht, was dir am wichtigsten ist, in dieser Reihenfolge erscheinen sie beim Zusammenfassen · **Reihenfolge zurücksetzen** · antippen → **bearbeiten** (eingebaute: Speichern legt eine eigene Kopie an) · **Eigene Vorlage** · eigene **Löschen** |
| **Einstellungen** | alle Bereiche wie unten beschrieben, mit Sprung-Knöpfen oben · **Akzentfarbe** färbt sofort das ganze Fenster · **Pegel testen** fürs Mikrofon · lokale KI mit einem Klick, Modelle laden/löschen · **QR-Code** und **6-stelliger Code** fürs iPhone, läuft sichtbar ab und erneuert sich · Speicherort und KI-Modelle **umziehen** mit Fortschritt · **Updates** mit „Was ist neu“ · **REKORD beenden** |
| **Einführung** | beim ersten Start, Schritt für Schritt (siehe [Erster Start](#erster-start-die-einführung)) – später unter *Einstellungen → Speicher & Datenschutz → Hilfe → Einführung starten* |
| **Laufwerk fehlt** | Liegt der Speicherort auf einer Festplatte, die gerade nicht angeschlossen ist, zeigt REKORD genau das statt einer leeren Liste: **Nochmal prüfen** oder **Neu auf diesem Computer anfangen** |
| **Menüleiste / Taskleiste** | Solange REKORD läuft, sitzt sein Symbol oben in der Menüleiste (Mac) bzw. unten rechts im Infobereich (Windows, Linux): zeigt, ob gerade aufgenommen wird, **REKORD öffnen**, **Aufnehmen** bzw. **Aufnahme stoppen & speichern**, **REKORD beenden**. Ist eine Aufnahme fertig ausgewertet, während du in einem anderen Programm bist, kommt eine **Mitteilung** – antippen öffnet sie. |

**Tastatur**

| Taste | Was passiert |
|---|---|
| **Strg + R** (Mac: **⌘ R**) | Neue Aufnahme – von überall |
| **Leertaste** | Pause / weiter (während der Aufnahme) |
| **H** | Wichtigen Moment markieren (★) |
| **Strg + F** (Mac: **⌘ F**) | Suchen |
| **Strg + I** (Mac: **⌘ I**) | Importieren |
| **Strg + V** (Mac: **⌘ V**) | kopierte Audio-/Videodateien importieren |
| **Strg + 1** … **Strg + 5** (Mac: **⌘ 1** … **⌘ 5**) | Aufnahmen / Live / Fragen / Personen / Vorlagen – wie links in der Leiste |
| **Strg + ,** (Mac: **⌘ ,**) | Einstellungen |

**Hell oder dunkel:** das kleine Symbol unten links schaltet um – *wie das System*, *hell*, *dunkel*.

**Schließen:** Läuft gerade eine Aufnahme, fragt REKORD vorher und speichert sie (**Speichern & beenden**). Ist *Mit dem Computer starten* an, läuft REKORD nach dem Schließen unsichtbar weiter, damit das iPhone es erreicht – ein Klick aufs REKORD-Symbol holt das Fenster zurück.

**Mikrofon am Mac:** Beim ersten Aufnehmen fragt macOS, ob REKORD das Mikrofon benutzen darf → **Erlauben**. Aus Versehen abgelehnt? *Systemeinstellungen → Datenschutz & Sicherheit → Mikrofon* → REKORD an.

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
- **Noch ein Schritt:** Solange keine KI gewählt ist, steht hier die Auswahl **Lokal · gratis**, **Claude**, **ChatGPT** oder **Ohne KI weiter**.
- **Suchen:** findet Titel *und* alles, was gesagt wurde.
- **Datei transkribieren** (links unter *Aufnehmen*, auf jeder Seite – auch im Menüleisten-Symbol): Audio- oder Videodatei wählen (der Dialog startet in **Downloads**) – die Aufnahme öffnet sich sofort und wird ausgewertet. Genauso: ins Fenster ziehen oder im Finder/Explorer kopieren und in REKORD mit **⌘ V** / **Strg + V** einfügen – **jedes Audio- und Videoformat** (MP3, MP4, M4A, WAV, MOV, MKV, AVI, WMV, AIFF, MTS …; auch ungewöhnliche Endungen, solange Ton drin ist): Sprachmemos, Zoom, Teams-Aufzeichnungen, WhatsApp, Diktiergerät. **Bei Videos** speichert REKORD zusätzlich ein Standbild, wann immer sich das Bild deutlich ändert (neue Folie, Bildschirm, Szene) – im **Transkript** steht es direkt über dem Satz, der dazu gesagt wurde; antippen → groß, **Ab hier anhören**. Kann REKORD eine Datei nicht lesen, sagt es warum. **Unterlagen gleich mit:** Im Dialog Audio *und* PDF/Folien zusammen auswählen (oder zusammen reinziehen) – die Dokumente werden Unterlagen der neuen Aufnahme.
- **Falsche Datei erwischt?** In der Liste auf **■** neben dem Fortschritt klicken – oder Aufnahme öffnen → **Stoppen** (die Aufnahme bleibt, *Nochmal* wertet sie aus) bzw. **Löschen** (stoppt und entfernt sie).
- **Ordner:** erscheinen oben als Filter, sobald eine Aufnahme einen Ordner hat (vergibst du unter *Notizen*).
- Eine Aufnahme anklicken öffnet sie:
  - **Titel** antippen zum Umbenennen.
  - **Player:** Wellenform und farbige Sprecher-Leiste anklicken zum Springen, **±15 s**, Tempo **1×–2×**. ★ markiert deine Highlights.
  - **Sprecher-Karten:** antippen → Namen ändern, **Stimme merken** (wird künftig erkannt) oder mit einem doppelt erkannten Sprecher **zusammenführen**.
  - **Wer ist das?** erscheint, solange es eine **Nicht erkannte Stimme** gibt: pro unbekannter Stimme ▶ anhören, Namen eingeben, **Merken**. *Später* blendet es aus.
  - Darunter die Reiter:

| Reiter | Was du dort machst |
|---|---|
| **Zusammenfassung** | Vorlage wählen → **Zusammenfassen**. Mehrere Vorlagen geben mehrere Blickwinkel. To-do-Häkchen sind klickbar, Zeitstempel springen ins Audio. Kopieren, bearbeiten, löschen. |
| **Transkript** | Text antippen zum Korrigieren · **Namen** links bei einem Satz antippen → **Wer sagt das?**: Person wählen oder neuen Namen eingeben → **Zuordnen** (mit *Alle Sätze dieser Stimme* und *Stimme dabei lernen*) · **Suchen & Ersetzen**, auch Sprechernamen, optional dauerhaft ins Vokabular · Zeit anklicken springt hin · *Mitscrollen* beim Abspielen |
| **Mind Map** | **Mind Map erstellen** · als **SVG** oder **PNG** speichern |
| **Fragen** | Chat nur über diese Aufnahme, z. B. *„Wer hat was zugesagt?“* |
| **Notizen** | eigene Notizen (fließen in Zusammenfassungen ein) · **Ordner** vergeben |
| **Unterlagen** | **Unterlagen hinzufügen** oder Dateien reinziehen (PDF, Word, PowerPoint, Excel, Text, Fotos) · je Datei **Öffnen** und 🗑 · **Im Transkript korrigiert**: jede Korrektur als *falsch → richtig* – antippen nimmt sie zurück, nochmal antippen setzt sie wieder · **Alle rückgängig** · **Neu abgleichen** |
| **Export** | Markdown, Word, Text, Untertitel als SRT oder WebVTT, JSON, Zwischenablage, PDF (übers Drucken), Original-Audio |

  - **Audio anhängen** (oben rechts, neben „…“) bzw. *„…“ → Dateien anhängen …* (z. B. Teil 2 des Meetings oder Sprachmemos dazu: kommen hinten an die Aufnahme, danach wird alles zusammen neu transkribiert – Sprecher über alle Teile hinweg; ★-Momente behalten ihre Zeit) · **Unterlagen** (oben rechts) bzw. *„…“ → Unterlagen hinzufügen …* · *„…“ → Auswertung stoppen* · *Neu verarbeiten* (z. B. nach Modellwechsel) · *Personen neu erkennen* (nach dem Anlernen neuer Leute) · *Umbenennen* · *Löschen*. Eine Datei auf die offene Aufnahme ziehen fragt: **Anhängen** oder **Als neue Aufnahme**. Ein PDF oder Dokument auf die offene Aufnahme ziehen macht es ohne Rückfrage zur Unterlage.

### Unterlagen: Namen und Begriffe richtig

Die Spracherkennung hört nur Klang. Einen Namen wie *Boenke* oder einen Begriff wie *Zapier*, den sie nie gesehen hat, schreibt sie, wie er klingt: *Bönke*, *Sapir*. Die Agenda, die Folien oder die Teilnehmerliste wissen, wie es richtig heißt.

- **Hinzufügen:** vor der Aufnahme in *Wer ist dabei?* → **Unterlagen**, während der Aufnahme auf die Live-Seite ziehen, danach in der Aufnahme → **Unterlagen** – oder beim Import zusammen mit der Audiodatei auswählen. Geht: **PDF, Word (DOCX), PowerPoint (PPTX), Excel (XLSX), OpenDocument, Text, Markdown, HTML, RTF, EPUB, Fotos** (JPG, PNG, HEIC …). Alte Formate (DOC, PPT, Pages, Keynote) bitte als PDF speichern.
- **Was passiert:** REKORD liest die Dateien und sucht die seltenen Wörter heraus – Namen, Fachbegriffe, Produktnamen, Abkürzungen. Ein eingebautes Wörterbuch (Deutsch/Englisch) sagt, was ein normales Wort ist. Steht im Transkript etwas, das gleich klingt oder fast gleich geschrieben ist, wird es korrigiert: *Bönke → Boenke*, *Sapir → Zapier*, *Order Bird → Orderbird*. Normale Wörter (*Vortrag*, *Konzept*) werden nie angefasst.
- **Mit lokaler KI** (Ollama, LM Studio) sucht zusätzlich die KI nach falsch erkannten Begriffen – sie darf nur Wörter einsetzen, die wirklich in den Unterlagen stehen, nie umformulieren. Korrekturen der KI sind mit **KI** markiert.
- **Fotos und gescannte PDFs:** am Mac liest die eingebaute Texterkennung von macOS den Text (offline, wie *Live Text*). Unter Windows/Linux eine lokale KI, die Bilder versteht (Ollama mit z. B. *qwen2.5vl* oder *gemma3*).
- **Alles prüfbar:** Reiter **Unterlagen** → *Im Transkript korrigiert* zeigt jede Korrektur mit Anzahl. Antippen nimmt sie zurück (überall in dieser Aufnahme), **Alle rückgängig** stellt das Transkript her, wie es erkannt wurde – deine eigenen Änderungen bleiben. Entfernst du eine Unterlage, gehen die Korrekturen, die nur aus ihr kamen.
- **Zusammenfassung und Fragen** kennen die Unterlagen als Hintergrund (*„laut Agenda.pdf …“*) – mit einer lokalen KI.
- **Datenschutz:** Unterlagen bleiben auf diesem Rechner (neben der Aufnahme, im REKORD-Ordner). Auch wenn Claude oder ChatGPT als KI eingestellt ist, gehen sie dort **nicht** hin – außer du schaltest *Einstellungen → Transkription → Unterlagen an Cloud-KI* selbst ein.

### Live
- Oben: **Vor Ort**, **Online** oder **Vorlesung**.
  - **Vor Ort** – alle sitzen im Raum, das Mikrofon reicht.
  - **Online** – Teams, Zoom, Meet …: REKORD nimmt am Computer zusätzlich den **Ton des Calls** auf, also die anderen Teilnehmer, direkt aus dem Lautsprecher-Signal. Kopfhörer sind kein Problem. Nur Ton, kein Bild. Am Mac fragt macOS beim ersten Mal nach **Bildschirm- & Systemaudioaufnahme** → REKORD erlauben (macOS 13 oder neuer). Am iPhone geht das nicht – dort das iPhone neben den Lautsprecher legen.
    - **Call + mein Mikro** – die anderen im Call **und du**. Das ganze Meeting.
    - **Nur Call-Ton** – nur, was Teams, Zoom, Meet … am Computer abspielen. Dein Mikrofon wird **gar nicht geöffnet**: du bist nicht auf der Aufnahme, Tippen und Hintergrund bei dir auch nicht. Gut für Webinare, Vorträge und Calls, in denen du nur zuhörst. Bei „Wie viele?“ zählst du dich dann nicht mit. Geht der Call-Ton auf dem Computer nicht, startet REKORD nicht stumm, sondern sagt warum.
  - **Vorlesung** – eine Person trägt vor (Uni, Schulung, Vortrag). Mitzählen musst du nicht: REKORD erkennt die vortragende Person an der Stimme – bekannt mit Namen, sonst **„Vortragende Person“** – und sammelt alle anderen Stimmen unter **„Publikum“**. Danach wird automatisch ein **Lernzettel** geschrieben: Kernaussagen, Definitionen, Prüfungsrelevantes, Fragen aus dem Hörsaal. Mit **„Wer ist das?“** gibst du der vortragenden Person einen Namen.
- **Titel** eingeben (optional).
- **Wer ist dabei?** Die Karte zeigt, wer angekündigt ist; **Festlegen** ändert es. **Vorstellungsrunde** lässt eine neue Person ihren Text einsprechen.
- **Roter Knopf** (oder **Leertaste**) → zuerst **Wer ist dabei?** (Anzahl + Bekannte, siehe [Erste Aufnahme](#5-erste-aufnahme)), dann läuft die Aufnahme. Nochmal drücken stoppt · **★** (oder Taste **H**) markiert einen wichtigen Moment · **Pause**.
- Mitte: **wer gerade spricht**, groß und in der Farbe der Person.
- Rechts *Im Raum*: alle Stimmen mit Redeanteil. Unbekannte stehen gesammelt als **Nicht erkannte Stimme** – antippen → Namen eingeben → die zuletzt gehörte Stimme ist ab sofort erkannt.
- *Mitschrift*: das Transkript, live.

### Fragen
Ein Chat über **alle** Aufnahmen: *„Was hat Lisa letzte Woche zum Budget gesagt?“* Die Antworten haben anklickbare Quellen, die direkt an die Stelle in der Aufnahme springen. **Verlauf leeren** oben rechts.

### Personen
- **Person einsprechen:** Namen eingeben → Weg wählen: **Text vorlesen**, **Einfach reden lassen** oder **Aus Aufnahme lernen** → **Aufnahme starten** (mind. 25 s Sprache, ideal ~45 s) → **Stimme speichern**. Oder eine Datei mit nur dieser Person wählen.
- **Stift-Symbol:** Namen oder Farbe ändern, oder **Stimmabdruck löschen**.
- Jede Bestätigung („Stimme merken“) verbessert den Stimmabdruck.

### Vorlagen
31 fertige Formate (Business, Vertrieb, Events, Medien, HR, Bildung, Kreativ, Persönlich, Recht, Analyse) – als eine Liste in **deiner Reihenfolge**.
- **Sortieren:** am **⠿**-Griff packen und nach oben oder unten ziehen – oder **↑ ↓**, **⤒** schiebt ganz nach oben. Wird sofort gespeichert. Was oben steht, steht auch beim **Zusammenfassen** (und in der iPhone-App) ganz oben in der Auswahl. **Reihenfolge zurücksetzen** stellt die ursprüngliche wieder her.
- Vorlage anklicken → ansehen. **Speichern** legt eine eigene Kopie an, die du anpassen kannst.
- **Eigene Vorlage:** Namen, Kategorie, Kurzbeschreibung und den Text schreiben, was die KI liefern soll.

### Einstellungen
Oben gibt's Sprung-Knöpfe zu den Bereichen. *Darstellung* und *Audio & Mikrofon* gelten **nur für dieses Gerät**, alles andere für den ganzen Computer. Die Meeting-Art (*Vor Ort*, *Online*, *Vorlesung*) wählst du vor jeder Aufnahme bei **Wer ist dabei?** – REKORD merkt sich die letzte.

| Bereich | Felder (so heißen sie in der App) |
|---|---|
| **Darstellung** | **Erscheinungsbild** System / Hell / Dunkel · **Akzentfarbe** (9 fertige oder eigene als `#RRGGBB`) |
| **Audio & Mikrofon** | **Mikrofon** wählen + *Pegel testen* · **Mitschrift während der Aufnahme** an/aus (aus = nur zeigen, wer spricht, die Texte kommen danach – spart Rechenleistung) · **Computer wach halten**: während einer Aufnahme geht der Computer nicht in den Ruhezustand (der Bildschirm darf aus) |
| **KI** | Anbieter wählen: Claude, ChatGPT, Lokal, Kompatibel, Aus · Lokal: **Lokales Modell** – **Lokal einrichten** (installiert alles) · *Dein Computer*: RAM + Grafikchip erkannt, **Bestes Modell … laden & verwenden** · *Auf diesem Computer*: **Verwenden** oder **🗑 Löschen** je Modell (war es aktiv, springt REKORD auf ein anderes), **Alle nicht verwendeten löschen** · *Weitere Modelle*: **Laden & verwenden** (zu große mit *Trotzdem laden*) · *Anderes Modell*: jeden Namen von ollama.com/library eintippen → **Laden & verwenden** · Claude/ChatGPT: **Key erstellen ↗** · **API-Key** · **Modell** (*Laden* holt die Liste) · Claude: **Denkaufwand**, **Ausweichmodell** · Lokal/Kompatibel: **Ollama-Adresse** bzw. **Server-Adresse**, **Kontextlänge** · **Verbindung** → *Testen* · **Sprache der Zusammenfassungen** · **Automatisch zusammenfassen** + Standard-Vorlage |
| **Transkription** | **Sprache** (fest eingestellt = genauer, *Automatisch* für gemischte Meetings) · **Engine**: *Whisper ONNX* (läuft überall) oder *faster-whisper* (wortgenaue Zeiten, hört Begriffe aus Vokabular und Unterlagen direkt, sehr schnell mit NVIDIA-Grafikkarte, sonst auf dem Prozessor – darunter steht, worauf es läuft) · **Modell** (*small* = Standard, *turbo* = beste Qualität; nicht geladen → **Jetzt laden**) · **Computer flüssig halten** → *Im Hintergrund auswerten* (Standard: niedrige Priorität, höchstens die Hälfte der Kerne – du arbeitest normal weiter; aus = schneller fertig, Computer dabei ausgelastet) · **CPU-Threads** · **Vokabular** für Namen, die falsch erkannt werden · **Unterlagen** → *Mit lokaler KI abgleichen* (Standard an; der Abgleich am Klang und an der Schreibweise läuft immer) · **Unterlagen an Cloud-KI** → *Erlauben* (Standard aus: Unterlagen verlassen nie diesen Rechner) |
| **Sprecher-Erkennung** | **Personen-Erkennung (Aufnahmen)** und **Personen-Erkennung (live)**: wie streng (höher = weniger Verwechslungen) · **Sprecher trennen**: erscheint eine Person doppelt, runterdrehen · **Anzahl Sprecher**: wenn bekannt, fest einstellen · **Stimmabdruck-Modell** |
| **Modelle** | **Alles Nötige laden** (fehlt etwas zum Transkribieren, ein Klick für alles) · je Modell *Laden* (mit Fortschritt; ging es schief, steht der Grund darunter und *Nochmal*) oder *Entfernen* · auch unter *Transkription → Modell*: **Jetzt laden**, direkt beim gewählten Modell |
| **iPhone & Geräte** | **QR-Code** für die iPhone-App · **Adresse** · **Kopplungs-Code** (6 Ziffern, 10 Minuten gültig, *Neuer Code*) · **Gekoppelte Geräte** (*Trennen* je Gerät, **Alle Geräte trennen**) · Linux: **Firewall** → *Für iPhone freigeben*, falls sie das iPhone blockiert |
| **Claude Desktop (MCP)** | **Claude Desktop**: *Mit Claude Desktop verbinden*, danach *Claude neu starten* · **Claude Code**: *Mit Claude Code verbinden* · *Von Hand eintragen*: Konfiguration zum **Kopieren** |
| **Speicher & Datenschutz** | **Speicherort**: wo Aufnahmen, Datenbank und Stimmabdrücke liegen – *Ändern …* → Laufwerk wählen (eingebaut, extern, NVMe, NAS) → **Umziehen**; REKORD kopiert alles, startet neu, der alte Ordner bleibt als Sicherheitskopie · **KI-Modelle**: wo Sprachmodelle und lokale KI liegen – eigenes Laufwerk möglich, *Ändern …* nimmt vorhandene Modelle mit · **Eingangsordner**: Dateien, die hier landen, werden automatisch verarbeitet · **Was verlässt das Gerät?** · **Mit dem Computer starten**: REKORD läuft ab dem Einschalten im Hintergrund, das iPhone kann sich jederzeit verbinden · **Hilfe**: *Einführung starten*, *Anleitung ↗* · **Version & Updates**: *Nach Updates suchen*, **Jetzt auf … aktualisieren**, *Automatisch nach Updates suchen* (siehe [Updates](#updates)) · **Beenden** → *REKORD beenden* |

In der **bisherigen Ansicht** (startet, wo das REKORD-Fenster nicht geht, und im Browser am Handy) gibt es zusätzlich: **Dichte** *Luftig* / *Kompakt* · **Audio-Verarbeitung** (Rauschunterdrückung, Echo-Unterdrückung, automatische Lautstärke des Browsers) · **Live-Erkennung** an/aus (aus spart Akku am Handy) · **Bildschirm wach halten**.

**In der iPhone-App** gibt's die Reiter *Live*, *Aufnahmen*, *Personen* und *Einstellungen* (Theme, Akzentfarbe, Mikrofon, KI, Hub). *Fragen über alle* und *Vorlagen* gibt's am Computer.
Auch dort fragt der rote Knopf zuerst **Wer ist dabei?**. Starts über Sperrbildschirm-Widget, Kontrollzentrum oder Action Button nehmen die zuletzt bestätigte Runde.

---

## Updates

Gibt es eine neue Version, steht links unter dem Status **„Update auf … →“**.
**Einstellungen → Speicher & Datenschutz → Version & Updates → Jetzt auf … aktualisieren**:

1. REKORD lädt die neue Version (Fortschritt wird angezeigt).
2. Sie **ersetzt** die installierte App – am selben Ort, mit denselben Verknüpfungen. Keine zweite App daneben.
3. REKORD startet neu und zeigt *„REKORD wurde auf … aktualisiert ✓“*. Aufnahmen, Personen und Einstellungen bleiben.

| | |
|---|---|
| **Läuft gerade eine Aufnahme** | Das Update wartet – erst stoppen. Eine Aufnahme wird nie abgebrochen. |
| **Neue Version von Hand gestartet**, während die alte noch offen ist | Die alte beendet sich von selbst, die neue übernimmt. Nimmt die alte gerade auf, übernimmt die neue direkt nach der Aufnahme. |
| **REKORD zweimal geöffnet** | Es kommt das offene Fenster nach vorne – kein zweites. |
| **Eine alte Kopie gestartet** (alte Verknüpfung, Kopie in *Downloads*) | Sie startet stattdessen die neueste installierte Version. |
| **Linux mit Paket** (deb, rpm, pacman) | Linux fragt einmal nach deinem Passwort. AUR (*rekord-bin*): über deinen AUR-Helfer aktualisieren. |
| **Mac** | Nach jedem Update fragt macOS nochmal nach Mikrofon bzw. *Bildschirm- & Systemaudioaufnahme* – erlauben (beim Systemaudio danach REKORD einmal neu starten). Grund: Ohne kostenpflichtiges Apple-Zertifikat hat jede Version eine neue Signatur, und macOS hängt die Erlaubnis an die alte. REKORD setzt die alten Schalter deshalb beim ersten Start einer neuen Version selbst zurück. |

*Automatisch nach Updates suchen* (an): REKORD fragt beim Start und alle 6 Stunden bei GitHub nach. Installiert wird nur auf Klick.
Die Installations-Zeile von oben funktioniert weiterhin auch als Update.

---

## Wenn was nicht klappt

| Problem | Lösung |
|---|---|
| **Mac:** *„REKORD ist beschädigt“* | Terminal öffnen, `xattr -dr com.apple.quarantine /Applications/REKORD.app` eingeben, REKORD nochmal öffnen |
| **Kein Mikrofon** | *Live* → unter dem Aufnahmeknopf das richtige **Mikrofon** wählen. Mac: in der Fehlermeldung **Mikrofon-Einstellung öffnen** → REKORD an |
| **Mac: alles erlaubt, aber REKORD sagt, es darf nicht aufnehmen** | Der Schalter gehört noch zu einer älteren REKORD-Version (jede Version hat eine neue Signatur). In der Fehlermeldung **Rechte neu setzen** tippen, Aufnahme neu starten, erlauben, wenn macOS fragt – beim Call-Ton danach REKORD einmal neu starten. **Systemaudio-Einstellung öffnen** bzw. **Mikrofon-Einstellung öffnen** springt direkt zum Schalter. Ohne Knopf, im Terminal (REKORD vorher beenden): `tccutil reset ScreenCapture app.rekord.desktop` und `tccutil reset Microphone app.rekord.desktop`. Steht in der Meldung *„Das ist keine fehlende Erlaubnis“*, meldet macOS einen anderen Fehler (mit Code) – den bitte [melden](https://github.com/KimJongUnNK/rekord/issues/new), er steht auch in **rekord.log**. |
| **iPhone findet den Computer nicht** | Gleiches WLAN? (Gäste-WLANs trennen Geräte.) Ist REKORD am Computer offen? (Tipp: *Speicher & Datenschutz* → **Mit dem Computer starten**.) Windows: Firewall „Private Netzwerke“ erlaubt? Linux: *iPhone & Geräte* → **Für iPhone freigeben** |
| **Lokal einrichten hängt oder bricht ab** | Internet prüfen, nochmal **Lokal einrichten** – fertige Teile werden nicht neu geladen. |
| **„Modelle werden geladen“ geht nicht weiter** | Internet prüfen → *Einstellungen → Modelle* → **Laden** |
| **Zusammenfassung zeigt Fehler** | *Einstellungen → KI* → **Testen**. Key richtig kopiert? Guthaben auf dem API-Konto? |
| **Claude Desktop sieht REKORD nicht** | Claude ganz beenden und neu öffnen (*Claude neu starten*). Steht unter *Claude Desktop (MCP)* **Verbunden**? |
| **Falsche Person erkannt** | Im Transkript auf den Namen tippen → richtigen Namen eingeben, *Stimme merken* bleibt an |
| **REKORD beenden** | Fenster schließen (läuft eine Aufnahme, wird sie vorher gespeichert). Mit *Mit dem Computer starten* läuft REKORD im Hintergrund weiter – ganz beenden: *Einstellungen* → ganz unten **REKORD beenden** |
| **Lieber die bisherige Ansicht** | REKORD mit der Umgebungsvariable `REKORD_CLASSIC=1` starten – dann öffnet sich alles wie vor Version 1.1. |
| **Fenster bleibt leer / Fehler suchen** | REKORD schreibt Meldungen in **rekord.log**: Mac `~/Library/Application Support/REKORD/`, Windows `%APPDATA%\REKORD\`, Linux `~/.config/REKORD/`. Beim [Problem melden](https://github.com/KimJongUnNK/rekord/issues/new) gern mitschicken. |
| **Zwei REKORD-Fenster / alte Version** | Ab 1.0.8 nicht mehr möglich (siehe [Updates](#updates)). Einmalig von einer älteren Version: alle REKORD-Fenster schließen, dann die neue öffnen. |
| **Backup** | Den **Speicherort**-Ordner kopieren (steht unter *Einstellungen → Speicher & Datenschutz*). Da liegt alles drin. |
| **„Laufwerk fehlt“ beim Start** | Der Speicherort liegt auf einer Festplatte oder einem Netzlaufwerk, das gerade nicht verbunden ist. Anschließen → **Nochmal prüfen**. Kommt es nicht mehr zurück: **Neu auf diesem Computer anfangen** (die Daten auf dem Laufwerk bleiben unberührt). |
| **REKORD zeigt mich als stumm, obwohl ich rede** | Ab 1.3.3 behoben: Die Anzeige „wer spricht“ wartete hinter der Live-Transkription. Erscheint das Mikrofon-Banner *„Vom Mikrofon kommt kein Ton an“*: Stummschalter prüfen oder direkt im Banner das richtige Mikrofon wählen – die Aufnahme läuft weiter. |
| **Live-Mitschrift hängt hinterher** | Auf langsamen Computern kommt die Live-Mitschrift nicht in Echtzeit mit. Sie holt dann auf (*„… übersprungen, damit die Mitschrift beim Jetzt bleibt“*) – nach dem Stopp steht trotzdem alles im Transkript, denn die genaue Auswertung nimmt immer die ganze Aufnahme. |
| **Zusammenfassung passt nicht zum Gespräch** | Direkt nach dem Stopp ist nur die Live-Mitschrift da. Ab 1.3.3 wartet *Zusammenfassen* deshalb auf die genaue Auswertung (*Nach der Auswertung*). Ältere Zusammenfassungen, die zu früh entstanden sind: im Reiter *Zusammenfassung* löschen und neu erstellen. |
| **AirPods-Aufnahme klingt dumpf / „elektronisch“** | Zwei Gründe. 1) Bluetooth: Sobald das Mikrofon von AirPods & Co. benutzt wird, schalten sie in den Telefon-Modus – das klingt immer nach Telefon. Besser: das Mikrofon des Computers wählen und die AirPods nur zum Hören nutzen. 2) Bis 1.3.2 hat REKORD selbst den Klang verschlechtert (die Umrechnung auf 16 kHz) – ab 1.3.3 sauber, bei jedem Mikrofon. |
| **Aufnahme da, aber beim Abspielen kein Ton** | Bis 1.3.2 spielte REKORD immer auf dem Ausgang, der beim Start aktiv war (z. B. AirPods, die inzwischen weg sind). Ab 1.3.3 immer auf dem aktuellen Ausgang des Systems. Sonst: Lautstärke/Ausgang in den Systemeinstellungen prüfen. |
| **„Spracherkennung fehlt“ / Modell nicht geladen** | Links unten auf **jetzt laden** klicken (oder *Aufnahmen* → **Jetzt laden**, oder *Einstellungen → Modelle → Alles Nötige laden*). Einmalig, danach offline. Ist das gewählte Modell noch nicht da, nimmt REKORD solange ein vorhandenes – es bricht nicht ab. Klappt das Laden nicht, steht der Grund dabei (z. B. *Keine Verbindung zu github.com*, *Kein Platz mehr auf dem Laufwerk*). |
| **Namen oder Fachbegriffe falsch geschrieben** | Unterlagen zur Aufnahme geben (Agenda, Folien, Teilnehmerliste): Aufnahme öffnen → **Unterlagen**. REKORD korrigiert dann, was gleich klingt. Findet es nichts: Steht das Wort wirklich so in der Datei? Ist es ein gescanntes PDF oder Foto, braucht es am Mac nichts weiter, sonst eine lokale KI, die Bilder versteht. Für Wörter, die in jeder Aufnahme falsch kommen: *Einstellungen → Transkription → Vokabular*. |
| **Eine Korrektur aus den Unterlagen ist falsch** | Reiter **Unterlagen** → die Korrektur antippen: sie ist überall in dieser Aufnahme zurückgenommen und bleibt es, auch beim nächsten Abgleich. |
| **Falsche Datei wird gerade ausgewertet** | In der Liste **■** neben dem Fortschritt, oder Aufnahme öffnen → **Stoppen** (bzw. **Löschen**). |
| **Computer wird beim Auswerten langsam** | Ab 1.3.1 wertet REKORD im Hintergrund aus: eigener Prozess mit niedriger Priorität (Mac: Utility-QoS), höchstens die Hälfte der Kerne, danach wird der Speicher der Sprachmodelle sofort frei. Prüfen: *Einstellungen → Transkription → Computer flüssig halten* ist an. Mit lokaler KI reserviert Ollama nur noch so viel Speicher, wie die Zusammenfassung braucht, und gibt ihn nach 2 Minuten frei. Immer noch zäh (z. B. 8 GB RAM)? *CPU-Threads* runter auf 2 und als KI-Modell eine Nummer kleiner (z. B. *qwen3:4b*). |
| **Person wird oft nicht erkannt** | Nochmal *einsprechen* (am besten mit dem Mikro, mit dem du aufnimmst) · vor der Aufnahme bei *Wer ist dabei?* die Leute antippen · nach der Aufnahme bei *Wer ist das?* bestätigen – jede Bestätigung macht die Erkennung besser. |

---

## Linux

**Eine Zeile für jede Distro** (Debian, Ubuntu, Mint, Fedora, openSUSE, Arch …) – wählt das passende Paket, öffnet die Firewall fürs iPhone und startet REKORD:

```
curl -fsSL https://github.com/KimJongUnNK/rekord/releases/latest/download/install.sh | sh
```

Oder von Hand – alle Dateien liegen auf der [Release-Seite](https://github.com/KimJongUnNK/rekord/releases/latest):

| Distro | Befehl |
|---|---|
| **Jede** (AppImage) | `chmod +x REKORD-*.AppImage && ./REKORD-*.AppImage` |
| Debian, Ubuntu, Mint, Pop!_OS | `sudo apt install ./rekord_*_amd64.deb` |
| Fedora, RHEL/Alma/Rocky 9 | `sudo dnf install ./rekord-*.x86_64.rpm` |
| openSUSE | `sudo zypper in --allow-unsigned-rpm ./rekord-*.x86_64.rpm` |
| Arch, Manjaro, EndeavourOS | `sudo pacman -U rekord-*.pkg.tar.zst` |
| Ohne root | `tar xzf REKORD-*-Linux-x86_64.tar.gz && ./rekord-*/install.sh` |

REKORD öffnet unter Linux sein eigenes Fenster (X11 und Wayland). Fehlt dem System etwas dafür – z. B. auf einem Server ohne Bildschirm –, öffnet sich die bisherige Ansicht im Browser. Die Pakete (deb, rpm, pacman) geben die Firewall-Ports fürs iPhone selbst frei.
Mit AppImage oder tar.gz: *Einstellungen → iPhone & Geräte* → **Für iPhone freigeben** (fragt nach deinem Passwort). Von Hand:
- Fedora, openSUSE, RHEL: `sudo firewall-cmd --permanent --add-port=8765/tcp && sudo firewall-cmd --reload`
- Ubuntu, Mint: `sudo ufw allow 8765/tcp`
