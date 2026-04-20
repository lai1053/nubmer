#!/usr/bin/env python3
"""
PK10 冠亚和 intraday gate 窗口的资金曲线回放。

默认口径：
1. 直接使用 intraday gate 已经落地的 summary/detail 输出，不再重建数据库样本。
2. 默认回放 intraday 最优候选 `intraday_1007`。
3. 初始资金 5000，每注固定 100。
4. 当天 active 时，每个 tail slot 只算 1 注；若资金不够覆盖全部 slot，则按 score 从高到低买得起的那些 slot。
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_SIM_START = "2025-01-01"
DEFAULT_SIM_END = "2025-12-31"
DEFAULT_BANKROLL = 5000.0
DEFAULT_STAKE = 100.0
DEFAULT_CANDIDATE_ID = "intraday_1007"
DEFAULT_OUTPUT_DIRNAME = "number_sum_intraday_gate_outputs_db6y_daily85"
NEGATIVE_DISCOUNT = 0.85
DEFAULT_MAX_FUNDED_SLOTS_PER_DAY = 0
DEFAULT_STAKING_MODE = "fixed"
DEFAULT_MAX_MULTIPLIER = 1
DEFAULT_DB_HOST = "127.0.0.1"
DEFAULT_DB_PORT = 3307
DEFAULT_DB_USER = "root"
DEFAULT_DB_PASS = "123456"
DEFAULT_DB_NAME = "xyft_lottery_data"
DEFAULT_DB_TABLE = "pks_history"


def settle_real(book_pnl_units: float) -> float:
    return float(book_pnl_units if book_pnl_units >= 0.0 else NEGATIVE_DISCOUNT * book_pnl_units)


def import_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay intraday PK10 number-sum bankroll over an arbitrary simulation window")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--stake", type=float, default=DEFAULT_STAKE)
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument(
        "--staking-mode",
        choices=(
            "fixed",
            "martingale_linear",
            "martingale_double",
            "step_compound",
            "profit_compound",
            "anti_martingale",
        ),
        default=DEFAULT_STAKING_MODE,
        help="Bet-sizing rule across executed active days.",
    )
    parser.add_argument(
        "--max-multiplier",
        type=int,
        default=DEFAULT_MAX_MULTIPLIER,
        help="Maximum stake multiplier for martingale modes.",
    )
    parser.add_argument(
        "--max-funded-slots-per-day",
        type=int,
        default=DEFAULT_MAX_FUNDED_SLOTS_PER_DAY,
        help="Cap funded tail slots per active day; 0 means no extra cap.",
    )
    parser.add_argument(
        "--skip-hour-start",
        type=int,
        default=None,
        help="Inclusive local hour to start skipping bets, e.g. 6 for 06:00.",
    )
    parser.add_argument(
        "--skip-hour-end",
        type=int,
        default=None,
        help="Exclusive local hour to stop skipping bets, e.g. 7 for 07:00.",
    )
    parser.add_argument("--db-host", default=DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-pass", default=DEFAULT_DB_PASS)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--table", default=DEFAULT_DB_TABLE)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / DEFAULT_OUTPUT_DIRNAME,
    )
    return parser.parse_args()


def gate_is_on(day_row: pd.Series, candidate_row: pd.Series) -> bool:
    if float(day_row["requested_slots"]) <= 0.0:
        return False
    if float(day_row["selected_mean_edge"]) > float(candidate_row["mean_edge_cap"]):
        return False

    gate_family = str(candidate_row["gate_family"])
    raw_high = float(day_row["preview_raw_high_bias"])
    mid_share = float(day_row["preview_mid_share"])
    mean_sum = float(day_row["preview_mean_sum"])

    if gate_family == "high_only":
        return raw_high >= float(candidate_row["raw_high_threshold"])
    if gate_family == "high_mean":
        return (
            raw_high >= float(candidate_row["raw_high_threshold"])
            and mean_sum >= float(candidate_row["mean_sum_threshold"])
        )
    if gate_family == "high_mid":
        return (
            raw_high >= float(candidate_row["raw_high_threshold"])
            and mid_share >= float(candidate_row["mid_share_threshold"])
        )
    if gate_family == "mid_only":
        return mid_share >= float(candidate_row["mid_share_threshold"])
    raise ValueError(f"Unknown gate_family: {gate_family}")


def build_daily_frame(detail_df: pd.DataFrame, candidate_row: pd.Series) -> pd.DataFrame:
    grouped = (
        detail_df.groupby(["date", "split"], as_index=False)
        .agg(
            requested_slots=("slot", "size"),
            selected_score=("score_value", "mean"),
            selected_mean_edge=("mean_edge_value", "mean"),
            selected_symmetry_gap=("symmetry_gap_value", "mean"),
            preview_raw_high_bias=("preview_raw_high_bias", "mean"),
            preview_mid_share=("preview_mid_share", "mean"),
            preview_mean_sum=("preview_mean_sum", "mean"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    grouped["active"] = grouped.apply(lambda row: gate_is_on(row, candidate_row), axis=1)
    return grouped


def next_multiplier(current_multiplier: int, staking_mode: str, max_multiplier: int, last_real_points: float) -> int:
    if staking_mode == "fixed":
        return 1
    if staking_mode == "anti_martingale":
        if last_real_points > 0.0:
            return min(current_multiplier + 1, max_multiplier)
        return 1
    if last_real_points < 0.0:
        if staking_mode == "martingale_linear":
            return min(current_multiplier + 1, max_multiplier)
        if staking_mode == "martingale_double":
            return min(current_multiplier * 2, max_multiplier)
    return 1


def bankroll_based_multiplier(
    bankroll: float,
    start_bankroll: float,
    staking_mode: str,
    max_multiplier: int,
) -> int:
    if staking_mode == "step_compound":
        # 每增加一个“初始本金”台阶，注额提升一档。
        return max(1, min(max_multiplier, int(bankroll // start_bankroll)))
    if staking_mode == "profit_compound":
        # 只用利润加仓：每赚到 50% 初始本金，注额再加一档。
        profit = max(0.0, bankroll - start_bankroll)
        profit_step = 0.5 * start_bankroll
        if profit_step <= 0:
            return 1
        return max(1, min(max_multiplier, 1 + int(profit // profit_step)))
    return 1


def apply_hour_skip_filter(args: argparse.Namespace, detail_df: pd.DataFrame, sim_start: pd.Timestamp, sim_end: pd.Timestamp) -> tuple[pd.DataFrame, int]:
    if args.skip_hour_start is None or args.skip_hour_end is None:
        return detail_df, 0

    if not (0 <= int(args.skip_hour_start) <= 23 and 1 <= int(args.skip_hour_end) <= 24):
        raise ValueError("skip-hour window must use 0..23 start and 1..24 end")
    if int(args.skip_hour_start) >= int(args.skip_hour_end):
        raise ValueError("skip-hour-start must be smaller than skip-hour-end")

    root = Path(__file__).resolve().parent
    vmod = import_module_from_path(
        "pk10_number_sum_validation_for_intraday_bankroll",
        root / "pk10_number_sum_validation.py",
    )
    issue_df = vmod.load_issue_history_from_db(
        db_host=args.db_host,
        db_port=args.db_port,
        db_user=args.db_user,
        db_pass=args.db_pass,
        db_name=args.db_name,
        table=args.table,
        date_start=str(sim_start.date()),
        date_end=str(sim_end.date()),
    )
    if issue_df.empty:
        return detail_df, 0

    issue_df["draw_date"] = pd.to_datetime(issue_df["draw_date"], format="%Y-%m-%d")
    issue_df["pre_draw_time"] = pd.to_datetime(issue_df["pre_draw_time"], format="%Y-%m-%d %H:%M:%S")
    issue_df = issue_df.sort_values(["draw_date", "pre_draw_time", "pre_draw_issue"]).reset_index(drop=True)
    issue_df["slot"] = issue_df.groupby("draw_date").cumcount().astype(int)
    issue_df["hour"] = issue_df["pre_draw_time"].dt.hour.astype(int)

    slot_hours = issue_df.loc[:, ["draw_date", "slot", "hour"]].rename(columns={"draw_date": "date"})
    in_window_mask = (detail_df["date"] >= sim_start) & (detail_df["date"] <= sim_end)
    work = detail_df.loc[in_window_mask].copy()
    keep_outside = detail_df.loc[~in_window_mask].copy()
    work = work.merge(slot_hours, on=["date", "slot"], how="left")
    missing_hour = int(work["hour"].isna().sum())
    if missing_hour > 0:
        raise ValueError(f"Missing issue-hour mapping for {missing_hour} detail rows")

    keep_mask = ~work["hour"].between(int(args.skip_hour_start), int(args.skip_hour_end) - 1)
    filtered = work.loc[keep_mask].drop(columns=["hour"]).reset_index(drop=True)
    removed = int((~keep_mask).sum())
    combined = pd.concat([keep_outside, filtered], ignore_index=True)
    combined = combined.sort_values(["date", "slot", "score_value"], ascending=[True, True, False]).reset_index(drop=True)
    return combined, removed


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = args.output_dir / "intraday_gate_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing intraday gate summary: {summary_path}")

    summary_df = pd.read_csv(summary_path)
    candidate_match = summary_df[summary_df["candidate_id"] == args.candidate_id].copy()
    if candidate_match.empty:
        raise ValueError(f"Candidate not found in {summary_path}: {args.candidate_id}")
    candidate_row = candidate_match.iloc[0]

    baseline_name = str(candidate_row["baseline_name"])
    preview_cut = int(candidate_row["preview_cut"])
    detail_path = args.output_dir / f"{baseline_name}_cut{preview_cut}_intraday_detail.csv"
    if not detail_path.exists():
        raise FileNotFoundError(f"Missing intraday detail file: {detail_path}")

    detail_df = pd.read_csv(detail_path)
    detail_df["date"] = pd.to_datetime(detail_df["date"])
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)
    detail_df, removed_rows = apply_hour_skip_filter(args, detail_df, sim_start, sim_end)

    daily_frame = build_daily_frame(detail_df, candidate_row)
    daily_frame["date"] = pd.to_datetime(daily_frame["date"])

    date_range = pd.date_range(sim_start, sim_end, freq="D")
    sim_frame = pd.DataFrame({"date": date_range})
    sim_frame = sim_frame.merge(daily_frame, on="date", how="left")
    sim_frame["split"] = sim_frame["split"].fillna("out_of_sample_gap")
    for col in [
        "requested_slots",
        "selected_score",
        "selected_mean_edge",
        "selected_symmetry_gap",
        "preview_raw_high_bias",
        "preview_mid_share",
        "preview_mean_sum",
    ]:
        sim_frame[col] = sim_frame[col].fillna(0.0)
    sim_frame["active"] = sim_frame["active"].fillna(False).astype(bool)

    bankroll = float(args.start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0
    stake = float(args.stake)
    max_multiplier = max(1, int(args.max_multiplier))
    current_multiplier = 1
    executed_days = 0
    executed_slots = 0
    skipped_active_due_to_cash = 0
    rows = []

    for _, day_row in sim_frame.iterrows():
        day_date = pd.Timestamp(day_row["date"])
        bankroll_before = bankroll
        requested_slots = int(day_row["requested_slots"]) if bool(day_row["active"]) else 0
        if args.staking_mode in {"step_compound", "profit_compound"}:
            day_multiplier = bankroll_based_multiplier(
                bankroll=bankroll,
                start_bankroll=float(args.start_bankroll),
                staking_mode=args.staking_mode,
                max_multiplier=max_multiplier,
            )
        else:
            day_multiplier = current_multiplier
        effective_stake = stake * day_multiplier
        affordable_slots = int(bankroll // effective_stake) if effective_stake > 0.0 else 0
        funded_slots = 0
        daily_book_units = 0.0
        daily_real_points = 0.0

        if requested_slots > 0:
            cap_slots = requested_slots
            if args.max_funded_slots_per_day > 0:
                cap_slots = min(cap_slots, int(args.max_funded_slots_per_day))
            funded_slots = min(cap_slots, affordable_slots)
            if funded_slots > 0:
                picks = (
                    detail_df[detail_df["date"] == day_date]
                    .sort_values(["score_value", "slot"], ascending=[False, True])
                    .head(funded_slots)
                    .copy()
                )
                daily_book_units = float(picks["book_pnl"].sum())
                daily_real_points = float(settle_real(daily_book_units * day_multiplier) * stake)
                executed_days += 1
                executed_slots += funded_slots
            else:
                skipped_active_due_to_cash += 1

        bankroll += daily_real_points
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": str(day_date.date()),
                "split": str(day_row["split"]),
                "active": bool(day_row["active"]),
                "requested_slots": requested_slots,
                "affordable_slots": affordable_slots,
                "funded_slots": funded_slots,
                "stake_multiplier": day_multiplier,
                "effective_stake_per_slot": effective_stake,
                "daily_book_pnl_units": daily_book_units,
                "daily_real_pnl_points": daily_real_points,
                "daily_nominal_cost_points": funded_slots * effective_stake,
                "bankroll_before_day": bankroll_before,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
                "preview_raw_high_bias": float(day_row["preview_raw_high_bias"]),
                "preview_mid_share": float(day_row["preview_mid_share"]),
                "preview_mean_sum": float(day_row["preview_mean_sum"]),
            }
        )

        if funded_slots > 0:
            current_multiplier = next_multiplier(
                current_multiplier=day_multiplier,
                staking_mode=args.staking_mode,
                max_multiplier=max_multiplier,
                last_real_points=daily_real_points,
            )

    curve_df = pd.DataFrame(rows)
    summary_out = pd.DataFrame(
        [
            {
                "candidate_id": args.candidate_id,
                "baseline_name": baseline_name,
                "preview_cut": preview_cut,
                "gate_family": candidate_row["gate_family"],
                "simulation_start": str(sim_start.date()),
                "simulation_end": str(sim_end.date()),
                "start_bankroll": args.start_bankroll,
                "stake_per_bet": stake,
                "staking_mode": args.staking_mode,
                "max_multiplier": max_multiplier,
                "max_funded_slots_per_day": int(args.max_funded_slots_per_day),
                "skip_hour_start": args.skip_hour_start,
                "skip_hour_end": args.skip_hour_end,
                "removed_detail_rows": removed_rows,
                "days_in_simulation": int(curve_df.shape[0]),
                "active_days": int(curve_df["active"].sum()),
                "executed_days": executed_days,
                "executed_slots": executed_slots,
                "executed_bets": executed_slots,
                "skipped_active_due_to_cash": skipped_active_due_to_cash,
                "final_bankroll": bankroll,
                "net_profit_points": bankroll - args.start_bankroll,
                "roi_on_start_bankroll_pct": (bankroll / args.start_bankroll - 1.0) * 100.0,
                "peak_bankroll": peak,
                "min_bankroll": min_bankroll,
                "max_drawdown_points": max_drawdown,
            }
        ]
    )

    sim_start_token = str(sim_start.date())
    sim_end_token = str(sim_end.date())
    cap_token = "nocap" if int(args.max_funded_slots_per_day) <= 0 else f"cap{int(args.max_funded_slots_per_day)}"
    staking_token = (
        "fixed"
        if args.staking_mode == "fixed"
        else f"{args.staking_mode}_max{max_multiplier}"
    )
    skip_token = (
        "noskip"
        if args.skip_hour_start is None or args.skip_hour_end is None
        else f"skiph{int(args.skip_hour_start):02d}-{int(args.skip_hour_end):02d}"
    )
    stem = (
        f"{args.candidate_id}_bankroll_{int(args.start_bankroll)}_stake{int(args.stake)}"
        f"_{staking_token}_{cap_token}_{skip_token}_{sim_start_token}_{sim_end_token}"
    )
    curve_path = args.output_dir / f"{stem}_daily.csv"
    summary_path = args.output_dir / f"{stem}_summary.csv"
    report_path = args.output_dir / f"{stem}_report.md"
    plot_path = args.output_dir / f"{stem}_curve.png"

    curve_df.to_csv(curve_path, index=False)
    summary_out.to_csv(summary_path, index=False)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(13, 6.5), dpi=160)
    x = pd.to_datetime(curve_df["date"])
    ax.plot(x, curve_df["bankroll_after_day"], color="#0f4c5c", lw=2.0, label="End-of-day bankroll")
    ax.axhline(args.start_bankroll, color="#999999", lw=1.2, ls="--", label="Start bankroll")

    executed = curve_df[curve_df["funded_slots"] > 0]
    wins = executed[executed["daily_real_pnl_points"] >= 0]
    losses = executed[executed["daily_real_pnl_points"] < 0]

    if not wins.empty:
        ax.scatter(pd.to_datetime(wins["date"]), wins["bankroll_after_day"], color="#2a9d8f", s=20, zorder=3, label="Executed gain day")
    if not losses.empty:
        ax.scatter(pd.to_datetime(losses["date"]), losses["bankroll_after_day"], color="#d62828", s=20, zorder=3, label="Executed loss day")

    ax.set_title(
        "PK10 Number Sum Intraday Gate Bankroll Curve"
        f" ({sim_start_token} to {sim_end_token})"
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Bankroll points")
    ax.legend(loc="upper left", frameon=True)
    ax.text(
        0.99,
        0.02,
        f"Start {args.start_bankroll:.0f} | Final {bankroll:.1f} | PnL {bankroll - args.start_bankroll:+.1f} | Max DD {max_drawdown:.1f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.85, "edgecolor": "#cccccc"},
    )
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(plot_path, bbox_inches="tight")
    plt.close(fig)

    report_lines = [
        "# PK10 Number Sum Intraday Gate Bankroll Replay",
        "",
        f"- candidate `{args.candidate_id}` = `{baseline_name} / cut={preview_cut} / {candidate_row['gate_family']}`.",
        f"- simulation `{sim_start_token}` to `{sim_end_token}`, start bankroll `{args.start_bankroll:.0f}`, stake `{stake:.0f}`, staking `{args.staking_mode}` max `{max_multiplier}x`, max funded slots/day `{args.max_funded_slots_per_day}`.",
        f"- skipped local-hour window `{args.skip_hour_start}:00` to `{args.skip_hour_end}:00` removed detail rows `{removed_rows}`."
        if args.skip_hour_start is not None and args.skip_hour_end is not None
        else "- no intraday hour skip filter.",
        f"- active days `{int(curve_df['active'].sum())}`, executed days `{executed_days}`, executed slots `{executed_slots}`, skipped active due to cash `{skipped_active_due_to_cash}`.",
        f"- final bankroll `{bankroll:.1f}`, net `{bankroll - args.start_bankroll:+.1f}`, ROI `{(bankroll / args.start_bankroll - 1.0) * 100.0:.2f}%`.",
        f"- peak `{peak:.1f}`, min `{min_bankroll:.1f}`, max drawdown `{max_drawdown:.1f}`.",
        "",
        f"![Intraday Bankroll Curve]({plot_path})",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
