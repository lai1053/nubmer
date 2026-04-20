#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import time
import importlib.util
import math
import os
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ROUND36_FILE = BASE_DIR / "pk10_round36_three_play_2025_replay.py"
ROUND35_FILE = ROOT_DIR / "pk10_round35_daily_deployment_refinement" / "pk10_round35_daily_deployment_refinement.py"
ROUND35_TRACE = (
    ROOT_DIR
    / "pk10_round35_daily_deployment_refinement"
    / "round35_outputs"
    / "round35_best_trace.csv"
)
ROUND9_FILE = ROOT_DIR / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py"
ROUND16_FILE = ROOT_DIR / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py"

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
DEFAULT_FACE_POLICY_ID = "core40_spread_only__exp0_off__oe40_spread_only__cd2"
DEFAULT_SUM_CANDIDATE = "intraday_1037"
DEFAULT_EXACT_WINDOW_ID = "exactdw_frozen_edge_low_consensus_obs192"
DEFAULT_EXACT_BASE_GATE_ID = "late|big|edge_low|same_top1_prev=all"
DEFAULT_EXACT_OBS_WINDOW = 192
DEFAULT_EXACT_EXECUTION_RULE = "front_pair_major_consensus_only"
DEFAULT_EXACT_NET_WIN = 8.9
DEFAULT_EXACT_STAKING_MODE = "martingale"
DEFAULT_BLACKOUT_START = ""
DEFAULT_BLACKOUT_END = ""

SOURCE_DB_HOST = os.environ.get("PK10_SOURCE_DB_HOST", "127.0.0.1")
SOURCE_DB_PORT = int(os.environ.get("PK10_SOURCE_DB_PORT", "3306"))
SOURCE_DB_USER = os.environ.get("PK10_SOURCE_DB_USER", "root")
SOURCE_DB_PASS = os.environ.get("PK10_SOURCE_DB_PASS", "")
SOURCE_DB_NAME = os.environ.get("PK10_SOURCE_DB_NAME", "xyft_lottery_data")
SOURCE_TABLE = os.environ.get("PK10_SOURCE_TABLE", "pks_history")


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay an aligned shared-bankroll PK10 path for face + sum + exact.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--query-start", default=DEFAULT_QUERY_START)
    parser.add_argument("--query-end", default=DEFAULT_QUERY_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    parser.add_argument("--face-policy-id", default=DEFAULT_FACE_POLICY_ID)
    parser.add_argument("--sum-candidate-id", default=DEFAULT_SUM_CANDIDATE)
    parser.add_argument("--exact-window-id", default=DEFAULT_EXACT_WINDOW_ID)
    parser.add_argument("--exact-base-gate-id", default=DEFAULT_EXACT_BASE_GATE_ID)
    parser.add_argument("--exact-obs-window", type=int, default=DEFAULT_EXACT_OBS_WINDOW)
    parser.add_argument("--exact-execution-rule", default=DEFAULT_EXACT_EXECUTION_RULE)
    parser.add_argument("--exact-net-win", type=float, default=DEFAULT_EXACT_NET_WIN)
    parser.add_argument("--exact-staking-mode", choices=("martingale", "fixed"), default=DEFAULT_EXACT_STAKING_MODE)
    parser.add_argument("--blackout-start", default=DEFAULT_BLACKOUT_START)
    parser.add_argument("--blackout-end", default=DEFAULT_BLACKOUT_END)
    return parser.parse_args()


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


def parse_time_of_day(text: str) -> time | None:
    value = str(text).strip()
    if not value:
        return None
    return pd.Timestamp(f"2000-01-01 {value}").time()


def complete_week_query_end(sim_end: pd.Timestamp, requested_query_end: str) -> pd.Timestamp:
    requested = pd.Timestamp(requested_query_end)
    week_end = sim_end + pd.Timedelta(days=int(6 - sim_end.weekday()))
    return max(requested, week_end)


def build_issue_schedule_frame(issue_df: pd.DataFrame) -> pd.DataFrame:
    work = issue_df.copy()
    work["draw_date"] = pd.to_datetime(work["draw_date"], format="%Y-%m-%d")
    time_text = work["pre_draw_time"].astype(str).str.extract(r"(\d{2}:\d{2}:\d{2})", expand=False)
    time_text = time_text.fillna(work["pre_draw_time"].astype(str))
    work["draw_ts"] = pd.to_datetime(
        work["draw_date"].dt.strftime("%Y-%m-%d") + " " + time_text,
        format="%Y-%m-%d %H:%M:%S",
    )
    work = work.sort_values(["draw_date", "draw_ts", "pre_draw_issue"]).reset_index(drop=True)
    day_counts = work.groupby("draw_date").size()
    expected_per_day = int(day_counts.mode().iloc[0])
    complete_days = day_counts[day_counts == expected_per_day].index
    work = work[work["draw_date"].isin(complete_days)].copy()
    work["issue_idx_in_day"] = work.groupby("draw_date").cumcount()
    work["slot_1based"] = work["issue_idx_in_day"] + 1
    iso = work["draw_date"].dt.isocalendar()
    work["iso_year"] = iso["year"].astype(int)
    work["iso_week"] = iso["week"].astype(int)
    work["week_id"] = work["iso_year"].astype(str) + "-W" + work["iso_week"].astype(str).str.zfill(2)
    week_days = work.groupby("week_id")["draw_date"].nunique()
    complete_weeks = week_days[week_days == 7].index
    work = work[work["week_id"].isin(complete_weeks)].copy()
    valid_week_ids = (
        work.groupby("week_id", sort=True)["draw_date"]
        .min()
        .sort_values()
        .index
        .tolist()
    )
    work["week_id"] = pd.Categorical(work["week_id"], categories=valid_week_ids, ordered=True)
    work = work.sort_values(["week_id", "draw_date", "issue_idx_in_day"]).reset_index(drop=True)
    return work[["draw_date", "draw_ts", "issue_idx_in_day", "slot_1based", "week_id"]].copy()


def build_allowed_trade_lookup(
    schedule_df: pd.DataFrame,
    blackout_start: time | None,
    blackout_end: time | None,
) -> pd.DataFrame:
    out = schedule_df.copy()
    out["allowed_trade"] = True
    if blackout_start is not None and blackout_end is not None:
        times = out["draw_ts"].dt.time
        out["allowed_trade"] = ~((times >= blackout_start) & (times < blackout_end))
    out["date"] = pd.to_datetime(out["draw_date"])
    return out[["date", "draw_ts", "issue_idx_in_day", "slot_1based", "week_id", "allowed_trade"]].copy()


def build_allowed_mask_cube(allowed_lookup: pd.DataFrame, bundle) -> pd.DataFrame:
    week_meta = (
        allowed_lookup.groupby("week_id", sort=True)["date"]
        .agg(["min", "max", "nunique"])
        .rename(columns={"min": "week_start", "max": "week_end", "nunique": "n_days"})
        .reset_index()
        .sort_values("week_start")
        .reset_index(drop=True)
    )
    if int(week_meta["n_days"].min()) != 7 or int(week_meta["n_days"].max()) != 7:
        raise RuntimeError("Allowed-trade lookup does not contain complete weeks only")
    expected_rows = len(week_meta) * 7 * int(bundle.n_slots)
    if len(allowed_lookup) != expected_rows:
        raise RuntimeError(f"Allowed-trade lookup row count mismatch: got {len(allowed_lookup)}, expected {expected_rows}")
    schedule_week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    if len(schedule_week_start) != len(bundle.week_start) or not (schedule_week_start == bundle.week_start).all():
        raise RuntimeError("Allowed-trade lookup week alignment mismatch with face bundle")
    return allowed_lookup["allowed_trade"].to_numpy(dtype=bool).reshape(len(week_meta), 7, int(bundle.n_slots))


def parse_face_policy_id(policy_id: str) -> tuple[tuple[int, str], tuple[int, str], tuple[int, str], int]:
    parts = policy_id.split("__")
    if len(parts) != 4:
        raise RuntimeError(f"Unsupported face policy id: {policy_id}")
    core_part, exp_part, oe_part, cd_part = parts
    if not (core_part.startswith("core") and exp_part.startswith("exp") and oe_part.startswith("oe") and cd_part.startswith("cd")):
        raise RuntimeError(f"Unsupported face policy id: {policy_id}")

    def parse_leg(text: str, prefix: str) -> tuple[int, str]:
        tail = text[len(prefix):]
        number_text, family = tail.split("_", 1)
        return int(number_text), family

    core_cfg = parse_leg(core_part, "core")
    exp_cfg = parse_leg(exp_part, "exp")
    oe_cfg = parse_leg(oe_part, "oe")
    cooldown = int(cd_part[2:])
    return core_cfg, exp_cfg, oe_cfg, cooldown


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


def day_ledger_from_positions_with_mask(
    week_cube,
    selected_positions_meta,
    week_allowed_mask,
) -> tuple[pd.Series, pd.Series]:
    daily_ledger = pd.Series(0.0, index=range(week_cube.shape[0]), dtype=float)
    daily_bets = pd.Series(0.0, index=range(week_cube.shape[0]), dtype=float)
    if selected_positions_meta is None:
        return daily_ledger, daily_bets
    for payload in selected_positions_meta:
        if not payload:
            continue
        slot_idx = int(payload[0])
        active_days = week_allowed_mask[:, slot_idx].astype(float)
        if active_days.sum() <= 0.0:
            continue
        big_positions = [int(x) - 1 for x in payload[1]]
        small_positions = [int(x) - 1 for x in payload[2]]
        if len(big_positions) == 1 and len(small_positions) == 1:
            top = week_cube[:, slot_idx, big_positions[0]].astype("int16")
            bottom = week_cube[:, slot_idx, small_positions[0]].astype("int16")
            daily_ledger += active_days * ((1995 * (top + 1 - bottom) - 2000) / 1000.0)
            daily_bets += active_days * 2.0
        elif len(big_positions) == 2 and len(small_positions) == 2:
            top = week_cube[:, slot_idx][:, big_positions].astype("int16")
            bottom = week_cube[:, slot_idx][:, small_positions].astype("int16")
            hits = top.sum(axis=1) + (2 - bottom.sum(axis=1))
            daily_ledger += active_days * ((1995 * hits - 4000) / 1000.0)
            daily_bets += active_days * 4.0
        else:
            raise ValueError(f"Unsupported payload: {payload}")
    return daily_ledger, daily_bets


def build_component_daily_with_mask(bundle, series: dict[str, object], week_starts: list[str], line_name: str, allowed_mask_cube) -> pd.DataFrame:
    lookup = {pd.Timestamp(ws).strftime("%Y-%m-%d"): idx for idx, ws in enumerate(bundle.week_start)}
    rows: list[dict[str, object]] = []
    for week_start in week_starts:
        week_idx = lookup[week_start]
        week_cube = bundle.big_cube[week_idx]
        week_allowed = allowed_mask_cube[week_idx]
        daily_ledger, daily_bets = day_ledger_from_positions_with_mask(week_cube, series["selected_positions_meta"][week_idx], week_allowed)
        for day_offset in range(7):
            ledger = float(daily_ledger.iloc[day_offset])
            bets = float(daily_bets.iloc[day_offset])
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


def build_face_frame(
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_stake: float,
    policy_id: str,
) -> pd.DataFrame:
    trace_df = pd.read_csv(ROUND35_TRACE, parse_dates=["date"])
    matched = trace_df[trace_df["policy_id"] == policy_id].copy()
    if matched.empty:
        raise RuntimeError(f"Missing round35 trace rows for policy_id={policy_id}")

    matched = matched[(matched["date"] >= sim_start) & (matched["date"] <= sim_end)].copy()
    if matched.empty:
        raise RuntimeError(f"No round35 rows for {policy_id} in {sim_start.date()} -> {sim_end.date()}")

    date_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    matched = date_range.merge(
        matched[["date", "week_start", "day_index_in_week", "mode", "policy_real_unit", "policy_bets"]],
        on="date",
        how="left",
    )
    matched["mode"] = matched["mode"].fillna("cash")
    matched["policy_real_unit"] = matched["policy_real_unit"].fillna(0.0)
    matched["policy_bets"] = matched["policy_bets"].fillna(0.0)
    matched["face_base_real_pnl"] = matched["policy_real_unit"].astype(float) * float(base_stake)
    return matched


def build_face_frame_from_issue_history(
    round35_mod,
    round9_mod,
    round16_mod,
    issue_df: pd.DataFrame,
    allowed_lookup: pd.DataFrame,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_stake: float,
    policy_id: str,
) -> pd.DataFrame:
    bs_bundle = round9_mod.preprocess_history(issue_df)
    allowed_mask_cube = build_allowed_mask_cube(allowed_lookup, bs_bundle)

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
    bs_signal_states, bs_uniform, bs_balanced = round35_mod.build_signal_states(round9_mod, bs_bundle, [bs_core, bs_exp])
    bs_core_series = round9_mod.evaluate_candidate_series(bs_core, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9_mod.evaluate_candidate_series(bs_exp, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)

    round9_mod.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle = round16_mod.preprocess_odd_even(round9_mod, issue_df)
    if len(oe_bundle.week_start) != len(bs_bundle.week_start) or not (oe_bundle.week_start == bs_bundle.week_start).all():
        raise RuntimeError("Odd/even bundle week alignment mismatch with face bundle")
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
    oe_signal_states, oe_uniform, oe_balanced = round35_mod.build_signal_states(round9_mod, oe_bundle, [oe_cfg])
    oe_series = round9_mod.evaluate_candidate_series(oe_cfg, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    week_starts = [pd.Timestamp(x).strftime("%Y-%m-%d") for x in pd.to_datetime(bs_bundle.week_start)]
    core_daily = build_component_daily_with_mask(bs_bundle, bs_core_series, week_starts, "core", allowed_mask_cube)
    exp_daily = build_component_daily_with_mask(bs_bundle, bs_exp_series, week_starts, "exp", allowed_mask_cube)
    oe_daily = build_component_daily_with_mask(oe_bundle, oe_series, week_starts, "oe", allowed_mask_cube)

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
    df["day_index"] = range(1, len(df) + 1)

    core_cfg, exp_cfg, oe_cfg_parsed, cooldown_days = parse_face_policy_id(policy_id)
    _, trace = round35_mod.simulate_policy(df, policy_id, core_cfg, exp_cfg, oe_cfg_parsed, cooldown_days)
    trace["date"] = pd.to_datetime(trace["date"])
    matched = trace[(trace["date"] >= sim_start) & (trace["date"] <= sim_end)].copy()
    matched["face_base_real_pnl"] = matched["policy_real_unit"].astype(float) * float(base_stake)
    return matched[["date", "week_start", "day_index_in_week", "mode", "policy_real_unit", "policy_bets", "face_base_real_pnl"]].reset_index(drop=True)


def build_sum_inputs(
    vmod,
    rmod,
    intraday_mod,
    issue_df: pd.DataFrame,
    candidate_row: pd.Series,
    allowed_lookup: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    sum_bundle = vmod.preprocess_exact_sum(issue_df)
    baseline_lookup = {cfg.name: cfg for cfg in intraday_mod.baseline_configs()}
    baseline_name = str(candidate_row["baseline_name"])
    preview_cut = int(candidate_row["preview_cut"])
    if baseline_name not in baseline_lookup:
        raise RuntimeError(f"Missing sum baseline config: {baseline_name}")
    _, detail_df = intraday_mod.build_intraday_base_series(vmod, rmod, sum_bundle, baseline_lookup[baseline_name], preview_cut)
    detail_df["date"] = pd.to_datetime(detail_df["date"])

    preview_grouped = (
        detail_df.groupby(["date", "split"], as_index=False)
        .agg(
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

    allowed_detail = detail_df
    if allowed_lookup is not None:
        slot_lookup = allowed_lookup[["date", "issue_idx_in_day", "allowed_trade"]].rename(columns={"issue_idx_in_day": "slot"})
        allowed_detail = detail_df.merge(slot_lookup, on=["date", "slot"], how="left")
        allowed_detail["allowed_trade"] = allowed_detail["allowed_trade"].fillna(True).astype(bool)
        allowed_detail = allowed_detail[allowed_detail["allowed_trade"]].copy()

    allowed_counts = (
        allowed_detail.groupby(["date", "split"], as_index=False)
        .agg(requested_slots=("slot", "size"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    grouped = preview_grouped.merge(allowed_counts, on=["date", "split"], how="left")
    grouped["requested_slots"] = grouped["requested_slots"].fillna(0).astype(int)
    picks = allowed_detail.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in picks.groupby("date")}
    return grouped, picks_by_date


def build_exact_inputs(
    number_window_mod,
    round9_mod,
    issue_df: pd.DataFrame,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_gate_id: str,
    obs_window: int,
    execution_rule: str,
    exact_net_win: float,
    allowed_lookup: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
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
        (rule_state_df["base_gate_id"] == base_gate_id)
        & (rule_state_df["obs_window"] == obs_window)
    ].copy()
    if filtered.empty:
        raise RuntimeError("Exact daily-window rule_state is empty for the selected frozen candidate")

    rule_col = f"rule_{execution_rule}"
    if rule_col not in filtered.columns:
        raise RuntimeError(f"Missing exact execution rule column: {rule_col}")

    filtered["execute_exact"] = filtered[rule_col].astype(bool)
    filtered["selected_number_exec"] = filtered.apply(
        lambda row: number_window_mod.selected_number_for_rule(execution_rule, row),
        axis=1,
    )
    filtered["exact_hit_exec"] = (
        filtered["execute_exact"] & (filtered["target_number"] == filtered["selected_number_exec"])
    ).astype(int)
    filtered["cell_book_pnl_units"] = filtered["exact_hit_exec"].map(
        lambda hit: float(exact_net_win) if int(hit) == 1 else -1.0
    )
    filtered["day_date"] = pd.to_datetime(filtered["day_date"])

    active_cells = filtered[filtered["execute_exact"]].copy()
    if allowed_lookup is not None:
        slot_lookup = allowed_lookup[["date", "slot_1based", "allowed_trade"]].rename(columns={"date": "day_date"})
        active_cells = active_cells.merge(slot_lookup, on=["day_date", "slot_1based"], how="left")
        active_cells["allowed_trade"] = active_cells["allowed_trade"].fillna(True).astype(bool)
        active_cells = active_cells[active_cells["allowed_trade"]].copy()

    split_frame = filtered[["day_date", "split"]].drop_duplicates().copy()
    grouped = (
        active_cells.groupby(["day_date", "split"], as_index=False)
        .agg(
            issue_exposures=("execute_exact", "sum"),
            exact_hits_count=("exact_hit_exec", "sum"),
        )
        .sort_values("day_date")
        .reset_index(drop=True)
    )
    grouped = split_frame.merge(grouped, on=["day_date", "split"], how="left")
    grouped["issue_exposures"] = grouped["issue_exposures"].fillna(0).astype(int)
    grouped["exact_hits_count"] = grouped["exact_hits_count"].fillna(0).astype(int)
    picks_by_date = {
        pd.Timestamp(day): frame.sort_values(["slot_1based"], kind="stable").reset_index(drop=True)
        for day, frame in active_cells.groupby("day_date")
    }

    full_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    daily_frame = full_range.merge(grouped.rename(columns={"day_date": "date"}), on="date", how="left")
    daily_frame["split"] = daily_frame["split"].fillna("out_of_sample_gap")
    daily_frame["issue_exposures"] = daily_frame["issue_exposures"].fillna(0).astype(int)
    daily_frame["exact_hits_count"] = daily_frame["exact_hits_count"].fillna(0).astype(int)
    return daily_frame, picks_by_date


def build_svg(series_df: pd.DataFrame, output_path: Path, title: str) -> None:
    width, height = 1200, 520
    left, right, top, bottom = 70, 30, 40, 55
    inner_w = width - left - right
    inner_h = height - top - bottom

    all_values = series_df["bankroll_after_day"].astype(float).tolist()
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

    for idx, day in enumerate(series_df["date"].dt.strftime("%m-%d").tolist()):
        lines.append(f"<text x='{x_at(idx, len(series_df)):.2f}' y='{top + inner_h + 20}' text-anchor='middle' font-size='11' font-family='Arial, sans-serif' fill='#4b5563'>{day}</text>")

    points = " ".join(
        f"{x_at(i, len(series_df)):.2f},{y_at(v):.2f}"
        for i, v in enumerate(series_df["bankroll_after_day"].astype(float).tolist())
    )
    lines.append(f"<polyline fill='none' stroke='#1d4ed8' stroke-width='2.5' points='{points}' />")
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def replay_shared_bankroll(
    round36_mod,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    start_bankroll: float,
    base_stake: float,
    max_multiplier: int,
    face_policy_id: str,
    face_frame: pd.DataFrame,
    sum_candidate_row: pd.Series,
    sum_grouped: pd.DataFrame,
    sum_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    exact_frame: pd.DataFrame,
    exact_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    exact_window_id: str,
    exact_base_gate_id: str,
    exact_obs_window: int,
    exact_execution_rule: str,
    exact_net_win: float,
    exact_staking_mode: str,
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
    sum_daily["sum_active"] = sum_daily.apply(lambda row: round36_mod.gate_is_on(row, sum_candidate_row), axis=1)

    combined = (
        full_range.merge(face_frame, on="date", how="left")
        .merge(sum_daily, on="date", how="left")
        .merge(exact_frame, on="date", how="left")
    )
    combined["mode"] = combined["mode"].fillna("cash")
    combined["face_base_real_pnl"] = combined["face_base_real_pnl"].fillna(0.0)
    combined["policy_bets"] = combined["policy_bets"].fillna(0.0)
    combined["issue_exposures"] = combined["issue_exposures"].fillna(0).astype(int)
    combined["exact_hits_count"] = combined["exact_hits_count"].fillna(0).astype(int)

    bankroll = float(start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0

    face_multiplier = 1
    sum_multiplier = 1
    exact_multiplier = 1

    face_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    sum_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    exact_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    skipped_sum_due_to_cash = 0
    skipped_exact_due_to_cash = 0

    rows: list[dict[str, object]] = []
    for _, row in combined.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll

        face_active = str(row["mode"]) != "cash"
        applied_face_multiplier = face_multiplier if face_active else 0
        face_real = float(row["face_base_real_pnl"]) * applied_face_multiplier
        if face_active:
            face_ladder_counts[face_multiplier] += 1

        sum_requested_slots = int(row["requested_slots"]) if bool(row["sum_active"]) else 0
        sum_funded_slots = 0
        sum_book_units = 0.0
        sum_real = 0.0
        affordable_sum_slots = max(0, int(bankroll_before // (base_stake * sum_multiplier))) if sum_multiplier > 0 else 0
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
        effective_exact_multiplier = 1 if exact_staking_mode == "fixed" else exact_multiplier
        affordable_exact_slots = max(0, int(bankroll_before // (base_stake * effective_exact_multiplier))) if effective_exact_multiplier > 0 else 0
        if exact_requested_slots > 0:
            exact_funded_slots = min(exact_requested_slots, affordable_exact_slots)
            if exact_funded_slots > 0:
                exact_picks = exact_picks_by_date.get(day, pd.DataFrame()).head(exact_funded_slots).copy()
                exact_book_units = float(exact_picks["cell_book_pnl_units"].sum()) if not exact_picks.empty else 0.0
                exact_real = round36_mod.settle_real(exact_book_units * effective_exact_multiplier) * base_stake
                exact_ladder_counts[effective_exact_multiplier] += 1
            else:
                skipped_exact_due_to_cash += 1

        total_real = face_real + sum_real + exact_real
        bankroll += total_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "face_mode": str(row["mode"]),
                "face_active": face_active,
                "face_executed_bets": int(row["policy_bets"]),
                "face_multiplier": applied_face_multiplier,
                "face_real_pnl": face_real,
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
                "exact_multiplier": effective_exact_multiplier if exact_requested_slots > 0 else 0,
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

        if face_active:
            face_multiplier = round36_mod.next_multiplier(face_multiplier, max_multiplier=max_multiplier, last_real_pnl=face_real)
        if sum_funded_slots > 0:
            sum_multiplier = round36_mod.next_multiplier(sum_multiplier, max_multiplier=max_multiplier, last_real_pnl=sum_real)
        if exact_funded_slots > 0 and exact_staking_mode == "martingale":
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
                "face_policy_id": str(face_policy_id),
                "sum_candidate_id": str(sum_candidate_row["candidate_id"]),
                "sum_gate_family": str(sum_candidate_row["gate_family"]),
                "sum_baseline_name": str(sum_candidate_row["baseline_name"]),
                "sum_preview_cut": int(sum_candidate_row["preview_cut"]),
                "exact_window_id": str(exact_window_id),
                "exact_base_gate_id": str(exact_base_gate_id),
                "exact_obs_window": int(exact_obs_window),
                "exact_execution_rule": str(exact_execution_rule),
                "exact_net_win": float(exact_net_win),
                "exact_staking_mode": str(exact_staking_mode),
                "days_in_simulation": int(daily_df.shape[0]),
                "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
                "net_profit": float(daily_df["total_real_pnl"].sum()),
                "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / start_bankroll - 1.0) * 100.0),
                "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
                "min_bankroll": float(daily_df["bankroll_after_day"].min()),
                "max_drawdown": float(max_drawdown),
                "face_profit": float(daily_df["face_real_pnl"].sum()),
                "sum_profit": float(daily_df["sum_real_pnl"].sum()),
                "exact_profit": float(daily_df["exact_real_pnl"].sum()),
                "face_active_days": int(daily_df["face_active"].sum()),
                "sum_active_days": int(daily_df["sum_active"].sum()),
                "exact_active_days": int(daily_df["exact_active"].sum()),
                "sum_funded_slots": int(daily_df["sum_funded_slots"].sum()),
                "exact_funded_slots": int(daily_df["exact_funded_slots"].sum()),
                "skipped_sum_due_to_cash": skipped_sum_due_to_cash,
                "skipped_exact_due_to_cash": skipped_exact_due_to_cash,
                "face_days_1x": face_ladder_counts[1],
                "face_days_2x": face_ladder_counts[2],
                "face_days_4x": face_ladder_counts[4],
                "face_days_5x": face_ladder_counts[5],
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
    global args
    args = parse_args()
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)
    blackout_start = parse_time_of_day(args.blackout_start)
    blackout_end = parse_time_of_day(args.blackout_end)
    effective_query_end = complete_week_query_end(sim_end, args.query_end)

    if str(NUMBER_WINDOW_DIR) not in sys.path:
        sys.path.insert(0, str(NUMBER_WINDOW_DIR))

    round36_mod = import_module(ROUND36_FILE, "round36_for_round36_aligned")
    round35_mod = import_module(ROUND35_FILE, "round35_for_round36_aligned")
    round9_mod = import_module(ROUND9_FILE, "round9_for_round36_aligned")
    round16_mod = import_module(ROUND16_FILE, "round16_for_round36_aligned")
    vmod = import_module(SUM_VALIDATION_FILE, "sum_validation_for_round36_aligned")
    rmod = import_module(SUM_REFINEMENT_FILE, "sum_refinement_for_round36_aligned")
    intraday_mod = import_module(SUM_INTRADAY_FILE, "sum_intraday_for_round36_aligned")
    number_window_mod = import_module(NUMBER_WINDOW_FILE, "number_daily_window_for_round36_aligned")

    issue_df = load_issue_history(vmod, query_start=args.query_start, query_end=str(effective_query_end.date()))
    if issue_df.empty:
        raise RuntimeError("Issue history query returned no rows")

    allowed_lookup = build_allowed_trade_lookup(
        build_issue_schedule_frame(issue_df),
        blackout_start=blackout_start,
        blackout_end=blackout_end,
    )

    if blackout_start is None or blackout_end is None:
        face_frame = build_face_frame(
            sim_start=sim_start,
            sim_end=sim_end,
            base_stake=float(args.base_stake),
            policy_id=args.face_policy_id,
        )
    else:
        face_frame = build_face_frame_from_issue_history(
            round35_mod=round35_mod,
            round9_mod=round9_mod,
            round16_mod=round16_mod,
            issue_df=issue_df,
            allowed_lookup=allowed_lookup,
            sim_start=sim_start,
            sim_end=sim_end,
            base_stake=float(args.base_stake),
            policy_id=args.face_policy_id,
        )
    sum_candidate_row = load_sum_candidate_row(args.sum_candidate_id)
    sum_grouped, sum_picks_by_date = build_sum_inputs(
        vmod=vmod,
        rmod=rmod,
        intraday_mod=intraday_mod,
        issue_df=issue_df,
        candidate_row=sum_candidate_row,
        allowed_lookup=allowed_lookup if blackout_start is not None and blackout_end is not None else None,
    )
    exact_frame, exact_picks_by_date = build_exact_inputs(
        number_window_mod=number_window_mod,
        round9_mod=round9_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
        base_gate_id=args.exact_base_gate_id,
        obs_window=int(args.exact_obs_window),
        execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        allowed_lookup=allowed_lookup if blackout_start is not None and blackout_end is not None else None,
    )

    daily_df, summary_df = replay_shared_bankroll(
        round36_mod=round36_mod,
        sim_start=sim_start,
        sim_end=sim_end,
        start_bankroll=float(args.start_bankroll),
        base_stake=float(args.base_stake),
        max_multiplier=max(1, int(args.max_multiplier)),
        face_policy_id=args.face_policy_id,
        face_frame=face_frame,
        sum_candidate_row=sum_candidate_row,
        sum_grouped=sum_grouped,
        sum_picks_by_date=sum_picks_by_date,
        exact_frame=exact_frame,
        exact_picks_by_date=exact_picks_by_date,
        exact_window_id=args.exact_window_id,
        exact_base_gate_id=args.exact_base_gate_id,
        exact_obs_window=int(args.exact_obs_window),
        exact_execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        exact_staking_mode=args.exact_staking_mode,
    )

    blackout_tag = ""
    if blackout_start is not None and blackout_end is not None:
        blackout_tag = f"_blackout_{args.blackout_start.replace(':', '')}_{args.blackout_end.replace(':', '')}"

    stem = (
        f"aligned_face_{args.face_policy_id}"
        f"__sum_{args.sum_candidate_id}"
        f"__exact_{args.exact_window_id}_{args.exact_staking_mode}"
        f"_bankroll_{int(args.start_bankroll)}_stake_{int(args.base_stake)}"
        f"_m{int(args.max_multiplier)}{blackout_tag}_pks_history_{sim_start.date()}_{sim_end.date()}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    curve_path = OUTPUT_DIR / f"{stem}_curve.svg"

    daily_df.to_csv(daily_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    build_svg(
        daily_df,
        curve_path,
        title=(
            f"Aligned Shared Bankroll Curve | {sim_start.date()} -> {sim_end.date()} | "
            f"{args.face_policy_id} + {args.sum_candidate_id} + {args.exact_window_id}"
        ),
    )

    print(summary_path)
    print(daily_path)
    print(curve_path)


if __name__ == "__main__":
    main()
