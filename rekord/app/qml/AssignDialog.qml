import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// "Wer sagt das?" for one line – sorts the unknown voices out one sentence at a time.
Sheet {
    id: d
    required property var page
    property var seg: ({})
    property var cur: ({})
    property int sameVoice: 1
    property var names: []
    function ask(segId) {
        const rec = page.rec
        seg = rec.segments.find(x => x.id === segId) || {}
        cur = page.spk(seg.speaker_id)
        sameVoice = seg.voice !== null && seg.voice !== undefined ? rec.segments.filter(x => x.speaker_id === seg.speaker_id && x.voice === seg.voice).length : 1
        const set = {}
        rec.speakers.filter(x => !page.unnamed(x.name)).forEach(x => set[x.name] = 1)
        page.knownNames.forEach(n => set[n] = 1)
        delete set[cur.name]
        names = Object.keys(set)
        newName.text = ""
        all.checked = true
        rem.checked = true
        open()
    }
    function assign(name) {
        name = name.trim()
        if (!name) return
        const remember = rem.checked
        page.app.call("POST", "/api/segments/" + seg.id + "/assign", { name: name, remember: remember, whole_voice: d.sameVoice > 1 && all.checked },
                      () => { page.app.toast(remember ? name + " ✓ – Stimme gelernt" : name + " ✓"); page.reload() })
        close()
    }
    contentItem: ColumnLayout {
        spacing: 12
        Text { text: "Wer sagt das?"; font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; color: Theme.fg }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: quote.implicitHeight + 24
            radius: 10
            color: Theme.card2
            Text {
                id: quote
                anchors.fill: parent
                anchors.margins: 12
                text: "„" + (d.seg.text || "") + "“"
                wrapMode: Text.WordWrap
                font.family: Theme.text; font.pixelSize: 15; font.italic: true; color: Theme.fg
            }
        }
        RowLayout {
            Btn { small: true; iconName: "play"; text: "Anhören"; onClicked: player.playRange(d.seg.start, d.seg.end) }
            Muted { text: d.page.fmt(d.seg.start || 0) + " · jetzt: " + (d.cur.name || "") }
        }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            visible: d.names.length > 0
            Repeater {
                model: d.names
                delegate: Btn { required property string modelData; small: true; text: modelData; onClicked: d.assign(modelData) }
            }
        }
        Input { id: newName; Layout.fillWidth: true; placeholderText: "…oder neuer Name"; onAccepted: d.assign(text) }
        Check { id: all; visible: d.sameVoice > 1; text: "Alle " + d.sameVoice + " Sätze dieser Stimme" }
        RowLayout { Check { id: rem; text: "Stimme dabei lernen" } Tip { key: "remember" } }
        Btn {
            kind: "ghost"; small: true
            text: "Alle Sätze von „" + (d.cur.name || "") + "“ umbenennen …"
            onClicked: { const sid = d.seg.speaker_id; d.close(); d.page.editSpeaker(sid) }
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: "Zuordnen"; enabled: newName.text.trim() !== ""; onClicked: d.assign(newName.text) }
        }
    }
}
