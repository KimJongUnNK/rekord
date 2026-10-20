import QtQuick
import "."

// Short messages at the bottom of the window.
Item {
    id: t
    width: parent ? parent.width : 400
    height: col.implicitHeight
    function show(msg) {
        if (!msg) return
        model.append({ msg: msg })
        if (model.count > 3) model.remove(0)
        timer.restart()
    }
    ListModel { id: model }
    Timer { id: timer; interval: 3800; onTriggered: if (model.count) { model.remove(0); if (model.count) restart() } }
    Column {
        id: col
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        spacing: 8
        move: Transition { NumberAnimation { properties: "y"; duration: Theme.mid; easing.type: Easing.OutCubic } }
        add: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.mid }
                NumberAnimation { property: "scale"; from: 0.9; to: 1; duration: Theme.slow; easing.type: Easing.OutBack }
            }
        }
        Repeater {
            model: model
            delegate: Rectangle {
                required property string msg
                anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
                width: Math.min(t.width - 48, label.implicitWidth + 40)
                height: label.implicitHeight + 22
                radius: 12
                color: Theme.fg
                Text {
                    id: label
                    anchors.centerIn: parent
                    width: Math.min(implicitWidth, t.width - 88)
                    text: msg
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    font.family: Theme.text
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: Theme.bg
                }
            }
        }
    }
}
