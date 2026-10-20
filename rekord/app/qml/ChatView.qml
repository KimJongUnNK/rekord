import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Ask questions – about one recording or about all of them. Answers name the places they come from.
Item {
    id: v
    required property var app
    property string scope: "global"           // chat history: "global" or a recording id
    property string askPath: "/api/ask"
    property var suggestions: []
    property string placeholder: "Frag etwas …"
    property bool busy: false
    property string live: ""
    property var messages: []
    signal seek(real sec)

    function load() {
        app.call("GET", "/api/chat/" + scope, null, (r) => { v.messages = r.items.map(m => ({ role: m.role, content: m.content })); scrollDown() }, () => {})
    }
    function clear() { app.call("DELETE", "/api/chat/" + scope, null, () => { v.messages = [] }) }
    function send(q) {
        q = q.trim()
        if (!q || busy) return
        composerBox.text = ""
        messages = messages.concat([{ role: "user", content: q }])
        busy = true; live = ""
        scrollDown()
        app.stream(askPath, { question: q }, (t) => { v.live = t; scrollDown() },
                   (t) => { v.messages = v.messages.concat([{ role: "assistant", content: t }]); v.busy = false; v.live = ""; scrollDown() },
                   (err) => { v.messages = v.messages.concat([{ role: "assistant", content: "**Fehler:** " + err }]); v.busy = false; v.live = "" })
    }
    function scrollDown() { Qt.callLater(() => list.positionViewAtEnd()) }
    onScopeChanged: load()
    Component.onCompleted: load()

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 14
            model: v.messages.concat(v.busy ? [{ role: "assistant", content: v.live || "…", live: true }] : [])
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: Item {
                id: msg
                required property var modelData
                width: list.width - 12
                height: bubble.height
                readonly property bool mine: modelData.role === "user"
                Rectangle {
                    id: bubble
                    anchors.right: msg.mine ? parent.right : undefined
                    width: msg.mine ? Math.min(parent.width * 0.75, userText.implicitWidth + 32) : parent.width
                    height: (msg.mine ? userText.implicitHeight : answer.implicitHeight) + 26
                    radius: 16
                    color: msg.mine ? Theme.fg : Theme.card
                    border.width: msg.mine ? 0 : 1
                    border.color: Theme.line
                    Text {
                        id: userText
                        visible: msg.mine
                        anchors.fill: parent
                        anchors.margins: 13
                        text: msg.modelData.content
                        wrapMode: Text.WordWrap
                        font.family: Theme.text; font.pixelSize: 15
                        color: Theme.bg
                    }
                    Markdown {
                        id: answer
                        visible: !msg.mine
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 14
                        source: msg.modelData.content
                        onSeek: (s) => v.seek(s)
                        onOpenRecording: (rid, s) => v.app.openRecording(rid, s)
                    }
                }
            }
            ColumnLayout {  // suggestions while empty
                visible: v.messages.length === 0 && !v.busy
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 560)
                spacing: 8
                Muted { Layout.alignment: Qt.AlignHCenter; text: "Zum Beispiel:" }
                Repeater {
                    model: v.suggestions
                    delegate: Btn { required property string modelData; Layout.alignment: Qt.AlignHCenter; text: modelData; onClicked: v.send(modelData) }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Area {
                id: composerBox
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(160, Math.max(50, composerBox.area.implicitHeight + 4))
                placeholderText: v.placeholder
                submitOnEnter: true
                onSubmit: v.send(composerBox.text)
            }
            Btn { kind: "primary"; iconName: "next"; implicitHeight: 50; implicitWidth: 50; enabled: !v.busy && composerBox.text.trim() !== ""; onClicked: v.send(composerBox.text) }
        }
    }
}
