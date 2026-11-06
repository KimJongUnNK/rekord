import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// A summary, edited like in Word: font, size, bold, italic, underline, strikethrough, sub/superscript, colour,
// highlight, headings, lists. Saved with every format (and as Markdown for the AI) – copied or exported to Word as is.
Sheet {
    id: d
    objectName: "richEditor"
    property string heading
    property var onSave: null   // fn(markdown, html)
    property var st: ({})       // the formats at the cursor (which buttons are on)
    readonly property var doc: area.textDocument
    readonly property int s0: area.selectionStart
    readonly property int s1: area.selectionEnd
    readonly property var colors: ["#595959", "#C00000", "#FF5A1F", "#C99A06", "#16A34A", "#2D7FF9", "#7C3AED"]
    readonly property var marks: ["#FFF176", "#A5F3B5", "#9ADCFB", "#F9B4D1", "#FFCC99"]

    function edit(title, markdown, html, fn) {
        heading = title
        onSave = fn
        open()
        richFmt.load(area.textDocument, markdown || "", html || "")
        area.cursorPosition = 0
        refresh()
        area.forceActiveFocus()
    }
    function refresh() { st = richFmt.state(area.textDocument, area.selectionStart, area.selectionEnd) }
    function toggle(what) { richFmt.toggle(doc, s0, s1, what); refresh() }
    function save() {
        const md = richFmt.markdown(area.textDocument), html = richFmt.html(area.textDocument), fn = onSave
        close()
        if (fn) fn(md, html)
    }
    width: Math.min(parent ? parent.width - 48 : 980, 980)

    component Tool: AbstractButton {
        id: tb
        property string hint
        property bool on: false
        property string glyph
        property var glyphFont: ({})
        implicitWidth: Math.max(34, label.implicitWidth + 16)
        implicitHeight: 32
        hoverEnabled: true
        focusPolicy: Qt.NoFocus   // the selection in the text stays
        ToolTip.visible: hovered && hint !== ""
        ToolTip.delay: 400
        ToolTip.text: hint
        background: Rectangle {
            radius: 7
            color: tb.on ? Theme.accentSoft : tb.hovered ? Theme.card2 : "transparent"
            border.width: tb.on ? 1 : 0
            border.color: Theme.accentLine
        }
        contentItem: Text {
            id: label
            text: tb.glyph
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: tb.on ? Theme.accent : Theme.fg
            font.family: tb.glyphFont.family || Theme.text
            font.pixelSize: tb.glyphFont.size || 15
            font.bold: !!tb.glyphFont.bold
            font.italic: !!tb.glyphFont.italic
            font.underline: !!tb.glyphFont.underline
            font.strikeout: !!tb.glyphFont.strike
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }
    component Sep: Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 22; color: Theme.line2 }
    component Swatches: Popup {
        id: sw
        property var list: []
        property bool none: false
        signal chose(string c)
        padding: 8
        background: Rectangle { radius: 10; color: Theme.card; border.width: 1; border.color: Theme.line2 }
        contentItem: Row {
            spacing: 6
            Repeater {
                model: sw.list
                delegate: Rectangle {
                    required property string modelData
                    width: 24; height: 24; radius: 6; color: modelData
                    border.width: 1; border.color: Theme.line2
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { sw.chose(parent.modelData); sw.close() } }
                }
            }
            Rectangle {
                visible: sw.none
                width: 24; height: 24; radius: 6; color: "transparent"; border.width: 1; border.color: Theme.line2
                Text { anchors.centerIn: parent; text: "✕"; color: Theme.fg2; font.pixelSize: 12 }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { sw.chose(""); sw.close() } }
            }
        }
    }

    Shortcut { sequences: [StandardKey.Bold]; enabled: d.opened; onActivated: d.toggle("bold") }
    Shortcut { sequences: [StandardKey.Italic]; enabled: d.opened; onActivated: d.toggle("italic") }
    Shortcut { sequences: [StandardKey.Underline]; enabled: d.opened; onActivated: d.toggle("underline") }
    Shortcut { sequences: [StandardKey.Save]; enabled: d.opened; onActivated: d.save() }

    contentItem: ColumnLayout {
        spacing: 10
        Text { text: d.heading; font.family: Theme.display; font.pixelSize: 24; font.weight: Font.Black; color: Theme.fg; Layout.fillWidth: true; elide: Text.ElideRight }

        // ---- the toolbar (like Word)
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: bar.implicitHeight + 16
            radius: 12
            color: Theme.card2
            border.width: 1
            border.color: Theme.line
            Flow {
                id: bar
                anchors.fill: parent
                anchors.margins: 8
                spacing: 4
                Select {
                    objectName: "richFont"
                    width: 170
                    options: [{ value: "", label: "Schrift" }].concat(richFmt.fonts().map(f => ({ value: f, label: f })))
                    value: d.st.font || ""
                    onPicked: (v) => { if (v) richFmt.setFont(d.doc, d.s0, d.s1, v); d.refresh() }
                }
                Select {
                    objectName: "richSize"
                    width: 76
                    options: richFmt.sizes().map(s => ({ value: s, label: String(s) }))
                    value: d.st.size || 12
                    onPicked: (v) => { richFmt.setSize(d.doc, d.s0, d.s1, v); d.refresh() }
                }
                Tool { glyph: "A⁺"; hint: "Schrift größer"; onClicked: { richFmt.grow(d.doc, d.s0, d.s1, 1); d.refresh() } }
                Tool { glyph: "A⁻"; hint: "Schrift kleiner"; onClicked: { richFmt.grow(d.doc, d.s0, d.s1, -1); d.refresh() } }
                Select {
                    objectName: "richHeading"
                    width: 150
                    options: [{ value: 0, label: "Text" }, { value: 1, label: "Überschrift 1" }, { value: 2, label: "Überschrift 2" }, { value: 3, label: "Überschrift 3" }]
                    value: d.st.heading || 0
                    onPicked: (v) => { richFmt.heading(d.doc, d.s0, d.s1, v); d.refresh() }
                }
                Tool { glyph: "⌫"; hint: "Formatierung entfernen"; onClicked: { richFmt.clear(d.doc, d.s0, d.s1); d.refresh() } }
                Sep {}
                Tool { objectName: "richBold"; glyph: "B"; glyphFont: ({ bold: true }); hint: "Fett (Strg/⌘ + B)"; on: !!d.st.bold; onClicked: d.toggle("bold") }
                Tool { glyph: "I"; glyphFont: ({ italic: true, family: "Georgia" }); hint: "Kursiv (Strg/⌘ + I)"; on: !!d.st.italic; onClicked: d.toggle("italic") }
                Tool { glyph: "U"; glyphFont: ({ underline: true }); hint: "Unterstrichen (Strg/⌘ + U)"; on: !!d.st.underline; onClicked: d.toggle("underline") }
                Tool { glyph: "ab"; glyphFont: ({ strike: true, size: 14 }); hint: "Durchgestrichen"; on: !!d.st.strike; onClicked: d.toggle("strike") }
                Tool { glyph: "x₂"; hint: "Tiefgestellt"; on: !!d.st.sub; onClicked: d.toggle("sub") }
                Tool { glyph: "x²"; hint: "Hochgestellt"; on: !!d.st.sup; onClicked: d.toggle("sup") }
                Sep {}
                Tool {
                    id: colorBtn
                    glyph: "A"; glyphFont: ({ bold: true }); hint: "Schriftfarbe"
                    Rectangle { anchors.bottom: parent.bottom; anchors.bottomMargin: 4; anchors.horizontalCenter: parent.horizontalCenter; width: 18; height: 3; radius: 1.5; color: "#C00000" }
                    onClicked: colorPop.open()
                    Swatches { id: colorPop; y: colorBtn.height + 4; list: d.colors; none: true; onChose: (c) => { richFmt.setColor(d.doc, d.s0, d.s1, c); d.refresh() } }
                }
                Tool {
                    id: markBtn
                    glyph: "✎"; hint: "Markieren (Textmarker)"
                    Rectangle { anchors.bottom: parent.bottom; anchors.bottomMargin: 4; anchors.horizontalCenter: parent.horizontalCenter; width: 18; height: 3; radius: 1.5; color: "#FFF176" }
                    onClicked: markPop.open()
                    Swatches { id: markPop; y: markBtn.height + 4; list: d.marks; none: true; onChose: (c) => { richFmt.setHighlight(d.doc, d.s0, d.s1, c); d.refresh() } }
                }
                Sep {}
                Tool { glyph: "• ≡"; hint: "Aufzählung"; on: d.st.list === "bullet"; onClicked: { richFmt.list(d.doc, d.s0, d.s1, "bullet"); d.refresh() } }
                Tool { glyph: "1. ≡"; hint: "Nummerierung"; on: d.st.list === "number"; onClicked: { richFmt.list(d.doc, d.s0, d.s1, "number"); d.refresh() } }
            }
        }

        // ---- the page
        ScrollView {
            id: sv
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(600, (d.parent ? d.parent.height : 760) - 300)
            clip: true
            TextArea {
                id: area
                objectName: "richArea"
                textFormat: TextEdit.RichText
                wrapMode: TextEdit.Wrap
                persistentSelection: true   // stays selected while you click the toolbar
                selectByMouse: true
                font.family: Theme.text
                font.pixelSize: 15
                color: Theme.fg
                selectionColor: Theme.accent
                selectedTextColor: Theme.onAccent
                leftPadding: 22; rightPadding: 22; topPadding: 18; bottomPadding: 18
                background: Rectangle { radius: 12; color: Theme.card; border.width: 1; border.color: Theme.line2 }
                onCursorPositionChanged: d.refresh()
                onSelectionEndChanged: d.refresh()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Muted { Layout.fillWidth: true; font.pixelSize: 12; text: "Text markieren, dann formatieren. Kopieren und Word-Export übernehmen alles genau so." }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { objectName: "richSave"; kind: "primary"; text: "Speichern"; onClicked: d.save() }
        }
    }
}
