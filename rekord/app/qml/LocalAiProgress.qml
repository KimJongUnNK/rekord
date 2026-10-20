import QtQuick
import QtQuick.Layouts
import "."

// "Lokal einrichten": install Ollama → start → download the model → ready. Polls while it runs.
ColumnLayout {
    id: p
    required property var app
    property bool active: false
    property string state_: ""
    property string step: ""
    property real value: 0
    property string extra: ""
    property string error: ""
    signal done(string model)
    spacing: 6
    function gb(n) { return (n || 0).toLocaleString(Qt.locale("de_AT"), "f", 1) + " GB" }
    function poll() {
        app.call("GET", "/api/ollama", null, (o) => {
            const su = o.setup, pr = su.model ? (o.pulls[su.model] || {}) : {}
            p.state_ = su.state; p.step = su.step || "…"; p.error = su.error || ""
            p.value = su.state === "installing" && su.total ? su.done / su.total : su.state === "pulling" && pr.total ? pr.done / pr.total : 0
            p.extra = su.state === "installing" && su.total ? " · " + gb(su.done / 1e9) + " von " + gb(su.total / 1e9)
                    : su.state === "pulling" && pr.total ? " · " + gb(pr.done / 1e9) + " von " + gb(pr.total / 1e9) : ""
            if (su.state === "done") { p.active = false; p.app.toast("Lokale KI ist bereit."); p.done(su.model || "") }
            else if (su.state === "error") p.active = false
        }, () => {})
    }
    Timer { running: p.active; repeat: true; interval: 1000; triggeredOnStart: true; onTriggered: p.poll() }
    visible: active || state_ === "error" || state_ === "done"
    Text {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: p.state_ === "error" ? "✗ " + p.error : p.state_ === "done" ? "✓ Lokale KI bereit" : p.step + p.extra
        font.family: Theme.text; font.pixelSize: 13
        color: p.state_ === "error" ? Theme.err : p.state_ === "done" ? Theme.ok : Theme.fg2
    }
    Bar { visible: p.active; Layout.fillWidth: true; value: p.value }
    Muted { visible: p.active; font.pixelSize: 12; text: "Läuft im Hintergrund weiter – du kannst REKORD schon benutzen." }
}
