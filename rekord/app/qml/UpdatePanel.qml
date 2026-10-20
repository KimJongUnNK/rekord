import QtQuick
import QtQuick.Layouts
import "."

// Version & Updates: look for a new REKORD, read what's new, install (it replaces itself and restarts).
ColumnLayout {
    id: u
    required property var app
    property var info: null
    property bool checking: false
    spacing: 8
    function load(check) {
        checking = !!check
        app.call(check ? "POST" : "GET", check ? "/api/update/check" : "/api/update", null, (r) => { u.checking = false; u.info = r }, (e) => { u.checking = false; u.app.toast(e) })
    }
    Component.onCompleted: load(false)
    Timer {  // follow a running update
        running: u.info !== null && ["downloading", "installing", "restarting"].indexOf(u.info.state) >= 0
        interval: 700; repeat: true
        onTriggered: u.load(false)
    }
    Text {
        textFormat: Text.StyledText
        font.family: Theme.text; font.pixelSize: 14; color: Theme.fg
        text: u.info ? "REKORD <b>" + u.info.current + "</b>" + (u.info.available ? " · neu: <b><font color='" + Theme.accent + "'>" + u.info.latest + "</font></b>" : "") : "REKORD " + rekord.version
    }
    ColumnLayout {
        visible: u.info !== null && u.info.state === "downloading"
        Layout.fillWidth: true
        Muted { text: u.info ? "Lade Version " + u.info.latest + " … " + (u.info.total ? Math.round(u.info.done / u.info.total * 100) : 0) + " %" : "" }
        Bar { Layout.fillWidth: true; value: u.info && u.info.total ? u.info.done / u.info.total : 0 }
    }
    Muted { visible: u.info !== null && u.info.state === "installing"; text: "Installiere – ersetzt die alte Version …" }
    Muted { visible: u.info !== null && u.info.state === "restarting"; text: "REKORD startet neu …" }
    Text { visible: u.info !== null && !!u.info.error; text: u.info ? u.info.error || "" : ""; color: Theme.err; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    ColumnLayout {
        visible: u.info !== null && u.info.available && ["downloading", "installing", "restarting"].indexOf(u.info.state) < 0
        Layout.fillWidth: true
        spacing: 8
        Rectangle {
            visible: u.info && !!u.info.notes
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(260, notes.implicitHeight + 24)
            radius: 10
            color: Theme.card2
            Flickable {
                anchors.fill: parent
                anchors.margins: 12
                clip: true
                contentHeight: notes.implicitHeight
                Markdown { id: notes; width: parent.width; source: u.info ? u.info.notes || "" : ""; font.pixelSize: 13 }
            }
        }
        Btn {
            visible: u.info && u.info.can_install
            kind: "primary"
            text: u.info ? "Jetzt auf " + u.info.latest + " aktualisieren" : ""
            iconName: "download"
            onClicked: u.app.confirm("Auf " + u.info.latest + " aktualisieren?", "REKORD lädt die neue Version, ersetzt die alte und startet neu. Aufnahmen, Personen und Einstellungen bleiben.", "Aktualisieren",
                                     () => u.app.call("POST", "/api/update/install", null, (r) => u.info = r, (e) => { u.app.toast(e); u.load(false) }), false)
        }
        Markdown { visible: u.info && !u.info.can_install; Layout.fillWidth: true; source: u.info ? u.info.manual || "" : ""; font.pixelSize: 13 }
    }
    Muted {
        visible: u.info !== null && !u.info.available && ["downloading", "installing", "restarting"].indexOf(u.info.state) < 0
        font.pixelSize: 13
        text: !u.info ? "" : u.info.latest ? "✓ Aktuell" + (u.info.checked ? " · geprüft vor " + Math.max(1, Math.round((Date.now() / 1000 - u.info.checked) / 60)) + " min" : "")
                                          : u.info.check_error || "Noch nicht geprüft"
    }
    RowLayout {
        Btn { small: true; text: u.checking ? "Suche …" : "Nach Updates suchen"; enabled: !u.checking; iconName: "refresh"; onClicked: u.load(true) }
        Btn { visible: u.info && !!u.info.page; small: true; text: "Release-Seite"; iconName: "open"; onClicked: api.openUrl(u.info.page) }
    }
}
