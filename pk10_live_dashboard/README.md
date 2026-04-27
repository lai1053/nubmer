# PK10 Live Dashboard

PK10 Live Dashboard is a FastAPI + React operations console for monitoring PK10 strategy execution, bankroll state, current betting broadcasts, historical bet records, broadcast logs, and application users.

The production deployment used by this project serves the frontend through nginx and proxies API/SSE traffic to a local FastAPI process managed by PM2.

## Features

- Application login with cookie sessions.
- Admin user management: create users, change roles, enable/disable accounts, reset passwords, and review login records.
- Mobile-first dashboard for live PK10 operations:
  - current and next issue
  - SSE or polling status
  - current betting broadcast
  - core bankroll metrics
  - line status for face, sum, and exact strategies
  - bankroll curve
  - bet history and broadcast history
- Optional primary vs. shadow strategy comparison.
- Read-only API lookup by draw date and draw code across the raw issue table plus bet and broadcast tables.

## Project Layout

```text
pk10_live_dashboard/
  backend/
    app/
      main.py       FastAPI routes
      auth.py       file-backed user store and session cookies
      db.py         MySQL connection helpers and runtime table setup
      runtime.py    polling, history sync, snapshot, persistence
      settings.py   environment configuration
      strategy.py   strategy simulation and decision logic
    requirements.txt
    .env.example
  frontend/
    src/
      App.jsx
      main.jsx
      styles.css
    package.json
    vite.config.js
  deploy/
    ecosystem.config.cjs
    pk10.nginx.conf
```

Runtime files are intentionally excluded from Git, including `backend/auth_users.json`, `backend/.venv/`, `frontend/node_modules/`, and `frontend/dist/`.

## Backend

Install dependencies:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create environment config from the example:

```bash
cp .env.example /root/pk10/.env
```

The PM2 config expects `/root/pk10/.env` and starts:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 18080
```

Important environment variables:

- `PK10_AUTH_STORE`: path for the JSON user store.
- `PK10_AUTH_SECRET`: session signing secret. Use a long random value in production.
- `PK10_ADMIN_USER`, `PK10_ADMIN_PASSWORD`, `PK10_ADMIN_DISPLAY_NAME`: bootstrap admin account used only when the user store does not exist.
- `PK10_DB_HOST`, `PK10_DB_PORT`, `PK10_DB_USER`, `PK10_DB_PASS`, `PK10_DB_NAME`, `PK10_DB_TABLE`: MySQL connection and raw issue table.
- `PK10_HISTORY_START_DATE`: earliest issue history to load.
- `PK10_REPLAY_START_DATE`: start date for simulated/live strategy bookkeeping.
- Strategy variables such as `PK10_FACE_POLICY_ID`, `PK10_SUM_CANDIDATE_ID`, `PK10_EXACT_BASE_GATE_ID`, and compare strategy flags.

## Frontend

Install and build:

```bash
cd frontend
npm install
npm run build
```

The production build output is `frontend/dist/`. In production, sync that directory to the nginx root, usually:

```bash
/var/www/pk10-live
```

For local frontend development:

```bash
npm run dev
```

The production API path is same-origin. nginx proxies `/api/` and `/events/stream` to the backend.

## Production Deployment

The included deployment files assume:

- app path: `/root/pk10/pk10_live_dashboard`
- backend process: `pk10-live-dashboard`
- backend listen address: `127.0.0.1:18080`
- frontend nginx root: `/var/www/pk10-live`
- public port: `5173`

Start or restart the backend:

```bash
pm2 start deploy/ecosystem.config.cjs
pm2 restart pk10-live-dashboard --update-env
```

Publish frontend assets:

```bash
npm run build
rsync -a --delete frontend/dist/ /var/www/pk10-live/
```

Health check:

```bash
curl http://127.0.0.1:18080/api/health
```

Public check:

```bash
curl http://<host>:5173/
```

## API Authentication

Most API routes require an application session cookie.

Login:

```bash
curl -c cookie.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<password>"}' \
  http://<host>:5173/api/auth/login
```

Use the cookie for authenticated calls:

```bash
curl -b cookie.txt http://<host>:5173/api/dashboard
```

Logout:

```bash
curl -b cookie.txt -X POST http://<host>:5173/api/auth/logout
```

## API Reference

### `GET /api/health`

Returns backend status and current issue metadata. This endpoint is intended for basic service checks.

Example:

```json
{
  "status": "ok",
  "generated_at": "2026-04-27T03:10:35.875021+00:00",
  "pre_draw_issue": 33992681
}
```

### `GET /api/dashboard`

Requires login. Returns the current dashboard snapshot used by the frontend, including market metadata, strategy profiles, current actions, daily curve, and totals.

### `GET /api/history/bets`

Requires login. Returns paginated bet history from `pk10_bet_log`.

Query parameters:

- `page`: page number, default `1`.
- `page_size`: page size, clamped to `10..200`, default `40`.
- `scope`: one of `all`, `broadcasted`, or `pending_future`.

Example:

```bash
curl -b cookie.txt 'http://<host>:5173/api/history/bets?page=1&page_size=40&scope=all'
```

### `GET /api/history/broadcasts`

Requires login. Returns paginated broadcast history from `pk10_broadcast_log`.

Query parameters:

- `page`: page number, default `1`.
- `page_size`: page size, clamped to `10..200`, default `40`.
- `issue`: optional issue number. When supplied, matches either `pre_draw_issue` or `draw_issue`.

Example:

```bash
curl -b cookie.txt 'http://<host>:5173/api/history/broadcasts?issue=33992130'
```

### `GET /api/history/by-code`

Requires login. Looks up one draw by date and draw code, then returns related records from the two strategy tables:

- `pk10_bet_log`
- `pk10_broadcast_log`

The endpoint first searches the raw issue table configured by `PK10_DB_TABLE` using:

- `draw_date = date`
- `pre_draw_code = code`

It then uses the matched `pre_draw_issue` values to fetch:

- bets where `pk10_bet_log.pre_draw_issue` matches
- broadcasts where `pk10_broadcast_log.pre_draw_issue` or `pk10_broadcast_log.draw_issue` matches

Query parameters:

- `date`: required, format `YYYY-MM-DD`.
- `code`: required, exact raw draw code string, for example `04,10,09,06,03,07,08,02,01,05`.

Example request:

```bash
curl -b cookie.txt --get \
  --data-urlencode 'date=2026-04-26' \
  --data-urlencode 'code=04,10,09,06,03,07,08,02,01,05' \
  http://<host>:5173/api/history/by-code
```

Example response:

```json
{
  "date": "2026-04-26",
  "code": "04,10,09,06,03,07,08,02,01,05",
  "issues": [
    {
      "draw_date": "2026-04-26",
      "pre_draw_issue": 33992130,
      "pre_draw_time": "2026-04-26 23:41:48",
      "pre_draw_code": "04,10,09,06,03,07,08,02,01,05",
      "sum_fs": 14,
      "sum_big_small": 0,
      "sum_single_double": 1,
      "first_dt": 1,
      "second_dt": 0,
      "third_dt": 0,
      "fourth_dt": 1,
      "fifth_dt": 1,
      "group_code": 1
    }
  ],
  "bets": [
    {
      "id": 2983672,
      "draw_date": "2026-04-26",
      "pre_draw_issue": 33992130,
      "slot_1based": 1129,
      "line_name": "sum",
      "status": "executed",
      "selection_json": {
        "sum_value": 13
      },
      "total_cost": "10.00",
      "pnl": "-10.0000"
    }
  ],
  "broadcasts": [
    {
      "id": 1132118,
      "server_time": "2026-04-26 23:40:33",
      "draw_date": "2026-04-26",
      "pre_draw_issue": 33992129,
      "draw_issue": 33992130,
      "line_name": "sum",
      "actionable": 1,
      "payload_json": {
        "status": "executed",
        "selection": {
          "sum_value": 13
        }
      }
    }
  ],
  "counts": {
    "issues": 1,
    "bets": 1,
    "broadcasts": 1
  }
}
```

If no issue matches the supplied date and code, the endpoint returns empty arrays and zero counts.

## Admin API

Admin-only endpoints require a logged-in user with role `admin`.

- `GET /api/admin/users`
- `POST /api/admin/users`
- `PATCH /api/admin/users/{user_id}`
- `DELETE /api/admin/users/{user_id}`
- `GET /api/admin/login-events`

These endpoints back the user management screen in the frontend.

## Development Notes

- Keep backend API changes backward compatible with the React frontend.
- Do not commit runtime state or secrets.
- After changing backend code, restart `pk10-live-dashboard`.
- After changing frontend code, run `npm run build` and publish `frontend/dist/`.
- After every completed change, commit and push to `main`.
