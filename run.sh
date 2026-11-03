#!/usr/bin/env bash
# Lance SANKOFA : backend + interface compilée sur http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r backend/requirements.txt; }
[ -f .env ] || cp .env.example .env
if [ ! -d frontend/dist ] || [ "${REBUILD:-0}" = "1" ]; then
  (cd frontend && npm install --silent && npm run build)
fi
[ -f data/places/porto-novo-marche/manifest.json ] || (cd backend && ../.venv/bin/python harvest.py)
ls data/music/*.mp3 >/dev/null 2>&1 || (cd backend && ../.venv/bin/python build_music.py)
cd backend && exec ../.venv/bin/uvicorn sankofa.api:app --host 127.0.0.1 --port "${PORT:-8000}"
