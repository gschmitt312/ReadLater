#!/usr/bin/env bash
# Convenience launcher for the 13F Viewer (backend + frontend).
# Requires SEC_USER_AGENT to be set (EDGAR 403s without it).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${SEC_USER_AGENT:-}" ]]; then
  echo "WARNING: SEC_USER_AGENT is not set — EDGAR will reject requests with 403."
  echo "  export SEC_USER_AGENT=\"Your Name <your-email>\""
fi

# Pick an available Python (macOS typically has python3, not python).
PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "ERROR: Python 3 not found. Install it (e.g. 'brew install python') and retry."
  exit 1
fi

# Backend
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  "$PY" -m venv .venv
  ./.venv/bin/pip install -r requirements.txt
fi
./.venv/bin/uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

# Frontend
cd "$ROOT/frontend"
[[ -d node_modules ]] || npm install
npm run dev
