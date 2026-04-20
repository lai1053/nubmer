# PK10 Number Sum Intraday Gate Report

- Settlement basis: `day` with negative-side factor `0.85`.
- Intraday scope: same-day preview on the first `cut` issues, then only trade tail slots `>= cut`.
- Search-time bootstrap reps are reduced to `400` to keep the intraday grid tractable.

## Best Tail Baseline
- `base_nsum_00072 / cut=192` test `1.2077` / CI low `0.2727`, recent30 CI low `-2.5482`, recent60 CI low `-0.4848`.

## Best Gated Candidate
- `intraday_1007` = `base_stable_020 / cut=192 / high_mid / raw_high>=0.02 / mean_sum>=0.00 / mid_share>=0.46 / mean_cap<=0.96`.
- test `0.5227` / CI low `0.2182`, recent30 `1.9283` / CI low `0.1380`, recent60 CI low `0.0533`, post-2026-01-12 CI low `0.5409`.
- exposure reduction `67.68%`, delta vs ungated tail test CI `0.0067`, delta recent30 CI `0.2516`, acceptance count `4`.