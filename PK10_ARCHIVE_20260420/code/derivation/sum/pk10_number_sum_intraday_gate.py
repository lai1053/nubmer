#!/usr/bin/env python3
"""
PK10 冠亚和 exact-sum 的第一版 intraday gate 探索。

目标：
1. 在日结算 85 折口径下，用当天前段 issue 的 raw 分布去决定当天后段是否开仓。
2. 只交易 preview cut 之后仍未过去的 tail slots，避免任何同日 hindsight。
3. 验证“日内 regime gate”是否比跨日前视 gate 更适合 1152 期/天的结构。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd


TRAIN_END = pd.Timestamp("2024-12-31")
TEST_START = pd.Timestamp("2025-01-01")
POST_WINDOW_START = pd.Timestamp("2026-01-12")
RECENT_DAY_WINDOWS = (30, 60, 120)
PREVIEW_CUTS = (192, 288, 384, 576)
INTRADAY_BOOTSTRAP_REPS = 400
ODDS_PROFILES = ("default_net", "minus_one")


@dataclass(frozen=True)
class BaselineConfig:
    name: str
    lookback_weeks: int
    prior_strength: int
    score_mode: str
    daily_issue_cap: int
    allowed_sums: Tuple[int, ...]
    slot_blacklist: Tuple[int, ...]


@dataclass(frozen=True)
class GateConfig:
    gate_family: str
    raw_high_threshold: float
    mean_sum_threshold: float
    mid_share_threshold: float
    mean_edge_cap: float


def import_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def apply_odds_profile(vmod, odds_profile: str) -> np.ndarray:
    base = np.asarray(vmod.NET_ODDS, dtype=float)
    if odds_profile == "default_net":
        adjusted = base.copy()
    elif odds_profile == "minus_one":
        adjusted = base - 1.0
    else:
        raise ValueError(f"Unknown odds_profile: {odds_profile}")
    vmod.NET_ODDS = adjusted
    return adjusted


def baseline_configs() -> List[BaselineConfig]:
    return [
        BaselineConfig(
            name="base_nsum_00072",
            lookback_weeks=39,
            prior_strength=20,
            score_mode="lcb164",
            daily_issue_cap=8,
            allowed_sums=tuple(range(3, 20)),
            slot_blacklist=(),
        ),
        BaselineConfig(
            name="base_nsum_00120",
            lookback_weeks=39,
            prior_strength=120,
            score_mode="lcb164",
            daily_issue_cap=8,
            allowed_sums=tuple(range(3, 20)),
            slot_blacklist=(),
        ),
        BaselineConfig(
            name="base_stable_020",
            lookback_weeks=39,
            prior_strength=120,
            score_mode="lcb2",
            daily_issue_cap=4,
            allowed_sums=(9, 10, 11, 12, 13),
            slot_blacklist=(919, 7),
        ),
        BaselineConfig(
            name="base_stable_008",
            lookback_weeks=39,
            prior_strength=80,
            score_mode="lcb2",
            daily_issue_cap=4,
            allowed_sums=(9, 10, 11, 12, 13),
            slot_blacklist=(919, 7),
        ),
    ]


def gate_grid() -> List[GateConfig]:
    configs: List[GateConfig] = []
    for mean_edge_cap in (0.93, 0.96, 1.00):
        for raw_high_threshold in (0.02, 0.04, 0.06, 0.08):
            configs.append(
                GateConfig(
                    gate_family="high_only",
                    raw_high_threshold=raw_high_threshold,
                    mean_sum_threshold=0.0,
                    mid_share_threshold=0.0,
                    mean_edge_cap=mean_edge_cap,
                )
            )
            for mean_sum_threshold in (11.00, 11.05, 11.10, 11.15):
                configs.append(
                    GateConfig(
                        gate_family="high_mean",
                        raw_high_threshold=raw_high_threshold,
                        mean_sum_threshold=mean_sum_threshold,
                        mid_share_threshold=0.0,
                        mean_edge_cap=mean_edge_cap,
                    )
                )
            for mid_share_threshold in (0.44, 0.46, 0.48, 0.50):
                configs.append(
                    GateConfig(
                        gate_family="high_mid",
                        raw_high_threshold=raw_high_threshold,
                        mean_sum_threshold=0.0,
                        mid_share_threshold=mid_share_threshold,
                        mean_edge_cap=mean_edge_cap,
                    )
                )
        for mid_share_threshold in (0.44, 0.46, 0.48, 0.50):
            configs.append(
                GateConfig(
                    gate_family="mid_only",
                    raw_high_threshold=0.0,
                    mean_sum_threshold=0.0,
                    mid_share_threshold=mid_share_threshold,
                    mean_edge_cap=mean_edge_cap,
                )
            )
    return configs


def day_dates_from_bundle(bundle) -> pd.DatetimeIndex:
    week_start = pd.to_datetime(bundle.week_start)
    day_dates = [
        week_start[week_idx] + pd.Timedelta(days=day_offset)
        for week_idx in range(len(week_start))
        for day_offset in range(bundle.sum_cube.shape[1])
    ]
    return pd.DatetimeIndex(day_dates)


def recent_day_mask(base_mask: np.ndarray, window: int) -> np.ndarray:
    idx = np.flatnonzero(base_mask)
    out = np.zeros_like(base_mask, dtype=bool)
    if idx.size == 0:
        return out
    selected = idx[-window:] if idx.size >= window else idx
    out[selected] = True
    return out


def daily_split_metrics(vmod, series: Dict[str, np.ndarray], mask: np.ndarray, seed_offset: int) -> Dict[str, float]:
    idx = np.flatnonzero(mask & ~np.isnan(series["real"]))
    if idx.size == 0:
        return {
            "avg_daily_real_pnl": float("nan"),
            "bootstrap_ci_low_real": float("nan"),
            "bootstrap_ci_high_real": float("nan"),
            "positive_day_rate": float("nan"),
            "avg_bets_per_day": float("nan"),
            "avg_selected_score": float("nan"),
            "avg_selected_mean_edge": float("nan"),
            "avg_selected_symmetry_gap": float("nan"),
            "avg_preview_raw_high_bias": float("nan"),
            "avg_preview_mid_share": float("nan"),
            "avg_preview_mean_sum": float("nan"),
            "n_days": 0.0,
        }
    split_values = series["real"][idx]
    ci_low, ci_high = vmod.bootstrap_mean_ci(
        split_values,
        seed=vmod.GLOBAL_SEED + seed_offset,
        n_boot=INTRADAY_BOOTSTRAP_REPS,
    )
    return {
        "avg_daily_real_pnl": float(np.mean(split_values)),
        "bootstrap_ci_low_real": ci_low,
        "bootstrap_ci_high_real": ci_high,
        "positive_day_rate": float(np.mean(split_values > 0.0)),
        "avg_bets_per_day": float(np.mean(series["issues"][idx])),
        "avg_selected_score": float(np.mean(series["selected_score"][idx])),
        "avg_selected_mean_edge": float(np.mean(series["selected_mean_edge"][idx])),
        "avg_selected_symmetry_gap": float(np.mean(series["selected_symmetry_gap"][idx])),
        "avg_preview_raw_high_bias": float(np.mean(series["preview_raw_high_bias"][idx])),
        "avg_preview_mid_share": float(np.mean(series["preview_mid_share"][idx])),
        "avg_preview_mean_sum": float(np.mean(series["preview_mean_sum"][idx])),
        "n_days": float(idx.size),
    }


def total_bets(series: Dict[str, np.ndarray], mask: np.ndarray) -> float:
    idx = np.flatnonzero(mask & ~np.isnan(series["issues"]))
    if idx.size == 0:
        return 0.0
    return float(np.sum(series["issues"][idx]))


def apply_day_mask(series: Dict[str, np.ndarray], active_days: np.ndarray) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    for key, values in series.items():
        kept = values.astype(np.float64).copy()
        valid = ~np.isnan(kept)
        kept[valid & ~active_days] = 0.0
        out[key] = kept
    return out


def build_intraday_base_series(
    vmod,
    rmod,
    bundle,
    baseline: BaselineConfig,
    preview_cut: int,
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    signal_state = rmod.build_full_signal_state(
        vmod=vmod,
        bundle=bundle,
        lookback_weeks=baseline.lookback_weeks,
        prior_strength=baseline.prior_strength,
        score_mode=baseline.score_mode,
    )
    choice_state = rmod.build_choice_state(vmod, signal_state, baseline.allowed_sums)

    n_weeks, n_days_per_week, _ = bundle.sum_cube.shape
    n_days = n_weeks * n_days_per_week
    day_dates = day_dates_from_bundle(bundle)

    ledger = np.full(n_days, np.nan, dtype=np.float64)
    real = np.full(n_days, np.nan, dtype=np.float64)
    issues = np.full(n_days, np.nan, dtype=np.float64)
    selected_score = np.full(n_days, np.nan, dtype=np.float64)
    selected_mean_edge = np.full(n_days, np.nan, dtype=np.float64)
    selected_symmetry_gap = np.full(n_days, np.nan, dtype=np.float64)
    preview_raw_high_bias = np.full(n_days, np.nan, dtype=np.float64)
    preview_mid_share = np.full(n_days, np.nan, dtype=np.float64)
    preview_mean_sum = np.full(n_days, np.nan, dtype=np.float64)

    detail_rows: List[Dict[str, object]] = []
    blocked_slots = set(int(slot) for slot in baseline.slot_blacklist)

    for week_idx in range(baseline.lookback_weeks, n_weeks):
        week_score = choice_state.score[week_idx].astype(np.float64)
        order = np.argsort(-week_score, kind="stable")
        selected_slots = [
            int(slot)
            for slot in order
            if slot not in blocked_slots and week_score[slot] > 0.0
        ][: baseline.daily_issue_cap]

        for day_offset in range(n_days_per_week):
            flat_idx = week_idx * n_days_per_week + day_offset
            day_date = day_dates[flat_idx]
            day_sum_idx = bundle.sum_cube[week_idx, day_offset].astype(np.int16)
            day_sum_values = day_sum_idx + 3
            preview_values = day_sum_values[:preview_cut]
            preview_raw_high_bias[flat_idx] = float(np.mean(preview_values > 11) - np.mean(preview_values < 11))
            preview_mid_share[flat_idx] = float(np.mean((preview_values >= 9) & (preview_values <= 13)))
            preview_mean_sum[flat_idx] = float(np.mean(preview_values))

            tradable_slots = [slot for slot in selected_slots if slot >= preview_cut]
            if not tradable_slots:
                ledger[flat_idx] = 0.0
                real[flat_idx] = 0.0
                issues[flat_idx] = 0.0
                selected_score[flat_idx] = 0.0
                selected_mean_edge[flat_idx] = 0.0
                selected_symmetry_gap[flat_idx] = 0.0
                continue

            daily_book = 0.0
            for slot in tradable_slots:
                sum_index = int(choice_state.sum_idx[week_idx, slot])
                hit = int(bundle.sum_cube[week_idx, day_offset, slot] == sum_index)
                book_pnl = float(vmod.NET_ODDS[sum_index] if hit else -1.0)
                daily_book += book_pnl
                detail_rows.append(
                    {
                        "baseline_name": baseline.name,
                        "preview_cut": int(preview_cut),
                        "date": str(day_date.date()),
                        "week_start": str(pd.Timestamp(bundle.week_start[week_idx]).date()),
                        "split": (
                            "train"
                            if day_date <= TRAIN_END
                            else ("test" if day_date >= TEST_START else "other")
                        ),
                        "slot": slot,
                        "sum_value": int(vmod.INDEX_TO_SUM[sum_index]),
                        "score_value": float(choice_state.score[week_idx, slot]),
                        "mean_edge_value": float(choice_state.mean_edge[week_idx, slot]),
                        "symmetry_gap_value": float(choice_state.symmetry_gap[week_idx, slot]),
                        "preview_raw_high_bias": preview_raw_high_bias[flat_idx],
                        "preview_mid_share": preview_mid_share[flat_idx],
                        "preview_mean_sum": preview_mean_sum[flat_idx],
                        "book_pnl": book_pnl,
                        "real_pnl": float(vmod.settle_real(book_pnl)),
                        "hit": hit,
                    }
                )

            ledger[flat_idx] = daily_book
            real[flat_idx] = vmod.settle_real(daily_book)
            issues[flat_idx] = float(len(tradable_slots))
            selected_score[flat_idx] = float(np.mean(choice_state.score[week_idx, tradable_slots]))
            selected_mean_edge[flat_idx] = float(np.mean(choice_state.mean_edge[week_idx, tradable_slots]))
            selected_symmetry_gap[flat_idx] = float(np.mean(choice_state.symmetry_gap[week_idx, tradable_slots]))

    detail_df = pd.DataFrame(detail_rows)
    return (
        {
            "ledger": ledger,
            "real": real,
            "issues": issues,
            "selected_score": selected_score,
            "selected_mean_edge": selected_mean_edge,
            "selected_symmetry_gap": selected_symmetry_gap,
            "preview_raw_high_bias": preview_raw_high_bias,
            "preview_mid_share": preview_mid_share,
            "preview_mean_sum": preview_mean_sum,
        },
        detail_df,
    )


def gate_flag(series: Dict[str, np.ndarray], day_idx: int, gate_config: GateConfig) -> bool:
    raw_high = float(series["preview_raw_high_bias"][day_idx])
    mid_share = float(series["preview_mid_share"][day_idx])
    mean_sum = float(series["preview_mean_sum"][day_idx])
    mean_edge = float(series["selected_mean_edge"][day_idx])
    issues = float(series["issues"][day_idx])

    if np.isnan(raw_high) or np.isnan(mid_share) or np.isnan(mean_sum) or np.isnan(mean_edge) or issues <= 0.0:
        return False
    if mean_edge > gate_config.mean_edge_cap:
        return False
    if gate_config.gate_family == "high_only":
        return raw_high >= gate_config.raw_high_threshold
    if gate_config.gate_family == "high_mean":
        return raw_high >= gate_config.raw_high_threshold and mean_sum >= gate_config.mean_sum_threshold
    if gate_config.gate_family == "high_mid":
        return raw_high >= gate_config.raw_high_threshold and mid_share >= gate_config.mid_share_threshold
    if gate_config.gate_family == "mid_only":
        return mid_share >= gate_config.mid_share_threshold
    raise ValueError(f"Unknown gate_family: {gate_config.gate_family}")


def build_report(best_tail_row: pd.Series, best_gate_row: pd.Series, acceptance_count: int, odds_profile: str) -> str:
    lines: List[str] = []
    lines.append("# PK10 Number Sum Intraday Gate Report")
    lines.append("")
    lines.append("- Settlement basis: `day` with negative-side factor `0.85`.")
    lines.append("- Intraday scope: same-day preview on the first `cut` issues, then only trade tail slots `>= cut`.")
    lines.append(f"- Odds profile: `{odds_profile}`.")
    lines.append("- Search-time bootstrap reps are reduced to `400` to keep the intraday grid tractable.")
    lines.append("")
    lines.append("## Best Tail Baseline")
    lines.append(
        f"- `{best_tail_row['baseline_name']} / cut={int(best_tail_row['preview_cut'])}` "
        f"test `{best_tail_row['avg_daily_real_pnl_test']:.4f}` / CI low `{best_tail_row['test_bootstrap_ci_low_real']:.4f}`, "
        f"recent30 CI low `{best_tail_row['recent30_bootstrap_ci_low_real']:.4f}`, "
        f"recent60 CI low `{best_tail_row['recent60_bootstrap_ci_low_real']:.4f}`."
    )
    lines.append("")
    lines.append("## Best Gated Candidate")
    lines.append(
        f"- `{best_gate_row['candidate_id']}` = `{best_gate_row['baseline_name']} / cut={int(best_gate_row['preview_cut'])} "
        f"/ {best_gate_row['gate_family']} / raw_high>={best_gate_row['raw_high_threshold']:.2f} "
        f"/ mean_sum>={best_gate_row['mean_sum_threshold']:.2f} / mid_share>={best_gate_row['mid_share_threshold']:.2f} "
        f"/ mean_cap<={best_gate_row['mean_edge_cap']:.2f}`."
    )
    lines.append(
        f"- test `{best_gate_row['avg_daily_real_pnl_test']:.4f}` / CI low `{best_gate_row['test_bootstrap_ci_low_real']:.4f}`, "
        f"recent30 `{best_gate_row['recent30_avg_daily_real_pnl']:.4f}` / CI low `{best_gate_row['recent30_bootstrap_ci_low_real']:.4f}`, "
        f"recent60 CI low `{best_gate_row['recent60_bootstrap_ci_low_real']:.4f}`, "
        f"post-2026-01-12 CI low `{best_gate_row['post_2026_01_12_bootstrap_ci_low_real']:.4f}`."
    )
    lines.append(
        f"- exposure reduction `{best_gate_row['test_exposure_reduction_pct']:.2%}`, "
        f"delta vs ungated tail test CI `{best_gate_row['delta_vs_tail_test_ci_low']:.4f}`, "
        f"delta recent30 CI `{best_gate_row['delta_vs_tail_recent30_ci_low']:.4f}`, "
        f"acceptance count `{acceptance_count}`."
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PK10 number sum intraday gate exploration")
    parser.add_argument("--date-start", default="2020-01-01")
    parser.add_argument("--date-end", default="2026-04-15")
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3307)
    parser.add_argument("--db-user", default="root")
    parser.add_argument("--db-pass", default="123456")
    parser.add_argument("--db-name", default="xyft_lottery_data")
    parser.add_argument("--table", default="pks_history")
    parser.add_argument("--odds-profile", choices=ODDS_PROFILES, default="default_net")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "number_sum_intraday_gate_outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    root = Path(__file__).resolve().parent
    vmod = import_module_from_path("pk10_number_sum_validation_for_intraday_gate", root / "pk10_number_sum_validation.py")
    rmod = import_module_from_path("pk10_number_sum_refinement_for_intraday_gate", root / "pk10_number_sum_refinement.py")
    adjusted_net_odds = apply_odds_profile(vmod, args.odds_profile)

    print("intraday_gate: loading issue history", flush=True)
    issue_df = vmod.load_issue_history_from_db(
        db_host=args.db_host,
        db_port=args.db_port,
        db_user=args.db_user,
        db_pass=args.db_pass,
        db_name=args.db_name,
        table=args.table,
        date_start=args.date_start,
        date_end=args.date_end,
    )

    print("intraday_gate: preprocessing complete weeks", flush=True)
    bundle = vmod.preprocess_exact_sum(issue_df)
    day_dates = day_dates_from_bundle(bundle)
    train_mask = day_dates <= TRAIN_END
    test_mask = day_dates >= TEST_START
    post_mask = day_dates >= POST_WINDOW_START

    pd.DataFrame(
        [
            {
                "source": f"mysql://{args.db_user}@{args.db_host}:{args.db_port}/{args.db_name}.{args.table}",
                "requested_date_start": args.date_start,
                "requested_date_end": args.date_end,
                "odds_profile": args.odds_profile,
                "net_odds_json": json.dumps([float(x) for x in adjusted_net_odds]),
                "sample_min_date": bundle.sample_min_date,
                "sample_max_date": bundle.sample_max_date,
                "complete_weeks": int(len(bundle.week_start)),
                "complete_days": int(len(day_dates)),
                "train_days": int(train_mask.sum()),
                "test_days": int(test_mask.sum()),
                "expected_per_day": int(bundle.expected_per_day),
            }
        ]
    ).to_csv(args.output_dir / "intraday_gate_data_summary.csv", index=False)

    tail_rows: List[Dict[str, object]] = []
    summary_rows: List[Dict[str, object]] = []
    daily_series_store: Dict[str, Dict[str, np.ndarray]] = {}
    active_store: Dict[str, np.ndarray] = {}

    candidate_counter = 0

    print("intraday_gate: building tail baselines", flush=True)
    for baseline in baseline_configs():
        for preview_cut in PREVIEW_CUTS:
            base_series, detail_df = build_intraday_base_series(vmod, rmod, bundle, baseline, preview_cut)
            detail_df.to_csv(
                args.output_dir / f"{baseline.name}_cut{preview_cut}_intraday_detail.csv",
                index=False,
            )

            train_metrics = daily_split_metrics(vmod, base_series, train_mask, 1000 + candidate_counter)
            test_metrics = daily_split_metrics(vmod, base_series, test_mask, 2000 + candidate_counter)
            recent_metrics = {
                window: daily_split_metrics(
                    vmod,
                    base_series,
                    recent_day_mask(test_mask, window),
                    3000 + 100 * window + candidate_counter,
                )
                for window in RECENT_DAY_WINDOWS
            }
            post_metrics = daily_split_metrics(vmod, base_series, post_mask, 4000 + candidate_counter)

            tail_rows.append(
                {
                    "baseline_name": baseline.name,
                    "preview_cut": int(preview_cut),
                    "lookback_weeks": baseline.lookback_weeks,
                    "prior_strength": baseline.prior_strength,
                    "score_mode": baseline.score_mode,
                    "daily_issue_cap": baseline.daily_issue_cap,
                    "allowed_sums_json": json.dumps(list(baseline.allowed_sums)),
                    "slot_blacklist_json": json.dumps(list(baseline.slot_blacklist)),
                    "avg_daily_real_pnl_test": test_metrics["avg_daily_real_pnl"],
                    "test_bootstrap_ci_low_real": test_metrics["bootstrap_ci_low_real"],
                    "recent30_bootstrap_ci_low_real": recent_metrics[30]["bootstrap_ci_low_real"],
                    "recent60_bootstrap_ci_low_real": recent_metrics[60]["bootstrap_ci_low_real"],
                    "recent120_bootstrap_ci_low_real": recent_metrics[120]["bootstrap_ci_low_real"],
                    "post_2026_01_12_bootstrap_ci_low_real": post_metrics["bootstrap_ci_low_real"],
                    "avg_bets_per_day_test": test_metrics["avg_bets_per_day"],
                }
            )

            ungated_test_total_bets = total_bets(base_series, test_mask)

            for gate_config in gate_grid():
                candidate_counter += 1
                candidate_id = f"intraday_{candidate_counter:04d}"
                active_days = np.array(
                    [gate_flag(base_series, day_idx, gate_config) for day_idx in range(len(day_dates))],
                    dtype=bool,
                )
                gated_series = apply_day_mask(base_series, active_days)
                daily_series_store[candidate_id] = gated_series
                active_store[candidate_id] = active_days

                train_metrics = daily_split_metrics(vmod, gated_series, train_mask, 5000 + candidate_counter)
                test_metrics = daily_split_metrics(vmod, gated_series, test_mask, 6000 + candidate_counter)
                recent_metrics = {
                    window: daily_split_metrics(
                        vmod,
                        gated_series,
                        recent_day_mask(test_mask, window),
                        7000 + 100 * window + candidate_counter,
                    )
                    for window in RECENT_DAY_WINDOWS
                }
                post_metrics = daily_split_metrics(vmod, gated_series, post_mask, 8000 + candidate_counter)

                test_total_bets = total_bets(gated_series, test_mask)
                exposure_reduction = (
                    0.0 if ungated_test_total_bets <= 0.0 else 1.0 - (test_total_bets / ungated_test_total_bets)
                )
                acceptance_met = (
                    test_metrics["bootstrap_ci_low_real"] > 0.0
                    and recent_metrics[30]["bootstrap_ci_low_real"] > 0.0
                    and recent_metrics[60]["bootstrap_ci_low_real"] > 0.0
                )

                summary_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "baseline_name": baseline.name,
                        "preview_cut": int(preview_cut),
                        "lookback_weeks": baseline.lookback_weeks,
                        "prior_strength": baseline.prior_strength,
                        "score_mode": baseline.score_mode,
                        "daily_issue_cap": baseline.daily_issue_cap,
                        "allowed_sums_json": json.dumps(list(baseline.allowed_sums)),
                        "slot_blacklist_json": json.dumps(list(baseline.slot_blacklist)),
                        "gate_family": gate_config.gate_family,
                        "raw_high_threshold": gate_config.raw_high_threshold,
                        "mean_sum_threshold": gate_config.mean_sum_threshold,
                        "mid_share_threshold": gate_config.mid_share_threshold,
                        "mean_edge_cap": gate_config.mean_edge_cap,
                        "avg_daily_real_pnl_train": train_metrics["avg_daily_real_pnl"],
                        "train_bootstrap_ci_low_real": train_metrics["bootstrap_ci_low_real"],
                        "avg_daily_real_pnl_test": test_metrics["avg_daily_real_pnl"],
                        "test_bootstrap_ci_low_real": test_metrics["bootstrap_ci_low_real"],
                        "test_positive_day_rate": test_metrics["positive_day_rate"],
                        "avg_bets_per_day_test": test_metrics["avg_bets_per_day"],
                        "recent30_avg_daily_real_pnl": recent_metrics[30]["avg_daily_real_pnl"],
                        "recent30_bootstrap_ci_low_real": recent_metrics[30]["bootstrap_ci_low_real"],
                        "recent60_avg_daily_real_pnl": recent_metrics[60]["avg_daily_real_pnl"],
                        "recent60_bootstrap_ci_low_real": recent_metrics[60]["bootstrap_ci_low_real"],
                        "recent120_avg_daily_real_pnl": recent_metrics[120]["avg_daily_real_pnl"],
                        "recent120_bootstrap_ci_low_real": recent_metrics[120]["bootstrap_ci_low_real"],
                        "post_2026_01_12_avg_daily_real_pnl": post_metrics["avg_daily_real_pnl"],
                        "post_2026_01_12_bootstrap_ci_low_real": post_metrics["bootstrap_ci_low_real"],
                        "test_exposure_reduction_pct": exposure_reduction,
                        "acceptance_met": acceptance_met,
                    }
                )

    print("intraday_gate: writing outputs", flush=True)
    tail_df = pd.DataFrame(tail_rows).sort_values(
        by=["test_bootstrap_ci_low_real", "recent30_bootstrap_ci_low_real", "recent60_bootstrap_ci_low_real"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    tail_df.to_csv(args.output_dir / "intraday_tail_baselines.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.merge(
        tail_df[
            [
                "baseline_name",
                "preview_cut",
                "test_bootstrap_ci_low_real",
                "recent30_bootstrap_ci_low_real",
                "recent60_bootstrap_ci_low_real",
            ]
        ].rename(
            columns={
                "test_bootstrap_ci_low_real": "tail_test_bootstrap_ci_low_real",
                "recent30_bootstrap_ci_low_real": "tail_recent30_bootstrap_ci_low_real",
                "recent60_bootstrap_ci_low_real": "tail_recent60_bootstrap_ci_low_real",
            }
        ),
        on=["baseline_name", "preview_cut"],
        how="left",
    )
    summary_df["delta_vs_tail_test_ci_low"] = (
        summary_df["test_bootstrap_ci_low_real"] - summary_df["tail_test_bootstrap_ci_low_real"]
    )
    summary_df["delta_vs_tail_recent30_ci_low"] = (
        summary_df["recent30_bootstrap_ci_low_real"] - summary_df["tail_recent30_bootstrap_ci_low_real"]
    )
    summary_df["delta_vs_tail_recent60_ci_low"] = (
        summary_df["recent60_bootstrap_ci_low_real"] - summary_df["tail_recent60_bootstrap_ci_low_real"]
    )
    summary_df = summary_df.sort_values(
        by=[
            "acceptance_met",
            "recent30_bootstrap_ci_low_real",
            "recent60_bootstrap_ci_low_real",
            "test_bootstrap_ci_low_real",
            "post_2026_01_12_bootstrap_ci_low_real",
            "avg_daily_real_pnl_test",
        ],
        ascending=[False, False, False, False, False, False],
    ).reset_index(drop=True)
    summary_df.to_csv(args.output_dir / "intraday_gate_summary.csv", index=False)

    acceptance_count = int(summary_df["acceptance_met"].fillna(False).astype(bool).sum())
    pd.DataFrame([{"acceptance_true_count": acceptance_count}]).to_csv(
        args.output_dir / "intraday_gate_acceptance_count.csv",
        index=False,
    )

    best_tail_row = tail_df.iloc[0]
    best_row = summary_df.iloc[0]
    best_id = str(best_row["candidate_id"])
    best_series = daily_series_store[best_id]
    best_active = active_store[best_id]

    daily_rows: List[Dict[str, object]] = []
    cumulative_real = 0.0
    running_peak = 0.0
    for day_idx, day_date in enumerate(day_dates):
        if np.isnan(best_series["real"][day_idx]):
            continue
        cumulative_real += float(best_series["real"][day_idx])
        running_peak = max(running_peak, cumulative_real)
        daily_rows.append(
            {
                "candidate_id": best_id,
                "date": str(day_date.date()),
                "split": "train" if day_date <= TRAIN_END else ("test" if day_date >= TEST_START else "other"),
                "active": bool(best_active[day_idx]),
                "daily_book_pnl": float(best_series["ledger"][day_idx]),
                "daily_real_pnl": float(best_series["real"][day_idx]),
                "daily_bets": float(best_series["issues"][day_idx]),
                "selected_score": float(best_series["selected_score"][day_idx]),
                "selected_mean_edge": float(best_series["selected_mean_edge"][day_idx]),
                "selected_symmetry_gap": float(best_series["selected_symmetry_gap"][day_idx]),
                "preview_raw_high_bias": float(best_series["preview_raw_high_bias"][day_idx]),
                "preview_mid_share": float(best_series["preview_mid_share"][day_idx]),
                "preview_mean_sum": float(best_series["preview_mean_sum"][day_idx]),
                "cumulative_real_pnl": cumulative_real,
                "running_peak_real_pnl": running_peak,
                "drawdown_real_pnl": cumulative_real - running_peak,
            }
        )
    pd.DataFrame(daily_rows).to_csv(args.output_dir / "intraday_gate_best_series.csv", index=False)

    (args.output_dir / "intraday_gate_report.md").write_text(
        build_report(best_tail_row, best_row, acceptance_count, args.odds_profile),
        encoding="utf-8",
    )
    print("intraday_gate: done", flush=True)


if __name__ == "__main__":
    main()
