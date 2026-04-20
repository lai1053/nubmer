# PK10 Round37 No-6-to-7 Replay

Replay the current confirmed robust daily deployment window on
`xyft_lottery_data.pks_history` from `2025-01-01` to `2026-01-01`,
with an added trading constraint:

- exclude all issues from `06:00:00` (inclusive) to `07:00:00` (exclusive)

The replay uses:

- initial bankroll `1000`
- stake per bet `10`
- daily martingale `1x -> 2x -> 4x -> 5x`
- current robust deployment policy from round35
