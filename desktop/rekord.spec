# PyInstaller spec:  pyinstaller desktop/rekord.spec   → dist/REKORD(.app/.exe)
# Models are not bundled (downloaded on first start into ~/Rekord/models).
import os
import sys
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas, binaries, hidden = [], [], []
for pkg in ("sherpa_onnx", "av", "webview", "uvicorn", "anthropic", "openai", "zeroconf", "docx", "qrcode", "certifi", "zstandard", "soundcard"):  # PySide6: its own hooks
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception:
        pass
datas += [(os.path.join(ROOT, "rekord", "web"), os.path.join("rekord", "web")),  # previous interface + iPhone pairing page
          (os.path.join(ROOT, "rekord", "app", "qml"), os.path.join("rekord", "app", "qml"))]  # REKORD's window (Qt Quick)

a = Analysis([os.path.join(SPECPATH, "launch.py")], pathex=[ROOT], binaries=binaries, datas=datas,
             hiddenimports=hidden + ["rekord.server", "rekord.mcp_server", "rekord.integrations", "rekord.pairing", "rekord.llm.auto", "rekord.storage",
                                      "rekord.capture", "rekord.updater", "mcp.server.mcpserver", "mcp.server.fastmcp",
                                      "rekord.app", "rekord.app.bridge", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2",
                                      "PySide6.QtMultimedia"]
                           + (["ScreenCaptureKit", "CoreMedia", "dispatch", "Foundation"] if sys.platform == "darwin" else ["soundcard", "cffi"]),
             excludes=["tkinter", "matplotlib", "torch", "PIL",  # PIL: only needed at build time for the icon
                       # Qt parts REKORD doesn't use (the window needs Core, Gui, Qml, Quick, Controls, Multimedia)
                       "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebView",
                       "PySide6.Qt3DCore", "PySide6.QtQuick3D", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
                       "PySide6.QtPdf", "PySide6.QtDesigner", "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtTextToSpeech",
                       "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSerialPort",
                       "PySide6.QtWidgets", "qtpy", "PyQt5", "PyQt6"])

# QML: only the modules the window imports (QtQuick, Controls.Basic, Layouts, Dialogs, Shapes, QtQml) – the rest of
# Qt's QML library (3D, charts, maps, web …) would add hundreds of MB.
_QML_SKIP = ("Qt3D", "QtQuick3D", "QtCharts", "QtDataVisualization", "QtGraphs", "QtLocation", "QtPositioning", "QtSensors",
             "QtTextToSpeech", "QtRemoteObjects", "QtScxml", "QtWebEngine", "QtWebView", "QtWebChannel", "QtWebSockets",
             "QtTest", "Qt5Compat", "QtWayland", "QtMultimedia", "QtQuick/VirtualKeyboard", "QtQuick/Pdf", "QtQuick/Scene2D",
             "QtQuick/Scene3D", "QtQuick/Timeline", "QtQuick/Particles", "QtQuick/LocalStorage",
             "QtQuick/Controls/Material", "QtQuick/Controls/Universal", "QtQuick/Controls/Imagine", "QtQuick/Controls/FluentWinUI3",
             "QtQuick/Controls/Fusion", "QtQuick/Controls/iOS", "QtQuick/Controls/macOS", "QtQuick/Controls/Windows")
_LIB_SKIP = ("Qt6WebEngine", "QtWebEngine", "Qt6Quick3D", "QtQuick3D", "Qt63D", "Qt3D", "Qt6Charts", "QtCharts",
             "Qt6DataVisualization", "QtDataVisualization", "Qt6Graphs", "QtGraphs", "Qt6Pdf", "QtPdf", "Qt6Designer", "QtDesigner",
             "Qt6Location", "QtLocation", "Qt6VirtualKeyboard", "QtVirtualKeyboard", "Qt6Sensors", "QtSensors", "Qt6TextToSpeech",
             "QtTextToSpeech", "Qt6RemoteObjects", "Qt6Scxml", "Qt6Bluetooth", "Qt6Nfc", "Qt6ShaderTools", "QtShaderTools",
             "Qt6QuickParticles", "QtQuickParticles", "Qt6QuickTimeline", "Qt6SpatialAudio", "Qt6Quick3DPhysics",
             "Qt6QuickControls2Material", "Qt6QuickControls2Universal", "Qt6QuickControls2Imagine", "Qt6QuickControls2Fusion",
             "Qt6QuickControls2FluentWinUI3", "Qt6QuickControls2IOS", "Qt6QuickControls2MacOS", "Qt6QuickControls2Windows",
             "QtQuickControls2Material", "QtQuickControls2Universal", "QtQuickControls2Imagine", "QtQuickControls2Fusion",
             "QtQuickControls2FluentWinUI3", "QtQuickControls2IOS", "QtQuickControls2MacOS", "QtQuickControls2Windows")


def _keep(dest):
    d = dest.replace("\\", "/")
    if "/qml/" in d and any(f"/qml/{m}/" in d or d.endswith(f"/qml/{m}") for m in _QML_SKIP):
        return False
    if "/Qt/translations/" in d and "_de." not in d:  # Qt's own texts (file dialog …): German is enough
        return False
    base = d.rsplit("/", 1)[-1]
    return not any(base.startswith(x) or base.startswith("lib" + x) or f"/{x}.framework/" in d for x in _LIB_SKIP)


a.datas = [x for x in a.datas if _keep(x[0])]
a.binaries = [x for x in a.binaries if _keep(x[0])]
pyz = PYZ(a.pure)
icon = os.path.join(SPECPATH, "icon.ico" if sys.platform == "win32" else "icon.png")
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="REKORD", console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="REKORD")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="REKORD.app", icon=os.path.join(SPECPATH, "icon.png"), bundle_identifier="app.rekord.desktop",
                 info_plist={"NSMicrophoneUsageDescription": "REKORD nimmt Meetings auf – alles bleibt auf diesem Mac.",
                             "NSLocalNetworkUsageDescription": "Damit dein iPhone REKORD im WLAN findet und aufnehmen kann.",
                             "NSBonjourServices": ["_rekord._tcp"],
                             "LSApplicationCategoryType": "public.app-category.productivity", "NSHighResolutionCapable": True})
