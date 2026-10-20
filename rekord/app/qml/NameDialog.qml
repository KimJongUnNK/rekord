import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// "Wer ist das?" – name a voice while recording; REKORD remembers it from then on.
Sheet {
    id: dlg
    property int key: -1
    property string current: ""
    function ask(k, label) { key = k; current = label; field.text = ""; open(); field.forceActiveFocus() }
    function save(name) {
        if (!name.trim()) return
        live.nameSpeaker(dlg.key, name.trim())
        close()
        refreshLater.start()
    }
    Timer { id: refreshLater; interval: 1500; onTriggered: people.refresh() }

    contentItem: ColumnLayout {
        spacing: 16
        Text { text: "STIMME BENENNEN"; font.family: Theme.text; font.pixelSize: 12; font.weight: Font.Black; font.letterSpacing: 1.2; color: Theme.accent }
        Text {
            Layout.fillWidth: true
            text: "Wer ist das?"
            font.family: Theme.display; font.pixelSize: 30; font.weight: Font.Black; font.letterSpacing: -1
            color: Theme.fg
        }
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Gerade als „" + dlg.current + "“ erkannt. Gib einen Namen ein – REKORD merkt sich die Stimme und erkennt sie ab jetzt, auch in künftigen Aufnahmen."
            font.family: Theme.text; font.pixelSize: 14; color: Theme.fg2
        }
        TextField {
            id: field
            Layout.fillWidth: true
            placeholderText: "Name, z. B. Lisa"
            font.family: Theme.text
            font.pixelSize: 16
            color: Theme.fg
            placeholderTextColor: Theme.fg3
            selectionColor: Theme.accent
            selectedTextColor: Theme.onAccent
            leftPadding: 14
            topPadding: 12
            bottomPadding: 12
            background: Rectangle {
                radius: 12
                color: Theme.bg
                border.width: field.activeFocus ? 2 : 1
                border.color: field.activeFocus ? Theme.accent : Theme.line
            }
            onAccepted: dlg.save(text)
        }
        Flow {  // people REKORD knows already
            Layout.fillWidth: true
            spacing: 8
            visible: matches.length > 0
            readonly property var matches: people.items.filter(p => !field.text || p.name.toLowerCase().indexOf(field.text.toLowerCase()) >= 0).slice(0, 8)
            Repeater {
                model: parent.matches
                delegate: Chip {
                    required property var modelData
                    text: modelData.name
                    dot: modelData.color
                    onClicked: dlg.save(modelData.name)
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: dlg.close() }
            Btn { kind: "primary"; text: "Merken"; iconName: "check"; enabled: field.text.trim() !== ""; onClicked: dlg.save(field.text) }
        }
    }
}
