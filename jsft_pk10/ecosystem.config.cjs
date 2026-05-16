module.exports = {
  apps: [
    {
      name: 'jsft-pk10-shadow',
      cwd: '/root/jsft_pk10',
      script: '/bin/bash',
      args: '-lc "set -a && source /root/jsft_pk10/.env && exec /root/jsft_pk10/.venv/bin/python -m uvicorn app:app --host ${JSFT_HOST:-0.0.0.0} --port ${JSFT_PORT:-5174}"',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_restarts: 10,
      env: {
        PYTHONUNBUFFERED: '1'
      }
    }
  ]
}
