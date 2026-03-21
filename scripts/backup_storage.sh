#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/knowledge_platform"
STORAGE_DIR="${APP_ROOT}/storage"
BACKUP_DIR="${APP_ROOT}/backups/storage"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "${BACKUP_DIR}"

if [[ ! -d "${STORAGE_DIR}" ]]; then
  echo "Storage directory not found: ${STORAGE_DIR}"
  exit 1
fi

tar -czf "${BACKUP_DIR}/storage_${TS}.tar.gz" -C "${APP_ROOT}" storage

# Keep latest 14 backups
ls -1t "${BACKUP_DIR}"/storage_*.tar.gz 2>/dev/null | sed -n '15,$p' | xargs -r rm -f

echo "Storage backup completed: ${BACKUP_DIR}/storage_${TS}.tar.gz"
