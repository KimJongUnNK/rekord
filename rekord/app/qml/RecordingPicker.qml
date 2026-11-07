import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Other recordings behind this one – picked from a list like Unterlagen, several at once (lecture parts 2 and 3 …).
Sheet {
    id: d
    objectName: "recordingPicker"
    property var page
    property var items: []
    property var picked: ({})
    readonly property int count: Object.keys(picked).length
    property string query: ""

    function show() {
        picked = {}
        query = ""
        items = []
        open()
        page.app.call("GET", "/api/recordings", null, (r) => {
            items = (r.items || []).filter(x => x.id !== page.rid && x.status === "done" && x.duration > 0)
        })
    }
    function toggle(id) {
        const m = Object.assign({}, picked)
        if (m[id]) delete m[id]
        else m[id] = true
        picked = m
    }
    function pick(ids) { const m = {}; for (const i of ids) m[i] = true; picked = m }  // for the UI check
    function confirm() {
        const ids = Object.keys(picked)
        if (!ids.length) return
        close()
        page.app.call("POST", "/api/recordings/" + page.rid + "/append-recordings", { ids: ids }, (r) => {
            page.app.toast((ids.length === 1 ? "1 Aufnahme" : ids.length + " Aufnahmen") + " angehängt – alles wird jetzt zusammen transkribiert.")
            page.reload()
            library.refresh()
        }, (err) => page.app.toast(err))
    }
    readonly property var shown: items.filter(x => !query || x.title.toLowerCase().indexOf(query.toLowerCase()) >= 0)

    contentItem: ColumnLayout {
        spacing: 12
        Title { text: "Aufnahmen anhängen"; Layout.fillWidth: true }
        Muted {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Mehrere antippen – sie kommen hinter diese Aufnahme, die älteste zuerst. Danach wird alles zusammen transkribiert, Sprecher über alle Teile. Die angehängten Aufnahmen bleiben in der Liste."
        }
        Input { Layout.fillWidth: true; placeholderText: "Suchen"; onTextChanged: d.query = text }
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(380, Math.max(60, list.contentHeight))
            clip: true
            ListView {
                id: list
                objectName: "pickerList"
                model: d.shown
                spacing: 4
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    width: ListView.view.width
                    height: 52
                    radius: 10
                    color: d.picked[modelData.id] ? Theme.accentSoft : (ma.containsMouse ? Theme.card2 : "transparent")
                    border.width: d.picked[modelData.id] ? 1 : 0
                    border.color: Theme.accentLine
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 12
                        Check { checked: !!d.picked[row.modelData.id]; onClicked: d.toggle(row.modelData.id) }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text { text: row.modelData.title; color: Theme.fg; font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; elide: Text.ElideRight; Layout.fillWidth: true }
                            Muted {
                                font.pixelSize: 12
                                text: new Date(row.modelData.created_at * 1000).toLocaleString(Qt.locale("de_AT"), "dd.MM.yyyy HH:mm")
                                      + " · " + Math.max(1, Math.round(row.modelData.duration / 60)) + " min"
                            }
                        }
                    }
                    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; z: -1; cursorShape: Qt.PointingHandCursor; onClicked: d.toggle(row.modelData.id) }
                }
            }
        }
        Muted { visible: d.shown.length === 0; text: d.items.length ? "Nichts gefunden." : "Keine anderen fertigen Aufnahmen." }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn {
                objectName: "pickerOk"
                kind: "primary"
                enabled: d.count > 0
                text: d.count > 1 ? d.count + " anhängen" : "Anhängen"
                onClicked: d.confirm()
            }
        }
    }
}
