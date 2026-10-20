import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Everything that was said: click a name → "Wer sagt das?", click the time → listen, edit the text in place.
Item {
    id: v
    required property var page
    property string q: ""
    property bool follow: true
    readonly property var segs: page.rec ? page.rec.segments : []
    readonly property var shown: q ? segs.filter(s => (s.text || "").toLowerCase().indexOf(q) >= 0 || page.spk(s.speaker_id).name.toLowerCase().indexOf(q) >= 0) : segs
    readonly property var hl: page.rec && page.rec.highlights ? page.rec.highlights : []
    property int active: -1

    FindReplaceDialog { id: frep; page: v.page }

    Connections {  // the line being played: highlighted, and (Mitscrollen) kept in view
        target: player
        function onTick() {
            const t = player.position
            const i = v.shown.findIndex(s => t >= s.start && t < s.end + 0.3)
            if (i !== v.active) {
                v.active = i
                if (i >= 0 && v.follow && player.playing) list.positionViewAtIndex(i, ListView.Center)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Input {
                Layout.preferredWidth: 300
                placeholderText: "Im Transkript suchen"
                onTextChanged: v.q = text.trim().toLowerCase()
            }
            Btn { small: true; text: "Suchen & Ersetzen"; onClicked: frep.start() }
            Check { text: "Mitscrollen"; checked: v.follow; onToggled: v.follow = checked; font.pixelSize: 13 }
            Item { Layout.fillWidth: true }
            Muted { text: v.q ? v.shown.length + " von " + v.segs.length : v.segs.length + " Sätze"; font.pixelSize: 13 }
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: v.shown
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property var who: v.page.spk(modelData.speaker_id)
                readonly property bool star: v.hl.some(h => h >= modelData.start - 2 && h <= modelData.end + 2)
                width: list.width - 12
                height: line.implicitHeight + 14
                radius: 10
                color: index === v.active ? Theme.accentSoft : rowHover.hovered ? Theme.card : "transparent"
                HoverHandler { id: rowHover }
                RowLayout {
                    id: line
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 7
                    spacing: 12
                    ColumnLayout {
                        Layout.preferredWidth: 150
                        Layout.maximumWidth: 150
                        Layout.fillWidth: false
                        Layout.alignment: Qt.AlignTop
                        spacing: 2
                        AbstractButton {
                            Layout.fillWidth: true
                            implicitHeight: nameRow.implicitHeight
                            hoverEnabled: true
                            onClicked: v.page.assignLine(row.modelData.id)
                            ToolTip.visible: hovered
                            ToolTip.delay: 600
                            ToolTip.text: "Wer sagt das? – antippen zum Zuordnen"
                            contentItem: RowLayout {
                                id: nameRow
                                spacing: 6
                                Rectangle { width: 8; height: 8; radius: 4; color: row.who.color }
                                Text {
                                    Layout.fillWidth: true
                                    text: row.who.name
                                    elide: Text.ElideRight
                                    font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold
                                    font.underline: parent.parent.hovered
                                    color: Theme.fg
                                }
                            }
                            background: null
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                        }
                        Text {
                            text: v.page.fmt(row.modelData.start) + (row.star ? "  ★" : "")
                            font.family: Theme.text; font.pixelSize: 12; font.features: ({ "tnum": 1 })
                            color: row.star ? Theme.accent : Theme.fg3
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: player.seekPlay(row.modelData.start) }
                        }
                    }
                    TextArea {
                        id: ta
                        Layout.fillWidth: true
                        text: row.modelData.text
                        wrapMode: TextArea.Wrap
                        font.family: Theme.text; font.pixelSize: 15
                        color: Theme.fg
                        selectionColor: Theme.accent
                        selectedTextColor: Theme.onAccent
                        selectByMouse: true
                        padding: 0
                        topPadding: 2
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                            border.width: ta.activeFocus ? 1 : 0
                            border.color: Theme.accent
                            anchors.margins: -4
                        }
                        onEditingFinished: {
                            const t = text.trim()
                            if (t !== row.modelData.text) {
                                row.modelData.text = t
                                v.page.app.call("PATCH", "/api/segments/" + row.modelData.id, { text: t }, () => v.page.app.toast("Gespeichert"))
                            }
                        }
                    }
                }
            }
            Muted {
                visible: list.count === 0
                anchors.centerIn: parent
                text: v.q ? "Nichts gefunden." : v.page.rec && v.page.rec.status === "done" ? "Keine Sprache erkannt." : "Transkript entsteht gerade …"
            }
        }
    }
}
