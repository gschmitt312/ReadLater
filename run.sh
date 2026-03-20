#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if ! command -v uvicorn &>/dev/null; then
  echo "Installing dependencies…"
  pip install -r requirements.txt
fi

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
