import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Button: default (card), primary (accent), ghost (no frame), danger.
Button {
    id: b
    property string kind: "default"
    property string iconName: ""
    property bool small: false
    property bool iconOnly: text === ""
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    font.family: Theme.text
    font.pixelSize: small ? 13 : 14
    font.weight: Font.DemiBold
    implicitHeight: small ? 32 : 40
    implicitWidth: iconOnly ? implicitHeight : Math.max(implicitHeight, row.implicitWidth + leftPadding + rightPadding)
    leftPadding: iconOnly ? 0 : (small ? 12 : 16)
    rightPadding: leftPadding
    opacity: enabled ? 1 : 0.4
    scale: down ? 0.96 : 1
    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }

    readonly property color fgColor: kind === "primary" ? Theme.onAccent : kind === "danger" ? "#FFFFFF" : Theme.fg

    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Icon {
                visible: b.iconName !== ""
                name: b.iconName
                color: b.fgColor
                filled: b.iconName === "stop" || b.iconName === "record" || b.iconName === "play"
                Layout.preferredWidth: b.small ? 16 : 18
                Layout.preferredHeight: Layout.preferredWidth
            }
            Text {
                visible: b.text !== ""
                text: b.text
                font: b.font
                color: b.fgColor
            }
        }
    }

    background: Rectangle {
        radius: b.small ? 9 : 11
        color: b.kind === "primary" ? (b.down ? Qt.darker(Theme.accent, 1.12) : b.hovered ? Qt.lighter(Theme.accent, 1.07) : Theme.accent)
             : b.kind === "danger" ? (b.hovered ? Qt.lighter(Theme.err, 1.08) : Theme.err)
             : b.kind === "ghost" ? (b.hovered || b.down ? Theme.card2 : "transparent")
             : (b.hovered || b.down ? Theme.card2 : Theme.card)
        border.width: b.kind === "default" ? 1 : 0
        border.color: b.hovered ? Theme.line2 : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle {  // keyboard focus ring
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: b.visualFocus
        }
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
