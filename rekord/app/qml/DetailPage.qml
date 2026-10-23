import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// One recording: title, player, who talked how much, "Wer ist das?", and the tabs
// Zusammenfassung · Transkript · Mind Map · Fragen · Notizen · Export.
Page {
    id: page
    objectName: "detailPage"
    required property var app
    property string rid: ""
    property var rec: null
    // progress of the running analysis: kept apart from rec, so a tick doesn't rebuild transcript, players and charts
    property string jobStage: ""
    property real jobProgress: 0
    property var templates: []
    property var knownNames: []
    property int tab: 0
    property real startAt: 0
    readonly property var tabs: ["Zusammenfassung", "Transkript", "Mind Map", "Fragen", "Notizen", "Export"]
    readonly property bool busy: rec && (rec.status === "queued" || rec.status === "processing" || rec.status === "recording")

    function open(id, t) {
        if (id !== rid) { rec = null; tab = 0 }
        rid = id
        startAt = t || 0
        reload()
        app.call("GET", "/api/templates", null, (r) => page.templates = r.items, () => {})
        app.call("GET", "/api/profiles", null, (r) => page.knownNames = r.items.map(p => p.name), () => {})
    }
    function reload() {
        const id = rid
        app.call("GET", "/api/recordings/" + id, null, (r) => {
            if (id !== page.rid) return
            const first = !page.rec || page.rec.id !== r.id
            page.rec = r
            page.jobStage = r.stage || ""
            page.jobProgress = r.progress || 0
            if (first) {
                player.load(r.audio_path || "")
                if (page.startAt > 0) { player.seek(page.startAt); page.tab = 1; page.startAt = 0 }
                else if (!r.summaries.some(s => s.template_id !== "mindmap") && r.segments.length) page.tab = 1
                notes.fill()
            }
        }, (err) => { page.app.toast(err); page.app.go("library") })
    }
    function spk(sid) { return (rec && rec.speakers.find(s => s.id === sid)) || { name: "?", color: Theme.fg3, id: -1 } }
    function unnamed(n) { return n === "Nicht erkannte Stimme" || n === "Vortragende Person" || n === "Publikum" || /^Sprecher \d+$/.test(n || "") }
    function initials(n) {
        if (n === "Nicht erkannte Stimme" || n === "Publikum") return "?"
        return (n || "?").replace(/^Sprecher\s*/, "S").split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase()
    }
    function fmt(t) {
        t = Math.max(0, Math.floor(t || 0))
        const h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), s = t % 60
        const p = (x) => (x < 10 ? "0" : "") + x
        return h ? h + ":" + p(m) + ":" + p(s) : p(m) + ":" + p(s)
    }
    function dur(t) { return t >= 3600 ? Math.floor(t / 3600) + " h " + Math.round(t % 3600 / 60) + " min" : t >= 60 ? Math.round(t / 60) + " min" : Math.round(t) + " s" }
    function assignLine(id) { assignDlg.ask(id) }
    function editSpeaker(sid) { speakerDlg.edit(sid) }
    readonly property var talk: {
        const t = {}
        if (rec) for (const s of rec.segments) t[s.speaker_id] = (t[s.speaker_id] || 0) + s.end - s.start
        return t
    }
    readonly property real talkTotal: Object.values(talk).reduce((a, b) => a + b, 0) || 1

    onShownChanged: if (!shown) player.pause()
    Connections {
        target: api
        function onEvent(ev) {
            if (ev.id !== page.rid || !page.rec) return
            if (ev.type === "progress") {
                page.jobStage = ev.stage
                page.jobProgress = ev.progress
                if (page.rec.status !== "processing") {  // once: from "queued" to "processing"
                    const r = Object.assign({}, page.rec)
                    r.status = "processing"
                    page.rec = r
                }
            } else if (["done", "summary_done", "error", "queued"].indexOf(ev.type) >= 0) {
                page.reload()
            } else if (ev.type === "summary_started") {
                page.app.toast("Zusammenfassung wird erstellt …")
            }
        }
    }

    SpeakerDialog { id: speakerDlg; objectName: "speakerDlg"; page: page }
    AssignDialog { id: assignDlg; objectName: "assignDlg"; page: page }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        anchors.bottomMargin: 20
        spacing: 14

        // ---- header
        RowLayout {
            Layout.fillWidth: true
            Btn { kind: "ghost"; small: true; iconName: "back"; text: "Aufnahmen"; onClicked: page.app.go("library") }
            Item { Layout.fillWidth: true }
            Btn {
                id: moreBtn
                small: true
                text: "•••"
                onClicked: more.popup(moreBtn, 0, moreBtn.height + 4)
                Menu {
                    id: more
                    MenuItem { text: "Neu verarbeiten (andere Einstellungen/Modell)"; onTriggered: page.app.call("POST", "/api/recordings/" + page.rid + "/reprocess", null, () => { page.app.toast("Wird neu verarbeitet …"); page.reload() }) }
                    MenuItem { text: "Personen neu erkennen"; onTriggered: page.app.call("POST", "/api/recordings/" + page.rid + "/reidentify", null, (r) => { page.app.toast(r.renamed + " Person(en) erkannt"); page.reload() }) }
                    MenuItem { text: "Umbenennen"; onTriggered: page.app.prompt("Titel", page.rec.title, (t) => page.app.call("PATCH", "/api/recordings/" + page.rid, { title: t }, () => { page.reload(); library.refresh() })) }
                    MenuSeparator {}
                    MenuItem {
                        text: "Löschen"
                        onTriggered: page.app.confirm("Aufnahme löschen?", "Audio, Transkript und Zusammenfassungen werden endgültig entfernt.", "Löschen",
                                                      () => page.app.call("DELETE", "/api/recordings/" + page.rid, null, () => { player.stop(); page.app.toast("Gelöscht"); page.app.go("library") }))
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            TextInput {  // the title: click and type
                id: titleIn
                Layout.fillWidth: true
                text: page.rec ? page.rec.title : ""
                font.family: Theme.display; font.pixelSize: 36; font.weight: Font.Black; font.letterSpacing: -1.5
                color: Theme.fg
                selectionColor: Theme.accent
                selectedTextColor: Theme.onAccent
                selectByMouse: true
                clip: true
                onEditingFinished: {
                    const t = text.trim()
                    if (page.rec && t && t !== page.rec.title) page.app.call("PATCH", "/api/recordings/" + page.rid, { title: t }, () => { page.app.toast("Titel gespeichert"); page.reload(); library.refresh() })
                }
                Keys.onEscapePressed: { text = page.rec.title; focus = false }
                HoverHandler { cursorShape: Qt.IBeamCursor }
            }
            RowLayout {
                spacing: 10
                Muted {
                    text: page.rec ? new Date(page.rec.created_at * 1000).toLocaleString(Qt.locale("de_AT"), "dd.MM.yyyy HH:mm") + " · " + page.dur(page.rec.duration || 0)
                                     + (page.rec.language ? " · " + page.rec.language.toUpperCase() : "") : ""
                    color: Theme.fg3
                }
                Rectangle {
                    visible: page.rec && !!page.rec.folder
                    Layout.preferredHeight: 22
                    Layout.preferredWidth: folderT.implicitWidth + 16
                    radius: 11
                    color: Theme.card2
                    Text { id: folderT; anchors.centerIn: parent; text: page.rec ? "▸ " + (page.rec.folder || "") : ""; font.family: Theme.text; font.pixelSize: 12; font.weight: Font.Bold; color: Theme.fg2 }
                }
                Text {
                    visible: page.rec && (page.rec.highlights || []).length > 0
                    text: "★ " + (page.rec ? (page.rec.highlights || []).length : 0)
                    font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.accent
                }
            }
        }

        Card {  // still being worked on / failed
            visible: page.busy || (page.rec && page.rec.status === "error")
            Layout.fillWidth: true
            Layout.preferredHeight: progCol.implicitHeight + 28
            border.color: page.rec && page.rec.status === "error" ? Theme.err : Theme.line
            ColumnLayout {
                id: progCol
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    BusyIndicator { visible: page.busy; running: page.busy; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                    Text {
                        Layout.fillWidth: true
                        text: page.rec ? (page.rec.status === "error" ? "Verarbeitung fehlgeschlagen. " + (page.rec.error || "") : (page.jobStage || "In Warteschlange")) : ""
                        wrapMode: Text.WordWrap
                        font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg
                    }
                    Text { visible: page.busy; text: Math.round(page.jobProgress * 100) + " %"; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg2 }
                    Btn { visible: page.rec && page.rec.status === "error"; small: true; text: "Nochmal"; onClicked: page.app.call("POST", "/api/recordings/" + page.rid + "/reprocess", null, () => page.app.toast("Neu gestartet")) }
                }
                Bar { visible: page.busy; Layout.fillWidth: true; value: page.jobProgress }
                Muted { visible: page.busy; font.pixelSize: 12; text: "Sprecher trennen → Personen erkennen → transkribieren → zusammenfassen. Läuft komplett auf diesem Rechner." }
            }
        }

        PlayerBar { page: page; Layout.fillWidth: true; visible: page.rec && !!page.rec.audio_path }

        Flow {  // who talked how much – click to rename, remember or merge
            Layout.fillWidth: true
            spacing: 8
            visible: page.rec && page.rec.speakers.length > 0
            Repeater {
                model: page.rec ? page.rec.speakers : []
                delegate: AbstractButton {
                    id: sb
                    required property var modelData
                    hoverEnabled: true
                    implicitHeight: 48
                    implicitWidth: sbRow.implicitWidth + 24
                    onClicked: page.editSpeaker(modelData.id)
                    background: Rectangle {
                        radius: 24
                        color: sb.hovered ? Theme.card2 : Theme.card
                        border.width: 1
                        border.color: sb.hovered ? Theme.line2 : Theme.line
                    }
                    contentItem: Item {
                        RowLayout {
                            id: sbRow
                            anchors.verticalCenter: parent.verticalCenter
                            x: 6
                            spacing: 10
                            Rectangle {
                                width: 36; height: 36; radius: 18; color: sb.modelData.color
                                Text { anchors.centerIn: parent; text: page.initials(sb.modelData.name); color: "#FFFFFF"; font.pixelSize: 13; font.weight: Font.Black }
                            }
                            ColumnLayout {
                                spacing: 0
                                Text { text: sb.modelData.name; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
                                Text {
                                    text: Math.round((page.talk[sb.modelData.id] || 0) / page.talkTotal * 100) + " % · "
                                          + (sb.modelData.profile_id ? "erkannt" + (sb.modelData.match_score && sb.modelData.match_score < 1 ? " " + Math.round(sb.modelData.match_score * 100) + " %" : "")
                                                                     : (sb.modelData.voices > 1 ? sb.modelData.voices + " Stimmen" : "nicht erkannt"))
                                    font.family: Theme.text; font.pixelSize: 12; color: Theme.fg3
                                }
                            }
                            Item { width: 6 }
                        }
                    }
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                }
            }
        }

        NamingCard { page: page; names: page.knownNames; Layout.fillWidth: true }

        Segmented {  // the tabs
            Layout.fillWidth: true
            Layout.maximumWidth: 900
            model: page.tabs.map((t, i) => ({ value: String(i), label: t }))
            value: String(page.tab)
            onPicked: (v) => page.tab = Number(v)
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 220
            currentIndex: page.tab
            SummaryView { page: page }
            TranscriptView { page: page }
            MindMapView { page: page }
            ChatView {
                app: page.app
                scope: page.rid || "global"
                askPath: "/api/recordings/" + page.rid + "/ask"
                placeholder: "Frag etwas zu dieser Aufnahme …"
                suggestions: ["Was wurde entschieden?", "Welche To-dos habe ich?", "Wer hat was zugesagt?",
                              "Gab es Widersprüche oder offene Fragen?", "Schreib eine kurze Mail an alle Teilnehmer."]
                onSeek: (s) => player.seekPlay(s)
            }
            NotesView { id: notes; page: page }
            ExportView { page: page }
        }
    }
}
