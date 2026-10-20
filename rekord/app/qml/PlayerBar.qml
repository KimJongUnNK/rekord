import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Waveform, who-spoke-when bar with ★ highlights, play / ±15 s / speed.
Card {
    id: bar
    required property var page
    readonly property var rec: page.rec
    readonly property real dur: Math.max(1, (rec && rec.duration) || player.duration || 1)
    implicitHeight: col.implicitHeight + 28

    RowLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        Rectangle {  // play / pause
            id: playBtn
            width: 44; height: 44; radius: 22
            color: playMouse.containsMouse ? Qt.lighter(Theme.accent, 1.07) : Theme.accent
            scale: playMouse.pressed ? 0.93 : 1
            Behavior on scale { NumberAnimation { duration: 90 } }
            Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: player.playing ? 0 : 2; width: 20; height: 20; name: player.playing ? "pause" : "play"; filled: !player.playing; stroke: 2.4; color: Theme.onAccent }
            MouseArea { id: playMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: player.toggle() }
        }
        Btn { kind: "ghost"; small: true; text: "−15"; onClicked: player.skip(-15); ToolTip.visible: hovered; ToolTip.text: "15 Sekunden zurück" }
        Btn { kind: "ghost"; small: true; text: "+15"; onClicked: player.skip(15); ToolTip.visible: hovered; ToolTip.text: "15 Sekunden vor" }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 5
            Item {  // waveform: played part in the accent color
                id: wave
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                readonly property var peaks: bar.rec && bar.rec.peaks ? bar.rec.peaks : []
                readonly property int n: Math.max(1, Math.floor(width / 3))
                readonly property real played: player.position / bar.dur
                Repeater {
                    model: wave.n
                    delegate: Rectangle {
                        required property int index
                        readonly property real p: wave.peaks.length ? wave.peaks[Math.floor(index / wave.n * wave.peaks.length)] : 0.06
                        x: index * wave.width / wave.n
                        width: Math.max(1, wave.width / wave.n - 1.2)
                        height: Math.max(2, p * (wave.height - 2))
                        y: (wave.height - height) / 2
                        radius: 1
                        color: index / wave.n < wave.played ? Theme.accent : Theme.line2
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (m) => player.seekPlay(m.x / width * bar.dur)
                }
            }
            Item {  // who spoke when, with ★ highlights
                id: tl
                Layout.fillWidth: true
                Layout.preferredHeight: 8
                Rectangle { anchors.fill: parent; radius: 3; color: Theme.card2 }
                Repeater {
                    model: bar.rec ? bar.rec.segments : []
                    delegate: Rectangle {
                        required property var modelData
                        x: modelData.start / bar.dur * tl.width
                        width: Math.max(1, (modelData.end - modelData.start) / bar.dur * tl.width)
                        height: tl.height
                        color: bar.page.spk(modelData.speaker_id).color
                    }
                }
                Repeater {
                    model: bar.rec && bar.rec.highlights ? bar.rec.highlights : []
                    delegate: Text {
                        required property var modelData
                        text: "★"
                        font.pixelSize: 11
                        color: Theme.accent
                        x: modelData / bar.dur * tl.width - width / 2
                        y: -12
                    }
                }
                Rectangle {  // playhead
                    width: 2; height: tl.height + 6; y: -3; radius: 1
                    color: Theme.fg
                    x: player.position / bar.dur * tl.width - 1
                    visible: player.position > 0
                }
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -4
                    cursorShape: Qt.PointingHandCursor
                    onClicked: (m) => player.seekPlay(Math.max(0, m.x - 4) / tl.width * bar.dur)
                }
            }
        }

        ColumnLayout {
            spacing: 2
            Text {
                Layout.alignment: Qt.AlignRight
                text: bar.page.fmt(player.position) + " / " + bar.page.fmt(bar.dur)
                font.family: Theme.text; font.pixelSize: 13; font.features: ({ "tnum": 1 }); color: Theme.fg2
            }
            Text {
                Layout.alignment: Qt.AlignRight
                Layout.maximumWidth: 220
                visible: !player.available || player.error !== ""
                text: player.error
                elide: Text.ElideRight
                font.pixelSize: 11; color: Theme.err
            }
        }
        Btn {
            small: true
            text: player.rate + "×"
            onClicked: player.nextRate()
            ToolTip.visible: hovered
            ToolTip.text: "Wiedergabe-Tempo"
        }
    }
}
