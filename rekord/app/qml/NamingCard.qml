import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// "Wer ist das?" right after a recording: one row per voice REKORD didn't know – listen, name it, Merken.
Card {
    id: card
    required property var page
    property var names: []  // people REKORD knows (suggestions)
    readonly property var rows: build()
    visible: rows.length > 0 && !page.app.namingLater[page.rid]
    implicitHeight: col.implicitHeight + 32
    border.color: Qt.rgba(1, 0.353, 0.122, 0.35)
    color: Theme.accentSoft

    readonly property var introRe: /(?:^|[\s,.;:!?])(?:[Hh]ier (?:ist|spricht)|[Mm]ein Name ist|[Ii]ch heiße|[Tt]his is|[Mm]y name is|[Ii]ch bin(?: der| die)?)\s+([A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)/g
    readonly property var notNames: ["Ich", "Heute", "Hier", "Jetzt", "Gerade", "Auch", "Noch", "Mal", "Eigentlich", "Okay", "Der", "Die", "Das", "Ein", "Eine", "Team"]

    function build() {
        const rec = page.rec
        if (!rec || rec.status !== "done") return []
        const out = []
        for (const x of rec.speakers) {
            if (x.profile_id || !page.unnamed(x.name)) continue
            const lines = rec.segments.filter(g => g.speaker_id === x.id)
            const by = {}
            for (const g of lines) { const v = g.voice === null || g.voice === undefined ? "one" : g.voice; (by[v] = by[v] || []).push(g) }
            const groups = Object.values(by).sort((a, b) => a[0].start - b[0].start)
            for (const g of groups) out.push({ sid: x.id, lines: g, single: groups.length === 1, suggest: suggest(g) })
        }
        return out
    }
    function suggest(lines) {  // "Hier ist Emil …" → Emil ("ich bin X" only for names REKORD knows)
        for (const sg of lines) {
            const re = new RegExp(introRe.source, "g")
            let m
            while ((m = re.exec(sg.text || "")) !== null) {
                const name = m[1], weak = /ich bin/i.test(m[0])
                if (notNames.indexOf(name) >= 0) continue
                if (!weak || names.some(k => k.toLowerCase() === name.toLowerCase())) return name
            }
        }
        return ""
    }
    function save(r, name) {
        name = name.trim()
        if (!name) { page.app.toast("Namen eingeben"); return }
        const done = () => { page.app.toast(name + ": Stimme gemerkt ✓"); page.reload() }
        if (r.single) page.app.call("PATCH", "/api/speakers/" + r.sid, { name: name, remember: true }, done)
        else page.app.call("POST", "/api/segments/" + r.lines[0].id + "/assign", { name: name, remember: true, whole_voice: true }, done)
    }

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Wer ist das?"; font.family: Theme.display; font.pixelSize: 20; font.weight: Font.Black; color: Theme.fg }
            Tip { key: "naming" }
            Item { Layout.fillWidth: true }
            Btn { kind: "ghost"; small: true; text: "Später"; onClicked: { const m = card.page.app.namingLater; m[card.page.rid] = true; card.page.app.namingLater = Object.assign({}, m) } }
        }
        Muted {
            Layout.fillWidth: true
            text: (card.rows.length > 1 ? card.rows.length + " Stimmen hat REKORD nicht erkannt." : "Eine Stimme hat REKORD nicht erkannt.")
                + " Anhören, Namen eingeben, Merken – ab der nächsten Aufnahme wird sie automatisch erkannt."
        }
        Repeater {
            model: card.rows
            delegate: RowLayout {
                id: row
                required property var modelData
                Layout.fillWidth: true
                spacing: 10
                Rectangle {
                    width: 34; height: 34; radius: 17; color: "#8A877F"
                    Text { anchors.centerIn: parent; text: "?"; color: "#FFFFFF"; font.pixelSize: 15; font.weight: Font.Black }
                }
                Btn {
                    small: true; iconName: "play"
                    ToolTip.visible: hovered; ToolTip.text: "Anhören"
                    onClicked: {
                        const mine = row.modelData.lines.slice().sort((a, b) => (b.end - b.start) - (a.end - a.start))
                        if (mine.length) player.playRange(mine[0].start, mine[0].end)
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    Text {
                        text: "Ab " + card.page.fmt(row.modelData.lines[0].start) + " · " + row.modelData.lines.length + (row.modelData.lines.length === 1 ? " Satz" : " Sätze")
                        font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.fg
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "„" + (row.modelData.lines[0].text || "").slice(0, 90) + "“"
                        elide: Text.ElideRight
                        font.family: Theme.text; font.pixelSize: 12; color: Theme.fg2
                    }
                }
                NameField {
                    id: nf
                    Layout.preferredWidth: 190
                    names: card.names
                    text: row.modelData.suggest
                    onAccepted: card.save(row.modelData, nf.text)
                }
                Btn { kind: "primary"; small: true; text: "Merken"; onClicked: card.save(row.modelData, nf.text) }
            }
        }
    }
}
