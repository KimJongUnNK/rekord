# REKORD – alle Versionen

Was sich in welcher Version geändert hat, neueste zuerst. Die Downloads stehen immer unter [Releases](https://github.com/KimJongUnNK/rekord/releases/latest).

## 1.4.13 – KI-Verhalten in den Einstellungen · „Ändern“ klappt auch bei langen Vorlesungen · PDF ohne Transkript
- **Neu: Einstellungen → KI-Verhalten.** Länge (Kurz / Normal / Ausführlich), Ton (Direkt / Sachlich / Locker), Beispiele zu jedem Punkt, Emojis, Sprache, Zeitstempel und eigene Regeln – einmal eingestellt, gilt es für jede Zusammenfassung, jede Änderung und jede Antwort, mit Claude, ChatGPT und lokaler KI. Die KI bekommt alles als **einen** festen Block Regeln (nicht verteilt, nicht doppelt); darunter steht genau der Text, den sie liest. Was sich prüfen lässt, prüft REKORD danach selbst: keine Zeitstempel, keine Emojis (wenn aus), kein leeres „z. B.“.
- **Behoben: „Sag der KI, was sie ändern soll“ reagierte nicht** bei langen Aufnahmen mit lokaler KI. Die Anfrage gab nach 2 Minuten auf, während das Transkript noch verdichtet wurde. Jetzt mit Fortschrittsbalken („Teil 3 von 9 …“, „Die KI ändert die Zusammenfassung …“), ohne Zeitlimit, die neue Fassung erscheint beim Schreiben. Ändert die KI nichts oder gibt nichts zurück, steht das klar da.
- **Verdichtete Abschnitte langer Aufnahmen bleiben gespeichert** – auch nach einem Neustart fängt die nächste Änderung oder Frage nicht von vorn an.
- **Behoben: „z. B.,.“ ohne Beispiel** (z. B. bei „Prüfungsrelevant“). Ursache: Die KI schrieb „z. B. [12:34]“, der Zeitstempel wurde entfernt, „z. B.“ blieb übrig. Jetzt verschwindet ein leeres „z. B.“ mit, die Vorlage *Vorlesung / Lernzettel* verlangt bei „Prüfungsrelevant“ das konkrete Beispiel aus der Vorlesung, und die KI hat die Regel, nie Platzhalter stehen zu lassen.
- **PDF-Export: nur, was zusammengeschrieben wurde** – Zusammenfassungen, Mind Map, Notizen. Eine lange Vorlesung ist ein paar Seiten statt 45. Das ganze Transkript gibt's mit *Export → PDF: ganzes Transkript anhängen*. Gibt es noch keine Zusammenfassung, kommt das Transkript automatisch.
- **Leise Aufnahmen lauter – jetzt auch in der Live-Mitschrift**, mit Schalter unter *Einstellungen → Transkription* (Standard: an) und Anzeige im Fortschritt („Lautstärke angepasst: +12 dB“). Die Aufnahme selbst bleibt unverändert.

## 1.4.12 – PDF-Export im Dark Mode
- **Behoben: leere PDF-Seiten.** Mit REKORD im Dark Mode war der exportierte Text weiß – auf weißem Papier unsichtbar, nur die Fußzeile war zu sehen. Das PDF druckt jetzt immer schwarze Schrift auf weißem Papier, egal welches Design eingestellt ist.

## 1.4.11 – Kopieren und Bearbeiten wandern mit · Listen sauber nummeriert
- **Lange Zusammenfassungen:** Scrollst du über den Kopf einer Zusammenfassung hinaus, bleibt oben eine Leiste mit Titel, **Kopieren** und **Bearbeiten** stehen – bis die Zusammenfassung zu Ende ist. Kein Zurückscrollen mehr.
- **Behoben: Lernfragen hießen alle „1.“** und die Antwort-Punkte standen unterschiedlich weit eingerückt. Leerzeilen zwischen den Punkten beenden die Liste nicht mehr, Einrückung zählt nach Ebene (2, 3 oder 4 Leerzeichen = eine Ebene), eine Liste ab „5.“ bleibt bei 5, eingerückte Zeilen unter einem Punkt gehören zu ihm. To-dos haben nur noch das Kästchen, keinen Punkt daneben.

## 1.4.10 – Formeln lesbar · PDF-Export ohne Abschneiden
- **Formeln:** Die KI bekommt die Regel, Formeln als Formelschrift zu schreiben (`Gewinn = Umsatz − Kosten`, `x²`, `√a`, `Σ`, `≤`, `Δ`) – auch gesprochene Formeln („Umsatz minus Kosten ist der Gewinn“). Was trotzdem als LaTeX kommt (`$\frac{G}{K} \cdot 100$`, `x^{2}`, `\Delta K`, `K\ddot{a}ufe`), wandelt REKORD automatisch um: `G / K · 100`, `x²`, `ΔK`, `Käufe` – in neuen Zusammenfassungen, Antworten und KI-Änderungen beim Speichern, in älteren beim Anzeigen, beim Kopieren, im Word-, Markdown- und PDF-Export. Offline, ohne Zusatzprogramm. Geld („$5“), Dateinamen und Code bleiben unberührt. Die Vorlage *Vorlesung / Lernzettel* schreibt jede Formel in eine eigene Zeile und erklärt die Variablen.
- **PDF-Export neu:** Der Text wird am PDF selbst gemessen statt am Bildschirm – auf dem Mac liefen Zeilen über den rechten Rand und wurden abgeschnitten. Jetzt: feste Ränder, lange Wörter und Links brechen um, keine Zeile wird zwischen zwei Seiten geteilt, jeder Sprecherbeitrag ein eigener Absatz, Fußzeile mit Titel und „Seite n von N“, Titel nur einmal.

## 1.4.9 – Lange Aufnahmen mit lokaler KI: kein „timed out“ mehr · Fortschrittsbalken beim Zusammenfassen
- **Behoben: „Fehler: timed out“** bei langen Aufnahmen (z. B. 2 h 43 min Vorlesung) mit lokaler KI. Das Transkript passt nicht in den Kontext eines kleinen Modells und wird erst abschnittsweise verdichtet – die Abschnitte waren riesig, die Notizen unbegrenzt lang, und nach 10 Minuten ohne Antwort von Ollama brach REKORD ab. Jetzt: Abschnitte von höchstens ~8 000 Tokens, kurze Notizen (max. 1 500 Tokens je Abschnitt), Ollama darf bis zu 30 Minuten still rechnen (Modell von externer Festplatte laden, langer Prompt).
- **Fortschrittsbalken beim Zusammenfassen** (und bei der Mind Map): Balken mit Prozent und was gerade passiert – „Transkript wird vorbereitet“, bei langen Aufnahmen „Teil 3 von 9 wird verdichtet …“, „Die KI liest das Transkript …“, „Die KI schreibt …“. Der Balken läuft nur vorwärts und steht erst bei 100 %, wenn die Zusammenfassung wirklich fertig ist.
- **Verdichtete Abschnitte werden gemerkt:** ein zweiter Versuch, eine andere Vorlage oder eine Frage zur selben Aufnahme fängt nicht von vorn an.
- Bricht Ollama trotzdem ab, sagt REKORD warum und was hilft (nochmal versuchen – Abschnitte bleiben gemerkt – oder ein kleineres Modell).

## 1.4.8 – Zeitstempel nur, wenn du danach fragst
- **Zeitstempel** (*Einstellungen → KI*, Standard: **Nur wenn ich danach frage**): Antworten (eine Aufnahme und *Fragen* über alle), neue Zusammenfassungen und KI-Änderungen kommen ohne [mm:ss] und ohne Aufnahme-Links – auch wenn eine Vorlage welche verlangt. Fragst du „an welcher Stelle?“, „welche Minute?“, „mit Zeitstempel“ o. Ä., stehen sie drin. Weil kleine lokale Modelle Anweisungen gern überlesen, nimmt REKORD Zeitstempel zusätzlich selbst heraus, auch beim Live-Mitschreiben. *Immer* stellt das alte Verhalten her. Bestehende Zusammenfassungen bleiben, wie sie sind.

## 1.4.7 – Die KI kennt Dateinamen und Unterlagen · eigene Anweisungen an die KI
- **Dateinamen:** REKORD merkt sich die Original-Dateinamen jeder Aufnahme (Import, Reinziehen, Eingangsordner, Kommandozeile, Anhängen, Zusammenführen – live Aufgenommenes heißt wie die Aufnahme). Die KI bekommt bei jeder Frage und Zusammenfassung: Titel, ID, Datum, Dauer, Herkunft, Datei(en) in Reihenfolge, Ordner, Teilnehmer, Unterlagen mit Seitenzahl. „Wie heißt die Datei?“ beantwortet sie jetzt direkt – auch unter *Fragen* über alle Aufnahmen. Aufnahmen von vor 1.4.7 haben keinen gespeicherten Dateinamen.
- **Anweisungen an die KI** (*Einstellungen → KI*): eigene Regeln für Ton, Länge und Form – gelten für Fragen (eine Aufnahme und alle), Zusammenfassungen und „Sag der KI, was sie ändern soll“, mit lokaler KI genauso wie mit Claude oder ChatGPT. **Vorschlag einsetzen** füllt kurze, direkte Regeln ein (keine Einleitung, keine Emojis, Stichpunkte, nichts erfinden).

## 1.4.6 – Aufnahmen anhängen und zusammenführen, mehrere auf einmal
- **Aufnahmen anhängen wie Unterlagen:** In der Aufnahme oben rechts **Anhängen → Aufnahmen aus REKORD …**: Liste mit Suche, mehrere antippen → **N anhängen**. Sie kommen hinter die Aufnahme (älteste zuerst), alles wird zusammen neu transkribiert; Sterne, Notizen, Teilnehmer und Unterlagen kommen mit, die angehängten bleiben in der Liste. *Dateien vom Computer …* gibt es weiter (Mehrfachauswahl). Schnittstelle: `POST /api/recordings/{id}/append-recordings` mit `{ids}`.
- **Zusammenführen:** *Aufnahmen → Auswählen* → zwei oder mehr antippen → **N zusammenführen**. Eine neue Aufnahme entsteht: die Teile hintereinander (die älteste zuerst, 1 s Pause dazwischen), alles zusammen neu transkribiert, Sprecher über alle Teile. Sterne wandern an ihre Stelle, Notizen (mit Überschrift je Teil), Teilnehmer, Ordner und Unterlagen kommen mit. Der Titel: „VO Statistik Teil 1/2/3“ → „VO Statistik“, sonst „Erste + N weitere“. Die einzelnen Aufnahmen bleiben erhalten. Schnittstelle: `POST /api/recordings/merge` mit `{ids, title?}`.
- **Audio anhängen mit mehreren Dateien:** werden jetzt nach Namen sortiert angehängt (Teil 1 vor Teil 2 vor Teil 10), egal in welcher Reihenfolge der Dialog sie liefert.

## 1.4.5 – Zusammenfassungen formatieren wie in Word · Kopieren mit Formatierung
- **Formatieren wie in Word:** *Bearbeiten* öffnet die Zusammenfassung als formatierten Text mit Werkzeugleiste – Schrift (Aptos, Calibri, Arial, Helvetica, Georgia, Times New Roman, Verdana, Courier New), Größe 8–72 pt, **A⁺/A⁻**, **Fett**, *Kursiv*, Unterstrichen, Durchgestrichen, Tief-/Hochgestellt, Schriftfarbe (oder *Automatisch*), Textmarker in fünf Farben, Überschrift 1–3, Aufzählung, Nummerierung, *Formatierung entfernen*. Text markieren, dann formatieren; ohne Markierung gilt es für das Wort am Cursor. **Strg/⌘ + B, I, U**, **Strg/⌘ + S** speichert. Keine `**` oder `#` mehr im Editor.
- **Gespeichert mit jeder Formatierung:** Die Zusammenfassung zeigt sie genau so an (Zeitstempel springen weiter ins Audio). Für KI, Suche und Markdown-Export speichert REKORD zusätzlich Markdown (fett/kursiv/Überschriften/Listen bleiben, Farbe und Größe kennt Markdown nicht). Ändert danach die KI die Zusammenfassung, gilt ihre Fassung – **Rückgängig** bringt die formatierte zurück.
- **Kopieren mit Formatierung:** *Kopieren* legt echtes HTML plus sauberen Text in die Zwischenablage – Word, Pages, Google Docs, Outlook und Mail fügen fett als fett, Listen als Listen, Überschriften als Überschriften ein. Auch für noch nie bearbeitete KI-Zusammenfassungen (Markdown wird umgewandelt). Die Schrift der App wird nicht mitgeschickt, Word nimmt seine Standardschrift – was du selbst eingestellt hast, bleibt.
- **Word-Export übernimmt alles:** Fett, kursiv, unterstrichen, durchgestrichen, hoch/tief, Farbe, Textmarker (nächste Word-Markerfarbe), Größe, Schrift, Überschriften als Word-Überschriften, Aufzählung/Nummerierung als Word-Listen, Tabellen als Word-Tabellen.
- **Export → Kopieren für Word:** die ganze Aufnahme (Zusammenfassungen + Transkript) formatiert in die Zwischenablage; *Markdown kopieren* gibt es weiter für Notion/Obsidian.

## 1.4.4 – ein Transkript aus mehreren Dateien · Mind Maps mit Ästen · Zusammenfassung per KI ändern · Rolle „Geräusch“
- **Mehrere Dateien → eine Aufnahme:** Werden mehrere Audio-/Videodateien auf einmal gewählt oder reingezogen, fragt REKORD: *Eine Aufnahme* (nach Namen sortiert – „Teil 1“ vor „Teil 2“ –, hintereinander mit kurzer Pause, ein Transkript, Sprecher über alle Teile; „Teil 1“ fällt aus dem Titel) oder *Einzeln*. Mitgewählte PDFs & Co. werden Unterlagen. Schnittstelle: `POST /api/recordings` mit `combine=true`.
- **Mind Maps:** Linien zeichnet jetzt Qt selbst (QtQuick.Shapes) – das Canvas blieb manchmal leer. Spaltenbreite nach dem längsten Text, die Mitte wächst mit; Texte bis 52 Zeichen ungekürzt. Der Parser versteht jede Einrückung (2/4 Leerzeichen, Tabs), Codeblöcke und `<think>`-Blöcke. Ist die Liste flach (keine Unterpunkte oder mehr als 9 Äste), ordnet die KI sie in einem zweiten Schritt in 4–6 Äste. Genauere Vorgabe an die KI (Beispiel, konkrete Begriffe statt allgemeiner). Im Browser zeichnet REKORD die Mind Map wie im Fenster (`/api/summaries/{id}/mindmap.svg`).
- **Zusammenfassung per KI ändern:** Feld über jeder Zusammenfassung (und unter der Mind Map): „keine Sternchen“, „kürzer“, „mit Emojis“, „To-dos als Tabelle“ → **Ändern**. Der Rest bleibt, Zeitstempel bleiben, nichts wird erfunden. **Rückgängig** wechselt zur vorigen Fassung (und wieder zurück).
- **Rolle „Geräusch“:** gibt es in jeder Aufnahme – *Wer sagt das? → Ist ein Geräusch – ausblenden*, beim Sprecher *Ist ein Geräusch – alle Zeilen ausblenden*, bei „Wer ist das?“ der Knopf **Geräusch**. Solche Zeilen stehen nicht im Transkript (*N Geräusche ausgeblendet · zeigen*), nicht in Zusammenfassung, Fragen, Export und Suche; aus ihnen wird nie ein Stimmprofil. Reine Geräusch-Tags („[Musik]“, „*hustet*“, „(Applaus)“) und typische Whisper-Phantome („Untertitel der Amara.org-Community“, „Vielen Dank fürs Zuschauen“) ordnet REKORD bei der Auswertung selbst zu.
- **Stopp neben „Datei transkribieren“:** In der Seitenleiste steht, was gerade transkribiert wird (Titel, Schritt, Prozent, wie viele warten) mit **Stopp**; in der Aufnahme groß **Transkription stoppen**.
- **Mehrere Aufnahmen löschen:** *Aufnahmen → Auswählen* → antippen oder **Alle** → **N löschen** (eine Bestätigung). Schnittstelle: `POST /api/recordings/delete`.
- **Scrollen überall:** Ausklappmenüs zeigen bis zu 9 Einträge und scrollen (vorher war die Liste zu klein); das Namensfeld zeigt alle bekannten Namen statt nur 12; „Wer ist das?“ und „Wer sagt das?“ scrollen bei vielen Stimmen/Namen; Aufnahme-Seite und Aufnahmen-Liste scrollen als Ganzes, wenn das Fenster klein ist.
- **Browser-Version entfernt:** REKORD ist nur noch die App. Die Web-Oberfläche (index.html, app.js, Service Worker, Kopplungsseite) und pywebview sind raus; Hilfetexte und Vorlese-Texte liegen jetzt in `rekord/data/help.json` und `reading.json`. `http://localhost:8765/` sagt nur noch, dass REKORD läuft (die Schnittstelle für Claude Desktop & Werkzeuge bleibt). Kann das Fenster nicht starten (z. B. Linux ohne Bildschirm), sagt REKORD warum, statt eine Webseite zu öffnen; `REKORD_CLASSIC` gibt es nicht mehr.
- **Icons:** App-Icon im Mac-Stil (abgerundetes Quadrat mit transparentem Rand) für Dock, Fenster, Windows-Taskleiste und Linux. In der Mac-Menüleiste ein Template-Symbol (einfarbig, passt sich hell/dunkel an; Ring = bereit, voller Punkt = nimmt auf).

## 1.4.3 – Modell passend zum Rechner · leise Aufnahmen lauter
- **Automatische Modellwahl:** Beim Start liest REKORD Arbeitsspeicher, Prozessorkerne, Apple-Chip und NVIDIA-Karte aus und wählt die Spracherkennung, die darauf am besten läuft – NVIDIA (mit faster-whisper) → faster-whisper turbo auf der Karte (unter 4 GB Grafikspeicher: small), ab 16 GB RAM und 8 Kernen → Whisper turbo, ab 8 GB und 4 Kernen → small, darunter → base. Das passende Modell wird gleich geladen. *Einstellungen → Transkription → Passend zu diesem Computer* zeigt, was erkannt wurde; ein selbst gewähltes Modell schaltet die Automatik ab, der Haken schaltet sie wieder an.
- **Leise Aufnahmen lauter:** Vor der Auswertung misst REKORD, wie laut die Sprache ist (die lauten Stellen, Pausen zählen nicht), und hebt sie auf etwa -20 dBFS – höchstens +30 dB, Spitzen werden weich begrenzt statt abgeschnitten. Nur für die Auswertung; die gespeicherte Aufnahme bleibt unverändert. Laute Aufnahmen bleiben, wie sie sind.

## 1.4.2 – angehängte Audios anhören · unbekannte Stimmen jederzeit benennen
- **Behoben: Nach *Audio anhängen* lief nur Teil 1.** Die Aufnahme bekommt beim Anhängen eine neue, längere Datei – der Player behielt die alte. Der Balken zeigte schon die ganze Länge, Spulen hinter Teil 1 sprang zum Anfang. Jetzt lädt der Player die neue Datei (die Stelle bleibt), auch im Browser.
- **„Wer ist das?“ verschwindet nicht mehr.** *Später* klappt es auf eine Zeile zusammen („2 Stimmen nicht erkannt“), **Jetzt benennen** öffnet es wieder – bisher war es bis zum Neustart weg.

## 1.4.1 – nur noch für den Computer: iPhone-App entfernt
- **Die iPhone-App gibt es nicht mehr.** REKORD ist ein Programm für Mac, Windows und Linux. Weg sind: der iPhone-Schritt in der Einführung, *Einstellungen → iPhone & Geräte* (QR-Code, Kopplungs-Code, Firewall-Knopf), die IPA auf der Release-Seite und der iOS-Build.
- **Nur noch auf diesem Computer erreichbar (127.0.0.1).** Die App öffnet sich nicht mehr fürs WLAN – Windows fragt nicht mehr nach der Firewall, macOS nicht mehr nach dem lokalen Netzwerk. Die Linux-Pakete öffnen keine Ports mehr und schließen beim Update den Port 8765, den ältere Versionen geöffnet haben. Wer trotzdem ein eigenes Gerät koppeln will: `--lan` bzw. `REKORD_LAN=1` (Koppeln über die Schnittstelle `/api/pair`).
- **Vom Handy aufnehmen:** mit der Sprachmemo-App, Datei in den Eingangsordner (iCloud/Dropbox/OneDrive) – siehe Anleitung, Abschnitt 3.
- **Release-Seite neu:** Logo, Download-Knöpfe, Installation in einer Zeile, kurz „Neu in …“; die ganze Geschichte steht hier im Changelog.

## 1.4.0 – Transkript mit der KI bearbeiten · Rückgängig wie in Word · Update per Klick
- **Sag der KI, was sie am Transkript ändern soll:** Über dem Transkript ein Feld – „Lass den Smalltalk weg“, „Schreib Emil statt Emir“, „Ähms raus“, „Mach aus Stichworten ganze Sätze“ → **Ändern**. Die KI ändert oder entfernt einzelne Zeilen; Sprecher und Zeiten bleiben, erfunden wird nichts. Ihre Antwort wird von Formatierung befreit – keine Sternchen, Rauten oder Aufzählungszeichen im Text.
- **Rückgängig und Wiederholen wie in Word:** **↶ Rückgängig** / **↷ Wiederholen** über bis zu 50 Schritte, auch mit **Strg/⌘ + Z** und **Strg/⌘ + ⇧ + Z**. Gilt für alles, was den Text ändert: eigenes Tippen, *Suchen & Ersetzen* und die KI. Entfernte Zeilen kommen an ihrer Stelle zurück. Bleibt auch nach einem Neustart erhalten.
- **Word-Export ohne KI-Zeichen:** Zusammenfassungen kommen als echtes Word-Dokument – **fett** ist fett, Listen sind Listen (auch verschachtelt und nummeriert), To-dos werden ☐/☑, Tabellen werden Word-Tabellen, Zitate werden Zitate. Keine `**`, `#`, `|` oder `- [ ]` mehr. Was du im Transkript geändert hast, steht genau so im Export.
- **Update per Klick, ohne Terminal:** REKORD schaut jetzt alle 30 Minuten nach einer neuen Version (bisher alle 6 Stunden – darum kam der Hinweis oft gar nicht). Unten links steht dann **Jetzt aktualisieren**; ein Klick lädt, ersetzt und startet REKORD neu. Neben der Version unten links gibt es jederzeit **Nach Updates suchen**. Scheitert ein Update, steht der Grund dabei.
- **Lokale KI: der echte Fehler statt „500 Internal Server Error“.** Bricht Ollama ab, zeigt REKORD Ollamas eigene Meldung mit dem passenden Tipp – zu wenig Speicher (kleineres Modell / kürzere Kontextlänge), Modell fehlt, Ollama zu alt, Absturz beim Laden.

## 1.3.9 – kein Englisch mehr, wenn Deutsch gesprochen wird
- **Behoben: Einzelne Sätze kamen auf Englisch.** *Automatisch* erkennt die Sprache pro Satz – bei kurzen Sätzen („Ja, passt.“, „Okay.“) hat Whisper dabei oft Englisch geraten und den Satz dann auf Englisch geschrieben. Jetzt bekommen Sätze unter 4 Sekunden die **Hauptsprache der Aufnahme** (woran die längeren Sätze erkannt wurden). Längere Sätze behalten ihre eigene Sprache – Meetings, die wirklich zwischen Deutsch und Englisch wechseln, bleiben richtig. Live genauso, sobald nach ~15 Sekunden klar ist, was die Hauptsprache ist. faster-whisper erkennt bei *Automatisch* jetzt pro Abschnitt statt einmal für die ganze Datei.
- **Behoben: *distil-large-v3* kann nur Englisch** – deutsche Aufnahmen kamen damit als englische Übersetzung raus. Es steht jetzt so in der Liste, und ist es gewählt, die Sprache aber nicht Englisch, nimmt REKORD automatisch ein mehrsprachiges Modell.
- Am sichersten bleibt: Sprache fest auf **Deutsch** (*Einstellungen → Transkription*). Schon falsch transkribiert? Aufnahme öffnen → *„…“ → Neu verarbeiten*.

## 1.3.8 – zwei Spracherkennungen zur Wahl
- **faster-whisper ist jetzt in jeder App dabei** (Mac, Windows, Linux) – unter *Einstellungen → Transkription → Engine* frei wählbar neben *Whisper ONNX*. Bisher stand es nur als „nicht installiert“ da, ließ sich aber auswählen – und dann scheiterte jede Transkription. Das ist behoben.
- **Was faster-whisper besser kann:** Es kennt die Zeit jedes einzelnen Worts – jedes Wort bekommt seinen Sprecher, genauer bei schnellen Wechseln. Und es hört die Namen und Begriffe aus dem *Vokabular* und den *Unterlagen* schon beim Erkennen, statt sie hinterher zu korrigieren.
- **Mit NVIDIA-Grafikkarte sehr schnell, sonst auf dem Prozessor:** REKORD probiert die Grafikkarte und nimmt automatisch den Prozessor, wenn sie nicht geht (z. B. ohne CUDA 12/cuDNN unter Windows). Unter *Engine* steht, worauf es gerade läuft.
- **Seine Modelle wie alle anderen:** *faster-whisper turbo, large-v3, distil-large-v3, medium, small, base, tiny* – unter *Modell* mit **Jetzt laden** (mit Fortschritt) oder unter *Einstellungen → Modelle*. Geladen wird von Hugging Face in den REKORD-Modellordner, danach offline. Klappt das Laden nicht, wertet REKORD die Aufnahme mit Whisper ONNX aus, statt abzubrechen.

## 1.3.7 – Unterlagen: Namen und Fachbegriffe richtig · Auswertung stoppen · Modelle per Klick laden
- **Unterlagen zur Aufnahme:** Agenda, Folien, Teilnehmerliste, Vertrag, Foto vom Whiteboard – als **PDF, Word, PowerPoint, Excel, OpenDocument, Text, Markdown, HTML, RTF, EPUB oder Bild**. Hinzufügen vor der Aufnahme in *Wer ist dabei?*, während der Aufnahme auf die Live-Seite ziehen, beim Import einfach zusammen mit der Audiodatei auswählen, oder später: Aufnahme öffnen → **Unterlagen** (oder PDF auf die Aufnahme ziehen).
- **Namen und Begriffe richtig im Transkript:** Die Spracherkennung schreibt seltene Wörter, wie sie klingen – *Bönke*, *Sapir*, *Order Bird*. REKORD sucht in den Unterlagen die seltenen Wörter (Namen, Fachbegriffe, Produktnamen, Abkürzungen) und korrigiert, was im Transkript gleich klingt (Kölner Phonetik) oder fast gleich geschrieben ist: *Boenke*, *Zapier*, *Orderbird*. Normale Wörter fasst REKORD nie an – ein eingebautes Wörterbuch (je 50 000 deutsche und englische Wörter) sagt, was ein echtes Wort ist, *Vortrag* wird also nie zu *Vertrag*. Funktioniert schon in der Live-Mitschrift.
- **Alles nachvollziehbar:** neuer Reiter **Unterlagen** in jeder Aufnahme – die Dateien (Öffnen, Entfernen) und *Im Transkript korrigiert*: jede Korrektur als *falsch → richtig* mit Anzahl. Antippen nimmt sie überall zurück, nochmal antippen setzt sie wieder; **Alle rückgängig** zeigt das Transkript, wie es erkannt wurde – deine eigenen Änderungen bleiben. Entfernst du eine Unterlage, gehen ihre Korrekturen mit.
- **Mit lokaler KI noch genauer:** Mit Ollama oder LM Studio sucht zusätzlich die KI nach falsch erkannten Begriffen. Sie darf nur Wörter einsetzen, die in den Unterlagen stehen, und nichts umformulieren.
- **Fotos und gescannte PDFs:** Am Mac liest die eingebaute Texterkennung von macOS den Text (offline, wie *Live Text*), unter Windows/Linux eine lokale KI, die Bilder versteht (z. B. *qwen2.5vl* in Ollama).
- **Zusammenfassung und Fragen** kennen die Unterlagen als Hintergrund („laut Agenda.pdf …“) – mit einer lokalen KI.
- **Bleibt auf deinem Computer:** Unterlagen gehen nie an eine Cloud-KI – auch nicht, wenn Claude oder ChatGPT eingestellt ist. Wer das will, schaltet es selbst ein (*Einstellungen → Transkription → Unterlagen an Cloud-KI*).
- **Auswertung stoppen:** Die falsche Datei erwischt? In der Liste **■** neben dem Fortschritt, oder in der Aufnahme **Stoppen** – die Auswertung endet sofort (ihr Prozess wird beendet), die Aufnahme bleibt, *Nochmal* startet sie neu. **Löschen** geht jetzt auch mitten in der Auswertung und stoppt sie zuerst.
- **Sprachmodelle laden – endlich per Klick:** Fehlt etwas, steht links unten **jetzt laden** (und in *Aufnahmen* **Jetzt laden**) – ein Klick lädt alles Nötige, mit Fortschritt. Unter *Transkription → Modell* gibt es **Jetzt laden** direkt beim gewählten Modell, unter *Modelle* **Alles Nötige laden**. Behoben: Nach *Laden* passierte sichtbar nichts (der Fortschritt kam erst, wenn man die Seite neu öffnete), und das Modell-Menü zeigte „wird geladen“, obwohl nichts lud.
- **Kein Abbruch mehr wegen eines fehlenden Modells:** Ist das gewählte Sprachmodell noch nicht da, nimmt REKORD solange ein vorhandenes. Fehlt ein Modell ganz, lädt die Auswertung es sichtbar (*„Lädt Whisper small (einmalig)“*) – und klappt das nicht, steht der Grund in Worten da (keine Verbindung, kein Platz …) statt einer technischen Fehlermeldung.
- Auch in der Browser-Version und über die Schnittstelle (`/api/recordings/{id}/documents`, `/cancel`, `/api/models/download-missing`).

## 1.3.6 – Videos mit Bildern im Transkript · jedes Format · 2 Klicks zum Transkript
- **Mac: REKORD sagt jetzt, was macOS wirklich meldet.** Bisher klang jeder Fehler beim Call-Ton wie eine fehlende Erlaubnis – auch wenn der Schalter längst an war. Jetzt steht die echte Antwort von macOS (Text und Fehlercode) in der Meldung und in *rekord.log*. Nur eine echte Ablehnung zeigt weiter die Knöpfe zum Erlauben.
- **Mac-App: Signatur wird nach jedem Build geprüft.** Die Release-Pipeline prüft die Signatur der Mac-App streng und bricht ab, wenn sie ungültig ist; die Installations-Zeile und das In-App-Update signieren die App auf deinem Mac zusätzlich selbst (ad hoc) – damit macOS die Erlaubnisse immer einer gültigen App zuordnen kann.
- **Videos mit Bildern im Transkript:** Bei einem Video (Teams-/Zoom-Aufzeichnung mit Bildschirmfreigabe, Vortrag, Webinar) speichert REKORD automatisch ein Standbild, wann immer sich das Bild deutlich ändert – neue Folie, anderer Bildschirm, neue Szene. Im Transkript steht es direkt über dem Satz, der dazu gesagt wurde; antippen zeigt es groß, mit *Ab hier anhören*. Ein Mauszeiger oder kleine Bewegungen zählen nicht. Läuft lokal, ohne Internet.
- **Jedes Audio- und Videoformat:** nicht mehr nur eine feste Liste – MKV, AVI, WMV, AIFF, MTS und alles andere, was Ton enthält, auch mit ungewöhnlicher Endung.
- **Fertige Audios in 2 Schritten statt 4:** Links, direkt unter *Aufnehmen*, gibt es auf jeder Seite **Datei transkribieren** – Datei wählen, die Aufnahme öffnet sich sofort und wird ausgewertet. Kein Seitenwechsel, kein Suchen in der Liste. Dasselbe beim Reinziehen, beim Einfügen mit ⌘V und im Menüleisten-Symbol.
- **Dateien an eine Aufnahme anhängen:** Aufnahme öffnen → **Audio anhängen** (oben rechts, sichtbar statt im Menü versteckt) – oder Datei auf die Aufnahme ziehen → *Anhängen*. Teil 2 des Meetings, Sprachmemos dazu, ein zweites Gerät – alles kommt hinten dran, und REKORD transkribiert die ganze Aufnahme neu, mit Sprechern über alle Teile hinweg. Deine Originaldateien bleiben unberührt.
- **Dateien einfügen:** Audio- oder Videodatei im Finder/Explorer kopieren (z. B. aus *Downloads*) und in REKORD **⌘ V** / **Strg + V** – wird importiert und transkribiert. Auch ein kopierter Dateipfad geht.
- **Importieren** öffnet direkt im Ordner *Downloads*.
- Kann REKORD eine Datei nicht lesen (macOS sperrt *Downloads*, Datei weg), sagt es das jetzt – statt still nichts zu tun. Nach einem Update wird auch die *Downloads*-Erlaubnis frisch abgefragt.

## 1.3.5 – Mac: „alles erlaubt, aber REKORD darf nicht aufnehmen“ behoben
- **Der Fehler:** Unter *Datenschutz & Sicherheit* stand REKORD auf „an“, trotzdem meldete REKORD, macOS erlaube Mikrofon bzw. Call-Ton nicht. Grund: Die Mac-App hat kein kostenpflichtiges Apple-Zertifikat, jede Version hat deshalb eine neue Signatur – und macOS hängt die Erlaubnis an die Signatur der **alten** Version. Der Schalter sieht an aus, gilt aber nicht mehr.
- **Automatisch:** Beim ersten Start einer neuen Version setzt REKORD seine alten Schalter selbst zurück. macOS fragt dann bei der nächsten Aufnahme sauber neu – erlauben, beim Call-Ton danach REKORD einmal neu starten.
- **Knöpfe statt Wegbeschreibung:** Verweigert macOS trotzdem etwas, stehen direkt in der Meldung **Systemaudio-Einstellung öffnen** bzw. **Mikrofon-Einstellung öffnen** (springt genau zum Schalter von REKORD) und **Rechte neu setzen**.

## 1.3.4 – Online-Meetings: mit oder ohne dein Mikrofon
- **Du entscheidest, ob du mit drauf bist.** Bei *Online* fragt „Wer ist dabei?“ jetzt: **Call + mein Mikro** (wie bisher: die anderen im Call und du) oder **Nur Call-Ton** – dann nimmt REKORD nur auf, was Teams, Zoom, Meet … am Computer abspielen.
- **Nur Call-Ton heißt wirklich: Mikrofon aus.** Es wird gar nicht erst geöffnet – kein Tippen, Husten oder Hintergrund von dir auf der Aufnahme, keine Mikrofon-Abfrage. Ideal für Webinare, Vorträge und Calls, in denen du nur zuhörst. Der Pegel zeigt dann den Call-Ton, oben steht *Nur Call-Ton · Mikro aus*.
- **Ehrlich, wenn's nicht geht:** Kann der Computer den Call-Ton nicht abgreifen (z. B. macOS älter als 13, keine Erlaubnis für *Bildschirm- & Systemaudioaufnahme*), startet *Nur Call-Ton* nicht stumm, sondern sagt warum – mit Mikrofon geht's dann wie gewohnt.
- REKORD merkt sich deine Wahl für die nächste Aufnahme. Auch in der Browser-Version (Einstellungen → Audio & Mikrofon und bei „Wer ist dabei?“).

## 1.3.3 – Live-Anzeige, Klang und Wiedergabe repariert
- **„Ich rede, aber REKORD zeigt mich stumm“ – behoben.** Die Anzeige, wer gerade spricht, wartete hinter der Live-Transkription, und schon jede Atempause galt als Stille. Jetzt hat sie einen eigenen Ablauf, und „niemand spricht“ kommt erst nach 1,2 s echter Ruhe. Gemessen (Echtzeit, Test-Meeting): vorher 94 % der Sprechzeit fälschlich als stumm angezeigt, jetzt 1 %.
- **Klang: nicht mehr „elektronisch“.** Die Umrechnung des Mikrofons auf 16 kHz passierte in kleinen Häppchen ohne Filter – Störgeräusche fast so laut wie die Stimme (Signal-Rausch-Abstand 0–11 dB). Jetzt ein durchgehender Filter: 95 dB, sauberer Klang in der Aufnahme und bessere Erkennung. Gilt für das Mikrofon im Fenster, *Person einsprechen*, den Call-Ton bei Online-Meetings und den Live-Stream vom iPhone.
- **Abspielen ohne Ton – behoben.** REKORD spielte immer auf dem Ausgabegerät, das beim Start aktiv war (z. B. AirPods, die später weg sind). Jetzt immer auf dem aktuellen Ausgang des Systems.
- **Zusammenfassung passt zum Gespräch:** Solange die genaue Auswertung läuft, wird nicht mehr aus der Live-Mitschrift zusammengefasst. *Nach der Auswertung* merkt die Vorlage vor, das Protokoll entsteht dann automatisch aus dem vollständigen Transkript.
- **Mikrofon-Wächter:** Kommt kein Ton an (stumm geschaltet, falsches Mikro), zeigt REKORD das während der Aufnahme – mit Mikrofon-Wechsel direkt im Hinweis, ohne Stopp. Setzt das Mikrofon aus (AirPods raus, USB abgesteckt), startet REKORD es von selbst neu.
- **Mehrkanal-Mikrofone und Audio-Interfaces:** REKORD nimmt den Kanal mit der Stimme, statt alle zu mitteln (das hat die Stimme verdünnt oder sogar ausgelöscht).
- **Bluetooth-Hinweis:** Bei AirPods & Co. als Mikrofon sagt REKORD, dass Bluetooth dann nur Telefonqualität aufnimmt – und empfiehlt das Mikrofon des Computers.
- **Live-Mitschrift auf langsamen Computern:** Sätze desselben Sprechers werden gebündelt; fällt sie zu weit zurück, holt sie sichtbar auf statt immer weiter hinterherzuhinken. Nach dem Stopp steht ohnehin alles im Transkript.

## 1.3.2 – aktuelle Sprach-Engine und Claude-Schnittstelle
- **Sprach-Engine sherpa-onnx 2.0** (Transkription, Sprecher-Trennung, Stimmabdrücke, Live-Erkennung). Auf den Test-Meetings liefert sie exakt dieselben Ergebnisse wie die bisherige Version; alle Tests mit echten Modellen laufen damit.
- **Claude über die neue API-Version 2026-10-21** (Anthropic-SDK 2): Der API-Key geht jetzt als `Authorization: Bearer` raus statt im `x-api-key`-Header – laut Anthropic nimmt die API beides an. Für dich ändert sich nichts: Key bleibt, Zusammenfassungen, Denkaufwand und Ausweichmodell funktionieren wie bisher.
- Wenn die Sprach-Engine in der Auswertung nicht laden kann, steht das jetzt als Fehler bei der Aufnahme (vorher blieb sie ohne Meldung hängen).
- Unter der Haube: Die Test-Meetings liegen fest im Projekt, statt bei jedem Testlauf neu synthetisiert zu werden – neue Bibliotheksversionen können die Tests nicht mehr unbemerkt verändern.

## 1.3.1 – der Computer bleibt flüssig, während REKORD auswertet
- **Auswertung im Hintergrund:** Sprecher trennen und Transkribieren laufen jetzt in einem eigenen Prozess mit niedriger Priorität und höchstens der Hälfte der Prozessorkerne. Am Mac mit Apples Utility-Priorität: Apps, mit denen du arbeitest, haben Vorrang. Gemessen: Andere Programme behalten während der Auswertung 94 % ihrer Rechenleistung (vorher 68 %). Die Auswertung dauert dafür etwas länger.
- **Speicher sofort zurück:** Die Sprachmodelle (~1 GB) liegen nur noch im Auswerte-Prozess und sind weg, sobald er fertig ist – vorher blieben sie bis zum Beenden von REKORD im Speicher.
- **Live-Mitschrift** nutzt nur noch die Hälfte der Kerne.
- **Lokale KI (Ollama) braucht viel weniger RAM:** Statt immer Platz für 32.000 Tokens zu reservieren (bei qwen3:8b ~4,5 GB extra), nur so viel, wie die Zusammenfassung wirklich braucht. Danach gibt Ollama den Speicher nach 2 statt 5 Minuten frei. Startet REKORD Ollama selbst, nutzt es einen halb so großen Zwischenspeicher (8-Bit-KV-Cache).
- **Weniger Unruhe in der Oberfläche:** Fortschritt kommt in wenigen Schritten statt mehrmals pro Sekunde, und die Aufnahme-Ansicht baut sich dabei nicht mehr jedes Mal neu auf.
- Neu: *Einstellungen → Transkription → Computer flüssig halten* (Standard an). Aus = volle Leistung, schneller fertig.

## 1.3.0 – alles im REKORD-Fenster
Ab jetzt ist REKORD am Computer komplett ein eigenes Programm – keine Seite öffnet mehr die bisherige Ansicht.
- **Fragen** über alle Aufnahmen als Chat: Die Antwort nennt, wer es wann gesagt hat, ein Klick öffnet die Aufnahme genau an der Stelle.
- **Vorlagen:** am ⠿-Griff ziehen oder mit ⤒ ↑ ↓ sortieren (die Liste rückt live mit), antippen zum Bearbeiten, eigene anlegen und löschen.
- **Symbol in der Menüleiste / Taskleiste:** zeigt, ob aufgenommen wird, startet oder stoppt eine Aufnahme, holt das Fenster zurück, beendet REKORD. Läuft REKORD im Hintergrund (*Mit dem Computer starten*), ist es so jederzeit erreichbar.
- **Mitteilung**, wenn eine Aufnahme fertig ausgewertet ist, während du in einem anderen Programm bist – antippen öffnet sie.
- **Einstellungen** komplett im REKORD-Fenster: Darstellung, Mikrofon mit **Pegel testen**, KI (Claude, ChatGPT, lokal, kompatibel – mit Verbindungstest), Transkription, Sprecher-Erkennung, Modelle, iPhone, Claude Desktop, Speicher, Updates. Sprung-Knöpfe oben, ⓘ bei jedem Punkt.
- **Akzentfarbe** wählen – das ganze Fenster färbt sich sofort um (Text auf hellen Farben wird automatisch dunkel).
- **Lokale KI mit einem Klick** direkt im Fenster: Ollama installieren, bestes Modell für deinen Computer laden, Modelle verwenden oder löschen, Fortschritt live.
- **iPhone koppeln:** QR-Code und 6-stelliger Code mit Countdown, gekoppelte Geräte trennen.
- **Speicherort umziehen** (auch auf externe Festplatte, NVMe, NAS) mit Fortschritt; **„Laufwerk fehlt“** zeigt klar, was los ist: *Nochmal prüfen* oder *Neu auf diesem Computer anfangen*.
- **Einführung beim ersten Start** im Fenster: Speicherort → Aussehen → Sprache → Mikrofon (mit Pegel) → KI → deine Stimme → iPhone → **Erste Aufnahme**. Jeder Schritt überspringbar, später unter *Einstellungen → Hilfe* nochmal.
- **Computer wach halten:** Während einer Aufnahme schläft der Computer nicht ein.
- Ohne KI zeigt *Aufnahmen* eine Karte, um eine KI zu verbinden.
- Tastenkürzel wie die Leiste links: **Strg + 1 … 5** Aufnahmen, Live, Fragen, Personen, Vorlagen · **Strg + ,** Einstellungen.
- **Beenden ohne Absturzmeldung**, auch wenn im Hintergrund gerade eine Aufnahme ausgewertet wird – die Auswertung geht beim nächsten Start weiter.

## 1.2.0 – Aufnahmen und Personen komplett im neuen Fenster
- **Player:** Wellenform, farbige Sprecher-Leiste mit ★-Momenten, ±15 s, Tempo bis 2× – klick irgendwo hin, und es spielt ab dort.
- **Sprecher:** antippen → umbenennen, **Stimme merken** (künftig automatisch erkannt) oder doppelt erkannte zusammenführen.
- **Wer ist das?** direkt unter dem Player: unbekannte Stimme anhören, Namen eingeben (REKORD schlägt vor, wenn sich jemand vorgestellt hat), **Merken**.
- **Zusammenfassung:** Vorlage wählen, die KI schreibt **live sichtbar** mit. To-dos abhaken, Zeitstempel springen ins Audio, kopieren, bearbeiten, löschen.
- **Transkript:** Text direkt im Fenster korrigieren, Namen antippen → **Wer sagt das?** (ganze Stimme zuordnen, Stimme lernen), suchen, **Suchen & Ersetzen** (auch dauerhaft ins Vokabular), **Mitscrollen** beim Abspielen.
- **Mind Map:** gezeichnet im Fenster, Unterpunkte jetzt richtig unter ihren Themen. Als SVG oder PNG speichern.
- **Fragen** zu dieser Aufnahme als Chat · **Notizen** mit automatischem Speichern · **Ordner** per Klick.
- **Export:** Markdown, Word, **PDF**, Text, SRT, WebVTT, JSON, Original-Audio – mit „Speichern unter …“ – oder in die Zwischenablage.
- **•••**: neu verarbeiten, Personen neu erkennen, umbenennen, löschen.
- **Personen** im neuen Fenster: alle Stimmen mit Aufnahmen und Stimmproben, Name und Farbe ändern, Stimmabdruck löschen.
- **Person einsprechen** – drei Wege, jetzt mit dem Mikrofon direkt im Programm: **Text vorlesen** (jeder Name bekommt seinen eigenen Text), **Einfach reden lassen** (mit 💬 Gesprächsidee) oder **Aus Aufnahme lernen** (Stimme anhören, auswählen). Der Zähler zählt nur Sekunden, in denen wirklich gesprochen wird. Oder eine Datei mit nur dieser Person.
- **Vorstellungsrunde:** bei *Wer ist dabei?* neue Personen gleich einsprechen – danach zählen sie als bekannt.
- Unter der Haube: das Fenster spricht mit derselben lokalen Schnittstelle wie die iPhone-App – eine Logik für beide, alles bleibt synchron.

## 1.1.0 – REKORD ist jetzt ein echtes Programm
- **Eigenes Fenster statt Webseite:** REKORD läuft am Computer als natives Programm (Mac, Windows, Linux) – schneller, direkter, durchgehend animiert. Kein Browser, kein Web-Fenster.
- **Aufnahmen:** neue Liste mit Sprecher-Punkten, Fortschritt der Auswertung direkt in der Zeile, Suche (auch im Gesagten), Ordner-Filter, **Importieren** oder Dateien einfach ins Fenster ziehen.
- **Aufnahme ansehen:** Redeanteile jeder Person, Zusammenfassung und Transkript – aktualisiert sich von selbst, während REKORD auswertet.
- **Live:** großer animierter Sprecher in der Farbe der Person (Ringe, wenn gesprochen wird, Leuchten im Takt der Stimme), Redeanteile, Mitschrift live, unbekannte Stimme antippen → benennen. **Wer ist dabei?** mit Vor Ort, Online und Vorlesung, merkt sich die letzte Runde. Mikrofon direkt auf der Live-Seite wählen.
- **Tastatur:** Strg/⌘ + R neue Aufnahme · Leertaste Pause · H Moment markieren · Strg/⌘ + F Suchen · Strg/⌘ + I Importieren.
- **Hell, dunkel oder wie das System** – Umschalter unten links.
- **Schließen während einer Aufnahme** speichert sie zuerst. Mit *Mit dem Computer starten* bleibt REKORD nach dem Schließen fürs iPhone erreichbar.
- Fragen, Personen, Vorlagen und Einstellungen ziehen als Nächstes um und öffnen sich bis dahin in einem eigenen Fenster der bisherigen Ansicht (gleiche Daten).
- Mikrofone mit 44,1 oder 48 kHz (die meisten Macs und Headsets) werden für die Erkennung sauber umgerechnet.

## 1.0.11 – Vorlagen nach deiner Wichtigkeit
- **Vorlagen sortieren:** am ⠿-Griff ziehen oder mit ↑ ↓ ⤒ verschieben – was dir wichtig ist, kommt nach oben. Die Reihenfolge gilt überall: beim Zusammenfassen, bei der Standard-Vorlage und in der iPhone-App. *Reihenfolge zurücksetzen* stellt die ursprüngliche wieder her.
- Die Vorlagen-Auswahl beim Zusammenfassen ist jetzt eine Liste in deiner Reihenfolge (Kategorie steht dahinter).
- **Behoben:** Wer die Einstellungen sehr schnell wieder verlassen hat, bekam im Hintergrund einen Fehler.

## 1.0.10 – lokale KI: das beste Modell für deinen Computer
- **REKORD erkennt deinen Computer** (Arbeitsspeicher + Apple-Chip oder NVIDIA-Grafik) und wählt das stärkste lokale Modell, das darauf flott läuft – z. B. *qwen3:14b* bei 24 GB mit Apple-Chip, *qwen3:30b* ab 32 GB. Vorher war bei 8b Schluss.
- *Einstellungen → KI → Lokal*: **Bestes Modell laden & verwenden** mit einem Klick (schaltet nach dem Download automatisch um).
- **Jedes Modell verwenden oder löschen**: klare Knöpfe *Verwenden* und *🗑 Löschen* bei jedem geladenen Modell, dazu **Alle nicht verwendeten löschen** (zeigt, wie viel Platz frei wird).
- **Anderes Modell**: jeden Namen aus der Ollama-Bibliothek eintippen (z. B. *llama3.1:8b*) → *Laden & verwenden*. Mehr Modelle zur Auswahl (bis *qwen3:32b*), zu große sind markiert („läuft hier nur langsam“).

## 1.0.9 – Uni-Modus, Stimmen frei lernen, einfache Kopplung
- **Stimme lernen – drei Wege:** **Text vorlesen** (wie bisher), **Einfach reden lassen** (die Person redet über irgendwas – oder du lässt jemanden reden, der sowieso spricht, z. B. den Prof; kurze Zwischenrufe anderer lässt REKORD weg) oder **Aus Aufnahme lernen** (Stimme aus einer fertigen Aufnahme anhören und auswählen). Gezählt werden nur Sekunden, in denen wirklich gesprochen wird. Überall: Einführung, Personen, „Wer ist dabei?“, iPhone-App.
- **Vorlesung** als dritte Meeting-Art (Computer und iPhone): Mitzählen entfällt. REKORD erkennt die vortragende Person (bekannt mit Namen, sonst „Vortragende Person“) und sammelt alle anderen unter „Publikum“. Danach automatisch ein **Lernzettel**: Kernaussagen, Definitionen, Prüfungsrelevantes, Fragen aus dem Hörsaal, Prüfungsfragen.
- **Koppeln mit 6 Ziffern** (z. B. `482 913`) statt langem Code: gilt 10 Minuten, das iPhone bekommt dabei einen eigenen Schlüssel. 5 falsche Versuche → 1 Minute Pause. Geräte einzeln trennen oder **Alle Geräte trennen**. Der QR-Code geht weiter.
- **iPhone nur noch als App:** Die Web-Version fürs Handy (Browser, Zertifikat, Einrichtungsseite) ist raus. Im WLAN spricht nur die gekoppelte iPhone-App mit REKORD – die Oberfläche gibt es nur am Computer. Dadurch auch kein zweiter Port (8766) mehr.

## 1.0.8 – Online-Meetings und echte Updates
- **Vor Ort oder Online:** Vor jeder Aufnahme fragt *„Wer ist dabei?“* auch, wo das Meeting stattfindet. **Online** (Teams, Zoom, Meet …) nimmt am Computer zusätzlich den **Ton des Calls** auf – also die Stimmen der anderen, direkt aus dem Lautsprecher-Signal, auch wenn Teams oder Zoom als App läuft und du Kopfhörer trägst. Nur Ton, kein Bild. Windows und Linux ohne Rückfrage; am Mac fragt macOS einmal nach *Bildschirm- & Systemaudioaufnahme* (macOS 13+). Klappt der Call-Ton nicht, läuft die Aufnahme mit dem Mikrofon weiter und REKORD sagt warum.
- **Updates mit einem Klick, die wirklich ersetzen:** *Einstellungen → Version & Updates → Jetzt aktualisieren* lädt die neue Version, **ersetzt** die installierte App am selben Ort und startet neu – Aufnahmen, Personen und Einstellungen bleiben. Links erscheint *„Update auf … →“*, sobald es etwas Neues gibt. Läuft eine Aufnahme, wartet das Update.
- **Nie mehr zwei REKORDs:** Startest du eine neuere Version, während die alte läuft, beendet sich die alte und die neue übernimmt (nimmt die alte gerade auf: direkt danach). REKORD zweimal öffnen holt das offene Fenster nach vorne. Eine alte Kopie (alte Verknüpfung, *Downloads*) startet stattdessen die neueste installierte Version; *Mit dem Computer starten* zeigt immer auf die neueste.
- **Installations-Zeile** (`install.sh` / `install.ps1`) beendet jetzt zuerst jedes laufende REKORD – auch alte Kopien – und bricht ab, statt eine laufende Aufnahme abzuschneiden.
- **Behoben (Windows):** Per Doppelklick gestartet blieb das Fenster leer – ohne Konsole stürzte der interne Server beim Start ab. Jetzt startet er immer; Meldungen landen in `rekord.log` (siehe Anleitung → *Wenn was nicht klappt*).
- **Mac:** Nach diesem Update fragt macOS evtl. einmal neu nach Mikrofon bzw. Systemaudio – erlauben.
- **Einmalig beim Wechsel von 1.0.7:** Die alte Version kennt das neue Update noch nicht. Am einfachsten die Installations-Zeile nochmal ausführen oder alle REKORD-Fenster schließen und die neue Version öffnen. Ab 1.0.8 geht alles in der App.

## 1.0.7 – Einführung, Hilfe, richtige Stimmen
- **Einführung beim ersten Start:** Speicherort → Aussehen → Sprache → Mikrofon → KI → deine Stimme → iPhone. Alles überspringbar, jederzeit wiederholbar (*Einstellungen → Hilfe → Einführung starten*).
- **ⓘ an jedem Punkt:** Neben jeder Einstellung und jedem Begriff erklärt ein ⓘ, was er macht – Maus drüber oder antippen.
- **Speicherort frei wählbar:** eingebauter Speicher, externe Festplatte, zweite SSD (NVMe) oder Netzlaufwerk (NAS) – getrennt für Daten und KI-Modelle. Beim ersten Start wird gefragt, **bevor** etwas heruntergeladen wird. Umziehen später mit Fortschritt; fehlt ein Laufwerk beim Start, sagt REKORD Bescheid statt einen leeren Ordner anzulegen.
- **„Wer ist dabei?“ vor jeder Aufnahme:** Wie viele sprechen (dich mitgezählt) und wer ist schon bekannt. Ohne Angabe startet keine Aufnahme. REKORD trennt dann genau so viele Stimmen – auch wenn noch niemand bekannt ist.
- **Keine „Sprecher 1, 2, 3“ mehr:** Stimmen, die REKORD nicht kennt, landen gesammelt unter **„Nicht erkannte Stimme“** – transkribiert wird trotzdem alles.
- **„Wer ist das?“ nach der Aufnahme:** Pro unbekannter Stimme anhören, Namen eingeben, *Merken* – ab dann erkannt. Stellt sich jemand vor („Hier ist Emil“), steht der Name schon drin. Im Transkript ordnet **„Wer sagt das?“** einen Satz – oder alle Sätze dieser Stimme – einer Person zu.
- **Einsprechen mit eigenem Text pro Person:** ca. 45 Sekunden, mindestens 25. REKORD prüft, ob wirklich nur eine Stimme zu hören ist, lässt Husten und Geräusche weg und zeigt die Qualität an. Auch in der iPhone-App.
- **Lokale KI-Modelle löschen:** *Einstellungen → KI → Lokal* → **Löschen** neben jedem geladenen Modell.
- **Behoben:** Das App-Fenster hat Aussehen, Mikrofon und Teilnehmer bei jedem Start vergessen.

## 1.0.6
- **Sprecher-Erkennung:** Wird eine Person versehentlich als zwei Sprecher erkannt, führt REKORD die beiden jetzt automatisch zusammen (nur wenn die Stimmabdrücke eindeutig dieselbe Person sind und die Sprecherzahl nicht fest eingestellt ist).
- Die Ende-zu-Ende-Tests laufen jetzt mit immer gleichen Test-Stimmen – kein Zufall mehr in der Qualitätskontrolle.

## 1.0.5 – alles mit einem Klick
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

## 1.0.4
- **Lokale KI ohne Terminal:** Unter *Einstellungen → KI → Lokal* erkennt REKORD Ollama und startet es bei Bedarf. Deine vorhandenen Modelle sind antippbar, neue lädst du per **Laden**-Knopf mit Fortschrittsbalken. Das erste geladene Modell wird automatisch verwendet.
- Denk-Text lokaler Modelle (`<think>…</think>`) landet nicht mehr in Zusammenfassungen.
- **Behoben:** Die Pegel-Anzeige blieb nach dem Sprechen auf dem Höchstwert hängen. Jetzt misst sie in dB und fällt sauber zurück.

## 1.0.3
- **Behoben (Linux):** Der Modell-Download schlug auf Fedora, Arch und openSUSE mit einem SSL-Fehler fehl. REKORD bringt jetzt seine eigene Zertifikatsliste mit.
- **Behoben (Linux):** Das Öffnen des Browsers ist unter KDE abgestürzt (`kde-open`, falsche Systembibliotheken).
- Die Release-Tests machen jetzt auf jeder Distro einen echten HTTPS-Download.

## 1.0.2
- **Neue Anleitung** ([docs/ANLEITUNG.md](https://github.com/KimJongUnNK/rekord/blob/main/docs/ANLEITUNG.md)): Installation pro Plattform, die iPhone-Wege im Vergleich, KI verbinden und jeder Menüpunkt erklärt. Ein Test sorgt dafür, dass sie jeden Knopf der App abdeckt.
- **Behoben:** *Einstellungen → Claude Desktop (MCP)* zeigte in der fertigen Mac/Windows/Linux-App einen Befehl, der dort nicht funktioniert.
- **Behoben:** *Vorlagen* war am Handy nicht erreichbar. Die untere Leiste zeigt jetzt alle 6 Punkte, plus Link *Vorlagen verwalten* bei der Zusammenfassung.
- Texte in der App und in der iPhone-App passen jetzt zur Anleitung (keine Hinweise mehr auf Terminal-Optionen).

## 1.0.1
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
