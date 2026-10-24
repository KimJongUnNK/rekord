import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Live: start, then see who speaks, who talked how much, and the words as they come.
Page {
    id: page
    required property var app
    readonly property bool idle: live.state === "idle"
    readonly property var sp: live.speaking
    readonly property bool someone: !!sp.name
    readonly property bool canName: someone && !sp.known && sp.key >= 0
    readonly property var meetings: ({ person: { label: "Vor Ort", icon: "room" }, online: { label: "Online", icon: "online" },
                                       lecture: { label: "Vorlesung", icon: "lecture" } })

    Component.onCompleted: live.refreshMics()
    onShownChanged: if (shown && idle) live.refreshMics()

    NameDialog { id: nameDlg }

    // ================================================================ before the recording
    ColumnLayout {
        visible: page.idle
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 560)
        spacing: 18

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Live"
            font.family: Theme.display; font.pixelSize: 54; font.weight: Font.Black; font.letterSpacing: -2.4
            color: Theme.fg
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Nimm auf und sieh live, wer gerade spricht – mit Namen, sobald REKORD die Stimme kennt."
            font.family: Theme.text; font.pixelSize: 16; color: Theme.fg2
        }

        Item {  // the big record button, breathing
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 18
            Layout.bottomMargin: 18
            width: 188; height: 188
            Repeater {
                model: 2
                delegate: Rectangle {
                    id: breath
                    required property int index
                    anchors.centerIn: parent
                    width: 132; height: 132; radius: 66
                    color: Theme.accent
                    opacity: 0
                    SequentialAnimation {
                        running: page.shown && page.idle
                        loops: Animation.Infinite
                        PauseAnimation { duration: breath.index * 1100 }
                        ParallelAnimation {
                            NumberAnimation { target: breath; property: "scale"; from: 1; to: 1.42; duration: 2200; easing.type: Easing.OutCubic }
                            NumberAnimation { target: breath; property: "opacity"; from: 0.28; to: 0; duration: 2200; easing.type: Easing.OutCubic }
                        }
                        PauseAnimation { duration: (1 - breath.index) * 1100 }
                    }
                }
            }
            Rectangle {
                id: bigRec
                anchors.centerIn: parent
                width: 132; height: 132; radius: 66
                color: recMouse.containsMouse ? Qt.lighter(Theme.accent, 1.07) : Theme.accent
                scale: recMouse.pressed ? 0.94 : recMouse.containsMouse ? 1.04 : 1
                Behavior on scale { NumberAnimation { duration: Theme.mid; easing.type: Easing.OutBack } }
                Rectangle { anchors.centerIn: parent; width: 40; height: 40; radius: 20; color: Theme.onAccent }
                MouseArea {
                    id: recMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: page.app.startRecording()
                }
            }
        }

        RowLayout {  // microphone
            Layout.alignment: Qt.AlignHCenter
            spacing: 10
            Icon { name: "mic"; width: 18; height: 18; color: Theme.fg3 }
            ComboBox {
                id: micBox
                Layout.preferredWidth: 340
                model: [{ id: "", name: "Standard-Mikrofon des Systems" }].concat(live.mics)
                textRole: "name"
                valueRole: "id"
                currentIndex: Math.max(0, model.findIndex(m => m.id === live.mic))
                onActivated: live.setMic(currentValue)
                font.family: Theme.text
                font.pixelSize: 14
                background: Rectangle { radius: 11; color: Theme.card; border.width: 1; border.color: micBox.hovered ? Theme.line2 : Theme.line }
                contentItem: Text {
                    leftPadding: 14
                    rightPadding: 30
                    text: micBox.displayText
                    font: micBox.font
                    color: Theme.fg
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    width: micBox.width
                    highlighted: micBox.highlightedIndex === index
                    contentItem: Text { text: modelData.name; font: micBox.font; color: Theme.fg; elide: Text.ElideRight }
                    background: Rectangle { color: highlighted ? Theme.card2 : Theme.card }
                }
                popup.background: Rectangle { radius: 11; color: Theme.card; border.width: 1; border.color: Theme.line }
            }
        }
        Text {  // AirPods & co.: telephone quality as soon as their microphone is used
            visible: live.micHint !== ""
            Layout.fillWidth: true
            Layout.maximumWidth: 560
            Layout.alignment: Qt.AlignHCenter
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: live.micHint
            font.family: Theme.text; font.pixelSize: 13; color: Theme.warn
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: rekord.status.live ? "Gerade nimmt ein anderes Gerät auf (z. B. die iPhone-App) – das Gespräch erscheint danach unter Aufnahmen."
                : live.error ? live.error
                : "Strg+R startet von überall. Während der Aufnahme: Leertaste = Pause, H = Moment markieren."
            font.family: Theme.text; font.pixelSize: 13; color: live.error ? Theme.err : Theme.fg3
        }
    }

    // ================================================================ during the recording
    ColumnLayout {
        visible: !page.idle
        anchors.fill: parent
        anchors.margins: 32
        spacing: 18

        // ---- header: type, title, time
        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Rectangle {
                Layout.preferredHeight: 30
                Layout.preferredWidth: badgeRow.implicitWidth + 22
                radius: 15
                color: Theme.card2
                border.width: 1
                border.color: Theme.line
                RowLayout {
                    id: badgeRow
                    anchors.centerIn: parent
                    spacing: 6
                    Icon { name: (page.meetings[live.meeting] || page.meetings.person).icon; width: 16; height: 16; color: Theme.fg2 }
                    Text { text: (page.meetings[live.meeting] || page.meetings.person).label; font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.fg2 }
                }
            }
            Rectangle {
                visible: live.callAudio
                Layout.preferredHeight: 30
                Layout.preferredWidth: callRow.implicitWidth + 22
                radius: 15
                color: Qt.rgba(0.13, 0.77, 0.37, 0.14)
                RowLayout {
                    id: callRow
                    anchors.centerIn: parent
                    spacing: 6
                    Icon { name: "wave"; width: 16; height: 16; color: Theme.ok }
                    Text { text: "Call-Ton läuft mit"; font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.ok }
                }
            }
            Text {
                Layout.fillWidth: true
                text: live.title
                elide: Text.ElideRight
                font.family: Theme.display; font.pixelSize: 24; font.weight: Font.Black; font.letterSpacing: -0.6
                color: Theme.fg
            }
            Rectangle {
                id: pulse5
                width: 12; height: 12; radius: 6
                color: live.state === "paused" ? Theme.fg3 : Theme.accent
                SequentialAnimation on opacity {
                    onRunningChanged: if (!running) pulse5.opacity = 1
                    running: live.state === "recording"
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 700 }
                    NumberAnimation { to: 1; duration: 700 }
                }
            }
            Text {
                text: live.elapsedText
                font.family: Theme.display; font.pixelSize: 40; font.weight: Font.Black; font.letterSpacing: -1.2
                font.features: ({ "tnum": 1 })
                color: live.state === "paused" ? Theme.fg3 : Theme.fg
            }
        }

        Rectangle {  // e.g. the call sound couldn't be captured
            visible: live.notes !== ""
            Layout.fillWidth: true
            Layout.preferredHeight: noteText.implicitHeight + 20
            radius: 10
            color: Qt.rgba(0.96, 0.62, 0.04, 0.14)
            Text {
                id: noteText
                anchors.fill: parent
                anchors.margins: 10
                wrapMode: Text.WordWrap
                text: live.notes
                font.family: Theme.text; font.pixelSize: 13; color: Theme.fg
            }
        }

        Rectangle {  // nothing arrives from the microphone: say so, and switch without stopping
            visible: live.micWarning !== ""
            Layout.fillWidth: true
            Layout.preferredHeight: warnRow.implicitHeight + 20
            radius: 10
            color: Qt.rgba(0.94, 0.27, 0.27, 0.12)
            border.width: 1
            border.color: Qt.rgba(0.94, 0.27, 0.27, 0.4)
            RowLayout {
                id: warnRow
                x: 12; y: 10
                width: parent.width - 24
                spacing: 12
                Icon { name: "mic"; width: 18; height: 18; color: Theme.err }
                Text { Layout.fillWidth: true; text: live.micWarning; wrapMode: Text.WordWrap; font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.fg }
                Select {
                    Layout.preferredWidth: 300
                    options: [{ value: "", label: "Standard-Mikrofon des Systems" }].concat(live.mics.map(m => ({ value: m.id, label: m.name })))
                    value: live.mic
                    onPicked: (v) => live.setMic(v)
                }
            }
        }

        // ---- body
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 24

            ColumnLayout {
                Layout.fillWidth: false
                Layout.preferredWidth: Math.min(480, Math.max(290, page.width * 0.42))
                Layout.fillHeight: true
                spacing: 8

                SpeakerOrb {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(340, page.height * 0.42)
                    tint: page.someone ? page.sp.color : Theme.line2
                    initial: !page.someone ? "" : page.sp.name === "Nicht erkannte Stimme" ? "?" : page.sp.name.charAt(0).toUpperCase()
                    level: live.state === "recording" ? live.level : 0
                    active: page.someone && live.state === "recording"
                    busy: live.state === "starting" || live.state === "stopping"
                    clickable: page.canName
                    onClicked: nameDlg.ask(page.sp.key, page.sp.name)
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: live.state === "starting" ? "Startet …" : live.state === "stopping" ? "Wird gespeichert …"
                        : live.state === "paused" ? "Pausiert" : page.someone ? page.sp.name : "Stille"
                    font.family: Theme.display; font.pixelSize: 34; font.weight: Font.Black; font.letterSpacing: -1.2
                    color: Theme.fg
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: live.state === "starting" ? "Mikrofon und Erkennung starten – beim allerersten Mal dauert das etwas, nichts geht verloren."
                        : live.state === "stopping" ? "Gleich fertig – danach wertet REKORD alles noch einmal genau aus."
                        : page.canName ? "Antippen, um die Stimme zu benennen"
                        : page.someone ? "erkannt" : "Wartet auf die nächste Stimme …"
                    font.family: Theme.text; font.pixelSize: 14; color: page.canName ? Theme.accent : Theme.fg3
                }

                // roster: who talked how much
                ListView {
                    id: roster
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.topMargin: 10
                    clip: true
                    spacing: 6
                    interactive: contentHeight > height
                    model: live.roster
                    delegate: AbstractButton {
                        id: who
                        required property var modelData
                        width: roster.width
                        height: 50
                        hoverEnabled: true
                        enabled: !modelData.known && modelData.key >= 0
                        onClicked: nameDlg.ask(modelData.key, modelData.name)
                        background: Rectangle {
                            radius: 12
                            color: who.hovered ? Theme.card2 : Theme.card
                            border.width: 1
                            border.color: Theme.line
                        }
                        contentItem: Item {
                            Rectangle { id: wdot; width: 12; height: 12; radius: 6; color: who.modelData.color; anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                anchors.left: wdot.right
                                anchors.leftMargin: 10
                                anchors.right: share.left
                                anchors.rightMargin: 10
                                anchors.top: parent.top
                                anchors.topMargin: 8
                                elide: Text.ElideRight
                                text: who.modelData.name + (who.modelData.voices > 1 ? "  ·  " + who.modelData.voices + " Stimmen" : "")
                                font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold
                                color: who.modelData.waiting ? Theme.fg3 : Theme.fg
                            }
                            Rectangle {  // share bar
                                anchors.left: wdot.right
                                anchors.leftMargin: 10
                                anchors.right: share.left
                                anchors.rightMargin: 10
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 10
                                height: 4
                                radius: 2
                                color: Theme.card2
                                Rectangle {
                                    height: parent.height
                                    radius: 2
                                    width: parent.width * Math.min(1, who.modelData.share)
                                    color: who.modelData.color
                                    Behavior on width { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }
                                }
                            }
                            Text {
                                id: share
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                text: who.modelData.waiting ? "noch still" : who.enabled ? "benennen" : Math.round(who.modelData.share * 100) + " %"
                                font.family: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; font.features: ({ "tnum": 1 })
                                color: who.enabled ? Theme.accent : Theme.fg3
                            }
                        }
                        HoverHandler { cursorShape: who.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
                    }
                    add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.mid } }
                }
            }

            // ---- transcript
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radius
                color: Theme.card
                border.width: 1
                border.color: Theme.line
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 10
                    RowLayout {
                        Text { text: "MITSCHRIFT"; font.family: Theme.text; font.pixelSize: 12; font.weight: Font.Black; font.letterSpacing: 1.2; color: Theme.fg3 }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: live.highlights > 0
                            text: "★ " + live.highlights
                            font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.accent
                        }
                    }
                    ListView {
                        id: words
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 12
                        model: live.lines
                        property bool follow: true
                        onMovementEnded: follow = atYEnd
                        onCountChanged: if (follow) Qt.callLater(positionViewAtEnd)
                        ScrollBar.vertical: ScrollBar {}
                        delegate: ColumnLayout {
                            id: ln
                            required property string time
                            required property string name
                            required property string color
                            required property string text
                            required property bool gap  // a slow computer: the live text skipped ahead
                            width: words.width - 12
                            spacing: 2
                            RowLayout {
                                visible: !ln.gap
                                spacing: 8
                                Rectangle { width: 8; height: 8; radius: 4; color: ln.color }
                                Text { text: ln.name; font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.fg }
                                Text { text: ln.time; font.family: Theme.text; font.pixelSize: 12; font.features: ({ "tnum": 1 }); color: Theme.fg3 }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: ln.text
                                wrapMode: Text.WordWrap
                                font.family: Theme.text; font.pixelSize: ln.gap ? 13 : 16; font.italic: ln.gap
                                lineHeight: 1.08; color: ln.gap ? Theme.fg3 : Theme.fg
                            }
                        }
                        add: Transition {
                            ParallelAnimation {
                                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.slow }
                                NumberAnimation { property: "y"; from: words.contentHeight + 20; duration: Theme.slow; easing.type: Easing.OutCubic }
                            }
                        }
                        Text {
                            visible: words.count === 0
                            anchors.centerIn: parent
                            width: parent.width - 40
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: "Was gesagt wird, erscheint hier – ein paar Sekunden nach jedem Satz."
                            font.family: Theme.text; font.pixelSize: 14; color: Theme.fg3
                        }
                    }
                }
            }
        }

        // ---- controls
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 12
            Btn {
                text: "Markieren"
                iconName: "star"
                enabled: live.state === "recording"
                onClicked: live.highlight()
                ToolTip.visible: hovered
                ToolTip.delay: 400
                ToolTip.text: "Wichtiger Moment (H) – taucht in der Zusammenfassung auf"
            }
            Btn {
                text: live.state === "paused" ? "Weiter" : "Pause"
                iconName: live.state === "paused" ? "play" : "pause"
                enabled: live.state === "recording" || live.state === "paused"
                onClicked: live.state === "paused" ? live.resume() : live.pause()
                ToolTip.visible: hovered
                ToolTip.delay: 400
                ToolTip.text: "Leertaste"
            }
            Btn {
                kind: "primary"
                text: "Stopp & speichern"
                iconName: "stop"
                enabled: live.state === "recording" || live.state === "paused"
                implicitHeight: 46
                onClicked: live.stop()
            }
        }
    }
}
