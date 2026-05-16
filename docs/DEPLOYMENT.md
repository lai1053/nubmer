# Server Deployment

These notes describe how to deploy this repository on a Linux server.

## Prerequisites

- Ubuntu/Debian style host
- Python 3.10+
- Node.js and npm
- nginx
- PM2
- MySQL reachable from the server
- Git access to `git@github.com:lai1053/nubmer.git`

Install common packages:

```bash
sudo bash scripts/bootstrap_server.sh
```

The bootstrap script is intentionally conservative. It installs missing system packages through `apt` when available and enables nginx when systemd is available.

## Clone

```bash
mkdir -p /root/pk10
cd /root/pk10
git clone git@github.com:lai1053/nubmer.git
cd nubmer
```

To update an existing checkout:

```bash
cd /root/pk10/nubmer
git pull --ff-only origin main
```

## Deploy 5173

```bash
cd /root/pk10/nubmer
sudo bash scripts/deploy_5173_pk10_live.sh
```

Defaults:

- repository source: `/root/pk10/nubmer/pk10_live_dashboard`
- runtime source: `/root/pk10/pk10_live_dashboard`
- environment file: `/root/pk10/.env`
- frontend root: `/var/www/pk10-live`
- nginx config: `/etc/nginx/sites-available/pk10-live.conf`
- PM2 app: `pk10-live-dashboard`
- backend health: `http://127.0.0.1:18080/api/health`

If `/root/pk10/.env` does not exist, the script creates it from `pk10_live_dashboard/backend/.env.example` and prints a warning. Edit it before depending on the service.

## Deploy 5174

```bash
cd /root/pk10/nubmer
sudo bash scripts/deploy_5174_jsft_shadow.sh
```

Defaults:

- repository source: `/root/pk10/nubmer/jsft_pk10`
- runtime source: `/root/jsft_pk10`
- environment file: `/root/jsft_pk10/.env`
- nginx config: `/etc/nginx/sites-available/jsft-pk10-shadow.conf`
- PM2 app: `jsft-pk10-shadow`
- backend health: `http://127.0.0.1:18084/api/health`

If `/root/jsft_pk10/.env` does not exist, the script creates it from `jsft_pk10/.env.example` and prints a warning. Edit it before depending on the service.

## Path Overrides

The scripts support path overrides through environment variables:

```bash
APP_BASE=/opt/pk10 \
REPO_DIR=/opt/pk10/nubmer \
PK10_APP_DIR=/opt/pk10/pk10_live_dashboard \
PK10_WEB_ROOT=/srv/pk10-live \
sudo -E bash scripts/deploy_5173_pk10_live.sh
```

```bash
REPO_DIR=/opt/pk10/nubmer \
JSFT_APP_DIR=/opt/jsft_pk10 \
sudo -E bash scripts/deploy_5174_jsft_shadow.sh
```

## Verification

```bash
bash scripts/check_services.sh
```

Manual checks:

```bash
pm2 status
curl http://127.0.0.1:18080/api/health
curl http://127.0.0.1:18084/api/health
curl -I http://127.0.0.1:5173/
curl -I http://127.0.0.1:5174/
```

## Rollback

Rollback is Git based:

```bash
cd /root/pk10/nubmer
git log --oneline -10
git checkout <known-good-commit>
sudo bash scripts/deploy_5173_pk10_live.sh
sudo bash scripts/deploy_5174_jsft_shadow.sh
```

Return to main afterward:

```bash
git checkout main
git pull --ff-only origin main
```
