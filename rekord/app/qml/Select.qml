import QtQuick
import QtQuick.Controls.Basic
import "."

// Drop-down: model = [{value, label}], value = the chosen one.
ComboBox {
    id: c
    property var options: []
    property var value
    signal picked(var value)
    model: options
    textRole: "label"
    valueRole: "value"
    currentIndex: Math.max(0, options.findIndex(o => o.value === value))
    onActivated: (i) => { c.value = options[i].value; c.picked(options[i].value) }
    font.family: Theme.text
    font.pixelSize: 14
    implicitHeight: 38
    hoverEnabled: true
    background: Rectangle { radius: 10; color: Theme.card; border.width: c.visualFocus ? 2 : 1; border.color: c.visualFocus ? Theme.accent : c.hovered ? Theme.line2 : Theme.line }
    contentItem: Text {
        leftPadding: 12
        rightPadding: 28
        text: c.displayText
        font: c.font
        color: Theme.fg
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Icon { name: "next"; rotation: 90; width: 14; height: 14; color: Theme.fg3; x: c.width - width - 10; y: (c.height - height) / 2 }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: c.popup.width
        highlighted: c.highlightedIndex === index
        contentItem: Text { text: modelData.label; font: c.font; color: Theme.fg; elide: Text.ElideRight; wrapMode: Text.NoWrap }
        background: Rectangle { color: highlighted ? Theme.card2 : Theme.card }
    }
    popup.background: Rectangle { radius: 10; color: Theme.card; border.width: 1; border.color: Theme.line }
    popup.implicitHeight: Math.min(contentItem.implicitHeight + 8, 420)
}
