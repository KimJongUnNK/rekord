import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// One recording: who talked how much, the summaries, the transcript.
Page {
    id: page
    required property var app
    property int tab: 0

    Connections {
        target: detail
        function onChanged() { if (page.tab === 0 && detail.summaries.length === 0 && detail.lines.count > 0) page.tab = 1 }
    }
    onShownChanged: if (shown) tab = 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        anchors.bottomMargin: 0
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            Btn { kind: "ghost"; small: true; iconName: "back"; text: "Aufnahmen"; onClicked: page.app.go("library") }
            Item { Layout.fillWidth: true }
            Btn {
                small: true
                iconName: "open"
                text: "Bearbeiten, Fragen, Export"
                onClicked: rekord.openClassic("r/" + detail.rid)
                ToolTip.visible: hovered
                ToolTip.delay: 400
                ToolTip.text: "Öffnet diese Aufnahme in der bisherigen Ansicht – zieht als Nächstes in die neue App um."
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                Layout.fillWidth: true
                text: detail.title || "Ohne Titel"
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.family: Theme.display
                font.pixelSize: 38
                font.weight: Font.Black
                font.letterSpacing: -1.6
                color: Theme.fg
            }
            Text {
                text: detail.meta
                font.family: Theme.text
                font.pixelSize: 14
                font.features: ({ "tnum": 1 })
                color: Theme.fg3
            }
        }

        // ---- who talked how much
        ColumnLayout {
            visible: detail.speakers.length > 0
            Layout.fillWidth: true
            spacing: 10
            Row {  // one bar, a segment per person
                Layout.fillWidth: true
                Layout.preferredHeight: 10
                spacing: 3
                Repeater {
                    model: detail.speakers
                    delegate: Rectangle {
                        required property var modelData
                        height: 10
                        radius: 5
                        width: Math.max(6, (page.width - 72 - 3 * detail.speakers.length) * modelData.share)
                        color: modelData.color
                    }
                }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 16
                Repeater {
                    model: detail.speakers
                    delegate: Row {
                        required property var modelData
                        spacing: 7
                        Rectangle { width: 10; height: 10; radius: 5; color: modelData.color; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: modelData.name; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold; color: Theme.fg }
                        Text { text: Math.round(modelData.share * 100) + " %"; font.family: Theme.text; font.pixelSize: 14; color: Theme.fg3 }
                    }
                }
            }
        }

        // ---- processing
        Rectangle {
            visible: detail.status === "queued" || detail.status === "processing"
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            radius: 12
            color: Theme.accentSoft
            RowLayout {
                anchors.fill: parent
                anchors.margins: 16
                BusyIndicator { running: parent.visible; Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
                Text {
                    Layout.fillWidth: true
                    text: "Wird genau ausgewertet – wer wann was gesagt hat. Das Ergebnis erscheint hier von selbst."
                    wrapMode: Text.WordWrap
                    font.family: Theme.text; font.pixelSize: 14; color: Theme.fg
                }
            }
        }

        Segmented {
            Layout.preferredWidth: 360
            model: [{ value: "0", label: "Zusammenfassung" }, { value: "1", label: "Transkript" }]
            value: String(page.tab)
            onPicked: (v) => page.tab = Number(v)
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: page.tab

            // ---- summaries
            ScrollView {
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: parent.width
                    spacing: 16
                    Repeater {
                        model: detail.summaries
                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: sumCol.implicitHeight + 44
                            radius: Theme.radius
                            color: Theme.card
                            border.width: 1
                            border.color: Theme.line
                            ColumnLayout {
                                id: sumCol
                                anchors.fill: parent
                                anchors.margins: 22
                                spacing: 10
                                Text {
                                    text: modelData.title.toUpperCase()
                                    font.family: Theme.text; font.pixelSize: 12; font.weight: Font.Black; font.letterSpacing: 1.2
                                    color: Theme.accent
                                }
                                TextEdit {
                                    Layout.fillWidth: true
                                    text: modelData.content
                                    textFormat: TextEdit.MarkdownText
                                    readOnly: true
                                    selectByMouse: true
                                    wrapMode: TextEdit.Wrap
                                    font.family: Theme.text
                                    font.pixelSize: 15
                                    color: Theme.fg
                                    selectionColor: Theme.accent
                                    selectedTextColor: Theme.onAccent
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        visible: detail.summaries.length === 0
                        Layout.fillWidth: true
                        Layout.topMargin: 30
                        spacing: 10
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: "Noch keine Zusammenfassung"
                            font.family: Theme.display; font.pixelSize: 22; font.weight: Font.Black; color: Theme.fg
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.maximumWidth: 460
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            text: rekord.status.ai ? "Sie entsteht von selbst, sobald die Aufnahme ausgewertet ist." : "Verbinde eine KI (Claude, ChatGPT oder lokal mit Ollama) – dann fasst REKORD jedes Gespräch zusammen."
                            font.family: Theme.text; font.pixelSize: 14; color: Theme.fg2
                        }
                        Btn {
                            visible: !rekord.status.ai
                            Layout.alignment: Qt.AlignHCenter
                            text: "KI verbinden"
                            iconName: "spark"
                            onClicked: rekord.openClassic("settings?s=ai")
                        }
                    }
                }
            }

            // ---- transcript
            ListView {
                id: lines
                clip: true
                model: detail.lines
                spacing: 14
                bottomMargin: 36
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: RowLayout {
                    id: line
                    required property string time
                    required property string name
                    required property string color
                    required property string text
                    width: lines.width - 14
                    spacing: 14
                    Text {
                        Layout.preferredWidth: 52
                        Layout.alignment: Qt.AlignTop
                        Layout.topMargin: 2
                        text: time
                        font.family: Theme.text; font.pixelSize: 13; font.features: ({ "tnum": 1 }); color: Theme.fg3
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text { text: name; font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: line.color }
                        TextEdit {
                            Layout.fillWidth: true
                            text: line.text
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            font.family: Theme.text; font.pixelSize: 15; color: Theme.fg
                            selectionColor: Theme.accent
                            selectedTextColor: Theme.onAccent
                        }
                    }
                }
                Text {
                    visible: lines.count === 0
                    anchors.centerIn: parent
                    text: detail.status === "done" ? "In dieser Aufnahme wurde nichts gesagt." : "Das Transkript erscheint, sobald die Auswertung fertig ist."
                    font.family: Theme.text; font.pixelSize: 14; color: Theme.fg3
                }
            }
        }
    }
}
