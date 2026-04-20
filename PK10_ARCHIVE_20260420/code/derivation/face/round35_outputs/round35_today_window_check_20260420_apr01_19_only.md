# Round35 Today Window Check 2026-04-20 Using Only 2026-04-01 To 2026-04-19

- Policy: `core40_spread_only__exp0_off__oe40_spread_only__cd2`
- Data source: `xyft_lottery_data.pks_history`
- Historical slice used for inference: only `2026-04-01` to `2026-04-19`

## Result
- `rows = 15`
- `history_days = 14`
- `core_gate_today = False`
- `oe_gate_today = False`

## Why
- The frozen round35 gate requires a full `40`-day trailing window.
- When the source is restricted to `2026-04-01` to `2026-04-19`, the preprocessing keeps only complete natural weeks, so only `14` historical days remain usable before the `2026-04-20` placeholder row.
- Because the `40`-day rolling window is not satisfied, both gates stay off.

## Interpretation
- If you insist on inferring `2026-04-20` only from `2026-04-01` to `2026-04-19`, then `2026-04-20` is **not** a window day under the frozen round35 logic.
- If you use the full historical context up to `2026-04-19`, then `2026-04-20` is still an active `core_plus_oe` day.
