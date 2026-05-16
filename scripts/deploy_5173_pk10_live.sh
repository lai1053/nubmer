#!/usr/bin/env bash
set -euo pipefail

APP_BASE="${APP_BASE:-/root/pk10}"
REPO_DIR="${REPO_DIR:-${APP_BASE}/nubmer}"
PK10_APP_DIR="${PK10_APP_DIR:-${APP_BASE}/pk10_live_dashboard}"
PK10_WEB_ROOT="${PK10_WEB_ROOT:-/var/www/pk10-live}"
PK10_ENV_FILE="${PK10_ENV_FILE:-${APP_BASE}/.env}"
PK10_PM2_NAME="${PK10_PM2_NAME:-pk10-live-dashboard}"
NGINX_AVAILABLE="${NGINX_AVAILABLE:-/etc/nginx/sites-available/pk10-live.conf}"
NGINX_ENABLED="${NGINX_ENABLED:-/etc/nginx/sites-enabled/pk10-live.conf}"

if [ ! -d "${REPO_DIR}/pk10_live_dashboard" ]; then
  echo "Missing source directory: ${REPO_DIR}/pk10_live_dashboard" >&2
  exit 1
fi

mkdir -p "${PK10_APP_DIR}" "${PK10_WEB_ROOT}" "${APP_BASE}"

src="$(cd "${REPO_DIR}/pk10_live_dashboard" && pwd)"
if [ "$(cd "${PK10_APP_DIR}" 2>/dev/null && pwd || true)" != "$src" ]; then
  rsync -a --delete \
    --exclude 'backend/.venv/' \
    --exclude 'backend/__pycache__/' \
    --exclude 'backend/app/__pycache__/' \
    --exclude 'backend/auth_users.json' \
    --exclude 'frontend/node_modules/' \
    --exclude 'frontend/dist/' \
    --exclude '.DS_Store' \
    "${src}/" "${PK10_APP_DIR}/"
fi

if [ ! -f "$PK10_ENV_FILE" ]; then
  install -m 600 "${PK10_APP_DIR}/backend/.env.example" "$PK10_ENV_FILE"
  echo "Created ${PK10_ENV_FILE} from example. Review database and auth settings before production use." >&2
fi

python3 -m venv "${PK10_APP_DIR}/backend/.venv"
"${PK10_APP_DIR}/backend/.venv/bin/pip" install -U pip
"${PK10_APP_DIR}/backend/.venv/bin/pip" install -r "${PK10_APP_DIR}/backend/requirements.txt"

npm --prefix "${PK10_APP_DIR}/frontend" ci
npm --prefix "${PK10_APP_DIR}/frontend" run build
rsync -a --delete "${PK10_APP_DIR}/frontend/dist/" "${PK10_WEB_ROOT}/"

install -m 644 "${PK10_APP_DIR}/deploy/pk10.nginx.conf" "$NGINX_AVAILABLE"
ln -sfn "$NGINX_AVAILABLE" "$NGINX_ENABLED"
nginx -t

if pm2 describe "$PK10_PM2_NAME" >/dev/null 2>&1; then
  pm2 restart "$PK10_PM2_NAME" --update-env
else
  pm2 start "${PK10_APP_DIR}/deploy/ecosystem.config.cjs"
fi
pm2 save || true

if command -v systemctl >/dev/null 2>&1; then
  systemctl reload nginx
else
  nginx -s reload
fi

curl -fsS "http://127.0.0.1:18080/api/health" >/dev/null
curl -fsSI "http://127.0.0.1:5173/" >/dev/null

echo "5173 deployment complete."
