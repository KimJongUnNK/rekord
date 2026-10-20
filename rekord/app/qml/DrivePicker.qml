import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "."

// Where should REKORD keep its data (or its models)? Drives as big buttons, the folder below.
Sheet {
    id: d
    required property var app
    property string what: "home"   // home | models
    property string heading: ""
    property var info: null
    property int picked: -1
    property var onOk: null
    readonly property var kindIcon: ({ internal: "💻", external: "🔌", nvme: "⚡", network: "🌐", removable: "💾" })
    function ask(kind, title, fn) {
        what = kind; heading = title; onOk = fn; picked = -1; info = null
        app.call("GET", "/api/storage", null, (s) => {
            d.info = s
            path.text = kind === "models" ? s.models : s.home
        })
        open()
    }
    function gb(n) { return (n || 0).toLocaleString(Qt.locale("de_AT"), "f", 1) + " GB" }
    FolderDialog {
        id: folderDlg
        onAccepted: path.text = rekord.localPath(selectedFolder.toString())
    }
    width: Math.min(parent ? parent.width - 48 : 640, 640)
    contentItem: ColumnLayout {
        spacing: 12
        RowLayout {
            Text { text: d.heading; font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; color: Theme.fg }
            Tip { key: d.what === "models" ? "modelsdir" : "storage" }
        }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: d.info && d.info.drives ? d.info.drives : []
                delegate: AbstractButton {
                    id: dv
                    required property var modelData
                    required property int index
                    width: 280; height: 56
                    hoverEnabled: true
                    onClicked: {
                        d.picked = index
                        const sug = d.info.suggest[modelData.path] || { home: d.info.home, models: d.info.models }
                        path.text = d.what === "models" ? sug.models : sug.home
                    }
                    background: Rectangle {
                        radius: 12
                        color: d.picked === dv.index ? Theme.accentSoft : dv.hovered ? Theme.card2 : Theme.card
                        border.width: d.picked === dv.index ? 2 : 1
                        border.color: d.picked === dv.index ? Theme.accent : Theme.line
                    }
                    contentItem: RowLayout {
                        spacing: 10
                        Text { Layout.leftMargin: 12; text: d.kindIcon[dv.modelData.kind] || "💽"; font.pixelSize: 22 }
                        ColumnLayout {
                            spacing: 0
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: dv.modelData.name; elide: Text.ElideRight; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
                            Text { text: dv.modelData.kind_label + " · " + d.gb(dv.modelData.free_gb) + " frei" + (dv.modelData.writable ? "" : " · schreibgeschützt"); font.family: Theme.text; font.pixelSize: 12; color: Theme.fg3 }
                        }
                    }
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                }
            }
        }
        Muted { text: "Ordner" }
        RowLayout {
            Layout.fillWidth: true
            Input { id: path; Layout.fillWidth: true }
            Btn { small: true; text: "Auswählen …"; onClicked: folderDlg.open() }
        }
        Check { id: oll; visible: d.what === "models"; checked: true; text: "Lokale KI-Modelle (Ollama) mitnehmen" }
        Muted {
            Layout.fillWidth: true
            font.pixelSize: 12
            text: !d.info || !d.info.usage ? "" : d.what === "models"
                  ? "Belegt gerade " + d.gb(d.info.usage.models_gb + (d.info.models_custom ? 0 : d.info.usage.ollama_gb)) + "."
                  : "Belegt gerade " + d.gb(d.info.usage.data_gb) + ". Danach startet REKORD kurz neu; der alte Ordner bleibt als Sicherheitskopie."
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn {
                kind: "primary"; text: "Umziehen"
                enabled: path.text.trim() !== "" && d.info && path.text.trim() !== (d.what === "models" ? d.info.models : d.info.home)
                onClicked: { const fn = d.onOk, t = path.text.trim(), withOll = oll.checked; d.close(); if (fn) fn(t, withOll) }
            }
        }
    }
}
