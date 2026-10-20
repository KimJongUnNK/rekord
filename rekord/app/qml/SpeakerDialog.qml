import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A speaker of this recording: rename, remember the voice (recognized from then on), or merge with a duplicate.
Sheet {
    id: d
    required property var page
    property var sp: ({})
    property var others: []
    function edit(sid) {
        sp = page.rec.speakers.find(x => x.id === sid) || {}
        others = page.rec.speakers.filter(x => x.id !== sid)
        nameF.text = page.unnamed(sp.name) ? "" : sp.name
        rem.checked = !!sp.profile_id || page.unnamed(sp.name)
        merge.value = ""
        open()
        nameF.forceActiveFocus()
    }
    function save() {
        const app = page.app
        if (merge.value !== "") {
            app.call("POST", "/api/recordings/" + page.rid + "/speakers/merge", { source: sp.id, target: Number(merge.value) },
                     () => { app.toast("Zusammengeführt"); page.reload() })
        } else {
            const name = nameF.text.trim()
            if (!name) { app.toast("Namen eingeben"); return }
            const remember = (sp.voices || 1) <= 1 && rem.checked
            app.call("PATCH", "/api/speakers/" + sp.id, { name: name, remember: remember },
                     () => { app.toast(remember ? name + ": Stimme gespeichert ✓" : "Umbenannt"); page.reload() })
        }
        close()
    }
    contentItem: ColumnLayout {
        spacing: 14
        Eyebrow { text: "Sprecher" }
        Text { text: d.sp.name || ""; font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; color: Theme.fg; Layout.fillWidth: true; elide: Text.ElideRight }
        Input { id: nameF; Layout.fillWidth: true; big: true; placeholderText: "Name"; onAccepted: d.save() }
        Muted {
            Layout.fillWidth: true
            visible: (d.sp.voices || 1) > 1
            text: "Hier stecken " + d.sp.voices + " verschiedene Stimmen. Zum Lernen im Transkript einzelne Sätze antippen und zuordnen."
        }
        RowLayout {
            visible: (d.sp.voices || 1) <= 1
            Check { id: rem; text: "Stimme merken – in Zukunft automatisch erkennen" }
            Tip { key: "remember" }
        }
        ColumnLayout {
            visible: d.others.length > 0
            Layout.fillWidth: true
            spacing: 6
            Muted { text: "Oder zusammenführen mit (falls doppelt erkannt)" }
            Select {
                id: merge
                Layout.fillWidth: true
                options: [{ value: "", label: "—" }].concat(d.others.map(o => ({ value: String(o.id), label: o.name })))
                value: ""
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: merge.value !== "" ? "Zusammenführen" : "Speichern"; onClicked: d.save() }
        }
    }
}
