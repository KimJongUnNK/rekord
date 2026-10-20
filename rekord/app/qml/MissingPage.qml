import QtQuick
import QtQuick.Layouts
import "."

// The drive with REKORD's data isn't connected: say so instead of showing an empty library.
Page {
    id: page
    required property var app
    property string msg: ""
    property bool waiting: false

    function retry() {
        msg = "Suche …"
        app.call("POST", "/api/storage/missing", { action: "retry" }, (r) => {
            if (!r.found) { page.msg = "Noch nicht gefunden."; return }
            page.waiting = true
            page.msg = "Gefunden – REKORD startet neu …"
        })
    }
    function forget() {
        app.confirm("Neu anfangen?", "REKORD legt einen neuen, leeren Ordner auf diesem Computer an. Die Daten auf dem Laufwerk bleiben unberührt – du kannst später wieder dorthin wechseln.",
                    "Neu anfangen", () => app.call("POST", "/api/storage/missing", { action: "forget" }, () => { page.waiting = true; page.msg = "REKORD startet neu …" }))
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 72, 620)
        spacing: 18
        Rectangle {
            width: 84; height: 84; radius: 42
            color: Theme.accentSoft
            Icon { anchors.centerIn: parent; width: 38; height: 38; name: "drive"; color: Theme.accent }
        }
        Title { text: "Laufwerk fehlt." }
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            textFormat: Text.StyledText
            font.family: Theme.text; font.pixelSize: 16; color: Theme.fg
            text: "REKORD speichert auf <b>" + rekord.status.storageMissing + "</b> – dieses Laufwerk ist gerade nicht angeschlossen."
        }
        Muted {
            Layout.fillWidth: true
            text: "Schließ die Festplatte an (oder verbinde das Netzlaufwerk) und klick auf „Nochmal prüfen“. Deine Aufnahmen sind dort sicher."
        }
        RowLayout {
            spacing: 10
            Btn { kind: "primary"; iconName: "refresh"; text: "Nochmal prüfen"; enabled: !page.waiting; onClicked: page.retry() }
            Btn { text: "Neu auf diesem Computer anfangen"; enabled: !page.waiting; onClicked: page.forget() }
            Tip { key: "storage" }
        }
        Muted { visible: page.msg !== ""; text: page.msg }
    }
}
