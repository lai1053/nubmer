# PK10 Number Sum Intraday Gate Report

- Settlement basis: `day` with negative-side factor `0.85`.
- Intraday scope: same-day preview on the first `cut` issues, then only trade tail slots `>= cut`.
- Odds profile: `minus_one`.
- Search-time bootstrap reps are reduced to `400` to keep the intraday grid tractable.

## Best Tail Baseline
- `base_nsum_00072 / cut=192` test `0.9224` / CI low `0.0688`, recent30 CI low `-2.6061`, recent60 CI low `-1.5681`.

## Best Gated Candidate
- `intraday_0396` = `base_nsum_00072 / cut=576 / high_mid / raw_high>=0.08 / mean_sum>=0.00 / mid_share>=0.50 / mean_cap<=0.93`.
- test `0.0401` / CI low `0.0000`, recent30 `0.0000` / CI low `0.0000`, recent60 CI low `0.0000`, post-2026-01-12 CI low `0.0000`.
- exposure reduction `99.85%`, delta vs ungated tail test CI `0.0488`, delta recent30 CI `2.5135`, acceptance count `0`.