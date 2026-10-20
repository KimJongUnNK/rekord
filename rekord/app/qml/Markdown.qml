import QtQuick
import "."

// Rendered Markdown (summaries, answers): timestamps jump in the audio, to-dos can be ticked, links open.
TextEdit {
    id: m
    property string source
    signal seek(real sec)
    signal task(int line)
    signal openRecording(string rid, real sec)
    text: rekord.markdown(source)
    textFormat: TextEdit.RichText
    readOnly: true
    selectByMouse: true
    wrapMode: TextEdit.Wrap
    font.family: Theme.text
    font.pixelSize: 15
    color: Theme.fg
    selectionColor: Theme.accent
    selectedTextColor: Theme.onAccent
    onLinkActivated: (link) => {
        if (link.startsWith("seek:")) m.seek(Number(link.slice(5)))
        else if (link.startsWith("task:")) m.task(Number(link.slice(5)))
        else if (link.startsWith("rec:")) { const p = link.split(":"); m.openRecording(p[1], Number(p[2])) }
        else api.openUrl(link)
    }
    HoverHandler { cursorShape: m.hoveredLink ? Qt.PointingHandCursor : Qt.IBeamCursor }
}
