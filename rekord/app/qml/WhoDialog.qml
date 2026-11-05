import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "."

// "Wer ist dabei?" before every recording: where (room / online / lecture), how many, who is known.
Sheet {
    id: dlg
    required property var app
    signal started()
    property string meeting: "person"
    property bool withMic: true   // online: your own microphone too – false = only the call's sound
    readonly property bool callOnly: meeting === "online" && live.callAvailable && !withMic
    property var ids: []
    property int total: 0
    readonly property bool lecture: meeting === "lecture"
    readonly property var known: people.items.filter(p => dlg.ids.indexOf(p.id) >= 0)
    readonly property int fresh: Math.max(0, total - ids.length)
    readonly property bool ready: lecture || total > 0

    function openFresh() {
        const w = live.lastWho
        meeting = w.meeting || "person"
        withMic = w.mic !== false
        const have = people.items.map(p => p.id)
        ids = (w.ids || []).filter(i => have.indexOf(i) >= 0)
        total = Math.max(w.total || 0, ids.length)
        titleField.text = ""
        people.refresh()
        open()
        titleField.forceActiveFocus()
    }
    function toggle(pid) {
        const next = ids.slice()
        const i = next.indexOf(pid)
        if (i >= 0) next.splice(i, 1)
        else { next.push(pid); total = Math.max(total, next.length) }
        ids = next
    }
    function go() {
        if (!ready) return
        live.start(titleField.text, meeting, ids, lecture ? ids.length : total, !callOnly)
        close()
        started()
    }

    contentItem: ColumnLayout {
        spacing: 18
        Keys.onReturnPressed: dlg.go()
        Keys.onEnterPressed: dlg.go()

        ColumnLayout {
            spacing: 4
            Text { text: "NEUE AUFNAHME"; font.family: Theme.text; font.pixelSize: 12; font.weight: Font.Black; font.letterSpacing: 1.2; color: Theme.accent }
            Text {
                text: "Wer ist dabei?"
                font.family: Theme.display; font.pixelSize: 34; font.weight: Font.Black; font.letterSpacing: -1.3
                color: Theme.fg
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: dlg.lecture ? "Ist die vortragende Person schon bekannt? Dann antippen – sonst einfach starten."
                    : "Damit REKORD weiß, wie viele Stimmen es trennen muss – und wen es schon kennt."
                font.family: Theme.text; font.pixelSize: 14; color: Theme.fg2
            }
        }

        TextField {
            id: titleField
            Layout.fillWidth: true
            placeholderText: "Titel (optional) – z. B. Team-Meeting, VO Statistik"
            font.family: Theme.text
            font.pixelSize: 15
            color: Theme.fg
            placeholderTextColor: Theme.fg3
            selectionColor: Theme.accent
            selectedTextColor: Theme.onAccent
            leftPadding: 14
            topPadding: 11
            bottomPadding: 11
            background: Rectangle {
                radius: 12
                color: Theme.bg
                border.width: titleField.activeFocus ? 2 : 1
                border.color: titleField.activeFocus ? Theme.accent : Theme.line
            }
            onAccepted: dlg.go()
        }

        Segmented {
            Layout.fillWidth: true
            model: [{ value: "person", label: "Vor Ort", icon: "room" }, { value: "online", label: "Online", icon: "online" },
                    { value: "lecture", label: "Vorlesung", icon: "lecture" }]
            value: dlg.meeting
            onPicked: (v) => dlg.meeting = v
        }
        Text {
            Layout.fillWidth: true
            Layout.topMargin: -6
            wrapMode: Text.WordWrap
            text: dlg.meeting === "person" ? "Alle im Raum – das Mikrofon reicht."
                : dlg.meeting === "online" ? (!live.callAvailable ? "Den Ton vom Computer kann REKORD hier nicht abgreifen – stell die Lautsprecher so, dass das Mikrofon mithört."
                                              : dlg.withMic ? "Teams, Zoom, Meet …: REKORD nimmt den Ton vom Computer auf – nur Ton, kein Bild – plus dein Mikrofon. Du bist mit drauf."
                                              : "Nur der Ton vom Computer – was Teams, Zoom, Meet … abspielen. Dein Mikrofon bleibt aus: du bist nicht drauf, Geräusche bei dir auch nicht.")
                : "Eine Person trägt vor, Fragen aus dem Hörsaal sammelt REKORD unter „Publikum“. Mitzählen musst du nicht. Mikro Richtung Vortrag."
            font.family: Theme.text; font.pixelSize: 14; color: Theme.fg3
        }

        // ---- online: with or without your own microphone
        ColumnLayout {
            visible: dlg.meeting === "online" && live.callAvailable
            Layout.fillWidth: true
            spacing: 8
            RowLayout {
                spacing: 6
                Text { text: "Dein Mikrofon auch aufnehmen?"; font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; color: Theme.fg }
                Tip { key: "callmic" }
            }
            Segmented {
                Layout.fillWidth: true
                model: [{ value: "both", label: "Call + mein Mikro", icon: "mic" }, { value: "call", label: "Nur Call-Ton", icon: "wave" }]
                value: dlg.withMic ? "both" : "call"
                onPicked: (v) => dlg.withMic = v === "both"
            }
        }

        // ---- how many
        ColumnLayout {
            visible: !dlg.lecture
            Layout.fillWidth: true
            spacing: 10
            Text { text: dlg.callOnly ? "Wie viele sind im Call zu hören – ohne dich?" : "Wie viele seid ihr – dich mitgezählt?"; font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; color: Theme.fg }
            RowLayout {
                spacing: 8
                Btn { small: true; iconName: "minus"; onClicked: dlg.total = Math.max(Math.max(1, dlg.ids.length), dlg.total - 1) }
                Text {
                    Layout.preferredWidth: 44
                    horizontalAlignment: Text.AlignHCenter
                    text: dlg.total || "–"
                    font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; font.features: ({ "tnum": 1 })
                    color: Theme.fg
                }
                Btn { small: true; iconName: "plus"; onClicked: dlg.total = Math.min(30, dlg.total + 1) }
                Item { width: 8 }
                Repeater {
                    model: [1, 2, 3, 4, 5, 6, 8]
                    delegate: Btn {
                        required property int modelData
                        small: true
                        text: String(modelData)
                        kind: dlg.total === modelData ? "primary" : "default"
                        onClicked: dlg.total = Math.max(modelData, dlg.ids.length)
                    }
                }
            }
        }

        // ---- who is known
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                text: dlg.lecture ? "Vortragende Person" : "Wer davon ist bekannt?"
                visible: people.items.length > 0
                font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; color: Theme.fg
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: people.items
                    delegate: Chip {
                        required property var modelData
                        text: modelData.name
                        dot: modelData.color
                        on: dlg.ids.indexOf(modelData.id) >= 0
                        onClicked: dlg.toggle(modelData.id)
                    }
                }
            }
            Text {
                visible: people.items.length === 0
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Noch niemand angelernt – alle zählen als neu. Während der Aufnahme kannst du jede Stimme antippen und benennen."
                font.family: Theme.text; font.pixelSize: 14; color: Theme.fg3
            }
        }

        // ---- summary
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: sumText.implicitHeight + 26
            radius: 12
            color: Theme.card2
            Text {
                id: sumText
                anchors.fill: parent
                anchors.margins: 13
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                font.family: Theme.text
                font.pixelSize: 14
                color: Theme.fg2
                text: {
                    const names = dlg.known.map(p => p.name)
                    if (dlg.lecture)
                        return "<b>Vortrag</b>: " + (names.length ? names.join(", ") : "wird an der Stimme erkannt") + " · alle anderen: Publikum"
                    if (!dlg.total)
                        return "<font color='" + Theme.accent + "'>Wähle oben, wie viele ihr seid.</font>"
                    const parts = [names.join(", "), dlg.fresh ? dlg.fresh + " neu" : ""].filter(x => x)
                    return "<b>" + dlg.total + (dlg.total === 1 ? " Person" : " Personen") + "</b>: " + parts.join(" + ")
                        + (dlg.fresh ? "<br>Neue Stimmen landen unter „Nicht erkannte Stimme“. Besser: jetzt kurz einsprechen lassen – dann erkennt REKORD sie mit Namen."
                                     : "<br>Geschlossene Runde: jede Stimme wird einer dieser Personen zugeordnet.")
                }
            }
        }
        RowLayout {  // Vorstellungsrunde: each new person says ~45 s, then counts as known
            visible: !dlg.lecture && dlg.fresh > 0
            Btn {
                small: true
                iconName: "mic"
                text: dlg.fresh === 1 ? "Neue Person jetzt einsprechen" : "Neue Personen jetzt einsprechen (" + dlg.fresh + ")"
                onClicked: {
                    const n = dlg.fresh
                    dlg.app.enroll({ intro: true, step: n > 1 ? "1 von " + n : "" }, (prof) => {
                        if (dlg.ids.indexOf(prof.id) < 0) dlg.ids = dlg.ids.concat([prof.id])
                        dlg.total = Math.max(dlg.total, dlg.ids.length)
                    })
                }
            }
            Tip { key: "intro" }
        }

        // ---- Unterlagen (optional): agenda, slides, attendee list – their names and terms are right from the first sentence
        ColumnLayout {
            objectName: "whoDocs"
            Layout.fillWidth: true
            spacing: 8
            FileDialog {
                id: docDlg
                title: "Unterlagen zur Aufnahme"
                fileMode: FileDialog.OpenFiles
                currentFolder: library.downloadsUrl
                nameFilters: [library.docFilter, "Alle Dateien (*)"]
                onAccepted: live.addDocs(selectedFiles)
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text { text: "Unterlagen"; font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; color: Theme.fg }
                Text { text: "optional"; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg3 }
                Item { Layout.fillWidth: true }
                Btn { objectName: "whoDocsAdd"; small: true; iconName: "plus"; text: "PDF, Folien, Dokumente …"; onClicked: docDlg.open() }
            }
            Text {
                visible: live.docs.length === 0
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Agenda, Folien, Teilnehmerliste: Namen und Fachbegriffe daraus schreibt REKORD richtig – schon live. Bleibt auf diesem Rechner."
                font.family: Theme.text; font.pixelSize: 13; color: Theme.fg3
            }
            Flow {
                visible: live.docs.length > 0
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: live.docs
                    delegate: Rectangle {
                        id: dchip
                        required property string modelData
                        required property int index
                        height: 32
                        width: dRow.implicitWidth + 22
                        radius: 16
                        color: Theme.card2
                        border.width: 1
                        border.color: Theme.line
                        RowLayout {
                            id: dRow
                            anchors.verticalCenter: parent.verticalCenter
                            x: 12
                            spacing: 8
                            Text { text: dchip.modelData; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg; elide: Text.ElideMiddle; Layout.maximumWidth: 260 }
                            AbstractButton {
                                implicitWidth: 18; implicitHeight: 18
                                onClicked: live.removeDoc(dchip.index)
                                contentItem: Icon { name: "close"; width: 12; height: 12; color: Theme.fg3 }
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: dlg.close() }
            Btn { kind: "primary"; text: "Aufnahme starten"; iconName: "record"; enabled: dlg.ready; onClicked: dlg.go() }
        }
    }
}
