import QtQuick
import QtQuick.Layouts
import "."

// A short text (e.g. a new title) – win.prompt(title, value, fn).
Sheet {
    id: d
    property string heading
    property var onOk: null
    function ask(title, value, fn) { heading = title; field.text = value || ""; onOk = fn; open(); field.forceActiveFocus(); field.selectAll() }
    function done() { const fn = d.onOk, v = field.text.trim(); d.close(); if (fn && v) fn(v) }
    width: Math.min(parent ? parent.width - 48 : 480, 480)
    contentItem: ColumnLayout {
        spacing: 14
        Text { text: d.heading; font.family: Theme.display; font.pixelSize: 24; font.weight: Font.Black; color: Theme.fg }
        Input { id: field; Layout.fillWidth: true; big: true; onAccepted: d.done() }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: "OK"; enabled: field.text.trim() !== ""; onClicked: d.done() }
        }
    }
}
