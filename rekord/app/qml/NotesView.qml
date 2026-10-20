import QtQuick
import QtQuick.Layouts
import "."

// Own notes (they flow into summaries) and the folder.
Item {
    id: v
    required property var page
    property bool ready: false
    function fill() { ready = false; notes.text = page.rec ? (page.rec.notes || "") : ""; folder.text = page.rec ? (page.rec.folder || "") : ""; ready = true }
    Timer { id: saveT; interval: 800; onTriggered: v.page.app.call("PATCH", "/api/recordings/" + v.page.rid, { notes: notes.text }, () => v.page.app.toast("Notizen gespeichert")) }
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Muted { text: "Eigene Notizen. Fließen in Zusammenfassungen ein." }
        Area { id: notes; Layout.fillWidth: true; Layout.fillHeight: true; placeholderText: "Notizen …"; onEdited: if (v.ready) saveT.restart() }
        RowLayout {
            spacing: 10
            Muted { text: "Ordner" }
            Input {
                id: folder
                Layout.preferredWidth: 320
                placeholderText: "z. B. Voltage, Coffee Club, Uni"
                onEditingFinished: if (v.ready && text.trim() !== (v.page.rec.folder || "")) v.page.app.call("PATCH", "/api/recordings/" + v.page.rid, { folder: text.trim() }, () => { v.page.app.toast("Ordner gespeichert"); v.page.reload() })
            }
            Repeater {
                model: library.folders.filter(f => f !== folder.text).slice(0, 6)
                delegate: Chip { required property string modelData; text: modelData; onClicked: { folder.text = modelData; folder.editingFinished() } }
            }
        }
    }
}
