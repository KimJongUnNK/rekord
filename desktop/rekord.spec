# PyInstaller spec:  pyinstaller desktop/rekord.spec   → dist/REKORD(.app/.exe)
# Models are not bundled (downloaded on first start into ~/Rekord/models).
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hidden = [], [], []
for pkg in ("sherpa_onnx", "av", "webview", "uvicorn", "anthropic", "openai", "zeroconf", "mcp", "docx"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception:
        pass
datas += collect_data_files("rekord", includes=["web/*", "web/icons/*"])

a = Analysis(["launch.py"], pathex=[".."], binaries=binaries, datas=datas, hiddenimports=hidden + ["rekord.server"],
             excludes=["tkinter", "matplotlib", "torch"])
pyz = PYZ(a.pure)
icon = "icon.ico" if sys.platform == "win32" else "icon.png"
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="REKORD", console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="REKORD")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="REKORD.app", icon="icon.png", bundle_identifier="app.rekord.desktop",
                 info_plist={"NSMicrophoneUsageDescription": "REKORD nimmt Meetings auf – alles bleibt auf diesem Mac.",
                             "LSApplicationCategoryType": "public.app-category.productivity", "NSHighResolutionCapable": True})
