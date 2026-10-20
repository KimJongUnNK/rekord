import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import QtCore
import "."

// The topics as a map: the AI builds it, REKORD draws it; save as SVG or PNG.
Item {
    id: v
    required property var page
    property bool busy: false
    readonly property var mm: page.rec ? page.rec.summaries.find(s => s.template_id === "mindmap") : null
    readonly property var layout: mm ? rekord.mindmap(mm.content) : ({ nodes: [], edges: [], width: 0, height: 0 })

    function create() {
        busy = true
        page.app.stream("/api/recordings/" + page.rid + "/summaries", { template_id: "mindmap" }, null,
                        () => { v.busy = false; v.page.reload() },
                        (err) => { v.busy = false; v.page.app.toast("Mind Map: " + err) })
    }

    FileDialog {
        id: saveDlg
        property string kind: "svg"
        fileMode: FileDialog.SaveFile
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        nameFilters: kind === "svg" ? ["SVG (*.svg)"] : ["PNG (*.png)"]
        defaultSuffix: kind
        onAccepted: {
            if (kind === "svg") {
                if (rekord.saveMindmapSvg(v.mm.content, selectedFile.toString(), Theme.fg, Theme.fg2, Theme.card)) v.page.app.toast("Gespeichert")
            } else {
                const path = rekord.localPath(selectedFile.toString())
                canvasArea.grabToImage(r => { v.page.app.toast(r.saveToFile(path) ? "Gespeichert" : "Speichern fehlgeschlagen") }, Qt.size(canvasArea.width * 2, canvasArea.height * 2))
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        RowLayout {
            spacing: 8
            Btn {
                kind: v.mm ? "default" : "primary"
                text: v.busy ? "Entsteht …" : v.mm ? "Neu erstellen" : "Mind Map erstellen"
                iconName: "spark"
                enabled: !v.busy && v.page.rec && v.page.rec.segments.length > 0
                onClicked: v.create()
            }
            Btn { visible: !!v.mm; text: "SVG speichern"; onClicked: { saveDlg.kind = "svg"; saveDlg.selectedFile = saveDlg.currentFolder + "/" + rekord.safeName(v.page.rec.title + " – Mind Map") + ".svg"; saveDlg.open() } }
            Btn { visible: !!v.mm; text: "PNG speichern"; onClicked: { saveDlg.kind = "png"; saveDlg.selectedFile = saveDlg.currentFolder + "/" + rekord.safeName(v.page.rec.title + " – Mind Map") + ".png"; saveDlg.open() } }
            BusyIndicator { running: v.busy; visible: v.busy; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
        }
        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            Flickable {
                id: fl
                anchors.fill: parent
                anchors.margins: 1
                contentWidth: Math.max(width, canvasArea.width)
                contentHeight: Math.max(height, canvasArea.height)
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                ScrollBar.horizontal: ScrollBar {}
                Rectangle {
                    id: canvasArea
                    width: v.layout.width
                    height: v.layout.height
                    color: Theme.card
                    Canvas {
                        id: edges
                        anchors.fill: parent
                        property var edgeData: v.layout.edges
                        onEdgeDataChanged: requestPaint()
                        Connections { target: Theme; function onDarkChanged() { edges.requestPaint() } }
                        onPaint: {
                            const c = getContext("2d")
                            c.reset()
                            for (const e of edgeData) {
                                const mx = (e.x1 + e.x2) / 2
                                c.beginPath()
                                c.moveTo(e.x1, e.y1)
                                c.bezierCurveTo(mx, e.y1, mx, e.y2, e.x2, e.y2)
                                c.strokeStyle = e.color || Theme.fg3
                                c.globalAlpha = 0.75
                                c.lineWidth = e.width
                                c.stroke()
                            }
                        }
                    }
                    Repeater {
                        model: v.layout.nodes
                        delegate: Item {
                            required property var modelData
                            x: modelData.x
                            y: modelData.y
                            Rectangle {  // the center
                                visible: modelData.depth === 0
                                x: -10; y: -20; width: 214; height: 40; radius: 20
                                color: Theme.fg
                                Text {
                                    anchors.centerIn: parent
                                    width: parent.width - 20
                                    horizontalAlignment: Text.AlignHCenter
                                    elide: Text.ElideRight
                                    text: modelData.text
                                    font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Black
                                    color: Theme.bg
                                }
                            }
                            Rectangle {
                                visible: modelData.depth > 0
                                x: -2 - width / 2; y: -height / 2
                                width: modelData.depth === 1 ? 10 : 7; height: width; radius: width / 2
                                color: modelData.color
                            }
                            Text {
                                visible: modelData.depth > 0
                                x: 8
                                y: -height / 2
                                text: modelData.text
                                font.family: Theme.text
                                font.pixelSize: modelData.depth === 1 ? 14 : 13
                                font.weight: modelData.depth === 1 ? Font.Black : Font.Medium
                                color: modelData.depth === 1 ? Theme.fg : Theme.fg2
                            }
                        }
                    }
                }
            }
            Muted {
                visible: !v.mm
                anchors.centerIn: parent
                text: v.busy ? "Mind Map entsteht …" : "Die KI baut aus dem Gespräch eine Mind Map."
            }
        }
    }
}
