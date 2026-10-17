#!/bin/sh
set -eu

if [ ! -f /app/data/radar.db ]; then
  mkdir -p /app/data
  if [ -f /app/seed/radar.db ]; then
    cp /app/seed/radar.db /app/data/radar.db
  fi
fi

cd /app
if [ "${UV_SYNC:-}" = "1" ]; then
  uv sync --frozen --no-dev
fi

port="${PORT:-8000}"
if [ "${UVICORN_RELOAD:-}" = "1" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port "$port" --reload --reload-dir /app/app
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$port"
