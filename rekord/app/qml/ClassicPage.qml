import QtQuick
import QtQuick.Layouts
import "."

// Pages that move into the new app next: until then they open in the previous interface (own window, same data).
Page {
    id: page
    property string which: ""
    readonly property var info: ({
        "ask": { title: "Fragen", icon: "ask", route: "ask",
                 text: "Frag alle deine Aufnahmen auf einmal – z. B. „Was haben wir mit Anna zum Budget beschlossen?“ Die Antwort zeigt, wo es gesagt wurde." },
        "templates": { title: "Vorlagen", icon: "templates", route: "templates",
                       text: "Formate für Zusammenfassungen: nach Wichtigkeit sortieren, eigene anlegen, Vorlesung, Meeting, Interview …" },
        "settings": { title: "Einstellungen", icon: "settings", route: "settings",
                      text: "KI verbinden (Claude, ChatGPT, lokal), Speicherort, iPhone koppeln (6-stelliger Code), Updates, Mit dem Computer starten." }
    })
    readonly property var cur: info[which] || info["ask"]

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 560)
        spacing: 16
        Rectangle {
            width: 76; height: 76; radius: 22
            color: Theme.accentSoft
            Icon { anchors.centerIn: parent; width: 34; height: 34; name: page.cur.icon; color: Theme.accent }
        }
        Text {
            text: page.cur.title
            font.family: Theme.display; font.pixelSize: 44; font.weight: Font.Black; font.letterSpacing: -2
            color: Theme.fg
        }
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: page.cur.text
            font.family: Theme.text; font.pixelSize: 16; lineHeight: 1.15; color: Theme.fg2
        }
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Diese Seite zieht als Nächstes in die neue App um. Bis dahin öffnet sie sich in einem eigenen Fenster der bisherigen Ansicht – mit denselben Daten."
            font.family: Theme.text; font.pixelSize: 14; color: Theme.fg3
        }
        Btn {
            Layout.topMargin: 6
            kind: "primary"
            text: page.cur.title + " öffnen"
            iconName: "open"
            onClicked: rekord.openClassic(page.cur.route)
        }
    }
}
