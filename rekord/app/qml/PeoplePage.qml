import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Personen: the voices REKORD knows – learn new ones, rename, recolor, forget.
Page {
    id: page
    required property var app
    onShownChanged: if (shown) people.refresh()

    PersonDialog { id: personDlg; app: page.app }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        anchors.bottomMargin: 0
        spacing: 18
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 2
                RowLayout {
                    Eyebrow { text: "Stimmabdrücke · bleiben auf diesem Gerät" }
                    Tip { key: "people" }
                }
                Title { text: "Personen" }
            }
            Item { Layout.fillWidth: true }
            Btn { kind: "primary"; iconName: "mic"; text: "Person einsprechen"; onClicked: page.app.enroll({}, null) }
        }
        Muted {
            Layout.fillWidth: true
            Layout.maximumWidth: 760
            text: "REKORD erkennt Menschen an ihrer Stimme – live im Meeting und in jeder Aufnahme. Neue Person: hier einsprechen, im Live-Modus auf die unbekannte Stimme tippen oder in einer Aufnahme bei „Wer ist das?“ benennen."
        }
        GridView {
            id: grid
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: people.items
            readonly property int cols: Math.max(1, Math.floor(width / 320))
            cellWidth: width / cols
            cellHeight: 96
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: Item {
                id: cell
                required property var modelData
                width: grid.cellWidth
                height: grid.cellHeight
                Card {
                    anchors.fill: parent
                    anchors.rightMargin: 12
                    anchors.bottomMargin: 12
                    color: pHover.hovered ? Theme.card2 : Theme.card
                    HoverHandler { id: pHover }
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 12
                        Rectangle {
                            width: 48; height: 48; radius: 24; color: cell.modelData.color
                            Text { anchors.centerIn: parent; text: cell.modelData.name.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase(); color: "#FFFFFF"; font.pixelSize: 17; font.weight: Font.Black }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text { Layout.fillWidth: true; text: cell.modelData.name; elide: Text.ElideRight; font.family: Theme.display; font.pixelSize: 18; font.weight: Font.Black; color: Theme.fg }
                            Text { text: cell.modelData.recordings + " Aufnahme(n) · " + cell.modelData.samples + " Stimmproben"; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg3 }
                        }
                        Btn { kind: "ghost"; small: true; iconName: "edit"; onClicked: personDlg.edit(cell.modelData); ToolTip.visible: hovered; ToolTip.text: "Name, Farbe oder Stimmabdruck löschen" }
                    }
                }
            }
            ColumnLayout {
                visible: grid.count === 0
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 460)
                spacing: 12
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 84; height: 84; radius: 42
                    color: Theme.accentSoft
                    Icon { anchors.centerIn: parent; width: 36; height: 36; name: "people"; color: Theme.accent }
                }
                Text { Layout.alignment: Qt.AlignHCenter; text: "Noch niemand angelernt"; font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; color: Theme.fg }
                Muted { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: "Einmal ca. 45 Sekunden einsprechen – dann steht der Name in jedem Meeting." }
                Btn { Layout.alignment: Qt.AlignHCenter; kind: "primary"; iconName: "mic"; text: "Person einsprechen"; onClicked: page.app.enroll({}, null) }
            }
        }
    }
}
