import QtQuick
import QtQuick.Layouts
import "."

// A block of settings with a heading.
ColumnLayout {
    id: s
    property string title
    property string tip
    property string badge
    default property alias content: box.data
    Layout.fillWidth: true
    spacing: 12
    RowLayout {
        spacing: 8
        Text { text: s.title; font.family: Theme.display; font.pixelSize: 24; font.weight: Font.Black; font.letterSpacing: -0.6; color: Theme.fg }
        Tip { visible: s.tip !== ""; key: s.tip }
        Rectangle {
            visible: s.badge !== ""
            Layout.preferredHeight: 22
            Layout.preferredWidth: badgeT.implicitWidth + 16
            radius: 11
            color: Theme.card2
            Text { id: badgeT; anchors.centerIn: parent; text: s.badge; font.family: Theme.text; font.pixelSize: 11; font.weight: Font.Bold; color: Theme.fg2 }
        }
    }
    Card {
        Layout.fillWidth: true
        implicitHeight: box.implicitHeight + 40
        ColumnLayout {  // only the width is given – the height follows the content (no layout loop)
            id: box
            x: 20; y: 20
            width: parent.width - 40
            spacing: 20
        }
    }
}
