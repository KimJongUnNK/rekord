import QtQuick
import QtQuick.Controls.Basic
import "."

// Drop-down: model = [{value, label}], value = the chosen one.
ComboBox {
    id: c
    property var options: []
    property var value
    signal picked(var value)
    function openList() { popup.open() }
    function closeList() { popup.close() }
    readonly property real listHeight: popup.contentItem ? popup.contentItem.height : 0
    readonly property real listContentHeight: popup.contentItem ? popup.contentItem.contentHeight : 0
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
        width: c.popup.width - 8 - (c.popup.contentItem.ScrollBar.vertical.visible ? 10 : 0)
        height: 38
        highlighted: c.highlightedIndex === index
        contentItem: Text { text: modelData.label; font: c.font; color: Theme.fg; elide: Text.ElideRight; wrapMode: Text.NoWrap }
        background: Rectangle { color: highlighted ? Theme.card2 : Theme.card }
    }
    // the list: as tall as its entries, at most ~9 rows (or what fits in the window) – then it scrolls (wheel, drag, bar)
    popup: Popup {
        y: c.height + 4
        width: Math.max(c.width, 220)
        padding: 4
        implicitHeight: Math.min(list.contentHeight + 8, 9 * 38 + 8, c.Window.height ? c.Window.height * 0.6 : 360)
        contentItem: ListView {
            id: list
            objectName: "selectList"
            clip: true
            implicitHeight: contentHeight
            model: c.popup.visible ? c.delegateModel : null
            currentIndex: c.highlightedIndex
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 0
            ScrollBar.vertical: ScrollBar { policy: list.contentHeight > list.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
            onVisibleChanged: if (visible) positionViewAtIndex(Math.max(0, c.currentIndex), ListView.Center)
        }
        background: Rectangle { radius: 10; color: Theme.card; border.width: 1; border.color: Theme.line }
    }
}
