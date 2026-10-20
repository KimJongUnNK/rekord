import QtQuick
import QtQuick.Controls.Basic
import "."

// Checkbox with a label (can wrap).
CheckBox {
    id: cb
    font.family: Theme.text
    font.pixelSize: 14
    spacing: 10
    hoverEnabled: true
    indicator: Rectangle {
        x: cb.leftPadding
        y: cb.topPadding + (cb.availableHeight - height) / 2
        width: 20; height: 20; radius: 6
        color: cb.checked ? Theme.accent : Theme.bg
        border.width: cb.checked ? 0 : 1.5
        border.color: cb.hovered ? Theme.fg3 : Theme.line2
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Icon { anchors.centerIn: parent; width: 14; height: 14; name: "check"; stroke: 2.4; color: Theme.onAccent; visible: cb.checked }
    }
    contentItem: Text {
        leftPadding: cb.indicator.width + cb.spacing
        text: cb.text
        font: cb.font
        color: Theme.fg
        wrapMode: Text.WordWrap
        verticalAlignment: Text.AlignVCenter
    }
}
