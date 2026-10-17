## REKORD – lokaler KI-Rekorder mit Live-Sprechererkennung

**Downloads**
| Datei | Für |
|---|---|
| `REKORD-Windows-x64.zip` | Windows 10/11 – entpacken, `REKORD.exe` starten |
| `REKORD-macOS-AppleSilicon.zip` | Mac mit Apple-Chip (M1 und neuer) |
| `REKORD-iOS-unsigned.ipa` | iPhone – per [Sideloadly](https://sideloadly.io) oder AltStore mit deiner Apple-ID installieren |

**Erster Start:** lädt einmalig die Sprachmodelle (~700 MB). Danach läuft alles offline.
Das Programm ist im WLAN erreichbar (geschützt durch Kopplungs-Code), damit das iPhone sich verbinden kann.

**Warnungen beim Öffnen (Apps sind nicht signiert):**
- **Windows:** „Der Computer wurde durch Windows geschützt" → *Weitere Informationen* → *Trotzdem ausführen*. Firewall-Frage: *Privates Netzwerk* erlauben.
- **macOS:** Rechtsklick auf REKORD → *Öffnen* → *Öffnen*. Oder im Terminal: `xattr -dr com.apple.quarantine /Applications/REKORD.app`
- **iPhone:** nach dem Sideloaden *Einstellungen → Allgemein → VPN & Geräteverwaltung → deiner Apple-ID vertrauen*. Mit kostenloser Apple-ID 7 Tage gültig, Sideloadly erneuert automatisch.

### Neu in 1.0.1
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
