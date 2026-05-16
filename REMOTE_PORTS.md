# Remote Port Inventory

This file records the currently deployed services on `sscm_red_book_activity`
for planning and review.

## Port 5173

- Public URL: `http://8.148.182.237:5173/`
- nginx config: `/etc/nginx/sites-enabled/pk10-live.conf`
- Static root: `/var/www/pk10-live`
- Backend PM2 app: `pk10-live-dashboard`
- Backend bind: `127.0.0.1:18080`
- Running source: `/root/pk10/pk10_live_dashboard`
- Repository path: `pk10_live_dashboard/`

## Port 5174

- Public URL: `http://8.148.182.237:5174/`
- nginx config: `/etc/nginx/sites-enabled/jsft-pk10-shadow.conf`
- Backend PM2 app: `jsft-pk10-shadow`
- Backend bind: `127.0.0.1:18084`
- Running source: `/root/jsft_pk10`
- Repository path: `jsft_pk10/`

## Commit Hygiene

- Do not commit real `.env` files, environment backups, virtualenvs, logs, or
  runtime account/user state.
- Commit source code, README files, example environment files, nginx templates,
  PM2 ecosystem files, and small review artifacts only.
