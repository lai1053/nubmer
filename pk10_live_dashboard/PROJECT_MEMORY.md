# Project Memory

This file is the handoff memory for future Codex threads working on this project.

## Current Project

- Project name: PK10 Live Dashboard
- Local workspace path: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard`
- Remote app host alias: `sscm_red_book_activity`
- Remote app path: `/root/pk10/pk10_live_dashboard`
- Remote Git working copy: `/root/pk10/nubmer`
- GitHub repository: `git@github.com:lai1053/nubmer.git`
- GitHub project subdirectory: `pk10_live_dashboard/`
- Public URL: `http://8.148.182.237:5173/`
- Backend process name: `pk10-live-dashboard`
- Backend local port: `127.0.0.1:18080`
- nginx static root: `/var/www/pk10-live`

## Git Rules

The user explicitly asked that every completed code or doc change must be committed and pushed.

Remote Git commands should run from:

```bash
cd /root/pk10/nubmer
```

Use this SSH key for GitHub:

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_sscm -o IdentitiesOnly=yes -o BatchMode=yes"
```

Typical commit flow:

```bash
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_sscm -o IdentitiesOnly=yes -o BatchMode=yes"
cd /root/pk10/nubmer
git status --short
git add pk10_live_dashboard/<changed-files>
git commit -m "<message>"
git push origin main
git rev-parse --short HEAD
git status --short
```

Do not commit runtime state or secrets:

- `backend/auth_users.json`
- `backend/.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `.env`
- local database files

## Deployment

Backend code deploy:

```bash
rsync -az --exclude 'frontend/node_modules/' --exclude 'frontend/dist/' --exclude 'backend/.venv/' --exclude 'backend/auth_users.json' \
  pk10_live_dashboard/ sscm_red_book_activity:/root/pk10/pk10_live_dashboard/

ssh sscm_red_book_activity 'pm2 restart pk10-live-dashboard --update-env'
```

Frontend deploy:

```bash
cd pk10_live_dashboard/frontend
npm run build
rsync -az --delete dist/ sscm_red_book_activity:/var/www/pk10-live/
```

The user previously requested no local 5173 dev server should be left running. Check with:

```bash
lsof -iTCP:5173 -sTCP:LISTEN -nP || true
```

Health checks:

```bash
curl http://8.148.182.237:5173/api/health
curl http://8.148.182.237:5173/
```

## Authentication

The app uses application-level login with cookie sessions.

- Login route: `POST /api/auth/login`
- Current user route: `GET /api/auth/me`
- Logout route: `POST /api/auth/logout`
- Admin-only user management routes are under `/api/admin/*`.

Do not write real production passwords into docs or commits.

## Current Backend APIs

All routes below require login unless noted.

- `GET /api/health`: unauthenticated health check.
- `GET /api/dashboard`: live dashboard snapshot.
- `GET /api/curve/daily?start_date=YYYY-MM-DD`: daily curve.
- `GET /api/history/bets?page=1&page_size=40&scope=all`: bet history from `pk10_bet_log`.
- `GET /api/history/broadcasts?page=1&page_size=40&issue=33992130`: broadcast history from `pk10_broadcast_log`.
- `GET /api/history/by-code?date=YYYY-MM-DD&code=04,10,...`: lookup raw issue by exact draw code, then return related `bets` and `broadcasts`.
- `GET /api/history/issues?date=YYYY-MM-DD&code=jssc`: return all raw records for that date from `pks_history`.
- `GET /api/history/issues?date=YYYY-MM-DD&code=jsft`: return all raw records for that date from `jsft_pks_history`.

Current mapping for `/api/history/issues`:

- `jssc` -> `pks_history`
- `jsft` -> `jsft_pks_history`

At the time this memory was written, remote MySQL had `pks_history`, but `jsft_pks_history` did not exist yet. The `jsft` route returns `404` with a clear message until that table is created.

Verified examples:

- `/api/history/issues?date=2026-04-26&code=jssc` returned `1143` rows.
- `/api/history/by-code?date=2026-04-26&code=04,10,09,06,03,07,08,02,01,05` returned `issues=1`, `bets=1`, `broadcasts=1`.

## Database Tables

Configured raw history table:

- `settings.db_table`, currently `pks_history`

Runtime and strategy tables:

- `pk10_runtime_state`
- `pk10_broadcast_log`
- `pk10_bet_log`
- `pk10_daily_equity`

Raw issue fields used by APIs:

- `id`
- `draw_date`
- `pre_draw_time`
- `pre_draw_issue`
- `pre_draw_code`
- `sum_fs`
- `sum_big_small`
- `sum_single_double`
- `first_dt`
- `second_dt`
- `third_dt`
- `fourth_dt`
- `fifth_dt`
- `group_code`
- `raw_json`
- `created_at`

## Frontend State

The frontend has already been redesigned as a mobile-first operations console.

Current mobile order:

1. sticky session bar
2. compact live header
3. current betting broadcast
4. three core bankroll metrics
5. three line status panels
6. bankroll curve
7. history cards

On mobile, shadow/compare strategy is collapsed into a compare section. Desktop still shows strategies side-by-side.

Admin pages were also made mobile friendly. Login timestamps are displayed in Beijing time.

## Recently Completed Commits

- `c6f0124` Add PK10 live dashboard app
- `11243d8` Add history lookup by date and code
- `b56514e` Rewrite PK10 dashboard README
- `e4ae62a` Add issue history lookup endpoint

Future threads should run `git log --oneline -5` on the remote Git working copy to get the latest actual state.
