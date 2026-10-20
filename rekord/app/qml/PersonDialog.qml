import QtQuick
import QtQuick.Layouts
import "."

// A person REKORD knows: name, color – or forget the voiceprint.
Sheet {
    id: d
    required property var app
    property var p: ({})
    property string color: "#3B82F6"
    readonly property var swatches: ["#FF5A1F", "#3B82F6", "#22C55E", "#E11D74", "#A855F7", "#EAB308", "#0EA5E9", "#F97316", "#14B8A6", "#EF4444", "#8B5CF6", "#64748B"]
    function edit(person) { p = person; nameF.text = person.name; color = person.color; hex.text = person.color; open() }
    function save() {
        const c = /^#[0-9a-fA-F]{6}$/.test(hex.text) ? hex.text : color
        app.call("PATCH", "/api/profiles/" + p.id, { name: nameF.text.trim(), color: c }, () => { app.toast("Gespeichert"); people.refresh(); d.close() })
    }
    contentItem: ColumnLayout {
        spacing: 14
        Text { text: d.p.name || ""; font.family: Theme.display; font.pixelSize: 28; font.weight: Font.Black; color: Theme.fg }
        Muted { text: "Name" }
        Input { id: nameF; Layout.fillWidth: true; big: true; onAccepted: d.save() }
        Muted { text: "Farbe" }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: d.swatches
                delegate: Rectangle {
                    required property string modelData
                    width: 30; height: 30; radius: 15
                    color: modelData
                    border.width: d.color.toUpperCase() === modelData ? 3 : 0
                    border.color: Theme.fg
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { d.color = modelData; hex.text = modelData } }
                }
            }
            Input { id: hex; width: 110; placeholderText: "#RRGGBB"; onTextEdited: if (/^#[0-9a-fA-F]{6}$/.test(text)) d.color = text.toUpperCase() }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            Btn {
                kind: "danger"
                text: "Stimmabdruck löschen"
                onClicked: {
                    const person = d.p
                    d.close()
                    d.app.confirm(person.name + " vergessen?", "Der Stimmabdruck wird gelöscht. Bestehende Transkripte behalten den Namen.", "Löschen",
                                  () => d.app.call("DELETE", "/api/profiles/" + person.id, null, () => { d.app.toast("Gelöscht"); people.refresh() }))
                }
            }
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: "Speichern"; enabled: nameF.text.trim() !== ""; onClicked: d.save() }
        }
    }
}
