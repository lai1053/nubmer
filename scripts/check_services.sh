#!/usr/bin/env bash
set -euo pipefail

PUBLIC_HOST="${PUBLIC_HOST:-127.0.0.1}"

check_url() {
  local label="$1"
  local url="$2"
  echo "==> ${label}: ${url}"
  if curl -fsS -m 8 "$url" >/tmp/nubmer-check.out 2>/tmp/nubmer-check.err; then
    head -c 300 /tmp/nubmer-check.out
    echo
  else
    echo "FAILED"
    cat /tmp/nubmer-check.err >&2 || true
    return 1
  fi
}

check_head() {
  local label="$1"
  local url="$2"
  echo "==> ${label}: ${url}"
  curl -fsSI -m 8 "$url" | sed -n '1,8p'
}

failures=0

check_url "5173 backend health" "http://127.0.0.1:18080/api/health" || failures=$((failures + 1))
check_url "5174 backend health" "http://127.0.0.1:18084/api/health" || failures=$((failures + 1))
check_url "5174 frozen-windows" "http://127.0.0.1:18084/api/frozen-windows" || failures=$((failures + 1))
check_url "5174 data-quality" "http://127.0.0.1:18084/api/data-quality" || failures=$((failures + 1))
check_url "5174 shadow-status" "http://127.0.0.1:18084/api/shadow/status" || failures=$((failures + 1))
check_head "5173 public nginx" "http://${PUBLIC_HOST}:5173/" || failures=$((failures + 1))
check_head "5174 public nginx" "http://${PUBLIC_HOST}:5174/" || failures=$((failures + 1))
check_head "5200 public nginx" "http://${PUBLIC_HOST}:5200/" || failures=$((failures + 1))

echo "==> PM2"
if command -v pm2 >/dev/null 2>&1; then
  pm2 status || failures=$((failures + 1))
else
  echo "pm2 not found"
  failures=$((failures + 1))
fi

echo "==> Listening ports"
if command -v ss >/dev/null 2>&1; then
  ss -lntp | grep -E ':(5173|5174|18080|18084)\b' || true
else
  netstat -lntp 2>/dev/null | grep -E ':(5173|5174|18080|18084)\b' || true
fi

rm -f /tmp/nubmer-check.out /tmp/nubmer-check.err

if [ "$failures" -ne 0 ]; then
  echo "Service check completed with ${failures} failure(s)." >&2
  exit 1
fi

echo "All service checks passed."
