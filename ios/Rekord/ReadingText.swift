import Foundation

/// The text a person reads when REKORD learns their voice (~50 s). Same name → same text as in the web app
/// (same pool, same FNV-1a hash), different people → different texts.
enum ReadingText {
    static let pool = [
        "Heute früh habe ich zuerst einen starken Kaffee getrunken und dann in Ruhe meine Nachrichten gelesen.",
        "Auf dem Weg zur Arbeit fahre ich meistens mit dem Fahrrad, außer es regnet in Strömen.",
        "Wusstest du, dass manche Schnecken bis zu drei Jahre am Stück schlafen können?",
        "Für das Sommerfest brauchen wir noch Getränke, Tische, Stühle und eine ordentliche Lautsprecheranlage.",
        "Wenn ich ehrlich bin, finde ich lange Besprechungen ohne Tagesordnung ziemlich anstrengend.",
        "Der Zug nach Zürich fährt um siebzehn Uhr zweiunddreißig von Gleis vier ab.",
        "Könnten wir das Budget bis Freitag noch einmal gemeinsam durchgehen?",
        "Im Herbst färben sich die Blätter gelb, orange und tiefrot, und die Luft riecht nach Regen.",
        "Mein Lieblingsessen ist eine Pizza mit Pilzen, Paprika und extra viel Käse.",
        "Ich glaube, wir sollten zuerst die wichtigsten Aufgaben verteilen und danach über Details sprechen.",
        "Gestern Abend war das Konzert so laut, dass mir heute noch die Ohren klingeln.",
        "Bitte schick mir die Unterlagen per E-Mail, dann schaue ich sie mir am Wochenende an.",
        "Zwölf Zwerge zogen zwanzig Zentner Zucker quer durch den Zoo.",
        "Fischers Fritz fischt frische Fische, frische Fische fischt Fischers Fritz.",
        "Das Wetter in den Bergen kann sich innerhalb einer Stunde komplett ändern.",
        "Wie viele Leute erwarten wir eigentlich beim nächsten Workshop?",
        "Ehrlich gesagt hätte ich nie gedacht, dass das Projekt so schnell fertig wird!",
        "Unsere Nachbarin hat einen kleinen Hund, der jeden Morgen pünktlich um sechs Uhr bellt.",
        "Für die Präsentation brauche ich noch drei Folien mit Zahlen und eine kurze Zusammenfassung.",
        "Am liebsten verbringe ich meine Freizeit draußen, am See oder irgendwo in den Bergen.",
        "Kannst du mir kurz erklären, wie das neue Programm eigentlich funktioniert?",
        "Die Rechnung über vierhundertneunundachtzig Euro ist schon letzte Woche bezahlt worden.",
        "Manchmal ist es besser, eine Pause zu machen und später mit frischem Kopf weiterzuarbeiten.",
        "Quer über den Platz lief ein junger Mann mit einem riesigen Strauß Sonnenblumen.",
        "Wir treffen uns am Dienstag um halb zehn im großen Besprechungsraum im dritten Stock.",
        "Hast du schon gehört, dass die Bibliothek ab nächster Woche auch sonntags geöffnet hat?",
        "Die Technik für den Abend besteht aus zwei Mikrofonen, einem Mischpult und vier Boxen.",
        "Jeder im Team sollte genau wissen, wer für welche Aufgabe verantwortlich ist.",
        "Bei schönem Wetter grillen wir im Garten, bei schlechtem kochen wir eine große Suppe.",
        "Vielleicht sollten wir den Termin um eine Woche verschieben, damit wirklich alle dabei sein können.",
        "Xaver übt jeden Abend Saxophon, sehr zur Freude seiner Nachbarn im Erdgeschoss.",
        "Ich bin gespannt, was die Kundinnen und Kunden zu unserem Vorschlag sagen werden.",
        "Achtung, die Brücke über den Fluss ist wegen Bauarbeiten bis Ende Juli gesperrt.",
        "Ob wir das schaffen? Ich denke schon, wenn wir uns die Arbeit gut aufteilen.",
    ]

    static func make(name: String, variant: Int = 0) -> String {
        let key = name.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() + "#\(variant)"
        var h: UInt32 = 2166136261
        for u in key.utf16 { h ^= UInt32(u); h = h &* 16777619 }
        let order = pool.enumerated()
            .map { (i, t) in ((h ^ (UInt32(i + 1) &* 2654435761)) % 100003, i, t) }
            .sorted { ($0.0, $0.1) < ($1.0, $1.1) }
            .map { $0.2 }
        let who = name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "…" : name.trimmingCharacters(in: .whitespacesAndNewlines)
        return ([ "Hallo, ich heiße \(who). Ich lese diesen Text jetzt in meiner normalen Stimme vor, damit REKORD mich in Meetings erkennt." ]
                + order.prefix(7)
                + [ "Zum Schluss zähle ich langsam bis zehn: eins, zwei, drei, vier, fünf, sechs, sieben, acht, neun, zehn." ]).joined(separator: " ")
    }
}
