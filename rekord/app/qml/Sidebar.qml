import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Left column: brand, the big record button, navigation, status.
Rectangle {
    id: side
    required property var app
    readonly property bool narrow: width < 150
    color: Theme.bg2
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.line }

    readonly property var items: [
        { page: "library", label: "Aufnahmen", icon: "library", tip: "Alle Gespräche – suchen, importieren, öffnen" },
        { page: "live", label: "Live", icon: "live", tip: "Aufnehmen und live sehen, wer spricht" },
        { page: "ask", label: "Fragen", icon: "ask", tip: "Fragen über alle Aufnahmen" },
        { page: "people", label: "Personen", icon: "people", tip: "Die Stimmen, die REKORD kennt" },
        { page: "templates", label: "Vorlagen", icon: "templates", tip: "Formate für Zusammenfassungen" },
        { page: "settings", label: "Einstellungen", icon: "settings", tip: "Mikrofon, KI, Speicherort, iPhone …" }
    ]
    readonly property string current: side.app.page === "detail" ? "library" : side.app.page
    readonly property bool recording: live.state === "recording" || live.state === "paused" || live.state === "starting" || live.state === "stopping"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: side.narrow ? 12 : 16
        anchors.topMargin: 22
        spacing: 18

        // ---- brand
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            Row {
                anchors.left: parent.left
                anchors.leftMargin: side.narrow ? 0 : 8
                anchors.horizontalCenter: side.narrow ? parent.horizontalCenter : undefined
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                Text {
                    text: side.narrow ? "R" : "REKORD"
                    font.family: Theme.display
                    font.pixelSize: 27
                    font.weight: Font.Black
                    font.letterSpacing: -1.3
                    color: Theme.fg
                }
                Rectangle {
                    id: pulse2
                    width: 9; height: 9; radius: 4.5
                    color: Theme.accent
                    y: 4
                    SequentialAnimation on opacity {
                        onRunningChanged: if (!running) pulse2.opacity = 1
                        running: side.recording
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.25; duration: 600 }
                        NumberAnimation { to: 1; duration: 600 }
                    }
                }
            }
        }

        // ---- record
        Button {
            id: rec
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            hoverEnabled: true
            focusPolicy: Qt.TabFocus
            onClicked: side.app.startRecording()
            ToolTip.visible: hovered && side.narrow
            ToolTip.text: "Aufnehmen (Strg+R)"
            scale: down ? 0.97 : 1
            Behavior on scale { NumberAnimation { duration: 90 } }
            background: Rectangle {
                radius: 14
                color: side.recording ? Theme.fg : rec.hovered ? Qt.lighter(Theme.accent, 1.07) : Theme.accent
                Behavior on color { ColorAnimation { duration: Theme.mid } }
            }
            contentItem: Item {
                RowLayout {
                    anchors.centerIn: parent
                    spacing: 10
                    Rectangle {
                        id: pulse3
                        width: 12; height: 12; radius: 6
                        color: side.recording ? Theme.accent : Theme.onAccent
                        SequentialAnimation on scale {
                            onRunningChanged: if (!running) pulse3.scale = 1
                            running: live.state === "recording"
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.6; duration: 650; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1; duration: 650; easing.type: Easing.InOutSine }
                        }
                    }
                    Text {
                        visible: !side.narrow
                        text: live.state === "recording" ? live.elapsedText : live.state === "paused" ? "Pausiert"
                            : live.state === "starting" ? "Startet …" : live.state === "stopping" ? "Speichert …" : "Aufnehmen"
                        font.family: Theme.text
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        font.features: ({ "tnum": 1 })
                        color: side.recording ? Theme.bg : Theme.onAccent
                    }
                }
            }
            HoverHandler { cursorShape: Qt.PointingHandCursor }
        }

        // ---- navigation
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: nav.implicitHeight
            Rectangle {  // the highlight slides to the current page
                id: pill
                width: parent.width
                height: 42
                radius: 11
                color: Theme.fg
                readonly property int idx: Math.max(0, side.items.findIndex(i => i.page === side.current))
                y: idx * 44
                Behavior on y { SpringAnimation { spring: 4.5; damping: 0.35; epsilon: 0.25 } }
            }
            Column {
                id: nav
                width: parent.width
                spacing: 2
                Repeater {
                    model: side.items
                    delegate: AbstractButton {
                        id: navItem
                        required property var modelData
                        width: nav.width
                        height: 42
                        hoverEnabled: true
                        focusPolicy: Qt.TabFocus
                        readonly property bool on: side.current === modelData.page
                        onClicked: side.app.go(modelData.page)
                        ToolTip.visible: hovered && side.narrow
                        ToolTip.text: modelData.label
                        ToolTip.delay: 300
                        background: Rectangle {
                            radius: 11
                            color: !navItem.on && navItem.hovered ? Theme.card : "transparent"
                            border.width: navItem.visualFocus ? 2 : 0
                            border.color: Theme.accent
                        }
                        contentItem: Item {
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: side.narrow ? 0 : 12
                                spacing: 12
                                Item {
                                    Layout.preferredWidth: side.narrow ? navItem.width : 20
                                    Layout.preferredHeight: 20
                                    Icon {
                                        anchors.centerIn: parent
                                        width: 20; height: 20
                                        name: navItem.modelData.icon
                                        color: navItem.on ? Theme.bg : Theme.fg2
                                    }
                                    Rectangle {  // recording indicator on "Live"
                                        visible: navItem.modelData.page === "live" && side.recording
                                        width: 8; height: 8; radius: 4
                                        color: Theme.accent
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.rightMargin: side.narrow ? navItem.width / 2 - 14 : -3
                                    }
                                }
                                Text {
                                    visible: !side.narrow
                                    Layout.fillWidth: true
                                    text: navItem.modelData.label
                                    font.family: Theme.text
                                    font.pixelSize: 15
                                    font.weight: Font.DemiBold
                                    color: navItem.on ? Theme.bg : Theme.fg2
                                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                                }
                            }
                        }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        // ---- update
        Rectangle {
            visible: !side.narrow && !!rekord.status.update
            Layout.fillWidth: true
            Layout.preferredHeight: upCol.implicitHeight + 24
            radius: 12
            color: Theme.accentSoft
            border.width: 1
            border.color: Qt.rgba(1, 0.353, 0.122, 0.35)
            ColumnLayout {
                id: upCol
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8
                Text {
                    Layout.fillWidth: true
                    text: rekord.status.updateState === "downloading" ? "Update " + rekord.status.update + " lädt … " + Math.round((rekord.status.updateProgress || 0) * 100) + " %"
                        : rekord.status.updateState === "installing" || rekord.status.updateState === "restarting" ? "Update wird installiert …"
                        : "Neue Version " + rekord.status.update
                    wrapMode: Text.WordWrap
                    font.family: Theme.text
                    font.pixelSize: 13
                    font.weight: Font.Bold
                    color: Theme.fg
                }
                Btn {
                    visible: !rekord.status.updateState || rekord.status.updateState === "idle" || rekord.status.updateState === "error"
                    small: true
                    kind: "primary"
                    text: "Jetzt aktualisieren"
                    iconName: "download"
                    Layout.fillWidth: true
                    onClicked: rekord.installUpdate()
                }
            }
        }

        // ---- status + theme
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                id: pulse4
                width: 8; height: 8; radius: 4
                Layout.alignment: Qt.AlignTop
                Layout.topMargin: 5
                Layout.leftMargin: side.narrow ? 0 : 8
                visible: !side.narrow
                color: rekord.status.storageMissing ? Theme.err : !rekord.status.ready || rekord.status.pending ? Theme.accent : Theme.ok
                SequentialAnimation on opacity {
                    onRunningChanged: if (!running) pulse4.opacity = 1
                    running: !rekord.status.ready || rekord.status.pending > 0
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.3; duration: 700 }
                    NumberAnimation { to: 1; duration: 700 }
                }
            }
            Text {
                visible: !side.narrow
                Layout.fillWidth: true
                text: rekord.status.storageMissing ? "Speicherort nicht verbunden"
                    : rekord.status.downloading ? "Lädt " + rekord.status.downloading
                    : !rekord.status.ready ? "Spracherkennung fehlt noch"
                    : rekord.status.pending ? rekord.status.pending + " in Arbeit"
                    : "Bereit · " + (rekord.status.ai ? "KI: " + rekord.status.ai : "keine KI")
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.family: Theme.text
                font.pixelSize: 12
                color: Theme.fg3
            }
            Btn {
                kind: "ghost"
                small: true
                iconName: Theme.mode === "light" ? "sun" : Theme.mode === "dark" ? "moon" : "auto"
                Layout.alignment: side.narrow ? Qt.AlignHCenter : Qt.AlignRight
                ToolTip.visible: hovered
                ToolTip.delay: 400
                ToolTip.text: Theme.mode === "light" ? "Hell" : Theme.mode === "dark" ? "Dunkel" : "Wie das System"
                onClicked: rekord.setTheme(Theme.mode === "system" ? "light" : Theme.mode === "light" ? "dark" : "system")
            }
        }
        Text {
            visible: !side.narrow
            Layout.leftMargin: 8
            text: "Version " + rekord.version
            font.family: Theme.text
            font.pixelSize: 12
            color: Theme.fg3
            opacity: 0.8
        }
    }
}
