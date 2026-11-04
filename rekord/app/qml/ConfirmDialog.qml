import QtQuick
import QtQuick.Layouts
import "."

// "Wirklich löschen?" – one instance in Main, used through win.confirm(…).
Sheet {
    id: d
    property string heading
    property string body
    property string okLabel: "Löschen"
    property bool danger: true
    property var onOk: null
    property string altLabel: ""   // optional second choice (e.g. "Als neue Aufnahme")
    property var onAlt: null
    function ask(title, text, label, fn, isDanger, alt, altFn) {
        heading = title; body = text || ""; okLabel = label || "Löschen"; onOk = fn; danger = isDanger !== false
        altLabel = alt || ""; onAlt = altFn || null
        open()
    }
    width: Math.min(parent ? parent.width - 48 : 480, 480)
    contentItem: ColumnLayout {
        spacing: 14
        Text {
            Layout.fillWidth: true
            text: d.heading
            wrapMode: Text.WordWrap
            font.family: Theme.display; font.pixelSize: 24; font.weight: Font.Black; font.letterSpacing: -0.6
            color: Theme.fg
        }
        Muted { Layout.fillWidth: true; visible: d.body !== ""; text: d.body }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { visible: d.altLabel !== ""; text: d.altLabel; onClicked: { const fn = d.onAlt; d.close(); if (fn) fn() } }
            Btn {
                kind: d.danger ? "danger" : "primary"
                text: d.okLabel
                onClicked: { const fn = d.onOk; d.close(); if (fn) fn() }
            }
        }
    }
}
