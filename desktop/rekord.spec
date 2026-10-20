# PyInstaller spec:  pyinstaller desktop/rekord.spec   → dist/REKORD(.app/.exe)
# Models are not bundled (downloaded on first start into ~/Rekord/models).
import os
import sys
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas, binaries, hidden = [], [], []
for pkg in ("sherpa_onnx", "av", "webview", "uvicorn", "anthropic", "openai", "zeroconf", "docx", "qrcode", "certifi", "zstandard", "soundcard"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception:
        pass
datas += [(os.path.join(ROOT, "rekord", "web"), os.path.join("rekord", "web"))]  # the UI

a = Analysis([os.path.join(SPECPATH, "launch.py")], pathex=[ROOT], binaries=binaries, datas=datas,
             hiddenimports=hidden + ["rekord.server", "rekord.mcp_server", "rekord.integrations", "rekord.pairing", "rekord.llm.auto", "rekord.storage",
                                      "rekord.capture", "rekord.updater", "mcp.server.mcpserver", "mcp.server.fastmcp"]
                           + (["ScreenCaptureKit", "CoreMedia", "dispatch", "Foundation"] if sys.platform == "darwin" else ["soundcard", "cffi"]),
             excludes=["tkinter", "matplotlib", "torch", "PIL"])  # PIL: only needed at build time for the icon
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
