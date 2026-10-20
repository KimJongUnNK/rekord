import QtQuick
import QtQuick.Controls.Basic
import "."

// Modal dialog that scales in over a dimmed window.
Popup {
    id: sheet
    parent: Overlay.overlay
    modal: true
    focus: true
    anchors.centerIn: parent
    width: Math.min(parent ? parent.width - 48 : 560, 580)
    padding: 28
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle {
        color: Theme.scrim
        Behavior on opacity { NumberAnimation { duration: Theme.mid } }
    }
    background: Rectangle {
        radius: 20
        color: Theme.card
        border.width: 1
        border.color: Theme.line
    }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.mid; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.94; to: 1; duration: Theme.slow; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
        }
    }
    exit: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast }
            NumberAnimation { property: "scale"; from: 1; to: 0.97; duration: Theme.fast }
        }
    }
}
