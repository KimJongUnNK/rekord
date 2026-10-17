#!/bin/bash
# Installs + starts REKORD inside a distro container and checks hub, web UI, CLI and MCP.
# Usage (in container): test-in-distro.sh "<install command>" <port> [full]
#   full = also transcribe /fx/meeting1.wav (needs MODELS=<models dir> and the fixture mounted)
set -u
INSTALL="$1"; PORT="$2"; FULL="${3:-}"
sh -c "$INSTALL" > /tmp/install.log 2>&1 || { echo "INSTALL FAILED"; tail -5 /tmp/install.log; exit 1; }
REKORD=$(command -v rekord || echo /opt/rekord/REKORD)
echo "installed: $REKORD"
[ -f /usr/share/applications/rekord.desktop ] && echo "desktop entry: ok" || echo "desktop entry: (none)"
mkdir -p /rk
[ -n "${MODELS:-}" ] && ln -sfn "$MODELS" /rk/models
export REKORD_HOME=/rk REKORD_PORT=$PORT REKORD_LAN=0 REKORD_HEADLESS=1
"$REKORD" > /tmp/app.log 2>&1 &
ok=""
for i in $(seq 1 60); do
  if exec 3<>/dev/tcp/127.0.0.1/$PORT 2>/dev/null; then
    printf "GET /api/status HTTP/1.0\r\nHost: x\r\n\r\n" >&3; r=$(cat <&3); exec 3>&-
    echo "$r" | grep -q '"version":"' && { ok=1; break; }
  fi; sleep 1
done
[ -n "$ok" ] && echo "hub: ok (api/status)" || { echo "hub: FAILED"; tail -15 /tmp/app.log; exit 1; }
exec 3<>/dev/tcp/127.0.0.1/$PORT; printf "GET / HTTP/1.0\r\nHost: x\r\n\r\n" >&3
cat <&3 | grep -q "<title>REKORD</title>" && echo "web ui: ok" || { echo "web ui: FAILED"; exit 1; }; exec 3>&-
"$REKORD" models list 2>/dev/null | grep -q "whisper-small" && echo "cli: ok" || { echo "cli: FAILED"; exit 1; }
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' \
  | timeout 30 "$REKORD" mcp 2>/dev/null | head -c 400 | grep -q '"serverInfo"' && echo "mcp: ok" || { echo "mcp: FAILED"; exit 1; }
if [ "$FULL" = full ]; then
  out=$(REKORD_PORT=0 timeout 300 "$REKORD" process /fx/meeting1.wav 2>/dev/null)
  echo "transcribe: $(echo "$out" | grep -c '^\*\*Sprecher') lines, speakers: $(echo "$out" | grep -o '^\*\*Sprecher [0-9]' | sort -u | tr '\n' ' ')"
  echo "$out" | grep -m2 "Sprecher" | cut -c1-110
fi
