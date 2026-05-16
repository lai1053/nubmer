# JSFT PK10 Shadow

Small forward-shadow service for the JSFT V4.1 core window.

## What It Runs

- Window: `sum12_cap15`
- Code: `jsft`
- Play: 冠亚和
- Bet value: `sum=12`
- Daily cap: `15`
- Deployment level: forward shadow only, not champion

The service intentionally does not run the JSSC production runtime. It only reads
`jsft_pks_history`, checks data quality, and publishes the next active slots.

## Start

```bash
cd /root/jsft_pk10
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
pm2 start ecosystem.config.cjs
```

Open:

```text
http://<host>:5174/
```

The public port is handled by nginx on `5174`; the FastAPI backend listens on
`127.0.0.1:18084`.

## Data Requirement

The MySQL table must exist:

```text
xyft_lottery_data.jsft_pks_history
```

Expected columns follow the live dashboard history schema:

- `draw_date`
- `pre_draw_time`
- `pre_draw_issue`
- `pre_draw_code`
- `sum_fs`

If the table is missing, the service stays online but reports `missing_table`.
