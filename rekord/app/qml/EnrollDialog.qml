import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import QtCore
import "."

// "Person einsprechen": three ways to learn a voice – read a text, just talk, or take it from a recording.
Sheet {
    id: d
    required property var app
    property string mode: "read"          // read | free | recording
    property int variant: 0
    property string lang: "de"
    property string idea: ""
    property string file: ""               // a sample from a file instead of the microphone
    property var recordings: []
    property var voices: []
    property int picked: -1
    property string pickedRec: ""
    property bool saving: false
    property string heading: "Person einsprechen"
    property var onDone: null
    readonly property int target: 45
    readonly property int minimum: 25
    readonly property bool named: nameF.text.trim() !== ""
    readonly property bool canSave: named && !saving && (mode === "recording" ? picked >= 0 : (voice.path !== "" && voice.speech >= minimum) || file !== "")

    // opts: {name, intro, step}; fn(profile) after it was saved
    function start(opts, fn) {
        opts = opts || {}
        heading = opts.intro ? "Vorstellungsrunde" + (opts.step ? " · " + opts.step : "") : "Person einsprechen"
        onDone = fn || null
        nameF.text = opts.name || ""
        variant = 0; idea = ""; file = ""; picked = -1; pickedRec = ""; voices = []; saving = false
        voice.discard()
        mode = app.enrollMode || "read"
        app.call("GET", "/api/settings", null, (s) => d.lang = s.language === "en" ? "en" : "de", () => {})
        loadRecordings()
        open()
        nameF.forceActiveFocus()
    }
    function loadRecordings() {
        app.call("GET", "/api/recordings", null, (r) => d.recordings = r.items.filter(x => x.status === "done"), () => {})
    }
    function pickRecording(rid) {
        pickedRec = rid; voices = []; picked = -1
        if (!rid) return
        const rec = recordings.find(x => x.id === rid)
        samplePlayer.load(rec ? rec.audio_path || "" : "")
        app.call("GET", "/api/recordings/" + rid + "/voices", null, (r) => d.voices = r.items)
    }
    function fmt(t) { t = Math.floor(t || 0); return Math.floor(t / 60) + ":" + (t % 60 < 10 ? "0" : "") + (t % 60) }
    function save() {
        const name = nameF.text.trim()
        if (!canSave) return
        saving = true
        if (mode === "recording") {
            const v = voices[picked]
            app.call("POST", "/api/profiles/learn", { recording_id: pickedRec, speaker_id: v.speaker_id, voice: v.voice, name: name }, (prof) => {
                d.saving = false
                app.toast(name + ": Stimme aus der Aufnahme gelernt ✓ (" + Math.round(v.seconds) + " s)")
                d.finish(prof)
            }, (err) => { d.saving = false; app.toast(err) })
            return
        }
        app.toast("Stimmabdruck wird berechnet …")
        app.upload("/api/profiles/enroll", file || voice.path, { name: name, mode: mode === "free" ? "free" : "read" }, (prof) => {
            d.saving = false
            const q = prof.quality || {}
            const grade = q.consistency >= 0.85 ? "sehr gut" : q.consistency >= 0.75 ? "gut" : "ok – nochmal einsprechen macht sie sicherer"
            app.toast(name + ": Stimme gespeichert ✓ · " + Math.round(q.seconds || 0) + " s Sprache · Qualität " + grade
                      + (q.left_out >= 3 ? " · " + Math.round(q.left_out) + " s andere Stimmen weggelassen" : ""))
            voice.discard()
            d.finish(prof)
        }, (err) => { d.saving = false; app.toast(err) })
    }
    function finish(prof) { const fn = onDone; close(); people.refresh(); if (fn) fn(prof) }

    onClosed: { voice.discard(); samplePlayer.stop() }
    onModeChanged: { app.enrollMode = mode; if (voice.recording) voice.stop() }

    Connections { target: voice; function onFailed(msg) { d.app.toast(msg) } }

    FileDialog {
        id: fileDlg
        title: "Datei mit nur dieser Person"
        currentFolder: StandardPaths.writableLocation(StandardPaths.MusicLocation)
        nameFilters: ["Audio & Video (*.m4a *.mp3 *.wav *.webm *.ogg *.opus *.flac *.aac *.mp4 *.mov *.caf)", "Alle Dateien (*)"]
        onAccepted: { voice.discard(); d.file = selectedFile.toString() }
    }

    width: Math.min(parent ? parent.width - 48 : 640, 640)
    contentItem: ColumnLayout {
        spacing: 14
        RowLayout {
            Text { text: d.heading; font.family: Theme.display; font.pixelSize: 28; font.weight: Font.Black; font.letterSpacing: -0.8; color: Theme.fg }
            Tip { key: "intro" }
        }
        Input { id: nameF; Layout.fillWidth: true; big: true; placeholderText: "Name der Person" }
        RowLayout {
            Text { text: "Wie soll REKORD die Stimme lernen?"; font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; color: Theme.fg }
            Tip { key: "enrollmode" }
        }
        Segmented {
            Layout.fillWidth: true
            model: [{ value: "read", label: "Text vorlesen" }, { value: "free", label: "Einfach reden lassen" }, { value: "recording", label: "Aus Aufnahme lernen" }]
            value: d.mode
            onPicked: (v) => d.mode = v
        }

        // ---- read a text
        ColumnLayout {
            visible: d.mode === "read"
            Layout.fillWidth: true
            spacing: 8
            Muted { Layout.fillWidth: true; text: "Lies diesen Text vor – ganz normal, wie im Meeting (ca. " + d.target + " Sekunden):" }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(200, readText.implicitHeight + 28)
                radius: 12
                color: Theme.card2
                Flickable {
                    anchors.fill: parent
                    anchors.margins: 14
                    clip: true
                    contentHeight: readText.implicitHeight
                    Text {
                        id: readText
                        width: parent.width
                        text: rekord.readingText(nameF.text, d.variant, d.lang)
                        wrapMode: Text.WordWrap
                        font.family: Theme.text; font.pixelSize: 16; lineHeight: 1.2
                        color: Theme.fg
                    }
                }
            }
            Btn { kind: "ghost"; small: true; text: "↻ Anderer Text"; onClicked: d.variant++ }
        }

        // ---- just talk
        ColumnLayout {
            visible: d.mode === "free"
            Layout.fillWidth: true
            spacing: 8
            Muted {
                Layout.fillWidth: true
                text: "Die Person redet einfach – über irgendwas, so lange sie will. Kein Text, nichts vorlesen. Passt auch, wenn jemand gerade sowieso redet, z. B. der Prof am Anfang der Vorlesung: Mikro in seine Richtung, Aufnahme starten. Kurze Zwischenrufe anderer lässt REKORD weg."
            }
            Btn { kind: "ghost"; small: true; text: "💬 Gesprächsidee"; onClicked: d.idea = rekord.talkIdea(d.lang, d.idea) }
            Rectangle {
                visible: d.idea !== ""
                Layout.fillWidth: true
                Layout.preferredHeight: ideaT.implicitHeight + 24
                radius: 12
                color: Theme.card2
                Text { id: ideaT; anchors.fill: parent; anchors.margins: 12; text: d.idea; wrapMode: Text.WordWrap; font.family: Theme.text; font.pixelSize: 15; color: Theme.fg }
            }
        }

        // ---- the microphone (read / free)
        ColumnLayout {
            visible: d.mode !== "recording"
            Layout.fillWidth: true
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Btn {
                    kind: voice.recording ? "default" : "primary"
                    iconName: voice.recording ? "stop" : "record"
                    text: voice.recording ? "Fertig" : voice.path ? "Neu aufnehmen" : "Aufnahme starten"
                    enabled: d.named
                    onClicked: {
                        if (voice.recording) { voice.stop(); return }
                        d.file = ""
                        voice.start(d.mode === "free" ? 240 : 120)
                    }
                }
                Text {
                    text: Math.floor(voice.speech) + " s"
                    font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; font.features: ({ "tnum": 1 })
                    color: voice.speech >= d.minimum ? Theme.ok : Theme.fg
                }
                Rectangle {  // live level
                    Layout.fillWidth: true
                    Layout.maximumWidth: 200
                    height: 8; radius: 4
                    color: Theme.card2
                    Rectangle {
                        height: parent.height; radius: 4
                        width: parent.width * voice.level
                        color: voice.talking ? Theme.accent : Theme.fg3
                        Behavior on width { NumberAnimation { duration: 80 } }
                    }
                }
                Item { Layout.fillWidth: true }
            }
            Bar { Layout.fillWidth: true; value: voice.speech / d.target }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                font.family: Theme.text; font.pixelSize: 13
                color: Theme.fg2
                text: d.file ? "Datei gewählt: <b>" + rekord.localPath(d.file).split(/[\\/]/).pop() + "</b>"
                    : !d.named ? "Zuerst den Namen eingeben" + (d.mode === "read" ? " – der Text wird für die Person erstellt." : ".")
                    : !voice.recording && !voice.path ? "Gezählt wird nur, wenn wirklich gesprochen wird. Mindestens " + d.minimum + " Sekunden – je länger, desto sicherer."
                    : voice.speech < d.minimum ? (d.mode === "read" ? "Weiterlesen" : "Weiterreden lassen") + " … noch " + Math.ceil(d.minimum - voice.speech) + " s Sprache bis zum Minimum."
                    : voice.speech < d.target ? "<font color='" + Theme.ok + "'>✓ Reicht.</font> " + (d.mode === "read" ? "Bis zum Ende lesen" : "Noch etwas länger") + " macht die Erkennung noch sicherer."
                    : "<font color='" + Theme.ok + "'>✓ Perfekt.</font> " + (voice.recording ? "Du kannst auf „Fertig“ drücken." : "Jetzt speichern.")
            }
            Btn { kind: "ghost"; small: true; text: "…oder eine Datei mit nur dieser Person"; onClicked: fileDlg.open() }
        }

        // ---- from a recording
        ColumnLayout {
            visible: d.mode === "recording"
            Layout.fillWidth: true
            spacing: 8
            Muted { Layout.fillWidth: true; text: "Die Stimme aus einer fertigen Aufnahme nehmen – z. B. den Prof aus der Vorlesung. Aufnahme wählen, Stimme anhören, auswählen." }
            Select {
                Layout.fillWidth: true
                options: [{ value: "", label: d.recordings.length ? "Aufnahme wählen …" : "Noch keine fertige Aufnahme" }]
                         .concat(d.recordings.map(r => ({ value: r.id, label: r.title + " · " + new Date(r.created_at * 1000).toLocaleString(Qt.locale("de_AT"), "dd.MM.yyyy HH:mm") })))
                value: d.pickedRec
                onPicked: (v) => d.pickRecording(v)
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(230, voiceCol.implicitHeight)
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    id: voiceCol
                    width: parent.width
                    spacing: 6
                    Repeater {
                        model: d.voices
                        delegate: AbstractButton {
                            id: vr
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            implicitHeight: 54
                            hoverEnabled: true
                            onClicked: { d.picked = index; if (!nameF.text.trim() && modelData.known) nameF.text = modelData.name }
                            background: Rectangle {
                                radius: 10
                                color: d.picked === vr.index ? Theme.accentSoft : vr.hovered ? Theme.card2 : Theme.card
                                border.width: d.picked === vr.index ? 2 : 1
                                border.color: d.picked === vr.index ? Theme.accent : Theme.line
                            }
                            contentItem: RowLayout {
                                spacing: 10
                                Rectangle { Layout.leftMargin: 10; width: 12; height: 12; radius: 6; color: vr.modelData.color }
                                Btn {
                                    small: true; iconName: "play"
                                    onClicked: { const s = vr.modelData.samples[0]; samplePlayer.playRange(s[0], s[1]) }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    Text {
                                        text: (vr.modelData.known ? vr.modelData.name : vr.modelData.name === "Nicht erkannte Stimme" || vr.modelData.name === "Publikum"
                                               ? "Stimme ab " + d.fmt(vr.modelData.first) : vr.modelData.name) + " · " + Math.round(vr.modelData.seconds) + " s"
                                        font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg
                                    }
                                    Text { Layout.fillWidth: true; text: "„" + vr.modelData.text + "“"; elide: Text.ElideRight; font.family: Theme.text; font.pixelSize: 12; color: Theme.fg2 }
                                }
                            }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                        }
                    }
                    Muted { visible: d.pickedRec !== "" && d.voices.length === 0; text: "Keine Stimmen in dieser Aufnahme." }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: d.saving ? "Speichert …" : d.mode === "recording" ? "Stimme lernen" : "Stimme speichern"; enabled: d.canSave; onClicked: d.save() }
        }
    }
}
