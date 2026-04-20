module.exports = {
  apps: [
    {
      name: 'pk10-live-dashboard',
      cwd: '/root/pk10/pk10_live_dashboard/backend',
      script: '/bin/bash',
      args: '-lc "set -a && source /root/pk10/.env && exec /root/pk10/pk10_live_dashboard/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18080"',
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
