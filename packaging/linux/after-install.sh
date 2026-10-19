#!/bin/sh
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
# the iPhone (app: 8765, browser: 8766, discovery: mDNS) must reach REKORD in the Wi-Fi: open the ports if a firewall runs
if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
  firewall-cmd --permanent --add-port=8765/tcp --add-port=8766/tcp --add-service=mdns >/dev/null 2>&1 \
    && firewall-cmd --reload >/dev/null 2>&1 && echo "REKORD: Firewall-Ports 8765/8766 fürs iPhone freigegeben." || true
elif command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow 8765/tcp >/dev/null 2>&1 && ufw allow 8766/tcp >/dev/null 2>&1 && ufw allow 5353/udp >/dev/null 2>&1 \
    && echo "REKORD: Firewall-Ports 8765/8766 fürs iPhone freigegeben." || true
fi
exit 0
