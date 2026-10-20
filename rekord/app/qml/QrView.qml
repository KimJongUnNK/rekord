import QtQuick
import "."

// The pairing QR code, drawn crisply from the hub's matrix (always black on white, so every camera reads it).
Rectangle {
    id: q
    property var rows: []
    readonly property int n: rows.length
    color: "#FFFFFF"
    radius: 12
    implicitWidth: 220
    implicitHeight: 220
    Canvas {
        id: c
        anchors.fill: parent
        anchors.margins: 14
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            if (!q.n) return
            const cell = Math.floor(Math.min(width, height) / q.n)
            const off = Math.floor((Math.min(width, height) - cell * q.n) / 2)
            ctx.fillStyle = "#000000"
            for (let y = 0; y < q.n; y++) {
                const r = q.rows[y]
                for (let x = 0; x < r.length; x++) if (r[x] === "1") ctx.fillRect(off + x * cell, off + y * cell, cell, cell)
            }
        }
    }
    onRowsChanged: c.requestPaint()
}
