# Production Deployment Guide

## 1) Server prerequisites

- Ubuntu 22.04+ (or similar Linux)
- `python3`, `python3-venv`, `nginx`, `git`
- Optional but recommended: PostgreSQL 14+

## 2) Directory layout

```text
/opt/knowledge_platform
├── backend/
├── frontend/
├── .venv/
├── .env
├── storage/
├── data/
└── backups/
```

## 3) Pull code and install dependencies

```bash
cd /opt
git clone https://github.com/wr447329532/knowledge_platform.git
cd /opt/knowledge_platform
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## 4) Configure env

```bash
cp deploy/.env.example.prod .env
```

Update at least:

- `JWT_SECRET_KEY` (must be strong random value)
- `DATABASE_URL`
- `STORAGE_ROOT`
- `STORAGE_SYSTEM_TOTAL_BYTES`

Create storage/data directories:

```bash
mkdir -p /opt/knowledge_platform/storage /opt/knowledge_platform/data /opt/knowledge_platform/backups
```

## 5) Build frontend

```bash
cd /opt/knowledge_platform/frontend
npm install
npm run build
```

## 6) Configure systemd backend service

Run DB migrations before first start:

```bash
cd /opt/knowledge_platform
source .venv/bin/activate
alembic upgrade head
```

Then configure and start service:

```bash
sudo cp /opt/knowledge_platform/deploy/systemd/knowledge-platform.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable knowledge-platform
sudo systemctl start knowledge-platform
sudo systemctl status knowledge-platform
```

## 7) Configure nginx

```bash
sudo cp /opt/knowledge_platform/deploy/nginx/knowledge-platform.conf /etc/nginx/sites-available/knowledge-platform
sudo ln -s /etc/nginx/sites-available/knowledge-platform /etc/nginx/sites-enabled/knowledge-platform
sudo nginx -t
sudo systemctl reload nginx
```

## 8) Verify

- API health: `curl http://127.0.0.1:8000/health`
- Frontend: open `http://<server-ip>/`
- Check login, upload, preview, download, recycle bin

## 9) Must-do before internet exposure

- Enable HTTPS (Let's Encrypt)
- Restrict firewall ports
- Change default admin password immediately
- Enable daily backups (see scripts in `scripts/`)

## No-domain deployment (IP only)

If you do not have a domain yet:

- Keep nginx `server_name _;`
- Access via `http://<server-ip>/`
- Skip HTTPS temporarily (but keep service internal or IP-restricted)
- Add only your trusted frontend origins to `CORS_ALLOW_ORIGINS`
