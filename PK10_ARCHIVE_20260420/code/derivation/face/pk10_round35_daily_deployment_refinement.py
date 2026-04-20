#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import itertools
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd


DEFAULT_SSH_HOST = "local"
DEFAULT_DB_HOST = "127.0.0.1"
DEFAULT_DB_PORT = 3307
DEFAULT_DB_USER = "root"
DEFAULT_DB_PASS = "123456"
DEFAULT_DB_NAME = "xyft_lottery_data"
DEFAULT_DB_TABLE = "pks_history"
DELTA_STAR_LINEAR = 0.005 / 1.995
INITIAL_BANKROLL = 1000.0
STAKE_PER_BET = 50.0


def import_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PK10 round35 daily deployment refinement")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "round35_outputs")
    parser.add_argument("--cache-path", type=Path, default=Path(__file__).resolve().parent / "round35_issue_history.pkl")
    parser.add_argument("--ssh-host", default=DEFAULT_SSH_HOST)
    parser.add_argument("--db-host", default=DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-pass", default=DEFAULT_DB_PASS)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--table", default=DEFAULT_DB_TABLE)
    parser.add_argument("--refresh-cache", action="store_true")
    return parser.parse_args()


def make_candidate(round9_mod, *, line_name: str, strategy_family: str, map_name: str, bucket_model: str,
                   score_model: str, lookback_weeks: int, holding_weeks: int, prior_strength: int,
                   selector_family: str, daily_issue_cap: int, gap_threshold: float):
    return round9_mod.CandidateConfig(
        line_name=line_name,
        strategy_family=strategy_family,
        bucket_model=bucket_model,
        score_model=score_model,
        lookback_weeks=lookback_weeks,
        holding_weeks=holding_weeks,
        prior_strength=prior_strength,
        selector_family=selector_family,
        daily_issue_cap=daily_issue_cap,
        gap_threshold=gap_threshold,
        audit_only=False,
        map_name=map_name,
    )


def build_signal_states(round9_mod, bundle, configs: Sequence[object]):
    caps = sorted({int(cfg.daily_issue_cap) for cfg in configs})
    uniform_indices = round9_mod.build_uniform_selector_indices(bundle.n_slots, caps)
    balanced_indices = round9_mod.build_balanced_selector_indices(bundle.slot_to_decile, caps)
    signal_states: Dict[Tuple[str, str, int, int], Dict[str, np.ndarray]] = {}
    for cfg in configs:
        key = (cfg.bucket_model, cfg.score_model, int(cfg.lookback_weeks), int(cfg.prior_strength))
        if key in signal_states:
            continue
        counts, exposures = round9_mod.get_bucket_counts(bundle, cfg.bucket_model)
        signal_states[key] = round9_mod.compute_signal_state(
            counts=counts,
            exposures=exposures,
            lookback_weeks=int(cfg.lookback_weeks),
            prior_strength=int(cfg.prior_strength),
            score_model=cfg.score_model,
        )
    return signal_states, uniform_indices, balanced_indices


def day_ledger_from_positions(week_cube: np.ndarray, selected_positions_meta) -> Tuple[np.ndarray, np.ndarray]:
    daily_ledger = np.zeros(week_cube.shape[0], dtype=float)
    daily_bets = np.zeros(week_cube.shape[0], dtype=float)
    if selected_positions_meta is None:
        return daily_ledger, daily_bets
    for payload in selected_positions_meta:
        if not payload:
            continue
        slot_idx = int(payload[0])
        big_positions = np.asarray(payload[1], dtype=int) - 1
        small_positions = np.asarray(payload[2], dtype=int) - 1
        if big_positions.size == 1 and small_positions.size == 1:
            top = week_cube[:, slot_idx, big_positions[0]].astype(np.int16)
            bottom = week_cube[:, slot_idx, small_positions[0]].astype(np.int16)
            daily_ledger += (1995 * (top + 1 - bottom) - 2000) / 1000.0
            daily_bets += 2.0
        elif big_positions.size == 2 and small_positions.size == 2:
            top = week_cube[:, slot_idx][:, big_positions].astype(np.int16)
            bottom = week_cube[:, slot_idx][:, small_positions].astype(np.int16)
            hits = top.sum(axis=1) + (2 - bottom.sum(axis=1))
            daily_ledger += (1995 * hits - 4000) / 1000.0
            daily_bets += 4.0
        else:
            raise ValueError(f"Unsupported payload: {payload}")
    return daily_ledger, daily_bets


def build_component_daily(bundle, series: Dict[str, np.ndarray], week_starts: Sequence[str], line_name: str) -> pd.DataFrame:
    lookup = {pd.Timestamp(ws).strftime("%Y-%m-%d"): idx for idx, ws in enumerate(bundle.week_start)}
    rows: List[Dict[str, object]] = []
    for week_start in week_starts:
        week_idx = lookup[week_start]
        week_cube = bundle.big_cube[week_idx]
        daily_ledger, daily_bets = day_ledger_from_positions(week_cube, series["selected_positions_meta"][week_idx])
        for day_offset in range(7):
            ledger = float(daily_ledger[day_offset])
            bets = float(daily_bets[day_offset])
            issues = float(bets / 4.0) if bets > 0 else 0.0
            implied_spread = (ledger / issues + 0.01) / 3.99 if issues > 0 else float("nan")
            rows.append(
                {
                    "line_name": line_name,
                    "week_start": week_start,
                    "date": (pd.Timestamp(week_start) + pd.Timedelta(days=day_offset)).strftime("%Y-%m-%d"),
                    "day_index_in_week": day_offset + 1,
                    "daily_ledger_unit": ledger,
                    "daily_bets": bets,
                    "daily_implied_spread": implied_spread,
                }
            )
    return pd.DataFrame(rows)


def read_baseline_daily(root: Path) -> pd.DataFrame:
    df = pd.read_csv(root / "pk10_round33_daily_window_search" / "round33_outputs" / "round33_best_daily_trace.csv")
    return df


def compute_trailing_metrics(values: pd.Series, window: int) -> pd.DataFrame:
    roll_mean = values.shift(1).rolling(window, min_periods=window).mean()
    roll_std = values.shift(1).rolling(window, min_periods=window).std(ddof=1)
    ci_low = roll_mean - 1.96 * roll_std / np.sqrt(window)
    return pd.DataFrame({"mean": roll_mean, "ci_low": ci_low})


def daily85(ledger: float) -> float:
    return ledger if ledger >= 0.0 else 0.85 * ledger


def bootstrap_mean_ci(arr: np.ndarray, n_boot: int = 3000, seed: int = 20260416) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    if arr.size == 0:
        return float("nan"), float("nan")
    means = np.empty(n_boot, dtype=float)
    n = arr.size
    for i in range(n_boot):
        sample = arr[rng.integers(0, n, size=n)]
        means[i] = sample.mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def max_drawdown_from_scaled(arr: np.ndarray) -> float:
    equity = INITIAL_BANKROLL + np.cumsum(arr * STAKE_PER_BET)
    peaks = np.maximum.accumulate(equity)
    return float(np.min(equity - peaks))


def gate_from_family(series: pd.Series, spread: pd.Series, window: int, family: str) -> pd.Series:
    stats = compute_trailing_metrics(series, window)
    spread_mean = spread.shift(1).rolling(window, min_periods=window).mean()
    on = (stats["mean"] > 0.0) & (spread_mean > DELTA_STAR_LINEAR)
    if family == "spread_only":
        return on.fillna(False)
    if family == "spread_ci":
        return (on & (stats["ci_low"] > 0.0)).fillna(False)
    if family == "spread_ci_strict":
        return (on & (stats["ci_low"] > 0.10)).fillna(False)
    if family == "off":
        return pd.Series(False, index=series.index)
    raise ValueError(family)


def simulate_policy(df: pd.DataFrame, policy_id: str, core_cfg: Tuple[int, str], exp_cfg: Tuple[int, str], oe_cfg: Tuple[int, str], cooldown_days: int) -> Tuple[Dict[str, object], pd.DataFrame]:
    work = df.copy()
    core_on = gate_from_family(work["core_ledger_unit"], work["core_implied_spread"], core_cfg[0], core_cfg[1])
    exp_on = gate_from_family(work["exp_ledger_unit"], work["exp_implied_spread"], exp_cfg[0], exp_cfg[1])
    oe_on = gate_from_family(work["oe_ledger_unit"], work["oe_implied_spread"], oe_cfg[0], oe_cfg[1])

    cooldown = 0
    modes = []
    ledger_out = []
    bets_out = []
    reals: List[float] = []
    for idx, row in work.iterrows():
        if cooldown > 0:
            mode = "cash"
            ledger = 0.0
            bets = 0.0
            cooldown -= 1
        elif bool(core_on.iloc[idx]):
            ledger = float(row["core_ledger_unit"])
            bets = float(row["core_bets"])
            mode = "core"
            if bool(exp_on.iloc[idx]):
                ledger += float(row["exp_ledger_unit"])
                bets += float(row["exp_bets"])
                mode = "core_plus_expansion"
            if bool(oe_on.iloc[idx]):
                ledger += float(row["oe_ledger_unit"])
                bets += float(row["oe_bets"])
                mode = "core_plus_expansion_plus_oe" if mode == "core_plus_expansion" else "core_plus_oe"
        else:
            mode = "cash"
            ledger = 0.0
            bets = 0.0
        real = daily85(ledger)
        if cooldown_days > 0 and real < 0.0 and bets > 0.0:
            cooldown = cooldown_days
        modes.append(mode)
        ledger_out.append(ledger)
        bets_out.append(bets)
        reals.append(real)

    work["policy_id"] = policy_id
    work["mode"] = modes
    work["policy_ledger_unit"] = ledger_out
    work["policy_real_unit"] = reals
    work["policy_bets"] = bets_out

    arr = work["policy_real_unit"].to_numpy(dtype=float)
    low, high = bootstrap_mean_ci(arr)
    r13, _ = bootstrap_mean_ci(work.tail(13)["policy_real_unit"].to_numpy(dtype=float))
    r26, _ = bootstrap_mean_ci(work.tail(26)["policy_real_unit"].to_numpy(dtype=float))
    r52, _ = bootstrap_mean_ci(work.tail(52)["policy_real_unit"].to_numpy(dtype=float))
    summary = {
        "policy_id": policy_id,
        "core_window": core_cfg[0],
        "core_family": core_cfg[1],
        "exp_window": exp_cfg[0],
        "exp_family": exp_cfg[1],
        "oe_window": oe_cfg[0],
        "oe_family": oe_cfg[1],
        "cooldown_days": cooldown_days,
        "avg_daily_real_unit": float(work["policy_real_unit"].mean()),
        "bootstrap_ci_low_daily_unit": low,
        "bootstrap_ci_high_daily_unit": high,
        "recent13_ci_low_daily_unit": r13,
        "recent26_ci_low_daily_unit": r26,
        "recent52_ci_low_daily_unit": r52,
        "avg_daily_bets": float(work["policy_bets"].mean()),
        "active_day_share": float((work["policy_bets"] > 0).mean()),
        "final_bankroll": float(INITIAL_BANKROLL + np.cumsum(arr * STAKE_PER_BET)[-1]),
        "max_drawdown_scaled": max_drawdown_from_scaled(arr),
        "days_core": int((work["mode"] == "core").sum()),
        "days_core_plus_oe": int((work["mode"] == "core_plus_oe").sum()),
        "days_core_plus_expansion": int((work["mode"] == "core_plus_expansion").sum()),
        "days_core_plus_expansion_plus_oe": int((work["mode"] == "core_plus_expansion_plus_oe").sum()),
        "days_cash": int((work["mode"] == "cash").sum()),
    }
    return summary, work


def build_svg(baseline: pd.DataFrame, best: pd.DataFrame, output_path: Path) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=False)
    bx = np.arange(1, len(baseline) + 1)
    px = np.arange(1, len(best) + 1)
    beq = INITIAL_BANKROLL + np.cumsum(baseline["policy_real_unit"].to_numpy(dtype=float) * STAKE_PER_BET)
    peq = INITIAL_BANKROLL + np.cumsum(best["policy_real_unit"].to_numpy(dtype=float) * STAKE_PER_BET)
    bdd = beq - np.maximum.accumulate(beq)
    pdd = peq - np.maximum.accumulate(peq)

    axes[0].plot(bx, beq, label="round33_best_daily", color="#6b7280", linewidth=2)
    axes[0].plot(px, peq, label="round35_best_deployment", color="#2563eb", linewidth=2.2)
    axes[0].set_title("Daily85 Bankroll")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(fontsize=9)

    axes[1].plot(bx, bdd, label="round33_baseline", color="#6b7280", linewidth=2)
    axes[1].plot(px, pdd, label="round35_best", color="#2563eb", linewidth=2.2)
    axes[1].set_title("Drawdown From Peak")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def build_report(summary_df: pd.DataFrame, baseline: pd.DataFrame, best: pd.Series) -> str:
    base_arr = baseline["policy_real_unit"].to_numpy(dtype=float)
    base_final = float(INITIAL_BANKROLL + np.cumsum(base_arr * STAKE_PER_BET)[-1])
    base_dd = max_drawdown_from_scaled(base_arr)
    base_low, base_high = bootstrap_mean_ci(base_arr)
    base_r13, _ = bootstrap_mean_ci(baseline.tail(13)["policy_real_unit"].to_numpy(dtype=float))
    base_r26, _ = bootstrap_mean_ci(baseline.tail(26)["policy_real_unit"].to_numpy(dtype=float))
    base_r52, _ = bootstrap_mean_ci(baseline.tail(52)["policy_real_unit"].to_numpy(dtype=float))
    lines = []
    lines.append("# Round35 Daily Deployment Refinement")
    lines.append("")
    lines.append("- This round starts from the frozen retained components and searches a more robust daily deployment policy.")
    lines.append("- Differences vs round33: component-specific gates and optional 1-2 day cooldown after a negative active day.")
    lines.append("")
    lines.append("## Baseline")
    lines.append(
        f"- round33 best daily path: final `{base_final:.2f}`, "
        f"CI low `{base_low:.4f}`, recent13/26/52 CI low `{base_r13:.4f} / {base_r26:.4f} / {base_r52:.4f}`, "
        f"max DD `{base_dd:.2f}`."
    )
    lines.append("")
    lines.append("## Best Refined Policy")
    lines.append(
        f"- {best['policy_id']} -> final `{best['final_bankroll']:.2f}`, "
        f"CI low `{best['bootstrap_ci_low_daily_unit']:.4f}`, "
        f"recent13/26/52 CI low `{best['recent13_ci_low_daily_unit']:.4f} / {best['recent26_ci_low_daily_unit']:.4f} / {best['recent52_ci_low_daily_unit']:.4f}`, "
        f"avg daily bets `{best['avg_daily_bets']:.2f}`, active share `{best['active_day_share']:.2%}`, max DD `{best['max_drawdown_scaled']:.2f}`."
    )
    lines.append("")
    lines.append("## Answer")
    better_short = (
        float(best["recent13_ci_low_daily_unit"]) > base_r13
        and float(best["recent26_ci_low_daily_unit"]) > base_r26
    )
    better_risk = float(best["max_drawdown_scaled"]) > base_dd
    if better_short and better_risk:
        lines.append("- The refined daily deployment policy improves both short-window stability and drawdown versus round33.")
    elif better_short:
        lines.append("- The refined daily deployment policy improves short-window stability versus round33, but not drawdown.")
    elif better_risk:
        lines.append("- The refined daily deployment policy reduces drawdown versus round33, but does not materially fix short-window stability.")
    else:
        lines.append("- The refined daily deployment policy does not materially improve short-window robustness over round33.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    base_dir = Path(__file__).resolve().parent.parent
    round9_mod = import_module_from_path(
        "pk10_round9_for_round35",
        base_dir / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py",
    )
    round16_mod = import_module_from_path(
        "pk10_round16_for_round35",
        base_dir / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py",
    )

    issue_df = round9_mod.load_full_issue_history(
        ssh_host=args.ssh_host,
        db_host=args.db_host,
        db_port=args.db_port,
        db_user=args.db_user,
        db_pass=args.db_pass,
        db_name=args.db_name,
        table=args.table,
        cache_path=args.cache_path,
        refresh=args.refresh_cache,
    )

    bs_bundle = round9_mod.preprocess_history(issue_df)
    bs_core = make_candidate(round9_mod, line_name="slow_static_quartet", strategy_family="quartet_fixed_map", map_name="M4_72_vs_910",
                             bucket_model="exact_slot", score_model="beta_shrunk_rate", lookback_weeks=26, holding_weeks=4,
                             prior_strength=20, selector_family="daily_gap_topk", daily_issue_cap=15, gap_threshold=0.0125)
    bs_exp = make_candidate(round9_mod, line_name="slow_static_quartet", strategy_family="quartet_fixed_map", map_name="M4_72_vs_910",
                            bucket_model="exact_slot", score_model="beta_shrunk_rate", lookback_weeks=26, holding_weeks=4,
                            prior_strength=20, selector_family="daily_gap_topk", daily_issue_cap=18, gap_threshold=0.0025)
    bs_signal_states, bs_uniform, bs_balanced = build_signal_states(round9_mod, bs_bundle, [bs_core, bs_exp])
    bs_core_series = round9_mod.evaluate_candidate_series(bs_core, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9_mod.evaluate_candidate_series(bs_exp, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)

    round9_mod.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle = round16_mod.preprocess_odd_even(round9_mod, issue_df)
    oe_cfg = make_candidate(round9_mod, line_name="odd_even_oemap47_gated", strategy_family="quartet_fixed_map", map_name="OEMAP_47_vs_29",
                            bucket_model="exact_slot", score_model="beta_shrunk_rate", lookback_weeks=26, holding_weeks=4,
                            prior_strength=20, selector_family="daily_gap_topk", daily_issue_cap=10, gap_threshold=0.0025)
    oe_signal_states, oe_uniform, oe_balanced = build_signal_states(round9_mod, oe_bundle, [oe_cfg])
    oe_series = round9_mod.evaluate_candidate_series(oe_cfg, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    baseline = read_baseline_daily(base_dir)
    week_starts = sorted(baseline["week_start"].unique().tolist())
    core_daily = build_component_daily(bs_bundle, bs_core_series, week_starts, "core")
    exp_daily = build_component_daily(bs_bundle, bs_exp_series, week_starts, "exp")
    oe_daily = build_component_daily(oe_bundle, oe_series, week_starts, "oe")

    df = core_daily[["week_start", "date", "day_index_in_week", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
        columns={"daily_ledger_unit": "core_ledger_unit", "daily_bets": "core_bets", "daily_implied_spread": "core_implied_spread"}
    )
    df = df.merge(
        exp_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={"daily_ledger_unit": "exp_ledger_unit", "daily_bets": "exp_bets", "daily_implied_spread": "exp_implied_spread"}
        ),
        on="date",
        how="left",
    )
    df = df.merge(
        oe_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={"daily_ledger_unit": "oe_ledger_unit", "daily_bets": "oe_bets", "daily_implied_spread": "oe_implied_spread"}
        ),
        on="date",
        how="left",
    )
    df = df.fillna(0.0)
    df["day_index"] = np.arange(1, len(df) + 1)

    core_options = [(20, "spread_only"), (40, "spread_only"), (40, "spread_ci")]
    exp_options = [(20, "spread_only"), (40, "spread_only"), (40, "spread_ci"), (0, "off")]
    oe_options = [(20, "spread_only"), (40, "spread_only"), (40, "spread_ci"), (0, "off")]
    cooldown_options = [0, 1, 2]

    summary_rows = []
    best_trace = None
    best_key = None
    for core_cfg, exp_cfg, oe_cfg, cooldown in itertools.product(core_options, exp_options, oe_options, cooldown_options):
        policy_id = (
            f"core{core_cfg[0]}_{core_cfg[1]}__exp{exp_cfg[0]}_{exp_cfg[1]}__"
            f"oe{oe_cfg[0]}_{oe_cfg[1]}__cd{cooldown}"
        )
        summary, trace = simulate_policy(df, policy_id, core_cfg, exp_cfg, oe_cfg, cooldown)
        summary_rows.append(summary)
        key = (
            summary["recent13_ci_low_daily_unit"],
            summary["recent26_ci_low_daily_unit"],
            summary["bootstrap_ci_low_daily_unit"],
            -abs(summary["max_drawdown_scaled"]),
            summary["final_bankroll"],
        )
        if best_key is None or key > best_key:
            best_key = key
            best_trace = trace

    summary_df = pd.DataFrame(summary_rows).sort_values(
        by=["recent13_ci_low_daily_unit", "recent26_ci_low_daily_unit", "bootstrap_ci_low_daily_unit", "max_drawdown_scaled", "final_bankroll"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    summary_df.to_csv(args.output_dir / "round35_daily_deployment_summary.csv", index=False)
    summary_df.head(15).to_csv(args.output_dir / "round35_top_policies.csv", index=False)
    if best_trace is None:
        raise RuntimeError("No deployment trace produced")
    best_trace.to_csv(args.output_dir / "round35_best_trace.csv", index=False)

    build_svg(baseline, best_trace, args.output_dir / "round35_daily_deployment_curves.png")
    report = build_report(summary_df, baseline, summary_df.iloc[0])
    (args.output_dir / "round35_report.md").write_text(report, encoding="utf-8")
    print(args.output_dir / "round35_report.md")


if __name__ == "__main__":
    main()
