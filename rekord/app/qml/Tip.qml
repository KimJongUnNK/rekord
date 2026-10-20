import QtQuick
import QtQuick.Controls.Basic
import "."

// ⓘ next to a setting or term: hover or click shows what it does (texts: web/help.js, one place for both views).
Rectangle {
    id: t
    property string key
    width: 18; height: 18; radius: 9
    color: hov.hovered || pop.opened ? Theme.fg : "transparent"
    border.width: 1.4
    border.color: hov.hovered || pop.opened ? Theme.fg : Theme.fg3
    Text {
        anchors.centerIn: parent
        text: "i"
        font.family: Theme.text; font.pixelSize: 11; font.weight: Font.Black
        color: hov.hovered || pop.opened ? Theme.bg : Theme.fg3
    }
    HoverHandler { id: hov; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: pop.opened ? pop.close() : pop.open() }
    Timer { running: hov.hovered && !pop.opened; interval: 350; onTriggered: pop.open() }
    Popup {
        id: pop
        y: t.height + 6
        x: Math.min(0, (t.parent ? t.parent.width : 300) - 320)
        width: 320
        padding: 14
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { radius: 12; color: Theme.fg; border.width: 0 }
        contentItem: Text {
            text: rekord.tip(t.key)
            textFormat: Text.RichText
            wrapMode: Text.WordWrap
            font.family: Theme.text; font.pixelSize: 13; lineHeight: 1.1
            color: Theme.bg
        }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
    }
    Timer { running: pop.opened && !hov.hovered; interval: 2500; onTriggered: if (!hov.hovered) pop.close() }
}
