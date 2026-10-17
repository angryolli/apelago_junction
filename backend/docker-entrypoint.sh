#!/bin/sh
set -eu

cd /app
uv sync --frozen --no-dev
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
