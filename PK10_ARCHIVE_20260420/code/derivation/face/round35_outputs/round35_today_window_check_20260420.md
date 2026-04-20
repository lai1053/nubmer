# Round35 Today Window Check 2026-04-20

- Database used: `xyft_lottery_data.pks_history`
- Latest complete date available at check time: `2026-04-19`
- Decision date inferred: `2026-04-20`
- Policy: `core40_spread_only__exp0_off__oe40_spread_only__cd2`

## Result
- `mode_today = core_plus_oe`
- `policy_bets_today = 0.0` in the placeholder row because no realized `2026-04-20` issues were loaded yet; this should be read as a mode decision, not as an executed-bet count.
- `prev_mode = cash`
- `prev_real = 0.0`
- `core_gate_today = True`
- `oe_gate_today = True`

## Trailing 40-Day Context
- `core_40d_mean_ledger = 1.14675`
- `core_40d_mean_spread = 0.0216667`
- `oe_40d_mean_ledger = 0.149375`
- `oe_40d_mean_spread = 0.00625`

## Interpretation
- Under the frozen round35 robust deployment logic, `2026-04-20` is still an active window day.
- Because `expansion` is permanently off in this policy, the actionable mode is `core + oe`.
- The previous day was `cash`, so there is no cooldown carry-over blocking today's activation.
