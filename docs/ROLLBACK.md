# Rollback Guide

## When to rollback

- Login fails globally
- File upload/preview/download has severe regression
- Data model mismatch after deployment

## 1) Stop services

```bash
sudo systemctl stop knowledge-platform
```

## 2) Restore code to previous commit

```bash
cd /opt/knowledge_platform
git fetch --all
git checkout <previous-good-commit>
```

## 3) Restore database and storage (if needed)

Database:

```bash
cp /opt/knowledge_platform/backups/db/app_YYYYMMDD_HHMMSS.db /opt/knowledge_platform/data/app.db
```

Storage:

```bash
tar -xzf /opt/knowledge_platform/backups/storage/storage_YYYYMMDD_HHMMSS.tar.gz -C /opt/knowledge_platform
```

## 4) Restart services

```bash
sudo systemctl start knowledge-platform
sudo systemctl status knowledge-platform
sudo systemctl reload nginx
```

## 5) Smoke verification

- `GET /health`
- Admin login
- Upload one file
- Preview one PDF/text file
- Restore one recycle-bin item
