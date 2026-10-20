import QtQuick
import "."

// Thin progress bar.
Rectangle {
    property real value: 0
    implicitHeight: 6
    radius: height / 2
    color: Theme.card2
    Rectangle {
        height: parent.height
        radius: parent.radius
        width: parent.width * Math.max(0, Math.min(1, parent.value))
        color: Theme.accent
        Behavior on width { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }
    }
}
