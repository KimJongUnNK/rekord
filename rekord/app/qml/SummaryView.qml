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
    property real progress: 0          // the bar while summarizing: 0…1
    property string progressLabel: ""
    property string streamTitle: ""
    readonly property var list: page.rec ? page.rec.summaries.filter(s => s.template_id !== "mindmap") : []
    readonly property bool hasText: page.rec && page.rec.segments.length > 0
    readonly property bool noAi: !rekord.status.ai
    // the full analysis still runs: the live transcript has gaps – the summary is written once it's complete
    readonly property bool analyzing: page.busy
    property var later: []  // templates asked for meanwhile
    property var pinned: null  // the card whose header has scrolled out of view – its buttons stay on top
    Connections { target: v.page; function onRidChanged() { v.later = [] } }

    function askLater() {
        const t = page.templates.find(x => x.id === tpl)
        const name = t ? t.name : tpl
        page.app.call("POST", "/api/recordings/" + page.rid + "/summaries/later", { template_id: tpl }, (r) => {
            if (v.later.indexOf(name) < 0) v.later = v.later.concat([name])
            page.app.toast(r.queued ? "Vorgemerkt – „" + name + "“ entsteht, sobald das Transkript vollständig ist."
                                    : "„" + name + "“ kommt sowieso: automatisch nach der Auswertung.")
        })
    }

    function generate() {
        const t = page.templates.find(x => x.id === tpl)
        busy = true; streamText = ""; streamTitle = t ? t.name : tpl; progress = 0; progressLabel = "Startet …"
        page.app.stream("/api/recordings/" + page.rid + "/summaries", { template_id: tpl },
                        (txt) => v.streamText = txt,
                        () => { v.busy = false; v.streamText = ""; v.page.reload() },
                        (err) => { v.busy = false; v.streamText = "**Fehler:** " + err },
                        (p, label) => { v.progress = Math.max(v.progress, p); v.progressLabel = label })
    }

    RichEditor { id: richDlg }

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
            Btn {
                kind: "primary"
                text: v.busy ? "Schreibt …" : v.analyzing ? "Nach der Auswertung" : "Zusammenfassen"
                iconName: "spark"
                enabled: (v.hasText || v.analyzing) && !v.busy && !v.noAi
                onClicked: v.analyzing ? v.askLater() : v.generate()
            }
            Muted {
                Layout.fillWidth: true
                font.pixelSize: 13
                wrapMode: Text.WordWrap
                text: !v.analyzing ? "Mehrere Vorlagen = mehrere Blickwinkel auf dasselbe Gespräch."
                    : v.later.length ? "Vorgemerkt: " + v.later.join(", ") + " – entsteht automatisch, sobald das Transkript vollständig ist."
                    : "Die genaue Auswertung läuft noch – erst danach ist das Transkript vollständig. Zusammenfassen merkt die Vorlage vor."
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
        Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        ScrollView {
            id: scroll
            anchors.fill: parent
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
                        ColumnLayout {  // how far it is: preparing (long recordings: piece by piece), then writing
                            objectName: "summaryProgress"
                            visible: v.busy
                            Layout.fillWidth: true
                            spacing: 6
                            Bar { objectName: "summaryProgressBar"; Layout.fillWidth: true; value: v.progress }
                            RowLayout {
                                Layout.fillWidth: true
                                Muted { Layout.fillWidth: true; font.pixelSize: 12; text: v.progressLabel; elide: Text.ElideRight }
                                Muted { font.pixelSize: 12; text: Math.round(v.progress * 100) + " %" }
                            }
                        }
                        Markdown {  // what the AI writes – the status line already stands under the bar
                            visible: v.streamText !== "" && v.streamText !== "*" + v.progressLabel + "*"
                            Layout.fillWidth: true; source: v.streamText; onSeek: (s) => player.seekPlay(s)
                        }
                    }
                }
                Repeater {
                    model: v.list
                    delegate: Card {
                        id: sc
                        required property var modelData
                        // long summary scrolled past its header: the bar sticks to the top until the card ends
                        readonly property real viewTop: scroll.contentItem ? scroll.contentItem.contentY : 0
                        readonly property bool headerGone: sc.y + sCol.y + 30 < viewTop && sc.y + sc.height - 90 > viewTop
                        onHeaderGoneChanged: { if (headerGone) v.pinned = sc; else if (v.pinned === sc) v.pinned = null }
                        Component.onDestruction: if (v.pinned === sc) v.pinned = null
                        function copy() { api.copyRich(sc.modelData.content, sc.modelData.rich || ""); v.page.app.toast("Kopiert – mit Formatierung") }
                        function edit() {
                            richDlg.edit(sc.modelData.title, sc.modelData.content, sc.modelData.rich || "",
                                         (md, html) => v.page.app.call("PATCH", "/api/summaries/" + sc.modelData.id, { content: md, rich: html },
                                                                       () => { v.page.app.toast("Gespeichert"); v.page.reload() }))
                        }
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
                                Btn {
                                    objectName: "summaryCopy"
                                    kind: "ghost"; small: true; text: "Kopieren"
                                    ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Mit Formatierung – in Word, Pages oder Google Docs einfügen, fett bleibt fett"
                                    onClicked: sc.copy()
                                }
                                Btn {
                                    objectName: "summaryEdit"
                                    kind: "ghost"; small: true; text: "Bearbeiten"
                                    onClicked: sc.edit()
                                }
                                Btn {
                                    kind: "ghost"; small: true; iconName: "close"
                                    ToolTip.visible: hovered; ToolTip.text: "Löschen"
                                    onClicked: v.page.app.confirm("Zusammenfassung löschen?", sc.modelData.title, "Löschen",
                                                                  () => v.page.app.call("DELETE", "/api/summaries/" + sc.modelData.id, null, () => v.page.reload()))
                                }
                            }
                            RowLayout {  // tell the AI what to change: "keine Sternchen", "kürzer", "To-dos als Tabelle", "mit Emojis"
                                Layout.fillWidth: true
                                spacing: 8
                                property bool busy: false
                                id: aiRow
                                function run() {
                                    const t = aiField.text.trim()
                                    if (!t || busy) return
                                    busy = true
                                    v.page.app.call("POST", "/api/summaries/" + sc.modelData.id + "/ai", { instruction: t }, () => {
                                        aiRow.busy = false
                                        aiField.text = ""
                                        v.page.app.toast("Geändert – „Rückgängig“ holt die vorige Fassung zurück.")
                                        v.page.reload()
                                    }, (err) => { aiRow.busy = false; v.page.app.toast("KI: " + err) })
                                }
                                Input {
                                    id: aiField
                                    objectName: "summaryAi"
                                    Layout.fillWidth: true
                                    enabled: !aiRow.busy
                                    placeholderText: "Sag der KI, was sie ändern soll – z. B. „keine Sternchen“, „kürzer“, „Spiegelstriche statt Punkte“, „To-dos als Tabelle“"
                                    onAccepted: aiRow.run()
                                }
                                BusyIndicator { visible: aiRow.busy; running: visible; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                                Btn { kind: "primary"; small: true; iconName: "spark"; text: "Ändern"; enabled: !aiRow.busy && aiField.text.trim() !== ""; onClicked: aiRow.run() }
                                Btn {
                                    objectName: "summaryUndo"
                                    visible: !!sc.modelData.prev
                                    kind: "ghost"; small: true; text: "↶ Rückgängig"
                                    ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Zur Fassung vor der letzten KI-Änderung – nochmal klicken: wieder zurück"
                                    onClicked: v.page.app.call("POST", "/api/summaries/" + sc.modelData.id + "/undo", null, () => { v.page.app.toast("Rückgängig"); v.page.reload() })
                                }
                            }
                            TextEdit {  // formatted in the editor: shown exactly like that
                                visible: !!sc.modelData.rich
                                Layout.fillWidth: true
                                text: sc.modelData.rich ? rekord.richDisplay(sc.modelData.rich, String(Theme.accent)) : ""
                                textFormat: TextEdit.RichText
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.Wrap
                                font.family: Theme.text
                                font.pixelSize: 15
                                color: Theme.fg
                                selectionColor: Theme.accent
                                selectedTextColor: Theme.onAccent
                                onLinkActivated: (link) => { if (link.startsWith("seek:")) player.seekPlay(Number(link.slice(5))); else api.openUrl(link) }
                                HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.IBeamCursor }
                            }
                            Markdown {
                                visible: !sc.modelData.rich
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
        Rectangle {  // the pinned header: title + Kopieren + Bearbeiten while scrolling through a long summary
            objectName: "summarySticky"
            visible: v.pinned !== null
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: stickyRow.implicitHeight + 16
            color: Theme.card
            border.color: Theme.accentLine
            radius: 10
            z: 2
            RowLayout {
                id: stickyRow
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 12
                spacing: 8
                Eyebrow { text: v.pinned ? v.pinned.modelData.title : ""; Layout.fillWidth: true; elide: Text.ElideRight }
                Btn { objectName: "summaryStickyCopy"; kind: "ghost"; small: true; text: "Kopieren"; onClicked: if (v.pinned) v.pinned.copy() }
                Btn { objectName: "summaryStickyEdit"; kind: "ghost"; small: true; text: "Bearbeiten"; onClicked: if (v.pinned) v.pinned.edit() }
            }
        }
        }
    }
}
