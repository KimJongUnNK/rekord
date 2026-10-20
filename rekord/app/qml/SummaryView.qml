import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "."

// Protocols, to-dos, decisions – one card per template; the AI's text appears while it writes.
Item {
    id: v
    required property var page
    property string tpl: "auto"
    property bool busy: false
    property string streamText: ""
    property string streamTitle: ""
    readonly property var list: page.rec ? page.rec.summaries.filter(s => s.template_id !== "mindmap") : []
    readonly property bool hasText: page.rec && page.rec.segments.length > 0
    readonly property bool noAi: !rekord.status.ai

    function generate() {
        const t = page.templates.find(x => x.id === tpl)
        busy = true; streamText = ""; streamTitle = t ? t.name : tpl
        page.app.stream("/api/recordings/" + page.rid + "/summaries", { template_id: tpl },
                        (txt) => v.streamText = txt,
                        () => { v.busy = false; v.streamText = ""; v.page.reload() },
                        (err) => { v.busy = false; v.streamText = "**Fehler:** " + err })
    }

    TextDialog { id: editDlg }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Select {
                Layout.preferredWidth: 340
                options: v.page.templates.filter(t => t.id !== "mindmap").map(t => ({ value: t.id, label: t.name + " · " + t.category }))
                value: v.tpl
                onPicked: (x) => v.tpl = x
            }
            Btn { kind: "primary"; text: v.busy ? "Schreibt …" : "Zusammenfassen"; iconName: "spark"; enabled: v.hasText && !v.busy; onClicked: v.generate() }
            Muted {
                Layout.fillWidth: true
                font.pixelSize: 13
                text: "Mehrere Vorlagen = mehrere Blickwinkel auf dasselbe Gespräch."
            }
            Btn { kind: "ghost"; small: true; text: "Vorlagen verwalten"; onClicked: v.page.app.go("templates") }
        }
        Card {
            visible: v.noAi
            Layout.fillWidth: true
            Layout.preferredHeight: noAiRow.implicitHeight + 28
            RowLayout {
                id: noAiRow
                anchors.fill: parent
                anchors.margins: 14
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: (rekord.status.aiProblem || "Keine KI verbunden") + "."; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Muted { text: "Transkript und Sprecher funktionieren auch ohne KI."; font.pixelSize: 13 }
                }
                Btn { text: "KI verbinden"; iconName: "spark"; onClicked: v.page.app.go("settings", "ai") }
            }
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: parent.width
                spacing: 14
                Card {  // the one being written right now
                    visible: v.busy || v.streamText !== ""
                    Layout.fillWidth: true
                    Layout.preferredHeight: liveCol.implicitHeight + 36
                    border.color: Theme.accent
                    ColumnLayout {
                        id: liveCol
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 10
                        RowLayout {
                            Eyebrow { text: v.streamTitle }
                            BusyIndicator { running: v.busy; visible: v.busy; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                        }
                        Markdown { Layout.fillWidth: true; source: v.streamText || "…"; onSeek: (s) => player.seekPlay(s) }
                    }
                }
                Repeater {
                    model: v.list
                    delegate: Card {
                        id: sc
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: sCol.implicitHeight + 36
                        ColumnLayout {
                            id: sCol
                            anchors.fill: parent
                            anchors.margins: 18
                            spacing: 10
                            RowLayout {
                                Layout.fillWidth: true
                                Eyebrow { text: sc.modelData.title }
                                Muted { text: (sc.modelData.model ? sc.modelData.model + " · " : "") + new Date(sc.modelData.created_at * 1000).toLocaleString(Qt.locale("de_AT"), "dd.MM.yyyy HH:mm"); font.pixelSize: 12; color: Theme.fg3 }
                                Item { Layout.fillWidth: true }
                                Btn { kind: "ghost"; small: true; text: "Kopieren"; onClicked: { api.copyText(sc.modelData.content); v.page.app.toast("Kopiert (Markdown)") } }
                                Btn { kind: "ghost"; small: true; text: "Bearbeiten"; onClicked: editDlg.edit(sc.modelData.title, sc.modelData.content, (t) => v.page.app.call("PATCH", "/api/summaries/" + sc.modelData.id, { content: t }, () => v.page.reload())) }
                                Btn {
                                    kind: "ghost"; small: true; iconName: "close"
                                    ToolTip.visible: hovered; ToolTip.text: "Löschen"
                                    onClicked: v.page.app.confirm("Zusammenfassung löschen?", sc.modelData.title, "Löschen",
                                                                  () => v.page.app.call("DELETE", "/api/summaries/" + sc.modelData.id, null, () => v.page.reload()))
                                }
                            }
                            Markdown {
                                Layout.fillWidth: true
                                source: sc.modelData.content
                                onSeek: (s) => player.seekPlay(s)
                                onOpenRecording: (rid, s) => v.page.app.openRecording(rid, s)
                                onTask: (line) => {
                                    const c = rekord.toggleTask(sc.modelData.content, line)
                                    sc.modelData.content = c
                                    source = c
                                    v.page.app.call("PATCH", "/api/summaries/" + sc.modelData.id, { content: c }, () => {})
                                }
                            }
                        }
                    }
                }
                ColumnLayout {
                    visible: v.list.length === 0 && !v.busy
                    Layout.fillWidth: true
                    Layout.topMargin: 40
                    spacing: 8
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: v.hasText ? "Noch keine Zusammenfassung." : "Wartet auf das Transkript …"
                        font.family: Theme.display; font.pixelSize: 22; font.weight: Font.Black; color: Theme.fg
                    }
                    Muted { Layout.alignment: Qt.AlignHCenter; visible: v.hasText; text: "Vorlage wählen und los." }
                }
            }
        }
    }
}
