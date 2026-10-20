import QtQuick
import QtQuick.Layouts
import "."

// Segmented choice with a sliding highlight: model = [{value, label, icon}]
Rectangle {
    id: seg
    property var model: []
    property string value: ""
    signal picked(string value)
    implicitHeight: 48
    implicitWidth: 420
    radius: 13
    color: Theme.card2
    border.width: 1
    border.color: Theme.line

    readonly property int index: Math.max(0, model.findIndex(m => m.value === value))
    readonly property real cell: (width - 8) / Math.max(1, model.length)

    Rectangle {
        x: 4 + seg.index * seg.cell
        y: 4
        width: seg.cell
        height: seg.height - 8
        radius: 10
        color: Theme.fg
        Behavior on x { SpringAnimation { spring: 4; damping: 0.32; epsilon: 0.25 } }
    }
    Row {
        anchors.fill: parent
        anchors.margins: 4
        Repeater {
            model: seg.model
            delegate: Item {
                required property var modelData
                required property int index
                width: seg.cell
                height: parent.height
                readonly property bool on: seg.value === modelData.value
                RowLayout {
                    anchors.centerIn: parent
                    spacing: 8
                    Icon {
                        visible: !!modelData.icon
                        name: modelData.icon || ""
                        color: on ? Theme.bg : Theme.fg2
                        Layout.preferredWidth: 18
                        Layout.preferredHeight: 18
                    }
                    Text {
                        text: modelData.label
                        font.family: Theme.text
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        color: on ? Theme.bg : Theme.fg2
                        Behavior on color { ColorAnimation { duration: Theme.fast } }
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { seg.value = modelData.value; seg.picked(modelData.value) }
                }
            }
        }
    }
}
