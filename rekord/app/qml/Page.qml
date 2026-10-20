import QtQuick
import "."

// A page that fades and slides in when it's shown.
Item {
    id: p
    property bool shown: false
    opacity: shown ? 1 : 0
    visible: opacity > 0.01
    enabled: shown
    transform: Translate { y: p.shown ? 0 : 18; Behavior on y { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } } }
    Behavior on opacity { NumberAnimation { duration: Theme.mid; easing.type: Easing.OutCubic } }
}
