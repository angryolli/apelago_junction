#!/bin/sh
set -eu

cd /app
bun install --frozen-lockfile
exec bun run dev --host 0.0.0.0 --port 5173
