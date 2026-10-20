import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Lokal (Ollama): install, start, the best model for this computer, load/use/delete models – no terminal.
ColumnLayout {
    id: o
    required property var app
    property string model: ""     // the model in use
    signal modelChosen(string name)
    property var st: null
    readonly property bool settingUp: st && ["installing", "starting", "pulling"].indexOf(st.setup.state) >= 0
    readonly property var installedNames: st ? st.models.map(m => m.name) : []
    readonly property var pulling: st ? Object.keys(st.pulls).filter(k => st.pulls[k].state === "downloading") : []
    spacing: 12
    function gb(n) { return (n || 0).toLocaleString(Qt.locale("de_AT"), "f", 1) + " GB" }
    function has(n) { return installedNames.indexOf(n) >= 0 || installedNames.indexOf(n + ":latest") >= 0 }
    function pct(pr) { return pr && pr.total ? Math.round(pr.done / pr.total * 100) : 0 }
    function load() { app.call("GET", "/api/ollama", null, (r) => o.st = r, (e) => o.st = null) }
    function settings() { app.call("GET", "/api/settings", null, (s) => { if (s.llm.ollama.model !== o.model) o.modelChosen(s.llm.ollama.model || "") }, () => {}) }
    function pull(name) {
        app.call("POST", "/api/ollama/pull", { model: name, use: true }, () => { app.toast(name + " wird geladen – danach automatisch verwendet"); load() })
    }
    function remove(name) {
        app.confirm(name + " löschen?", "Das Modell wird vom Computer entfernt und der Speicher frei. Neu laden geht jederzeit.", "Löschen", () =>
            app.call("DELETE", "/api/ollama/models/" + encodeURIComponent(name), null, (r) => {
                app.toast(name + " gelöscht" + (r.model ? " · jetzt: " + r.model : "")); o.modelChosen(r.model || ""); rekord.refresh(); load()
            }))
    }
    Component.onCompleted: load()
    Timer {  // follow downloads and a starting Ollama
        running: o.visible && o.st !== null && !o.settingUp && (o.pulling.length > 0 || (o.st.installed && !o.st.running))
        interval: o.pulling.length > 0 ? 1000 : 4000
        repeat: true
        onTriggered: { o.load(); o.settings(); rekord.refresh() }
    }

    Muted { visible: o.st === null; text: "Prüfe Ollama …" }

    LocalAiProgress {
        id: prog
        Layout.fillWidth: true
        app: o.app
        active: o.settingUp
        onDone: (m) => { o.modelChosen(m); rekord.refresh(); o.load() }
    }

    // ---- not installed
    ColumnLayout {
        visible: o.st !== null && !o.st.installed && !o.settingUp
        Layout.fillWidth: true
        spacing: 8
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            textFormat: Text.StyledText
            font.family: Theme.text; font.pixelSize: 14; color: Theme.fg
            text: o.st && o.st.can_install
                  ? "Ein Klick: REKORD installiert <b>Ollama</b> (das kostenlose Programm für lokale KI) und lädt <b>" + o.st.default + "</b>, passend zu deinen " + o.gb(o.st.ram_gb) + " RAM. Dauert je nach Internet 5–15 Minuten, danach läuft alles offline."
                  : "Ollama lässt sich auf diesem Computer nicht automatisch installieren – lade es von ollama.com und starte REKORD neu."
        }
        RowLayout {
            Btn { visible: o.st && o.st.can_install; kind: "primary"; text: "Lokal einrichten"; iconName: "download"; onClicked: o.app.call("POST", "/api/ollama/setup", {}, () => { o.load(); prog.active = true }) }
            Btn { visible: o.st && !o.st.can_install; text: "ollama.com"; iconName: "open"; onClicked: api.openUrl("https://ollama.com/download") }
        }
        Text { visible: o.st && o.st.setup.state === "error"; text: "✗ " + (o.st ? o.st.setup.error : ""); color: Theme.err; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }

    // ---- installed, not running
    RowLayout {
        visible: o.st !== null && o.st.installed && !o.st.running && !o.settingUp
        Muted { text: "Ollama ist installiert, läuft aber nicht." }
        Btn {
            kind: "primary"; text: "Ollama starten"
            onClicked: { enabled = false; o.app.call("POST", "/api/ollama/start", null, (r) => { enabled = true; if (!r.ok) o.app.toast("Ollama startet nicht – Computer einmal neu starten."); o.load() }) }
        }
    }

    // ---- running
    ColumnLayout {
        visible: o.st !== null && o.st.running && !o.settingUp
        Layout.fillWidth: true
        spacing: 12
        RowLayout {
            Rectangle { width: 8; height: 8; radius: 4; color: Theme.ok }
            Muted { text: "Ollama läuft" + (o.st && o.st.version ? " · v" + o.st.version : ""); font.pixelSize: 13 }
        }
        Rectangle {  // the best model for this computer
            Layout.fillWidth: true
            Layout.preferredHeight: bestCol.implicitHeight + 28
            radius: 12
            color: Theme.card2
            readonly property var best: o.st ? (o.st.recommended.find(r => r.best) || { name: o.st.best, size_gb: 0 }) : { name: "", size_gb: 0 }
            readonly property var bestPull: o.st && o.st.pulls[best.name] ? o.st.pulls[best.name] : ({})
            id: bestBox
            ColumnLayout {
                id: bestCol
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8
                RowLayout { Eyebrow { text: "Dein Computer" } Tip { key: "bestmodel" } }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    textFormat: Text.StyledText
                    font.family: Theme.text; font.pixelSize: 14; color: Theme.fg
                    text: "<b>" + (o.st ? o.st.hardware.label : "") + "</b> → am besten: <b>" + bestBox.best.name + "</b> <font color='" + Theme.fg3 + "'>" + o.gb(bestBox.best.size_gb) + "</font>"
                }
                RowLayout {
                    visible: o.model === bestBox.best.name || o.model === bestBox.best.name + ":latest"
                    Text { text: "✓ wird verwendet"; color: Theme.accent; font.pixelSize: 13; font.weight: Font.Bold }
                }
                ColumnLayout {
                    visible: bestBox.bestPull.state === "downloading"
                    Layout.fillWidth: true
                    Muted { font.pixelSize: 13; text: "Lädt " + o.pct(bestBox.bestPull) + " % – danach wird es automatisch verwendet" }
                    Bar { Layout.fillWidth: true; value: o.pct(bestBox.bestPull) / 100 }
                }
                Btn {
                    visible: o.model !== bestBox.best.name && o.model !== bestBox.best.name + ":latest" && bestBox.bestPull.state !== "downloading"
                    kind: "primary"; small: true
                    text: o.has(bestBox.best.name) ? bestBox.best.name + " verwenden" : bestBox.best.name + " laden & verwenden"
                    onClicked: o.app.call("POST", "/api/ollama/best", null, (r) => {
                        if (!r.pulling) { o.modelChosen(r.model); o.app.toast(r.model + " wird verwendet"); rekord.refresh() }
                        else o.app.toast(r.model + " wird geladen – danach automatisch verwendet")
                        o.load()
                    })
                }
            }
        }

        RowLayout { visible: o.st && o.st.models.length > 0; Eyebrow { text: "Auf diesem Computer" } Tip { key: "ollamadelete" } }
        Repeater {
            model: o.st ? o.st.models : []
            delegate: RowLayout {
                required property var modelData
                Layout.fillWidth: true
                readonly property bool on: modelData.name === o.model
                Text { text: (on ? "● " : "") + modelData.name; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
                Muted { text: o.gb(modelData.size_gb); font.pixelSize: 13 }
                Text { visible: on; text: "wird verwendet"; color: Theme.accent; font.pixelSize: 12; font.weight: Font.Bold }
                Text { visible: modelData.fits === false; text: "zu groß für " + o.gb(o.st.ram_gb) + " RAM"; color: Theme.fg3; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                Btn {
                    visible: !on; small: true; text: "Verwenden"
                    onClicked: o.app.call("PUT", "/api/settings", { llm: { ollama: { model: modelData.name } } }, () => { o.modelChosen(modelData.name); o.app.toast(modelData.name + " wird verwendet"); rekord.refresh() })
                }
                Btn { kind: "ghost"; small: true; iconName: "trash"; text: "Löschen"; onClicked: o.remove(modelData.name) }
            }
        }
        Btn {
            readonly property var unused: o.st ? o.st.models.filter(m => m.name !== o.model) : []
            visible: unused.length > 1
            kind: "ghost"; small: true
            text: "Alle nicht verwendeten löschen · " + o.gb(unused.reduce((a, m) => a + (m.size_gb || 0), 0)) + " frei machen"
            onClicked: {
                const list = unused.map(m => m.name)
                o.app.confirm(list.length + " Modelle löschen?", list.join(", ") + " – nur " + (o.model || "–") + " bleibt.", "Löschen", () => {
                    let left = list.length
                    for (const n of list) o.app.call("DELETE", "/api/ollama/models/" + encodeURIComponent(n), null, () => { if (--left === 0) { o.app.toast(list.length + " Modelle gelöscht"); o.load() } })
                })
            }
        }
        Muted {
            visible: o.st && o.st.service
            Layout.fillWidth: true
            font.pixelSize: 12
            text: "Ollama läuft hier als Systemdienst – der Speicherort für dessen Modelle wird im Dienst festgelegt (sudo systemctl edit ollama → Environment=\"OLLAMA_MODELS=…\")."
        }

        Eyebrow { text: "Weitere Modelle" }
        Repeater {
            model: o.st ? o.st.recommended : []
            delegate: ColumnLayout {
                id: rr
                required property var modelData
                readonly property var pr: o.st.pulls[modelData.name] || ({})
                Layout.fillWidth: true
                opacity: modelData.fits ? 1 : 0.6
                spacing: 4
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: rr.modelData.name; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
                    Text { visible: rr.modelData.best; text: "am besten für diesen Computer"; color: Theme.accent; font.pixelSize: 12; font.weight: Font.Bold }
                    Muted { text: o.gb(rr.modelData.size_gb) + " · ab " + rr.modelData.ram_gb + " GB RAM"; font.pixelSize: 12 }
                    Item { Layout.fillWidth: true }
                    Text { visible: o.has(rr.modelData.name); text: "geladen"; color: Theme.fg3; font.pixelSize: 12 }
                    Text { visible: !o.has(rr.modelData.name) && rr.pr.state === "downloading"; text: o.pct(rr.pr) ? o.pct(rr.pr) + " %" : (rr.pr.status || "…"); color: Theme.fg2; font.pixelSize: 12 }
                    Btn {
                        visible: !o.has(rr.modelData.name) && rr.pr.state !== "downloading"
                        small: true
                        kind: rr.modelData.best && o.st.models.length === 0 ? "primary" : "default"
                        text: rr.modelData.fits ? "Laden & verwenden" : "Trotzdem laden"
                        onClicked: o.pull(rr.modelData.name)
                    }
                }
                Muted { Layout.fillWidth: true; font.pixelSize: 12; text: rr.modelData.note + (rr.modelData.fits ? "" : " · läuft hier nur langsam") + (rr.pr.state === "error" ? " · " + rr.pr.error : "") }
                Bar { visible: rr.pr.state === "downloading"; Layout.fillWidth: true; value: o.pct(rr.pr) / 100 }
            }
        }
        RowLayout { Eyebrow { text: "Anderes Modell" } Tip { key: "othermodel" } }
        RowLayout {
            Layout.fillWidth: true
            Input { id: other; Layout.fillWidth: true; placeholderText: "Name von ollama.com/library, z. B. llama3.1:8b" }
            Btn { small: true; text: "Laden & verwenden"; onClicked: o.otherGo() }
        }
    }
    function otherGo() {
        const name = other.text.trim()
        if (!/^[\w.\-/:]+$/.test(name)) { app.toast("Name wie auf ollama.com/library, z. B. llama3.1:8b"); return }
        pull(name); other.text = ""
    }
    Connections { target: other; function onAccepted() { o.otherGo() } }
}
