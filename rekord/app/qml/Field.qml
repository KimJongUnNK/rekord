import QtQuick
import QtQuick.Layouts
import "."

// One setting: label (+ ⓘ and a hint) on the left, the control on the right – stacked when the window is narrow.
GridLayout {
    id: f
    property string label
    property string hint
    property string tip
    property bool wide: parent && parent.width > 640  // from the surrounding box: its own width would feed back
    default property alias content: holder.data
    Layout.fillWidth: true
    columns: wide ? 2 : 1
    columnSpacing: 24
    rowSpacing: 8
    ColumnLayout {
        Layout.preferredWidth: f.wide ? 260 : -1
        Layout.maximumWidth: f.wide ? 260 : 100000
        Layout.fillWidth: !f.wide
        Layout.alignment: Qt.AlignTop
        spacing: 3
        RowLayout {
            spacing: 6
            Text { text: f.label; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg; wrapMode: Text.WordWrap; Layout.maximumWidth: 230 }
            Tip { visible: f.tip !== ""; key: f.tip }
        }
        Text {
            visible: f.hint !== ""
            Layout.fillWidth: true
            text: f.hint
            wrapMode: Text.WordWrap
            textFormat: Text.StyledText
            font.family: Theme.text; font.pixelSize: 12; color: Theme.fg3
        }
    }
    ColumnLayout {
        id: holder
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        spacing: 8
    }
}
