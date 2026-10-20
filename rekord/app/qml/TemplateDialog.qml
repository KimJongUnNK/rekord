import QtQuick
import QtQuick.Layouts
import "."

// Write or change a template: name, category, short description, and what the AI should deliver.
// Built-in templates stay as they are – saving one makes your own copy.
Sheet {
    id: d
    required property var app
    property var t: null
    readonly property bool builtin: !!(t && t.builtin)
    signal saved()
    width: Math.min(parent ? parent.width - 48 : 760, 760)
    function edit(tpl) {
        t = tpl
        nameF.text = tpl ? (tpl.builtin ? tpl.name + " (eigene)" : tpl.name) : ""
        catF.text = tpl ? (tpl.builtin ? "Eigene" : tpl.category) : "Eigene"
        descF.text = tpl ? tpl.description || "" : ""
        promptF.text = tpl ? tpl.prompt : "# <Titel>\n## Kurzfassung\n## …\n## To-dos (- [ ] Aufgabe — **Person** — Deadline)"
        open()
        nameF.forceActiveFocus()
    }
    function save() {
        app.call("POST", "/api/templates", { id: t && !builtin ? t.id : null, name: nameF.text.trim() || "Vorlage", category: catF.text.trim(),
                                             description: descF.text.trim(), prompt: promptF.text }, () => {
            app.toast(d.builtin ? "Eigene Kopie gespeichert" : "Gespeichert")
            d.close()
            d.saved()
        })
    }
    contentItem: ColumnLayout {
        spacing: 12
        RowLayout {
            Text { text: d.t ? d.t.name : "Neue Vorlage"; font.family: Theme.display; font.pixelSize: 28; font.weight: Font.Black; color: Theme.fg; elide: Text.ElideRight; Layout.fillWidth: true }
            Tip { key: "templates" }
        }
        Muted { visible: d.builtin; Layout.fillWidth: true; text: "Eingebaute Vorlage – Speichern legt eine eigene Kopie an." }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Input { id: nameF; Layout.fillWidth: true; placeholderText: "Name" }
            Input { id: catF; Layout.preferredWidth: 200; placeholderText: "Kategorie" }
        }
        Input { id: descF; Layout.fillWidth: true; placeholderText: "Kurzbeschreibung" }
        Area {
            id: promptF
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(380, Math.max(240, d.parent ? d.parent.height - 420 : 300))
            mono: true
            placeholderText: "Was soll die KI liefern? Struktur, Abschnitte, Ton …"
        }
        Muted { Layout.fillWidth: true; font.pixelSize: 12; text: "Tipp: „- [ ]“ macht abhakbare To-dos, Überschriften mit # gliedern – und daraus wird auch die Mind Map." }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            Btn {
                visible: d.t !== null && !d.builtin
                kind: "danger"; iconName: "trash"; text: "Löschen"
                onClicked: {
                    const tpl = d.t
                    d.close()
                    d.app.confirm("„" + tpl.name + "“ löschen?", "Bestehende Zusammenfassungen bleiben.", "Löschen",
                                  () => d.app.call("DELETE", "/api/templates/" + tpl.id, null, () => { d.app.toast("Gelöscht"); d.saved() }))
                }
            }
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: "Speichern"; enabled: promptF.text.trim() !== ""; onClicked: d.save() }
        }
    }
}
