import QtQuick
import QtQuick.Controls.Basic
import "."

// A person (color dot + name) that can be toggled on.
AbstractButton {
    id: c
    property color dot: Theme.fg3
    property bool on: false
    hoverEnabled: true
    implicitHeight: 34
    implicitWidth: label.implicitWidth + 40
    focusPolicy: Qt.TabFocus
    scale: down ? 0.95 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }

    background: Rectangle {
        radius: height / 2
        color: c.on ? Theme.fg : c.hovered ? Theme.card2 : Theme.card
        border.width: 1
        border.color: c.on ? Theme.fg : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    contentItem: Item {
        Rectangle {
            id: dotItem
            width: 10; height: 10; radius: 5
            color: c.dot
            anchors.left: parent.left
            anchors.leftMargin: 13
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            text: c.text
            anchors.left: dotItem.right
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            font.family: Theme.text
            font.pixelSize: 14
            font.weight: Font.DemiBold
            color: c.on ? Theme.bg : Theme.fg
        }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
