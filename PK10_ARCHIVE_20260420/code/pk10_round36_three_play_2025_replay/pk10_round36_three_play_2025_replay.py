#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ROUND30_DAILY = (
    ROOT_DIR
    / "pk10_round30_daily85_exact_transfer"
    / "round30_outputs"
    / "round30_transfer_daily.csv"
)

SUM_OUTPUT_DIR = (
    ROOT_DIR
    / "pk10_number_sum_validation"
    / "number_sum_intraday_gate_outputs_db6y_daily85"
)
SUM_GATE_SUMMARY = SUM_OUTPUT_DIR / "intraday_gate_summary.csv"

NEGATIVE_DISCOUNT = 0.85
BS_SCENARIO = "bs_guardrail_daily85"
BS_OE_SCENARIO = "bs_plus_oe_mode_non_cash_daily85"
BS_SOURCE_STAKE = 50.0
DEFAULT_SIM_START = "2025-01-01"
DEFAULT_SIM_END = "2025-12-31"
DEFAULT_BANKROLL = 1000.0
DEFAULT_BASE_STAKE = 10.0
DEFAULT_SUM_CANDIDATE = "intraday_1007"
DEFAULT_MAX_MULTIPLIER = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a shared-bankroll three-play PK10 path for calendar year 2025.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--sum-candidate-id", default=DEFAULT_SUM_CANDIDATE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    return parser.parse_args()


def next_multiplier(current: int, max_multiplier: int, last_real_pnl: float) -> int:
    if last_real_pnl < 0.0:
        if current < 2:
            return min(2, max_multiplier)
        if current < 4:
            return min(4, max_multiplier)
        return min(5, max_multiplier)
    return 1


def settle_real(book_pnl_units: float) -> float:
    if book_pnl_units >= 0.0:
        return float(book_pnl_units)
    return float(book_pnl_units * NEGATIVE_DISCOUNT)


def load_bs_oe_frame(sim_start: pd.Timestamp, sim_end: pd.Timestamp, base_stake: float) -> pd.DataFrame:
    scale = base_stake / BS_SOURCE_STAKE
    raw = pd.read_csv(ROUND30_DAILY, parse_dates=["date"])
    keep = raw[raw["scenario"].isin([BS_SCENARIO, BS_OE_SCENARIO])].copy()
    pivot = (
        keep.pivot_table(index="date", columns="scenario", values="daily_real_pnl", aggfunc="first")
        .sort_index()
        .fillna(0.0)
    )
    date_range = pd.date_range(sim_start, sim_end, freq="D")
    pivot = pivot.reindex(date_range, fill_value=0.0)
    bs_base = pivot.get(BS_SCENARIO, pd.Series(0.0, index=date_range)).astype(float) * scale
    combo_base = pivot.get(BS_OE_SCENARIO, pd.Series(0.0, index=date_range)).astype(float) * scale
    out = pd.DataFrame(
        {
            "date": date_range,
            "bs_base_real_pnl": bs_base.values,
            "oe_base_real_pnl": (combo_base - bs_base).values,
        }
    )
    return out


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
        return raw_high >= float(candidate_row["raw_high_threshold"]) and mean_sum >= float(candidate_row["mean_sum_threshold"])
    if gate_family == "high_mid":
        return raw_high >= float(candidate_row["raw_high_threshold"]) and mid_share >= float(candidate_row["mid_share_threshold"])
    if gate_family == "mid_only":
        return mid_share >= float(candidate_row["mid_share_threshold"])
    raise ValueError(f"Unknown gate family: {gate_family}")


def load_sum_inputs(
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    candidate_id: str,
) -> tuple[pd.Series, pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    summary_df = pd.read_csv(SUM_GATE_SUMMARY)
    matched = summary_df[summary_df["candidate_id"] == candidate_id].copy()
    if matched.empty:
        raise ValueError(f"Missing intraday candidate: {candidate_id}")
    candidate_row = matched.iloc[0]

    baseline_name = str(candidate_row["baseline_name"])
    preview_cut = int(candidate_row["preview_cut"])
    detail_path = SUM_OUTPUT_DIR / f"{baseline_name}_cut{preview_cut}_intraday_detail.csv"
    detail_df = pd.read_csv(detail_path, parse_dates=["date"])

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

    date_range = pd.date_range(sim_start, sim_end, freq="D")
    daily_frame = pd.DataFrame({"date": date_range}).merge(grouped, on="date", how="left")
    daily_frame["split"] = daily_frame["split"].fillna("out_of_sample_gap")
    for col in [
        "requested_slots",
        "selected_score",
        "selected_mean_edge",
        "selected_symmetry_gap",
        "preview_raw_high_bias",
        "preview_mid_share",
        "preview_mean_sum",
    ]:
        daily_frame[col] = daily_frame[col].fillna(0.0)
    daily_frame["active"] = daily_frame["active"].fillna(False).astype(bool)

    sorted_details = detail_df.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in sorted_details.groupby("date")}
    return candidate_row, daily_frame, picks_by_date


def replay_three_play(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)
    max_multiplier = max(1, int(args.max_multiplier))

    bs_oe_frame = load_bs_oe_frame(sim_start=sim_start, sim_end=sim_end, base_stake=float(args.base_stake))
    sum_candidate_row, sum_frame, sum_picks_by_date = load_sum_inputs(
        sim_start=sim_start,
        sim_end=sim_end,
        candidate_id=args.sum_candidate_id,
    )

    combined = bs_oe_frame.merge(sum_frame, on="date", how="left")

    bankroll = float(args.start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0
    bs_multiplier = 1
    sum_multiplier = 1
    skipped_sum_due_to_cash = 0

    bs_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    sum_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    rows: list[dict[str, object]] = []

    for _, row in combined.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll

        bs_base_real = float(row["bs_base_real_pnl"])
        oe_base_real = float(row["oe_base_real_pnl"])
        bs_active = abs(bs_base_real) > 1e-12
        applied_bs_multiplier = bs_multiplier if bs_active else 0
        bs_real = bs_base_real * applied_bs_multiplier
        oe_real = oe_base_real
        if bs_active:
            bs_ladder_counts[bs_multiplier] += 1

        sum_requested_slots = int(row["requested_slots"]) if bool(row["active"]) else 0
        sum_funded_slots = 0
        sum_book_units = 0.0
        sum_real = 0.0
        affordable_sum_slots = int(bankroll_before // (float(args.base_stake) * sum_multiplier)) if sum_multiplier > 0 else 0

        if sum_requested_slots > 0:
            sum_funded_slots = min(sum_requested_slots, affordable_sum_slots)
            if sum_funded_slots > 0:
                picks = sum_picks_by_date.get(day, pd.DataFrame()).head(sum_funded_slots).copy()
                sum_book_units = float(picks["book_pnl"].sum()) if not picks.empty else 0.0
                sum_real = settle_real(sum_book_units * sum_multiplier) * float(args.base_stake)
                sum_ladder_counts[sum_multiplier] += 1
            else:
                skipped_sum_due_to_cash += 1

        total_real = bs_real + oe_real + sum_real
        bankroll += total_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "bs_active": bs_active,
                "bs_base_real_pnl": bs_base_real,
                "bs_multiplier": applied_bs_multiplier,
                "bs_real_pnl": bs_real,
                "oe_real_pnl": oe_real,
                "sum_active": bool(sum_requested_slots > 0),
                "sum_requested_slots": sum_requested_slots,
                "sum_affordable_slots": affordable_sum_slots,
                "sum_funded_slots": sum_funded_slots,
                "sum_multiplier": sum_multiplier if sum_requested_slots > 0 else 0,
                "sum_book_pnl_units": sum_book_units,
                "sum_real_pnl": sum_real,
                "total_real_pnl": total_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
                "sum_preview_raw_high_bias": float(row["preview_raw_high_bias"]),
                "sum_preview_mid_share": float(row["preview_mid_share"]),
                "sum_preview_mean_sum": float(row["preview_mean_sum"]),
            }
        )

        if bs_active:
            bs_multiplier = next_multiplier(bs_multiplier, max_multiplier=max_multiplier, last_real_pnl=bs_real)
        if sum_funded_slots > 0:
            sum_multiplier = next_multiplier(sum_multiplier, max_multiplier=max_multiplier, last_real_pnl=sum_real)

    daily_df = pd.DataFrame(rows)
    daily_df["month"] = daily_df["date"].dt.to_period("M").astype(str)
    monthly_df = (
        daily_df.groupby("month", as_index=False)
        .agg(
            bs_real_pnl=("bs_real_pnl", "sum"),
            oe_real_pnl=("oe_real_pnl", "sum"),
            sum_real_pnl=("sum_real_pnl", "sum"),
            total_real_pnl=("total_real_pnl", "sum"),
            bs_active_days=("bs_active", "sum"),
            sum_active_days=("sum_active", "sum"),
            sum_funded_slots=("sum_funded_slots", "sum"),
            month_end_bankroll=("bankroll_after_day", "last"),
            min_drawdown_from_peak=("drawdown_from_peak", "min"),
        )
    )

    summary_df = pd.DataFrame(
        [
            {
                "sim_start": str(sim_start.date()),
                "sim_end": str(sim_end.date()),
                "start_bankroll": float(args.start_bankroll),
                "base_stake": float(args.base_stake),
                "max_multiplier": max_multiplier,
                "sum_candidate_id": args.sum_candidate_id,
                "sum_gate_family": str(sum_candidate_row["gate_family"]),
                "sum_baseline_name": str(sum_candidate_row["baseline_name"]),
                "sum_preview_cut": int(sum_candidate_row["preview_cut"]),
                "days_in_simulation": int(daily_df.shape[0]),
                "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
                "net_profit": float(daily_df["total_real_pnl"].sum()),
                "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / float(args.start_bankroll) - 1.0) * 100.0),
                "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
                "min_bankroll": float(daily_df["bankroll_after_day"].min()),
                "max_drawdown": float(max_drawdown),
                "bs_profit": float(daily_df["bs_real_pnl"].sum()),
                "oe_profit": float(daily_df["oe_real_pnl"].sum()),
                "sum_profit": float(daily_df["sum_real_pnl"].sum()),
                "bs_active_days": int(daily_df["bs_active"].sum()),
                "sum_active_days": int(daily_df["sum_active"].sum()),
                "sum_funded_slots": int(daily_df["sum_funded_slots"].sum()),
                "skipped_sum_due_to_cash": skipped_sum_due_to_cash,
                "bs_days_1x": bs_ladder_counts[1],
                "bs_days_2x": bs_ladder_counts[2],
                "bs_days_4x": bs_ladder_counts[4],
                "bs_days_5x": bs_ladder_counts[5],
                "sum_days_1x": sum_ladder_counts[1],
                "sum_days_2x": sum_ladder_counts[2],
                "sum_days_4x": sum_ladder_counts[4],
                "sum_days_5x": sum_ladder_counts[5],
            }
        ]
    )
    return daily_df, monthly_df, summary_df


def write_report(path: Path, summary: pd.Series, monthly_df: pd.DataFrame) -> None:
    lines: list[str] = []
    lines.append("# Round36 Three-Play 2025 Replay")
    lines.append("")
    lines.append("- Shared bankroll across `big/small + odd/even + number-sum`.")
    lines.append("- Big/small uses `1x -> 2x -> 4x -> 5x`.")
    lines.append("- Odd/even stays fixed `1x` and is taken from the deployed `round32` daily mix.")
    lines.append("- Number-sum uses the intraday gate candidate listed in the summary, with its own independent `1x -> 2x -> 4x -> 5x` ladder.")
    lines.append("- `round32` source trace is linearly rescaled from stake `50` to stake `10`; this preserves the existing day-level settlement logic.")
    lines.append("")
    lines.append("## Summary")
    lines.append(
        f"- period `{summary['sim_start']} -> {summary['sim_end']}`, start bankroll `{summary['start_bankroll']:.2f}`, "
        f"base stake `{summary['base_stake']:.2f}`, final bankroll `{summary['final_bankroll']:.2f}`, "
        f"net profit `{summary['net_profit']:.2f}`, ROI `{summary['roi_on_start_bankroll_pct']:.2f}%`."
    )
    lines.append(
        f"- peak `{summary['peak_bankroll']:.2f}`, min bankroll `{summary['min_bankroll']:.2f}`, "
        f"max drawdown `{summary['max_drawdown']:.2f}`."
    )
    lines.append(
        f"- contribution split: BS `{summary['bs_profit']:.2f}`, OE `{summary['oe_profit']:.2f}`, "
        f"SUM `{summary['sum_profit']:.2f}`."
    )
    lines.append(
        f"- BS ladder days `1x={int(summary['bs_days_1x'])}, 2x={int(summary['bs_days_2x'])}, 4x={int(summary['bs_days_4x'])}, 5x={int(summary['bs_days_5x'])}`."
    )
    lines.append(
        f"- SUM ladder days `1x={int(summary['sum_days_1x'])}, 2x={int(summary['sum_days_2x'])}, 4x={int(summary['sum_days_4x'])}, 5x={int(summary['sum_days_5x'])}`."
    )
    lines.append("")
    lines.append("## Monthly")
    for _, row in monthly_df.iterrows():
        lines.append(
            f"- `{row['month']}` total `{row['total_real_pnl']:.2f}` "
            f"(BS `{row['bs_real_pnl']:.2f}`, OE `{row['oe_real_pnl']:.2f}`, SUM `{row['sum_real_pnl']:.2f}`), "
            f"month-end bankroll `{row['month_end_bankroll']:.2f}`."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    daily_df, monthly_df, summary_df = replay_three_play(args)
    summary = summary_df.iloc[0]
    sim_start_txt = str(pd.Timestamp(args.sim_start).date())
    sim_end_txt = str(pd.Timestamp(args.sim_end).date())

    stem = (
        f"three_play_{args.sum_candidate_id}_bankroll_{int(args.start_bankroll)}"
        f"_stake_{int(args.base_stake)}_m{int(args.max_multiplier)}_{sim_start_txt}_{sim_end_txt}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    monthly_path = OUTPUT_DIR / f"{stem}_monthly.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    report_path = OUTPUT_DIR / f"{stem}_report.md"

    daily_df.to_csv(daily_path, index=False)
    monthly_df.to_csv(monthly_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    write_report(report_path, summary=summary, monthly_df=monthly_df)

    print(report_path)
    print(summary_path)
    print(monthly_path)
    print(daily_path)


if __name__ == "__main__":
    main()
