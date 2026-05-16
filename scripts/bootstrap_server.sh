#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run as root or with sudo: sudo bash scripts/bootstrap_server.sh" >&2
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git rsync nginx python3 python3-venv python3-pip curl ca-certificates
else
  echo "apt-get not found; install git, rsync, nginx, python3, python3-venv, python3-pip, curl manually." >&2
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "node/npm not found. Install Node.js 20+ before deploying the 5173 frontend." >&2
fi

if ! command -v pm2 >/dev/null 2>&1; then
  if command -v npm >/dev/null 2>&1; then
    npm install -g pm2
  else
    echo "pm2 not found and npm is unavailable. Install PM2 manually." >&2
  fi
fi

mkdir -p /root/pk10 /var/www/pk10-live /root/jsft_pk10

if command -v systemctl >/dev/null 2>&1; then
  systemctl enable nginx >/dev/null 2>&1 || true
  systemctl start nginx >/dev/null 2>&1 || true
fi

echo "Bootstrap complete. Next: edit env files, then run deploy_5173_pk10_live.sh and/or deploy_5174_jsft_shadow.sh."
