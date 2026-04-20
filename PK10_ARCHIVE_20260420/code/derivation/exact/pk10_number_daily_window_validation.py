#!/usr/bin/env python3
"""
PK10 daily-window validation under day settlement with 0.85 loss discount.

This script keeps the weekly dynamic-pair subgroup scaffold fixed, then asks:
can same-day prefix observations identify a profitable late exact window within
the same calendar day?
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from pk10_number_identifiability_validation import (
    DEFAULT_HISTORY_PKL,
    DEFAULT_NET_WIN,
    DEFAULT_ROUND9_DIR,
    GROUP_LAYOUT,
    NumberBundle,
    build_dynamic_pair_candidate,
    half_distribution_state,
    load_round9_module,
    parse_csv_ints,
    preprocess_number_history,
    support_class_for_slot,
    validate_subgroup_state,
)


GLOBAL_SEED = 20260416
FINAL_LOSS_DISCOUNT = 0.85
DEFAULT_OUTPUT_DIR = Path("/home/asus/code/wechat-relay/number/outputs_daily_window")
DEFAULT_HALF_PRIOR_STRENGTH = 20.0
DEFAULT_LATE_SLOTS = "577,961,1152"
DEFAULT_CONTROL_SLOTS = "193,385,769"
OBS_WINDOWS = (192, 384, 576)
RECENT_ACTIVE_WINDOWS = (182, 91)
DAILY_THRESHOLD_N_MAX = 6

PAIR_RULE_IDS = (
    "front_pair_major_any_info",
    "front_pair_major_margin_q75_only",
    "front_pair_major_consensus_only",
    "front_pair_major_side_q75_only",
    "front_pair_major_margin_and_consensus",
    "front_pair_major_margin_and_side",
)
SINGLETON_RULE_IDS = (
    "front_singleton_always",
    "front_singleton_side_q75_only",
    "front_singleton_exact_q75_only",
)

LATE_BASE_GATES = (
    ("late", "big", "edge_low"),
    ("late", "small", "edge_high"),
    ("late", "small", "edge_low"),
    ("late", "big", "center"),
    ("late", "small", "center"),
)
CONTROL_BASE_GATES = (
    ("control", "big", "edge_low"),
    ("control", "small", "edge_high"),
    ("control", "small", "edge_low"),
    ("control", "big", "center"),
    ("control", "small", "center"),
)
BASE_GATE_SET = set(LATE_BASE_GATES + CONTROL_BASE_GATES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PK10 daily window validation")
    parser.add_argument("--round9-dir", type=Path, default=DEFAULT_ROUND9_DIR)
    parser.add_argument("--history-pkl", type=Path, default=DEFAULT_HISTORY_PKL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--net-win", type=float, default=DEFAULT_NET_WIN)
    parser.add_argument("--late-slots", default=DEFAULT_LATE_SLOTS)
    parser.add_argument("--control-slots", default=DEFAULT_CONTROL_SLOTS)
    parser.add_argument("--half-prior-strength", type=float, default=DEFAULT_HALF_PRIOR_STRENGTH)
    return parser.parse_args()


def settlement_transform_day(x: float) -> float:
    return x if x >= 0.0 else FINAL_LOSS_DISCOUNT * x


def exact_daily_real_ev(p: float, n_bets: int, net_win: float) -> float:
    out = 0.0
    for hits in range(n_bets + 1):
        ledger = (net_win + 1.0) * hits - n_bets
        prob = math.comb(n_bets, hits) * (p**hits) * ((1.0 - p) ** (n_bets - hits))
        out += prob * settlement_transform_day(ledger)
    return out


def subgroup_daily_real_ev(group_p: float, n_bets: int, group_size: int, net_win: float) -> float:
    out = 0.0
    win = (net_win + 1.0) - group_size
    lose = -float(group_size)
    for hits in range(n_bets + 1):
        ledger = win * hits + lose * (n_bets - hits)
        prob = math.comb(n_bets, hits) * (group_p**hits) * ((1.0 - group_p) ** (n_bets - hits))
        out += prob * settlement_transform_day(ledger)
    return out


def threshold_p_star_day(n_bets: int, net_win: float) -> float:
    lo = 0.0
    hi = 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if exact_daily_real_ev(mid, n_bets, net_win) >= 0.0:
            hi = mid
        else:
            lo = mid
    return hi


def threshold_g_star_day(n_bets: int, group_size: int, net_win: float) -> float:
    lo = 0.0
    hi = 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if subgroup_daily_real_ev(mid, n_bets, group_size, net_win) >= 0.0:
            hi = mid
        else:
            lo = mid
    return hi


def build_daily_threshold_table(net_win: float, n_max: int = DAILY_THRESHOLD_N_MAX) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for n_bets in range(1, n_max + 1):
        rows.append(
            {
                "ticket_family": "exact_single",
                "group_size": 1,
                "n_bets_per_day": n_bets,
                "threshold_prob": threshold_p_star_day(n_bets, net_win),
                "fair_prob": 0.10,
                "fair_real_ev": exact_daily_real_ev(0.10, n_bets, net_win),
            }
        )
        for group_size in range(1, 6):
            fair_prob = group_size / 10.0
            rows.append(
                {
                    "ticket_family": "subgroup",
                    "group_size": group_size,
                    "n_bets_per_day": n_bets,
                    "threshold_prob": threshold_g_star_day(n_bets, group_size, net_win),
                    "fair_prob": fair_prob,
                    "fair_real_ev": subgroup_daily_real_ev(fair_prob, n_bets, group_size, net_win),
                }
            )
    return pd.DataFrame(rows)


def build_daily_threshold_lookups(threshold_df: pd.DataFrame) -> Tuple[Dict[int, float], Dict[Tuple[int, int], float]]:
    exact_lookup: Dict[int, float] = {}
    subgroup_lookup: Dict[Tuple[int, int], float] = {}
    for row in threshold_df.itertuples(index=False):
        if row.ticket_family == "exact_single":
            exact_lookup[int(row.n_bets_per_day)] = float(row.threshold_prob)
        else:
            subgroup_lookup[(int(row.group_size), int(row.n_bets_per_day))] = float(row.threshold_prob)
    return exact_lookup, subgroup_lookup


def is_target_gate(support_class: str, side: str, group_id: str) -> bool:
    return (support_class, side, group_id) in BASE_GATE_SET


def base_gate_id_text(support_class: str, side: str, group_id: str) -> str:
    return f"{support_class}|{side}|{group_id}|same_top1_prev=all"


def rule_label(rule_id: str) -> str:
    return {
        "front_pair_major_any_info": "front pair major any info",
        "front_pair_major_margin_q75_only": "front pair major margin q75 only",
        "front_pair_major_consensus_only": "front pair major consensus only",
        "front_pair_major_side_q75_only": "front pair major side q75 only",
        "front_pair_major_margin_and_consensus": "front pair major margin and consensus",
        "front_pair_major_margin_and_side": "front pair major margin and side",
        "front_singleton_always": "front singleton always",
        "front_singleton_side_q75_only": "front singleton side q75 only",
        "front_singleton_exact_q75_only": "front singleton exact q75 only",
    }[rule_id]


def day_split_label(day_ts: pd.Timestamp, round9) -> str:
    if day_ts <= round9.TRAIN_END:
        return "train"
    if day_ts >= round9.TEST_START:
        return "test"
    return "other"


def validate_target_slots(n_slots: int, late_slots: Sequence[int], control_slots: Sequence[int]) -> None:
    bad = [slot for slot in list(late_slots) + list(control_slots) if slot < 1 or slot > n_slots]
    if bad:
        raise RuntimeError(f"Target slots out of range 1..{n_slots}: {sorted(bad)}")


def build_fixed_slot_state_tables(
    bundle: NumberBundle,
    round9,
    signal_state: Dict[str, np.ndarray],
    candidate,
    late_slots: Sequence[int],
    control_slots: Sequence[int],
    half_prior_strength: float,
) -> pd.DataFrame:
    weights = np.array([0.5 ** (age / 4.0) for age in range(candidate.lookback_weeks - 1, -1, -1)], dtype=float)
    target_slots = tuple(sorted(set(late_slots) | set(control_slots)))
    validate_target_slots(bundle.round9_bundle.n_slots, late_slots, control_slots)

    subgroup_rows: List[Dict[str, object]] = []
    prev_state: Dict[Tuple[int, str], Dict[str, int]] = {}
    n_weeks = bundle.round9_bundle.big_cube.shape[0]
    block_start = candidate.lookback_weeks
    block_id = 0
    while block_start < n_weeks:
        block = round9.dynamic_pair_block(bundle.round9_bundle, signal_state, candidate.bucket_model, block_start)
        block_end = min(block_start + candidate.holding_weeks, n_weeks)
        current_state: Dict[Tuple[int, str], Dict[str, int]] = {}
        for slot_1based in target_slots:
            slot = slot_1based - 1
            support_class = support_class_for_slot(slot_1based, late_slots, control_slots)
            for side in ("big", "small"):
                comp = half_distribution_state(
                    bundle=bundle,
                    block=block,
                    block_start=block_start,
                    slot=slot,
                    side=side,
                    weights=weights,
                    half_prior_strength=half_prior_strength,
                )
                key = (slot_1based, side)
                prev = prev_state.get(key)
                same_top1_prev = bool(prev is not None and prev["top1_number"] == comp["top1_number"])
                same_position_prev = bool(prev is not None and prev["position"] == comp["position"])
                base = {
                    "block_id": int(block_id),
                    "block_start_week_idx": int(block_start),
                    "block_end_week_idx": int(block_end - 1),
                    "block_start": str(pd.Timestamp(bundle.round9_bundle.week_start[block_start]).date()),
                    "block_end": str(pd.Timestamp(bundle.round9_bundle.week_end[block_end - 1]).date()),
                    "slot": int(slot),
                    "slot_1based": int(slot_1based),
                    "support_class": support_class,
                    "side": side,
                    "position": int(comp["position"]),
                    "position_1based": int(comp["position_1based"]),
                    "mass_mean": float(comp["mass_mean"]),
                    "top1_number": int(comp["top1_number"]),
                    "top1_share": float(comp["top1_share"]),
                    "top2_number": int(comp["top2_number"]),
                    "top2_share": float(comp["top2_share"]),
                    "top1_margin": float(comp["top1_margin"]),
                    "entropy_half": float(comp["entropy_half"]),
                    "same_top1_prev": bool(same_top1_prev),
                    "same_position_prev": bool(same_position_prev),
                    "raw_top1_exact_p": float(comp["raw_top1_exact_p"]),
                    "slot_gap_pred": float(np.asarray(block["slot_gap_pred"], dtype=float)[slot]),
                }
                for group_id, numbers in GROUP_LAYOUT[side]:
                    numbers_arr = np.array(numbers, dtype=int)
                    local_idx = np.nonzero(np.isin(comp["half_numbers"], numbers_arr))[0]
                    share = float(comp["q_mean"][local_idx].sum())
                    raw_group_p = float(comp["mass_mean"] * share)
                    best_local = int(local_idx[np.argmax(comp["q_mean"][local_idx])])
                    selected_number = int(comp["half_numbers"][best_local])
                    subgroup_rows.append(
                        {
                            **base,
                            "group_id": group_id,
                            "group_numbers_json": json.dumps(list(numbers)),
                            "group_size": int(len(numbers)),
                            "raw_group_share_in_half": share,
                            "raw_group_p": raw_group_p,
                            "selected_number_in_group": selected_number,
                            "selected_number": selected_number,
                            "raw_selected_exact_p": float(comp["mass_mean"] * comp["q_mean"][best_local]),
                            "base_gate_id": base_gate_id_text(support_class, side, group_id),
                        }
                    )
                current_state[key] = {"position": int(comp["position"]), "top1_number": int(comp["top1_number"])}
        prev_state = current_state
        block_start = block_end
        block_id += 1
    out = pd.DataFrame(subgroup_rows)
    validate_subgroup_state(out)
    return out


def choose_prefix_major(count_a: int, count_b: int, num_a: int, num_b: int, block_selected_number: int) -> int:
    if count_a > count_b:
        return int(num_a)
    if count_b > count_a:
        return int(num_b)
    if block_selected_number in (num_a, num_b):
        return int(block_selected_number)
    return int(min(num_a, num_b))


def build_daily_front_state(
    bundle: NumberBundle,
    subgroup_state_df: pd.DataFrame,
    obs_windows: Sequence[int],
    round9,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    filtered = subgroup_state_df[
        subgroup_state_df.apply(
            lambda row: is_target_gate(str(row["support_class"]), str(row["side"]), str(row["group_id"])),
            axis=1,
        )
    ].copy()
    for row in filtered.itertuples(index=False):
        group_numbers = [int(x) for x in json.loads(row.group_numbers_json)]
        side_numbers = list(range(6, 11)) if row.side == "big" else list(range(1, 6))
        for obs_window in obs_windows:
            if int(row.slot_1based) <= int(obs_window):
                continue
            for week_idx in range(int(row.block_start_week_idx), int(row.block_end_week_idx) + 1):
                week_start_ts = pd.Timestamp(bundle.round9_bundle.week_start[week_idx])
                for day_idx in range(7):
                    day_ts = week_start_ts + pd.Timedelta(days=day_idx)
                    sequence = bundle.number_cube[week_idx, day_idx, :, int(row.position)].astype(int)
                    prefix_seq = sequence[:obs_window]
                    target_number = int(sequence[int(row.slot)])
                    prefix_side_hits = int(np.isin(prefix_seq, side_numbers).sum())
                    prefix_group_hits = int(np.isin(prefix_seq, group_numbers).sum())
                    prefix_side_rate = float(prefix_side_hits / obs_window)
                    prefix_group_rate = float(prefix_group_hits / obs_window)
                    block_selected_number = int(row.selected_number)
                    prefix_block_exact_hits = int(np.sum(prefix_seq == block_selected_number))
                    prefix_block_exact_rate = float(prefix_block_exact_hits / obs_window)

                    prefix_major_number = block_selected_number
                    prefix_major_share = 1.0
                    prefix_pair_margin = 1.0
                    prefix_major_matches_block = True
                    pair_count_a = np.nan
                    pair_count_b = np.nan
                    other_number = np.nan
                    if int(row.group_size) == 2:
                        num_a, num_b = group_numbers
                        count_a = int(np.sum(prefix_seq == num_a))
                        count_b = int(np.sum(prefix_seq == num_b))
                        prefix_major_number = choose_prefix_major(count_a, count_b, num_a, num_b, block_selected_number)
                        other_number = int(num_b if prefix_major_number == num_a else num_a)
                        if prefix_group_hits > 0:
                            prefix_major_share = float(max(count_a, count_b) / prefix_group_hits)
                            prefix_pair_margin = float(abs(count_a - count_b) / prefix_group_hits)
                        else:
                            prefix_major_share = 0.5
                            prefix_pair_margin = 0.0
                        prefix_major_matches_block = bool(prefix_major_number == block_selected_number)
                        pair_count_a = float(count_a)
                        pair_count_b = float(count_b)

                    rows.append(
                        {
                            "block_id": int(row.block_id),
                            "week_idx": int(week_idx),
                            "day_idx_in_week": int(day_idx),
                            "day_date": str(day_ts.date()),
                            "split": day_split_label(day_ts, round9),
                            "slot": int(row.slot),
                            "slot_1based": int(row.slot_1based),
                            "support_class": str(row.support_class),
                            "side": str(row.side),
                            "group_id": str(row.group_id),
                            "group_size": int(row.group_size),
                            "obs_window": int(obs_window),
                            "position": int(row.position),
                            "position_1based": int(row.position_1based),
                            "same_top1_prev": bool(row.same_top1_prev),
                            "same_position_prev": bool(row.same_position_prev),
                            "base_gate_id": str(row.base_gate_id),
                            "group_numbers_json": row.group_numbers_json,
                            "selected_number_block": block_selected_number,
                            "target_number": target_number,
                            "prefix_side_hits": prefix_side_hits,
                            "prefix_side_rate": prefix_side_rate,
                            "prefix_group_hits": prefix_group_hits,
                            "prefix_group_rate": prefix_group_rate,
                            "prefix_block_exact_hits": prefix_block_exact_hits,
                            "prefix_block_exact_rate": prefix_block_exact_rate,
                            "prefix_major_number": int(prefix_major_number),
                            "prefix_other_number": other_number,
                            "prefix_major_share": float(prefix_major_share),
                            "prefix_pair_margin": float(prefix_pair_margin),
                            "prefix_major_matches_block": bool(prefix_major_matches_block),
                            "pair_count_a": pair_count_a,
                            "pair_count_b": pair_count_b,
                            "group_hit_outcome": int(target_number in group_numbers),
                            "block_exact_hit_outcome": int(target_number == block_selected_number),
                            "prefix_major_exact_hit_outcome": int(target_number == prefix_major_number),
                            "slot_gap_pred": float(row.slot_gap_pred),
                        }
                    )
    return pd.DataFrame(rows)


def build_daily_rule_state(front_state_df: pd.DataFrame) -> pd.DataFrame:
    work = front_state_df.copy()
    train_df = work[work["split"] == "train"].copy()

    pair_train = train_df[train_df["group_size"] == 2].copy()
    singleton_train = train_df[train_df["group_size"] == 1].copy()

    pair_margin_q75: Dict[Tuple[str, int], float] = {}
    pair_side_q75: Dict[Tuple[str, int], float] = {}
    singleton_side_q75: Dict[Tuple[str, int], float] = {}
    singleton_exact_q75: Dict[Tuple[str, int], float] = {}

    for key, sub in pair_train.groupby(["base_gate_id", "obs_window"], sort=False):
        pair_margin_q75[key] = float(sub["prefix_pair_margin"].quantile(0.75))
        pair_side_q75[key] = float(sub["prefix_side_rate"].quantile(0.75))
    for key, sub in singleton_train.groupby(["base_gate_id", "obs_window"], sort=False):
        singleton_side_q75[key] = float(sub["prefix_side_rate"].quantile(0.75))
        singleton_exact_q75[key] = float(sub["prefix_block_exact_rate"].quantile(0.75))

    work["pair_margin_q75_train"] = work.apply(
        lambda row: pair_margin_q75.get((str(row["base_gate_id"]), int(row["obs_window"])), float("nan")),
        axis=1,
    )
    work["pair_side_q75_train"] = work.apply(
        lambda row: pair_side_q75.get((str(row["base_gate_id"]), int(row["obs_window"])), float("nan")),
        axis=1,
    )
    work["singleton_side_q75_train"] = work.apply(
        lambda row: singleton_side_q75.get((str(row["base_gate_id"]), int(row["obs_window"])), float("nan")),
        axis=1,
    )
    work["singleton_exact_q75_train"] = work.apply(
        lambda row: singleton_exact_q75.get((str(row["base_gate_id"]), int(row["obs_window"])), float("nan")),
        axis=1,
    )

    pair_mask = work["group_size"] == 2
    singleton_mask = work["group_size"] == 1
    any_info = pair_mask & (work["prefix_group_hits"] > 0)
    work["rule_front_pair_major_any_info"] = any_info
    work["rule_front_pair_major_margin_q75_only"] = any_info & (
        work["prefix_pair_margin"] >= work["pair_margin_q75_train"]
    )
    work["rule_front_pair_major_consensus_only"] = any_info & work["prefix_major_matches_block"]
    work["rule_front_pair_major_side_q75_only"] = any_info & (
        work["prefix_side_rate"] >= work["pair_side_q75_train"]
    )
    work["rule_front_pair_major_margin_and_consensus"] = any_info & (
        (work["prefix_pair_margin"] >= work["pair_margin_q75_train"]) & work["prefix_major_matches_block"]
    )
    work["rule_front_pair_major_margin_and_side"] = any_info & (
        (work["prefix_pair_margin"] >= work["pair_margin_q75_train"])
        & (work["prefix_side_rate"] >= work["pair_side_q75_train"])
    )

    work["rule_front_singleton_always"] = singleton_mask
    work["rule_front_singleton_side_q75_only"] = singleton_mask & (
        work["prefix_side_rate"] >= work["singleton_side_q75_train"]
    )
    work["rule_front_singleton_exact_q75_only"] = singleton_mask & (
        work["prefix_block_exact_rate"] >= work["singleton_exact_q75_train"]
    )
    return work


def rule_ids_for_group_size(group_size: int) -> Tuple[str, ...]:
    return SINGLETON_RULE_IDS if int(group_size) == 1 else PAIR_RULE_IDS


def selected_number_for_rule(rule_id: str, row: pd.Series) -> int:
    if int(row["group_size"]) == 1:
        return int(row["selected_number_block"])
    return int(row["prefix_major_number"])


def row_value(row, key: str):
    if isinstance(row, pd.Series):
        return row[key]
    return getattr(row, key)


def selected_other_for_rule(rule_id: str, row):
    if int(row_value(row, "group_size")) == 1:
        return None
    other = row_value(row, "prefix_other_number")
    return None if pd.isna(other) else int(other)


def build_daily_execution_samples(rule_state_df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    key_cols = ["base_gate_id", "support_class", "side", "group_id", "group_size", "obs_window"]
    for base_key, base_df in rule_state_df.groupby(key_cols, sort=False):
        base_gate_id, support_class, side, group_id, group_size, obs_window = base_key
        for rule_id in rule_ids_for_group_size(int(group_size)):
            work = base_df.copy()
            rule_col = f"rule_{rule_id}"
            work["execute_exact"] = work[rule_col].astype(bool)
            work["selected_number_exec"] = work.apply(
                lambda row: selected_number_for_rule(rule_id, row),
                axis=1,
            )
            work["exact_hit_exec"] = np.where(
                work["execute_exact"],
                (work["target_number"] == work["selected_number_exec"]).astype(int),
                0,
            )
            work["group_hit_exec"] = np.where(work["execute_exact"], work["group_hit_outcome"], 0)
            grouped = (
                work.groupby(["day_date", "split"], sort=False)
                .agg(
                    issue_exposures=("execute_exact", "sum"),
                    group_hits_count=("group_hit_exec", "sum"),
                    exact_hits_count=("exact_hit_exec", "sum"),
                    executed_slots=("execute_exact", "sum"),
                )
                .reset_index()
            )
            selected_cells = (
                work[work["execute_exact"]]
                .groupby("day_date", sort=False)
                .apply(
                    lambda sub: json.dumps(
                        [
                            {
                                "slot": int(row.slot_1based),
                                "number": int(row.selected_number_exec),
                                "other": selected_other_for_rule(rule_id, row),
                            }
                            for row in sub.itertuples(index=False)
                        ],
                        ensure_ascii=False,
                    )
                )
                .to_dict()
            )
            for day_row in grouped.itertuples(index=False):
                issue_exposures = int(day_row.issue_exposures)
                group_hit_rate = float(day_row.group_hits_count / issue_exposures) if issue_exposures else float("nan")
                exact_hit_rate = float(day_row.exact_hits_count / issue_exposures) if issue_exposures else float("nan")
                rows.append(
                    {
                        "base_gate_id": base_gate_id,
                        "support_class": support_class,
                        "side": side,
                        "group_id": group_id,
                        "group_size": int(group_size),
                        "obs_window": int(obs_window),
                        "execution_rule": rule_id,
                        "execution_rule_label": rule_label(rule_id),
                        "day_date": day_row.day_date,
                        "split": day_row.split,
                        "execute_exact": bool(issue_exposures > 0),
                        "executed_slots": int(day_row.executed_slots),
                        "issue_exposures": issue_exposures,
                        "group_hits_count": int(day_row.group_hits_count),
                        "exact_hits_count": int(day_row.exact_hits_count),
                        "group_hit_rate": group_hit_rate,
                        "exact_hit_rate": exact_hit_rate,
                        "selected_cells_json": selected_cells.get(day_row.day_date, "[]"),
                    }
                )
    out = pd.DataFrame(rows)
    out["day_date"] = pd.to_datetime(out["day_date"])
    return out.sort_values(
        ["base_gate_id", "obs_window", "execution_rule", "day_date"],
        kind="stable",
    ).reset_index(drop=True)


def mean_lcb(round9, values: np.ndarray, seed: int) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan")
    low, _ = round9.bootstrap_mean_ci(arr, n_boot=round9.BOOTSTRAP_REPS, seed=seed)
    return float(arr.mean()), float(low)


def compute_recent_metrics(
    round9,
    late_df: pd.DataFrame,
    control_df: pd.DataFrame,
    label: str,
    n_days: int,
    seed_base: int,
) -> Dict[str, float]:
    sub = late_df.tail(n_days)
    if sub.empty:
        return {
            f"{label}_days": 0,
            f"{label}_exact_mean": float("nan"),
            f"{label}_exact_lcb": float("nan"),
            f"{label}_control_mean": float("nan"),
            f"{label}_control_diff": float("nan"),
        }
    late_values = sub["exact_hit_rate"].to_numpy(dtype=float)
    late_mean, late_lcb = mean_lcb(round9, late_values, seed=seed_base + 1)
    out = {
        f"{label}_days": int(len(sub)),
        f"{label}_exact_mean": late_mean,
        f"{label}_exact_lcb": late_lcb,
        f"{label}_control_mean": float("nan"),
        f"{label}_control_diff": float("nan"),
    }
    if not control_df.empty:
        ctrl_sub = control_df.tail(n_days)
        if not ctrl_sub.empty:
            ctrl_mean, _ = mean_lcb(round9, ctrl_sub["exact_hit_rate"].to_numpy(dtype=float), seed=seed_base + 2)
            out[f"{label}_control_mean"] = ctrl_mean
            out[f"{label}_control_diff"] = late_mean - ctrl_mean
    return out


def evaluate_daily_candidates(
    round9,
    daily_execution_samples_df: pd.DataFrame,
    exact_lookup: Dict[int, float],
    subgroup_lookup: Dict[Tuple[int, int], float],
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    counter = 0
    key_cols = [
        "base_gate_id",
        "support_class",
        "side",
        "group_id",
        "group_size",
        "obs_window",
        "execution_rule",
        "execution_rule_label",
    ]
    for key, sub in daily_execution_samples_df.groupby(key_cols, sort=False):
        counter += 1
        base_gate_id, support_class, side, group_id, group_size, obs_window, execution_rule, execution_rule_label = key
        train_df = sub[(sub["split"] == "train") & (sub["issue_exposures"] > 0)].copy()
        test_df = sub[(sub["split"] == "test") & (sub["issue_exposures"] > 0)].copy()
        train_days = int(len(train_df))
        test_days = int(len(test_df))
        n_eff_train = int(math.ceil(float(train_df["issue_exposures"].mean()))) if train_days else 0
        p_star_exact = exact_lookup.get(n_eff_train, float("nan"))
        subgroup_threshold_prob = subgroup_lookup.get((int(group_size), n_eff_train), float("nan"))

        p_exact_train_raw, p_exact_train_lcb = mean_lcb(
            round9,
            train_df["exact_hit_rate"].to_numpy(dtype=float),
            seed=GLOBAL_SEED + counter * 37 + 1,
        )
        sigma_train_raw, sigma_train_lcb = mean_lcb(
            round9,
            train_df["group_hit_rate"].to_numpy(dtype=float),
            seed=GLOBAL_SEED + counter * 37 + 2,
        )
        rho_train_values = (
            train_df.loc[train_df["group_hits_count"] > 0, "exact_hits_count"]
            / train_df.loc[train_df["group_hits_count"] > 0, "group_hits_count"]
        ).to_numpy(dtype=float)
        rho_train_raw, rho_train_lcb = mean_lcb(
            round9,
            rho_train_values,
            seed=GLOBAL_SEED + counter * 37 + 3,
        )
        p_exact_test_raw = float(test_df["exact_hit_rate"].mean()) if test_days else float("nan")
        sigma_test_raw = float(test_df["group_hit_rate"].mean()) if test_days else float("nan")
        rho_test_df = test_df[test_df["group_hits_count"] > 0]
        rho_test_raw = (
            float((rho_test_df["exact_hits_count"] / rho_test_df["group_hits_count"]).mean())
            if not rho_test_df.empty
            else float("nan")
        )
        rho_needed_at_sigma_lcb = (
            float(p_star_exact / sigma_train_lcb)
            if n_eff_train and np.isfinite(p_star_exact) and np.isfinite(sigma_train_lcb) and sigma_train_lcb > 0
            else float("nan")
        )

        rows.append(
            {
                "base_gate_id": base_gate_id,
                "support_class": support_class,
                "side": side,
                "group_id": group_id,
                "group_size": int(group_size),
                "obs_window": int(obs_window),
                "execution_rule": execution_rule,
                "execution_rule_label": execution_rule_label,
                "train_active_days": train_days,
                "test_active_days": test_days,
                "n_eff_train": n_eff_train,
                "p_star_exact": p_star_exact,
                "subgroup_threshold_prob": subgroup_threshold_prob,
                "sigma_train_raw": sigma_train_raw,
                "sigma_train_lcb": sigma_train_lcb,
                "sigma_test_raw": sigma_test_raw,
                "rho_train_raw": rho_train_raw,
                "rho_train_lcb": rho_train_lcb,
                "rho_test_raw": rho_test_raw,
                "p_exact_train_raw": p_exact_train_raw,
                "p_exact_train_lcb": p_exact_train_lcb,
                "p_exact_test_raw": p_exact_test_raw,
                "rho_needed_at_sigma_lcb": rho_needed_at_sigma_lcb,
                "late_minus_control_exact_train": float("nan"),
                "late_minus_control_exact_test": float("nan"),
                "recent182_days": 0,
                "recent182_exact_mean": float("nan"),
                "recent182_exact_lcb": float("nan"),
                "recent182_control_mean": float("nan"),
                "recent182_control_diff": float("nan"),
                "recent91_days": 0,
                "recent91_exact_mean": float("nan"),
                "recent91_exact_lcb": float("nan"),
                "recent91_control_mean": float("nan"),
                "recent91_control_diff": float("nan"),
                "daily_window": False,
            }
        )

    candidate_df = pd.DataFrame(rows)
    for side in ("big", "small"):
        for group_id in ("edge_low", "edge_high", "center"):
            for obs_window in OBS_WINDOWS:
                group_candidates = candidate_df[
                    (candidate_df["side"] == side)
                    & (candidate_df["group_id"] == group_id)
                    & (candidate_df["obs_window"] == obs_window)
                ]
                for execution_rule in group_candidates["execution_rule"].drop_duplicates().tolist():
                    late_row = group_candidates[
                        (group_candidates["support_class"] == "late")
                        & (group_candidates["execution_rule"] == execution_rule)
                    ]
                    control_row = group_candidates[
                        (group_candidates["support_class"] == "control")
                        & (group_candidates["execution_rule"] == execution_rule)
                    ]
                    if late_row.empty:
                        continue
                    late_idx = late_row.index[0]
                    if not control_row.empty:
                        control_idx = control_row.index[0]
                        train_diff = float(
                            candidate_df.at[late_idx, "p_exact_train_raw"] - candidate_df.at[control_idx, "p_exact_train_raw"]
                        )
                        test_diff = float(
                            candidate_df.at[late_idx, "p_exact_test_raw"] - candidate_df.at[control_idx, "p_exact_test_raw"]
                        )
                        candidate_df.at[late_idx, "late_minus_control_exact_train"] = train_diff
                        candidate_df.at[late_idx, "late_minus_control_exact_test"] = test_diff
                        candidate_df.at[control_idx, "late_minus_control_exact_train"] = train_diff
                        candidate_df.at[control_idx, "late_minus_control_exact_test"] = test_diff

                        late_samples = daily_execution_samples_df[
                            (daily_execution_samples_df["base_gate_id"] == candidate_df.at[late_idx, "base_gate_id"])
                            & (daily_execution_samples_df["obs_window"] == obs_window)
                            & (daily_execution_samples_df["execution_rule"] == execution_rule)
                            & (daily_execution_samples_df["support_class"] == "late")
                            & (daily_execution_samples_df["split"] == "test")
                            & (daily_execution_samples_df["issue_exposures"] > 0)
                        ]
                        control_samples = daily_execution_samples_df[
                            (daily_execution_samples_df["base_gate_id"] == candidate_df.at[control_idx, "base_gate_id"])
                            & (daily_execution_samples_df["obs_window"] == obs_window)
                            & (daily_execution_samples_df["execution_rule"] == execution_rule)
                            & (daily_execution_samples_df["support_class"] == "control")
                            & (daily_execution_samples_df["split"] == "test")
                            & (daily_execution_samples_df["issue_exposures"] > 0)
                        ]
                        for recent_days in RECENT_ACTIVE_WINDOWS:
                            metrics = compute_recent_metrics(
                                round9=round9,
                                late_df=late_samples,
                                control_df=control_samples,
                                label=f"recent{recent_days}",
                                n_days=recent_days,
                                seed_base=GLOBAL_SEED + obs_window * 1000 + recent_days * 10,
                            )
                            for col, value in metrics.items():
                                candidate_df.at[late_idx, col] = value
                                candidate_df.at[control_idx, col] = value

    late_mask = candidate_df["support_class"] == "late"
    control_train_exists = candidate_df["late_minus_control_exact_train"].notna()
    control_test_exists = candidate_df["late_minus_control_exact_test"].notna()
    candidate_df.loc[late_mask, "daily_window"] = (
        (candidate_df.loc[late_mask, "p_exact_train_lcb"] > candidate_df.loc[late_mask, "p_star_exact"])
        & (candidate_df.loc[late_mask, "p_exact_test_raw"] >= candidate_df.loc[late_mask, "p_exact_train_lcb"] - 0.01)
        & (
            (~control_train_exists[late_mask])
            | (candidate_df.loc[late_mask, "late_minus_control_exact_train"] > 0.0)
        )
        & (
            (~control_test_exists[late_mask])
            | (candidate_df.loc[late_mask, "late_minus_control_exact_test"] >= -0.01)
        )
    )
    return candidate_df


def candidate_sort_key(row: pd.Series) -> Tuple[float, float, float, float, int]:
    daily_window = 1.0 if bool(row["daily_window"]) else 0.0
    exact_margin = (
        float(row["p_exact_train_lcb"] - row["p_star_exact"])
        if np.isfinite(row["p_exact_train_lcb"]) and np.isfinite(row["p_star_exact"])
        else float("-inf")
    )
    control_test = (
        float(row["late_minus_control_exact_test"])
        if np.isfinite(row["late_minus_control_exact_test"])
        else float("-inf")
    )
    test_mean = float(row["p_exact_test_raw"]) if np.isfinite(row["p_exact_test_raw"]) else float("-inf")
    control_priority = 0 if row["support_class"] == "late" else 1
    return (-daily_window, -exact_margin, -control_test, -test_mean, control_priority)


def sort_candidate_level(candidate_df: pd.DataFrame) -> pd.DataFrame:
    work = candidate_df.copy()
    keys = work.apply(candidate_sort_key, axis=1, result_type="expand")
    keys.columns = ["_k1", "_k2", "_k3", "_k4", "_k5"]
    work = pd.concat([work, keys], axis=1)
    work = work.sort_values(
        ["_k1", "_k2", "_k3", "_k4", "_k5", "support_class", "obs_window", "execution_rule"],
        kind="stable",
    )
    return work.drop(columns=["_k1", "_k2", "_k3", "_k4", "_k5"]).reset_index(drop=True)


def build_control_diff_table(candidate_df: pd.DataFrame) -> pd.DataFrame:
    late = candidate_df[candidate_df["support_class"] == "late"].copy()
    control = candidate_df[candidate_df["support_class"] == "control"].copy()
    merged = late.merge(
        control[
            [
                "side",
                "group_id",
                "obs_window",
                "execution_rule",
                "base_gate_id",
                "p_exact_train_raw",
                "p_exact_test_raw",
            ]
        ],
        on=["side", "group_id", "obs_window", "execution_rule"],
        how="left",
        suffixes=("_late", "_control"),
    )
    merged["late_minus_control_exact_train"] = merged["p_exact_train_raw_late"] - merged["p_exact_train_raw_control"]
    merged["late_minus_control_exact_test"] = merged["p_exact_test_raw_late"] - merged["p_exact_test_raw_control"]
    return merged.rename(
        columns={
            "base_gate_id_late": "late_base_gate_id",
            "base_gate_id_control": "control_base_gate_id",
        }
    )


def report_lines(threshold_df: pd.DataFrame, subgroup_state_df: pd.DataFrame, candidate_df: pd.DataFrame) -> List[str]:
    exact_rows = threshold_df[(threshold_df["ticket_family"] == "exact_single") & (threshold_df["group_size"] == 1)]
    p1 = float(exact_rows[exact_rows["n_bets_per_day"] == 1]["threshold_prob"].iloc[0])
    p2 = float(exact_rows[exact_rows["n_bets_per_day"] == 2]["threshold_prob"].iloc[0])
    p3 = float(exact_rows[exact_rows["n_bets_per_day"] == 3]["threshold_prob"].iloc[0])
    late_rows = candidate_df[candidate_df["support_class"] == "late"].copy()
    winners = late_rows[late_rows["daily_window"]].copy()
    top_late = late_rows.head(10)

    lines = [
        "# PK10 Daily Window Validation",
        "",
        "## Config",
        "- Settlement is daily with 0.85 loss discount.",
        f"- Observation windows: `{', '.join(str(x) for x in OBS_WINDOWS)}`.",
        f"- Daily exact thresholds: `p*_1={p1:.6f}`, `p*_2={p2:.6f}`, `p*_3={p3:.6f}`.",
        f"- Subgroup state rows: `{len(subgroup_state_df)}`; candidate rows: `{len(candidate_df)}`.",
        "",
        "## Top Late Candidates",
    ]
    for _, row in top_late.iterrows():
        lines.append(
            f"- `{row['base_gate_id']} | obs={int(row['obs_window'])} | {row['execution_rule']}` -> "
            f"`n_day={int(row['n_eff_train'])}`, "
            f"`train exact/lcb={row['p_exact_train_raw']:.4f}/{row['p_exact_train_lcb']:.4f}`, "
            f"`test exact={row['p_exact_test_raw']:.4f}`, "
            f"`sigma lcb={row['sigma_train_lcb']:.4f}`, "
            f"`rho lcb={row['rho_train_lcb']:.4f}`, "
            f"`late-control train/test={row['late_minus_control_exact_train']:.4f}/{row['late_minus_control_exact_test']:.4f}`, "
            f"`daily_window={bool(row['daily_window'])}`."
        )
    lines.extend(["", "## Conclusion"])
    if winners.empty:
        lines.append("- 在当前 fixed slots 与 prefix rule 族下，仍未找到稳健的日维 exact 窗口。")
    else:
        labels = winners.apply(
            lambda row: f"{row['base_gate_id']} | obs={int(row['obs_window'])} | {row['execution_rule']}",
            axis=1,
        ).tolist()
        lines.append(f"- 已找到日维 exact 窗口，候选为：`{', '.join(labels)}`。")
    return lines


def main() -> None:
    args = parse_args()
    late_slots = parse_csv_ints(args.late_slots)
    control_slots = parse_csv_ints(args.control_slots)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    round9 = load_round9_module(args.round9_dir)
    raw_df = pd.read_pickle(args.history_pkl)
    bundle = preprocess_number_history(raw_df, round9)

    candidate = build_dynamic_pair_candidate(round9)
    counts, exposures = round9.get_bucket_counts(bundle.round9_bundle, candidate.bucket_model)
    signal_state = round9.compute_signal_state(
        counts=counts,
        exposures=exposures,
        lookback_weeks=candidate.lookback_weeks,
        prior_strength=candidate.prior_strength,
        score_model=candidate.score_model,
    )

    threshold_df = build_daily_threshold_table(net_win=args.net_win, n_max=DAILY_THRESHOLD_N_MAX)
    exact_lookup, subgroup_lookup = build_daily_threshold_lookups(threshold_df)

    subgroup_state_df = build_fixed_slot_state_tables(
        bundle=bundle,
        round9=round9,
        signal_state=signal_state,
        candidate=candidate,
        late_slots=late_slots,
        control_slots=control_slots,
        half_prior_strength=args.half_prior_strength,
    )
    front_state_df = build_daily_front_state(
        bundle=bundle,
        subgroup_state_df=subgroup_state_df,
        obs_windows=OBS_WINDOWS,
        round9=round9,
    )
    rule_state_df = build_daily_rule_state(front_state_df)
    daily_execution_samples_df = build_daily_execution_samples(rule_state_df)
    candidate_df = evaluate_daily_candidates(
        round9=round9,
        daily_execution_samples_df=daily_execution_samples_df,
        exact_lookup=exact_lookup,
        subgroup_lookup=subgroup_lookup,
    )
    control_diff_df = build_control_diff_table(candidate_df)
    candidate_df = sort_candidate_level(candidate_df)

    threshold_path = args.output_dir / "number_daily_window_theory_thresholds.csv"
    subgroup_state_path = args.output_dir / "number_daily_window_subgroup_state.csv"
    front_state_path = args.output_dir / "number_daily_window_front_state.csv"
    samples_path = args.output_dir / "number_daily_window_samples.csv"
    candidate_path = args.output_dir / "number_daily_window_candidate_level.csv"
    control_diff_path = args.output_dir / "number_daily_window_control_diff.csv"
    report_path = args.output_dir / "number_daily_window_report.md"

    threshold_df.to_csv(threshold_path, index=False)
    subgroup_state_df.to_csv(subgroup_state_path, index=False)
    front_state_df.to_csv(front_state_path, index=False)
    daily_execution_samples_df.to_csv(samples_path, index=False)
    candidate_df.to_csv(candidate_path, index=False)
    control_diff_df.to_csv(control_diff_path, index=False)
    report_path.write_text(
        "\n".join(report_lines(threshold_df, subgroup_state_df, candidate_df)) + "\n",
        encoding="utf-8",
    )

    print("Saved outputs:")
    for path in [
        threshold_path,
        subgroup_state_path,
        front_state_path,
        samples_path,
        candidate_path,
        control_diff_path,
        report_path,
    ]:
        print(path)


if __name__ == "__main__":
    main()
