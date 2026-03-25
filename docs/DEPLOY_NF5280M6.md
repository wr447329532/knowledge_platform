# Knowledge Platform Deployment Plan (NF5280M6)

## 1. Server Baseline

- Model: Inspur NF5280M6, 2U, dual-socket platform
- CPU: 1 x Intel Xeon 4316 (20 cores, 2.3GHz)
- Memory: 64GB DDR4 RDIMM
- Disk: 2 x 480GB SSD + 3 x 8TB SATA 7.2K
- RAID: supports RAID 0/1/5
- NIC: 2 x 1GbE
- PSU: 1+1 redundant
- Service: 3-year vendor support

This configuration is sufficient for the current 40-50 user scenario with document preview, upload/download, and audit workloads.

## 2. Recommended Deployment Topology

- Deployment mode: Docker Compose (`nginx + app + postgres`)
- Reverse proxy: Nginx container exposes port 80
- App: FastAPI container (internal port 8000)
- DB: PostgreSQL container (internal service name `db`)
- Storage:
  - DB data volume: `postgres_data`
  - File storage volume: `storage_data`
  - Backup target path on host: `/data/backup`

## 3. RAID and Disk Layout Recommendation

### 3.1 RAID

- 2 x 480GB SSD -> RAID1 (system + Docker runtime + container metadata)
- 3 x 8TB SATA -> RAID5 (business data + backups)

Rationale:
- SSD RAID1 improves OS and container stability.
- SATA RAID5 gives larger usable capacity for file storage and backup retention.

### 3.2 Host path planning (example)

- `/data/kp/storage` (mounted to `storage_data`)
- `/data/kp/postgres` (mounted to `postgres_data`)
- `/data/backup/db` (database backup)
- `/data/backup/storage` (file storage backup)
- `/data/backup/meta` (checksum and restore manifests)

## 4. Container Sizing (Final Draft)

For this hardware and current user scale:

- App workers: start with 4 (can increase to 6 after observation)
- App memory target: 6-10GB under normal load
- PostgreSQL memory target:
  - `shared_buffers`: 4GB
  - `effective_cache_size`: 16GB
  - `work_mem`: 16MB
  - `maintenance_work_mem`: 512MB
- Keep at least 20GB free on SSD and >= 15% free space on RAID5 data volume

## 5. Environment Baseline (Production)

Mandatory `.env` items:

- `JWT_SECRET_KEY`: strong random secret (must replace example)
- `CORS_ALLOW_ORIGINS`: whitelist only trusted origins
- `STORAGE_SYSTEM_TOTAL_BYTES`: set by actual policy
- `DB_AUTO_CREATE_TABLES_ON_STARTUP=false`
- `DB_COMPAT_PATCH_ON_STARTUP=false`
- `RESET_DEFAULT_ADMIN_PASSWORD_ON_STARTUP=false`

Database:
- Use PostgreSQL in production.
- Do not run production on SQLite.

## 6. Preview, Concurrency, and DB Lock Strategy

### 6.1 Concurrency

- Use multi-worker app process (starting at 4 workers).
- Keep Nginx proxy timeout values as currently configured.

### 6.2 Preview cache

Current code renders PDF preview pages on demand. For production:

- Add disk cache for rendered preview pages (recommended implementation in next iteration):
  - key: `entry_id + version_no + page + user_id`
  - TTL: 7 days
  - max cache size: 10GB
  - eviction: least recently used first

### 6.3 DB locks

- PostgreSQL row-level locking is acceptable for this workload.
- Avoid SQLite in production to prevent write lock contention under concurrent upload/audit actions.

## 7. Backup Policy (Hot + Cold)

## 7.1 Target objectives

- RPO: <= 24h (daily backups)
- RTO: <= 2h (single-node restore target)

## 7.2 Hot backup (daily, no downtime)

- DB logical backup: `pg_dump` daily
- Storage incremental backup: `rsync` daily
- Keep:
  - daily backups for 7 days
  - weekly backups for 4 weeks
  - monthly backups for 3 months

Example DB backup command:

```bash
docker exec kp_db pg_dump -U kp_user -d knowledge_platform -F c -f /tmp/kp_$(date +%F).dump
docker cp kp_db:/tmp/kp_$(date +%F).dump /data/backup/db/
```

## 7.3 Cold backup (weekly, short maintenance window)

- Maintenance window: once per week (low traffic period)
- Steps:
  1. Announce maintenance and block writes
  2. Stop app service (or set app read-only mode)
  3. Stop postgres container
  4. Snapshot/tar DB data path + storage path
  5. Start postgres, then app
  6. Validate service and run quick smoke checks

Example cold-backup flow:

```bash
docker compose stop app
docker compose stop db
tar -czf /data/backup/db/cold_db_$(date +%F).tar.gz /data/kp/postgres
tar -czf /data/backup/storage/cold_storage_$(date +%F).tar.gz /data/kp/storage
docker compose start db
docker compose start app
```

## 7.4 Restore drill

- Mandatory weekly restore drill in a test namespace/host
- Verify:
  - app starts successfully
  - `alembic current` is valid
  - login/upload/preview/recycle operations work

## 8. Go-Live Checklist (NF5280M6)

- [ ] `.env` production values reviewed and secret rotated
- [ ] PostgreSQL selected and reachable from app container
- [ ] `alembic upgrade head` executed successfully
- [ ] default admin password changed
- [ ] app container running without development reload mode
- [ ] smoke test passed (login/upload/preview/download/recycle)
- [ ] daily hot backup task enabled and tested
- [ ] weekly cold backup plan scheduled
- [ ] restore drill completed and documented
- [ ] CPU/memory/disk monitoring and alerting enabled

## 9. First 2 Weeks Operations Plan

- Day 1-2:
  - check logs 2 times/day
  - track API 5xx and preview latency
  - monitor disk growth (storage and backups)
- Day 3-7:
  - adjust worker count if needed (4 -> 6 only with evidence)
  - check backup integrity and checksums
- Week 2:
  - complete first full restore drill report
  - finalize baseline capacity report and expansion trigger thresholds

## 10. Expansion Trigger Thresholds

- CPU average > 70% for 3 consecutive days
- memory usage > 80% peak repeatedly
- preview p95 latency > 2.5s during business hours
- storage volume free space < 20%

If any threshold is met, first optimize cache/workers, then evaluate horizontal split (dedicated DB host or object storage migration).
