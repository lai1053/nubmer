# JSFT PK10 Shadow

Small forward-shadow service for the JSFT V4.1 core window.

## What It Runs

- Frozen window: `jsft_sum12_cap15__gate_g13_26_pos__daily85`
- Base window: `sum12_cap15`
- Gate: `g13_26_pos`
- Code: `jsft`
- Play: 冠亚和
- Bet value: `sum=12`
- Daily cap: `15`
- Settlement: `daily_85` (negative days settle at 0.85x)
- Deployment level: `core_shadow` (forward shadow only, NOT champion)
- Champion ready: `false` (requires 13 complete live-shadow days with gate active)

## API List

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | None | HTML dashboard |
| GET | `/api/health` | None | Health check with frozen window info |
| GET | `/api/frozen-windows` | None | List all registered frozen windows |
| GET | `/api/state` | Token* | Full state snapshot |
| GET | `/api/replay` | Token* | Account replay with bankroll constraint flag |
| GET | `/api/data-quality` | Token* | Last 120 days data quality table |
| GET | `/api/leakage-check` | Token* | Pre-day decision leakage audit |
| GET | `/api/shadow-log` | Token* | Read live shadow log |
| POST | `/api/shadow-log` | Token* | Append shadow log entry (manual) |
| GET | `/api/shadow/status` | Token* | Live shadow 13-day aggregation |
| POST | `/api/shadow/settle-latest-complete-day` | Token* | Auto-settle latest complete day |

*If `JSFT_SHADOW_API_TOKEN` is set, all non-`/api/health` and non-`/api/frozen-windows` endpoints require `Authorization: Bearer <token>`. If empty, all APIs are open.

## Live Shadow 13-Day Rule

- At least 13 complete shadow-log days required before `core_shadow_pass_candidate` can become `true`
- Even if pass, `champion_ready` remains `false` — champion requires manual review
- Live shadow status is visible at `GET /api/shadow/status`
