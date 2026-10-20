## REKORD – lokaler KI-Rekorder mit Live-Sprechererkennung

**Downloads**
| Datei | Für |
|---|---|
| `REKORD-Windows-x64.zip` | Windows 10/11 – entpacken, `REKORD.exe` starten |
| `REKORD-macOS-AppleSilicon.zip` | Mac mit Apple-Chip (M1 und neuer) |
| `REKORD-<ver>-x86_64.AppImage` | **Linux, jede Distro**: `chmod +x` und starten |
| `rekord_<ver>_amd64.deb` | Debian, Ubuntu, Mint, Pop!_OS: `sudo apt install ./rekord_*.deb` |
| `rekord-<ver>-1.x86_64.rpm` | Fedora, openSUSE, RHEL/Alma/Rocky 9: `sudo dnf install ./rekord-*.rpm` |
| `rekord-<ver>-1-x86_64.pkg.tar.zst` | Arch, Manjaro, EndeavourOS: `sudo pacman -U rekord-*.pkg.tar.zst` |
| `REKORD-<ver>-Linux-x86_64.tar.gz` | Linux ohne root: entpacken, `./install.sh` |
| `PKGBUILD` | Arch/AUR (`rekord-bin`): `makepkg -si` |
| `install.sh` / `install.ps1` | Installation in einer Zeile (siehe oben) |
| `REKORD-iOS-unsigned.ipa` | iPhone-App – mit Xcode, [Sideloadly](https://sideloadly.io) oder AltStore und deiner Apple-ID installieren |

**Am schnellsten:** Mac/Linux `curl -fsSL https://github.com/KimJongUnNK/rekord/releases/latest/download/install.sh | sh` · Windows (PowerShell) `irm https://github.com/KimJongUnNK/rekord/releases/latest/download/install.ps1 | iex`

**Installieren:** **[Schritt-für-Schritt-Anleitung für Mac, Windows, iPhone und Linux](https://github.com/KimJongUnNK/rekord/blob/main/docs/ANLEITUNG.md)**. Erster Start: einmalig ~700 MB Sprachmodelle, danach offline.
Die Apps sind nicht signiert. Wie du sie beim ersten Mal öffnest, steht in der Anleitung.

### Neu in 1.0.10 – lokale KI: das beste Modell für deinen Computer
- **REKORD erkennt deinen Computer** (Arbeitsspeicher + Apple-Chip oder NVIDIA-Grafik) und wählt das stärkste lokale Modell, das darauf flott läuft – z. B. *qwen3:14b* bei 24 GB mit Apple-Chip, *qwen3:30b* ab 32 GB. Vorher war bei 8b Schluss.
- *Einstellungen → KI → Lokal*: **Bestes Modell laden & verwenden** mit einem Klick (schaltet nach dem Download automatisch um).
- **Jedes Modell verwenden oder löschen**: klare Knöpfe *Verwenden* und *🗑 Löschen* bei jedem geladenen Modell, dazu **Alle nicht verwendeten löschen** (zeigt, wie viel Platz frei wird).
- **Anderes Modell**: jeden Namen aus der Ollama-Bibliothek eintippen (z. B. *llama3.1:8b*) → *Laden & verwenden*. Mehr Modelle zur Auswahl (bis *qwen3:32b*), zu große sind markiert („läuft hier nur langsam“).

### Neu in 1.0.9 – Uni-Modus, Stimmen frei lernen, einfache Kopplung
- **Stimme lernen – drei Wege:** **Text vorlesen** (wie bisher), **Einfach reden lassen** (die Person redet über irgendwas – oder du lässt jemanden reden, der sowieso spricht, z. B. den Prof; kurze Zwischenrufe anderer lässt REKORD weg) oder **Aus Aufnahme lernen** (Stimme aus einer fertigen Aufnahme anhören und auswählen). Gezählt werden nur Sekunden, in denen wirklich gesprochen wird. Überall: Einführung, Personen, „Wer ist dabei?“, iPhone-App.
- **Vorlesung** als dritte Meeting-Art (Computer und iPhone): Mitzählen entfällt. REKORD erkennt die vortragende Person (bekannt mit Namen, sonst „Vortragende Person“) und sammelt alle anderen unter „Publikum“. Danach automatisch ein **Lernzettel**: Kernaussagen, Definitionen, Prüfungsrelevantes, Fragen aus dem Hörsaal, Prüfungsfragen.
- **Koppeln mit 6 Ziffern** (z. B. `482 913`) statt langem Code: gilt 10 Minuten, das iPhone bekommt dabei einen eigenen Schlüssel. 5 falsche Versuche → 1 Minute Pause. Geräte einzeln trennen oder **Alle Geräte trennen**. Der QR-Code geht weiter.
- **iPhone nur noch als App:** Die Web-Version fürs Handy (Browser, Zertifikat, Einrichtungsseite) ist raus. Im WLAN spricht nur die gekoppelte iPhone-App mit REKORD – die Oberfläche gibt es nur am Computer. Dadurch auch kein zweiter Port (8766) mehr.

### Neu in 1.0.8 – Online-Meetings und echte Updates
- **Vor Ort oder Online:** Vor jeder Aufnahme fragt *„Wer ist dabei?“* auch, wo das Meeting stattfindet. **Online** (Teams, Zoom, Meet …) nimmt am Computer zusätzlich den **Ton des Calls** auf – also die Stimmen der anderen, direkt aus dem Lautsprecher-Signal, auch wenn Teams oder Zoom als App läuft und du Kopfhörer trägst. Nur Ton, kein Bild. Windows und Linux ohne Rückfrage; am Mac fragt macOS einmal nach *Bildschirm- & Systemaudioaufnahme* (macOS 13+). Klappt der Call-Ton nicht, läuft die Aufnahme mit dem Mikrofon weiter und REKORD sagt warum.
- **Updates mit einem Klick, die wirklich ersetzen:** *Einstellungen → Version & Updates → Jetzt aktualisieren* lädt die neue Version, **ersetzt** die installierte App am selben Ort und startet neu – Aufnahmen, Personen und Einstellungen bleiben. Links erscheint *„Update auf … →“*, sobald es etwas Neues gibt. Läuft eine Aufnahme, wartet das Update.
- **Nie mehr zwei REKORDs:** Startest du eine neuere Version, während die alte läuft, beendet sich die alte und die neue übernimmt (nimmt die alte gerade auf: direkt danach). REKORD zweimal öffnen holt das offene Fenster nach vorne. Eine alte Kopie (alte Verknüpfung, *Downloads*) startet stattdessen die neueste installierte Version; *Mit dem Computer starten* zeigt immer auf die neueste.
- **Installations-Zeile** (`install.sh` / `install.ps1`) beendet jetzt zuerst jedes laufende REKORD – auch alte Kopien – und bricht ab, statt eine laufende Aufnahme abzuschneiden.
- **Behoben (Windows):** Per Doppelklick gestartet blieb das Fenster leer – ohne Konsole stürzte der interne Server beim Start ab. Jetzt startet er immer; Meldungen landen in `rekord.log` (siehe Anleitung → *Wenn was nicht klappt*).
- **Mac:** Nach diesem Update fragt macOS evtl. einmal neu nach Mikrofon bzw. Systemaudio – erlauben.
- **Einmalig beim Wechsel von 1.0.7:** Die alte Version kennt das neue Update noch nicht. Am einfachsten die Installations-Zeile nochmal ausführen oder alle REKORD-Fenster schließen und die neue Version öffnen. Ab 1.0.8 geht alles in der App.

### Neu in 1.0.7 – Einführung, Hilfe, richtige Stimmen
- **Einführung beim ersten Start:** Speicherort → Aussehen → Sprache → Mikrofon → KI → deine Stimme → iPhone. Alles überspringbar, jederzeit wiederholbar (*Einstellungen → Hilfe → Einführung starten*).
- **ⓘ an jedem Punkt:** Neben jeder Einstellung und jedem Begriff erklärt ein ⓘ, was er macht – Maus drüber oder antippen.
- **Speicherort frei wählbar:** eingebauter Speicher, externe Festplatte, zweite SSD (NVMe) oder Netzlaufwerk (NAS) – getrennt für Daten und KI-Modelle. Beim ersten Start wird gefragt, **bevor** etwas heruntergeladen wird. Umziehen später mit Fortschritt; fehlt ein Laufwerk beim Start, sagt REKORD Bescheid statt einen leeren Ordner anzulegen.
- **„Wer ist dabei?“ vor jeder Aufnahme:** Wie viele sprechen (dich mitgezählt) und wer ist schon bekannt. Ohne Angabe startet keine Aufnahme. REKORD trennt dann genau so viele Stimmen – auch wenn noch niemand bekannt ist.
- **Keine „Sprecher 1, 2, 3“ mehr:** Stimmen, die REKORD nicht kennt, landen gesammelt unter **„Nicht erkannte Stimme“** – transkribiert wird trotzdem alles.
- **„Wer ist das?“ nach der Aufnahme:** Pro unbekannter Stimme anhören, Namen eingeben, *Merken* – ab dann erkannt. Stellt sich jemand vor („Hier ist Emil“), steht der Name schon drin. Im Transkript ordnet **„Wer sagt das?“** einen Satz – oder alle Sätze dieser Stimme – einer Person zu.
- **Einsprechen mit eigenem Text pro Person:** ca. 45 Sekunden, mindestens 25. REKORD prüft, ob wirklich nur eine Stimme zu hören ist, lässt Husten und Geräusche weg und zeigt die Qualität an. Auch in der iPhone-App.
- **Lokale KI-Modelle löschen:** *Einstellungen → KI → Lokal* → **Löschen** neben jedem geladenen Modell.
- **Behoben:** Das App-Fenster hat Aussehen, Mikrofon und Teilnehmer bei jedem Start vergessen.

### Neu in 1.0.6
- **Sprecher-Erkennung:** Wird eine Person versehentlich als zwei Sprecher erkannt, führt REKORD die beiden jetzt automatisch zusammen (nur wenn die Stimmabdrücke eindeutig dieselbe Person sind und die Sprecherzahl nicht fest eingestellt ist).
- Die Ende-zu-Ende-Tests laufen jetzt mit immer gleichen Test-Stimmen – kein Zufall mehr in der Qualitätskontrolle.

### Neu in 1.0.5 – alles mit einem Klick
- **Lokale KI in einem Klick:** *Lokal einrichten* installiert Ollama selbst (Mac, Windows, Linux – ohne Website, ohne Terminal), lädt das Modell, das zu deinem Arbeitsspeicher passt, und schaltet es ein. Mit Fortschrittsanzeige.
- **Erster Start:** Die Karte *„Noch ein Schritt“* fragt einmal: Lokal, Claude, ChatGPT oder ohne KI. Ist schon Ollama oder LM Studio mit einem Modell da, nimmt REKORD das automatisch.
- **Claude & ChatGPT:** Knopf *Key erstellen ↗* führt direkt zur richtigen Seite. Nach dem Einfügen testet REKORD sofort; bei ChatGPT wählt es das Modell selbst.
- **Claude Desktop & Claude Code:** *Mit Claude Desktop verbinden* trägt REKORD in Claudes Konfiguration ein (bestehende Einträge bleiben), *Claude neu starten* erledigt den Rest. Claude Code genauso.
- **iPhone: Aufnehmen im Browser** – ohne Sideloadly. Der rechte QR-Code öffnet eine Einrichtungs-Seite, die in 2 Minuten ein Zertifikat für die sichere Verbindung installiert. Danach Live-Aufnahme mit Sprecher-Erkennung direkt in Safari. Das Zertifikat gilt nur für Adressen im eigenen Netz.
- **Installation in einer Zeile** für Mac, Linux (`install.sh`) und Windows (`install.ps1`): ohne Gatekeeper-/SmartScreen-Umweg, mit Startmenü- und Desktop-Eintrag. Dieselbe Zeile macht Updates.
- **Windows:** Der Startmenü-Eintrag wird beim ersten Start automatisch angelegt.
- **Linux:** Die Pakete öffnen die Firewall-Ports fürs iPhone selbst; für AppImage/tar.gz gibt es *Für iPhone freigeben*.
- **Mit dem Computer starten:** REKORD läuft auf Wunsch ab dem Einschalten im Hintergrund, damit sich das iPhone jederzeit verbinden kann.
- **Behoben:** Bei der ersten Live-Aufnahme nach dem Start gingen die ersten Sekunden verloren, während die Modelle luden. Jetzt wird zwischengespeichert, und die Modelle werden schon beim Start vorgeladen.

### Neu in 1.0.4
- **Lokale KI ohne Terminal:** Unter *Einstellungen → KI → Lokal* erkennt REKORD Ollama und startet es bei Bedarf. Deine vorhandenen Modelle sind antippbar, neue lädst du per **Laden**-Knopf mit Fortschrittsbalken. Das erste geladene Modell wird automatisch verwendet.
- Denk-Text lokaler Modelle (`<think>…</think>`) landet nicht mehr in Zusammenfassungen.
- **Behoben:** Die Pegel-Anzeige blieb nach dem Sprechen auf dem Höchstwert hängen. Jetzt misst sie in dB und fällt sauber zurück.

### Neu in 1.0.3
- **Behoben (Linux):** Der Modell-Download schlug auf Fedora, Arch und openSUSE mit einem SSL-Fehler fehl. REKORD bringt jetzt seine eigene Zertifikatsliste mit.
- **Behoben (Linux):** Das Öffnen des Browsers ist unter KDE abgestürzt (`kde-open`, falsche Systembibliotheken).
- Die Release-Tests machen jetzt auf jeder Distro einen echten HTTPS-Download.

### Neu in 1.0.2
- **Neue Anleitung** ([docs/ANLEITUNG.md](https://github.com/KimJongUnNK/rekord/blob/main/docs/ANLEITUNG.md)): Installation pro Plattform, die iPhone-Wege im Vergleich, KI verbinden und jeder Menüpunkt erklärt. Ein Test sorgt dafür, dass sie jeden Knopf der App abdeckt.
- **Behoben:** *Einstellungen → Claude Desktop (MCP)* zeigte in der fertigen Mac/Windows/Linux-App einen Befehl, der dort nicht funktioniert.
- **Behoben:** *Vorlagen* war am Handy nicht erreichbar. Die untere Leiste zeigt jetzt alle 6 Punkte, plus Link *Vorlagen verwalten* bei der Zusammenfassung.
- Texte in der App und in der iPhone-App passen jetzt zur Anleitung (keine Hinweise mehr auf Terminal-Optionen).

### Neu in 1.0.1
- **Linux für alle Distros:** AppImage, .deb, .rpm, Arch-Paket, tar.gz und AUR-PKGBUILD. Jedes Release wird automatisch auf Debian, Ubuntu, Fedora, openSUSE und Arch installiert und gestartet.
- Ein zweiter Klick aufs App-Icon öffnet das laufende REKORD, statt einen zweiten Server zu starten. Gibt es kein natives Fenster, öffnet sich der Browser. Neuer Knopf *Einstellungen → REKORD beenden*.
- Die Desktop-App versteht CLI-Befehle, z. B. `rekord mcp` für Claude Code.
- **Behoben:** Wer eine falsch erkannte Person korrigiert hat (z. B. „Lisa" → „Anna"), hat damit Lisas Stimmprofil überschrieben. Jetzt bekommt Anna ein eigenes Profil, Lisa bleibt unverändert.
- **Behoben:** Claude Desktop / Claude Code (MCP) startete mit dem aktuellen MCP-SDK 2.x nicht. Läuft jetzt mit 1.x und 2.x.
- **Behoben:** Eine per Drag & Drop importierte Datei wurde mehrfach hochgeladen, wenn man vorher zwischen Ansichten gewechselt hatte.
- **Behoben:** Ein Klick auf einen Zeitstempel konnte die Wiedergabe einer vorher geöffneten Aufnahme auslösen.
- **Behoben:** Gleichzeitige Modell-Downloads (Erststart + Import) konnten sich gegenseitig die Datei zerschießen.
- Ohne eingerichtete KI gibt's keine fehlschlagenden Auto-Zusammenfassungen mehr, stattdessen einen klaren Hinweis „KI verbinden".
- Live-Modus: Stimmen benennen ist jetzt thread-sicher gegen die laufende Erkennung.
- Claude: kein leerer Beta-Header mehr, wenn das Ausweichmodell aus ist.
- Sicherheit: Kopplungs-Code wird timing-sicher verglichen, Farbwerte werden geprüft.
- Pipeline: GitHub Actions auf Node 24.

### Version 1.0.0
Live „Wer spricht", Personen-Wiedererkennung, Teilnehmer-Auswahl, Vorstellungsrunde, Claude/ChatGPT/Ollama, Mind Map, Lockscreen-Widgets & Live Activity – siehe README.
