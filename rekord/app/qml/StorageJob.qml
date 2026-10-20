import QtQuick
import QtQuick.Layouts
import "."

// A running move of the data or the models: progress, then done (the data folder ends with a restart).
ColumnLayout {
    id: j
    required property var app
    property bool active: false
    property string text_: ""
    property real value: 0
    property bool failed: false
    signal finished()
    visible: active || failed
    spacing: 4
    function poll() {
        app.call("GET", "/api/storage", null, (s) => {
            const job = s.job
            j.failed = job.state === "error"
            if (job.state === "error") { j.active = false; j.text_ = "✗ " + job.error; return }
            if (job.state === "done" && !job.restart) { j.active = false; j.app.toast("Umgezogen ✓"); j.finished(); return }
            j.value = job.restart ? 1 : (job.total ? job.done / job.total : 0)
            j.text_ = job.restart ? "Fertig – REKORD startet am neuen Ort neu …" : job.what + " werden verschoben … " + Math.round(j.value * 100) + " %"
        }, () => { j.text_ = "REKORD startet am neuen Ort neu …" })
    }
    Timer { running: j.active; repeat: true; interval: 800; triggeredOnStart: true; onTriggered: j.poll() }
    Text { text: j.text_; font.family: Theme.text; font.pixelSize: 13; color: j.failed ? Theme.err : Theme.fg2; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Bar { visible: j.active; Layout.fillWidth: true; value: j.value }
}
