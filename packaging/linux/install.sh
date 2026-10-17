#!/bin/sh
# Install REKORD for the current user (no root):  ./install.sh      Remove:  ./install.sh --uninstall
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="${XDG_DATA_HOME:-$HOME/.local/share}/rekord"
BIN="$HOME/.local/bin"
DESK="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
if [ "$1" = "--uninstall" ]; then
  rm -rf "$APP" "$BIN/rekord" "$DESK/rekord.desktop" "$ICONS/256x256/apps/rekord.png" "$ICONS/512x512/apps/rekord.png"
  echo "REKORD entfernt (deine Aufnahmen in ~/Rekord bleiben)."; exit 0
fi
mkdir -p "$APP" "$BIN" "$DESK" "$ICONS/256x256/apps" "$ICONS/512x512/apps"
rm -rf "$APP/app" && cp -a "$HERE/rekord" "$APP/app"
printf '#!/bin/sh\nexec "%s/app/REKORD" "$@"\n' "$APP" > "$BIN/rekord" && chmod +x "$BIN/rekord"
sed "s#^Exec=rekord#Exec=$BIN/rekord#" "$HERE/rekord.desktop" > "$DESK/rekord.desktop"
cp "$HERE/icons/256.png" "$ICONS/256x256/apps/rekord.png"; cp "$HERE/icons/512.png" "$ICONS/512x512/apps/rekord.png"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$DESK" || true
echo "REKORD installiert → im App-Menü oder mit 'rekord' starten."
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Hinweis: $BIN ist nicht im PATH.";; esac
