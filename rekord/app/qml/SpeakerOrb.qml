import QtQuick
import "."

// The big animated "who speaks now": the speaker's color, rings while they talk, a halo that follows the voice.
Item {
    id: orb
    property color tint: Theme.fg3
    property string initial: ""
    property real level: 0
    property bool active: false
    property bool busy: false
    property bool clickable: false
    signal clicked()
    implicitWidth: 300
    implicitHeight: 300

    property real smoothed: level
    Behavior on smoothed { NumberAnimation { duration: 110; easing.type: Easing.OutQuad } }
    readonly property real coreSize: Math.min(width, height) * 0.52

    Behavior on tint { ColorAnimation { duration: Theme.slow } }

    Repeater {  // ripples while someone talks
        model: 3
        delegate: Rectangle {
            id: ring
            required property int index
            anchors.centerIn: parent
            width: orb.coreSize
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 2
            border.color: orb.tint
            opacity: 0
            SequentialAnimation {
                running: orb.active
                onRunningChanged: if (!running) { ring.opacity = 0; ring.scale = 1 }
                PauseAnimation { duration: ring.index * 700 }
                ParallelAnimation {
                    loops: Animation.Infinite
                    NumberAnimation { target: ring; property: "scale"; from: 1; to: 1.85; duration: 2100; easing.type: Easing.OutCubic }
                    NumberAnimation { target: ring; property: "opacity"; from: 0.55; to: 0; duration: 2100; easing.type: Easing.OutCubic }
                }
            }
        }
    }
    Rectangle {  // halo, follows the loudness
        anchors.centerIn: parent
        width: orb.coreSize
        height: width
        radius: width / 2
        color: orb.tint
        opacity: 0.16 + orb.smoothed * 0.18
        scale: 1.08 + orb.smoothed * 0.55
    }
    Rectangle {
        id: core
        anchors.centerIn: parent
        width: orb.coreSize
        height: width
        radius: width / 2
        color: orb.tint
        scale: (mouse.pressed ? 0.96 : 1) * (1 + orb.smoothed * 0.05)
        Behavior on scale { NumberAnimation { duration: 90 } }
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.lighter(orb.tint, 1.18) }
            GradientStop { position: 1; color: orb.tint }
        }
        Text {
            anchors.centerIn: parent
            visible: !orb.busy && orb.initial !== ""
            text: orb.initial
            font.family: Theme.display
            font.pixelSize: Math.round(core.width * 0.42)
            font.weight: Font.Black
            color: "#FFFFFF"
        }
        Icon {
            anchors.centerIn: parent
            visible: !orb.busy && orb.initial === ""
            width: core.width * 0.3
            height: width
            name: "mic"
            stroke: 1.6
            color: "#FFFFFF"
            opacity: 0.9
        }
        Rectangle {  // starting: a turning arc
            visible: orb.busy
            anchors.centerIn: parent
            width: core.width * 0.38
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 4
            border.color: Qt.rgba(1, 1, 1, 0.35)
            Rectangle {
                width: 12; height: 12; radius: 6
                color: "#FFFFFF"
                x: parent.width / 2 - 6
                y: -4
            }
            RotationAnimation on rotation { running: orb.busy; from: 0; to: 360; duration: 1100; loops: Animation.Infinite }
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            enabled: orb.clickable
            cursorShape: orb.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: orb.clicked()
        }
    }
}
