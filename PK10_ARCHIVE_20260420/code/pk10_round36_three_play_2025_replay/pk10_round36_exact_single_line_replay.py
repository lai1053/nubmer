#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALIGNED_FILE = BASE_DIR / "pk10_round36_aligned_shared_bankroll_replay.py"
ROUND36_FILE = BASE_DIR / "pk10_round36_three_play_2025_replay.py"
ROUND9_FILE = BASE_DIR.parent / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py"
SUM_VALIDATION_FILE = BASE_DIR.parent / "pk10_number_sum_validation" / "pk10_number_sum_validation.py"
NUMBER_WINDOW_FILE = BASE_DIR.parent / "tmp_number_validation" / "pk10_number_daily_window_validation.py"
NUMBER_WINDOW_DIR = NUMBER_WINDOW_FILE.parent

DEFAULT_SIM_START = "2025-01-01"
DEFAULT_SIM_END = "2026-01-01"
DEFAULT_QUERY_START = "2024-01-01"
DEFAULT_QUERY_END = "2026-01-01"
DEFAULT_BANKROLL = 1000.0
DEFAULT_BASE_STAKE = 10.0
DEFAULT_MAX_MULTIPLIER = 5
DEFAULT_STAKING_MODE = "martingale_1245"
DEFAULT_MAX_FUNDED_SLOTS_PER_DAY = 0
DEFAULT_EXACT_WINDOW_ID = "exactdw_frozen_edge_low_consensus_obs192"
DEFAULT_EXACT_BASE_GATE_ID = "late|big|edge_low|same_top1_prev=all"
DEFAULT_EXACT_OBS_WINDOW = 192
DEFAULT_EXACT_EXECUTION_RULE = "front_pair_major_consensus_only"
DEFAULT_EXACT_NET_WIN = 8.9
DEFAULT_BLACKOUT_START = "06:00:00"
DEFAULT_BLACKOUT_END = "07:00:00"


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay the frozen PK10 exact daily-window rule as a single-line bankroll.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--query-start", default=DEFAULT_QUERY_START)
    parser.add_argument("--query-end", default=DEFAULT_QUERY_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    parser.add_argument(
        "--staking-mode",
        choices=("fixed", "martingale_linear", "martingale_1245"),
        default=DEFAULT_STAKING_MODE,
    )
    parser.add_argument(
        "--max-funded-slots-per-day",
        type=int,
        default=DEFAULT_MAX_FUNDED_SLOTS_PER_DAY,
        help="Cap funded exact slots per active day; 0 means no extra cap.",
    )
    parser.add_argument("--exact-window-id", default=DEFAULT_EXACT_WINDOW_ID)
    parser.add_argument("--exact-base-gate-id", default=DEFAULT_EXACT_BASE_GATE_ID)
    parser.add_argument("--exact-obs-window", type=int, default=DEFAULT_EXACT_OBS_WINDOW)
    parser.add_argument("--exact-execution-rule", default=DEFAULT_EXACT_EXECUTION_RULE)
    parser.add_argument("--exact-net-win", type=float, default=DEFAULT_EXACT_NET_WIN)
    parser.add_argument("--blackout-start", default=DEFAULT_BLACKOUT_START)
    parser.add_argument("--blackout-end", default=DEFAULT_BLACKOUT_END)
    return parser.parse_args()


def next_multiplier(current: int, staking_mode: str, max_multiplier: int, last_real_pnl: float) -> int:
    if staking_mode == "fixed":
        return 1
    if last_real_pnl < 0.0:
        if staking_mode == "martingale_linear":
            return min(current + 1, max_multiplier)
        if staking_mode == "martingale_1245":
            if current < 2:
                return min(2, max_multiplier)
            if current < 4:
                return min(4, max_multiplier)
            return min(8, max_multiplier)
    return 1


def replay_exact_single_line(
    round36_mod,
    exact_frame: pd.DataFrame,
    exact_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    start_bankroll: float,
    base_stake: float,
    staking_mode: str,
    max_multiplier: int,
    max_funded_slots_per_day: int,
    exact_window_id: str,
    exact_base_gate_id: str,
    exact_obs_window: int,
    exact_execution_rule: str,
    exact_net_win: float,
    blackout_start: str,
    blackout_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bankroll = float(start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0
    exact_multiplier = 1
    skipped_exact_due_to_cash = 0
    exact_ladder_counts = {mult: 0 for mult in range(1, max_multiplier + 1)}

    rows: list[dict[str, object]] = []
    for _, row in exact_frame.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll
        exact_requested_slots = int(row["issue_exposures"])
        exact_funded_slots = 0
        exact_book_units = 0.0
        exact_real = 0.0
        affordable_exact_slots = max(0, int(bankroll_before // (base_stake * exact_multiplier))) if exact_multiplier > 0 else 0
        if exact_requested_slots > 0:
            cap_slots = exact_requested_slots
            if max_funded_slots_per_day > 0:
                cap_slots = min(cap_slots, max_funded_slots_per_day)
            exact_funded_slots = min(cap_slots, affordable_exact_slots)
            if exact_funded_slots > 0:
                exact_picks = exact_picks_by_date.get(day, pd.DataFrame()).head(exact_funded_slots).copy()
                exact_book_units = float(exact_picks["cell_book_pnl_units"].sum()) if not exact_picks.empty else 0.0
                exact_real = round36_mod.settle_real(exact_book_units * exact_multiplier) * base_stake
                exact_ladder_counts[int(exact_multiplier)] += 1
            else:
                skipped_exact_due_to_cash += 1

        bankroll += exact_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "exact_active": bool(exact_requested_slots > 0),
                "exact_requested_slots": exact_requested_slots,
                "exact_affordable_slots": affordable_exact_slots,
                "exact_funded_slots": exact_funded_slots,
                "exact_multiplier": exact_multiplier if exact_requested_slots > 0 else 0,
                "exact_book_pnl_units": exact_book_units,
                "exact_real_pnl": exact_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
            }
        )

        if exact_funded_slots > 0:
            exact_multiplier = next_multiplier(
                exact_multiplier,
                staking_mode=staking_mode,
                max_multiplier=max_multiplier,
                last_real_pnl=exact_real,
            )

    daily_df = pd.DataFrame(rows)
    summary_row = {
        "sim_start": str(sim_start.date()),
        "sim_end": str(sim_end.date()),
        "start_bankroll": start_bankroll,
        "base_stake": base_stake,
        "staking_mode": staking_mode,
        "max_multiplier": max_multiplier,
        "max_funded_slots_per_day": max_funded_slots_per_day,
        "exact_window_id": exact_window_id,
        "exact_base_gate_id": exact_base_gate_id,
        "exact_obs_window": int(exact_obs_window),
        "exact_execution_rule": exact_execution_rule,
        "exact_net_win": float(exact_net_win),
        "blackout_start": blackout_start,
        "blackout_end": blackout_end,
        "days_in_simulation": int(daily_df.shape[0]),
        "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
        "net_profit": float(daily_df["exact_real_pnl"].sum()),
        "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / start_bankroll - 1.0) * 100.0),
        "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
        "min_bankroll": float(daily_df["bankroll_after_day"].min()),
        "max_drawdown": float(max_drawdown),
        "exact_profit": float(daily_df["exact_real_pnl"].sum()),
        "exact_active_days": int(daily_df["exact_active"].sum()),
        "exact_requested_slots": int(daily_df["exact_requested_slots"].sum()),
        "exact_funded_slots": int(daily_df["exact_funded_slots"].sum()),
        "skipped_exact_due_to_cash": skipped_exact_due_to_cash,
    }
    for mult in range(1, max_multiplier + 1):
        summary_row[f"exact_days_{mult}x"] = exact_ladder_counts.get(mult, 0)
    summary_df = pd.DataFrame([summary_row])
    return daily_df, summary_df


def main() -> None:
    global args
    args = parse_args()
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)

    if str(NUMBER_WINDOW_DIR) not in sys.path:
        sys.path.insert(0, str(NUMBER_WINDOW_DIR))

    aligned_mod = import_module(ALIGNED_FILE, "round36_aligned_exact_single")
    round36_mod = import_module(ROUND36_FILE, "round36_exact_single")
    round9_mod = import_module(ROUND9_FILE, "round9_exact_single")
    vmod = import_module(SUM_VALIDATION_FILE, "sum_validation_exact_single")
    number_window_mod = import_module(NUMBER_WINDOW_FILE, "number_window_exact_single")

    effective_query_end = aligned_mod.complete_week_query_end(sim_end, args.query_end)
    issue_df = aligned_mod.load_issue_history(vmod, query_start=args.query_start, query_end=str(effective_query_end.date()))
    if issue_df.empty:
        raise RuntimeError("Issue history query returned no rows")

    blackout_start = aligned_mod.parse_time_of_day(args.blackout_start)
    blackout_end = aligned_mod.parse_time_of_day(args.blackout_end)
    allowed_lookup = aligned_mod.build_allowed_trade_lookup(
        aligned_mod.build_issue_schedule_frame(issue_df),
        blackout_start=blackout_start,
        blackout_end=blackout_end,
    )

    exact_frame, exact_picks_by_date = aligned_mod.build_exact_inputs(
        number_window_mod=number_window_mod,
        round9_mod=round9_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
        base_gate_id=args.exact_base_gate_id,
        obs_window=int(args.exact_obs_window),
        execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        allowed_lookup=allowed_lookup,
    )

    daily_df, summary_df = replay_exact_single_line(
        round36_mod=round36_mod,
        exact_frame=exact_frame,
        exact_picks_by_date=exact_picks_by_date,
        sim_start=sim_start,
        sim_end=sim_end,
        start_bankroll=float(args.start_bankroll),
        base_stake=float(args.base_stake),
        staking_mode=args.staking_mode,
        max_multiplier=max(1, int(args.max_multiplier)),
        max_funded_slots_per_day=max(0, int(args.max_funded_slots_per_day)),
        exact_window_id=args.exact_window_id,
        exact_base_gate_id=args.exact_base_gate_id,
        exact_obs_window=int(args.exact_obs_window),
        exact_execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        blackout_start=args.blackout_start,
        blackout_end=args.blackout_end,
    )

    blackout_tag = ""
    if blackout_start is not None and blackout_end is not None:
        blackout_tag = f"_blackout_{args.blackout_start.replace(':', '')}_{args.blackout_end.replace(':', '')}"

    if args.staking_mode == DEFAULT_STAKING_MODE and int(args.max_multiplier) == DEFAULT_MAX_MULTIPLIER:
        staking_tag = f"_m{int(args.max_multiplier)}"
    elif args.staking_mode == "fixed":
        staking_tag = "_fixed"
    else:
        staking_tag = f"_{args.staking_mode}_max{int(args.max_multiplier)}"
    cap_tag = "" if int(args.max_funded_slots_per_day) <= 0 else f"_cap{int(args.max_funded_slots_per_day)}"

    stem = (
        f"exact_single_line_{args.exact_window_id}"
        f"_bankroll_{int(args.start_bankroll)}_stake_{int(args.base_stake)}"
        f"{staking_tag}{cap_tag}{blackout_tag}_pks_history_{sim_start.date()}_{sim_end.date()}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    curve_path = OUTPUT_DIR / f"{stem}_curve.svg"

    daily_df.to_csv(daily_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    aligned_mod.build_svg(
        daily_df.rename(columns={"exact_real_pnl": "total_real_pnl"}),
        curve_path,
        title=f"Exact Single-Line Curve | {sim_start.date()} -> {sim_end.date()} | {args.exact_window_id}",
    )

    print(summary_path)
    print(daily_path)
    print(curve_path)


if __name__ == "__main__":
    main()
