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

**Neu in dieser Version:** siehe README – Live „Wer spricht", Personen-Wiedererkennung, Teilnehmer-Auswahl, Vorstellungsrunde, Claude/ChatGPT/Ollama, Mind Map, Lockscreen-Widgets & Live Activity.
