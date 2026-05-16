# Architecture

This repository contains two active PK10-related services and one historical archive.

## Runtime Map

```text
client
  |
  | http://host:5173
  v
nginx :5173
  |-- static files from /var/www/pk10-live
  |-- /api/* and /events/stream -> 127.0.0.1:18080
                                      |
                                      v
                                  pk10-live-dashboard
                                  FastAPI + MySQL

client
  |
  | http://host:5174
  v
nginx :5174
  |
  v
127.0.0.1:18084
  |
  v
jsft-pk10-shadow
FastAPI + MySQL
```

## 5173 Live Dashboard

Source path in the repository:

```text
pk10_live_dashboard/
```

Default production runtime path:

```text
/root/pk10/pk10_live_dashboard
```

Main responsibilities:

- login and cookie sessions
- user management and login records
- live PK10 dashboard snapshots
- current betting broadcasts
- bet history and broadcast history
- raw issue lookup APIs
- SSE stream for frontend updates

Important runtime files:

- `/root/pk10/.env`: process environment loaded by PM2
- `/root/pk10/pk10_live_dashboard/backend/auth_users.json`: file-backed app users
- `/var/www/pk10-live`: built frontend assets served by nginx

## 5174 JSFT Shadow Service

Source path in the repository:

```text
jsft_pk10/
```

Default production runtime path:

```text
/root/jsft_pk10
```

Main responsibilities:

- read `xyft_lottery_data.jsft_pks_history`
- expose JSFT shadow dashboard pages and APIs
- run the JSFT history updater script
- keep JSFT research/shadow behavior separate from the 5173 JSSC live loop
- publish frozen window status, data quality, and live shadow metrics

5173 can view 5174 status via proxy APIs (`/api/jsft-shadow/*`) but 5174 does not participate in the 5173 JSSC live runtime loop.

### 5173/5174 Integration

- 5173 backend proxies JSFT shadow state through `/api/jsft-shadow/state`, `/api/jsft-shadow/replay`, `/api/jsft-shadow/data-quality`, `/api/jsft-shadow/shadow-status`
- These proxy APIs require 5173 login (same cookie auth as other dashboard APIs)
- If `PK10_JSFT_SHADOW_TOKEN` is set, the proxy passes an `Authorization: Bearer` header to 5174
- 5173 frontend displays a standalone JSFT Shadow panel (not mixed into JSSC bankroll curve)
- 5174 remains independently accessible on port 5174

Important runtime files:

- `/root/jsft_pk10/.env`: process environment loaded by PM2
- `/root/jsft_pk10/data/`: local replay outputs, shadow log, and updater state

## Database Tables

Current known table routing:

| Code | Raw issue table |
| --- | --- |
| `jssc` | `pks_history` |
| `jsft` | `jsft_pks_history` |

5173 also creates and reads its own runtime log tables for bets and broadcasts. The raw history API routes live in `pk10_live_dashboard/backend/app/main.py`.

## Deployment Boundary

The repository is the source of truth. Runtime directories on the server are deployment targets. Deploy scripts sync source from the cloned repository into the runtime directories, then restart PM2 and reload nginx.
