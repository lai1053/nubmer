#!/usr/bin/env bash
set -euo pipefail

APP_BASE="${APP_BASE:-/root/pk10}"
REPO_DIR="${REPO_DIR:-${APP_BASE}/nubmer}"
JSFT_APP_DIR="${JSFT_APP_DIR:-/root/jsft_pk10}"
JSFT_ENV_FILE="${JSFT_ENV_FILE:-${JSFT_APP_DIR}/.env}"
JSFT_PM2_NAME="${JSFT_PM2_NAME:-jsft-pk10-shadow}"
NGINX_AVAILABLE="${NGINX_AVAILABLE:-/etc/nginx/sites-available/jsft-pk10-shadow.conf}"
NGINX_ENABLED="${NGINX_ENABLED:-/etc/nginx/sites-enabled/jsft-pk10-shadow.conf}"

if [ ! -d "${REPO_DIR}/jsft_pk10" ]; then
  echo "Missing source directory: ${REPO_DIR}/jsft_pk10" >&2
  exit 1
fi

mkdir -p "${JSFT_APP_DIR}"

src="$(cd "${REPO_DIR}/jsft_pk10" && pwd)"
if [ "$(cd "${JSFT_APP_DIR}" 2>/dev/null && pwd || true)" != "$src" ]; then
  rsync -a --delete \
    --exclude '.env' \
    --exclude '.env.bak*' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'data/*.log' \
    --exclude 'data/*last.json' \
    --exclude 'data/live_shadow_log.csv' \
    --exclude '.DS_Store' \
    "${src}/" "${JSFT_APP_DIR}/"
fi

if [ ! -f "$JSFT_ENV_FILE" ]; then
  install -m 600 "${JSFT_APP_DIR}/.env.example" "$JSFT_ENV_FILE"
  echo "Created ${JSFT_ENV_FILE} from example. Review database settings before production use." >&2
fi

python3 -m venv "${JSFT_APP_DIR}/.venv"
"${JSFT_APP_DIR}/.venv/bin/pip" install -U pip
"${JSFT_APP_DIR}/.venv/bin/pip" install -r "${JSFT_APP_DIR}/requirements.txt"

install -m 644 "${JSFT_APP_DIR}/jsft-pk10-shadow.nginx.conf" "$NGINX_AVAILABLE"
ln -sfn "$NGINX_AVAILABLE" "$NGINX_ENABLED"
nginx -t

if pm2 describe "$JSFT_PM2_NAME" >/dev/null 2>&1; then
  pm2 restart "$JSFT_PM2_NAME" --update-env
else
  pm2 start "${JSFT_APP_DIR}/ecosystem.config.cjs"
fi
pm2 save || true

if command -v systemctl >/dev/null 2>&1; then
  systemctl reload nginx
else
  nginx -s reload
fi

curl -fsS "http://127.0.0.1:18084/api/health" >/dev/null
curl -fsSI "http://127.0.0.1:5174/" >/dev/null

echo "5174 deployment complete."
