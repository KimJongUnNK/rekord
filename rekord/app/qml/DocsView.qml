import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "."

// Unterlagen of a recording – agenda, slides, documents, photos of the whiteboard. REKORD reads them on this computer
// and writes names and terms from them right in the transcript; every correction is listed and can be switched off.
Item {
    id: v
    objectName: "docsView"
    required property var page
    readonly property var docs: page.rec ? (page.rec.documents || []) : []
    readonly property var fixes: page.rec ? (page.rec.context_fixes || []) : []
    readonly property var activeFixes: fixes.filter(f => !f.off)
    readonly property int fixCount: activeFixes.reduce((a, f) => a + (f.count || 0), 0)
    property bool working: false   // the transcript is being matched against the documents

    function add() { dlg.open() }
    function kindLabel(d) {
        return ({ pdf: "PDF", "text-doc": "Dokument", slides: "Folien", sheet: "Tabelle", image: "Bild", text: "Text" })[d.kind] || "Datei"
    }
    function meta(d) {
        const parts = [kindLabel(d)]
        if (d.pages) parts.push(d.pages + (d.kind === "slides" ? " Folien" : " Seiten"))
        if (d.words) parts.push(d.words.toLocaleString(Qt.locale("de_AT"), "f", 0) + " Wörter")
        if (d.via) parts.push("gelesen von " + d.via)
        return parts.join(" · ")
    }
    function toggle(f) {
        page.app.call("POST", "/api/recordings/" + page.rid + "/fixes", { from: f.from, to: f.to, on: !!f.off }, () => page.reload())
    }

    Connections {
        target: api
        function onEvent(ev) {
            if (ev.id !== v.page.rid) return
            if (ev.type === "context_started") v.working = true
            else if (ev.type === "context_done") {
                v.working = false
                if (ev.error) v.page.app.toast("Abgleich mit den Unterlagen: " + ev.error)
                else v.page.app.toast(ev.fixes ? ev.fixes + (ev.fixes === 1 ? " Begriff" : " Begriffe") + " aus den Unterlagen korrigiert"
                                               : "Abgeglichen – nichts zu korrigieren")
            } else if (ev.type === "documents") v.page.reload()
        }
    }

    FileDialog {
        id: dlg
        title: "Unterlagen zu dieser Aufnahme"
        fileMode: FileDialog.OpenFiles
        currentFolder: library.downloadsUrl
        nameFilters: [library.docFilter, "Alle Dateien (*)"]
        onAccepted: library.attachDocs(v.page.rid, selectedFiles)
    }

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        ColumnLayout {
            width: parent.width
            spacing: 14

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Muted {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Agenda, Folien, Verträge, Fotos vom Whiteboard: REKORD liest sie und schreibt Namen und Fachbegriffe daraus im Transkript richtig. "
                          + "Zusammenfassung und Fragen kennen den Hintergrund. Alles bleibt auf diesem Rechner."
                }
                Btn { objectName: "docsAdd"; small: true; kind: "primary"; iconName: "plus"; text: "Unterlagen hinzufügen"; onClicked: v.add() }
            }

            // ---- nothing yet: one big target
            AbstractButton {
                id: empty
                visible: v.docs.length === 0
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                hoverEnabled: true
                onClicked: v.add()
                background: Rectangle {
                    radius: Theme.radius
                    color: empty.hovered ? Theme.card2 : Theme.card
                    border.width: 2
                    border.color: empty.hovered ? Theme.accent : Theme.line2
                }
                contentItem: ColumnLayout {
                    spacing: 8
                    Item { Layout.fillHeight: true }
                    Icon { Layout.alignment: Qt.AlignHCenter; name: "import"; width: 30; height: 30; color: Theme.accent; stroke: 1.8 }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "PDF, Word, PowerPoint, Excel, Text oder Fotos hierher ziehen"
                        font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; color: Theme.fg
                    }
                    Muted { Layout.alignment: Qt.AlignHCenter; font.pixelSize: 13; text: "oder klicken – auch mehrere auf einmal" }
                    Item { Layout.fillHeight: true }
                }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
            }

            // ---- the documents
            Repeater {
                model: v.docs
                delegate: Card {
                    id: dc
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: dRow.implicitHeight + 24
                    border.color: modelData.note ? Theme.warn : Theme.line
                    RowLayout {
                        id: dRow
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12
                        Rectangle {
                            Layout.preferredWidth: 42; Layout.preferredHeight: 42; radius: 10
                            color: Theme.accentSoft
                            Text {
                                anchors.centerIn: parent
                                text: dc.modelData.kind === "image" ? "BILD" : (dc.modelData.name.split(".").pop() || "").toUpperCase().slice(0, 4)
                                font.family: Theme.text; font.pixelSize: 11; font.weight: Font.Black; color: Theme.accent
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: dc.modelData.name
                                elide: Text.ElideMiddle
                                font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg
                            }
                            Text { text: v.meta(dc.modelData); font.family: Theme.text; font.pixelSize: 12; color: Theme.fg3 }
                            Text {
                                visible: !!dc.modelData.note
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                text: dc.modelData.note || ""
                                font.family: Theme.text; font.pixelSize: 12; color: Theme.warn
                            }
                        }
                        Btn { small: true; kind: "ghost"; iconName: "external"; text: "Öffnen"; onClicked: Qt.openUrlExternally(dc.modelData.file) }
                        Btn {
                            small: true; kind: "ghost"; iconName: "trash"
                            ToolTip.visible: hovered; ToolTip.delay: 400; ToolTip.text: "Entfernen – Korrekturen, die nur aus diesem Dokument kamen, gehen mit"
                            onClicked: v.page.app.call("DELETE", "/api/recordings/" + v.page.rid + "/documents/" + encodeURIComponent(dc.modelData.name), null,
                                                       () => { v.page.app.toast("Entfernt"); v.page.reload() })
                        }
                    }
                }
            }

            // ---- what changed in the transcript
            RowLayout {
                visible: v.docs.length > 0
                Layout.fillWidth: true
                Layout.topMargin: 8
                spacing: 10
                Eyebrow { text: v.fixCount ? "Im Transkript korrigiert · " + v.fixCount : "Im Transkript korrigiert" }
                BusyIndicator { visible: v.working || v.page.busy; running: visible; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                Muted { visible: v.working; font.pixelSize: 12; text: "gleicht ab …" }
                Item { Layout.fillWidth: true }
                Btn {
                    small: true; kind: "ghost"; iconName: "refresh"; text: "Neu abgleichen"
                    enabled: !!v.page.rec && v.page.rec.status === "done" && !v.working
                    onClicked: v.page.app.call("POST", "/api/recordings/" + v.page.rid + "/fixes/rerun", null, () => { v.working = true })
                }
                Btn {
                    visible: v.activeFixes.length > 0
                    small: true; kind: "ghost"; text: "Alle rückgängig"
                    onClicked: v.page.app.call("POST", "/api/recordings/" + v.page.rid + "/fixes/undo", null, () => { v.page.app.toast("Transkript wie erkannt"); v.page.reload() })
                }
            }
            Muted {
                visible: v.docs.length > 0 && v.fixes.length === 0 && !v.working
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 13
                text: v.page.busy ? "Sobald die Auswertung fertig ist, gleicht REKORD das Transkript mit den Unterlagen ab."
                                  : "Nichts zu korrigieren – die Namen und Begriffe aus den Unterlagen stehen schon richtig im Transkript."
            }
            Flow {
                visible: v.fixes.length > 0
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: v.fixes
                    delegate: AbstractButton {
                        id: fx
                        required property var modelData
                        hoverEnabled: true
                        implicitHeight: 32
                        implicitWidth: fxRow.implicitWidth + 24
                        onClicked: v.toggle(modelData)
                        ToolTip.visible: hovered
                        ToolTip.delay: 400
                        ToolTip.text: modelData.off ? "Aus – klicken, um wieder zu korrigieren"
                                                    : "Klicken, um diese Korrektur zurückzunehmen (" + (modelData.by === "KI" ? "gefunden von der lokalen KI" : "gefunden am Klang und an der Schreibweise") + ")"
                        background: Rectangle {
                            radius: 16
                            color: fx.modelData.off ? "transparent" : fx.hovered ? Theme.card2 : Theme.card
                            border.width: 1
                            border.color: fx.modelData.off ? Theme.line : Theme.line2
                        }
                        contentItem: Item {
                            RowLayout {
                                id: fxRow
                                anchors.centerIn: parent
                                spacing: 6
                                Text { text: fx.modelData.from; font.family: Theme.text; font.pixelSize: 13; font.strikeout: !fx.modelData.off; color: Theme.fg3 }
                                Text { text: "→"; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg3 }
                                Text { text: fx.modelData.to; font.family: Theme.text; font.pixelSize: 13; font.weight: Font.Bold; font.strikeout: !!fx.modelData.off; color: fx.modelData.off ? Theme.fg3 : Theme.fg }
                                Text { visible: !fx.modelData.off && fx.modelData.count > 1; text: "×" + fx.modelData.count; font.family: Theme.text; font.pixelSize: 12; color: Theme.accent; font.weight: Font.Bold }
                                Text { visible: fx.modelData.by === "KI"; text: "KI"; font.family: Theme.text; font.pixelSize: 10; font.weight: Font.Black; color: Theme.accent }
                            }
                        }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                    }
                }
            }
            Muted {
                visible: !!(v.page.rec && v.page.rec.context_note)
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                text: v.page.rec ? (v.page.rec.context_note || "") : ""
            }
            Item { Layout.preferredHeight: 12 }
        }
    }
}
