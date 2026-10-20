import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A name: type freely, or pick one of the people REKORD already knows (▾).
Item {
    id: f
    property var names: []
    property alias text: field.text
    property string placeholder: "Name"
    signal accepted()
    implicitHeight: 38
    implicitWidth: 200
    readonly property var matches: names.filter(n => !field.text || n.toLowerCase().indexOf(field.text.toLowerCase()) >= 0).slice(0, 12)
    Input {
        id: field
        anchors.fill: parent
        rightPadding: f.names.length ? 30 : 12
        placeholderText: f.placeholder
        onAccepted: { pop.close(); f.accepted() }
        onTextEdited: if (f.matches.length && text) pop.open(); else pop.close()
    }
    Icon {
        visible: f.names.length > 0
        name: "next"; rotation: 90; width: 14; height: 14; color: Theme.fg3
        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
        MouseArea { anchors.fill: parent; anchors.margins: -8; cursorShape: Qt.PointingHandCursor; onClicked: pop.opened ? pop.close() : pop.open() }
    }
    Popup {
        id: pop
        y: f.height + 4
        width: f.width
        padding: 4
        height: Math.min(260, list.contentHeight + 8)
        visible: opened && f.matches.length > 0
        background: Rectangle { radius: 10; color: Theme.card; border.width: 1; border.color: Theme.line }
        contentItem: ListView {
            id: list
            clip: true
            model: f.matches
            delegate: ItemDelegate {
                required property string modelData
                width: list.width
                contentItem: Text { text: modelData; font.family: Theme.text; font.pixelSize: 14; color: Theme.fg }
                background: Rectangle { radius: 6; color: parent.hovered ? Theme.card2 : "transparent" }
                onClicked: { field.text = modelData; pop.close(); field.forceActiveFocus() }
            }
        }
    }
}
