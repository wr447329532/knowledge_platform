#!/usr/bin/env sh
set -eu

echo "[entrypoint] waiting for database (if applicable)..."
sleep 1

echo "[entrypoint] running alembic migrations..."
alembic upgrade head

echo "[entrypoint] starting backend..."
exec python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
