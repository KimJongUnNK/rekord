#!/bin/sh
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
# really removed (deb: remove/purge, rpm: 0) – not on updates: close the ports again
case "${1:-}" in
  remove|purge|0)
    if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
      firewall-cmd --permanent --remove-port=8765/tcp --remove-port=8766/tcp >/dev/null 2>&1 && firewall-cmd --reload >/dev/null 2>&1 || true
    elif command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
      ufw delete allow 8765/tcp >/dev/null 2>&1; ufw delete allow 8766/tcp >/dev/null 2>&1 || true
    fi ;;
esac
exit 0
