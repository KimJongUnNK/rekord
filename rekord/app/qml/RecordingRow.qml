import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// One recording in the list.
AbstractButton {
    id: row
    required property string rid
    required property string title
    required property string dateText
    required property string durationText
    required property string status
    required property string statusText
    required property real progress
    required property string folder
    required property var speakers
    required property string source
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    implicitHeight: 78
    readonly property bool busy: status === "queued" || status === "processing"

    background: Rectangle {
        radius: Theme.radius
        color: row.hovered ? Theme.card2 : Theme.card
        border.width: row.visualFocus ? 2 : 1
        border.color: row.visualFocus ? Theme.accent : row.hovered ? Theme.line2 : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle {  // processing progress along the bottom edge
            visible: row.busy
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: 1
            height: 3
            radius: 1.5
            width: (parent.width - 2) * Math.max(0.02, row.progress)
            color: Theme.accent
            Behavior on width { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }
        }
    }
    transform: Translate { x: row.hovered ? 3 : 0; Behavior on x { NumberAnimation { duration: Theme.mid; easing.type: Easing.OutCubic } } }

    contentItem: RowLayout {
        spacing: 16
        // speakers as overlapping dots
        Item {
            Layout.leftMargin: 18
            Layout.preferredWidth: 58
            Layout.preferredHeight: 40
            Rectangle {
                visible: row.speakers.length === 0
                anchors.centerIn: parent
                width: 40; height: 40; radius: 20
                color: Theme.card2
                border.width: 1
                border.color: Theme.line
                Icon { anchors.centerIn: parent; width: 18; height: 18; name: row.source === "import" ? "import" : "mic"; color: Theme.fg3 }
            }
            Repeater {
                model: row.speakers.slice(0, 3)
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    x: index * 15
                    y: 7
                    width: 26; height: 26; radius: 13
                    color: modelData.color
                    border.width: 2
                    border.color: row.hovered ? Theme.card2 : Theme.card
                    Text {
                        anchors.centerIn: parent
                        text: modelData.name === "Nicht erkannte Stimme" ? "?" : (modelData.name || "?").charAt(0).toUpperCase()
                        font.pixelSize: 12
                        font.weight: Font.Black
                        color: "#FFFFFF"
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 3
            Text {
                Layout.fillWidth: true
                text: row.title
                elide: Text.ElideRight
                font.family: Theme.text
                font.pixelSize: 16
                font.weight: Font.Bold
                color: Theme.fg
            }
            Text {
                Layout.fillWidth: true
                text: [row.dateText, row.durationText, row.speakers.map(s => s.name).join(", "), row.folder ? "▸ " + row.folder : ""].filter(x => x).join("  ·  ")
                elide: Text.ElideRight
                font.family: Theme.text
                font.pixelSize: 13
                color: Theme.fg3
            }
        }
        Rectangle {
            visible: row.statusText !== ""
            Layout.rightMargin: 4
            Layout.preferredHeight: 26
            Layout.preferredWidth: pillText.implicitWidth + 22
            radius: 13
            color: row.status === "error" ? Qt.rgba(0.94, 0.27, 0.27, 0.14) : row.status === "recording" ? Theme.accent : Theme.accentSoft
            Text {
                id: pillText
                anchors.centerIn: parent
                text: row.statusText
                font.family: Theme.text
                font.pixelSize: 12
                font.weight: Font.Bold
                font.features: ({ "tnum": 1 })
                color: row.status === "error" ? Theme.err : row.status === "recording" ? Theme.onAccent : Theme.accent
            }
        }
        Icon {
            Layout.rightMargin: 18
            width: 18; height: 18
            name: "next"
            color: Theme.fg3
            opacity: row.hovered ? 1 : 0.5
        }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
