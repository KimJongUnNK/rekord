import QtQuick
import QtQuick.Controls.Basic
import "."

// Text field in REKORD's look.
TextField {
    id: f
    property bool big: false
    font.family: Theme.text
    font.pixelSize: big ? 16 : 14
    color: Theme.fg
    placeholderTextColor: Theme.fg3
    selectionColor: Theme.accent
    selectedTextColor: Theme.onAccent
    leftPadding: 12
    rightPadding: 12
    topPadding: big ? 12 : 9
    bottomPadding: big ? 12 : 9
    selectByMouse: true
    background: Rectangle {
        radius: 10
        color: f.enabled ? Theme.bg : Theme.card2
        border.width: f.activeFocus ? 2 : 1
        border.color: f.activeFocus ? Theme.accent : Theme.line
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }
}
