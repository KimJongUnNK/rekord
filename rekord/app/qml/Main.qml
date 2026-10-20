import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "."

ApplicationWindow {
    id: win
    width: 1280
    height: 840
    minimumWidth: 760
    minimumHeight: 580
    visible: true
    color: Theme.bg
    title: live.state === "recording" ? "● " + live.elapsedText + " – REKORD" : live.state === "paused" ? "Pausiert – REKORD" : "REKORD"

    property string page: "library"
    property bool whoOpen: false
    property bool quitAfterSave: false
    readonly property bool narrow: width < 980

    Binding { target: Theme; property: "mode"; value: rekord.theme }

    function go(p) { page = p; if (p === "library") library.refresh() }
    function openRecording(rid) { detail.load(rid); page = "detail" }
    function startRecording() {
        if (live.state !== "idle") { page = "live"; return }
        who.openFresh()
    }
    function importFiles() { importDialog.open() }
    function toast(msg) { toasts.show(msg) }

    onWhoOpenChanged: if (whoOpen && !who.opened) who.openFresh(); else if (!whoOpen && who.opened) who.close()

    onClosing: (close) => {
        if (live.state !== "idle") { close.accepted = false; quitDialog.open(); return }
        if (rekord.keepRunning) { close.accepted = false; win.hide(); return }  // keeps running for the iPhone
        rekord.quit()
    }

    Connections {
        target: live
        function onFinished(rid) {
            if (win.quitAfterSave) { rekord.quit(); return }
            win.toast("Gespeichert – REKORD wertet jetzt alles noch einmal genau aus.")
            library.refresh()
            win.openRecording(rid)
        }
        function onToast(msg) { win.toast(msg) }
    }
    Connections { target: library; function onToast(msg) { win.toast(msg) } }
    Connections { target: rekord; function onToast(msg) { win.toast(msg) } }

    // ---- keyboard
    Shortcut { sequences: ["Ctrl+R", "Ctrl+N"]; onActivated: win.startRecording() }
    Shortcut { sequences: [StandardKey.Find]; onActivated: { win.go("library"); libraryPage.focusSearch() } }
    Shortcut { sequence: "Ctrl+I"; onActivated: win.importFiles() }
    Shortcut { sequence: "Ctrl+1"; onActivated: win.go("library") }
    Shortcut { sequence: "Ctrl+2"; onActivated: win.go("live") }
    Shortcut {
        sequence: "Space"
        enabled: win.page === "live" && (live.state === "recording" || live.state === "paused") && !who.opened
        onActivated: live.state === "paused" ? live.resume() : live.pause()
    }
    Shortcut {
        sequence: "H"
        enabled: win.page === "live" && live.state === "recording" && !who.opened
        onActivated: live.highlight()
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Sidebar {
            app: win
            Layout.fillHeight: true
            Layout.preferredWidth: win.narrow ? 76 : 236
            Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.mid; easing.type: Easing.OutCubic } }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            LibraryPage { id: libraryPage; app: win; anchors.fill: parent; shown: win.page === "library" }
            DetailPage { app: win; anchors.fill: parent; shown: win.page === "detail" }
            LivePage { app: win; anchors.fill: parent; shown: win.page === "live" }
            ClassicPage {
                anchors.fill: parent
                shown: ["ask", "people", "templates", "settings"].indexOf(win.page) >= 0
                which: shown ? win.page : which
            }
        }
    }

    // ---- drop files anywhere to import them
    DropArea {
        id: drop
        anchors.fill: parent
        keys: ["text/uri-list"]
        onDropped: (ev) => { library.importFiles(ev.urls); win.go("library") }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: 14
        radius: 20
        visible: opacity > 0
        opacity: drop.containsDrag ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        color: Qt.rgba(Theme.bg.r, Theme.bg.g, Theme.bg.b, 0.9)
        border.width: 3
        border.color: Theme.accent
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 12
            Icon { Layout.alignment: Qt.AlignHCenter; name: "import"; width: 54; height: 54; color: Theme.accent; stroke: 1.6 }
            Text { text: "Loslassen zum Importieren"; font.family: Theme.display; font.pixelSize: 32; font.weight: Font.Black; color: Theme.fg }
            Text { Layout.alignment: Qt.AlignHCenter; text: "Audio oder Video – REKORD erkennt, wer was gesagt hat."; font.family: Theme.text; font.pixelSize: 15; color: Theme.fg2 }
        }
    }

    FileDialog {
        id: importDialog
        title: "Aufnahmen importieren"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Audio & Video (*.m4a *.mp3 *.wav *.webm *.ogg *.opus *.flac *.aac *.mp4 *.mov *.mkv *.caf *.amr *.3gp)", "Alle Dateien (*)"]
        onAccepted: { library.importFiles(selectedFiles); win.go("library") }
    }

    WhoDialog {
        id: who
        onOpened: win.whoOpen = true
        onClosed: win.whoOpen = false
        onStarted: win.page = "live"
    }

    Sheet {  // closing while recording
        id: quitDialog
        contentItem: ColumnLayout {
            spacing: 14
            Text { text: "Die Aufnahme läuft noch"; font.family: Theme.display; font.pixelSize: 28; font.weight: Font.Black; font.letterSpacing: -0.8; color: Theme.fg }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Beim Beenden speichert REKORD sie zuerst – nichts geht verloren. Die genaue Auswertung macht REKORD beim nächsten Start fertig."
                font.family: Theme.text; font.pixelSize: 15; color: Theme.fg2
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 6
                Item { Layout.fillWidth: true }
                Btn { text: "Weiter aufnehmen"; onClicked: quitDialog.close() }
                Btn {
                    kind: "primary"
                    text: "Speichern & beenden"
                    iconName: "stop"
                    onClicked: {
                        quitDialog.close()
                        win.quitAfterSave = true
                        win.page = "live"
                        if (!live.stopForQuit()) rekord.quit()
                    }
                }
            }
        }
    }

    Toasts {
        id: toasts
        anchors.bottom: parent.bottom
        anchors.bottomMargin: win.page === "live" && live.state !== "idle" ? 104 : 28
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
        z: 100
    }
}
