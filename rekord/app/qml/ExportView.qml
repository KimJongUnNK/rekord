import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import QtCore
import "."

// Save as a file or copy: Markdown, Word, text, subtitles, JSON, PDF, the original audio.
Item {
    id: v
    required property var page
    readonly property var formats: [
        { k: "md", n: "Markdown", d: "Zusammenfassungen + Transkript – für Notion, Obsidian", ext: "md" },
        { k: "docx", n: "Word", d: "Zum Weiterschicken", ext: "docx" },
        { k: "pdf", n: "PDF", d: "Zum Drucken oder Archivieren", ext: "pdf" },
        { k: "txt", n: "Text", d: "Transkript pur", ext: "txt" },
        { k: "srt", n: "SRT", d: "Untertitel mit Sprechern", ext: "srt" },
        { k: "vtt", n: "WebVTT", d: "Untertitel fürs Web", ext: "vtt" },
        { k: "json", n: "JSON", d: "Alle Daten, maschinenlesbar", ext: "json" },
        { k: "audio", n: "Audio", d: "Originalaufnahme", ext: "" },
        { k: "clip", n: "In Zwischenablage", d: "Markdown kopieren", ext: "" }
    ]
    function exportAs(f) {
        if (f.k === "clip") { api.copyText(api.exportText(page.rid)); page.app.toast("Kopiert"); return }
        const ext = f.k === "audio" ? (page.rec.audio_path || "").split(".").pop() : f.ext
        dlg.fmt = f.k
        dlg.nameFilters = [f.n + " (*." + ext + ")"]
        dlg.defaultSuffix = ext
        dlg.selectedFile = dlg.currentFolder + "/" + rekord.safeName(page.rec.title) + "." + ext
        dlg.open()
    }
    FileDialog {
        id: dlg
        property string fmt
        fileMode: FileDialog.SaveFile
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        onAccepted: api.saveExport(v.page.rid, fmt, selectedFile.toString())
    }
    Flow {
        anchors.fill: parent
        spacing: 12
        Repeater {
            model: v.formats
            delegate: AbstractButton {
                id: c
                required property var modelData
                width: 230; height: 92
                hoverEnabled: true
                onClicked: v.exportAs(modelData)
                scale: down ? 0.97 : 1
                Behavior on scale { NumberAnimation { duration: 90 } }
                background: Rectangle {
                    radius: Theme.radius
                    color: c.hovered ? Theme.card2 : Theme.card
                    border.width: 1
                    border.color: c.hovered ? Theme.line2 : Theme.line
                }
                contentItem: ColumnLayout {
                    spacing: 4
                    Text { Layout.leftMargin: 16; Layout.topMargin: 14; text: c.modelData.n; font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Black; color: Theme.fg }
                    Text { Layout.leftMargin: 16; Layout.rightMargin: 12; Layout.fillWidth: true; text: c.modelData.d; wrapMode: Text.WordWrap; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg2 }
                    Item { Layout.fillHeight: true }
                }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }
        }
    }
}
