import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Vorlagen: the formats for summaries. Drag (⠿) or ↑ ↓ ⤒ – what's on top shows first when summarizing.
Page {
    id: page
    objectName: "templatesPage"
    required property var app
    property int count: 0
    onShownChanged: if (shown) load()

    function load() {
        app.call("GET", "/api/templates", null, (r) => {
            tm.clear()
            for (const t of r.items) tm.append({ tid: t.id, name: t.name, category: t.category || "", description: t.description || "",
                                                prompt: t.prompt || "", builtin: !!t.builtin })
            page.count = tm.count
        })
    }
    function openEditor(i) { editor.edit(i < 0 ? null : get(i)) }
    function get(i) { const t = tm.get(i); return { id: t.tid, name: t.name, category: t.category, description: t.description, prompt: t.prompt, builtin: t.builtin } }
    function move(from, to) {
        if (to < 0 || to >= tm.count || from === to) return
        tm.move(from, to, 1)
        saveTimer.restart()
    }
    Timer {
        id: saveTimer
        interval: 350
        onTriggered: {
            const ids = []
            for (let i = 0; i < tm.count; i++) ids.push(tm.get(i).tid)
            page.app.call("PUT", "/api/settings", { template_order: ids }, () => page.app.toast("Reihenfolge gespeichert"))
        }
    }
    ListModel { id: tm }
    TemplateDialog { id: editor; objectName: "templateDialog"; app: page.app; onSaved: page.load() }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        anchors.bottomMargin: 0
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 2
                RowLayout {
                    Eyebrow { text: page.count + " Vorlagen" }
                    Tip { key: "templates" }
                }
                Title { text: "Vorlagen" }
            }
            Item { Layout.fillWidth: true }
            Btn { kind: "primary"; iconName: "plus"; text: "Eigene Vorlage"; onClicked: editor.edit(null) }
        }
        RowLayout {
            Layout.fillWidth: true
            Muted { Layout.fillWidth: true; text: "Jede Vorlage ist ein Prompt – bau dir dein eigenes Protokoll-Format. ⠿ Ziehen oder ↑ ↓: oben steht, was dir am wichtigsten ist. In dieser Reihenfolge erscheinen sie auch beim Zusammenfassen."; wrapMode: Text.WordWrap }
            Tip { key: "tplorder" }
            Btn {
                kind: "ghost"; small: true; text: "Reihenfolge zurücksetzen"
                onClicked: page.app.call("PUT", "/api/settings", { template_order: [] }, () => { page.app.toast("Ursprüngliche Reihenfolge"); page.load() })
            }
        }

        ListView {
            id: list
            objectName: "templateList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 10
            model: tm
            bottomMargin: 36
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            moveDisplaced: Transition { NumberAnimation { properties: "y"; duration: Theme.mid; easing.type: Easing.OutCubic } }
            move: Transition { NumberAnimation { properties: "y"; duration: Theme.mid; easing.type: Easing.OutCubic } }

            delegate: Item {
                id: row
                required property int index
                required property string tid
                required property string name
                required property string category
                required property string description
                required property bool builtin
                width: list.width - 14
                height: card.height

                DropArea {  // another card dragged over this one takes its place – live
                    anchors.fill: parent
                    onEntered: (drag) => { if (drag.source && drag.source.index !== row.index) tm.move(drag.source.index, row.index, 1) }
                }
                Rectangle {
                    id: card
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter
                    width: row.width
                    height: body.implicitHeight + 28
                    radius: Theme.radius
                    color: grip.drag.active ? Theme.card2 : hover.hovered ? Theme.card2 : Theme.card
                    border.width: grip.drag.active ? 2 : 1
                    border.color: grip.drag.active ? Theme.accent : Theme.line
                    Drag.active: grip.drag.active
                    Drag.source: row
                    Drag.hotSpot.x: 20
                    Drag.hotSpot.y: height / 2
                    scale: grip.drag.active ? 1.02 : 1
                    Behavior on scale { NumberAnimation { duration: Theme.fast } }
                    states: State {  // while dragging, the card floats above the list
                        when: grip.drag.active
                        ParentChange { target: card; parent: list }
                        AnchorChanges { target: card; anchors.horizontalCenter: undefined; anchors.verticalCenter: undefined }
                        PropertyChanges { target: card; z: 10 }
                    }
                    HoverHandler { id: hover }
                    TapHandler { onTapped: editor.edit(page.get(row.index)) }
                    RowLayout {
                        id: body
                        x: 8; y: 14
                        width: parent.width - 22
                        spacing: 12
                        Item {
                            Layout.preferredWidth: 26
                            Layout.preferredHeight: 40
                            Icon { anchors.centerIn: parent; name: "grip"; width: 20; height: 20; stroke: 3.2; color: grip.containsMouse || grip.drag.active ? Theme.fg : Theme.fg3 }
                            MouseArea {
                                id: grip
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                                drag.target: card
                                drag.axis: Drag.YAxis
                                property int from: -1
                                onPressed: from = row.index
                                onReleased: if (row.index !== from) saveTimer.restart()
                            }
                        }
                        Text {
                            text: row.index + 1
                            Layout.preferredWidth: 24
                            horizontalAlignment: Text.AlignRight
                            font.family: Theme.display; font.pixelSize: 18; font.weight: Font.Black; font.features: ({ "tnum": 1 })
                            color: row.index < 3 ? Theme.accent : Theme.fg3
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            RowLayout {
                                spacing: 8
                                Text { text: row.name; font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Bold; color: Theme.fg; elide: Text.ElideRight; Layout.maximumWidth: body.width - 320 }
                                Rectangle {
                                    visible: row.category !== ""
                                    Layout.preferredHeight: 22
                                    Layout.preferredWidth: catT.implicitWidth + 16
                                    radius: 11
                                    color: Theme.card2
                                    Text { id: catT; anchors.centerIn: parent; text: row.category; font.family: Theme.text; font.pixelSize: 11; font.weight: Font.Bold; color: Theme.fg2 }
                                }
                                Rectangle {
                                    visible: !row.builtin
                                    Layout.preferredHeight: 22
                                    Layout.preferredWidth: ownT.implicitWidth + 16
                                    radius: 11
                                    color: Theme.accentSoft
                                    Text { id: ownT; anchors.centerIn: parent; text: "eigene"; font.family: Theme.text; font.pixelSize: 11; font.weight: Font.Bold; color: Theme.accent }
                                }
                            }
                            Text { Layout.fillWidth: true; visible: row.description !== ""; text: row.description; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg2 }
                        }
                        Row {
                            spacing: 2
                            Btn { kind: "ghost"; small: true; iconName: "top"; enabled: row.index > 0; onClicked: page.move(row.index, 0) || list.positionViewAtBeginning(); ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "Ganz nach oben" }
                            Btn { kind: "ghost"; small: true; iconName: "up"; enabled: row.index > 0; onClicked: page.move(row.index, row.index - 1); ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "Nach oben" }
                            Btn { kind: "ghost"; small: true; iconName: "down"; enabled: row.index < tm.count - 1; onClicked: page.move(row.index, row.index + 1); ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "Nach unten" }
                        }
                    }
                }
            }
        }
    }
}
