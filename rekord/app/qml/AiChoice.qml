import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Who writes the protocols? Lokal (one click), Claude, ChatGPT – or without AI for now.
ColumnLayout {
    id: a
    required property var app
    property bool withNone: true
    property string picked: ""
    property string defaultModel: ""
    signal ready()
    spacing: 12
    Component.onCompleted: app.call("GET", "/api/ollama", null, (o) => a.defaultModel = o.default || "", () => {})
    function choose(k) {
        picked = k
        if (k === "local") {
            app.call("POST", "/api/ollama/setup", {}, () => prog.active = true, (e) => app.toast(e))
            return
        }
        app.call("PUT", "/api/settings", { llm: { provider: k } }, () => { rekord.refresh(); if (k === "none") a.ready() })
    }
    Flow {
        id: cards
        Layout.fillWidth: true
        spacing: 10
        readonly property int n: a.withNone ? 4 : 3
        Repeater {
            model: [["local", "Lokal · gratis", "Ein Klick: REKORD lädt Ollama und " + (a.defaultModel || "ein passendes Modell") + ". Nichts verlässt den Computer."],
                    ["anthropic", "Claude", "Beste Qualität. API-Key einfügen."],
                    ["openai", "ChatGPT", "API-Key einfügen."]].concat(a.withNone ? [["none", "Erstmal ohne", "Nur Transkript und Sprecher."]] : [])
            delegate: AbstractButton {
                id: b
                required property var modelData
                width: Math.max(160, Math.floor((cards.width - (cards.n - 1) * 10) / cards.n)); height: 104
                hoverEnabled: true
                readonly property bool on: a.picked === modelData[0]
                onClicked: a.choose(modelData[0])
                background: Rectangle { radius: 14; color: b.on ? Theme.fg : b.hovered ? Theme.card2 : Theme.card; border.width: 1; border.color: b.on ? Theme.fg : Theme.line }
                contentItem: ColumnLayout {
                    spacing: 4
                    Text { Layout.leftMargin: 14; Layout.topMargin: 12; text: b.modelData[1]; font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Black; color: b.on ? Theme.bg : Theme.fg }
                    Text { Layout.leftMargin: 14; Layout.rightMargin: 12; Layout.fillWidth: true; text: b.modelData[2]; wrapMode: Text.WordWrap; maximumLineCount: 4; elide: Text.ElideRight; font.family: Theme.text; font.pixelSize: 12; color: b.on ? Theme.bg : Theme.fg3 }
                    Item { Layout.fillHeight: true }
                }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }
        }
    }
    LocalAiProgress { id: prog; Layout.fillWidth: true; app: a.app; onDone: { rekord.refresh(); a.ready() } }
    ColumnLayout {
        visible: a.picked === "anthropic" || a.picked === "openai"
        Layout.fillWidth: true
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Text { text: "API-Key"; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
            Tip { key: "apikey" }
        }
        RowLayout {
            Layout.fillWidth: true
            Input {
                id: key
                Layout.fillWidth: true
                echoMode: TextInput.Password
                placeholderText: "Key hier einfügen"
                onEditingFinished: if (text.trim()) {
                    const k = text.trim(), p = {}
                    p[a.picked] = { api_key: k }
                    res.text = "teste …"; res.color = Theme.fg2
                    a.app.call("PUT", "/api/settings", { llm: p }, () => a.app.call("POST", "/api/llm/test", null, (r) => {
                        res.text = r.ok ? "✓ verbunden" : "✗ " + r.error
                        res.color = r.ok ? Theme.ok : Theme.err
                        rekord.refresh()
                        if (r.ok) a.ready()
                    }))
                }
            }
            Btn { small: true; text: "Key erstellen"; iconName: "open"; onClicked: api.openUrl(a.picked === "anthropic" ? "https://console.anthropic.com/settings/keys" : "https://platform.openai.com/api-keys") }
        }
        Text { id: res; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg2; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }
}
