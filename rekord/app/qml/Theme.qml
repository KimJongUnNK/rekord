pragma Singleton
import QtQuick

// REKORD's look: bold type, two themes, one accent – the same palette as the iPhone app.
QtObject {
    property string mode: "system"  // system | light | dark
    readonly property bool dark: mode === "dark" || (mode === "system" && Qt.styleHints.colorScheme !== Qt.ColorScheme.Light)

    readonly property color accent: "#FF5A1F"
    readonly property color accentSoft: Qt.rgba(1, 0.353, 0.122, dark ? 0.16 : 0.12)
    readonly property color bg: dark ? "#0B0B0C" : "#F6F5F2"
    readonly property color bg2: dark ? "#121214" : "#EFEDE8"
    readonly property color card: dark ? "#161618" : "#FFFFFF"
    readonly property color card2: dark ? "#1D1D20" : "#F3F1EC"
    readonly property color line: dark ? "#2A2A2E" : "#E2DFD8"
    readonly property color line2: dark ? "#38383D" : "#D2CEC5"
    readonly property color fg: dark ? "#F6F5F2" : "#111111"
    readonly property color fg2: dark ? "#B4B2AC" : "#55534E"
    readonly property color fg3: dark ? "#77756F" : "#8A877F"
    readonly property color onAccent: dark ? "#0B0B0C" : "#FFFFFF"
    readonly property color ok: "#22C55E"
    readonly property color err: "#EF4444"
    readonly property color warn: "#F59E0B"
    readonly property color scrim: dark ? Qt.rgba(0, 0, 0, 0.62) : Qt.rgba(0.07, 0.06, 0.04, 0.38)

    readonly property string display: Qt.platform.os === "osx" ? "SF Pro Display"
                                    : Qt.platform.os === "windows" ? "Segoe UI Variable Display" : Qt.application.font.family
    readonly property string text: Qt.platform.os === "windows" ? "Segoe UI Variable Text" : Qt.application.font.family

    readonly property int radius: 14
    readonly property int radiusSm: 9
    readonly property int fast: 140
    readonly property int mid: 240
    readonly property int slow: 420
}
