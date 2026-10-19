#!/bin/sh
# REKORD in one line (macOS with Apple chip, every Linux):
#   curl -fsSL https://github.com/KimJongUnNK/rekord/releases/latest/download/install.sh | sh
# macOS: installs REKORD.app into Programme – without the Gatekeeper "Dennoch öffnen" detour.
# Linux: the right package for your distro (apt, dnf, zypper, pacman), otherwise a user install without root.
# Then REKORD starts. Running it again updates REKORD; your recordings in ~/Rekord stay.
set -eu
REPO="KimJongUnNK/rekord"
say() { printf '\033[1;38;5;202m▸\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || fail "curl fehlt"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
OS="$(uname -s)"
ARCH="$(uname -m)"

if [ "$OS" = "Darwin" ]; then
  [ "$ARCH" = "arm64" ] || fail "REKORD für Mac braucht einen Apple-Chip (M1 oder neuer)."
  say "Lade REKORD für Mac …"
  curl -fL --progress-bar -o "$TMP/rekord.zip" "https://github.com/$REPO/releases/latest/download/REKORD-macOS-AppleSilicon.zip"
  DEST=/Applications
  [ -w "$DEST" ] || DEST="$HOME/Applications"
  mkdir -p "$DEST"
  osascript -e 'tell application "REKORD" to quit' >/dev/null 2>&1 || true
  rm -rf "$DEST/REKORD.app"
  ditto -x -k "$TMP/rekord.zip" "$DEST"
  xattr -dr com.apple.quarantine "$DEST/REKORD.app" 2>/dev/null || true
  say "Installiert: $DEST/REKORD.app – startet jetzt."
  open "$DEST/REKORD.app"
  exit 0
fi

[ "$OS" = "Linux" ] || fail "Dieses Skript ist für macOS und Linux. Windows: siehe Anleitung."
[ "$ARCH" = "x86_64" ] || fail "REKORD für Linux gibt es für x86_64 (Intel/AMD)."
TAG="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest" | sed 's#.*/tag/v##')"
case "$TAG" in [0-9]*) ;; *) fail "Aktuelle Version nicht gefunden – Internet prüfen." ;; esac
URL="https://github.com/$REPO/releases/download/v$TAG"
get() { say "Lade $1 …"; curl -fL --progress-bar -o "$TMP/$1" "$URL/$1"; }

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 && SUDO="sudo"
fi
DONE=""
if [ "$(id -u)" -eq 0 ] || [ -n "$SUDO" ]; then
  [ -n "$SUDO" ] && say "Für die Installation fragt Linux nach deinem Passwort."
  if command -v apt-get >/dev/null 2>&1; then
    F="rekord_${TAG}_amd64.deb"; get "$F"; chmod 644 "$TMP/$F"; chmod 755 "$TMP"
    $SUDO apt-get install -y "$TMP/$F" && DONE=1
  elif command -v dnf >/dev/null 2>&1; then
    F="rekord-${TAG}-1.x86_64.rpm"; get "$F"; $SUDO dnf install -y "$TMP/$F" && DONE=1
  elif command -v zypper >/dev/null 2>&1; then
    F="rekord-${TAG}-1.x86_64.rpm"; get "$F"; $SUDO zypper --non-interactive install --allow-unsigned-rpm "$TMP/$F" && DONE=1
  elif command -v pacman >/dev/null 2>&1; then
    F="rekord-${TAG}-1-x86_64.pkg.tar.zst"; get "$F"; $SUDO pacman -U --noconfirm "$TMP/$F" && DONE=1
  fi
fi
if [ -z "$DONE" ]; then  # any other distro, or no sudo: just for this user
  F="REKORD-${TAG}-Linux-x86_64.tar.gz"; get "$F"
  tar -C "$TMP" -xzf "$TMP/$F"
  sh "$TMP/rekord-${TAG}/install.sh"
fi
say "REKORD $TAG ist installiert – startet jetzt (oder später über das App-Menü)."
BIN="$(command -v rekord || echo "$HOME/.local/bin/rekord")"
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  nohup "$BIN" >/dev/null 2>&1 &
else
  say "Kein Desktop erkannt – Start mit: $BIN"
fi
