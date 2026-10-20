import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Aufnahmen: search, folders, import, open.
Page {
    id: page
    required property var app
    function focusSearch() { search.forceActiveFocus(); search.selectAll() }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        anchors.bottomMargin: 0
        spacing: 20

        // ---- header
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                spacing: 2
                Text {
                    text: "Aufnahmen"
                    font.family: Theme.display
                    font.pixelSize: 44
                    font.weight: Font.Black
                    font.letterSpacing: -2
                    color: Theme.fg
                }
                Text {
                    text: library.model.count === 0 ? (library.query ? "Nichts gefunden" : "Noch leer")
                        : library.model.count + (library.model.count === 1 ? " Gespräch" : " Gespräche") + (library.query ? " gefunden" : "")
                    font.family: Theme.text
                    font.pixelSize: 14
                    color: Theme.fg3
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {  // search
                Layout.preferredWidth: Math.min(340, page.width * 0.32)
                Layout.preferredHeight: 42
                radius: 12
                color: Theme.card
                border.width: search.activeFocus ? 2 : 1
                border.color: search.activeFocus ? Theme.accent : Theme.line
                Behavior on border.color { ColorAnimation { duration: Theme.fast } }
                Icon { id: sIcon; name: "search"; width: 18; height: 18; color: Theme.fg3; anchors.left: parent.left; anchors.leftMargin: 13; anchors.verticalCenter: parent.verticalCenter }
                TextField {
                    id: search
                    anchors.left: sIcon.right
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 4
                    anchors.rightMargin: 8
                    placeholderText: "Suchen – auch im Gesagten (Strg+F)"
                    placeholderTextColor: Theme.fg3
                    color: Theme.fg
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.onAccent
                    font.family: Theme.text
                    font.pixelSize: 14
                    background: null
                    onTextChanged: library.search(text)
                    Keys.onEscapePressed: { text = ""; focus = false }
                }
            }
            Btn {
                text: "Importieren"
                iconName: "import"
                onClicked: page.app.importFiles()
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: "Audio- oder Videodateien (Strg+I) – oder einfach ins Fenster ziehen"
            }
        }

        // ---- first start / storage
        Rectangle {
            visible: rekord.status.storageMissing || rekord.status.welcomeDone === false || (rekord.status.ready === false && !rekord.status.downloading)
            Layout.fillWidth: true
            Layout.preferredHeight: setupRow.implicitHeight + 36
            radius: Theme.radius
            color: Theme.accentSoft
            border.width: 1
            border.color: Qt.rgba(1, 0.353, 0.122, 0.35)
            RowLayout {
                id: setupRow
                anchors.fill: parent
                anchors.margins: 18
                spacing: 16
                Icon { name: "spark"; width: 26; height: 26; color: Theme.accent }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: rekord.status.storageMissing ? "Der Speicherort ist nicht verbunden" : "Einmal einrichten – dann läuft alles von selbst"
                        font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Bold; color: Theme.fg
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: rekord.status.storageMissing ? "Steck das Laufwerk an, auf dem deine Aufnahmen liegen – oder wähle einen anderen Ort."
                            : "Speicherort wählen, Spracherkennung laden (einmalig, ~500 MB) und optional eine KI für Zusammenfassungen verbinden."
                        font.family: Theme.text; font.pixelSize: 14; color: Theme.fg2
                    }
                }
                Btn {
                    kind: "primary"
                    text: rekord.status.storageMissing ? "Speicherort" : "Einrichten"
                    onClicked: rekord.openClassic(rekord.status.storageMissing ? "settings?s=data" : "")
                }
            }
        }

        // ---- folders
        Flow {
            visible: library.folders.length > 0
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: [""].concat(library.folders)
                delegate: Chip {
                    required property string modelData
                    text: modelData || "Alle"
                    dot: modelData ? Theme.fg3 : Theme.accent
                    on: library.folder === modelData
                    onClicked: library.setFolder(modelData)
                }
            }
        }

        // ---- list
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            model: library.model
            bottomMargin: 36
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: RecordingRow {
                width: list.width - 14
                onClicked: page.app.openRecording(rid)
            }
            add: Transition {
                ParallelAnimation {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.mid }
                    NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.mid; easing.type: Easing.OutCubic }
                }
            }
            displaced: Transition { NumberAnimation { properties: "y"; duration: Theme.mid; easing.type: Easing.OutCubic } }

            // empty state
            ColumnLayout {
                visible: list.count === 0
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 460)
                spacing: 14
                Rectangle {
                    id: pulse1
                    Layout.alignment: Qt.AlignHCenter
                    width: 84; height: 84; radius: 42
                    color: Theme.accentSoft
                    Icon { anchors.centerIn: parent; width: 36; height: 36; name: library.query ? "search" : "live"; color: Theme.accent }
                    SequentialAnimation on scale {
                        onRunningChanged: if (!running) pulse1.scale = 1
                        running: list.count === 0 && page.shown
                        loops: Animation.Infinite
                        NumberAnimation { to: 1.06; duration: 1400; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1; duration: 1400; easing.type: Easing.InOutSine }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: library.query ? "Nichts zu „" + library.query + "“" : "Noch keine Aufnahmen"
                    font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; font.letterSpacing: -0.8
                    color: Theme.fg
                    wrapMode: Text.WordWrap
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: library.query ? "Gesucht wird in Titeln, Notizen und allem, was gesagt wurde."
                        : "Drück auf „Aufnehmen“ – oder zieh eine Audio- oder Videodatei in dieses Fenster."
                    font.family: Theme.text; font.pixelSize: 15; color: Theme.fg2
                }
                Btn {
                    visible: !library.query
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 6
                    kind: "primary"
                    text: "Aufnehmen"
                    iconName: "record"
                    onClicked: page.app.startRecording()
                }
            }
        }
    }
}
