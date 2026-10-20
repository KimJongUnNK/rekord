import QtQuick
import QtQuick.Layouts
import "."

// Edit a longer text (a summary as Markdown, a template prompt …).
Sheet {
    id: d
    property string heading
    property var onOk: null
    property bool mono: true
    function edit(title, text, fn) { heading = title; area.text = text; onOk = fn; open() }
    width: Math.min(parent ? parent.width - 48 : 860, 860)
    contentItem: ColumnLayout {
        spacing: 12
        Text { text: d.heading; font.family: Theme.display; font.pixelSize: 24; font.weight: Font.Black; color: Theme.fg; Layout.fillWidth: true; elide: Text.ElideRight }
        Area { id: area; mono: d.mono; Layout.fillWidth: true; Layout.preferredHeight: Math.min(560, (d.parent ? d.parent.height : 700) - 220) }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: "Speichern"; onClicked: { const fn = d.onOk; const t = area.text; d.close(); if (fn) fn(t) } }
        }
    }
}
