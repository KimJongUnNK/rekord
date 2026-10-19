# REKORD einrichten

**So funktioniert's:** REKORD läuft auf deinem **Computer** (Mac oder Windows). Dort wird aufgenommen, transkribiert und erkannt, wer spricht.
Das **iPhone ist optional**: Es verbindet sich übers WLAN mit dem Computer.

⏱ ca. 5 Minuten · einmalig ~700 MB Download · danach läuft alles offline

> **Beim ersten Start führt dich REKORD durch alles:** Speicherort → Aussehen → Sprache → Mikrofon → KI → deine Stimme → iPhone. Siehe [Erster Start](#erster-start-die-einführung).
> Überall, wo ein kleines **ⓘ** steht: Maus drüber (am Handy antippen) – dort steht, was der Punkt macht.
>
> **Was REKORD selbst erledigt:** Sprachmodelle laden · lokale KI (Ollama) installieren und das passende Modell wählen ·
> vorhandene KI erkennen (Ollama, LM Studio) · Modell für ChatGPT wählen · Claude Desktop/Claude Code verbinden ·
> Startmenü-Eintrag (Windows) · Firewall freigeben (Linux) · Zertifikat fürs Aufnehmen im Handy-Browser.
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

REKORD landet in **Programme** und startet sofort. Keine Sicherheitswarnung, kein Freischalten. Dieselbe Zeile macht später Updates.

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

REKORD wird installiert (ohne Admin), bekommt einen Eintrag im **Startmenü** und auf dem **Desktop** und startet. Kein blaues Warnfenster. Dieselbe Zeile macht später Updates.

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

> **Voraussetzung:** REKORD ist am Computer offen und beide sind im **selben WLAN**.

**Welcher Weg?**

| | **A · Web-App** | **B · iPhone-App** |
|---|:---:|:---:|
| Einrichten | 2 Minuten | ca. 15 Minuten |
| Aufnahmen ansehen, anhören, Fragen stellen | ✓ | ✓ |
| **Mit dem iPhone aufnehmen** + live sehen, wer spricht | ✓ | ✓ |
| Aufnahme läuft bei gesperrtem Bildschirm weiter | – | ✓ |
| Sperrbildschirm-Widget, Dynamic Island | – | ✓ |
| Du brauchst | nichts | Kabel + Computer + Apple-ID |

### Weg A · Web-App

1. Am Computer in REKORD: **Einstellungen** → **iPhone & Geräte**.
2. iPhone-Kamera auf den **rechten** QR-Code („Im Browser“) halten → Link öffnen.
3. Die Seite **„REKORD aufs Handy“** führt dich durch drei kurze Schritte – fürs Aufnehmen braucht Safari eine sichere Verbindung:
   - **Zertifikat laden** → **Erlauben**
   - App **Einstellungen** → ganz oben **Profil geladen** → **Installieren**
   - **Einstellungen** → **Allgemein** → **Info** → ganz unten **Zertifikatsvertrauenseinstellungen** → **REKORD Heimnetz** einschalten
4. Zurück in Safari wird Schritt 4 grün → **REKORD öffnen** → **Teilen** → **Zum Home-Bildschirm** → **Hinzufügen**.

**Warum ein Zertifikat?** Browser geben das Mikrofon nur über verschlüsselte Verbindungen frei. Das Zertifikat erzeugt REKORD auf deinem Computer; es gilt nur für Adressen im eigenen Netz und kann keine echten Websites betreffen. Nur ansehen ohne Aufnahme geht auch ohne: auf der Seite **„Ohne Zertifikat“** antippen.
Bildschirm beim Aufnehmen anlassen (REKORD hält ihn wach) – für Aufnahmen mit gesperrtem iPhone ist Weg B da.

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

## Erster Start: die Einführung

Beim ersten Öffnen erscheint die Einführung. Jeder Schritt lässt sich **Überspringen** und später in den Einstellungen ändern;
*Einstellungen → Speicher & Datenschutz → Hilfe → Einführung starten* zeigt sie nochmal.

| Schritt | Was passiert |
|---|---|
| **Willkommen** | Was REKORD kann, in drei Sätzen. |
| **Speicherort** | **Wo soll REKORD speichern?** Laufwerk antippen – eingebaut, externe Festplatte (USB/Thunderbolt), zweite SSD (NVMe) oder Netzlaufwerk (NAS) – oder einen Ordner eintragen. *KI-Modelle im selben Ordner* abwählen, um die großen Modelle woanders hinzulegen. Erst danach lädt REKORD etwas herunter. Liegt der Ort woanders, zieht REKORD kurz um und startet neu. |
| **Aussehen** | Hell/Dunkel, Akzentfarbe, Dichte – du siehst es sofort. |
| **Sprache** | **Sprache in den Meetings** (fest eingestellt = am genauesten, *Automatisch* für gemischte Runden) und **Protokolle schreiben auf** (Deutsch, Englisch oder wie im Gespräch). Bei Englisch bekommt man zum Einsprechen auch einen englischen Text. |
| **Mikrofon** | Mikrofon wählen, etwas sagen – der Balken muss ausschlagen. |
| **KI** | **Lokal · gratis** (ein Klick, läuft im Hintergrund weiter), **Claude** oder **ChatGPT** (Key einfügen, wird sofort getestet) oder *Erstmal ohne*. |
| **Deine Stimme** | Namen eingeben → **Jetzt einsprechen** → deinen Text vorlesen (siehe unten). Ab dann steht in jedem Meeting dein Name. |
| **iPhone** | QR-Code mit dem iPhone scannen (siehe [Weg A](#weg-a--web-app)). |
| **Fertig** | Übersicht, was eingerichtet ist · **Erste Aufnahme** oder **Zur App**. |

**Einsprechen – jede Person liest ihren eigenen Text.** REKORD erstellt für jeden Namen einen eigenen Text (ca. 45 Sekunden, mit Zahlen, Fragen,
unterschiedlichen Lauten). Mindestens 25 Sekunden, bis zum Ende ist besser. *Anderer Text* tauscht ihn aus. Danach **Stimme speichern**:
REKORD prüft, ob wirklich nur eine Stimme zu hören war, und zeigt die Qualität an. Klingt die Probe nach mehreren Leuten oder viel Lärm, bittet es um eine neue.

---

## 4. KI verbinden

Transkript und Sprecher-Erkennung gehen **ohne KI**. Für Protokoll, To-dos, Mind Map und Fragen brauchst du eine.
Beim ersten Start zeigt REKORD unter *Aufnahmen* die Karte **„Noch ein Schritt“** – dort einfach antippen. Später: **Einstellungen → KI**.
Ist auf dem Computer schon Ollama oder LM Studio mit einem Modell, nimmt REKORD das automatisch.

| | So geht's | Kosten |
|---|---|---|
| **Lokal · gratis** | **Lokal einrichten** antippen. REKORD installiert Ollama selbst, lädt das Modell, das zu deinem Arbeitsspeicher passt, und verwendet es. Fortschritt wird angezeigt, du kannst nebenbei weiterarbeiten. | **gratis**, nichts verlässt den Computer. *qwen3:8b* ab 16 GB RAM, *qwen3:4b* ab 8 GB. |
| **Claude** | **Key erstellen ↗** → bei Anthropic anmelden → *Create Key* → Key kopieren → ins Feld einfügen. REKORD testet sofort. | pro Nutzung, meist Cent-Beträge pro Meeting |
| **ChatGPT** | **Key erstellen ↗** → *Create new secret key* → kopieren → einfügen. Das Modell wählt REKORD selbst, getestet wird sofort. | pro Nutzung. Das ChatGPT-Plus-Abo zählt **nicht**. |

**Mit deinem Claude-Abo statt API-Key (Claude Desktop):**
REKORD → *Einstellungen → Claude Desktop (MCP)* → **Mit Claude Desktop verbinden** → **Claude neu starten**.
Danach kannst du Claude direkt fragen: *„Was haben wir im letzten Meeting entschieden?“* Für Claude im Terminal: **Mit Claude Code verbinden**.

---

## 5. Erste Aufnahme

1. **Leute einmal anlernen:** *Personen* → **Person einsprechen** → den eigenen Text vorlesen (ca. 45 s). Ab dann erkennt REKORD die Person mit Namen.
2. **Roter Knopf** → REKORD fragt **„Wer ist dabei?“** – das ist Pflicht, sonst startet keine Aufnahme:
   - **Wie viele sprechen?** – dich mitgezählt (Zahl antippen oder **−/+**).
   - **Wer davon ist bekannt?** – die Leute antippen, die REKORD schon kennt.
   - Alle anderen zählen als neu. Am besten gleich **„… jetzt einsprechen“** – jede neue Person liest ihren Text, dann ist sie ab sofort bekannt.
   - **Aufnahme starten**.
3. Während der Aufnahme siehst du, wer spricht. Stimmen, die REKORD nicht kennt, heißen **„Nicht erkannte Stimme“** – nie „Sprecher 1, 2, 3“. Transkribiert wird trotzdem alles.
4. **Stopp:** Ein paar Minuten später ist das Protokoll fertig. Gab es unbekannte Stimmen, fragt REKORD oben **„Wer ist das?“**: anhören (▶), Namen eingeben, **Merken** – ab der nächsten Aufnahme werden sie erkannt.
   Hat sich jemand vorgestellt („Hier ist Emil …“), steht der Name schon drin.

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
- **Importieren:** Audio- oder Videodateien wählen oder einfach ins Fenster ziehen (Sprachmemos, Zoom, Diktiergerät).
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
| **Export** | Markdown, Word, Text, Untertitel als SRT oder WebVTT, JSON, Zwischenablage, PDF (übers Drucken), Original-Audio |

  - **„…“ oben rechts:** *Neu verarbeiten* (z. B. nach Modellwechsel) · *Personen neu erkennen* (nach dem Anlernen neuer Leute) · *Umbenennen* · *Löschen*

### Live
- Am Handy im Browser steht beim ersten Mal **„Für Aufnahmen im Handy-Browser fehlt noch ein Schritt“** → **Jetzt einrichten** (siehe [Weg A](#weg-a--web-app)).
- Oben: **Mikrofon** oder **Mikro + Call-Ton**. Mit Call-Ton nimmst du am Computer auch Zoom, Teams oder Meet mit auf (Chrome/Edge).
- **Titel** eingeben (optional).
- **Wer ist dabei?** Die Karte zeigt, wer angekündigt ist; **Festlegen** ändert es. **Vorstellungsrunde** lässt eine neue Person ihren Text einsprechen.
- **Roter Knopf** (oder **Leertaste**) → zuerst **Wer ist dabei?** (Anzahl + Bekannte, siehe [Erste Aufnahme](#5-erste-aufnahme)), dann läuft die Aufnahme. Nochmal drücken stoppt · **★** (oder Taste **H**) markiert einen wichtigen Moment · **Pause**.
- Mitte: **wer gerade spricht**, groß und in der Farbe der Person.
- Rechts *Im Raum*: alle Stimmen mit Redeanteil. Unbekannte stehen gesammelt als **Nicht erkannte Stimme** – antippen → Namen eingeben → die zuletzt gehörte Stimme ist ab sofort erkannt.
- *Mitschrift*: das Transkript, live.

### Fragen
Ein Chat über **alle** Aufnahmen: *„Was hat Lisa letzte Woche zum Budget gesagt?“* Die Antworten haben anklickbare Quellen, die direkt an die Stelle in der Aufnahme springen. **Verlauf leeren** oben rechts.

### Personen
- **Person einsprechen:** Namen eingeben → REKORD zeigt den Text für diese Person (*Anderer Text* tauscht ihn) → **Aufnahme starten** → vorlesen (mind. 25 s, ideal ~45 s) → **Stimme speichern**. Oder eine Datei mit nur dieser Person wählen.
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
| **KI** | Anbieter wählen: Claude, ChatGPT, Lokal, Kompatibel, Aus · Lokal: **Lokales Modell** – **Lokal einrichten** (installiert alles), danach Modelle per *Laden* holen, deine Modelle antippen zum Verwenden, **Löschen** entfernt ein geladenes Modell (war es aktiv, springt REKORD auf ein anderes) · Claude/ChatGPT: **Key erstellen ↗** · **API-Key** · **Modell** (*Laden* holt die Liste) · Claude: **Denkaufwand**, **Ausweichmodell** · Lokal/Kompatibel: **Ollama-Adresse** bzw. **Server-Adresse**, **Kontextlänge** · **Verbindung** → *Testen* · **Sprache der Zusammenfassungen** · **Automatisch zusammenfassen** + Standard-Vorlage |
| **Transkription** | **Sprache** (fest eingestellt = genauer, *Automatisch* für gemischte Meetings) · **Engine** · **Modell** (*small* = Standard, *turbo* = beste Qualität) · **CPU-Threads** · **Vokabular** für Namen, die falsch erkannt werden |
| **Sprecher-Erkennung** | **Personen-Erkennung (Aufnahmen)** und **Personen-Erkennung (live)**: wie streng (höher = weniger Verwechslungen) · **Sprecher trennen**: erscheint eine Person doppelt, runterdrehen · **Anzahl Sprecher**: wenn bekannt, fest einstellen · **Stimmabdruck-Modell** |
| **Modelle** | Sprachmodelle *Laden* oder *Entfernen* |
| **iPhone & Geräte** | **QR-Codes** (links iPhone-App, rechts Browser) · **Adresse** · **Kopplungs-Code** *Neu erzeugen* (trennt alle gekoppelten Geräte) · Linux: **Firewall** → *Für iPhone freigeben*, falls sie das iPhone blockiert |
| **Claude Desktop (MCP)** | **Claude Desktop**: *Mit Claude Desktop verbinden*, danach *Claude neu starten* · **Claude Code**: *Mit Claude Code verbinden* · *Von Hand eintragen*: Konfiguration zum **Kopieren** |
| **Speicher & Datenschutz** | **Speicherort**: wo Aufnahmen, Datenbank und Stimmabdrücke liegen – *Ändern …* → Laufwerk wählen (eingebaut, extern, NVMe, NAS) → **Umziehen**; REKORD kopiert alles, startet neu, der alte Ordner bleibt als Sicherheitskopie · **KI-Modelle**: wo Sprachmodelle und lokale KI liegen – eigenes Laufwerk möglich, *Ändern …* nimmt vorhandene Modelle mit · **Eingangsordner**: Dateien, die hier landen, werden automatisch verarbeitet · **Was verlässt das Gerät?** · **Mit dem Computer starten**: REKORD läuft ab dem Einschalten im Hintergrund, das iPhone kann sich jederzeit verbinden · **Hilfe**: *Einführung starten*, *Anleitung ↗* · **Version** · **Beenden** → *REKORD beenden* |

**In der iPhone-App** gibt's die Reiter *Live*, *Aufnahmen*, *Personen* und *Einstellungen* (Theme, Akzentfarbe, Mikrofon, KI, Hub). *Fragen über alle* und *Vorlagen* laufen über die Web-App oder den Computer.
Auch dort fragt der rote Knopf zuerst **Wer ist dabei?**. Starts über Sperrbildschirm-Widget, Kontrollzentrum oder Action Button nehmen die zuletzt bestätigte Runde.

---

## Wenn was nicht klappt

| Problem | Lösung |
|---|---|
| **Mac:** *„REKORD ist beschädigt“* | Terminal öffnen, `xattr -dr com.apple.quarantine /Applications/REKORD.app` eingeben, REKORD nochmal öffnen |
| **Kein Mikrofon im App-Fenster** | Im Browser **http://localhost:8765** öffnen, dort geht's immer. Mac: *Systemeinstellungen → Datenschutz & Sicherheit → Mikrofon* → REKORD an |
| **iPhone findet den Computer nicht** | Gleiches WLAN? (Gäste-WLANs trennen Geräte.) Ist REKORD am Computer offen? (Tipp: *Speicher & Datenschutz* → **Mit dem Computer starten**.) Windows: Firewall „Private Netzwerke“ erlaubt? Linux: *iPhone & Geräte* → **Für iPhone freigeben** |
| **Im Handy-Browser geht Aufnehmen nicht** | Schritt 3 vergessen? *Einstellungen → Allgemein → Info → Zertifikatsvertrauenseinstellungen* → **REKORD Heimnetz** an. Neues WLAN am Computer? Einfach den rechten QR-Code nochmal scannen. |
| **Lokal einrichten hängt oder bricht ab** | Internet prüfen, nochmal **Lokal einrichten** – fertige Teile werden nicht neu geladen. |
| **„Modelle werden geladen“ geht nicht weiter** | Internet prüfen → *Einstellungen → Modelle* → **Laden** |
| **Zusammenfassung zeigt Fehler** | *Einstellungen → KI* → **Testen**. Key richtig kopiert? Guthaben auf dem API-Konto? |
| **Claude Desktop sieht REKORD nicht** | Claude ganz beenden und neu öffnen (*Claude neu starten*). Steht unter *Claude Desktop (MCP)* **Verbunden**? |
| **Falsche Person erkannt** | Im Transkript auf den Namen tippen → richtigen Namen eingeben, *Stimme merken* bleibt an |
| **REKORD beenden** | Fenster schließen. Läuft es im Browser: *Einstellungen* → ganz unten **REKORD beenden** |
| **Backup** | Den **Speicherort**-Ordner kopieren (steht unter *Einstellungen → Speicher & Datenschutz*). Da liegt alles drin. |
| **„Laufwerk fehlt“ beim Start** | Der Speicherort liegt auf einer Festplatte oder einem Netzlaufwerk, das gerade nicht verbunden ist. Anschließen → **Nochmal prüfen**. Kommt es nicht mehr zurück: **Neu auf diesem Computer anfangen** (die Daten auf dem Laufwerk bleiben unberührt). |
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
| openSUSE | `sudo zypper in ./rekord-*.x86_64.rpm` |
| Arch, Manjaro, EndeavourOS | `sudo pacman -U rekord-*.pkg.tar.zst` |
| Ohne root | `tar xzf REKORD-*-Linux-x86_64.tar.gz && ./rekord-*/install.sh` |

REKORD öffnet sich unter Linux im Browser. Die Pakete (deb, rpm, pacman) geben die Firewall-Ports fürs iPhone selbst frei.
Mit AppImage oder tar.gz: *Einstellungen → iPhone & Geräte* → **Für iPhone freigeben** (fragt nach deinem Passwort). Von Hand:
- Fedora, openSUSE, RHEL: `sudo firewall-cmd --permanent --add-port=8765/tcp --add-port=8766/tcp && sudo firewall-cmd --reload`
- Ubuntu, Mint: `sudo ufw allow 8765/tcp && sudo ufw allow 8766/tcp`
