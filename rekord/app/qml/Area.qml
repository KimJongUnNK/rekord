import QtQuick
import QtQuick.Controls.Basic
import "."

// Multi-line text in REKORD's look (scrolls when long).
ScrollView {
    id: sv
    property alias text: ta.text
    property alias placeholderText: ta.placeholderText
    property alias area: ta
    property bool mono: false
    property bool submitOnEnter: false  // chat: Enter sends, Shift+Enter makes a new line
    signal edited()
    signal submit()
    clip: true
    background: Rectangle {
        radius: 10
        color: Theme.bg
        border.width: ta.activeFocus ? 2 : 1
        border.color: ta.activeFocus ? Theme.accent : Theme.line
    }
    TextArea {
        id: ta
        wrapMode: TextArea.Wrap
        font.family: sv.mono ? (Qt.platform.os === "windows" ? "Consolas" : Qt.platform.os === "osx" ? "Menlo" : "monospace") : Theme.text
        font.pixelSize: sv.mono ? 13 : 14
        color: Theme.fg
        placeholderTextColor: Theme.fg3
        selectionColor: Theme.accent
        selectedTextColor: Theme.onAccent
        selectByMouse: true
        padding: 12
        background: null
        onTextChanged: if (activeFocus) sv.edited()
        Keys.onReturnPressed: (e) => { if (sv.submitOnEnter && !(e.modifiers & Qt.ShiftModifier)) { sv.submit(); e.accepted = true } else e.accepted = false }
        Keys.onEnterPressed: (e) => { if (sv.submitOnEnter && !(e.modifiers & Qt.ShiftModifier)) { sv.submit(); e.accepted = true } else e.accepted = false }
    }
}
