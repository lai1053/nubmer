from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from datetime import time
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .db import query_df
from .settings import settings


NEGATIVE_DISCOUNT = 0.85
SUM_NET_ODDS = (
    41.0,
    41.0,
    20.0,
    20.0,
    12.0,
    12.0,
    10.0,
    10.0,
    7.5,
    10.0,
    10.0,
    12.0,
    12.0,
    20.0,
    20.0,
    41.0,
    41.0,
)


def next_multiplier(current: int, max_multiplier: int, last_real_pnl: float) -> int:
    if last_real_pnl < 0.0:
        if current < 2:
            return min(2, max_multiplier)
        if current < 4:
            return min(4, max_multiplier)
        return min(5, max_multiplier)
    return 1


def settle_real(book_pnl_units: float) -> float:
    return float(book_pnl_units if book_pnl_units >= 0.0 else book_pnl_units * NEGATIVE_DISCOUNT)


def daily85(book_pnl_units: float) -> float:
    return settle_real(book_pnl_units)


def martingale_double_ladder(level_count: int) -> tuple[int, ...]:
    max_multiplier = max(1, int(level_count))
    ladder = [1]
    while ladder[-1] < max_multiplier:
        ladder.append(min(ladder[-1] * 2, max_multiplier))
    return tuple(ladder)


def next_ladder_multiplier(current: int, ladder: tuple[int, ...], last_real_pnl: float) -> int:
    if not ladder:
        return 1
    if last_real_pnl >= 0.0:
        return int(ladder[0])
    if current in ladder:
        index = ladder.index(current)
    else:
        index = 0
    return int(ladder[min(index + 1, len(ladder) - 1)])


def sum_net_odds_for_index(sum_index: int) -> float:
    return float(SUM_NET_ODDS[int(sum_index)])


def sum_net_odds_for_value(sum_value: int) -> float:
    return sum_net_odds_for_index(int(sum_value) - 3)


def sum_book_units(sum_index: int, hit: int | bool) -> float:
    return float(sum_net_odds_for_index(sum_index) if int(hit) == 1 else -1.0)


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class StrategyModules:
    round9: Any
    round16: Any
    round35: Any
    sum_vmod: Any
    sum_rmod: Any
    sum_intraday: Any
    number_window: Any
    source_root: Path

    @classmethod
    def load(cls, source_root: Path) -> "StrategyModules":
        number_dir = source_root / "tmp_number_validation"
        if str(number_dir) not in sys.path:
            sys.path.insert(0, str(number_dir))
        return cls(
            round9=import_module(
                source_root / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py",
                "pk10_live_round9",
            ),
            round16=import_module(
                source_root / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py",
                "pk10_live_round16",
            ),
            round35=import_module(
                source_root / "pk10_round35_daily_deployment_refinement" / "pk10_round35_daily_deployment_refinement.py",
                "pk10_live_round35",
            ),
            sum_vmod=import_module(
                source_root / "pk10_number_sum_validation" / "pk10_number_sum_validation.py",
                "pk10_live_sum_validation",
            ),
            sum_rmod=import_module(
                source_root / "pk10_number_sum_validation" / "pk10_number_sum_refinement.py",
                "pk10_live_sum_refinement",
            ),
            sum_intraday=import_module(
                source_root / "pk10_number_sum_validation" / "pk10_number_sum_intraday_gate.py",
                "pk10_live_sum_intraday",
            ),
            number_window=import_module(
                source_root / "tmp_number_validation" / "pk10_number_daily_window_validation.py",
                "pk10_live_number_window",
            ),
            source_root=source_root,
        )


@dataclass
class ReplayResult:
    daily_df: pd.DataFrame
    summary: dict[str, Any]
    end_bankroll: float
    end_face_multiplier: int
    end_sum_multiplier: int
    peak_bankroll: float
    min_bankroll: float
    max_drawdown: float
    sum_bet_rows: list[dict[str, Any]]


def parse_time_of_day(text: str | None) -> time | None:
    value = str(text or "").strip()
    if not value:
        return None
    return pd.Timestamp(f"2000-01-01 {value}").time()


def mysql_position_expr(position: int) -> str:
    return (
        "CAST("
        f"SUBSTRING_INDEX(SUBSTRING_INDEX(pre_draw_code, ',', {position}), ',', -1)"
        " AS UNSIGNED)"
    )


def load_issue_history_from_db(date_start: str, date_end: str | None = None) -> pd.DataFrame:
    filters = ["pre_draw_code IS NOT NULL", "pre_draw_code <> ''", f"draw_date >= '{date_start}'"]
    if date_end:
        filters.append(f"draw_date <= '{date_end}'")
    pos_cols = ",\n        ".join(f"{mysql_position_expr(i)} AS pos{i}" for i in range(1, 11))
    sql = f"""
    SELECT
        DATE_FORMAT(draw_date, '%Y-%m-%d') AS draw_date,
        DATE_FORMAT(pre_draw_time, '%Y-%m-%d %H:%i:%s') AS pre_draw_time,
        pre_draw_issue,
        {pos_cols}
    FROM {settings.db_table}
    WHERE {' AND '.join(filters)}
    ORDER BY draw_date, pre_draw_time, pre_draw_issue
    """
    df = query_df(sql)
    if df.empty:
        return df
    df["draw_date"] = pd.to_datetime(df["draw_date"])
    df["pre_draw_time"] = pd.to_datetime(df["pre_draw_time"])
    df["pre_draw_issue"] = df["pre_draw_issue"].astype(np.int64)
    for idx in range(1, 11):
        df[f"pos{idx}"] = df[f"pos{idx}"].astype(np.uint8)
    return df


def normalize_issue_df(issue_df: pd.DataFrame) -> pd.DataFrame:
    work = issue_df.copy()
    work["draw_date"] = pd.to_datetime(work["draw_date"]).dt.normalize()
    if "pre_draw_time" in work.columns:
        work["draw_ts"] = pd.to_datetime(work["pre_draw_time"])
    else:
        work["draw_ts"] = pd.to_datetime(work["draw_date"])
    work = work.sort_values(["draw_date", "draw_ts", "pre_draw_issue"]).reset_index(drop=True)
    return work


def build_schedule_frame(issue_df: pd.DataFrame) -> pd.DataFrame:
    work = normalize_issue_df(issue_df)
    work["slot_1based"] = work.groupby("draw_date").cumcount() + 1
    return work[
        [
            "draw_date",
            "draw_ts",
            "pre_draw_issue",
            "slot_1based",
        ]
    ].copy()


def filter_blackout(issue_df: pd.DataFrame, blackout_start: time | None, blackout_end: time | None) -> pd.DataFrame:
    if blackout_start is None or blackout_end is None:
        return normalize_issue_df(issue_df)
    work = normalize_issue_df(issue_df)
    time_values = work["draw_ts"].dt.time
    return work.loc[~((time_values >= blackout_start) & (time_values < blackout_end))].reset_index(drop=True)


def _extended_week_meta(work: pd.DataFrame) -> tuple[pd.DataFrame, int, pd.DataFrame]:
    if work.empty:
        raise RuntimeError("No rows available for extended-week preprocessing")
    day_counts = work.groupby("draw_date").size().sort_index()
    expected_per_day = int(day_counts.mode().iloc[0])
    last_date = pd.Timestamp(day_counts.index.max())
    keep_dates = set(day_counts[day_counts == expected_per_day].index.tolist())
    keep_dates.add(last_date)
    work = work[work["draw_date"].isin(keep_dates)].copy()
    work["issue_idx_in_day"] = work.groupby("draw_date").cumcount()
    iso = work["draw_date"].dt.isocalendar()
    work["iso_year"] = iso["year"].astype(int)
    work["iso_week"] = iso["week"].astype(int)
    work["week_id"] = work["iso_year"].astype(str) + "-W" + work["iso_week"].astype(str).str.zfill(2)
    week_days = work.groupby("week_id")["draw_date"].nunique()
    complete_week_ids = set(week_days[week_days == 7].index.tolist())
    ordered = (
        work.groupby("week_id", sort=True)["draw_date"]
        .agg(["min", "max", "nunique"])
        .rename(columns={"min": "first_date", "max": "last_date", "nunique": "n_days"})
        .reset_index()
        .sort_values("first_date")
        .reset_index(drop=True)
    )
    keep_week_ids = [wid for wid in ordered["week_id"].tolist() if wid in complete_week_ids]
    tail_week_id = str(ordered.iloc[-1]["week_id"])
    if tail_week_id not in keep_week_ids:
        keep_week_ids.append(tail_week_id)
    ordered = ordered[ordered["week_id"].isin(keep_week_ids)].copy().reset_index(drop=True)
    ordered["week_start"] = ordered["first_date"] - pd.to_timedelta(ordered["first_date"].dt.weekday, unit="D")
    ordered["week_end"] = ordered["week_start"] + pd.Timedelta(days=6)
    work = work[work["week_id"].isin(keep_week_ids)].copy()
    work["week_id"] = pd.Categorical(work["week_id"], categories=ordered["week_id"].tolist(), ordered=True)
    work = work.sort_values(["week_id", "draw_date", "issue_idx_in_day"]).reset_index(drop=True)
    return work, expected_per_day, ordered[["week_id", "week_start", "week_end"]].copy()


def _fill_extended_cube(
    work: pd.DataFrame,
    expected_per_day: int,
    week_meta: pd.DataFrame,
    value_columns: list[str],
    dtype: Any,
) -> tuple[np.ndarray, np.ndarray]:
    tail_shape = (len(value_columns),) if len(value_columns) > 1 else ()
    shape = (len(week_meta), 7, expected_per_day) + tail_shape
    cube = np.zeros(shape, dtype=dtype)
    mask = np.zeros((len(week_meta), 7, expected_per_day), dtype=bool)
    week_lookup = {str(row.week_id): idx for idx, row in week_meta.iterrows()}
    values = work[value_columns].to_numpy(dtype=dtype)
    for row_idx, row in enumerate(work.itertuples(index=False)):
        week_idx = week_lookup[str(row.week_id)]
        day_idx = int((pd.Timestamp(row.draw_date) - pd.Timestamp(week_meta.iloc[week_idx]["week_start"])).days)
        slot_idx = int(row.issue_idx_in_day)
        if day_idx < 0 or day_idx >= 7 or slot_idx < 0 or slot_idx >= expected_per_day:
            continue
        mask[week_idx, day_idx, slot_idx] = True
        if len(value_columns) == 1:
            cube[week_idx, day_idx, slot_idx] = values[row_idx][0]
        else:
            cube[week_idx, day_idx, slot_idx, :] = values[row_idx]
    return cube, mask


def build_extended_face_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = filter_blackout(issue_df, parse_time_of_day(settings.blackout_start), parse_time_of_day(settings.blackout_end))
    pos_cols = [f"pos{i}" for i in range(1, 11)]
    big_cols = [f"is_big_{i}" for i in range(1, 11)]
    work[big_cols] = (work[pos_cols].to_numpy(dtype=np.uint8) >= 6).astype(np.uint8)
    work["big_count"] = work[big_cols].sum(axis=1)
    work = work[work["big_count"] == 5].copy()
    work, expected_per_day, week_meta = _extended_week_meta(work)
    big_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, big_cols, np.uint8)
    weekly_exact_counts = big_cube.sum(axis=1).astype(np.uint16)
    slot_to_decile = ((np.arange(expected_per_day) * 10) // expected_per_day).astype(np.int8)
    weekly_decile_counts = np.zeros((len(week_meta), 10, 10), dtype=np.uint16)
    exposures_decile = np.zeros(10, dtype=np.uint16)
    for decile in range(10):
        slot_selector = slot_to_decile == decile
        exposures_decile[decile] = int(slot_selector.sum() * 7)
        weekly_decile_counts[:, decile, :] = weekly_exact_counts[:, slot_selector, :].sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    train_mask = week_end <= np.datetime64(mods.round9.TRAIN_END)
    test_mask = week_start >= np.datetime64(mods.round9.TEST_START)
    if bool(train_mask.any()):
        position_train_rates = big_cube[train_mask].mean(axis=(0, 1, 2))
    else:
        position_train_rates = big_cube.mean(axis=(0, 1, 2))
    desc = np.argsort(-position_train_rates)
    asc = np.argsort(position_train_rates)
    bundle = mods.round9.DatasetBundle(
        big_cube=big_cube,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        slot_to_decile=slot_to_decile,
        weekly_exact_counts=weekly_exact_counts,
        weekly_decile_counts=weekly_decile_counts,
        exposures_exact=np.full(expected_per_day, 7, dtype=np.uint16),
        exposures_decile=exposures_decile,
        train_mask_fixed_split=train_mask,
        test_mask_fixed_split=test_mask,
        static_pair_big_pos=int(desc[0]),
        static_pair_small_pos=int(asc[0]),
    )
    return bundle, slot_mask, build_schedule_frame(work)


def build_extended_odd_even_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = filter_blackout(issue_df, parse_time_of_day(settings.blackout_start), parse_time_of_day(settings.blackout_end))
    pos_cols = [f"pos{i}" for i in range(1, 11)]
    odd_cols = [f"is_odd_{i}" for i in range(1, 11)]
    work[odd_cols] = (work[pos_cols].to_numpy(dtype=np.uint8) % 2 == 1).astype(np.uint8)
    work["odd_count"] = work[odd_cols].sum(axis=1)
    work = work[work["odd_count"] == 5].copy()
    work, expected_per_day, week_meta = _extended_week_meta(work)
    odd_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, odd_cols, np.uint8)
    weekly_exact_counts = odd_cube.sum(axis=1).astype(np.uint16)
    slot_to_decile = ((np.arange(expected_per_day) * 10) // expected_per_day).astype(np.int8)
    weekly_decile_counts = np.zeros((len(week_meta), 10, 10), dtype=np.uint16)
    exposures_decile = np.zeros(10, dtype=np.uint16)
    for decile in range(10):
        slot_selector = slot_to_decile == decile
        exposures_decile[decile] = int(slot_selector.sum() * 7)
        weekly_decile_counts[:, decile, :] = weekly_exact_counts[:, slot_selector, :].sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    train_mask = week_end <= np.datetime64(mods.round16.TRAIN_END)
    test_mask = week_start >= np.datetime64(mods.round16.TEST_START)
    if bool(train_mask.any()):
        position_train_rates = odd_cube[train_mask].mean(axis=(0, 1, 2))
    else:
        position_train_rates = odd_cube.mean(axis=(0, 1, 2))
    desc = np.argsort(-position_train_rates)
    asc = np.argsort(position_train_rates)
    bundle = mods.round9.DatasetBundle(
        big_cube=odd_cube,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        slot_to_decile=slot_to_decile,
        weekly_exact_counts=weekly_exact_counts,
        weekly_decile_counts=weekly_decile_counts,
        exposures_exact=np.full(expected_per_day, 7, dtype=np.uint16),
        exposures_decile=exposures_decile,
        train_mask_fixed_split=train_mask,
        test_mask_fixed_split=test_mask,
        static_pair_big_pos=int(desc[0]),
        static_pair_small_pos=int(asc[0]),
    )
    return bundle, slot_mask, build_schedule_frame(work)


def build_extended_sum_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = normalize_issue_df(issue_df)
    work["sum_value"] = (work["pos1"].astype(np.uint8) + work["pos2"].astype(np.uint8)).astype(np.uint8)
    work["sum_idx"] = (work["sum_value"] - 3).astype(np.uint8)
    work, expected_per_day, week_meta = _extended_week_meta(work)
    sum_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, ["sum_idx"], np.uint8)
    weekly_sum_counts = np.zeros((len(week_meta), expected_per_day, 17), dtype=np.uint16)
    for sum_index in range(17):
        weekly_sum_counts[:, :, sum_index] = (sum_cube == sum_index).sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    bundle = mods.sum_vmod.SumBundle(
        sum_cube=sum_cube,
        weekly_sum_counts=weekly_sum_counts,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        train_mask_fixed_split=week_end <= np.datetime64(mods.sum_vmod.TRAIN_END),
        test_mask_fixed_split=week_start >= np.datetime64(mods.sum_vmod.TEST_START),
        raw_rows=int(len(work)),
        complete_rows=int(len(work)),
        expected_per_day=expected_per_day,
        complete_days=int(work["draw_date"].nunique()),
        sample_min_date=str(work["draw_date"].min().date()),
        sample_max_date=str(work["draw_date"].max().date()),
    )
    return bundle, slot_mask, build_schedule_frame(work)


def build_extended_number_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = normalize_issue_df(issue_df)
    pos_cols = [f"pos{i}" for i in range(1, 11)]
    work["big_count"] = (work[pos_cols].to_numpy(dtype=np.uint8) >= 6).sum(axis=1)
    work = work[work["big_count"] == 5].copy()
    work, expected_per_day, week_meta = _extended_week_meta(work)
    number_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, pos_cols, np.uint8)
    big_cube = (number_cube >= 6).astype(np.uint8)
    weekly_exact_counts = big_cube.sum(axis=1).astype(np.uint16)
    slot_to_decile = ((np.arange(expected_per_day) * 10) // expected_per_day).astype(np.int8)
    weekly_decile_counts = np.zeros((len(week_meta), 10, 10), dtype=np.uint16)
    exposures_decile = np.zeros(10, dtype=np.uint16)
    for decile in range(10):
        slot_selector = slot_to_decile == decile
        exposures_decile[decile] = int(slot_selector.sum() * 7)
        weekly_decile_counts[:, decile, :] = weekly_exact_counts[:, slot_selector, :].sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    train_mask = week_end <= np.datetime64(mods.round9.TRAIN_END)
    test_mask = week_start >= np.datetime64(mods.round9.TEST_START)
    if bool(train_mask.any()):
        position_train_rates = big_cube[train_mask].mean(axis=(0, 1, 2))
    else:
        position_train_rates = big_cube.mean(axis=(0, 1, 2))
    desc = np.argsort(-position_train_rates)
    asc = np.argsort(position_train_rates)
    weekly_number_counts = np.zeros((len(week_meta), expected_per_day, 10, 10), dtype=np.uint8)
    for number in range(1, 11):
        weekly_number_counts[..., number - 1] = (number_cube == number).sum(axis=1).astype(np.uint8)
    round9_bundle = mods.round9.DatasetBundle(
        big_cube=big_cube,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        slot_to_decile=slot_to_decile,
        weekly_exact_counts=weekly_exact_counts,
        weekly_decile_counts=weekly_decile_counts,
        exposures_exact=np.full(expected_per_day, 7, dtype=np.uint16),
        exposures_decile=exposures_decile,
        train_mask_fixed_split=train_mask,
        test_mask_fixed_split=test_mask,
        static_pair_big_pos=int(desc[0]),
        static_pair_small_pos=int(asc[0]),
    )
    bundle = mods.number_window.NumberBundle(
        round9_bundle=round9_bundle,
        number_cube=number_cube,
        weekly_number_counts=weekly_number_counts,
    )
    return bundle, slot_mask, build_schedule_frame(work)


def load_sum_candidate_row(mods: StrategyModules, candidate_id: str) -> pd.Series:
    paths = (
        mods.source_root
        / "pk10_number_sum_validation"
        / "number_sum_intraday_gate_outputs_local_pks_3306_20260417"
        / "intraday_gate_summary.csv",
        mods.source_root
        / "pk10_number_sum_validation"
        / "number_sum_intraday_gate_outputs_db6y_daily85"
        / "intraday_gate_summary.csv",
    )
    for path in paths:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        matched = df[df["candidate_id"] == candidate_id].copy()
        if not matched.empty:
            return matched.iloc[0]
    raise RuntimeError(f"Missing sum candidate row: {candidate_id}")


def gate_is_on(day_row: pd.Series | dict[str, Any], candidate_row: pd.Series) -> bool:
    requested_slots = float(day_row["requested_slots"])
    if requested_slots <= 0.0:
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


def face_mode_components(mode: str) -> tuple[str, ...]:
    if mode == "core":
        return ("core",)
    if mode == "core_plus_expansion":
        return ("core", "exp")
    if mode == "core_plus_oe":
        return ("core", "oe")
    if mode == "core_plus_expansion_plus_oe":
        return ("core", "exp", "oe")
    return tuple()


def face_payload_ticket_count(payload: dict[str, Any]) -> int:
    big_n = len(payload["big_positions"])
    small_n = len(payload["small_positions"])
    if big_n == 1 and small_n == 1:
        return 2
    return 4


def face_payload_book_units(issue_row: pd.Series | dict[str, Any], payload: dict[str, Any]) -> tuple[float, int, str]:
    numbers = np.array([int(issue_row[f"pos{i}"]) for i in range(1, 11)], dtype=np.int16)
    big_flags = (numbers >= 6).astype(np.int16)
    big_positions = [int(x) - 1 for x in payload["big_positions"]]
    small_positions = [int(x) - 1 for x in payload["small_positions"]]
    if len(big_positions) == 1 and len(small_positions) == 1:
        top = int(big_flags[big_positions[0]])
        bottom = int(big_flags[small_positions[0]])
        ledger = float((1995 * (top + 1 - bottom) - 2000) / 1000.0)
        hits = int(top + (1 - bottom))
        label = "双中" if hits == 2 else ("单中" if hits == 1 else "双失")
        return ledger, hits, label
    top = big_flags[big_positions]
    bottom = big_flags[small_positions]
    hits = int(top.sum() + (len(small_positions) - bottom.sum()))
    ledger = float((1995 * hits - 4000) / 1000.0)
    label = f"{hits}/4中"
    return ledger, hits, label


def schedule_maps(schedule_df: pd.DataFrame) -> dict[str, dict[int, dict[str, Any]]]:
    out: dict[str, dict[int, dict[str, Any]]] = {}
    if schedule_df.empty:
        return out
    work = schedule_df.copy()
    work["date_key"] = pd.to_datetime(work["draw_date"]).dt.strftime("%Y-%m-%d")
    for day, group in work.groupby("date_key", sort=False):
        out[day] = {
            int(row.slot_1based): {
                "issue": int(row.pre_draw_issue),
                "draw_ts": pd.Timestamp(row.draw_ts),
            }
            for row in group.itertuples(index=False)
        }
    return out


def build_face_context(mods: StrategyModules, issue_df: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, Any]:
    bundle, _slot_mask, schedule_df = build_extended_face_bundle(mods, issue_df)
    round9 = mods.round9
    round16 = mods.round16
    round35 = mods.round35
    bs_core = round35.make_candidate(
        round9,
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
    bs_exp = round35.make_candidate(
        round9,
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
    bs_signal_states, bs_uniform, bs_balanced = round35.build_signal_states(round9, bundle, [bs_core, bs_exp])
    bs_core_series = round9.evaluate_candidate_series(bs_core, bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9.evaluate_candidate_series(bs_exp, bundle, bs_signal_states, bs_uniform, bs_balanced)
    round9.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle, _oe_mask, _oe_schedule = build_extended_odd_even_bundle(mods, issue_df)
    oe_cfg = round35.make_candidate(
        round9,
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
    oe_signal_states, oe_uniform, oe_balanced = round35.build_signal_states(round9, oe_bundle, [oe_cfg])
    oe_series = round9.evaluate_candidate_series(oe_cfg, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    week_starts = [pd.Timestamp(x).strftime("%Y-%m-%d") for x in pd.to_datetime(bundle.week_start)]
    core_daily = round35.build_component_daily(bundle, bs_core_series, week_starts, "core")
    exp_daily = round35.build_component_daily(bundle, bs_exp_series, week_starts, "exp")
    oe_daily = round35.build_component_daily(oe_bundle, oe_series, week_starts, "oe")

    df = core_daily[
        ["week_start", "date", "day_index_in_week", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]
    ].rename(
        columns={
            "daily_ledger_unit": "core_ledger_unit",
            "daily_bets": "core_bets",
            "daily_implied_spread": "core_implied_spread",
        }
    )
    df = df.merge(
        exp_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={
                "daily_ledger_unit": "exp_ledger_unit",
                "daily_bets": "exp_bets",
                "daily_implied_spread": "exp_implied_spread",
            }
        ),
        on="date",
        how="left",
    )
    df = df.merge(
        oe_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={
                "daily_ledger_unit": "oe_ledger_unit",
                "daily_bets": "oe_bets",
                "daily_implied_spread": "oe_implied_spread",
            }
        ),
        on="date",
        how="left",
    )
    df = df.fillna(0.0)
    df["day_index"] = range(1, len(df) + 1)
    trace = round35.simulate_policy(
        df=df,
        policy_id=settings.face_policy_id,
        core_cfg=(40, "spread_only"),
        exp_cfg=(0, "off"),
        oe_cfg=(40, "spread_only"),
        cooldown_days=2,
    )[1]
    trace["date"] = pd.to_datetime(trace["date"])
    trace["face_base_real_pnl"] = trace["policy_real_unit"].astype(float) * float(settings.base_stake)
    series_map = {"core": bs_core_series, "exp": bs_exp_series, "oe": oe_series}
    plan_by_date: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for week_idx, week_start in enumerate(pd.to_datetime(bundle.week_start)):
        week_key = pd.Timestamp(week_start).strftime("%Y-%m-%d")
        for day_offset in range(7):
            date_key = (pd.Timestamp(week_start) + pd.Timedelta(days=day_offset)).strftime("%Y-%m-%d")
            plan_by_date.setdefault(date_key, {"core": [], "exp": [], "oe": []})
            for source_name, series in series_map.items():
                payloads = series["selected_positions_meta"][week_idx]
                if payloads is None:
                    continue
                items: list[dict[str, Any]] = []
                for slot, big_positions, small_positions in payloads:
                    items.append(
                        {
                            "source": source_name,
                            "slot_1based": int(slot) + 1,
                            "big_positions": list(big_positions),
                            "small_positions": list(small_positions),
                            "ticket_count": 2 if len(big_positions) == 1 and len(small_positions) == 1 else 4,
                            "odds_display": (
                                "双面双票 | 双中 +1.99 | 单中 -0.01 | 双失 -2.00"
                                if len(big_positions) == 1 and len(small_positions) == 1
                                else "双面四票 | 4中 +3.98 | 3中 +1.99 | 2中 -0.01 | 1中 -2.00 | 0中 -4.00"
                            ),
                        }
                    )
                plan_by_date[date_key][source_name] = items
    return {
        "trace_df": trace,
        "plan_by_date": plan_by_date,
        "schedule_df": schedule_df,
        "schedule_map": schedule_maps(schedule_df),
        "current_date": current_date.strftime("%Y-%m-%d"),
    }


def build_sum_context(mods: StrategyModules, issue_df: pd.DataFrame) -> dict[str, Any]:
    bundle, _slot_mask, schedule_df = build_extended_sum_bundle(mods, issue_df)
    candidate_row = load_sum_candidate_row(mods, settings.sum_candidate_id)
    baseline_lookup = {cfg.name: cfg for cfg in mods.sum_intraday.baseline_configs()}
    baseline = baseline_lookup[str(candidate_row["baseline_name"])]
    preview_cut = int(candidate_row["preview_cut"])
    base_series, detail_df = mods.sum_intraday.build_intraday_base_series(
        mods.sum_vmod,
        mods.sum_rmod,
        bundle,
        baseline,
        preview_cut,
    )
    if detail_df.empty or "date" not in detail_df.columns:
        raw_schedule = build_schedule_frame(issue_df)
        return {
            "bundle": bundle,
            "candidate_row": candidate_row,
            "grouped": pd.DataFrame(
                columns=[
                    "date",
                    "split",
                    "requested_slots",
                    "selected_score",
                    "selected_mean_edge",
                    "selected_symmetry_gap",
                    "preview_raw_high_bias",
                    "preview_mid_share",
                    "preview_mean_sum",
                    "sum_active",
                ]
            ),
            "picks_by_date": {},
            "schedule_df": raw_schedule,
            "schedule_map": schedule_maps(raw_schedule),
            "baseline": baseline,
            "choice_state": mods.sum_rmod.build_choice_state(
                mods.sum_vmod,
                mods.sum_rmod.build_full_signal_state(
                    vmod=mods.sum_vmod,
                    bundle=bundle,
                    lookback_weeks=baseline.lookback_weeks,
                    prior_strength=baseline.prior_strength,
                    score_mode=baseline.score_mode,
                ),
                baseline.allowed_sums,
            ),
            "preview_cut": preview_cut,
        }
    detail_df["date"] = pd.to_datetime(detail_df["date"])
    raw_schedule = build_schedule_frame(issue_df)
    blackout_start = parse_time_of_day(settings.blackout_start)
    blackout_end = parse_time_of_day(settings.blackout_end)
    raw_schedule["allowed_trade"] = True
    if blackout_start and blackout_end:
        times = raw_schedule["draw_ts"].dt.time
        raw_schedule["allowed_trade"] = ~((times >= blackout_start) & (times < blackout_end))
    allowed_lookup = raw_schedule[["draw_date", "slot_1based", "allowed_trade"]].rename(columns={"draw_date": "date"})
    allowed_detail = detail_df.merge(allowed_lookup, left_on=["date", "slot"], right_on=["date", "slot_1based"], how="left")
    allowed_detail["allowed_trade"] = allowed_detail["allowed_trade"].fillna(True).astype(bool)
    allowed_detail = allowed_detail[allowed_detail["allowed_trade"]].copy()
    allowed_detail["sum_value"] = allowed_detail["sum_value"].astype(int)
    allowed_detail["hit"] = allowed_detail["hit"].astype(int)
    allowed_detail["book_pnl"] = np.where(
        allowed_detail["hit"] == 1,
        allowed_detail["sum_value"].map(lambda value: sum_net_odds_for_value(int(value))),
        -1.0,
    )
    allowed_detail["real_pnl"] = allowed_detail["book_pnl"].map(settle_real)
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
    allowed_counts = (
        allowed_detail.groupby(["date", "split"], as_index=False)
        .agg(requested_slots=("slot", "size"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    grouped = preview_grouped.merge(allowed_counts, on=["date", "split"], how="left")
    grouped["requested_slots"] = grouped["requested_slots"].fillna(0).astype(int)
    grouped["sum_active"] = grouped.apply(lambda row: gate_is_on(row, candidate_row), axis=1)
    picks = allowed_detail.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in picks.groupby("date")}
    signal_state = mods.sum_rmod.build_full_signal_state(
        vmod=mods.sum_vmod,
        bundle=bundle,
        lookback_weeks=baseline.lookback_weeks,
        prior_strength=baseline.prior_strength,
        score_mode=baseline.score_mode,
    )
    choice_state = mods.sum_rmod.build_choice_state(mods.sum_vmod, signal_state, baseline.allowed_sums)
    return {
        "bundle": bundle,
        "candidate_row": candidate_row,
        "grouped": grouped,
        "picks_by_date": picks_by_date,
        "schedule_df": raw_schedule,
        "schedule_map": schedule_maps(raw_schedule),
        "baseline": baseline,
        "choice_state": choice_state,
        "preview_cut": preview_cut,
    }


def build_exact_context(mods: StrategyModules, issue_df: pd.DataFrame) -> dict[str, Any]:
    bundle, _slot_mask, schedule_df = build_extended_number_bundle(mods, issue_df)
    candidate = mods.number_window.build_dynamic_pair_candidate(mods.round9)
    counts, exposures = mods.round9.get_bucket_counts(bundle.round9_bundle, candidate.bucket_model)
    signal_state = mods.round9.compute_signal_state(
        counts=counts,
        exposures=exposures,
        lookback_weeks=candidate.lookback_weeks,
        prior_strength=candidate.prior_strength,
        score_model=candidate.score_model,
    )
    subgroup_state_df = mods.number_window.build_fixed_slot_state_tables(
        bundle=bundle,
        round9=mods.round9,
        signal_state=signal_state,
        candidate=candidate,
        late_slots=mods.number_window.parse_csv_ints(mods.number_window.DEFAULT_LATE_SLOTS),
        control_slots=mods.number_window.parse_csv_ints(mods.number_window.DEFAULT_CONTROL_SLOTS),
        half_prior_strength=mods.number_window.DEFAULT_HALF_PRIOR_STRENGTH,
    )
    front_state_df = mods.number_window.build_daily_front_state(
        bundle=bundle,
        subgroup_state_df=subgroup_state_df,
        obs_windows=mods.number_window.OBS_WINDOWS,
        round9=mods.round9,
    )
    rule_state_df = mods.number_window.build_daily_rule_state(front_state_df)
    filtered = rule_state_df[
        (rule_state_df["base_gate_id"] == settings.exact_base_gate_id)
        & (rule_state_df["obs_window"] == settings.exact_obs_window)
    ].copy()
    rule_col = f"rule_{settings.exact_execution_rule}"
    filtered["execute_exact"] = filtered[rule_col].astype(bool)
    filtered["selected_number_exec"] = filtered.apply(
        lambda row: mods.number_window.selected_number_for_rule(settings.exact_execution_rule, row),
        axis=1,
    )
    filtered["exact_hit_exec"] = (
        filtered["execute_exact"] & (filtered["target_number"] == filtered["selected_number_exec"])
    ).astype(int)
    filtered["cell_book_pnl_units"] = filtered["exact_hit_exec"].map(
        lambda hit: float(settings.exact_net_win) if int(hit) == 1 else -1.0
    )
    filtered["day_date"] = pd.to_datetime(filtered["day_date"])
    raw_schedule = build_schedule_frame(issue_df)
    blackout_start = parse_time_of_day(settings.blackout_start)
    blackout_end = parse_time_of_day(settings.blackout_end)
    raw_schedule["allowed_trade"] = True
    if blackout_start and blackout_end:
        times = raw_schedule["draw_ts"].dt.time
        raw_schedule["allowed_trade"] = ~((times >= blackout_start) & (times < blackout_end))
    active_cells = filtered[filtered["execute_exact"]].copy()
    slot_lookup = raw_schedule[["draw_date", "slot_1based", "allowed_trade"]].rename(columns={"draw_date": "day_date"})
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
    return {
        "bundle": bundle,
        "grouped": grouped,
        "picks_by_date": picks_by_date,
        "schedule_df": raw_schedule,
        "schedule_map": schedule_maps(raw_schedule),
        "subgroup_state_df": subgroup_state_df,
    }


def replay_shared_bankroll(
    mods: StrategyModules,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    face_ctx: dict[str, Any],
    sum_ctx: dict[str, Any],
    exact_ctx: dict[str, Any],
) -> ReplayResult:
    date_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    face_frame = face_ctx["trace_df"]
    face_frame = face_frame[(face_frame["date"] >= sim_start) & (face_frame["date"] <= sim_end)].copy()
    sum_grouped = sum_ctx["grouped"].copy()
    sum_grouped["date"] = pd.to_datetime(sum_grouped["date"])
    exact_grouped = exact_ctx["grouped"].copy()
    exact_grouped["date"] = pd.to_datetime(exact_grouped["day_date"])

    sum_daily = date_range.merge(sum_grouped, on="date", how="left")
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
    sum_daily["sum_active"] = sum_daily.apply(lambda row: gate_is_on(row, sum_ctx["candidate_row"]), axis=1)

    exact_daily = date_range.merge(
        exact_grouped[["date", "split", "issue_exposures", "exact_hits_count"]],
        on="date",
        how="left",
    )
    exact_daily["split"] = exact_daily["split"].fillna("out_of_sample_gap")
    exact_daily["issue_exposures"] = exact_daily["issue_exposures"].fillna(0).astype(int)
    exact_daily["exact_hits_count"] = exact_daily["exact_hits_count"].fillna(0).astype(int)

    combined = (
        date_range.merge(face_frame, on="date", how="left")
        .merge(sum_daily, on="date", how="left")
        .merge(exact_daily[["date", "issue_exposures", "exact_hits_count"]], on="date", how="left")
    )
    combined["mode"] = combined["mode"].fillna("cash")
    combined["face_base_real_pnl"] = combined["face_base_real_pnl"].fillna(0.0)
    combined["policy_bets"] = combined["policy_bets"].fillna(0.0)
    combined["issue_exposures"] = combined["issue_exposures"].fillna(0).astype(int)
    combined["exact_hits_count"] = combined["exact_hits_count"].fillna(0).astype(int)

    bankroll = float(settings.bankroll_start)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0
    face_multiplier = 1
    sum_multiplier = 1
    rows: list[dict[str, Any]] = []
    sum_bet_rows: list[dict[str, Any]] = []

    for _, row in combined.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll
        face_active = str(row["mode"]) != "cash"
        applied_face_multiplier = face_multiplier if face_active else 0
        face_real = float(row["face_base_real_pnl"]) * applied_face_multiplier

        sum_requested_slots = int(row["requested_slots"]) if bool(row["sum_active"]) else 0
        affordable_sum_slots = max(0, int(bankroll_before // (float(settings.base_stake) * sum_multiplier))) if sum_multiplier > 0 else 0
        sum_funded_slots = min(sum_requested_slots, affordable_sum_slots)
        sum_book_units = 0.0
        sum_real = 0.0
        if sum_funded_slots > 0:
            picks = sum_ctx["picks_by_date"].get(day, pd.DataFrame()).head(sum_funded_slots).copy()
            sum_book_units = float(picks["book_pnl"].sum()) if not picks.empty else 0.0
            sum_real = settle_real(sum_book_units * sum_multiplier) * float(settings.base_stake)

        exact_requested_slots = int(row["issue_exposures"])
        affordable_exact_slots = max(0, int(bankroll_before // float(settings.base_stake)))
        exact_funded_slots = min(exact_requested_slots, affordable_exact_slots)
        exact_book_units = 0.0
        exact_real = 0.0
        if exact_funded_slots > 0:
            picks = exact_ctx["picks_by_date"].get(day, pd.DataFrame()).head(exact_funded_slots).copy()
            exact_book_units = float(picks["cell_book_pnl_units"].sum()) if not picks.empty else 0.0
            exact_real = settle_real(exact_book_units) * float(settings.base_stake)

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
                "exact_multiplier": 1 if exact_requested_slots > 0 else 0,
                "exact_book_pnl_units": exact_book_units,
                "exact_real_pnl": exact_real,
                "total_real_pnl": total_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
            }
        )
        if face_active:
            face_multiplier = next_multiplier(face_multiplier, settings.max_multiplier, face_real)
        if sum_funded_slots > 0:
            sum_multiplier = next_multiplier(sum_multiplier, settings.max_multiplier, sum_real)

    daily_df = pd.DataFrame(rows)
    summary = {
        "sim_start": str(sim_start.date()),
        "sim_end": str(sim_end.date()),
        "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]) if not daily_df.empty else float(settings.bankroll_start),
        "net_profit": float(daily_df["total_real_pnl"].sum()) if not daily_df.empty else 0.0,
        "peak_bankroll": float(peak),
        "min_bankroll": float(min_bankroll),
        "max_drawdown": float(max_drawdown),
        "face_profit": float(daily_df["face_real_pnl"].sum()) if not daily_df.empty else 0.0,
        "sum_profit": float(daily_df["sum_real_pnl"].sum()) if not daily_df.empty else 0.0,
        "exact_profit": float(daily_df["exact_real_pnl"].sum()) if not daily_df.empty else 0.0,
    }
    return ReplayResult(
        daily_df=daily_df,
        summary=summary,
        end_bankroll=float(daily_df["bankroll_after_day"].iloc[-1]) if not daily_df.empty else float(settings.bankroll_start),
        end_face_multiplier=face_multiplier,
        end_sum_multiplier=sum_multiplier,
        peak_bankroll=float(peak),
        min_bankroll=float(min_bankroll),
        max_drawdown=float(max_drawdown),
        sum_bet_rows=sum_bet_rows,
    )


def current_day_issue_maps(issue_df: pd.DataFrame, current_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_day = normalize_issue_df(issue_df)
    raw_day = raw_day[raw_day["draw_date"] == current_date].copy().reset_index(drop=True)
    raw_day["slot_1based"] = np.arange(1, len(raw_day) + 1)
    face_day = filter_blackout(raw_day, parse_time_of_day(settings.blackout_start), parse_time_of_day(settings.blackout_end)).copy()
    face_day["slot_1based"] = np.arange(1, len(face_day) + 1)
    return raw_day, face_day


def build_live_sum_plan(mods: StrategyModules, sum_ctx: dict[str, Any], raw_day: pd.DataFrame) -> dict[str, Any]:
    preview_cut = int(sum_ctx["preview_cut"])
    latest_slot = int(len(raw_day))
    current_week_idx = int(len(sum_ctx["bundle"].week_start) - 1)
    score = sum_ctx["choice_state"].score[current_week_idx].astype(np.float64)
    order = np.argsort(-score, kind="stable")
    blocked_slots = set(int(x) for x in sum_ctx["baseline"].slot_blacklist)
    selected_slots = [int(slot) for slot in order if slot not in blocked_slots and score[slot] > 0.0][: int(sum_ctx["baseline"].daily_issue_cap)]
    if latest_slot < preview_cut:
        return {
            "status": "waiting_preview",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": f"等待前 {preview_cut} 期完成判窗",
        }
    day_sum_values = (raw_day["pos1"].astype(int) + raw_day["pos2"].astype(int)).to_numpy(dtype=np.int16)
    preview_values = day_sum_values[:preview_cut]
    tradable_slots = [slot for slot in selected_slots if slot >= preview_cut and slot < len(score)]
    metrics = {
        "requested_slots": len(tradable_slots),
        "selected_mean_edge": float(np.mean(sum_ctx["choice_state"].mean_edge[current_week_idx, tradable_slots])) if tradable_slots else 0.0,
        "preview_raw_high_bias": float(np.mean(preview_values > 11) - np.mean(preview_values < 11)),
        "preview_mid_share": float(np.mean((preview_values >= 9) & (preview_values <= 13))),
        "preview_mean_sum": float(np.mean(preview_values)),
    }
    if not tradable_slots or not gate_is_on(metrics, sum_ctx["candidate_row"]):
        return {
            "status": "no_window",
            "latest_slot": latest_slot,
            "requested_slots": len(tradable_slots),
            "picks": [],
            "message": "当前和值无可投注选项",
            **metrics,
        }
    picks: list[dict[str, Any]] = []
    for slot in tradable_slots:
        slot_1based = int(slot + 1)
        issue_row = raw_day[raw_day["slot_1based"] == slot_1based]
        issue_value = int(issue_row["pre_draw_issue"].iloc[0]) if not issue_row.empty else None
        sum_index = int(sum_ctx["choice_state"].sum_idx[current_week_idx, slot])
        picks.append(
            {
                "slot_1based": slot_1based,
                "pre_draw_issue": issue_value,
                "sum_value": int(mods.sum_vmod.INDEX_TO_SUM[sum_index]),
                "sum_index": sum_index,
                "score_value": float(sum_ctx["choice_state"].score[current_week_idx, slot]),
                "odds_display": f"和值 {int(mods.sum_vmod.INDEX_TO_SUM[sum_index])} | 净赢 {sum_net_odds_for_index(sum_index):.1f}",
            }
        )
    picks = sorted(picks, key=lambda item: (-item["score_value"], item["slot_1based"]))
    return {
        "status": "active",
        "latest_slot": latest_slot,
        "requested_slots": len(picks),
        "picks": picks,
        "message": "和值窗口已开启",
        **metrics,
    }


def build_live_exact_plan(mods: StrategyModules, exact_ctx: dict[str, Any], raw_day: pd.DataFrame) -> dict[str, Any]:
    latest_slot = int(len(raw_day))
    if latest_slot < settings.exact_obs_window:
        return {
            "status": "waiting_preview",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": f"等待前 {settings.exact_obs_window} 期完成判窗",
        }
    current_week_idx = int(len(exact_ctx["bundle"].round9_bundle.week_start) - 1)
    current_rows = exact_ctx["subgroup_state_df"][
        (exact_ctx["subgroup_state_df"]["base_gate_id"] == settings.exact_base_gate_id)
        & (exact_ctx["subgroup_state_df"]["block_start_week_idx"] <= current_week_idx)
        & (exact_ctx["subgroup_state_df"]["block_end_week_idx"] >= current_week_idx)
    ].copy()
    if current_rows.empty:
        return {
            "status": "no_window",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": "当前定位胆无可投注选项",
        }
    picks: list[dict[str, Any]] = []
    number_matrix = raw_day[[f"pos{i}" for i in range(1, 11)]].to_numpy(dtype=np.int16)
    for row in current_rows.itertuples(index=False):
        slot_1based = int(row.slot_1based)
        if slot_1based <= settings.exact_obs_window or slot_1based > exact_ctx["bundle"].round9_bundle.n_slots:
            continue
        prefix_seq = number_matrix[: settings.exact_obs_window, int(row.position)].astype(int)
        group_numbers = [int(x) for x in json.loads(row.group_numbers_json)]
        prefix_group_hits = int(np.isin(prefix_seq, group_numbers).sum())
        if prefix_group_hits <= 0:
            continue
        num_a, num_b = group_numbers
        count_a = int(np.sum(prefix_seq == num_a))
        count_b = int(np.sum(prefix_seq == num_b))
        block_selected = int(row.selected_number)
        if count_a > count_b:
            prefix_major = num_a
        elif count_b > count_a:
            prefix_major = num_b
        elif block_selected in (num_a, num_b):
            prefix_major = block_selected
        else:
            prefix_major = min(num_a, num_b)
        if prefix_major != block_selected:
            continue
        issue_row = raw_day[raw_day["slot_1based"] == slot_1based]
        issue_value = int(issue_row["pre_draw_issue"].iloc[0]) if not issue_row.empty else None
        picks.append(
            {
                "slot_1based": slot_1based,
                "pre_draw_issue": issue_value,
                "number": int(prefix_major),
                "other": int(num_b if prefix_major == num_a else num_a),
                "position_1based": int(row.position_1based),
                "odds_display": f"定位胆 {int(prefix_major)} | 净赢 {float(settings.exact_net_win):.1f}",
            }
        )
    picks = sorted(picks, key=lambda item: item["slot_1based"])
    if not picks:
        return {
            "status": "no_window",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": "当前定位胆无可投注选项",
        }
    return {
        "status": "active",
        "latest_slot": latest_slot,
        "requested_slots": len(picks),
        "picks": picks,
        "message": "定位胆窗口已开启",
    }


def build_live_face_plan(face_ctx: dict[str, Any], face_day: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, Any]:
    date_key = current_date.strftime("%Y-%m-%d")
    trace_row = face_ctx["trace_df"][face_ctx["trace_df"]["date"] == current_date]
    if trace_row.empty:
        return {"status": "cash", "mode": "cash", "latest_slot": int(len(face_day)), "picks": [], "message": "双面今日空仓"}
    mode = str(trace_row.iloc[0]["mode"])
    components = face_mode_components(mode)
    if not components:
        return {"status": "cash", "mode": mode, "latest_slot": int(len(face_day)), "picks": [], "message": "双面今日空仓"}
    by_source = face_ctx["plan_by_date"].get(date_key, {})
    picks: list[dict[str, Any]] = []
    for source in components:
        for item in by_source.get(source, []):
            row = dict(item)
            issue_row = face_day[face_day["slot_1based"] == row["slot_1based"]]
            row["pre_draw_issue"] = int(issue_row["pre_draw_issue"].iloc[0]) if not issue_row.empty else None
            picks.append(row)
    picks = sorted(picks, key=lambda item: (item["slot_1based"], item["source"]))
    return {
        "status": "active" if picks else "cash",
        "mode": mode,
        "latest_slot": int(len(face_day)),
        "picks": picks,
        "message": "双面可执行" if picks else "双面今日空仓",
    }


def allocate_live_line(line_name: str, start_bankroll: float, multiplier_value: int, picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if line_name == "face":
        funded = picks
    else:
        affordable = max(0, int(start_bankroll // (float(settings.base_stake) * multiplier_value)))
        funded = picks[:affordable]
    for item in funded:
        item["multiplier_value"] = multiplier_value
        item["stake"] = float(settings.base_stake) * multiplier_value
        item["ticket_count"] = int(item.get("ticket_count", 1))
        item["total_cost"] = item["stake"] * item["ticket_count"]
    return funded


def simulate_sum_settled_day(
    day_picks: pd.DataFrame,
    starting_multiplier: int,
    bankroll_before: float,
    schedule_map: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, float]:
    if day_picks.empty:
        return [], starting_multiplier, 0.0
    ladder = martingale_double_ladder(settings.max_multiplier)
    current_multiplier = int(starting_multiplier)
    cumulative_cost = 0.0
    events: list[dict[str, Any]] = []
    for pick in day_picks.sort_values(["slot", "score_value"], ascending=[True, False]).itertuples(index=False):
        stake = float(settings.base_stake) * current_multiplier
        total_cost = stake
        if cumulative_cost + total_cost > float(bankroll_before):
            break
        cumulative_cost += total_cost
        slot_1based = int(pick.slot) + 1
        issue_meta = schedule_map.get(slot_1based, {})
        book_points = float(pick.book_pnl) * stake
        events.append(
            {
                "draw_date": pd.Timestamp(pick.date).strftime("%Y-%m-%d"),
                "pre_draw_issue": issue_meta.get("issue"),
                "slot_1based": slot_1based,
                "line_name": "sum",
                "status": "settled",
                "selection_json": {"sum_value": int(pick.sum_value)},
                "odds_display": f"和值 {int(pick.sum_value)} | 净赢 {sum_net_odds_for_value(int(pick.sum_value)):.1f}",
                "stake": stake,
                "multiplier_value": current_multiplier,
                "ticket_count": 1,
                "total_cost": total_cost,
                "hit_count": int(pick.hit),
                "outcome_label": "命中" if int(pick.hit) == 1 else "未中",
                "pnl": book_points,
                "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
            }
        )
        current_multiplier = next_ladder_multiplier(current_multiplier, ladder, book_points)
    total_book_points = float(sum(item["pnl"] for item in events))
    return events, current_multiplier, total_book_points


def simulate_live_sum_day(
    day_picks: pd.DataFrame,
    starting_multiplier: int,
    bankroll_before: float,
    latest_slot: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, float]:
    if day_picks.empty:
        return [], [], starting_multiplier, 0.0
    ladder = martingale_double_ladder(settings.max_multiplier)
    current_multiplier = int(starting_multiplier)
    cumulative_cost = 0.0
    executed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    provisional_book_points = 0.0
    for pick in day_picks.sort_values(["slot_1based", "score_value"], ascending=[True, False]).itertuples(index=False):
        stake = float(settings.base_stake) * current_multiplier
        total_cost = stake
        if cumulative_cost + total_cost > float(bankroll_before):
            break
        cumulative_cost += total_cost
        payload = {
            "slot_1based": int(pick.slot_1based),
            "pre_draw_issue": pick.pre_draw_issue,
            "sum_value": int(pick.sum_value),
            "sum_index": int(pick.sum_index),
            "score_value": float(pick.score_value),
            "odds_display": f"和值 {int(pick.sum_value)} | 净赢 {sum_net_odds_for_value(int(pick.sum_value)):.1f}",
            "multiplier_value": current_multiplier,
            "stake": stake,
            "ticket_count": 1,
            "total_cost": total_cost,
        }
        if int(pick.slot_1based) <= int(latest_slot):
            book_units = float(pick.book_pnl)
            book_points = book_units * stake
            executed.append(
                {
                    **payload,
                    "status": "executed",
                    "hit_count": int(pick.hit),
                    "outcome_label": "命中" if int(pick.hit) == 1 else "未中",
                    "book_pnl_units": book_units,
                    "book_pnl": book_points,
                }
            )
            provisional_book_points += book_points
            current_multiplier = next_ladder_multiplier(current_multiplier, ladder, book_points)
        else:
            pending.append({**payload, "status": "pending"})
    return executed, pending, current_multiplier, provisional_book_points


def finalize_live_state(
    mods: StrategyModules,
    current_date: pd.Timestamp,
    raw_day: pd.DataFrame,
    face_day: pd.DataFrame,
    replay: ReplayResult,
    face_ctx: dict[str, Any],
    sum_ctx: dict[str, Any],
    exact_ctx: dict[str, Any],
    live_payload: dict[str, Any],
) -> dict[str, Any]:
    face_plan = build_live_face_plan(face_ctx, face_day, current_date)
    sum_plan = build_live_sum_plan(mods, sum_ctx, raw_day)
    exact_plan = build_live_exact_plan(mods, exact_ctx, raw_day)
    settled_bankroll = replay.end_bankroll
    face_funded = allocate_live_line("face", settled_bankroll, replay.end_face_multiplier, face_plan["picks"])
    sum_funded = allocate_live_line("sum", settled_bankroll, replay.end_sum_multiplier, sum_plan["picks"])
    exact_funded = allocate_live_line("exact", settled_bankroll, 1, exact_plan["picks"])

    raw_issue_lookup = {int(row.slot_1based): row for row in raw_day.itertuples(index=False)}
    face_issue_lookup = {int(row.slot_1based): row for row in face_day.itertuples(index=False)}
    face_latest_slot = int(len(face_day))
    raw_latest_slot = int(len(raw_day))

    face_executed, face_pending = [], []
    face_book_units = 0.0
    for item in face_funded:
        target = face_issue_lookup.get(int(item["slot_1based"]))
        if target is None or int(item["slot_1based"]) > face_latest_slot:
            face_pending.append(item)
            continue
        ledger, hit_count, label = face_payload_book_units(pd.Series(target._asdict()), item)
        enriched = {
            **item,
            "status": "executed",
            "hit_count": hit_count,
            "outcome_label": label,
            "book_pnl_units": ledger,
            "book_pnl": ledger * item["stake"],
        }
        face_book_units += ledger
        face_executed.append(enriched)
    face_real = daily85(face_book_units * replay.end_face_multiplier) * float(settings.base_stake) if face_funded else 0.0

    sum_executed, sum_pending = [], []
    sum_book_units_total = 0.0
    for item in sum_funded:
        target = raw_issue_lookup.get(int(item["slot_1based"]))
        if target is None or int(item["slot_1based"]) > raw_latest_slot:
            sum_pending.append(item)
            continue
        sum_index = int(item["sum_index"])
        hit = int(int(target.pos1) + int(target.pos2) == int(mods.sum_vmod.INDEX_TO_SUM[sum_index]))
        book_units = sum_book_units(sum_index, hit)
        enriched = {
            **item,
            "status": "executed",
            "hit_count": hit,
            "outcome_label": "命中" if hit else "未中",
            "book_pnl_units": book_units,
            "book_pnl": book_units * item["stake"],
        }
        sum_book_units_total += book_units
        sum_executed.append(enriched)
    sum_real = settle_real(sum_book_units_total * replay.end_sum_multiplier) * float(settings.base_stake) if sum_funded else 0.0

    exact_executed, exact_pending = [], []
    exact_book_units = 0.0
    for item in exact_funded:
        target_slot = int(item["slot_1based"]) + 1
        target = raw_issue_lookup.get(target_slot)
        if target is None or target_slot > raw_latest_slot:
            exact_pending.append(item)
            continue
        number = int(item["number"])
        target_row = pd.Series(target._asdict())
        position_1based = int(item["position_1based"])
        actual_number = int(target_row[f"pos{position_1based}"])
        hit = int(number == actual_number)
        book_units = float(settings.exact_net_win if hit else -1.0)
        enriched = {
            **item,
            "pre_draw_issue": int(target.pre_draw_issue),
            "status": "executed",
            "hit_count": hit,
            "outcome_label": "命中" if hit else f"未中({actual_number})",
            "book_pnl_units": book_units,
            "book_pnl": book_units * item["stake"],
        }
        exact_book_units += book_units
        exact_executed.append(enriched)
    exact_real = settle_real(exact_book_units) * float(settings.base_stake) if exact_funded else 0.0

    total_provisional = float(face_real + sum_real + exact_real)
    current_actions: list[dict[str, Any]] = []
    next_issue = int(live_payload["drawIssue"]) if live_payload.get("drawIssue") else None
    next_raw_slot = raw_latest_slot + 1
    next_face_slot = face_latest_slot + 1

    def maybe_append(line_name: str, candidates: list[dict[str, Any]], target_slot: int | None) -> None:
        if target_slot is None:
            return
        for item in candidates:
            if int(item["slot_1based"]) != int(target_slot):
                continue
            current_actions.append(
                {
                    "line_name": line_name,
                    "draw_issue": next_issue,
                    "slot_1based": int(item["slot_1based"]),
                    "stake": float(item["stake"]),
                    "multiplier_value": int(item["multiplier_value"]),
                    "ticket_count": int(item["ticket_count"]),
                    "total_cost": float(item["total_cost"]),
                    "selection": {
                        key: item[key]
                        for key in ("sum_value", "number", "other", "position_1based", "big_positions", "small_positions", "source")
                        if key in item
                    },
                    "odds_display": item["odds_display"],
                }
            )

    next_face_allowed = True
    draw_time = pd.Timestamp(live_payload["drawTime"]) if live_payload.get("drawTime") else None
    blackout_start = parse_time_of_day(settings.blackout_start)
    blackout_end = parse_time_of_day(settings.blackout_end)
    if draw_time is not None and blackout_start and blackout_end:
        next_face_allowed = not (blackout_start <= draw_time.time() < blackout_end)

    maybe_append("face", face_pending, next_face_slot if next_face_allowed else None)
    maybe_append("sum", sum_pending, next_raw_slot)
    maybe_append("exact", exact_pending, next_raw_slot)

    return {
        "settled_bankroll": settled_bankroll,
        "today_provisional_pnl": total_provisional,
        "estimated_close_bankroll": settled_bankroll + total_provisional,
        "current_actions": current_actions,
        "face": {
            "mode": face_plan["mode"],
            "multiplier_value": replay.end_face_multiplier,
            "requested_slots": len(face_plan["picks"]),
            "funded_slots": len(face_funded),
            "executed_slots": len(face_executed),
            "pending_slots": len(face_pending),
            "provisional_pnl": face_real,
            "status": face_plan["status"],
            "message": face_plan["message"],
            "executed": face_executed,
            "pending": face_pending,
        },
        "sum": {
            "multiplier_value": replay.end_sum_multiplier,
            "requested_slots": sum_plan["requested_slots"],
            "funded_slots": len(sum_funded),
            "executed_slots": len(sum_executed),
            "pending_slots": len(sum_pending),
            "provisional_pnl": sum_real,
            "status": sum_plan["status"],
            "message": sum_plan["message"],
            "executed": sum_executed,
            "pending": sum_pending,
        },
        "exact": {
            "multiplier_value": 1,
            "requested_slots": exact_plan["requested_slots"],
            "funded_slots": len(exact_funded),
            "executed_slots": len(exact_executed),
            "pending_slots": len(exact_pending),
            "provisional_pnl": exact_real,
            "status": exact_plan["status"],
            "message": exact_plan["message"],
            "executed": exact_executed,
            "pending": exact_pending,
        },
    }


def build_historical_bet_rows(
    mods: StrategyModules,
    replay: ReplayResult,
    face_ctx: dict[str, Any],
    sum_ctx: dict[str, Any],
    exact_ctx: dict[str, Any],
    current_live: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    settled_df = replay.daily_df
    face_schedule = face_ctx["schedule_map"]
    sum_schedule = sum_ctx["schedule_map"]
    exact_schedule = exact_ctx["schedule_map"]
    market = current_live.get("market", {})
    simulation_start = pd.Timestamp(settings.simulation_start_date).strftime("%Y-%m-%d")

    def current_live_issue_for_raw(slot_1based: int) -> int | None:
        latest_issue = market.get("pre_draw_issue")
        latest_slot = market.get("raw_latest_slot")
        if latest_issue is None or latest_slot is None:
            return None
        return int(latest_issue) - int(latest_slot) + int(slot_1based)

    for row in settled_df.itertuples(index=False):
        date_key = pd.Timestamp(row.date).strftime("%Y-%m-%d")
        face_components = face_mode_components(str(row.face_mode))
        for source_name in face_components:
            for item in face_ctx["plan_by_date"].get(date_key, {}).get(source_name, []):
                issue_meta = face_schedule.get(date_key, {}).get(int(item["slot_1based"]))
                if not issue_meta:
                    continue
                rows.append(
                    {
                        "draw_date": date_key,
                        "pre_draw_issue": issue_meta["issue"],
                        "slot_1based": int(item["slot_1based"]),
                        "line_name": "face",
                        "status": "settled",
                        "selection_json": {
                            "source": source_name,
                            "big_positions": item["big_positions"],
                            "small_positions": item["small_positions"],
                        },
                        "odds_display": item["odds_display"],
                        "stake": float(settings.base_stake) * int(row.face_multiplier or 1),
                        "multiplier_value": int(row.face_multiplier or 1),
                        "ticket_count": int(item["ticket_count"]),
                        "total_cost": float(settings.base_stake) * int(row.face_multiplier or 1) * int(item["ticket_count"]),
                        "hit_count": None,
                        "outcome_label": None,
                        "pnl": None,
                        "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
                    }
                )
        if int(row.sum_funded_slots) > 0:
            picks = sum_ctx["picks_by_date"].get(pd.Timestamp(row.date), pd.DataFrame()).head(int(row.sum_funded_slots))
            for pick in picks.itertuples(index=False):
                slot_1based = int(pick.slot) + 1
                issue_meta = sum_schedule.get(date_key, {}).get(slot_1based)
                if not issue_meta:
                    continue
                rows.append(
                    {
                        "draw_date": date_key,
                        "pre_draw_issue": issue_meta["issue"],
                        "slot_1based": slot_1based,
                        "line_name": "sum",
                        "status": "settled",
                        "selection_json": {"sum_value": int(pick.sum_value)},
                        "odds_display": f"和值 {int(pick.sum_value)} | 净赢 {sum_net_odds_for_value(int(pick.sum_value)):.1f}",
                        "stake": float(settings.base_stake) * int(row.sum_multiplier or 1),
                        "multiplier_value": int(row.sum_multiplier or 1),
                        "ticket_count": 1,
                        "total_cost": float(settings.base_stake) * int(row.sum_multiplier or 1),
                        "hit_count": int(pick.hit),
                        "outcome_label": "命中" if int(pick.hit) == 1 else "未中",
                        "pnl": float(pick.book_pnl) * float(settings.base_stake) * int(row.sum_multiplier or 1),
                        "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
                    }
                )
        if int(row.exact_funded_slots) > 0:
            picks = exact_ctx["picks_by_date"].get(pd.Timestamp(row.date), pd.DataFrame()).head(int(row.exact_funded_slots))
            for pick in picks.itertuples(index=False):
                issue_meta = exact_schedule.get(date_key, {}).get(int(pick.slot_1based))
                if not issue_meta:
                    continue
                rows.append(
                    {
                        "draw_date": date_key,
                        "pre_draw_issue": issue_meta["issue"],
                        "slot_1based": int(pick.slot_1based),
                        "line_name": "exact",
                        "status": "settled",
                        "selection_json": {
                            "number": int(pick.selected_number_exec),
                            "other": (
                                None
                                if not hasattr(pick, "prefix_other_number") or pd.isna(pick.prefix_other_number)
                                else int(pick.prefix_other_number)
                            ),
                            "position_1based": int(pick.position_1based),
                        },
                        "odds_display": f"定位胆 {int(pick.selected_number_exec)} | 净赢 {float(settings.exact_net_win):.1f}",
                        "stake": float(settings.base_stake),
                        "multiplier_value": 1,
                        "ticket_count": 1,
                        "total_cost": float(settings.base_stake),
                        "hit_count": int(pick.exact_hit_exec),
                        "outcome_label": "命中" if int(pick.exact_hit_exec) == 1 else "未中",
                        "pnl": float(pick.cell_book_pnl_units) * float(settings.base_stake),
                        "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
                    }
                )
    current_date_key = str(current_live["market"]["current_date"])
    if current_date_key >= simulation_start:
        for line_name in ("face", "sum", "exact"):
            line_state = current_live[line_name]
            for bucket_name in ("executed", "pending"):
                status = "executed" if bucket_name == "executed" else "pending"
                for item in line_state[bucket_name]:
                    row_issue = item.get("pre_draw_issue")
                    if line_name in {"sum", "exact"} and row_issue is None:
                        row_issue = current_live_issue_for_raw(int(item["slot_1based"])) or row_issue
                    rows.append(
                        {
                            "draw_date": current_date_key,
                            "pre_draw_issue": row_issue,
                            "slot_1based": int(item["slot_1based"]),
                            "line_name": line_name,
                            "status": status,
                            "selection_json": {
                                key: item[key]
                                for key in ("sum_value", "number", "other", "position_1based", "big_positions", "small_positions", "source")
                                if key in item
                            },
                            "odds_display": item["odds_display"],
                            "stake": float(item["stake"]),
                            "multiplier_value": int(item["multiplier_value"]),
                            "ticket_count": int(item["ticket_count"]),
                            "total_cost": float(item["total_cost"]),
                            "hit_count": item.get("hit_count"),
                            "outcome_label": item.get("outcome_label"),
                            "pnl": item.get("book_pnl"),
                            "meta_json": {"basis": "book"},
                        }
                    )
    rows.sort(key=lambda item: (item["draw_date"], item["pre_draw_issue"] or 0, item["line_name"], item["slot_1based"]))
    return rows


def serialize_daily_curve(daily_df: pd.DataFrame) -> list[dict[str, Any]]:
    if daily_df.empty:
        return []
    return [
        {
            "date": pd.Timestamp(row.date).strftime("%Y-%m-%d"),
            "settled_bankroll": float(row.bankroll_after_day),
            "total_real_pnl": float(row.total_real_pnl),
            "face_real_pnl": float(row.face_real_pnl),
            "sum_real_pnl": float(row.sum_real_pnl),
            "exact_real_pnl": float(row.exact_real_pnl),
            "drawdown_from_peak": float(row.drawdown_from_peak),
        }
        for row in daily_df.itertuples(index=False)
    ]


def build_runtime_context(mods: StrategyModules, issue_df: pd.DataFrame) -> dict[str, Any]:
    if issue_df.empty:
        raise RuntimeError("Issue history is empty")
    current_date = pd.Timestamp(issue_df["draw_date"].max()).normalize()
    current_day_complete = len(issue_df[issue_df["draw_date"] == current_date]) >= int(issue_df.groupby("draw_date").size().mode().iloc[0])
    settled_end = current_date if current_day_complete else current_date - pd.Timedelta(days=1)
    face_ctx = build_face_context(mods, issue_df, current_date)
    sum_ctx = build_sum_context(mods, issue_df)
    exact_ctx = build_exact_context(mods, issue_df)
    simulation_start = pd.Timestamp(settings.simulation_start_date)
    if settled_end < simulation_start:
        replay = ReplayResult(
            daily_df=pd.DataFrame(),
            summary={"face_profit": 0.0, "sum_profit": 0.0, "exact_profit": 0.0},
            end_bankroll=float(settings.bankroll_start),
            end_face_multiplier=1,
            end_sum_multiplier=1,
            peak_bankroll=float(settings.bankroll_start),
            min_bankroll=float(settings.bankroll_start),
            max_drawdown=0.0,
            sum_bet_rows=[],
        )
    else:
        replay = replay_shared_bankroll(
            mods=mods,
            sim_start=simulation_start,
            sim_end=settled_end,
            face_ctx=face_ctx,
            sum_ctx=sum_ctx,
            exact_ctx=exact_ctx,
        )
    return {
        "current_date": current_date,
        "current_day_complete": current_day_complete,
        "face_ctx": face_ctx,
        "sum_ctx": sum_ctx,
        "exact_ctx": exact_ctx,
        "replay": replay,
    }


def snapshot_from_context(mods: StrategyModules, issue_df: pd.DataFrame, live_payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    current_date = pd.Timestamp(context["current_date"])
    current_day_complete = bool(context["current_day_complete"])
    face_ctx = context["face_ctx"]
    sum_ctx = context["sum_ctx"]
    exact_ctx = context["exact_ctx"]
    replay: ReplayResult = context["replay"]
    raw_day, face_day = current_day_issue_maps(issue_df, current_date)
    live_state = finalize_live_state(mods, current_date, raw_day, face_day, replay, face_ctx, sum_ctx, exact_ctx, live_payload)
    market = {
        "server_time": str(live_payload.get("serverTime", "")),
        "current_date": current_date.strftime("%Y-%m-%d"),
        "pre_draw_issue": int(live_payload["preDrawIssue"]) if live_payload.get("preDrawIssue") is not None else None,
        "draw_issue": int(live_payload["drawIssue"]) if live_payload.get("drawIssue") is not None else None,
        "pre_draw_code": str(live_payload.get("preDrawCode", "")),
        "draw_time": str(live_payload.get("drawTime", "")),
        "raw_latest_slot": int(len(raw_day)),
        "face_latest_slot": int(len(face_day)),
        "issues_per_day": int(issue_df.groupby("draw_date").size().mode().iloc[0]),
        "current_day_complete": bool(current_day_complete),
    }
    daily_curve = serialize_daily_curve(replay.daily_df)
    if not current_day_complete:
        daily_curve.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "settled_bankroll": float(live_state["estimated_close_bankroll"]),
                "total_real_pnl": float(live_state["today_provisional_pnl"]),
                "face_real_pnl": float(live_state["face"]["provisional_pnl"]),
                "sum_real_pnl": float(live_state["sum"]["provisional_pnl"]),
                "exact_real_pnl": float(live_state["exact"]["provisional_pnl"]),
                "drawdown_from_peak": float((live_state["estimated_close_bankroll"]) - max(replay.peak_bankroll, live_state["estimated_close_bankroll"])),
                "provisional": True,
            }
        )
    contributions = {
        "settled": {
            "face": float(replay.summary.get("face_profit", 0.0)),
            "sum": float(replay.summary.get("sum_profit", 0.0)),
            "exact": float(replay.summary.get("exact_profit", 0.0)),
        },
        "today_provisional": {
            "face": float(live_state["face"]["provisional_pnl"]),
            "sum": float(live_state["sum"]["provisional_pnl"]),
            "exact": float(live_state["exact"]["provisional_pnl"]),
        },
    }
    current_actions = live_state["current_actions"]
    if not current_actions:
        current_actions = [
            {"line_name": "face", "draw_issue": market["draw_issue"], "message": live_state["face"]["message"]},
            {"line_name": "sum", "draw_issue": market["draw_issue"], "message": live_state["sum"]["message"]},
            {"line_name": "exact", "draw_issue": market["draw_issue"], "message": live_state["exact"]["message"]},
        ]
    snapshot = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "ranges": {
            "history_start_date": settings.history_start_date,
            "simulation_start_date": settings.simulation_start_date,
        },
        "market": market,
        "totals": {
            "settled_bankroll": float(live_state["settled_bankroll"]),
            "today_provisional_pnl": float(live_state["today_provisional_pnl"]),
            "estimated_close_bankroll": float(live_state["estimated_close_bankroll"]),
            "peak_bankroll": float(replay.peak_bankroll),
            "min_bankroll": float(replay.min_bankroll),
            "max_drawdown": float(replay.max_drawdown),
        },
        "contributions": contributions,
        "line_state": {
            "face": {key: value for key, value in live_state["face"].items() if key not in {"executed", "pending"}},
            "sum": {key: value for key, value in live_state["sum"].items() if key not in {"executed", "pending"}},
            "exact": {key: value for key, value in live_state["exact"].items() if key not in {"executed", "pending"}},
        },
        "today_plan": {
            "face": live_state["face"],
            "sum": live_state["sum"],
            "exact": live_state["exact"],
        },
        "current_actions": current_actions,
        "daily_curve": daily_curve,
        "replay": replay,
        "bet_rows": build_historical_bet_rows(mods, replay, face_ctx, sum_ctx, exact_ctx, {"market": market, **live_state}),
    }
    return snapshot


def build_snapshot(mods: StrategyModules, issue_df: pd.DataFrame, live_payload: dict[str, Any]) -> dict[str, Any]:
    context = build_runtime_context(mods, issue_df)
    return snapshot_from_context(mods, issue_df, live_payload, context)
