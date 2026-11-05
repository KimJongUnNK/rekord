#!/usr/bin/env bash
# REKORD starten (macOS / Linux). Erster Start: richtet alles ein (~2 Min + Modell-Download).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  echo "→ Richte REKORD ein …"
  "$PY" -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -e ".[all]"
fi
exec .venv/bin/python -m rekord serve "$@"
