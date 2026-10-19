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
| `REKORD-iOS-unsigned.ipa` | iPhone – per [Sideloadly](https://sideloadly.io) oder AltStore mit deiner Apple-ID installieren |

**Installieren:** **[Schritt-für-Schritt-Anleitung für Mac, Windows, iPhone und Linux](https://github.com/KimJongUnNK/rekord/blob/main/docs/ANLEITUNG.md)**. Erster Start: einmalig ~700 MB Sprachmodelle, danach offline.
Die Apps sind nicht signiert. Wie du sie beim ersten Mal öffnest, steht in der Anleitung.

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
