import QtQuick
import QtQuick.Shapes
import "."

// Line icons (24×24, round strokes) – the same set as the previous interface.
Item {
    id: root
    property string name
    property color color: Theme.fg
    property real stroke: 1.8
    property bool filled: false
    implicitWidth: 20
    implicitHeight: 20

    readonly property var paths: ({
        "library": "M4 5h16M4 12h16M4 19h10",
        "live": "M8 12a4 4 0 1 0 8 0a4 4 0 1 0 -8 0M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0",
        "ask": "M4 5h16v11H9l-5 4z",
        "people": "M5.5 8a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0 -7 0M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.9.6 3.1 2.3 3.5 5.2",
        "templates": "M6 3h9l4 4v14H6zM9 11h7M9 15h7",
        "settings": "M9 12a3 3 0 1 0 6 0a3 3 0 1 0 -6 0M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1",
        "search": "M4 11a7 7 0 1 0 14 0a7 7 0 1 0 -14 0M20 20l-3.5-3.5",
        "import": "M12 15V4M7.5 8.5L12 4l4.5 4.5M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4",
        "back": "M15 6l-6 6 6 6",
        "next": "M9 6l6 6-6 6",
        "star": "M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z",
        "pause": "M8 5v14M16 5v14",
        "play": "M7 5l12 7-12 7z",
        "stop": "M6 6h12v12H6z",
        "mic": "M9 6a3 3 0 0 1 6 0v6a3 3 0 0 1-6 0zM5 11a7 7 0 0 0 14 0M12 18v3",
        "room": "M5.5 8a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0 -7 0M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.9.6 3.1 2.3 3.5 5.2",
        "online": "M3 5h18v11H3zM8 20h8M12 16v4",
        "lecture": "M2.5 9l9.5-4.5 9.5 4.5-9.5 4.5zM6.5 11v5c1.5 1.5 3.5 2.3 5.5 2.3s4-.8 5.5-2.3v-5M21.5 9v5",
        "open": "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
        "sun": "M8 12a4 4 0 1 0 8 0a4 4 0 1 0 -8 0M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
        "moon": "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
        "auto": "M12 3v18M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0",
        "check": "M5 12.5l4.5 4.5L19 7",
        "close": "M6 6l12 12M18 6L6 18",
        "folder": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
        "download": "M12 4v11M7.5 10.5L12 15l4.5-4.5M4 20h16",
        "plus": "M12 5v14M5 12h14",
        "minus": "M5 12h14",
        "record": "M7 12a5 5 0 1 0 10 0a5 5 0 1 0 -10 0",
        "wave": "M3 12h2M7 8v8M11 5v14M15 9v6M19 11v2",
        "spark": "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
        "user": "M8 8a4 4 0 1 0 8 0a4 4 0 1 0 -8 0M4 21c1-4 4.2-6 8-6s7 2 8 6"
    })

    Shape {
        width: 24
        height: 24
        anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / 24
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.color
            strokeWidth: root.stroke
            fillColor: root.filled ? root.color : "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.paths[root.name] || "" }
        }
    }
}
