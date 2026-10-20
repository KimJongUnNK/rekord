"""Summary templates. Built-ins below; users add their own in the app (stored in SQLite)."""
from __future__ import annotations

from .. import db

T = lambda id, name, cat, desc, prompt: {"id": id, "name": name, "category": cat, "description": desc,  # noqa: E731
                                        "prompt": prompt.strip(), "builtin": True}

BUILTIN = [
    T("auto", "Auto (KI wählt Format)", "Standard", "Erkennt Gesprächsart und wählt die passende Struktur",
      """Erkenne zuerst, welche Art Gespräch das ist (Meeting, Call, Interview, Vorlesung, Brainstorming, Verkaufsgespräch,
privates Gespräch, Podcast ...). Wähle dann die Struktur, die für genau diese Art am nützlichsten ist.
Beginne IMMER mit einer Zeile '# <prägnanter Titel, max 8 Wörter>'.
Danach: **Kurzfassung** (3-5 Sätze), dann die passenden Abschnitte, und IMMER am Ende
'## To-dos' als Checkliste '- [ ] Aufgabe — **Person** — bis Datum' (nur wenn genannt) und '## Offene Fragen'."""),
    T("meeting", "Meeting-Protokoll", "Business", "Klassisches Protokoll mit Entscheidungen & To-dos",
      """# <Titel>
**Datum/Teilnehmer** aus dem Transkript.
## Kurzfassung (3 Sätze)
## Besprochene Themen (je Thema: Kernaussagen, wer was vertreten hat)
## Entscheidungen
## To-dos (- [ ] Aufgabe — **Verantwortlich** — Deadline)
## Offene Punkte & nächste Schritte"""),
    T("exec", "Executive Brief", "Business", "Eine Seite für Chefs: Was, warum, was jetzt",
      """# <Titel>
Maximal 200 Wörter. **BLUF** (Bottom line up front, 1 Satz). Dann 3 Bulletpoints Kontext,
3 Bulletpoints Entscheidungen/Risiken, 3 Bulletpoints nächste Schritte mit Verantwortlichen. Keine Füllwörter."""),
    T("actions", "Nur To-dos", "Business", "Alle Aufgaben, Verantwortliche, Deadlines",
      """# To-dos
Extrahiere JEDE Aufgabe, Zusage und Bitte. Format: '- [ ] Aufgabe — **Person** — Deadline [mm:ss]'.
Gruppiere nach Person. Erfinde keine Deadlines. Danach '## Ohne Verantwortlichen' für Aufgaben ohne Person."""),
    T("decisions", "Entscheidungsprotokoll", "Business", "Welche Entscheidungen, mit welcher Begründung",
      """# Entscheidungen
Tabelle | Entscheidung | Begründung | Wer hat entschieden | Zeit [mm:ss] |. Danach verworfene Optionen und warum."""),
    T("standup", "Daily / Stand-up", "Business", "Gestern / Heute / Blocker pro Person",
      """# Stand-up <Datum>
Je Person: **Name** — Erledigt / Heute / Blocker. Am Ende: Blocker, die jemand lösen muss, mit Owner."""),
    T("oneonone", "1:1 Gespräch", "Business", "Feedback, Ziele, Vereinbarungen",
      """# 1:1 <Namen>
## Stimmung & Themen ## Feedback (gegeben/erhalten) ## Ziele & Entwicklung ## Vereinbarungen (- [ ])"""),
    T("kickoff", "Projekt-Kickoff", "Business", "Ziele, Scope, Rollen, Timeline, Risiken",
      """# Kickoff: <Projekt>
## Ziel & Erfolgskriterien ## Scope (drin / nicht drin) ## Rollen (Tabelle Person | Rolle | Verantwortung)
## Timeline & Meilensteine ## Budget ## Risiken (Tabelle Risiko | Wahrscheinlichkeit | Gegenmaßnahme) ## Nächste Schritte"""),
    T("retro", "Retrospektive", "Business", "Gut / Schlecht / Verbessern",
      """# Retro
## Lief gut ## Lief schlecht ## Was wir ändern (konkrete Maßnahmen mit Owner) ## Stimmung im Team (1 Satz)"""),
    T("sales", "Sales Call", "Vertrieb", "BANT, Pain Points, Einwände, Next Steps",
      """# Call mit <Kunde>
## Kunde & Kontext ## Pain Points (mit Zitat) ## BANT (Budget, Authority, Need, Timing — je 'unbekannt' falls nicht genannt)
## Einwände & wie behandelt ## Kaufsignale ## Nächster Schritt + Datum ## Follow-up Mail (Entwurf, kurz)"""),
    T("client", "Kunden-Briefing", "Vertrieb", "Anforderungen des Kunden sauber erfasst",
      """# Briefing <Kunde>
## Ausgangslage ## Ziele des Kunden ## Anforderungen (Muss / Soll / Kann) ## Budget & Deadline ## Ansprechpartner
## Unklarheiten, die wir klären müssen ## Angebot: nächste Schritte"""),
    T("followup", "Follow-up E-Mail", "Vertrieb", "Fertige Mail an alle Teilnehmer",
      """Schreibe eine fertige Follow-up-E-Mail an die Teilnehmer: Betreffzeile, kurze Danksagung, 3-5 Bulletpoints Ergebnisse,
To-dos mit Namen und Deadline, nächster Termin. Ton: professionell, direkt, freundlich. Keine Floskeln."""),
    T("negotiation", "Verhandlung", "Vertrieb", "Positionen, Zugeständnisse, Ergebnis",
      """# Verhandlung
## Positionen (je Partei) ## Zugeständnisse (wer, was, Zeit) ## Ergebnis / Stand ## Rote Linien ## Nächste Runde vorbereiten"""),
    T("event", "Event-Planung", "Events", "Location, Line-up, Technik, Budget, Timeline",
      """# Event: <Name>
## Eckdaten (Datum, Location, Kapazität, Zielgruppe) ## Line-up / Programm ## Technik & Produktion (Ton, Licht, Bühne, Rider)
## Budget (Tabelle Posten | Betrag | Status) ## Genehmigungen & Behörden ## Marketing & Ticketing
## Timeline bis zum Event ## To-dos (- [ ] — **Person** — Deadline) ## Risiken"""),
    T("booking", "Booking / Künstler-Call", "Events", "Gage, Rider, Termine, Konditionen",
      """# Booking: <Künstler>
## Termin & Slot ## Gage & Zahlungsbedingungen ## Technical Rider ## Hospitality Rider ## Reise & Hotel
## Promo-Verpflichtungen ## Offene Punkte ## Vertragsstatus"""),
    T("sponsor", "Sponsoring-Gespräch", "Events", "Pakete, Gegenleistungen, Konditionen",
      """# Sponsoring <Firma>
## Interesse & Ziele des Sponsors ## Besprochene Pakete & Preise ## Gegenleistungen (Logo, Stand, Social ...)
## Einwände ## Deal-Status ## Nächste Schritte"""),
    T("interview", "Interview", "Medien", "Fragen & Antworten, beste Zitate",
      """# Interview mit <Name>
## Kurzporträt ## Fragen & Antworten (Q/A, Antworten verdichtet) ## Top 5 Zitate wörtlich mit [mm:ss] ## Themen für Folgefragen"""),
    T("podcast", "Podcast / Show Notes", "Medien", "Show Notes mit Kapitelmarken",
      """# <Episodentitel>
Kurzbeschreibung (2 Sätze, spannend). ## Kapitel (mm:ss — Titel) ## Key Takeaways ## Erwähnte Links/Namen/Bücher ## Zitat für Social"""),
    T("social", "Social Content", "Medien", "Posts, Hooks und Clips aus dem Gespräch (Englisch)",
      """Create social media content in ENGLISH from this conversation. Direct, no hashtags, no emojis spam.
## 5 Hooks (max 12 words) ## 3 Posts (LinkedIn/Instagram caption length) ## 5 Clip-worthy moments with [mm:ss] and why"""),
    T("hiring", "Bewerbungsgespräch", "HR", "Kandidat bewerten, strukturiert",
      """# Interview: <Kandidat> für <Rolle>
## Profil & Erfahrung ## Stärken (mit Beleg) ## Schwächen/Risiken ## Motivation ## Gehalt & Verfügbarkeit
## Bewertung (1-5) je Kriterium: Fachlich, Kommunikation, Culture Fit, Motivation ## Empfehlung"""),
    T("lecture", "Vorlesung / Lernzettel", "Bildung", "Kernaussagen, Definitionen, Prüfungsrelevantes, Fragen aus dem Hörsaal",
      """# <Thema der Vorlesung>
## Überblick (3-5 Sätze: worum ging es, wie hängt es mit dem Fach zusammen)
## Kernaussagen (je: Erklärung in einfachen Worten + ein Beispiel [mm:ss])
## Definitionen & Formeln (exakt so, wie sie genannt wurden)
## Prüfungsrelevant (alles, was die vortragende Person betont, wiederholt oder als „wichtig“ / „kommt dran“ markiert hat [mm:ss])
## Fragen aus dem Hörsaal (Frage → Antwort der vortragenden Person)
## 10 Prüfungsfragen mit Musterantwort
## Offene Fragen & zum Nachlesen (Literatur, Folien, Aufgaben bis zum nächsten Mal als - [ ] Checkliste)"""),
    T("study", "Lerngruppe", "Bildung", "Wer erklärt was, Aufgabenverteilung",
      """# Lerngruppe <Fach>
## Erklärte Themen (wer hat was erklärt) ## Verständnisprobleme ## Aufgabenverteilung (- [ ]) ## Nächstes Treffen"""),
    T("brainstorm", "Brainstorming", "Kreativ", "Alle Ideen geclustert und bewertet",
      """# Brainstorming: <Thema>
## Alle Ideen (geclustert nach Thema, mit Urheber) ## Top 3 (Impact vs. Aufwand, kurz begründet)
## Verrückteste Idee ## Nächste Schritte zum Testen"""),
    T("strategy", "Strategie-Session", "Kreativ", "Ziele, Optionen, Trade-offs, Entscheidung",
      """# Strategie: <Thema>
## Ausgangslage ## Ziele ## Optionen (je: Pro, Contra, Kosten) ## Trade-offs & Dissens (wer sieht was anders)
## Entscheidung / Empfehlung ## Erste Schritte (30 Tage)"""),
    T("doctor", "Arzttermin", "Persönlich", "Diagnose, Medikation, Anweisungen — verständlich",
      """# Arzttermin <Datum>
## Beschwerden ## Befund/Diagnose (in einfachen Worten) ## Medikamente (Name, Dosis, wann) ## Anweisungen
## Nächster Termin / Kontrollen ## Fragen fürs nächste Mal. Hinweis: keine eigenen medizinischen Ratschläge hinzufügen."""),
    T("personal", "Persönliches Gespräch", "Persönlich", "Kurz & locker zusammengefasst",
      """# <Titel>
Fasse locker in 5-8 Bulletpoints zusammen, was besprochen wurde, plus Dinge, die man sich merken sollte (Termine, Versprechen)."""),
    T("legal", "Rechts-/Vertragsgespräch", "Recht", "Positionen, Fristen, Risiken",
      """# <Titel>
## Sachverhalt ## Positionen der Parteien ## Genannte Fristen & Beträge (mit [mm:ss]) ## Risiken ## Vereinbarte Schritte.
Hinweis am Ende: 'Keine Rechtsberatung.'"""),
    T("quotes", "Zitate & Highlights", "Analyse", "Die stärksten Aussagen wörtlich",
      """# Highlights
## Markierte Momente (★) zuerst, falls vorhanden ## 10 stärkste Zitate wörtlich: > Zitat — **Sprecher** [mm:ss]"""),
    T("speakers", "Sprecher-Analyse", "Analyse", "Wer hat wie viel und was gesagt",
      """# Sprecher-Analyse
Tabelle | Sprecher | Redeanteil (aus Statistik) | Hauptthemen | Haltung |. Danach je Person 2-3 Sätze: Position, Anliegen, Zusagen.
Dann: Dynamik im Gespräch (Wer hat dominiert, wo gab es Konflikt/Einigkeit)."""),
    T("mindmap", "Mind Map", "Analyse", "Gesprächsstruktur als Mind Map",
      """Gib NUR eine verschachtelte Markdown-Liste aus (keinen anderen Text, keine Überschriften).
Erste Zeile: '- <Hauptthema>' . Darunter 3-7 Äste mit je 2-5 Unterpunkten (max 3 Ebenen, je max 6 Wörter)."""),
    T("qa", "FAQ aus dem Gespräch", "Analyse", "Fragen & Antworten zum Nachschlagen",
      """# FAQ
Erstelle 8-15 Fragen, die jemand, der nicht dabei war, stellen würde, mit präzisen Antworten aus dem Gespräch und [mm:ss]."""),
]
BY_ID = {t["id"]: t for t in BUILTIN}


def all_templates() -> list[dict]:
    """All templates in the user's order (Vorlagen: drag to the top what matters most); the rest as before."""
    from .. import config
    items = BUILTIN + db.list_custom_templates()
    order = {tid: i for i, tid in enumerate(config.load().get("template_order") or [])}
    return sorted(items, key=lambda t: (0, order[t["id"]]) if t["id"] in order else (1, items.index(t)))


def get(tid: str) -> dict:
    if tid in BY_ID:
        return BY_ID[tid]
    for t in db.list_custom_templates():
        if t["id"] == tid:
            return t
    raise KeyError(tid)
