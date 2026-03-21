#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/knowledge_platform"
DB_PATH="${APP_ROOT}/data/app.db"
BACKUP_DIR="${APP_ROOT}/backups/db"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "${BACKUP_DIR}"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "Database file not found: ${DB_PATH}"
  exit 1
fi

cp "${DB_PATH}" "${BACKUP_DIR}/app_${TS}.db"

# Keep latest 30 backups
ls -1t "${BACKUP_DIR}"/app_*.db 2>/dev/null | sed -n '31,$p' | xargs -r rm -f

echo "DB backup completed: ${BACKUP_DIR}/app_${TS}.db"
