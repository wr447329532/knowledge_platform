#!/usr/bin/env sh
set -eu
echo "[entrypoint] waiting for database (if applicable)..."
sleep 2
echo "[entrypoint] starting backend..."
exec gunicorn backend.app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${GUNICORN_WORKERS:-4}" \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile -
