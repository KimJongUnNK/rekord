#!/usr/bin/env bash
# Packages the PyInstaller build (desktop/dist/REKORD) for every Linux:
#   AppImage (any distro) · .deb (Debian/Ubuntu/Mint/Pop!_OS) · .rpm (Fedora/openSUSE/RHEL)
#   .pkg.tar.zst (Arch/Manjaro/EndeavourOS) · .tar.gz (anything, user install) · PKGBUILD (AUR: rekord-bin)
# Usage: packaging/linux/build.sh <dist/REKORD> <version> <outdir>
# Needs: fpm (gem install fpm), rpm, zstd, libarchive-tools (bsdtar), curl
set -euo pipefail
SRC="$(readlink -f "$1")"; VER="$2"; OUT="$(mkdir -p "$3" && readlink -f "$3")"
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
ICON256="$ROOT/desktop/icon.png"; ICON512="$ROOT/rekord/web/icons/icon-512.png"
DESC="Lokaler KI-Notizrekorder: aufnehmen, transkribieren, live erkennen wer spricht, zusammenfassen mit Claude/ChatGPT/Ollama."
URL="https://github.com/KimJongUnNK/rekord"
MAINT="Emil Boenke <KimJongUnNK@users.noreply.github.com>"
[ -x "$SRC/REKORD" ] || { echo "kein Build unter $SRC"; exit 1; }

# ---------------------------------------------------------------- system layout for deb / rpm / pacman
STAGE="$WORK/stage"
install -d "$STAGE/opt" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
           "$STAGE/usr/share/icons/hicolor/256x256/apps" "$STAGE/usr/share/icons/hicolor/512x512/apps" \
           "$STAGE/usr/share/doc/rekord"
cp -a "$SRC" "$STAGE/opt/rekord"
install -m755 "$HERE/rekord.sh" "$STAGE/usr/bin/rekord"
install -m644 "$HERE/rekord.desktop" "$STAGE/usr/share/applications/rekord.desktop"
install -m644 "$ICON256" "$STAGE/usr/share/icons/hicolor/256x256/apps/rekord.png"
install -m644 "$ICON512" "$STAGE/usr/share/icons/hicolor/512x512/apps/rekord.png"
install -m644 "$ROOT/LICENSE" "$STAGE/usr/share/doc/rekord/LICENSE"

FPM=(fpm -s dir -C "$STAGE" -n rekord -v "$VER" --iteration 1 -a x86_64 --license MIT --url "$URL"
     --maintainer "$MAINT" --vendor "REKORD" --description "$DESC"
     --after-install "$HERE/after-install.sh" --after-remove "$HERE/after-remove.sh" -f)
"${FPM[@]}" -t deb --category sound --deb-recommends xdg-utils --deb-no-default-config-files \
  -p "$OUT/rekord_${VER}_amd64.deb" .
"${FPM[@]}" -t rpm --rpm-os linux --rpm-rpmbuild-define "_build_id_links none" --rpm-tag "Recommends: xdg-utils" \
  -p "$OUT/rekord-${VER}-1.x86_64.rpm" .
"${FPM[@]}" -t pacman --pacman-compression zstd --pacman-optional-depends "xdg-utils: Browser öffnen" \
  -p "$OUT/rekord-${VER}-1-x86_64.pkg.tar.zst" .

# ---------------------------------------------------------------- tar.gz + user installer
TGZ="$WORK/rekord-${VER}"
install -d "$TGZ/icons"
cp -a "$SRC" "$TGZ/rekord"
install -m755 "$HERE/install.sh" "$TGZ/install.sh"
install -m644 "$HERE/rekord.desktop" "$TGZ/rekord.desktop"
install -m644 "$ICON256" "$TGZ/icons/256.png"; install -m644 "$ICON512" "$TGZ/icons/512.png"
install -m644 "$ROOT/LICENSE" "$TGZ/LICENSE"
tar -C "$WORK" -czf "$OUT/REKORD-${VER}-Linux-x86_64.tar.gz" "rekord-${VER}"

# ---------------------------------------------------------------- AppImage
APPDIR="$WORK/REKORD.AppDir"
install -d "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$SRC" "$APPDIR/usr/lib/rekord"
install -m755 "$HERE/AppRun" "$APPDIR/AppRun"
install -m644 "$HERE/rekord.desktop" "$APPDIR/rekord.desktop"
install -m644 "$HERE/rekord.desktop" "$APPDIR/usr/share/applications/rekord.desktop"
install -m644 "$ICON256" "$APPDIR/rekord.png"; ln -s rekord.png "$APPDIR/.DirIcon"
install -m644 "$ICON256" "$APPDIR/usr/share/icons/hicolor/256x256/apps/rekord.png"
TOOL="$WORK/appimagetool"
curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$TOOL"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT/REKORD-${VER}-x86_64.AppImage"

# ---------------------------------------------------------------- AUR PKGBUILD (rekord-bin), checksum filled in
SUM="$(sha256sum "$OUT/REKORD-${VER}-Linux-x86_64.tar.gz" | cut -d' ' -f1)"
sed -e "s/@VERSION@/$VER/g" -e "s/@SHA256@/$SUM/" "$HERE/PKGBUILD.in" > "$OUT/PKGBUILD"

ls -la "$OUT"
