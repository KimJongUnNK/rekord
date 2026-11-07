import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Aufnahmen: search, folders, import, open.
Page {
    id: page
    required property var app
    function focusSearch() { search.forceActiveFocus(); search.selectAll() }

    // ---- several at once: Auswählen → tick → Löschen
    property bool selecting: false
    property var picked: ({})
    readonly property int pickedCount: Object.keys(picked).length
    function togglePick(rid) {
        const m = Object.assign({}, picked)
        if (m[rid]) delete m[rid]
        else m[rid] = true
        picked = m
    }
    function pickAll() {
        const m = {}
        for (const r of library.model.rids()) m[r] = true
        picked = pickedCount === library.model.count ? {} : m
    }
    function stopSelecting() { selecting = false; picked = {} }
    function deletePicked() {
        const ids = Object.keys(picked)
        if (!ids.length) return
        app.confirm(ids.length === 1 ? "1 Aufnahme löschen?" : ids.length + " Aufnahmen löschen?",
                    "Audio, Transkript, Zusammenfassungen und Unterlagen werden endgültig entfernt. Laufende Auswertungen werden gestoppt.",
                    "Löschen", () => app.call("POST", "/api/recordings/delete", { ids: ids }, (r) => {
                        app.toast(r.deleted === 1 ? "1 Aufnahme gelöscht" : r.deleted + " Aufnahmen gelöscht")
                        page.stopSelecting()
                        library.refresh()
                    }), true)
    }
    // the bigger picture: lecture parts, a meeting on two devices → one recording, one transcript
    function mergePicked() {
        const ids = Object.keys(picked)
        if (ids.length < 2) return
        app.confirm(ids.length + " Aufnahmen zu einer zusammenführen?",
                    "Hintereinander, die älteste zuerst – dann wird alles zusammen transkribiert, Sprecher über alle Teile. "
                    + "Sterne, Notizen und Unterlagen kommen mit. Die einzelnen Aufnahmen bleiben erhalten.",
                    "Zusammenführen", () => app.call("POST", "/api/recordings/merge", { ids: ids }, (r) => {
                        app.toast("Zusammengeführt – „" + r.title + "“ wird jetzt transkribiert.")
                        page.stopSelecting()
                        library.refresh()
                        app.openRecording(r.id, 0)
                    }, (err) => app.toast(err)))
    }
    Shortcut { sequence: "Esc"; enabled: page.selecting && page.shown; onActivated: page.stopSelecting() }

    // a small window: the page scrolls, the list keeps a usable height
    Flickable {
        id: pageFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: body.height + 36
        interactive: contentHeight > height + 1
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        ScrollBar.vertical: ScrollBar { policy: pageFlick.interactive ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }

    ColumnLayout {
        id: body
        x: 36
        y: 36
        width: pageFlick.width - 72
        height: Math.max(pageFlick.height - 36, implicitHeight)
        spacing: 20

        // ---- header
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                spacing: 2
                Text {
                    text: "Aufnahmen"
                    font.family: Theme.display
                    font.pixelSize: 44
                    font.weight: Font.Black
                    font.letterSpacing: -2
                    color: Theme.fg
                }
                Text {
                    text: library.model.count === 0 ? (library.query ? "Nichts gefunden" : "Noch leer")
                        : library.model.count + (library.model.count === 1 ? " Gespräch" : " Gespräche") + (library.query ? " gefunden" : "")
                    font.family: Theme.text
                    font.pixelSize: 14
                    color: Theme.fg3
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {  // search
                Layout.preferredWidth: Math.min(340, page.width * 0.32)
                Layout.preferredHeight: 42
                radius: 12
                color: Theme.card
                border.width: search.activeFocus ? 2 : 1
                border.color: search.activeFocus ? Theme.accent : Theme.line
                Behavior on border.color { ColorAnimation { duration: Theme.fast } }
                Icon { id: sIcon; name: "search"; width: 18; height: 18; color: Theme.fg3; anchors.left: parent.left; anchors.leftMargin: 13; anchors.verticalCenter: parent.verticalCenter }
                TextField {
                    id: search
                    anchors.left: sIcon.right
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 4
                    anchors.rightMargin: 8
                    placeholderText: "Suchen – auch im Gesagten (Strg+F)"
                    placeholderTextColor: Theme.fg3
                    color: Theme.fg
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.onAccent
                    font.family: Theme.text
                    font.pixelSize: 14
                    background: null
                    onTextChanged: library.search(text)
                    Keys.onEscapePressed: { text = ""; focus = false }
                }
            }
            Btn {
                objectName: "selectButton"
                visible: list.count > 0
                kind: page.selecting ? "primary" : "ghost"
                text: page.selecting ? "Fertig" : "Auswählen"
                iconName: page.selecting ? "" : "check"
                onClicked: page.selecting ? page.stopSelecting() : page.selecting = true
                ToolTip.visible: hovered && !page.selecting
                ToolTip.delay: 500
                ToolTip.text: "Mehrere Aufnahmen auf einmal löschen"
            }
            Btn {
                text: "Datei transkribieren"
                iconName: "import"
                onClicked: page.app.importFiles()
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: "Audio- oder Videodateien (Strg+I) – oder einfach ins Fenster ziehen"
            }
        }

        // ---- first start / storage
        Rectangle {
            visible: rekord.status.welcomeDone === false || (rekord.status.ready === false && !rekord.status.downloading)
            Layout.fillWidth: true
            Layout.preferredHeight: setupRow.implicitHeight + 36
            radius: Theme.radius
            color: Theme.accentSoft
            border.width: 1
            border.color: Theme.accentLine
            RowLayout {
                id: setupRow
                anchors.fill: parent
                anchors.margins: 18
                spacing: 16
                Icon { name: "spark"; width: 26; height: 26; color: Theme.accent }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: rekord.status.welcomeDone === false ? "Einmal einrichten – dann läuft alles von selbst" : "Die Spracherkennung fehlt noch"
                        font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Bold; color: Theme.fg
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: rekord.status.welcomeDone === false ? "Speicherort wählen, Spracherkennung laden (einmalig, ~700 MB) und optional eine KI für Zusammenfassungen verbinden."
                            : rekord.status.downloading ? "Lädt " + rekord.status.downloading + " – einmalig, danach läuft alles offline."
                            : rekord.status.modelError ? "Laden fehlgeschlagen: " + rekord.status.modelError
                            : "Ohne die Sprachmodelle (" + (rekord.status.missingMb || 700) + " MB, einmalig) kann REKORD nicht mitschreiben. Ein Klick – danach offline."
                        font.family: Theme.text; font.pixelSize: 14; color: Theme.fg2
                    }
                }
                Btn {
                    objectName: "loadModelsButton"
                    kind: "primary"
                    visible: !rekord.status.downloading
                    iconName: rekord.status.welcomeDone === false ? "" : "download"
                    text: rekord.status.welcomeDone === false ? "Einrichten" : rekord.status.modelError ? "Nochmal laden" : "Jetzt laden"
                    onClicked: rekord.status.welcomeDone === false ? page.app.welcome(true) : rekord.downloadModels()
                }
                BusyIndicator { visible: !!rekord.status.downloading; running: visible; Layout.preferredWidth: 26; Layout.preferredHeight: 26 }
                Btn { visible: rekord.status.welcomeDone !== false; kind: "ghost"; text: "Modelle"; onClicked: page.app.go("settings", "models") }
            }
        }

        // ---- no AI yet: who writes the protocols? (once there's something to summarize)
        Rectangle {
            id: aiCard
            property bool hidden: !!rekord.pref("ai_card_hidden")
            visible: !hidden && rekord.status.welcomeDone === true && !rekord.status.ai && list.count > 0 && !library.query
            Layout.fillWidth: true
            Layout.preferredHeight: aiCol.implicitHeight + 36
            radius: Theme.radius
            color: Theme.card
            border.width: 1
            border.color: Theme.line
            ColumnLayout {
                id: aiCol
                x: 18; y: 18
                width: parent.width - 36
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    Icon { name: "spark"; width: 22; height: 22; color: Theme.accent }
                    Text { Layout.fillWidth: true; text: "Protokolle, To-dos, Mind Map – verbinde eine KI"; font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Bold; color: Theme.fg; elide: Text.ElideRight }
                    Tip { key: "provider" }
                    Btn { kind: "ghost"; small: true; text: "Später"; onClicked: { rekord.setPref("ai_card_hidden", true); aiCard.hidden = true } }
                }
                AiChoice { Layout.fillWidth: true; app: page.app; withNone: false; onReady: page.app.toast("KI verbunden – in jeder Aufnahme unter „Zusammenfassung“.") }
            }
        }

        // ---- folders
        Flow {
            visible: library.folders.length > 0
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: [""].concat(library.folders)
                delegate: Chip {
                    required property string modelData
                    text: modelData || "Alle"
                    dot: modelData ? Theme.fg3 : Theme.accent
                    on: library.folder === modelData
                    onClicked: library.setFolder(modelData)
                }
            }
        }

        // ---- selecting: what's ticked, delete it in one go
        Rectangle {
            objectName: "selectBar"
            visible: page.selecting
            Layout.fillWidth: true
            Layout.preferredHeight: 54
            radius: Theme.radius
            color: Theme.accentSoft
            border.width: 1
            border.color: Theme.accentLine
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 10
                spacing: 10
                Text {
                    text: page.pickedCount === 0 ? "Aufnahmen antippen, um sie auszuwählen"
                        : page.pickedCount === 1 ? "1 ausgewählt" : page.pickedCount + " ausgewählt"
                    font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Bold; color: Theme.fg
                }
                Item { Layout.fillWidth: true }
                Btn {
                    objectName: "pickAll"
                    small: true; kind: "ghost"
                    text: page.pickedCount === library.model.count && page.pickedCount > 0 ? "Keine" : "Alle"
                    onClicked: page.pickAll()
                }
                Btn {
                    objectName: "mergePicked"
                    small: true; kind: "ghost"; iconName: "import"
                    enabled: page.pickedCount > 1
                    text: page.pickedCount > 1 ? page.pickedCount + " zusammenführen" : "Zusammenführen"
                    ToolTip.visible: hovered; ToolTip.delay: 400
                    ToolTip.text: "Mehrere Aufnahmen → eine: hintereinander, ein Transkript, Sprecher über alle Teile. Die einzelnen bleiben."
                    onClicked: page.mergePicked()
                }
                Btn {
                    objectName: "deletePicked"
                    small: true; kind: "danger"; iconName: "trash"
                    enabled: page.pickedCount > 0
                    text: page.pickedCount > 0 ? page.pickedCount + " löschen" : "Löschen"
                    onClicked: page.deletePicked()
                }
            }
        }

        // ---- list
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 320
            Layout.preferredHeight: 320
            clip: true
            spacing: 10
            model: library.model
            bottomMargin: 36
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: RecordingRow {
                width: list.width - 14
                selecting: page.selecting
                picked: !!page.picked[rid]
                onClicked: page.selecting ? page.togglePick(rid) : page.app.openRecording(rid)
            }
            add: Transition {
                ParallelAnimation {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.mid }
                    NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.mid; easing.type: Easing.OutCubic }
                }
            }
            displaced: Transition { NumberAnimation { properties: "y"; duration: Theme.mid; easing.type: Easing.OutCubic } }

            // empty state
            ColumnLayout {
                visible: list.count === 0
                anchors.centerIn: parent
                width: Math.min(parent.width - 40, 460)
                spacing: 14
                Rectangle {
                    id: pulse1
                    Layout.alignment: Qt.AlignHCenter
                    width: 84; height: 84; radius: 42
                    color: Theme.accentSoft
                    Icon { anchors.centerIn: parent; width: 36; height: 36; name: library.query ? "search" : "live"; color: Theme.accent }
                    SequentialAnimation on scale {
                        onRunningChanged: if (!running) pulse1.scale = 1
                        running: list.count === 0 && page.shown
                        loops: Animation.Infinite
                        NumberAnimation { to: 1.06; duration: 1400; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1; duration: 1400; easing.type: Easing.InOutSine }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: library.query ? "Nichts zu „" + library.query + "“" : "Noch keine Aufnahmen"
                    font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; font.letterSpacing: -0.8
                    color: Theme.fg
                    wrapMode: Text.WordWrap
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: library.query ? "Gesucht wird in Titeln, Notizen und allem, was gesagt wurde."
                        : "Gespräch aufnehmen – oder eine fertige Audio- oder Videodatei transkribieren (auch einfach ins Fenster ziehen)."
                    font.family: Theme.text; font.pixelSize: 15; color: Theme.fg2
                }
                RowLayout {
                    visible: !library.query
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 6
                    spacing: 10
                    Btn { kind: "primary"; text: "Aufnehmen"; iconName: "record"; onClicked: page.app.startRecording() }
                    Btn { text: "Datei transkribieren"; iconName: "import"; onClicked: page.app.importFiles() }
                }
            }
        }
    }
    }
}
