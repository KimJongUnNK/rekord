import QtQuick
import QtQuick.Layouts
import "."

// Suchen & Ersetzen in the transcript (e.g. a misheard name), optionally into the vocabulary for future recordings.
Sheet {
    id: d
    required property var page
    function start() { f1.text = ""; f2.text = ""; sp.checked = true; voc.checked = false; open(); f1.forceActiveFocus() }
    function go() {
        const find = f1.text, replace = f2.text, app = page.app
        if (!find) return
        app.call("POST", "/api/recordings/" + page.rid + "/find_replace", { find: find, replace: replace, speakers: sp.checked }, (r) => {
            app.toast(r.changed + " Stellen ersetzt")
            page.reload()
            if (voc.checked) app.call("GET", "/api/settings", null, (s) => {
                app.call("PUT", "/api/settings", { vocabulary: (s.vocabulary || []).concat([{ from: find, to: replace }]) }, () => {})
            })
        })
        close()
    }
    contentItem: ColumnLayout {
        spacing: 12
        Text { text: "Suchen & Ersetzen"; font.family: Theme.display; font.pixelSize: 26; font.weight: Font.Black; color: Theme.fg }
        Input { id: f1; Layout.fillWidth: true; placeholderText: "Suchen (z. B. falsch erkannter Name)" }
        Input { id: f2; Layout.fillWidth: true; placeholderText: "Ersetzen durch"; onAccepted: d.go() }
        Check { id: sp; text: "Auch Sprechernamen" }
        RowLayout { Check { id: voc; text: "Dauerhaft ins Vokabular übernehmen (künftige Aufnahmen)" } Tip { key: "vocab" } }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Btn { text: "Abbrechen"; onClicked: d.close() }
            Btn { kind: "primary"; text: "Alle ersetzen"; enabled: f1.text !== ""; onClicked: d.go() }
        }
    }
}
