#!/bin/sh
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
# REKORD stays on this computer (127.0.0.1) – no open ports. Versions up to 1.4.0 opened 8765 for the iPhone app: close it.
if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
  if firewall-cmd --permanent --query-port=8765/tcp >/dev/null 2>&1; then
    firewall-cmd --permanent --remove-port=8765/tcp >/dev/null 2>&1 && firewall-cmd --reload >/dev/null 2>&1 || true
  fi
elif command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "8765/tcp"; then
  ufw delete allow 8765/tcp >/dev/null 2>&1 || true
fi
exit 0
