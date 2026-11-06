import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Everything that was said: click a name → "Wer sagt das?", click the time → listen, edit the text in place.
Item {
    id: v
    required property var page
    property string q: ""
    property bool follow: true
    readonly property var segs: page.rec ? page.rec.segments : []
    // "Geräusch": lines that are only a sound – out of sight unless asked for
    property bool showNoise: false
    readonly property var noiseIds: (page.rec ? page.rec.speakers : []).filter(s => s.name === "Geräusch").map(s => s.id)
    readonly property var spoken: noiseIds.length ? segs.filter(s => noiseIds.indexOf(s.speaker_id) < 0) : segs
    readonly property int noiseCount: segs.length - spoken.length
    readonly property var base: showNoise ? segs : spoken
    readonly property var shown: q ? base.filter(s => (s.text || "").toLowerCase().indexOf(q) >= 0 || page.spk(s.speaker_id).name.toLowerCase().indexOf(q) >= 0) : base
    readonly property var hl: page.rec && page.rec.highlights ? page.rec.highlights : []
    readonly property var stills: page.rec && page.rec.frames ? page.rec.frames : []  // from a video: what was on screen
    property int active: -1
    property bool aiBusy: false
    property var hist: ({})  // what Rückgängig / Wiederholen would do (fresh with every load of the recording)
    Connections { target: v.page; function onRecChanged() { v.hist = v.page.rec && v.page.rec.history ? v.page.rec.history : ({}) } }
    function loadHist() { page.app.call("GET", "/api/recordings/" + page.rid + "/transcript/history", null, (r) => v.hist = r, () => {}) }
    function step(dir) {  // dir: "undo" | "redo" – like in Word
        if (!(dir === "undo" ? hist.undo : hist.redo)) return
        page.app.call("POST", "/api/recordings/" + page.rid + "/transcript/" + dir, null, (r) => {
            if (r.done) page.app.toast((dir === "undo" ? "Rückgängig: " : "Wiederholt: ") + r.label)
            v.hist = r
            page.reload()
        })
    }
    Shortcut { sequences: [StandardKey.Undo]; enabled: v.visible && !(v.Window.activeFocusItem && v.Window.activeFocusItem.cursorPosition !== undefined); onActivated: v.step("undo") }
    Shortcut { sequences: [StandardKey.Redo, "Ctrl+Y"]; enabled: v.visible && !(v.Window.activeFocusItem && v.Window.activeFocusItem.cursorPosition !== undefined); onActivated: v.step("redo") }
    function aiEdit() {
        const t = aiIn.text.trim()
        if (!t || aiBusy) return
        aiBusy = true
        page.app.call("POST", "/api/recordings/" + page.rid + "/transcript/ai", { instruction: t }, (r) => {
            aiBusy = false
            aiIn.text = ""
            page.app.toast(r.changed || r.deleted
                           ? (r.changed ? r.changed + " Zeilen geändert" : "") + (r.changed && r.deleted ? ", " : "") + (r.deleted ? r.deleted + " entfernt" : "") + " – „Rückgängig“ holt alles zurück."
                           : (r.note || "Nichts zu ändern."))
            page.reload()
            v.loadHist()
        }, (err) => { aiBusy = false; page.app.toast(err) })
    }

    FindReplaceDialog { id: frep; page: v.page }

    Popup {  // a still, big – and listen from there
        id: big
        property var still: null
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(parent ? parent.width - 80 : 900, 1100)
        modal: true
        padding: 14
        background: Rectangle { radius: 16; color: Theme.card; border.width: 1; border.color: Theme.line }
        contentItem: ColumnLayout {
            spacing: 10
            Image {
                Layout.fillWidth: true
                Layout.preferredHeight: width * (implicitHeight > 0 ? implicitHeight / Math.max(1, implicitWidth) : 0.5625)
                source: big.still ? big.still.file : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
            RowLayout {
                Muted { text: big.still ? "Bild bei " + v.page.fmt(big.still.t) : ""; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
                Btn { small: true; kind: "primary"; iconName: "play"; text: "Ab hier anhören"; onClicked: { player.seekPlay(big.still.t); big.close() } }
                Btn { small: true; text: "Schließen"; onClicked: big.close() }
            }
        }
    }

    Connections {  // the line being played: highlighted, and (Mitscrollen) kept in view
        target: player
        function onTick() {
            const t = player.position
            const i = v.shown.findIndex(s => t >= s.start && t < s.end + 0.3)
            if (i !== v.active) {
                v.active = i
                if (i >= 0 && v.follow && player.playing) list.positionViewAtIndex(i, ListView.Center)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        RowLayout {  // tell the AI what to change: leave out, rewrite, correct – speakers and times stay
            objectName: "transcriptAi"
            Layout.fillWidth: true
            spacing: 10
            visible: v.segs.length > 0
            Icon { name: "spark"; width: 18; height: 18; color: Theme.accent }
            Input {
                id: aiIn
                Layout.fillWidth: true
                enabled: !v.aiBusy
                placeholderText: "Sag der KI, was sie ändern soll – z. B. „Lass den Smalltalk weg“, „Schreib Emil statt Emir“, „Ähms raus“"
                onAccepted: v.aiEdit()
            }
            BusyIndicator { visible: v.aiBusy; running: visible; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
            Btn { objectName: "transcriptAiGo"; small: true; kind: "primary"; text: v.aiBusy ? "Arbeitet …" : "Ändern"; enabled: !v.aiBusy && aiIn.text.trim().length > 0; onClicked: v.aiEdit() }
            Btn {  // like in Word: every change – by hand, Suchen & Ersetzen, the AI – one step back …
                objectName: "transcriptUndo"
                small: true; kind: "ghost"; text: "↶ Rückgängig"
                enabled: !!v.hist.undo
                ToolTip.visible: hovered; ToolTip.delay: 400
                ToolTip.text: v.hist.undo ? "Zurücknehmen: " + v.hist.undo + " (Strg/⌘ + Z)" : "Nichts zurückzunehmen"
                onClicked: v.step("undo")
            }
            Btn {  // … and forward again
                objectName: "transcriptRedo"
                small: true; kind: "ghost"; text: "↷ Wiederholen"
                enabled: !!v.hist.redo
                ToolTip.visible: hovered; ToolTip.delay: 400
                ToolTip.text: v.hist.redo ? "Wiederholen: " + v.hist.redo + " (Strg/⌘ + ⇧ + Z)" : "Nichts zu wiederholen"
                onClicked: v.step("redo")
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Input {
                Layout.preferredWidth: 300
                placeholderText: "Im Transkript suchen"
                onTextChanged: v.q = text.trim().toLowerCase()
            }
            Btn { small: true; text: "Suchen & Ersetzen"; onClicked: frep.start() }
            Check { text: "Mitscrollen"; checked: v.follow; onToggled: v.follow = checked; font.pixelSize: 13 }
            Item { Layout.fillWidth: true }
            Btn {
                objectName: "noiseToggle"
                visible: v.noiseCount > 0
                small: true; kind: "ghost"
                text: v.showNoise ? "Geräusche ausblenden" : (v.noiseCount === 1 ? "1 Geräusch" : v.noiseCount + " Geräusche") + " ausgeblendet · zeigen"
                onClicked: v.showNoise = !v.showNoise
                ToolTip.visible: hovered; ToolTip.delay: 400
                ToolTip.text: "Zeilen mit der Rolle „Geräusch“ – Husten, Musik, was die KI als Wort gehört hat. Sie stehen nicht im Protokoll und nicht im Export."
            }
            Muted { text: v.q ? v.shown.length + " von " + v.base.length : v.base.length + " Sätze"; font.pixelSize: 13 }
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: v.shown
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property var who: v.page.spk(modelData.speaker_id)
                readonly property bool star: v.hl.some(h => h >= modelData.start - 2 && h <= modelData.end + 2)
                readonly property var pics: v.stills.filter(f => f.seg === modelData.id)
                width: list.width - 12
                height: line.implicitHeight + 14
                radius: 10
                color: index === v.active ? Theme.accentSoft : rowHover.hovered ? Theme.card : "transparent"
                HoverHandler { id: rowHover }
                RowLayout {
                    id: line
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 7
                    spacing: 12
                    ColumnLayout {
                        Layout.preferredWidth: 150
                        Layout.maximumWidth: 150
                        Layout.fillWidth: false
                        Layout.alignment: Qt.AlignTop
                        spacing: 2
                        AbstractButton {
                            Layout.fillWidth: true
                            implicitHeight: nameRow.implicitHeight
                            hoverEnabled: true
                            onClicked: v.page.assignLine(row.modelData.id)
                            ToolTip.visible: hovered
                            ToolTip.delay: 600
                            ToolTip.text: "Wer sagt das? – antippen zum Zuordnen"
                            contentItem: RowLayout {
                                id: nameRow
                                spacing: 6
                                Rectangle { width: 8; height: 8; radius: 4; color: row.who.color }
                                Text {
                                    Layout.fillWidth: true
                                    text: row.who.name
                                    elide: Text.ElideRight
                                    font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold
                                    font.underline: parent.parent.hovered
                                    color: Theme.fg
                                }
                            }
                            background: null
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                        }
                        Text {
                            text: v.page.fmt(row.modelData.start) + (row.star ? "  ★" : "")
                            font.family: Theme.text; font.pixelSize: 12; font.features: ({ "tnum": 1 })
                            color: row.star ? Theme.accent : Theme.fg3
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: player.seekPlay(row.modelData.start) }
                        }
                    }
                    ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Flow {  // what was on screen while this was said
                        Layout.fillWidth: true
                        visible: row.pics.length > 0
                        spacing: 8
                        Repeater {
                            model: row.pics
                            delegate: Rectangle {
                                required property var modelData
                                width: 220
                                height: thumb.status === Image.Ready ? thumb.paintedHeight + 2 : 124
                                radius: 8
                                color: Theme.card2
                                border.width: thumbHover.hovered ? 2 : 1
                                border.color: thumbHover.hovered ? Theme.accent : Theme.line
                                clip: true
                                Image {
                                    id: thumb
                                    anchors.centerIn: parent
                                    width: parent.width - 2
                                    source: modelData.file
                                    sourceSize.width: 440
                                    fillMode: Image.PreserveAspectFit
                                    asynchronous: true
                                }
                                Rectangle {
                                    anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 6
                                    width: tLabel.implicitWidth + 10; height: 18; radius: 5
                                    color: Qt.rgba(0, 0, 0, 0.6)
                                    Text { id: tLabel; anchors.centerIn: parent; text: v.page.fmt(modelData.t); color: "white"; font.family: Theme.text; font.pixelSize: 11; font.features: ({ "tnum": 1 }) }
                                }
                                HoverHandler { id: thumbHover; cursorShape: Qt.PointingHandCursor }
                                TapHandler { onTapped: { big.still = modelData; big.open() } }
                            }
                        }
                    }
                    TextArea {
                        id: ta
                        Layout.fillWidth: true
                        text: row.modelData.text
                        wrapMode: TextArea.Wrap
                        font.family: Theme.text; font.pixelSize: 15
                        color: Theme.fg
                        selectionColor: Theme.accent
                        selectedTextColor: Theme.onAccent
                        selectByMouse: true
                        padding: 0
                        topPadding: 2
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                            border.width: ta.activeFocus ? 1 : 0
                            border.color: Theme.accent
                            anchors.margins: -4
                        }
                        onEditingFinished: {
                            const t = text.trim()
                            if (t !== row.modelData.text) {
                                row.modelData.text = t
                                v.page.app.call("PATCH", "/api/segments/" + row.modelData.id, { text: t }, () => { v.page.app.toast("Gespeichert"); v.loadHist() })
                            }
                        }
                    }
                    }
                }
            }
            Muted {
                visible: list.count === 0
                anchors.centerIn: parent
                text: v.q ? "Nichts gefunden." : v.page.rec && v.page.rec.status === "done" ? "Keine Sprache erkannt." : "Transkript entsteht gerade …"
            }
        }
    }
}
