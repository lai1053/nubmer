#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_SSH_HOST = "office_workstation"
DEFAULT_DB_HOST = "127.0.0.1"
DEFAULT_DB_PORT = 3307
DEFAULT_DB_USER = "root"
DEFAULT_DB_PASS = "123456"
DEFAULT_DB_NAME = "xyft_lottery_data"
DEFAULT_DB_TABLE = "pks_history"
INITIAL_BANKROLL = 1000.0
STAKE_PER_BET = 10.0
DATE_FROM = "2025-01-01"
DATE_TO = "2026-01-01"


def import_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PK10 round37 replay with 06:00-07:00 excluded")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "round37_outputs")
    parser.add_argument("--cache-path", type=Path, default=Path(__file__).resolve().parent / "round37_issue_history.pkl")
    parser.add_argument("--ssh-host", default=DEFAULT_SSH_HOST)
    parser.add_argument("--db-host", default=DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-pass", default=DEFAULT_DB_PASS)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--table", default=DEFAULT_DB_TABLE)
    parser.add_argument("--refresh-cache", action="store_true")
    return parser.parse_args()


def next_mult(mult: int) -> int:
    if mult <= 1:
        return 2
    if mult == 2:
        return 4
    return 5


def max_drawdown(bankroll: np.ndarray) -> float:
    peaks = np.maximum.accumulate(bankroll)
    return float(np.min(bankroll - peaks))


def bootstrap_mean_ci(arr: np.ndarray, n_boot: int = 3000, seed: int = 20260419):
    rng = np.random.default_rng(seed)
    n = arr.size
    means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample = arr[rng.integers(0, n, size=n)]
        means[i] = sample.mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def build_svg(df: pd.DataFrame, out_path: Path) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)
    x = np.arange(1, len(df) + 1)
    axes[0].plot(x, df["bankroll"].to_numpy(), color="#2563eb", linewidth=2.2)
    axes[0].set_title("Round37 Bankroll Curve")
    axes[0].grid(True, alpha=0.25)

    dd = df["bankroll"].to_numpy() - np.maximum.accumulate(df["bankroll"].to_numpy())
    axes[1].plot(x, dd, color="#dc2626", linewidth=2.0)
    axes[1].set_title("Drawdown From Peak")
    axes[1].grid(True, alpha=0.25)

    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in df["scaled_pnl"]]
    axes[2].bar(x, df["scaled_pnl"].to_numpy(), color=colors, width=0.8)
    axes[2].set_title("Daily PnL")
    axes[2].grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    root = Path(__file__).resolve().parent.parent
    round9_mod = import_module_from_path(
        "pk10_round9_for_round37",
        root / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py",
    )
    round16_mod = import_module_from_path(
        "pk10_round16_for_round37",
        root / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py",
    )
    round35_mod = import_module_from_path(
        "pk10_round35_for_round37",
        root / "pk10_round35_daily_deployment_refinement" / "pk10_round35_daily_deployment_refinement.py",
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
    ts_col = "ts" if "ts" in issue_df.columns else "pre_draw_time"
    issue_df[ts_col] = pd.to_datetime(issue_df[ts_col])
    issue_df = issue_df[(issue_df[ts_col].dt.hour < 6) | (issue_df[ts_col].dt.hour >= 7)].copy()

    bs_bundle = round9_mod.preprocess_history(issue_df)
    round9_mod.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle = round16_mod.preprocess_odd_even(round9_mod, issue_df)

    bs_core = round35_mod.make_candidate(
        round9_mod,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=15,
        gap_threshold=0.0125,
    )
    bs_exp = round35_mod.make_candidate(
        round9_mod,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=18,
        gap_threshold=0.0025,
    )
    oe_cfg = round35_mod.make_candidate(
        round9_mod,
        line_name="odd_even_oemap47_gated",
        strategy_family="quartet_fixed_map",
        map_name="OEMAP_47_vs_29",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=10,
        gap_threshold=0.0025,
    )

    bs_signal_states, bs_uniform, bs_balanced = round35_mod.build_signal_states(round9_mod, bs_bundle, [bs_core, bs_exp])
    oe_signal_states, oe_uniform, oe_balanced = round35_mod.build_signal_states(round9_mod, oe_bundle, [oe_cfg])
    bs_core_series = round9_mod.evaluate_candidate_series(bs_core, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9_mod.evaluate_candidate_series(bs_exp, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)
    oe_series = round9_mod.evaluate_candidate_series(oe_cfg, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    week_starts = [pd.Timestamp(ws).strftime("%Y-%m-%d") for ws in bs_bundle.week_start]
    core_daily = round35_mod.build_component_daily(bs_bundle, bs_core_series, week_starts, "core")
    exp_daily = round35_mod.build_component_daily(bs_bundle, bs_exp_series, week_starts, "exp")
    oe_daily = round35_mod.build_component_daily(oe_bundle, oe_series, week_starts, "oe")

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

    _, trace = round35_mod.simulate_policy(
        df=df,
        policy_id="round35_robust_no6to7",
        core_cfg=(40, "spread_only"),
        exp_cfg=(0, "off"),
        oe_cfg=(40, "spread_only"),
        cooldown_days=2,
    )
    trace["date"] = pd.to_datetime(trace["date"])
    trace = trace[(trace["date"] >= pd.Timestamp(DATE_FROM)) & (trace["date"] < pd.Timestamp(DATE_TO))].copy().reset_index(drop=True)

    bankroll = INITIAL_BANKROLL
    mult = 1
    rows = []
    for _, row in trace.iterrows():
        bets = float(row["policy_bets"])
        real_unit = float(row["policy_real_unit"])
        if bets > 0:
            used_mult = mult
            pnl = real_unit * STAKE_PER_BET * used_mult
            bankroll += pnl
            if pnl < 0:
                mult = next_mult(mult)
            elif pnl > 0:
                mult = 1
        else:
            used_mult = 0
            pnl = 0.0
        rows.append(
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "mode": row["mode"],
                "policy_bets": bets,
                "policy_real_unit": real_unit,
                "martingale_mult": used_mult,
                "scaled_pnl": pnl,
                "bankroll": bankroll,
            }
        )
        if bankroll <= 0:
            break

    replay_df = pd.DataFrame(rows)
    replay_df.to_csv(args.output_dir / "round37_daily_trace.csv", index=False)

    arr = replay_df["scaled_pnl"].to_numpy(dtype=float)
    bankroll_series = replay_df["bankroll"].to_numpy(dtype=float)
    ci_low, ci_high = bootstrap_mean_ci(arr)
    summary = pd.DataFrame(
        [
            {
                "date_from": DATE_FROM,
                "date_to": DATE_TO,
                "excluded_window": "06:00-07:00",
                "initial_bankroll": INITIAL_BANKROLL,
                "stake_per_bet": STAKE_PER_BET,
                "martingale_cap": "5x",
                "days_total": int(len(replay_df)),
                "days_active": int((replay_df["policy_bets"] > 0).sum()),
                "bets_total": float(replay_df["policy_bets"].sum()),
                "turnover_total": float((replay_df["policy_bets"] * STAKE_PER_BET * replay_df["martingale_mult"]).sum()),
                "final_bankroll": float(bankroll_series[-1]) if bankroll_series.size else INITIAL_BANKROLL,
                "total_profit": float(bankroll_series[-1] - INITIAL_BANKROLL) if bankroll_series.size else 0.0,
                "bootstrap_ci_low_daily_pnl": ci_low,
                "bootstrap_ci_high_daily_pnl": ci_high,
                "max_drawdown": max_drawdown(bankroll_series) if bankroll_series.size else 0.0,
                "min_bankroll": float(bankroll_series.min()) if bankroll_series.size else INITIAL_BANKROLL,
                "max_mult_hit": int(replay_df["martingale_mult"].max()) if not replay_df.empty else 0,
                "count_1x": int((replay_df["martingale_mult"] == 1).sum()),
                "count_2x": int((replay_df["martingale_mult"] == 2).sum()),
                "count_4x": int((replay_df["martingale_mult"] == 4).sum()),
                "count_5x": int((replay_df["martingale_mult"] == 5).sum()),
                "busted": bool((replay_df["bankroll"] <= 0).any()),
            }
        ]
    )
    summary.to_csv(args.output_dir / "round37_summary.csv", index=False)

    build_svg(replay_df, args.output_dir / "round37_curve.svg")

    report = [
        "# Round37 No-6-to-7 Replay",
        "",
        f"- Source table: `{args.db_name}.{args.table}`",
        f"- Date range: `{DATE_FROM}` to `{DATE_TO}`",
        "- Trading constraint: exclude all issues from `06:00` (inclusive) to `07:00` (exclusive).",
        "- Strategy: round35 robust deployment policy + daily martingale capped at `5x`.",
        "",
        "## Result",
        (
            f"- final bankroll `{summary.iloc[0]['final_bankroll']:.2f}`, total profit `{summary.iloc[0]['total_profit']:.2f}`, "
            f"days active `{int(summary.iloc[0]['days_active'])}`, bets `{summary.iloc[0]['bets_total']:.0f}`, "
            f"max DD `{summary.iloc[0]['max_drawdown']:.2f}`, min bankroll `{summary.iloc[0]['min_bankroll']:.2f}`, "
            f"max mult `{int(summary.iloc[0]['max_mult_hit'])}x`."
        ),
    ]
    (args.output_dir / "round37_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(args.output_dir / "round37_report.md")


if __name__ == "__main__":
    main()
