import QtQuick
import QtQuick.Layouts
import "."

// Fragen: one chat over all recordings. Answers say who said it and when – a click jumps there.
Page {
    id: page
    required property var app
    onShownChanged: if (shown) chat.load()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        anchors.bottomMargin: 28
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 2
                RowLayout {
                    Eyebrow { text: "Über alle Aufnahmen" }
                    Tip { key: "ask" }
                }
                Title { text: "Frag dein Gedächtnis." }
            }
            Item { Layout.fillWidth: true }
            Btn {
                visible: chat.messages.length > 0
                kind: "ghost"; small: true; text: "Verlauf leeren"; iconName: "trash"
                onClicked: page.app.confirm("Verlauf leeren?", "Die Fragen und Antworten hier werden gelöscht. Deine Aufnahmen bleiben.", "Leeren", () => chat.clear())
            }
        }
        Rectangle {  // without an AI there are no answers: say so, offer to connect one
            visible: rekord.status.welcomeDone !== undefined && !rekord.status.ai
            Layout.fillWidth: true
            Layout.preferredHeight: noAi.implicitHeight + 36
            radius: Theme.radius
            color: Theme.card
            border.width: 1
            border.color: Theme.line
            ColumnLayout {
                id: noAi
                x: 18; y: 18
                width: parent.width - 36
                spacing: 12
                Text { text: "Für Antworten braucht REKORD eine KI"; font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Bold; color: Theme.fg }
                Muted { Layout.fillWidth: true; text: rekord.status.aiProblem || "Lokal und gratis – oder Claude / ChatGPT mit API-Key." }
                AiChoice { Layout.fillWidth: true; app: page.app; withNone: false }
            }
        }
        ChatView {
            id: chat
            Layout.fillWidth: true
            Layout.fillHeight: true
            app: page.app
            scope: "global"
            askPath: "/api/ask"
            placeholder: "Was wurde wann von wem gesagt …"
            suggestions: ["Was hat Lisa letzte Woche zum Budget gesagt?", "Welche To-dos sind noch offen?",
                          "Wann haben wir über den Headliner gesprochen?", "Fass meine Meetings dieser Woche zusammen."]
        }
    }
}
