import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// First start: a short guided setup. Willkommen → Speicherort (before any big download) → Aussehen → Sprache →
// Mikrofon → KI → Deine Stimme → iPhone → Fertig. Every step can be skipped and changed later in the settings.
Popup {
    id: w
    objectName: "welcomeWiz"
    required property var app
    parent: Overlay.overlay
    x: 0; y: 0
    width: parent ? parent.width : 800
    height: parent ? parent.height : 600
    modal: true
    closePolicy: Popup.NoAutoClose
    padding: 0
    property var steps: []
    property int i: 0
    property bool needStorage: false
    property var st: null
    property var storage: null
    property int drive: -1
    property bool sameModels: true
    property bool micOk: false
    property string voiceName: ""
    property var settings: null
    property var pair: null
    property var known: []
    readonly property string step: steps[i] || "hi"

    function start(force) {
        app.call("GET", "/api/status", null, (s) => {
            w.st = s
            if (s.storage_missing) return
            if (!force && s.welcome_done) return
            w.needStorage = !s.storage_chosen
            w.steps = ["hi", "storage", "look", "lang", "mic", "ai", "voice", "phone", "done"]
            let saved = Number(rekord.pref("welcome_step") || 0)
            if (force) saved = 0
            w.i = Math.max(0, Math.min(w.steps.length - 1, saved))
            if (w.needStorage) w.i = Math.min(w.i, 1)
            w.open()
            w.enterStep()
        }, () => {})
    }
    function go(n) {
        leaveStep()
        i = Math.max(0, Math.min(steps.length - 1, n))
        rekord.setPref("welcome_step", i)
        enterStep()
    }
    function enterStep() {
        if (step === "storage") app.call("GET", "/api/storage", null, (s) => {
            w.storage = s
            const d = (s.drives || [])
            const k = d.findIndex(x => s.home.indexOf(x.path) === 0 && x.path !== "/")
            w.pickDrive(k >= 0 ? k : 0)
        })
        if (step === "lang" || step === "ai") app.call("GET", "/api/settings", null, (s) => w.settings = s)
        if (step === "mic") { live.refreshMics(); voice.start(600) }
        if (step === "voice") app.call("GET", "/api/profiles", null, (r) => w.known = r.items)
        if (step === "phone") app.call("GET", "/api/pair", null, (r) => w.pair = r, () => {})
        if (step === "done") app.call("GET", "/api/status", null, (s) => w.st = s)
    }
    function leaveStep() { if (step === "mic") voice.discard() }
    function pickDrive(k) {
        drive = k
        if (!storage || !storage.drives || !storage.drives[k]) { homeF.text = storage ? storage.home : ""; return }
        const d = storage.drives[k], sug = storage.suggest[d.path] || { home: storage.home, models: storage.models }
        homeF.text = !needStorage && storage.home.indexOf(d.path) === 0 && d.path !== "/" ? storage.home : sug.home
        if (sameModels) modelsF.text = sug.models
    }
    function finish(thenRecord) {
        leaveStep()
        app.call("PUT", "/api/settings", { welcome_done: true }, () => rekord.refresh())
        rekord.setPref("welcome_step", 0)
        close()
        if (thenRecord) app.startRecording()
    }
    function skip() {
        if (step === "storage" && needStorage) {  // keep the default place, but go on (models load now)
            app.call("POST", "/api/storage/choose", {}, () => go(i + 1))
            return
        }
        finish(false)
    }
    function storeAndGo() {
        const home = homeF.text.trim(), models = sameModels ? "" : modelsF.text.trim()
        if (!needStorage && home === storage.home && !models) { go(i + 1); return }
        rekord.setPref("welcome_step", i + 1)  // a move ends with a restart: continue there
        if (!needStorage && home !== storage.home) {
            app.call("POST", "/api/storage/move", { what: "home", target: home }, () => moveJob.active = true)
            return
        }
        app.call("POST", "/api/storage/choose", { home: home, models: models }, (r) => {
            if (r.state === "running") moveJob.active = true
            else go(i + 1)
        })
    }
    function gb(n) { return (n || 0).toLocaleString(Qt.locale("de_AT"), "f", 1) + " GB" }

    background: Rectangle { color: Theme.bg }
    contentItem: Item {
        Rectangle {
            id: card
            anchors.centerIn: parent
            width: Math.min(parent.width - 48, 760)
            height: Math.min(parent.height - 48, 680)
            radius: 22
            color: Theme.card
            border.width: 1
            border.color: Theme.line
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 18
                RowLayout {  // brand, progress dots, skip
                    Layout.fillWidth: true
                    Text { text: "REKORD"; font.family: Theme.display; font.pixelSize: 22; font.weight: Font.Black; font.letterSpacing: -1; color: Theme.fg }
                    Item { Layout.fillWidth: true }
                    Row {
                        spacing: 6
                        Repeater {
                            model: w.steps.length
                            delegate: Rectangle {
                                required property int index
                                width: index === w.i ? 22 : 8; height: 8; radius: 4
                                color: index === w.i ? Theme.accent : index < w.i ? Theme.fg2 : Theme.line2
                                Behavior on width { NumberAnimation { duration: Theme.mid } }
                            }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Btn { visible: w.step !== "done"; kind: "ghost"; small: true; text: "Überspringen"; onClicked: w.skip() }
                }

                Flickable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentHeight: body.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}
                    ColumnLayout {
                        id: body
                        width: parent.width - 8
                        spacing: 14

                        // ---- Willkommen
                        ColumnLayout {
                            visible: w.step === "hi"
                            Layout.fillWidth: true
                            spacing: 14
                            Text { text: "Hallo."; font.family: Theme.display; font.pixelSize: 64; font.weight: Font.Black; font.letterSpacing: -3; color: Theme.fg }
                            Text {
                                Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.StyledText
                                font.family: Theme.text; font.pixelSize: 18; lineHeight: 1.2; color: Theme.fg
                                text: "REKORD nimmt Meetings auf, erkennt live, <b>wer gerade spricht</b>, und schreibt dir danach Protokoll, To-dos und Mind Map."
                            }
                            Repeater {
                                model: ["<b>Erkennt Menschen an der Stimme</b> – einmal einsprechen, ab dann in jedem Meeting.",
                                        "<b>Alles auf deinem Computer</b> – Audio und Stimmen verlassen ihn nie.",
                                        "<b>Deine KI</b> – Claude, ChatGPT oder komplett offline."]
                                delegate: RowLayout {
                                    required property string modelData
                                    Layout.fillWidth: true
                                    Rectangle { width: 8; height: 8; radius: 4; color: Theme.accent }
                                    Text { Layout.fillWidth: true; text: modelData; textFormat: Text.StyledText; wrapMode: Text.WordWrap; font.family: Theme.text; font.pixelSize: 15; color: Theme.fg }
                                }
                            }
                            Muted { Layout.fillWidth: true; text: "Die Einrichtung dauert 2–3 Minuten. Jeder Schritt lässt sich überspringen und später ändern. Überall, wo du ein ⓘ siehst, steht die Erklärung." }
                        }

                        // ---- Speicherort
                        ColumnLayout {
                            visible: w.step === "storage"
                            Layout.fillWidth: true
                            spacing: 12
                            Eyebrow { text: "Schritt " + (w.i + 1) + " · Speicherort" }
                            RowLayout { Text { text: "Wo soll REKORD speichern?"; font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; color: Theme.fg } Tip { key: "storage" } }
                            Muted {
                                Layout.fillWidth: true
                                text: "Aufnahmen, Stimmabdrücke und die KI-Modelle. Wähle ein Laufwerk – auch eine externe Festplatte, eine zweite SSD (NVMe) oder ein Netzlaufwerk geht."
                                      + (w.needStorage ? " Erst danach lädt REKORD die Sprachmodelle (~0,7 GB)." : "")
                            }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 8
                                Repeater {
                                    model: w.storage && w.storage.drives ? w.storage.drives : []
                                    delegate: AbstractButton {
                                        id: dv
                                        required property var modelData
                                        required property int index
                                        width: 300; height: 56
                                        hoverEnabled: true
                                        onClicked: w.pickDrive(index)
                                        background: Rectangle { radius: 12; color: w.drive === dv.index ? Theme.accentSoft : dv.hovered ? Theme.card2 : Theme.bg; border.width: w.drive === dv.index ? 2 : 1; border.color: w.drive === dv.index ? Theme.accent : Theme.line }
                                        contentItem: RowLayout {
                                            spacing: 10
                                            Text { Layout.leftMargin: 12; text: ({ internal: "💻", external: "🔌", nvme: "⚡", network: "🌐", removable: "💾" })[dv.modelData.kind] || "💽"; font.pixelSize: 22 }
                                            ColumnLayout {
                                                spacing: 0
                                                Layout.fillWidth: true
                                                Text { Layout.fillWidth: true; text: dv.modelData.name; elide: Text.ElideRight; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
                                                Text { text: dv.modelData.kind_label + " · " + w.gb(dv.modelData.free_gb) + " frei"; font.family: Theme.text; font.pixelSize: 12; color: Theme.fg3 }
                                            }
                                        }
                                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                                    }
                                }
                            }
                            Muted { text: "Ordner für REKORD" }
                            Input { id: homeF; Layout.fillWidth: true }
                            RowLayout { Check { text: "KI-Modelle im selben Ordner"; checked: w.sameModels; onToggled: { w.sameModels = checked; w.pickDrive(w.drive) } } Tip { key: "modelsdir" } }
                            Input { id: modelsF; visible: !w.sameModels; Layout.fillWidth: true; placeholderText: "Ordner für KI-Modelle" }
                            Muted { font.pixelSize: 12; text: "Platzbedarf: Sprachmodelle ~0,7 GB · lokale KI 3–6 GB (optional) · Aufnahmen ~30 MB pro Stunde." }
                            StorageJob { id: moveJob; Layout.fillWidth: true; app: w.app; onFinished: w.go(w.i + 1) }
                        }

                        // ---- Aussehen
                        ColumnLayout {
                            visible: w.step === "look"
                            Layout.fillWidth: true
                            spacing: 14
                            Eyebrow { text: "Schritt " + (w.i + 1) + " · Aussehen" }
                            Text { text: "So soll's aussehen."; font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; color: Theme.fg }
                            RowLayout { Text { text: "Erscheinungsbild"; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg } Tip { key: "theme" } }
                            Segmented {
                                Layout.maximumWidth: 420; Layout.fillWidth: true
                                model: [{ value: "system", label: "System" }, { value: "light", label: "Hell" }, { value: "dark", label: "Dunkel" }]
                                value: rekord.theme
                                onPicked: (v) => rekord.setTheme(v)
                            }
                            RowLayout { Text { text: "Akzentfarbe"; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg } Tip { key: "accent" } }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 8
                                Repeater {
                                    model: ["#FF5A1F", "#2D7FF9", "#C6F432", "#E11D74", "#8B5CF6", "#FACC15", "#EF4444", "#14B8A6", "#F6F5F2"]
                                    delegate: Rectangle {
                                        required property string modelData
                                        width: 36; height: 36; radius: 18; color: modelData
                                        border.width: rekord.accent.toUpperCase() === modelData ? 3 : 1
                                        border.color: rekord.accent.toUpperCase() === modelData ? Theme.fg : Theme.line
                                        TapHandler { onTapped: rekord.setAccent(modelData) }
                                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                                    }
                                }
                            }
                            Muted { font.pixelSize: 13; text: "Du siehst die Änderung sofort." }
                        }

                        // ---- Sprache
                        ColumnLayout {
                            visible: w.step === "lang"
                            Layout.fillWidth: true
                            spacing: 12
                            Eyebrow { text: "Schritt " + (w.i + 1) + " · Sprache" }
                            Text { text: "Welche Sprache sprecht ihr?"; font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; color: Theme.fg }
                            RowLayout { Text { text: "Sprache in den Meetings"; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg } Tip { key: "lang" } }
                            Select {
                                Layout.maximumWidth: 320
                                options: [["", "Automatisch (pro Satz)"], ["de", "Deutsch"], ["en", "Englisch"], ["fr", "Französisch"], ["it", "Italienisch"], ["es", "Spanisch"],
                                          ["nl", "Niederländisch"], ["pt", "Portugiesisch"], ["pl", "Polnisch"], ["tr", "Türkisch"], ["ru", "Russisch"], ["uk", "Ukrainisch"],
                                          ["hr", "Kroatisch"], ["sr", "Serbisch"], ["ar", "Arabisch"], ["zh", "Chinesisch"], ["ja", "Japanisch"], ["ko", "Koreanisch"]].map(x => ({ value: x[0], label: x[1] }))
                                value: w.settings ? w.settings.language : ""
                                onPicked: (v) => w.app.call("PUT", "/api/settings", { language: v }, () => w.app.toast("Gespeichert"))
                            }
                            Muted { font.pixelSize: 13; Layout.fillWidth: true; text: "Fest eingestellt ist am genauesten. Automatisch erkennt die Sprache pro Satz – für gemischte Runden." }
                            RowLayout { Text { text: "Protokolle schreiben auf"; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg } Tip { key: "sumlang" } }
                            Select {
                                Layout.maximumWidth: 320
                                options: [{ value: "de", label: "Deutsch" }, { value: "en", label: "Englisch" }, { value: "auto", label: "Wie im Gespräch" }]
                                value: w.settings ? w.settings.summary_language : "de"
                                onPicked: (v) => w.app.call("PUT", "/api/settings", { summary_language: v }, () => w.app.toast("Gespeichert"))
                            }
                        }

                        // ---- Mikrofon
                        ColumnLayout {
                            visible: w.step === "mic"
                            Layout.fillWidth: true
                            spacing: 12
                            Eyebrow { text: "Schritt " + (w.i + 1) + " · Mikrofon" }
                            Text { text: "Hört REKORD dich?"; font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; color: Theme.fg }
                            Muted { Layout.fillWidth: true; text: "Wähle dein Mikrofon und sag etwas – der Balken sollte bis etwa zur Mitte ausschlagen." }
                            RowLayout { Text { text: "Mikrofon"; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg } Tip { key: "mic" } }
                            Select {
                                Layout.maximumWidth: 460; Layout.fillWidth: true
                                options: [{ value: "", label: "Standard-Mikrofon des Systems" }].concat(live.mics.map(m => ({ value: m.id, label: m.name })))
                                value: live.mic
                                onPicked: (v) => { live.setMic(v); voice.discard(); voice.start(600) }
                            }
                            Text { visible: live.micHint !== ""; Layout.fillWidth: true; text: live.micHint; wrapMode: Text.WordWrap; font.family: Theme.text; font.pixelSize: 12; color: Theme.warn }
                            Rectangle {
                                Layout.fillWidth: true
                                height: 16; radius: 8
                                color: Theme.card2
                                Rectangle {
                                    height: parent.height; radius: 8
                                    width: parent.width * voice.level
                                    color: Theme.accent
                                    Behavior on width { NumberAnimation { duration: 80 } }
                                    onWidthChanged: if (w.step === "mic" && voice.recording && voice.level > 0.25) w.micOk = true
                                }
                            }
                            Text {
                                font.family: Theme.text; font.pixelSize: 13
                                color: w.micOk ? Theme.ok : Theme.fg2
                                text: w.micOk ? "✓ REKORD hört dich." : Qt.platform.os === "osx" ? "Fragt macOS nach dem Mikrofon: Erlauben. Dann etwas sagen – zum Beispiel deinen Namen." : "Sag etwas – zum Beispiel deinen Namen."
                            }
                        }

                        // ---- KI
                        ColumnLayout {
                            visible: w.step === "ai"
                            Layout.fillWidth: true
                            spacing: 12
                            Eyebrow { text: "Schritt " + (w.i + 1) + " · KI" }
                            RowLayout { Text { text: "Wer schreibt deine Protokolle?"; font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; color: Theme.fg } Tip { key: "provider" } }
                            Text {
                                visible: !!rekord.status.ai
                                Layout.fillWidth: true; wrapMode: Text.WordWrap
                                text: "✓ Schon eingerichtet: " + rekord.status.ai + ". Du kannst das jederzeit ändern."
                                font.family: Theme.text; font.pixelSize: 14; color: Theme.ok
                            }
                            AiChoice { Layout.fillWidth: true; app: w.app }
                            Muted { font.pixelSize: 12; Layout.fillWidth: true; text: "Die lokale KI wird im Hintergrund fertig – du kannst schon weitermachen." }
                        }

                        // ---- Deine Stimme
                        ColumnLayout {
                            visible: w.step === "voice"
                            Layout.fillWidth: true
                            spacing: 12
                            Eyebrow { text: "Schritt " + (w.i + 1) + " · Deine Stimme" }
                            Text { text: "Damit REKORD dich erkennt."; font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; color: Theme.fg }
                            Muted { Layout.fillWidth: true; text: "Ca. 45 Sekunden sprechen – entweder einen Text vorlesen (jede Person bekommt ihren eigenen) oder einfach über irgendwas reden. Danach steht in jedem Meeting dein Name statt „Nicht erkannte Stimme“." }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 8
                                visible: w.known.length > 0
                                Muted { text: "Schon bekannt:" }
                                Repeater { model: w.known; delegate: Chip { required property var modelData; text: modelData.name; dot: modelData.color; enabled: false } }
                            }
                            RowLayout {
                                Input { id: myName; Layout.preferredWidth: 280; placeholderText: "Dein Name" }
                                Btn {
                                    kind: "primary"; iconName: "mic"; text: "Jetzt einsprechen"
                                    onClicked: w.app.enroll({ name: myName.text.trim() }, (prof) => {
                                        w.voiceName = prof.name
                                        w.app.call("GET", "/api/profiles", null, (r) => w.known = r.items)
                                    })
                                }
                            }
                            Text { visible: w.voiceName !== ""; text: "✓ " + w.voiceName + " ist gespeichert."; color: Theme.ok; font.pixelSize: 14; font.weight: Font.Bold }
                            Muted { font.pixelSize: 13; Layout.fillWidth: true; text: "Andere Leute sprichst du später unter Personen ein – oder direkt vor einem Meeting bei „Wer ist dabei?“." }
                        }

                        // ---- iPhone
                        ColumnLayout {
                            visible: w.step === "phone"
                            Layout.fillWidth: true
                            spacing: 12
                            Eyebrow { text: "Schritt " + (w.i + 1) + " · iPhone" }
                            Text { text: "Auch am iPhone aufnehmen?"; font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; color: Theme.fg }
                            Muted { Layout.fillWidth: true; text: "Mit der REKORD-App am iPhone: dort auf Koppeln tippen, den Code scannen oder die 6 Ziffern eintippen. Alles, was du am iPhone aufnimmst, landet hier." }
                            RowLayout {
                                visible: w.pair !== null && w.pair.urls.length > 0
                                spacing: 24
                                QrView { rows: w.pair ? w.pair.qr_rows : []; Layout.preferredWidth: 200; Layout.preferredHeight: 200 }
                                ColumnLayout {
                                    Text { text: w.pair ? w.pair.code.code.slice(0, 3) + " " + w.pair.code.code.slice(3) : ""; font.family: Theme.display; font.pixelSize: 40; font.weight: Font.Black; font.letterSpacing: 4; color: Theme.fg }
                                    Muted { Layout.maximumWidth: 280; text: "iPhone und Computer im selben WLAN. Der Code gilt 10 Minuten – später jederzeit unter Einstellungen → iPhone & Geräte." }
                                }
                            }
                            Muted { visible: w.pair === null || w.pair.urls.length === 0; text: "Gerade kein WLAN gefunden. Später unter Einstellungen → iPhone & Geräte." }
                        }

                        // ---- Fertig
                        ColumnLayout {
                            visible: w.step === "done"
                            Layout.fillWidth: true
                            spacing: 12
                            Text { text: "Fertig."; font.family: Theme.display; font.pixelSize: 64; font.weight: Font.Black; font.letterSpacing: -3; color: Theme.fg }
                            Repeater {
                                model: [[true, "Aussehen"],
                                        [w.micOk, w.micOk ? "Mikrofon hört dich" : "Mikrofon – nicht getestet"],
                                        [!!rekord.status.ai, rekord.status.ai ? "KI: " + rekord.status.ai : "KI – später unter Einstellungen → KI"],
                                        [w.voiceName !== "", w.voiceName ? "Deine Stimme: " + w.voiceName : "Deine Stimme – später unter Personen"]]
                                delegate: Text {
                                    required property var modelData
                                    text: (modelData[0] ? "✓  " : "–  ") + modelData[1]
                                    font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Bold
                                    color: modelData[0] ? Theme.ok : Theme.fg2
                                }
                            }
                            Text {
                                Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.StyledText
                                font.family: Theme.text; font.pixelSize: 15; color: Theme.fg
                                text: "Vor jeder Aufnahme fragt REKORD kurz: <b>Wer ist dabei?</b> – wie viele ihr seid und wer schon bekannt ist. So erkennt es jede Stimme richtig."
                            }
                        }
                    }
                }

                RowLayout {  // back / next
                    Layout.fillWidth: true
                    Btn { visible: w.i > 0; text: "Zurück"; onClicked: w.go(w.i - 1) }
                    Item { Layout.fillWidth: true }
                    Btn { visible: w.step === "done"; text: "Zur App"; onClicked: w.finish(false) }
                    Btn { visible: w.step === "done"; kind: "primary"; iconName: "record"; text: "Erste Aufnahme"; onClicked: w.finish(true) }
                    Btn {
                        visible: w.step !== "done"
                        kind: "primary"
                        text: w.step === "hi" ? "Los geht's" : w.step === "storage" && w.needStorage ? "Hier speichern" : "Weiter"
                        enabled: !(w.step === "storage" && moveJob.active)
                        onClicked: w.step === "storage" ? w.storeAndGo() : w.go(w.i + 1)
                    }
                }
            }
        }
    }
    onClosed: leaveStep()
}
