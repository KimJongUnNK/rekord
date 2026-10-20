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
    property var namingLater: ({})  // "Wer ist das? → Später" per recording, until REKORD is closed
    property string enrollMode: rekord.pref("enroll_mode") || "read"
    onEnrollModeChanged: rekord.setPref("enroll_mode", enrollMode)
    function enroll(opts, fn) { enrollDlg.start(opts, fn) }
    property bool whoOpen: false
    property bool welcomeOpen: false
    property bool quitAfterSave: false
    // the drive with the data is missing: only that message (and the settings) until it's back
    readonly property string shownPage: rekord.status.storageMissing && page !== "settings" ? "missing" : page
    readonly property bool narrow: width < 980

    Binding { target: Theme; property: "mode"; value: rekord.theme }
    Binding { target: Theme; property: "accent"; value: rekord.accent }
    // menus, tooltips, scroll bars, busy spinners follow REKORD's colors
    palette.window: Theme.card
    palette.windowText: Theme.fg
    palette.base: Theme.bg
    palette.alternateBase: Theme.card2
    palette.text: Theme.fg
    palette.button: Theme.card
    palette.buttonText: Theme.fg
    palette.brightText: Theme.fg
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.onAccent
    palette.toolTipBase: Theme.fg
    palette.toolTipText: Theme.bg
    palette.light: Theme.card2
    palette.midlight: Theme.line
    palette.mid: Theme.line2
    palette.dark: Theme.fg3
    palette.shadow: "#000000"
    palette.placeholderText: Theme.fg3
    palette.link: Theme.accent
    palette.linkVisited: Theme.accent

    property string settingsSection: ""
    function go(p, section) { page = p; settingsSection = section || ""; if (p === "library") library.refresh() }
    function openRecording(rid, t) { detailPage.open(rid, t || 0); page = "detail" }

    // ---- the local API (same one the iPhone app uses): answers arrive as callbacks
    property var _cb: ({})
    function call(method, path, body, ok, fail) {
        const id = api.request(method, path, body === undefined ? null : body)
        _cb[id] = { ok: ok, fail: fail }
        return id
    }
    function stream(path, body, onChunk, ok, fail) {
        const id = api.stream(path, body || {})
        _cb[id] = { ok: ok, fail: fail, chunk: onChunk }
        return id
    }
    function upload(path, file, fields, ok, fail) {
        const id = api.upload(path, file, JSON.stringify(fields || {}))
        _cb[id] = { ok: ok, fail: fail }
        return id
    }
    function confirm(title, text, okLabel, fn, danger) { confirmDlg.ask(title, text, okLabel, fn, danger) }
    function prompt(title, value, fn) { promptDlg.ask(title, value, fn) }
    Connections {
        target: api
        function onReply(id, ok, status, data) {
            const cb = win._cb[id]
            delete win._cb[id]
            if (!cb) return
            if (ok) { if (cb.ok) cb.ok(data) }
            else if (cb.fail) cb.fail(String(data), status)
            else win.toast(String(data))
        }
        function onChunk(id, text) { const cb = win._cb[id]; if (cb && cb.chunk) cb.chunk(text) }
        function onSaved(ok, msg) { win.toast(msg) }
    }
    function startRecording() {
        if (live.state !== "idle") { page = "live"; return }
        who.openFresh()
    }
    function importFiles() { importDialog.open() }
    function welcome(force) { welcomeWiz.start(force) }
    function quitApp() { if (live.state !== "idle") quitDialog.open(); else rekord.quit() }
    function toast(msg) { toasts.show(msg) }

    onWhoOpenChanged: if (whoOpen && !who.opened) who.openFresh(); else if (!whoOpen && who.opened) who.close()
    onWelcomeOpenChanged: if (welcomeOpen && !welcomeWiz.opened) welcomeWiz.start(true); else if (!welcomeOpen && welcomeWiz.opened) welcomeWiz.close()
    Component.onCompleted: Qt.callLater(() => welcomeWiz.start(false))  // first start: the short guided setup

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
    Connections {
        target: rekord
        function onToast(msg) { win.toast(msg) }
        function onNavigate(p, section) { win.go(p, section) }
    }

    // ---- keyboard
    Shortcut { sequences: ["Ctrl+R", "Ctrl+N"]; onActivated: win.startRecording() }
    Shortcut { sequences: [StandardKey.Find]; onActivated: { win.go("library"); libraryPage.focusSearch() } }
    Shortcut { sequence: "Ctrl+I"; onActivated: win.importFiles() }
    Shortcut { sequence: "Ctrl+1"; onActivated: win.go("library") }
    Shortcut { sequence: "Ctrl+2"; onActivated: win.go("live") }
    Shortcut { sequence: "Ctrl+3"; onActivated: win.go("ask") }
    Shortcut { sequence: "Ctrl+4"; onActivated: win.go("people") }
    Shortcut { sequence: "Ctrl+5"; onActivated: win.go("templates") }
    Shortcut { sequence: "Ctrl+,"; onActivated: win.go("settings") }  // Mac: ⌘ ,
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
            LibraryPage { id: libraryPage; app: win; anchors.fill: parent; shown: win.shownPage === "library" }
            DetailPage { id: detailPage; app: win; anchors.fill: parent; shown: win.shownPage === "detail" }
            LivePage { app: win; anchors.fill: parent; shown: win.shownPage === "live" }
            PeoplePage { app: win; anchors.fill: parent; shown: win.shownPage === "people" }
            SettingsPage { app: win; anchors.fill: parent; shown: win.shownPage === "settings" }
            MissingPage { app: win; anchors.fill: parent; shown: win.shownPage === "missing" }
            AskPage { app: win; anchors.fill: parent; shown: win.shownPage === "ask" }
            TemplatesPage { app: win; anchors.fill: parent; shown: win.shownPage === "templates" }
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

    EnrollDialog { id: enrollDlg; objectName: "enrollDlg"; app: win }

    WhoDialog {
        id: who
        app: win
        onOpened: win.whoOpen = true
        onClosed: win.whoOpen = false
        onStarted: win.page = "live"
    }

    WelcomeWizard {
        id: welcomeWiz
        app: win
        onOpened: win.welcomeOpen = true
        onClosed: win.welcomeOpen = false
    }

    ConfirmDialog { id: confirmDlg }
    PromptDialog { id: promptDlg }

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
