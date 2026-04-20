#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ROUND30_FILE = ROOT_DIR / "pk10_round30_daily85_exact_transfer" / "pk10_round30_daily85_exact_transfer.py"
ROUND9_FILE = ROOT_DIR / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py"
ROUND16_FILE = ROOT_DIR / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py"
ROUND36_FILE = BASE_DIR / "pk10_round36_three_play_2025_replay.py"

SUM_VALIDATION_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_validation.py"
SUM_REFINEMENT_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_refinement.py"
SUM_INTRADAY_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_intraday_gate.py"

NUMBER_WINDOW_FILE = ROOT_DIR / "tmp_number_validation" / "pk10_number_daily_window_validation.py"
NUMBER_WINDOW_DIR = NUMBER_WINDOW_FILE.parent

SUM_OUTPUT_CANDIDATE_PATHS = (
    ROOT_DIR / "pk10_number_sum_validation" / "number_sum_intraday_gate_outputs_local_pks_3306_20260417" / "intraday_gate_summary.csv",
    ROOT_DIR / "pk10_number_sum_validation" / "number_sum_intraday_gate_outputs_db6y_daily85" / "intraday_gate_summary.csv",
)

DEFAULT_SIM_START = "2026-04-06"
DEFAULT_SIM_END = "2026-04-12"
DEFAULT_QUERY_START = "2024-01-01"
DEFAULT_QUERY_END = "2026-04-12"
DEFAULT_BANKROLL = 1000.0
DEFAULT_BASE_STAKE = 10.0
DEFAULT_MAX_MULTIPLIER = 5
DEFAULT_SUM_CANDIDATE = "intraday_1007"

SOURCE_DB_HOST = "127.0.0.1"
SOURCE_DB_PORT = 3306
SOURCE_DB_USER = "root"
SOURCE_DB_PASS = ""
SOURCE_DB_NAME = "xyft_lottery_data"
SOURCE_TABLE = "pks_history"

EXACT_DAILY_WINDOW_ID = "exactdw_001"
EXACT_BASE_GATE_ID = "late|big|center|same_top1_prev=all"
EXACT_OBS_WINDOW = 192
EXACT_EXECUTION_RULE = "front_singleton_exact_q75_only"
EXACT_NET_WIN = 8.9


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a shared-bankroll four-play PK10 interval with number daily window.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--query-start", default=DEFAULT_QUERY_START)
    parser.add_argument("--query-end", default=DEFAULT_QUERY_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    parser.add_argument("--sum-candidate-id", default=DEFAULT_SUM_CANDIDATE)
    return parser.parse_args()


def week_starts_for_interval(sim_start: pd.Timestamp, sim_end: pd.Timestamp) -> list[str]:
    day_range = pd.date_range(sim_start, sim_end, freq="D")
    starts = sorted({(day - pd.Timedelta(days=int(day.weekday()))).strftime("%Y-%m-%d") for day in day_range})
    return starts


def load_issue_history(vmod, query_start: str, query_end: str) -> pd.DataFrame:
    return vmod.load_issue_history_from_db(
        db_host=SOURCE_DB_HOST,
        db_port=SOURCE_DB_PORT,
        db_user=SOURCE_DB_USER,
        db_pass=SOURCE_DB_PASS,
        db_name=SOURCE_DB_NAME,
        table=SOURCE_TABLE,
        date_start=query_start,
        date_end=query_end,
    )


def load_sum_candidate_row(candidate_id: str) -> pd.Series:
    for path in SUM_OUTPUT_CANDIDATE_PATHS:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        matched = df[df["candidate_id"] == candidate_id].copy()
        if not matched.empty:
            return matched.iloc[0]
    raise RuntimeError(f"Missing sum intraday candidate row for {candidate_id}")


def aggregate_sum_daily(detail_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    detail = detail_df.copy()
    detail["date"] = pd.to_datetime(detail["date"])
    grouped = (
        detail.groupby(["date", "split"], as_index=False)
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
    picks = detail.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in picks.groupby("date")}
    return grouped, picks_by_date


def build_bs_oe_frame(
    round30_mod,
    round9_mod,
    round16_mod,
    issue_df: pd.DataFrame,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_stake: float,
) -> pd.DataFrame:
    week_starts = week_starts_for_interval(sim_start, sim_end)

    bs_bundle = round9_mod.preprocess_history(issue_df)
    bs_core = round30_mod.make_round9_candidate(
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
    bs_expansion = round30_mod.make_round9_candidate(
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
    bs_signal_states, bs_uniform, bs_balanced = round30_mod.build_signal_states(round9_mod, bs_bundle, [bs_core, bs_expansion])
    bs_core_series = round9_mod.evaluate_candidate_series(bs_core, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9_mod.evaluate_candidate_series(bs_expansion, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)

    round9_mod.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle = round16_mod.preprocess_odd_even(round9_mod, issue_df)
    oe_candidate = round30_mod.make_round9_candidate(
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
    oe_signal_states, oe_uniform, oe_balanced = round30_mod.build_signal_states(round9_mod, oe_bundle, [oe_candidate])
    oe_series = round9_mod.evaluate_candidate_series(oe_candidate, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    policy_df = round30_mod.read_round10_policy(ROOT_DIR)
    policy_df = policy_df[policy_df["week_start"].isin(week_starts)].copy().reset_index(drop=True)
    oe_gate_df = round30_mod.read_round21_gate_trace(ROOT_DIR)
    oe_gate_df = oe_gate_df[oe_gate_df["week_start"].isin(week_starts)].copy().reset_index(drop=True)
    if policy_df.empty or oe_gate_df.empty:
        raise RuntimeError(f"Missing weekly policy rows for interval weeks: {week_starts}")

    bs_core_daily = round30_mod.build_daily_component_trace(bs_bundle, bs_core_series, policy_df, "bs_core")
    bs_exp_daily = round30_mod.build_daily_component_trace(bs_bundle, bs_exp_series, policy_df, "bs_expansion")
    oe_daily = round30_mod.build_daily_component_trace(oe_bundle, oe_series, oe_gate_df, "oe_mode_non_cash_base")

    bs_mode_map = policy_df.set_index("week_start")["mode"].to_dict()
    bs_rows: list[dict[str, object]] = []
    for week in policy_df["week_start"].tolist():
        core_week = round30_mod.apply_daily85(bs_core_daily[bs_core_daily["week_start"] == week].copy())
        exp_week = round30_mod.apply_daily85(bs_exp_daily[bs_exp_daily["week_start"] == week].copy())
        mode = bs_mode_map[week]
        for day in range(1, 8):
            core_row = core_week[core_week["day_index_in_week"] == day].iloc[0]
            exp_row = exp_week[exp_week["day_index_in_week"] == day].iloc[0]
            if mode == "core":
                real = float(core_row["daily_real_unit"])
            elif mode == "core_plus_expansion":
                real = float(core_row["daily_real_unit"] + exp_row["daily_real_unit"])
            else:
                real = 0.0
            bs_rows.append({"date": pd.Timestamp(core_row["date"]), "bs_real_unit": real})
    bs_daily = pd.DataFrame(bs_rows)

    oe_active_map = oe_gate_df.set_index("week_start")["active"].astype(int).to_dict()
    oe_rows: list[dict[str, object]] = []
    for week in oe_gate_df["week_start"].tolist():
        oe_week = round30_mod.apply_daily85(oe_daily[oe_daily["week_start"] == week].copy())
        active = oe_active_map[week] == 1
        for day in range(1, 8):
            oe_row = oe_week[oe_week["day_index_in_week"] == day].iloc[0]
            real = float(oe_row["daily_real_unit"]) if active else 0.0
            oe_rows.append({"date": pd.Timestamp(oe_row["date"]), "oe_real_unit": real})
    oe_daily_frame = pd.DataFrame(oe_rows)

    out = bs_daily.merge(oe_daily_frame, on="date", how="left")
    out["oe_real_unit"] = out["oe_real_unit"].fillna(0.0)
    out["bs_base_real_pnl"] = out["bs_real_unit"] * (base_stake / round30_mod.STAKE_PER_BET)
    out["oe_base_real_pnl"] = out["oe_real_unit"] * (base_stake / round30_mod.STAKE_PER_BET)
    out = out[(out["date"] >= sim_start) & (out["date"] <= sim_end)].copy()
    return out[["date", "bs_base_real_pnl", "oe_base_real_pnl"]].sort_values("date").reset_index(drop=True)


def build_sum_inputs(vmod, rmod, intraday_mod, issue_df: pd.DataFrame, candidate_row: pd.Series) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    sum_bundle = vmod.preprocess_exact_sum(issue_df)
    baseline_lookup = {cfg.name: cfg for cfg in intraday_mod.baseline_configs()}
    baseline_name = str(candidate_row["baseline_name"])
    preview_cut = int(candidate_row["preview_cut"])
    if baseline_name not in baseline_lookup:
        raise RuntimeError(f"Missing sum baseline config: {baseline_name}")
    _, detail_df = intraday_mod.build_intraday_base_series(vmod, rmod, sum_bundle, baseline_lookup[baseline_name], preview_cut)
    return aggregate_sum_daily(detail_df)


def build_exact_inputs(number_window_mod, round9_mod, issue_df: pd.DataFrame, sim_start: pd.Timestamp, sim_end: pd.Timestamp) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    bundle = number_window_mod.preprocess_number_history(issue_df, round9_mod)
    candidate = number_window_mod.build_dynamic_pair_candidate(round9_mod)
    counts, exposures = round9_mod.get_bucket_counts(bundle.round9_bundle, candidate.bucket_model)
    signal_state = round9_mod.compute_signal_state(
        counts=counts,
        exposures=exposures,
        lookback_weeks=candidate.lookback_weeks,
        prior_strength=candidate.prior_strength,
        score_model=candidate.score_model,
    )
    subgroup_state_df = number_window_mod.build_fixed_slot_state_tables(
        bundle=bundle,
        round9=round9_mod,
        signal_state=signal_state,
        candidate=candidate,
        late_slots=number_window_mod.parse_csv_ints(number_window_mod.DEFAULT_LATE_SLOTS),
        control_slots=number_window_mod.parse_csv_ints(number_window_mod.DEFAULT_CONTROL_SLOTS),
        half_prior_strength=number_window_mod.DEFAULT_HALF_PRIOR_STRENGTH,
    )
    front_state_df = number_window_mod.build_daily_front_state(
        bundle=bundle,
        subgroup_state_df=subgroup_state_df,
        obs_windows=number_window_mod.OBS_WINDOWS,
        round9=round9_mod,
    )
    rule_state_df = number_window_mod.build_daily_rule_state(front_state_df)

    filtered = rule_state_df[
        (rule_state_df["base_gate_id"] == EXACT_BASE_GATE_ID)
        & (rule_state_df["obs_window"] == EXACT_OBS_WINDOW)
    ].copy()
    if filtered.empty:
        raise RuntimeError("Exact daily-window rule_state is empty for fixed candidate")

    rule_col = f"rule_{EXACT_EXECUTION_RULE}"
    if rule_col not in filtered.columns:
        raise RuntimeError(f"Missing exact execution rule column: {rule_col}")

    filtered["execute_exact"] = filtered[rule_col].astype(bool)
    filtered["selected_number_exec"] = filtered.apply(
        lambda row: number_window_mod.selected_number_for_rule(EXACT_EXECUTION_RULE, row),
        axis=1,
    )
    filtered["exact_hit_exec"] = (
        filtered["execute_exact"] & (filtered["target_number"] == filtered["selected_number_exec"])
    ).astype(int)
    filtered["cell_book_pnl_units"] = filtered["exact_hit_exec"].map(lambda hit: EXACT_NET_WIN if int(hit) == 1 else -1.0)
    filtered["day_date"] = pd.to_datetime(filtered["day_date"])

    active_cells = filtered[filtered["execute_exact"]].copy()
    grouped = (
        active_cells.groupby(["day_date", "split"], as_index=False)
        .agg(
            issue_exposures=("execute_exact", "sum"),
            exact_hits_count=("exact_hit_exec", "sum"),
        )
        .sort_values("day_date")
        .reset_index(drop=True)
    )
    picks_by_date = {pd.Timestamp(day): frame.sort_values(["slot_1based"], kind="stable").reset_index(drop=True) for day, frame in active_cells.groupby("day_date")}

    full_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    daily_frame = full_range.merge(grouped.rename(columns={"day_date": "date"}), on="date", how="left")
    daily_frame["split"] = daily_frame["split"].fillna("out_of_sample_gap")
    daily_frame["issue_exposures"] = daily_frame["issue_exposures"].fillna(0).astype(int)
    daily_frame["exact_hits_count"] = daily_frame["exact_hits_count"].fillna(0).astype(int)
    return daily_frame, picks_by_date


def build_svg(series_map: dict[str, pd.DataFrame], output_path: Path, title: str) -> None:
    width, height = 1200, 520
    left, right, top, bottom = 70, 30, 40, 55
    inner_w = width - left - right
    inner_h = height - top - bottom
    colors = ["#1d4ed8", "#dc2626", "#0f766e", "#7c3aed"]

    all_values: list[float] = []
    for df in series_map.values():
        all_values.extend(df["bankroll_after_day"].astype(float).tolist())
    min_v = min(all_values)
    max_v = max(all_values)
    if math.isclose(min_v, max_v):
        min_v -= 1.0
        max_v += 1.0
    pad = (max_v - min_v) * 0.08
    min_v -= pad
    max_v += pad

    def x_at(idx: int, n: int) -> float:
        if n <= 1:
            return left + inner_w / 2.0
        return left + inner_w * idx / (n - 1)

    def y_at(value: float) -> float:
        return top + inner_h * (1.0 - (value - min_v) / (max_v - min_v))

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='white' />",
        f"<text x='{left}' y='24' font-size='18' font-family='Arial, sans-serif' fill='#111827'>{title}</text>",
        f"<line x1='{left}' y1='{top + inner_h}' x2='{left + inner_w}' y2='{top + inner_h}' stroke='#9ca3af' stroke-width='1' />",
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + inner_h}' stroke='#9ca3af' stroke-width='1' />",
    ]

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        value = min_v + (max_v - min_v) * frac
        y = y_at(value)
        lines.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left + inner_w}' y2='{y:.2f}' stroke='#e5e7eb' stroke-width='1' />")
        lines.append(f"<text x='{left - 10}' y='{y + 4:.2f}' text-anchor='end' font-size='11' font-family='Arial, sans-serif' fill='#4b5563'>{value:.1f}</text>")

    sample_df = next(iter(series_map.values()))
    for idx, day in enumerate(sample_df["date"].dt.strftime("%m-%d").tolist()):
        lines.append(f"<text x='{x_at(idx, len(sample_df)):.2f}' y='{top + inner_h + 20}' text-anchor='middle' font-size='11' font-family='Arial, sans-serif' fill='#4b5563'>{day}</text>")

    legend_x = left + 10
    legend_y = top + 10
    for idx, (label, df) in enumerate(series_map.items()):
        color = colors[idx % len(colors)]
        points = " ".join(
            f"{x_at(i, len(df)):.2f},{y_at(v):.2f}" for i, v in enumerate(df["bankroll_after_day"].astype(float).tolist())
        )
        lines.append(f"<polyline fill='none' stroke='{color}' stroke-width='2.5' points='{points}' />")
        ly = legend_y + idx * 18
        lines.append(f"<line x1='{legend_x}' y1='{ly}' x2='{legend_x + 20}' y2='{ly}' stroke='{color}' stroke-width='2.5' />")
        lines.append(f"<text x='{legend_x + 28}' y='{ly + 4}' font-size='12' font-family='Arial, sans-serif' fill='#111827'>{label}</text>")

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def replay_four_play(
    round36_mod,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    start_bankroll: float,
    base_stake: float,
    max_multiplier: int,
    sum_candidate_row: pd.Series,
    bs_oe_frame: pd.DataFrame,
    sum_grouped: pd.DataFrame,
    sum_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    exact_frame: pd.DataFrame,
    exact_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    full_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})

    sum_daily = full_range.merge(sum_grouped, on="date", how="left")
    sum_daily["split"] = sum_daily["split"].fillna("out_of_sample_gap")
    for col in [
        "requested_slots",
        "selected_score",
        "selected_mean_edge",
        "selected_symmetry_gap",
        "preview_raw_high_bias",
        "preview_mid_share",
        "preview_mean_sum",
    ]:
        sum_daily[col] = sum_daily[col].fillna(0.0)
    sum_daily["active"] = sum_daily.apply(lambda row: round36_mod.gate_is_on(row, sum_candidate_row), axis=1)

    combined = (
        full_range.merge(bs_oe_frame, on="date", how="left")
        .merge(sum_daily, on="date", how="left", suffixes=("", "_sum"))
        .merge(exact_frame, on="date", how="left")
    )
    combined["bs_base_real_pnl"] = combined["bs_base_real_pnl"].fillna(0.0)
    combined["oe_base_real_pnl"] = combined["oe_base_real_pnl"].fillna(0.0)
    combined["issue_exposures"] = combined["issue_exposures"].fillna(0).astype(int)
    combined["exact_hits_count"] = combined["exact_hits_count"].fillna(0).astype(int)

    bankroll = float(start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0

    bs_multiplier = 1
    sum_multiplier = 1
    exact_multiplier = 1

    bs_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    sum_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    exact_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    skipped_sum_due_to_cash = 0
    skipped_exact_due_to_cash = 0

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
        affordable_sum_slots = int(bankroll_before // (base_stake * sum_multiplier)) if sum_multiplier > 0 else 0
        if sum_requested_slots > 0:
            sum_funded_slots = min(sum_requested_slots, affordable_sum_slots)
            if sum_funded_slots > 0:
                picks = sum_picks_by_date.get(day, pd.DataFrame()).head(sum_funded_slots).copy()
                sum_book_units = float(picks["book_pnl"].sum()) if not picks.empty else 0.0
                sum_real = round36_mod.settle_real(sum_book_units * sum_multiplier) * base_stake
                sum_ladder_counts[sum_multiplier] += 1
            else:
                skipped_sum_due_to_cash += 1

        exact_requested_slots = int(row["issue_exposures"])
        exact_funded_slots = 0
        exact_book_units = 0.0
        exact_real = 0.0
        affordable_exact_slots = int(bankroll_before // (base_stake * exact_multiplier)) if exact_multiplier > 0 else 0
        if exact_requested_slots > 0:
            exact_funded_slots = min(exact_requested_slots, affordable_exact_slots)
            if exact_funded_slots > 0:
                exact_picks = exact_picks_by_date.get(day, pd.DataFrame()).head(exact_funded_slots).copy()
                exact_book_units = float(exact_picks["cell_book_pnl_units"].sum()) if not exact_picks.empty else 0.0
                exact_real = round36_mod.settle_real(exact_book_units * exact_multiplier) * base_stake
                exact_ladder_counts[exact_multiplier] += 1
            else:
                skipped_exact_due_to_cash += 1

        total_real = bs_real + oe_real + sum_real + exact_real
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
                "exact_active": bool(exact_requested_slots > 0),
                "exact_requested_slots": exact_requested_slots,
                "exact_affordable_slots": affordable_exact_slots,
                "exact_funded_slots": exact_funded_slots,
                "exact_multiplier": exact_multiplier if exact_requested_slots > 0 else 0,
                "exact_book_pnl_units": exact_book_units,
                "exact_real_pnl": exact_real,
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
            bs_multiplier = round36_mod.next_multiplier(bs_multiplier, max_multiplier=max_multiplier, last_real_pnl=bs_real)
        if sum_funded_slots > 0:
            sum_multiplier = round36_mod.next_multiplier(sum_multiplier, max_multiplier=max_multiplier, last_real_pnl=sum_real)
        if exact_funded_slots > 0:
            exact_multiplier = round36_mod.next_multiplier(exact_multiplier, max_multiplier=max_multiplier, last_real_pnl=exact_real)

    daily_df = pd.DataFrame(rows)
    summary_df = pd.DataFrame(
        [
            {
                "sim_start": str(sim_start.date()),
                "sim_end": str(sim_end.date()),
                "start_bankroll": start_bankroll,
                "base_stake": base_stake,
                "max_multiplier": max_multiplier,
                "source_table": SOURCE_TABLE,
                "sum_candidate_id": str(sum_candidate_row["candidate_id"]),
                "sum_gate_family": str(sum_candidate_row["gate_family"]),
                "sum_baseline_name": str(sum_candidate_row["baseline_name"]),
                "sum_preview_cut": int(sum_candidate_row["preview_cut"]),
                "exact_daily_window_id": EXACT_DAILY_WINDOW_ID,
                "exact_base_gate_id": EXACT_BASE_GATE_ID,
                "exact_obs_window": EXACT_OBS_WINDOW,
                "exact_execution_rule": EXACT_EXECUTION_RULE,
                "exact_net_win": EXACT_NET_WIN,
                "days_in_simulation": int(daily_df.shape[0]),
                "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
                "net_profit": float(daily_df["total_real_pnl"].sum()),
                "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / start_bankroll - 1.0) * 100.0),
                "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
                "min_bankroll": float(daily_df["bankroll_after_day"].min()),
                "max_drawdown": float(max_drawdown),
                "bs_profit": float(daily_df["bs_real_pnl"].sum()),
                "oe_profit": float(daily_df["oe_real_pnl"].sum()),
                "sum_profit": float(daily_df["sum_real_pnl"].sum()),
                "exact_profit": float(daily_df["exact_real_pnl"].sum()),
                "bs_active_days": int(daily_df["bs_active"].sum()),
                "sum_active_days": int(daily_df["sum_active"].sum()),
                "exact_active_days": int(daily_df["exact_active"].sum()),
                "sum_funded_slots": int(daily_df["sum_funded_slots"].sum()),
                "exact_funded_slots": int(daily_df["exact_funded_slots"].sum()),
                "skipped_sum_due_to_cash": skipped_sum_due_to_cash,
                "skipped_exact_due_to_cash": skipped_exact_due_to_cash,
                "bs_days_1x": bs_ladder_counts[1],
                "bs_days_2x": bs_ladder_counts[2],
                "bs_days_4x": bs_ladder_counts[4],
                "bs_days_5x": bs_ladder_counts[5],
                "sum_days_1x": sum_ladder_counts[1],
                "sum_days_2x": sum_ladder_counts[2],
                "sum_days_4x": sum_ladder_counts[4],
                "sum_days_5x": sum_ladder_counts[5],
                "exact_days_1x": exact_ladder_counts[1],
                "exact_days_2x": exact_ladder_counts[2],
                "exact_days_4x": exact_ladder_counts[4],
                "exact_days_5x": exact_ladder_counts[5],
            }
        ]
    )
    return daily_df, summary_df


def main() -> None:
    args = parse_args()
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)

    if str(NUMBER_WINDOW_DIR) not in sys.path:
        sys.path.insert(0, str(NUMBER_WINDOW_DIR))

    round30_mod = import_module(ROUND30_FILE, "round30_for_round36_four_play")
    round9_mod = import_module(ROUND9_FILE, "round9_for_round36_four_play")
    round16_mod = import_module(ROUND16_FILE, "round16_for_round36_four_play")
    round36_mod = import_module(ROUND36_FILE, "round36_for_round36_four_play")
    vmod = import_module(SUM_VALIDATION_FILE, "sum_validation_for_round36_four_play")
    rmod = import_module(SUM_REFINEMENT_FILE, "sum_refinement_for_round36_four_play")
    intraday_mod = import_module(SUM_INTRADAY_FILE, "sum_intraday_for_round36_four_play")
    number_window_mod = import_module(NUMBER_WINDOW_FILE, "number_daily_window_for_round36_four_play")

    issue_df = load_issue_history(vmod, query_start=args.query_start, query_end=args.query_end)
    if issue_df.empty:
        raise RuntimeError("Issue history query returned no rows")

    sum_candidate_row = load_sum_candidate_row(args.sum_candidate_id)
    bs_oe_frame = build_bs_oe_frame(
        round30_mod=round30_mod,
        round9_mod=round9_mod,
        round16_mod=round16_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
        base_stake=float(args.base_stake),
    )
    sum_grouped, sum_picks_by_date = build_sum_inputs(
        vmod=vmod,
        rmod=rmod,
        intraday_mod=intraday_mod,
        issue_df=issue_df,
        candidate_row=sum_candidate_row,
    )
    exact_frame, exact_picks_by_date = build_exact_inputs(
        number_window_mod=number_window_mod,
        round9_mod=round9_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
    )

    daily_df, summary_df = replay_four_play(
        round36_mod=round36_mod,
        sim_start=sim_start,
        sim_end=sim_end,
        start_bankroll=float(args.start_bankroll),
        base_stake=float(args.base_stake),
        max_multiplier=max(1, int(args.max_multiplier)),
        sum_candidate_row=sum_candidate_row,
        bs_oe_frame=bs_oe_frame,
        sum_grouped=sum_grouped,
        sum_picks_by_date=sum_picks_by_date,
        exact_frame=exact_frame,
        exact_picks_by_date=exact_picks_by_date,
    )

    stem = (
        f"four_play_{args.sum_candidate_id}_{EXACT_DAILY_WINDOW_ID}"
        f"_bankroll_{int(args.start_bankroll)}_stake_{int(args.base_stake)}"
        f"_m{int(args.max_multiplier)}_pks_history_{sim_start.date()}_{sim_end.date()}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    daily_df.to_csv(daily_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    print(summary_path)
    print(daily_path)


if __name__ == "__main__":
    main()
