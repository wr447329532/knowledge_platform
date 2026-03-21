# Ops Checklist (Go-Live Day)

## Pre-go-live

- [ ] `.env` reviewed (secret, db, storage, quota)
- [ ] `alembic upgrade head` executed successfully
- [ ] Default admin password changed
- [ ] Backend service running without `--reload`
- [ ] Nginx config tested (`nginx -t`)
- [ ] HTTPS enabled
- [ ] DB backup + storage backup completed

## Functional checks

- [ ] Login/logout
- [ ] Create library / edit library policy
- [ ] Upload / rename / delete / restore file
- [ ] Controlled preview for PDF/text/image
- [ ] Download permission behavior by role
- [ ] Department tree shared-library visibility
- [ ] My/Dept/Global recycle bin behavior
- [ ] Account security info displayed correctly

## Observability

- [ ] Service logs writable and rotating
- [ ] Disk usage alarm configured
- [ ] CPU/memory monitoring visible

## Post-go-live (first 48h)

- [ ] Hourly quick health checks
- [ ] Review error logs twice per day
- [ ] Validate backup jobs executed successfully
