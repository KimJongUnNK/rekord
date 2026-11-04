import QtQuick
import QtQuick.Layouts
import "."

// macOS refuses a permission although its switch may already show "on": straight to the switch, or reset it.
RowLayout {
    id: fix
    property string service: live.macBlocked   // "ScreenCapture" (call sound) or "Microphone"
    visible: service !== ""
    spacing: 8
    Btn {
        small: true
        kind: "primary"
        iconName: "settings"
        text: fix.service === "Microphone" ? "Mikrofon-Einstellung öffnen" : "Systemaudio-Einstellung öffnen"
        onClicked: live.openMacPrivacy(fix.service)
    }
    Btn {
        small: true
        iconName: "refresh"
        text: "Rechte neu setzen"
        onClicked: live.resetMacPermissions()
    }
}
