from __future__ import annotations

import asyncio
import csv
import json
import os
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pymysql
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from frozen_windows import FROZEN_WINDOWS, resolve_frozen_window


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SHADOW_LOG_PATH = DATA_DIR / "live_shadow_log.csv"

APP_NAME = os.getenv("JSFT_APP_NAME", "JSFT PK10 Shadow")
DB_HOST = os.getenv("JSFT_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("JSFT_DB_PORT", "3307"))
DB_USER = os.getenv("JSFT_DB_USER", "root")
DB_PASS = os.getenv("JSFT_DB_PASS", "")
DB_NAME = os.getenv("JSFT_DB_NAME", "xyft_lottery_data")
DB_TABLE = os.getenv("JSFT_DB_TABLE", "jsft_pks_history")
EXPECTED_ISSUES_PER_DAY = int(os.getenv("JSFT_EXPECTED_ISSUES_PER_DAY", "1152"))
CORE_SUM_VALUE = int(os.getenv("JSFT_CORE_SUM_VALUE", "12"))
CORE_CAP = int(os.getenv("JSFT_CORE_CAP", "15"))
REPLAY_START_DATE = os.getenv("JSFT_REPLAY_START_DATE", "2026-04-20")
REPLAY_HISTORY_START = os.getenv("JSFT_REPLAY_HISTORY_START", "2020-01-01")
BANKROLL_START = float(os.getenv("JSFT_BANKROLL_START", "1000"))
BASE_STAKE = float(os.getenv("JSFT_BASE_STAKE", "1"))
SUM12_NET_ODDS = float(os.getenv("JSFT_SUM12_NET_ODDS", "10"))
DAILY_GATE = os.getenv("JSFT_DAILY_GATE", "g13_26_pos")
ACCOUNT_CACHE_SECONDS = int(os.getenv("JSFT_ACCOUNT_CACHE_SECONDS", "300"))
TIMEZONE = os.getenv("JSFT_TIMEZONE", "Asia/Shanghai")
SHADOW_API_TOKEN = os.getenv("JSFT_SHADOW_API_TOKEN", "")
CURRENT_FROZEN_WINDOW_ID = os.getenv(
    "JSFT_CURRENT_FROZEN_WINDOW_ID",
    "jsft_sum12_cap15__gate_g13_26_pos__daily85",
)

_frozen = resolve_frozen_window(CURRENT_FROZEN_WINDOW_ID)
FROZEN_WINDOW_ID = _frozen["frozen_window_id"]
BASE_WINDOW_ID = _frozen["base_window_id"]
GATE_ID = _frozen["gate"]
DEPLOYMENT_LEVEL = _frozen["deployment_level"]
CHAMPION_READY = bool(_frozen["champion_ready"])
SETTLEMENT_MODE = _frozen["settlement"]

app = FastAPI(title=APP_NAME)
_ACCOUNT_CACHE: dict[str, Any] = {"key": None, "expires_at": 0.0, "value": None}
_ISSUE_COUNTS_CACHE: dict[str, Any] = {"expires_at": 0.0, "value": None}

_STATE_SNAPSHOT: dict[str, Any] | None = None
_STATE_GENERATED_AT: float = 0.0
_STATE_REFRESH_SECONDS: int = int(os.getenv("JSFT_STATE_REFRESH_SECONDS", "120"))
_STATE_BUSY = False

try:
    _tz = __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo(TIMEZONE)
except Exception:
    _tz = None


def now_iso() -> str:
    if _tz:
        return datetime.now(_tz).isoformat(timespec="seconds")
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


class ShadowLogPayload(BaseModel):
    date: str
    recommended_mode: str = "core"
    active_windows: str = "sum12_cap15"
    would_execute_bets_count: int = CORE_CAP
    executed_bets: int = 0
    account_daily_ledger_shadow: float
    account_daily_real_shadow: float
    account_daily_bonus_shadow: float
    data_quality_ok: bool = True
    gate_reason: str = ""
    notes: str = ""


def db_conn() -> pymysql.Connection:
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())


def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    with db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)


def _persist_bets(draw_date: str, tickets: list[dict[str, Any]]) -> None:
    if not tickets:
        return
    try:
        values_parts: list[str] = []
        params: list[Any] = []
        for t in tickets:
            values_parts.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            hit = int(t["hit"])
            pnl_val = round(t["ledger"], 4)
            params.extend([
                draw_date,
                int(t["pre_draw_issue"]),
                int(t["slot_1based"]),
                "冠亚和 12",
                BASE_STAKE,
                BASE_STAKE,
                hit,
                "hit" if hit else "miss",
                pnl_val,
                SUM12_NET_ODDS,
                "settled",
                json.dumps({"sum_value": CORE_SUM_VALUE, "play": "冠亚和", "sum_fs": t.get("sum_fs", 0)}),
                json.dumps({"frozen_window_id": FROZEN_WINDOW_ID}),
            ])
        sql = f"""
            INSERT IGNORE INTO jsft_bet_log
                (draw_date, pre_draw_issue, slot_1based,
                 odds_display, stake, total_cost, hit_count,
                 outcome_label, pnl, multiplier_value, status,
                 selection_json, meta_json)
            VALUES {", ".join(values_parts)}
        """
        execute(sql, tuple(params))
    except Exception:
        pass


def ensure_bet_log_table() -> None:
    execute(
        f"""
        CREATE TABLE IF NOT EXISTS jsft_bet_log (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            draw_date DATE NOT NULL,
            pre_draw_issue BIGINT NULL,
            slot_1based INT NOT NULL,
            line_name VARCHAR(32) NOT NULL DEFAULT 'sum',
            status VARCHAR(16) NOT NULL DEFAULT 'settled',
            selection_json JSON NOT NULL,
            odds_display VARCHAR(255) NOT NULL,
            stake DECIMAL(12,2) NOT NULL,
            multiplier_value INT NOT NULL DEFAULT 1,
            ticket_count INT NOT NULL DEFAULT 1,
            total_cost DECIMAL(12,2) NOT NULL,
            hit_count INT NULL,
            outcome_label VARCHAR(255) NULL,
            pnl DECIMAL(12,4) NULL,
            meta_json JSON NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_line_issue_slot (draw_date, line_name, slot_1based),
            KEY idx_draw_date (draw_date),
            KEY idx_issue (pre_draw_issue)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def table_exists() -> bool:
    rows = query(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = %s
        LIMIT 1
        """,
        (DB_NAME, DB_TABLE),
    )
    return bool(rows)


def uniform_slots(max_slot: int, cap: int) -> list[int]:
    cap = min(int(cap), int(max_slot))
    if cap <= 0:
        return []
    if cap == 1:
        return [1]
    return sorted({int(1 + (max_slot - 1) * idx / (cap - 1)) for idx in range(cap)})


def settle_real(ledger: float) -> float:
    return float(ledger if ledger >= 0 else ledger * 0.85)


def replay_selected_rows(expected_count: int) -> tuple[list[dict[str, Any]], list[str]]:
    slots = uniform_slots(expected_count, CORE_CAP)
    placeholders = ",".join(["%s"] * len(slots))
    day_index_sql = f"""
        SELECT
            draw_date,
            COUNT(*) AS issue_count,
            MIN(pre_draw_issue) AS min_issue
        FROM {DB_TABLE}
        WHERE draw_date >= %s
        GROUP BY draw_date
        HAVING issue_count = %s
    """
    day_rows = query(day_index_sql, (REPLAY_HISTORY_START, expected_count))
    full_dates = {str(row["draw_date"]) for row in day_rows}

    anomaly_dates: list[str] = []
    all_day_index_sql = f"""
        SELECT
            draw_date,
            COUNT(*) AS issue_count,
            MIN(pre_draw_issue) AS min_issue
        FROM {DB_TABLE}
        WHERE draw_date >= %s
        GROUP BY draw_date
        HAVING issue_count >= %s
    """
    all_day_rows = query(all_day_index_sql, (REPLAY_HISTORY_START, expected_count))
    for row in all_day_rows:
        draw_date = str(row["draw_date"])
        if draw_date not in full_dates:
            anomaly_dates.append(draw_date)

    if not full_dates:
        return [], anomaly_dates

    try:
        formatted_dates = "', '".join(sorted(full_dates))
    except Exception:
        formatted_dates = "', '".join(sorted(str(d) for d in full_dates))

    sql = f"""
        SELECT
            DATE_FORMAT(h.draw_date, '%%Y-%%m-%%d') AS draw_date,
            h.pre_draw_issue,
            DATE_FORMAT(h.pre_draw_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS pre_draw_time,
            h.sum_fs,
            CAST(h.pre_draw_issue - day_index.min_issue + 1 AS SIGNED) AS slot_1based,
            day_index.issue_count
        FROM {DB_TABLE} h
        INNER JOIN (
            SELECT
                draw_date,
                COUNT(*) AS issue_count,
                MIN(pre_draw_issue) AS min_issue
            FROM {DB_TABLE}
            WHERE draw_date >= %s
            GROUP BY draw_date
            HAVING issue_count = %s
        ) day_index ON day_index.draw_date = h.draw_date
        WHERE CAST(h.pre_draw_issue - day_index.min_issue + 1 AS SIGNED) IN ({placeholders})
        ORDER BY h.draw_date, slot_1based
    """
    rows = query(sql, tuple([REPLAY_HISTORY_START, expected_count, *slots]))
    return rows, sorted(anomaly_dates)


def summarize_base_day(draw_date: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    hits = sum(1 for row in rows if int(row.get("sum_fs") or 0) == CORE_SUM_VALUE)
    bets = len(rows)
    ledger = ((SUM12_NET_ODDS * hits) - (bets - hits)) * BASE_STAKE
    real = settle_real(ledger)
    return {
        "date": draw_date,
        "base_bets": bets,
        "base_hits": hits,
        "base_ledger": float(ledger),
        "base_real": float(real),
    }


def daily_gate_state(
    prior_base_days: list[dict[str, Any]],
    gate_name: str | None = None,
) -> dict[str, Any]:
    gate = (gate_name or GATE_ID or DAILY_GATE or "always").strip()
    values = [float(row["base_real"]) for row in prior_base_days]
    last13 = values[-13:] if len(values) >= 13 else []
    last26 = values[-26:] if len(values) >= 26 else []
    sum13 = float(sum(last13)) if last13 else 0.0
    sum26 = float(sum(last26)) if last26 else 0.0
    pos13 = int(sum(1 for value in last13 if value > 0.0))
    pos26 = int(sum(1 for value in last26 if value > 0.0))
    active = False
    reason = "gate_off"
    required_days = 0
    if gate in {"always", "fixed", "none"}:
        active = True
        reason = "always_on"
    elif gate == "g13_pos":
        required_days = 13
        active = len(values) >= 13 and sum13 > 0.0
        reason = f"prior13_real={sum13:.2f} > 0"
    elif gate == "g13_26_pos":
        required_days = 26
        active = len(values) >= 26 and sum13 > 0.0 and sum26 > 0.0
        reason = f"prior13_real={sum13:.2f}, prior26_real={sum26:.2f}"
    elif gate == "g7_avg_pos4":
        required_days = 7
        vals = values[-7:] if len(values) >= 7 else []
        active = (
            len(vals) == 7
            and sum(vals) > 0.0
            and sum(1 for value in vals if value > 0.0) >= 4
        )
        reason = (
            f"prior7_real={sum(vals) if vals else 0.0:.2f}, "
            f"positive_days={sum(1 for value in vals if value > 0.0)}"
        )
    elif gate == "g10_avg_pos6":
        required_days = 10
        vals = values[-10:] if len(values) >= 10 else []
        active = (
            len(vals) == 10
            and sum(vals) > 0.0
            and sum(1 for value in vals if value > 0.0) >= 6
        )
        reason = (
            f"prior10_real={sum(vals) if vals else 0.0:.2f}, "
            f"positive_days={sum(1 for value in vals if value > 0.0)}"
        )
    elif gate == "g13_avg_pos7":
        required_days = 13
        active = len(values) >= 13 and sum13 > 0.0 and pos13 >= 7
        reason = f"prior13_real={sum13:.2f}, positive_days={pos13}"
    elif gate == "g26_avg_pos14":
        required_days = 26
        active = len(values) >= 26 and sum26 > 0.0 and pos26 >= 14
        reason = f"prior26_real={sum26:.2f}, positive_days={pos26}"
    else:
        required_days = 26
        active = len(values) >= 26 and sum13 > 0.0 and sum26 > 0.0
        reason = (
            f"unknown gate {gate}; fallback g13_26_pos "
            f"with prior13_real={sum13:.2f}, prior26_real={sum26:.2f}"
        )
    if len(values) < required_days:
        active = False
        reason = f"need {required_days} prior complete days, have {len(values)}"
    return {
        "gate": gate,
        "active": bool(active),
        "reason": reason,
        "prior_days": int(len(values)),
        "prior13_real": round(sum13, 4),
        "prior26_real": round(sum26, 4),
        "prior13_positive_days": pos13,
        "prior26_positive_days": pos26,
    }


def account_replay(
    expected_count: int,
    bankroll_constrained: bool = True,
) -> dict[str, Any]:
    selected, anomaly_dates = replay_selected_rows(expected_count)
    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in selected:
        by_day.setdefault(str(row["draw_date"]), []).append(row)

    bankroll = BANKROLL_START
    peak = BANKROLL_START
    max_drawdown = 0.0
    daily_rows = []
    ticket_rows = []
    base_days: list[dict[str, Any]] = []
    latest_gate_state: dict[str, Any] | None = None
    total_skipped_due_to_bankroll = 0

    unconstrained_running_real = 0.0
    unconstrained_peak = 0.0
    unconstrained_max_dd = 0.0
    unconstrained_daily_rows: list[dict[str, Any]] = []

    for draw_date in sorted(by_day):
        rows_data = sorted(by_day[draw_date], key=lambda item: int(item["slot_1based"]))
        base_day = summarize_base_day(draw_date, rows_data)
        gate_state = daily_gate_state(base_days)
        base_days.append(base_day)
        if draw_date < REPLAY_START_DATE:
            continue
        latest_gate_state = gate_state

        affordable_bets = (
            max(0, int(bankroll // BASE_STAKE))
            if BASE_STAKE > 0 and bankroll > 0
            else 0
        )
        funded_rows = (
            rows_data[: min(len(rows_data), affordable_bets)]
            if gate_state["active"]
            else []
        )
        unconstrained_rows = (
            rows_data[:]  # all selected rows, no bankroll limit
            if gate_state["active"]
            else []
        )

        skipped = 0
        if gate_state["active"] and affordable_bets < len(rows_data):
            skipped = len(rows_data) - affordable_bets
            total_skipped_due_to_bankroll += skipped

        hits = 0
        ledger = 0.0
        tickets = []
        for row in funded_rows:
            hit = int(row.get("sum_fs") or 0) == CORE_SUM_VALUE
            hits += int(hit)
            ticket_ledger = (SUM12_NET_ODDS if hit else -1.0) * BASE_STAKE
            ledger += ticket_ledger
            ticket = {
                "draw_date": draw_date,
                "slot_1based": int(row["slot_1based"]),
                "pre_draw_issue": int(row["pre_draw_issue"]),
                "pre_draw_time": str(row["pre_draw_time"]),
                "sum_fs": int(row.get("sum_fs") or 0),
                "selection": f"冠亚和 {CORE_SUM_VALUE}",
                "hit": hit,
                "ledger": round(ticket_ledger, 4),
            }
            tickets.append(ticket)
            ticket_rows.append(ticket)
        real = settle_real(ledger)
        bonus = real - ledger
        before = bankroll
        bankroll += real
        peak = max(peak, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        unconstrained_hits = 0
        unconstrained_ledger = 0.0
        for row in unconstrained_rows:
            hit = int(row.get("sum_fs") or 0) == CORE_SUM_VALUE
            unconstrained_hits += int(hit)
            ticket_ledger = (SUM12_NET_ODDS if hit else -1.0) * BASE_STAKE
            unconstrained_ledger += ticket_ledger
        unconstrained_real = settle_real(unconstrained_ledger)
        unconstrained_running_real += unconstrained_real
        unconstrained_peak = max(unconstrained_peak, unconstrained_running_real)
        unconstrained_dd = unconstrained_running_real - unconstrained_peak
        unconstrained_max_dd = min(unconstrained_max_dd, unconstrained_dd)

        daily_rows.append(
            {
                "date": draw_date,
                "bankroll_start": round(before, 4),
                "bankroll_end": round(bankroll, 4),
                "window_active": bool(gate_state["active"]),
                "gate_reason": gate_state["reason"],
                "prior13_real": gate_state["prior13_real"],
                "prior26_real": gate_state["prior26_real"],
                "requested_bets": int(len(rows_data) if gate_state["active"] else 0),
                "affordable_bets": int(affordable_bets),
                "bets": int(len(funded_rows)),
                "hits": int(hits),
                "misses": int(len(funded_rows) - hits),
                "base_bets": int(base_day["base_bets"]),
                "base_hits": int(base_day["base_hits"]),
                "base_real": round(float(base_day["base_real"]), 4),
                "ledger": round(ledger, 4),
                "real": round(real, 4),
                "bonus": round(bonus, 4),
                "drawdown": round(drawdown, 4),
                "hit_rate": round(hits / max(len(funded_rows), 1), 6),
                "status": "settled",
                "skipped_bets_due_to_bankroll": skipped,
                "tickets": tickets,
            }
        )
        if bankroll_constrained and draw_date >= REPLAY_START_DATE:
            _persist_bets(draw_date, tickets)

        unconstrained_daily_rows.append(
            {
                "date": draw_date,
                "window_active": bool(gate_state["active"]),
                "gate_reason": gate_state["reason"],
                "requested_bets": int(len(rows_data) if gate_state["active"] else 0),
                "bets": int(len(unconstrained_rows)),
                "hits": int(unconstrained_hits),
                "ledger": round(unconstrained_ledger, 4),
                "real": round(unconstrained_real, 4),
                "running_real": round(unconstrained_running_real, 4),
                "bankroll_constrained": False,
            }
        )

    next_gate_state = daily_gate_state(base_days)

    totals = {
        "start_date": REPLAY_START_DATE,
        "history_start_date": REPLAY_HISTORY_START,
        "bankroll_start": BANKROLL_START,
        "bankroll_current": round(bankroll, 4),
        "total_real": round(bankroll - BANKROLL_START, 4),
        "total_ledger": round(sum(row["ledger"] for row in daily_rows), 4),
        "total_bonus": round(sum(row["bonus"] for row in daily_rows), 4),
        "day_count": int(len(daily_rows)),
        "active_days": int(sum(1 for row in daily_rows if row["bets"] > 0)),
        "cash_days": int(sum(1 for row in daily_rows if row["bets"] == 0)),
        "positive_days": int(sum(1 for row in daily_rows if row["real"] > 0)),
        "negative_days": int(sum(1 for row in daily_rows if row["real"] < 0)),
        "total_bets": int(sum(row["bets"] for row in daily_rows)),
        "total_hits": int(sum(row["hits"] for row in daily_rows)),
        "hit_rate": round(
            sum(row["hits"] for row in daily_rows)
            / max(sum(row["bets"] for row in daily_rows), 1),
            6,
        ),
        "max_drawdown": round(max_drawdown, 4),
        "stake": BASE_STAKE,
        "settlement": SETTLEMENT_MODE,
        "window": BASE_WINDOW_ID,
        "frozen_window_id": FROZEN_WINDOW_ID,
        "gate_id": GATE_ID,
        "sum_value": CORE_SUM_VALUE,
        "daily_gate": DAILY_GATE,
        "latest_gate_active": (
            bool(latest_gate_state["active"]) if latest_gate_state else False
        ),
        "next_gate_active": bool(next_gate_state["active"]),
        "bankroll_constrained": bankroll_constrained,
        "skipped_bets_due_to_bankroll": total_skipped_due_to_bankroll,
        "anomaly_dates_count": len(anomaly_dates),
        "anomaly_dates": anomaly_dates[:30],
    }

    unconstrained_totals = {
        "total_real": round(unconstrained_running_real, 4),
        "total_ledger": round(
            sum(row["ledger"] for row in unconstrained_daily_rows), 4
        ),
        "total_bets": int(sum(row["bets"] for row in unconstrained_daily_rows)),
        "total_hits": int(sum(row["hits"] for row in unconstrained_daily_rows)),
        "hit_rate": round(
            sum(row["hits"] for row in unconstrained_daily_rows)
            / max(sum(row["bets"] for row in unconstrained_daily_rows), 1),
            6,
        ),
        "max_drawdown": round(unconstrained_max_dd, 4),
        "bankroll_constrained": False,
        "unconstrained_note": "No bankroll limit, all active gate rows taken.",
    }

    return {
        "totals": totals,
        "daily": daily_rows,
        "tickets": ticket_rows[-120:],
        "next_gate_state": next_gate_state,
        "unconstrained_shadow_result": {
            "totals": unconstrained_totals,
            "daily": unconstrained_daily_rows,
        },
    }


def cached_account_replay(expected_count: int) -> dict[str, Any]:
    key = (
        expected_count,
        REPLAY_HISTORY_START,
        REPLAY_START_DATE,
        BANKROLL_START,
        BASE_STAKE,
        CORE_SUM_VALUE,
        CORE_CAP,
        SUM12_NET_ODDS,
        DAILY_GATE,
        CURRENT_FROZEN_WINDOW_ID,
    )
    now = time.monotonic()
    if (
        _ACCOUNT_CACHE["key"] == key
        and _ACCOUNT_CACHE["value"] is not None
        and now < float(_ACCOUNT_CACHE["expires_at"])
    ):
        return _ACCOUNT_CACHE["value"]
    value = account_replay(expected_count)
    _ACCOUNT_CACHE.update(
        {"key": key, "value": value, "expires_at": now + ACCOUNT_CACHE_SECONDS}
    )
    return value


def issue_counts(limit: int = 120) -> list[dict[str, Any]]:
    return query(
        f"""
        SELECT
            DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS draw_date,
            COUNT(*) AS issue_count,
            MIN(pre_draw_issue) AS min_issue,
            MAX(pre_draw_issue) AS max_issue,
            MIN(pre_draw_time) AS min_time,
            MAX(pre_draw_time) AS max_time
        FROM {DB_TABLE}
        GROUP BY draw_date
        ORDER BY draw_date DESC
        LIMIT {int(limit)}
        """
    )


def cached_issue_counts(limit: int = 120) -> list[dict[str, Any]]:
    now = time.monotonic()
    if (
        _ISSUE_COUNTS_CACHE["value"] is not None
        and now < float(_ISSUE_COUNTS_CACHE["expires_at"])
    ):
        return _ISSUE_COUNTS_CACHE["value"]
    value = issue_counts(limit)
    _ISSUE_COUNTS_CACHE.update(
        {"value": value, "expires_at": now + ACCOUNT_CACHE_SECONDS}
    )
    return value


def get_data_quality_summary(
    pre_fetched_counts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not table_exists():
        return {
            "status": "missing_table",
            "message": f"DB table {DB_NAME}.{DB_TABLE} does not exist.",
            "days": [],
        }
    rows = pre_fetched_counts if pre_fetched_counts is not None else cached_issue_counts(120)
    if not rows:
        return {
            "status": "empty_table",
            "message": f"DB table {DB_NAME}.{DB_TABLE} exists but has no rows.",
            "days": [],
        }
    issue_counter = Counter(
        int(row["issue_count"]) for row in rows if int(row["issue_count"]) > 0
    )
    inferred_expected = (
        issue_counter.most_common(1)[0][0] if issue_counter else EXPECTED_ISSUES_PER_DAY
    )
    expected_count = EXPECTED_ISSUES_PER_DAY or inferred_expected
    anomaly_dates: list[str] = []
    for row in rows:
        ic = int(row["issue_count"])
        row["expected_count"] = expected_count
        row["is_full_day"] = ic == expected_count
        if ic == expected_count:
            row["anomaly_reason"] = ""
        elif ic < expected_count:
            row["anomaly_reason"] = f"under: {expected_count - ic} missing"
            anomaly_dates.append(str(row["draw_date"]))
        else:
            row["anomaly_reason"] = f"over: {ic - expected_count} extra"
            anomaly_dates.append(str(row["draw_date"]))
    return {
        "status": "ok",
        "expected_count": expected_count,
        "inferred_expected_count": inferred_expected,
        "days": [
            {
                "date": str(row["draw_date"]),
                "issue_count": int(row["issue_count"]),
                "expected_count": int(row["expected_count"]),
                "is_full_day": bool(row["is_full_day"]),
                "anomaly_reason": str(row["anomaly_reason"]),
                "min_issue": int(row.get("min_issue") or 0),
                "max_issue": int(row.get("max_issue") or 0),
                "min_time": str(row.get("min_time") or ""),
                "max_time": str(row.get("max_time") or ""),
            }
            for row in rows
        ],
        "anomaly_date_count": len(anomaly_dates),
        "anomaly_dates": anomaly_dates[:30],
    }


def build_preday_decision(
    prior_base_days: list[dict[str, Any]],
    expected_count: int,
    today_observed_count: int = 0,
) -> dict[str, Any]:
    gate_state = daily_gate_state(prior_base_days)
    recommended_mode = "core" if gate_state["active"] else "cash"
    active_slots = uniform_slots(expected_count, CORE_CAP)
    slots: list[dict[str, Any]] = []
    for slot in active_slots:
        if slot <= today_observed_count:
            status = "observed"
        else:
            status = "pending"
        slots.append({"slot": slot, "status": status})
    would_execute_bets_count = (
        len([s for s in slots if s["status"] == "pending"])
        if gate_state["active"]
        else 0
    )
    return {
        "active": gate_state["active"],
        "gate_reason": gate_state["reason"],
        "recommended_mode": recommended_mode,
        "would_execute_bets_count": would_execute_bets_count,
        "slots": slots,
    }


def leakage_check() -> dict[str, Any]:
    if not table_exists():
        return {
            "status": "missing_table",
            "checked_days": 0,
            "failed_days": 0,
            "failed_rate": 0.0,
            "leakage_free": True,
            "rows": [],
        }
    expected_count = EXPECTED_ISSUES_PER_DAY
    selected, _ = replay_selected_rows(expected_count)
    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in selected:
        by_day.setdefault(str(row["draw_date"]), []).append(row)

    if not by_day:
        return {
            "status": "empty_data",
            "checked_days": 0,
            "failed_days": 0,
            "failed_rate": 0.0,
            "leakage_free": True,
            "rows": [],
        }

    result = cached_account_replay(expected_count)
    daily_map: dict[str, dict[str, Any]] = {
        str(row["date"]): row for row in result.get("daily", [])
    }

    base_days: list[dict[str, Any]] = []
    out_rows: list[dict[str, Any]] = []
    checked = 0
    failed = 0

    for date_str in sorted(by_day.keys()):
        today_rows = by_day[date_str]

        masked_decision = build_preday_decision(
            base_days, expected_count, today_observed_count=0
        )
        prior_days_count = len(base_days)

        if date_str >= REPLAY_START_DATE:
            day_row = daily_map.get(date_str)
            if day_row is not None:
                checked += 1
                original_decision = {
                    "active": bool(day_row.get("window_active", False)),
                    "gate_reason": str(day_row.get("gate_reason", "")),
                    "recommended_mode": (
                        "core" if bool(day_row.get("window_active", False)) else "cash"
                    ),
                    "would_execute_bets_count": int(
                        day_row.get("requested_bets", 0)
                    ),
                }

                decision_equal = (
                    original_decision["active"] == masked_decision["active"]
                    and original_decision["recommended_mode"]
                    == masked_decision["recommended_mode"]
                    and original_decision["gate_reason"] == masked_decision["gate_reason"]
                    and original_decision["would_execute_bets_count"]
                    == masked_decision["would_execute_bets_count"]
                )

                failed_reason = ""
                if not decision_equal:
                    failed += 1
                    parts = []
                    if original_decision["active"] != masked_decision["active"]:
                        parts.append(
                            f"active: orig={original_decision['active']} masked={masked_decision['active']}"
                        )
                    if original_decision["recommended_mode"] != masked_decision["recommended_mode"]:
                        parts.append(
                            f"mode: orig={original_decision['recommended_mode']} masked={masked_decision['recommended_mode']}"
                        )
                    if original_decision["gate_reason"] != masked_decision["gate_reason"]:
                        parts.append("gate_reason differs")
                    if original_decision["would_execute_bets_count"] != masked_decision["would_execute_bets_count"]:
                        parts.append(
                            f"bets: orig={original_decision['would_execute_bets_count']} masked={masked_decision['would_execute_bets_count']}"
                        )
                    failed_reason = "; ".join(parts)

                out_rows.append(
                    {
                        "date": date_str,
                        "prior_days": prior_days_count,
                        "decision_original": original_decision,
                        "decision_masked": masked_decision,
                        "decision_equal": decision_equal,
                        "failed_reason": failed_reason,
                    }
                )

        base_days.append(summarize_base_day(date_str, today_rows))

    return {
        "status": "ok",
        "checked_days": checked,
        "failed_days": failed,
        "failed_rate": round(failed / max(checked, 1), 6),
        "leakage_free": failed == 0,
        "method": "For each complete day from REPLAY_HISTORY_START, gate is recomputed from prior base_days only (masked today). Only days >= REPLAY_START_DATE are compared.",
        "rows": out_rows,
    }


SHADOW_LOG_HEADER = [
    "created_at",
    "date",
    "recommended_mode",
    "active_windows",
    "would_execute_bets_count",
    "executed_bets",
    "account_daily_ledger_shadow",
    "account_daily_real_shadow",
    "account_daily_bonus_shadow",
    "data_quality_ok",
    "gate_reason",
    "notes",
]


def migrate_shadow_log_schema() -> None:
    if not SHADOW_LOG_PATH.exists():
        return
    with SHADOW_LOG_PATH.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        old_header = reader.fieldnames or []
        old_rows: list[dict[str, str]] = list(reader)
    if not old_header:
        _write_new_shadow_log()
        return
    if "executed_bets" in old_header:
        return
    new_rows: list[dict[str, str]] = []
    for row in old_rows:
        new_row: dict[str, str] = {}
        for col in SHADOW_LOG_HEADER:
            if col == "executed_bets":
                new_row[col] = row.get("would_execute_bets_count", "")
            else:
                new_row[col] = row.get(col, "")
        new_rows.append(new_row)
    with SHADOW_LOG_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHADOW_LOG_HEADER)
        writer.writeheader()
        writer.writerows(new_rows)


def _write_new_shadow_log() -> None:
    with SHADOW_LOG_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SHADOW_LOG_HEADER)


def ensure_shadow_log() -> None:
    if SHADOW_LOG_PATH.exists():
        migrate_shadow_log_schema()
        return
    _write_new_shadow_log()


def read_shadow_log(limit: int = 100) -> list[dict[str, Any]]:
    ensure_shadow_log()
    with SHADOW_LOG_PATH.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-limit:]


def settle_latest_complete_day() -> dict[str, Any]:
    dq = get_data_quality_summary()
    full_days = [d for d in dq.get("days", []) if d["is_full_day"]]
    if not full_days:
        return {"status": "no_complete_day", "message": "No complete day found."}
    latest_complete = full_days[0]
    latest_date = str(latest_complete["date"])
    existing_rows = read_shadow_log(500)
    existing_dates = {str(row.get("date", "")) for row in existing_rows}
    if latest_date in existing_dates:
        return {
            "status": "already_settled",
            "date": latest_date,
            "message": f"Date {latest_date} already in shadow log.",
        }
    expected_count = EXPECTED_ISSUES_PER_DAY
    account = cached_account_replay(expected_count)
    daily_rows = account.get("daily", [])
    day_row = None
    for row in daily_rows:
        if str(row["date"]) == latest_date:
            day_row = row
            break
    if day_row is None:
        return {
            "status": "not_in_replay",
            "date": latest_date,
            "message": f"Date {latest_date} not found in replay daily data.",
        }
    day_active = bool(day_row.get("window_active", False))
    day_gate_reason = str(day_row.get("gate_reason", ""))
    payload = ShadowLogPayload(
        date=latest_date,
        recommended_mode=("core" if day_active else "cash"),
        active_windows=FROZEN_WINDOW_ID,
        would_execute_bets_count=int(day_row.get("requested_bets", 0)),
        executed_bets=int(day_row.get("bets", 0)),
        account_daily_ledger_shadow=float(day_row.get("ledger", 0)),
        account_daily_real_shadow=float(day_row.get("real", 0)),
        account_daily_bonus_shadow=float(day_row.get("bonus", 0)),
        data_quality_ok=bool(latest_complete["is_full_day"]),
        gate_reason=day_gate_reason,
        notes=f"auto-settled at {now_iso()}",
    )
    ensure_shadow_log()
    with SHADOW_LOG_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                now_iso(),
                payload.date,
                payload.recommended_mode,
                payload.active_windows,
                payload.would_execute_bets_count,
                payload.executed_bets,
                payload.account_daily_ledger_shadow,
                payload.account_daily_real_shadow,
                payload.account_daily_bonus_shadow,
                int(payload.data_quality_ok),
                payload.gate_reason,
                payload.notes,
            ]
        )
    return {
        "status": "settled",
        "date": latest_date,
        "row": {
            "date": latest_date,
            "recommended_mode": payload.recommended_mode,
            "active_windows": payload.active_windows,
            "would_execute_bets_count": payload.would_execute_bets_count,
            "executed_bets": payload.executed_bets,
            "account_daily_ledger_shadow": payload.account_daily_ledger_shadow,
            "account_daily_real_shadow": payload.account_daily_real_shadow,
            "account_daily_bonus_shadow": payload.account_daily_bonus_shadow,
            "data_quality_ok": payload.data_quality_ok,
            "gate_reason": payload.gate_reason,
        },
    }


def shadow_status() -> dict[str, Any]:
    rows = read_shadow_log(500)
    if not rows:
        return {
            "live_shadow_days": 0,
            "latest_settled_date": None,
            "live13_real": 0.0,
            "live13_ledger": 0.0,
            "live13_bonus": 0.0,
            "live13_positive_days": 0,
            "live13_max_drawdown": 0.0,
            "core_shadow_pass_candidate": False,
            "champion_ready": False,
            "status": "no_shadow_data",
        }
    last13 = rows[-13:]
    last13_real = sum(float(row.get("account_daily_real_shadow", 0)) for row in last13)
    last13_ledger = sum(
        float(row.get("account_daily_ledger_shadow", 0)) for row in last13
    )
    last13_bonus = sum(
        float(row.get("account_daily_bonus_shadow", 0)) for row in last13
    )
    last13_positive = sum(
        1
        for row in last13
        if float(row.get("account_daily_real_shadow", 0)) > 0
    )
    peak = 0.0
    max_dd = 0.0
    running = 0.0
    for row in last13:
        running += float(row.get("account_daily_real_shadow", 0))
        peak = max(peak, running)
        dd = running - peak
        max_dd = min(max_dd, dd)
    pass_candidate = (
        len(last13) >= 13
        and last13_real > 0.0
        and last13_positive >= 7
    )
    return {
        "live_shadow_days": len(rows),
        "latest_settled_date": (
            str(rows[-1].get("date", "")) if rows else None
        ),
        "live13_real": round(last13_real, 4),
        "live13_ledger": round(last13_ledger, 4),
        "live13_bonus": round(last13_bonus, 4),
        "live13_positive_days": last13_positive,
        "live13_max_drawdown": round(max_dd, 4),
        "core_shadow_pass_candidate": pass_candidate,
        "champion_ready": False,
        "frozen_window_id": FROZEN_WINDOW_ID,
        "deployment_level": DEPLOYMENT_LEVEL,
    }


def latest_summary() -> dict[str, Any]:
    if not table_exists():
        return {
            "table_exists": False,
            "status": "missing_table",
            "message": f"DB table {DB_NAME}.{DB_TABLE} does not exist.",
            "frozen_window_id": FROZEN_WINDOW_ID,
            "base_window_id": BASE_WINDOW_ID,
            "gate_id": GATE_ID,
            "deployment_level": DEPLOYMENT_LEVEL,
            "champion_ready": CHAMPION_READY,
        }
    counts_desc = cached_issue_counts(120)
    if not counts_desc:
        return {
            "table_exists": True,
            "status": "empty_table",
            "message": f"DB table {DB_NAME}.{DB_TABLE} exists but has no rows.",
            "frozen_window_id": FROZEN_WINDOW_ID,
            "base_window_id": BASE_WINDOW_ID,
            "gate_id": GATE_ID,
            "deployment_level": DEPLOYMENT_LEVEL,
            "champion_ready": CHAMPION_READY,
        }
    counts = list(reversed(counts_desc))
    issue_counter = Counter(
        int(row["issue_count"]) for row in counts if int(row["issue_count"]) > 0
    )
    inferred_expected = (
        issue_counter.most_common(1)[0][0] if issue_counter else EXPECTED_ISSUES_PER_DAY
    )
    expected_count = EXPECTED_ISSUES_PER_DAY or inferred_expected
    for row in counts:
        row["is_full_day"] = int(row["issue_count"]) == expected_count
    full_rows = [row for row in counts if row["is_full_day"]]
    latest_seen = counts[-1]
    latest_complete = full_rows[-1] if full_rows else None
    latest_complete_date = latest_complete["draw_date"] if latest_complete else None
    target = target_day(latest_seen, latest_complete_date, expected_count)
    account = cached_account_replay(expected_count)
    gate_state = account.get("next_gate_state", {})
    slots = build_decision_slots(
        target, latest_seen, expected_count, gate_state
    )
    shadow_stat = shadow_status()
    dq = get_data_quality_summary(pre_fetched_counts=list(counts_desc))

    return {
        "table_exists": True,
        "status": "ok",
        "frozen_window_id": FROZEN_WINDOW_ID,
        "base_window_id": BASE_WINDOW_ID,
        "gate_id": GATE_ID,
        "deployment_level": DEPLOYMENT_LEVEL,
        "champion_ready": CHAMPION_READY,
        "core_shadow_ready": shadow_stat.get("core_shadow_pass_candidate", False),
        "latest_complete_date": latest_complete_date,
        "data_quality_summary": dq,
        "next_decision": {
            "target": target,
            "gate_state": gate_state,
            "slots": slots,
        },
        "live_shadow_status": shadow_stat,
        "db": {
            "host": DB_HOST,
            "port": DB_PORT,
            "name": DB_NAME,
            "table": DB_TABLE,
        },
        "expected_issues_per_day": expected_count,
        "inferred_expected_issues_per_day": inferred_expected,
        "latest_seen": normalize_row(latest_seen),
        "recent_days": [normalize_row(row) for row in counts_desc[:14]],
        "target": target,
        "core_window": {
            "candidate_id": "sum12_cap15",
            "play": "冠亚和",
            "sum_value": CORE_SUM_VALUE,
            "cap": CORE_CAP,
            "daily_gate": DAILY_GATE,
            "gate_state": gate_state,
            "active_slots": uniform_slots(expected_count, CORE_CAP),
            "decision_slots": slots,
            "would_execute_bets_count": len(
                [
                    slot
                    for slot in slots
                    if slot["status"] in {"planned", "pending"}
                    and target["actionable"]
                ]
            ),
        },
        "readiness": {
            "mode": DEPLOYMENT_LEVEL,
            "champion_ready": CHAMPION_READY,
            "reason": (
                "Forward shadow only. Champion requires 13 complete live-shadow days."
            ),
        },
        "account": account,
        "generated_at": now_iso(),
    }


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key, value in list(out.items()):
        if isinstance(value, (datetime, date)):
            out[key] = value.isoformat(sep=" ")
    out["issue_count"] = int(out.get("issue_count") or 0)
    if out.get("min_issue") is not None:
        out["min_issue"] = int(out["min_issue"])
    if out.get("max_issue") is not None:
        out["max_issue"] = int(out["max_issue"])
    return out


def target_day(
    latest_seen: dict[str, Any],
    latest_complete_date: str | None,
    expected_count: int,
) -> dict[str, Any]:
    tz = _tz
    if tz:
        today = datetime.now(tz).date().isoformat()
    else:
        today = datetime.utcnow().date().isoformat()
    latest_seen_date = str(latest_seen["draw_date"])
    latest_seen_count = int(latest_seen["issue_count"])
    if latest_seen_date == today and latest_seen_count < expected_count:
        target_date = latest_seen_date
        target_kind = "today_partial"
        actionable = True
    elif latest_seen_date < today and latest_seen_count < expected_count:
        target_date = latest_seen_date
        target_kind = "stale_partial_past"
        actionable = False
    elif latest_complete_date:
        target_date = (
            datetime.strptime(latest_complete_date, "%Y-%m-%d").date()
            + timedelta(days=1)
        ).isoformat()
        actionable = target_date >= today
        target_kind = (
            "next_after_latest_complete"
            if actionable
            else "stale_next_after_latest_complete"
        )
    else:
        target_date = today
        target_kind = "today_no_complete_history"
        actionable = True
    return {
        "date": target_date,
        "kind": target_kind,
        "actionable": actionable,
        "today": today,
        "latest_seen_date": latest_seen_date,
        "latest_seen_count": latest_seen_count,
    }


def build_decision_slots(
    target: dict[str, Any],
    latest_seen: dict[str, Any],
    expected_count: int,
    gate_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    gate_state = gate_state or {}
    if not bool(gate_state.get("active", False)):
        return []
    active_slots = uniform_slots(expected_count, CORE_CAP)
    target_is_latest_seen = target["date"] == str(latest_seen["draw_date"])
    observed_count = (
        int(latest_seen["issue_count"]) if target_is_latest_seen else 0
    )
    min_issue = (
        int(latest_seen["min_issue"])
        if target_is_latest_seen and latest_seen.get("min_issue") is not None
        else None
    )
    rows = []
    for slot in active_slots:
        if not target.get("actionable", False) and target_is_latest_seen and slot <= observed_count:
            status = "stale_missed"
        elif not target.get("actionable", False):
            status = "stale_unavailable"
        elif target_is_latest_seen and slot <= observed_count:
            status = "missed"
        elif target_is_latest_seen:
            status = "pending"
        else:
            status = "planned"
        rows.append(
            {
                "slot": slot,
                "sum_value": CORE_SUM_VALUE,
                "window": BASE_WINDOW_ID,
                "frozen_window_id": FROZEN_WINDOW_ID,
                "status": status,
                "expected_issue": (
                    min_issue + slot - 1 if min_issue is not None else None
                ),
            }
        )
    return rows


def _verify_token(request: Request) -> None:
    token = SHADOW_API_TOKEN.strip()
    if not token:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    provided = auth[len("Bearer "):]
    if provided != token:
        raise HTTPException(status_code=403, detail="Invalid API token")


def _health_path(request: Request) -> bool:
    return request.url.path.rstrip("/") in {"/api/health", "/api/frozen-windows"}


async def _refresh_state_snapshot() -> None:
    global _STATE_SNAPSHOT, _STATE_GENERATED_AT, _STATE_BUSY
    if _STATE_BUSY:
        return
    _STATE_BUSY = True
    try:
        snapshot = await asyncio.to_thread(latest_summary)
        _STATE_SNAPSHOT = snapshot
        _STATE_GENERATED_AT = time.monotonic()
    except Exception:
        pass
    finally:
        _STATE_BUSY = False


async def _background_refresher() -> None:
    while True:
        await asyncio.sleep(5)
        if _STATE_SNAPSHOT is None:
            await _refresh_state_snapshot()
            continue
        elapsed = time.monotonic() - _STATE_GENERATED_AT
        if elapsed > _STATE_REFRESH_SECONDS:
            await _refresh_state_snapshot()


@app.on_event("startup")
async def _on_startup() -> None:
    await asyncio.to_thread(ensure_bet_log_table)
    asyncio.create_task(_background_refresher())


@app.middleware("http")
async def token_middleware(request: Request, call_next):
    if not _health_path(request) and SHADOW_API_TOKEN.strip():
        try:
            _verify_token(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
    response = await call_next(request)
    return response


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.get("/api/health")
async def health() -> dict[str, Any]:
    try:
        exists = table_exists()
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "generated_at": now_iso(),
        }
    return {
        "ok": True,
        "table_exists": exists,
        "table": f"{DB_NAME}.{DB_TABLE}",
        "frozen_window_id": FROZEN_WINDOW_ID,
        "base_window_id": BASE_WINDOW_ID,
        "gate_id": GATE_ID,
        "deployment_level": DEPLOYMENT_LEVEL,
        "champion_ready": CHAMPION_READY,
    }


@app.get("/api/frozen-windows")
async def api_frozen_windows() -> dict[str, Any]:
    return {
        "current_frozen_window_id": FROZEN_WINDOW_ID,
        "frozen_windows": FROZEN_WINDOWS,
    }


@app.get("/api/state")
async def state() -> dict[str, Any]:
    if _STATE_SNAPSHOT is not None:
        return _STATE_SNAPSHOT
    try:
        return latest_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/replay")
async def replay() -> dict[str, Any]:
    try:
        if not table_exists():
            return {
                "status": "missing_table",
                "message": f"DB table {DB_NAME}.{DB_TABLE} does not exist.",
                "frozen_window_id": FROZEN_WINDOW_ID,
                "gate_id": GATE_ID,
            }
        counts_desc = cached_issue_counts(120)
        issue_counter = Counter(
            int(row["issue_count"])
            for row in counts_desc
            if int(row["issue_count"]) > 0
        )
        inferred_expected = (
            issue_counter.most_common(1)[0][0]
            if issue_counter
            else EXPECTED_ISSUES_PER_DAY
        )
        expected_count = EXPECTED_ISSUES_PER_DAY or inferred_expected
        replay_result = cached_account_replay(expected_count)
        totals = replay_result.get("totals", {})
        totals["bankroll_constrained"] = True
        totals["frozen_window_id"] = FROZEN_WINDOW_ID
        totals["gate_id"] = GATE_ID
        totals["settlement"] = SETTLEMENT_MODE
        return {
            "status": "ok",
            "frozen_window_id": FROZEN_WINDOW_ID,
            "gate_id": GATE_ID,
            "settlement": SETTLEMENT_MODE,
            "bankroll_constrained": True,
            "skipped_bets_due_to_bankroll": totals.get(
                "skipped_bets_due_to_bankroll", 0
            ),
            **replay_result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/shadow-log")
async def shadow_log(limit: int = 100) -> dict[str, Any]:
    return {"rows": read_shadow_log(limit)}


@app.post("/api/shadow-log")
async def append_shadow_log(payload: ShadowLogPayload) -> dict[str, Any]:
    ensure_shadow_log()
    with SHADOW_LOG_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                now_iso(),
                payload.date,
                payload.recommended_mode,
                payload.active_windows,
                payload.would_execute_bets_count,
                payload.executed_bets,
                payload.account_daily_ledger_shadow,
                payload.account_daily_real_shadow,
                payload.account_daily_bonus_shadow,
                int(payload.data_quality_ok),
                payload.gate_reason,
                payload.notes,
            ]
        )
    return {"ok": True, "rows": read_shadow_log(20)}


@app.get("/api/data-quality")
async def api_data_quality() -> dict[str, Any]:
    return get_data_quality_summary()


@app.get("/api/leakage-check")
async def api_leakage_check() -> dict[str, Any]:
    return leakage_check()


@app.get("/api/shadow/status")
async def api_shadow_status() -> dict[str, Any]:
    return shadow_status()


@app.post("/api/shadow/settle-latest-complete-day")
async def api_shadow_settle() -> dict[str, Any]:
    return settle_latest_complete_day()


@app.get("/api/jsft-bet-log")
async def api_jsft_bet_log(page: int = 1, page_size: int = 60) -> dict[str, Any]:
    page = max(1, int(page))
    page_size = max(10, min(200, int(page_size)))
    offset = (page - 1) * page_size
    try:
        total_rows = query("SELECT COUNT(*) AS cnt FROM jsft_bet_log")
        total = int(total_rows[0]["cnt"]) if total_rows else 0
        rows = query(
            """
            SELECT
                id, draw_date, pre_draw_issue, slot_1based,
                odds_display, stake, total_cost, hit_count,
                outcome_label, pnl, status,
                DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
            FROM jsft_bet_log
            ORDER BY draw_date DESC, slot_1based DESC
            LIMIT %s OFFSET %s
            """,
            (page_size, offset),
        )
        return {
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total else 1,
        }
    except Exception:
        return {"rows": [], "page": 1, "page_size": page_size, "total": 0, "total_pages": 1}


@app.get("/api/jssc-bet-log")
async def api_jssc_bet_log(page: int = 1, page_size: int = 40) -> dict[str, Any]:
    page = max(1, int(page))
    page_size = max(10, min(200, int(page_size)))
    offset = (page - 1) * page_size
    try:
        total_row = query("SELECT COUNT(*) AS cnt FROM pk10_bet_log WHERE draw_date >= '2026-04-01'")
        total = int(total_row[0]["cnt"]) if total_row else 0
        rows = query(
            """
            SELECT
                b.id,
                DATE_FORMAT(b.draw_date, '%%Y-%%m-%%d') AS draw_date,
                b.pre_draw_issue,
                b.slot_1based,
                b.line_name,
                b.status,
                b.selection_json,
                b.odds_display,
                b.stake,
                b.multiplier_value,
                b.total_cost,
                b.hit_count,
                b.outcome_label,
                b.pnl,
                b.meta_json,
                DATE_FORMAT(h.pre_draw_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS pre_draw_time,
                h.pre_draw_code
            FROM pk10_bet_log b
            LEFT JOIN pks_history h ON h.pre_draw_issue = b.pre_draw_issue
            WHERE b.draw_date >= '2026-04-01'
            ORDER BY b.draw_date DESC, b.pre_draw_issue DESC, b.id DESC
            LIMIT %s OFFSET %s
            """,
            (page_size, offset),
        )
        for row in rows:
            if isinstance(row.get("selection_json"), str):
                try:
                    row["selection_json"] = json.loads(row["selection_json"])
                except Exception:
                    pass
            if isinstance(row.get("meta_json"), str):
                try:
                    row["meta_json"] = json.loads(row["meta_json"])
                except Exception:
                    pass
            meta = row.get("meta_json") or {}
            row["broadcast_state"] = meta.get("broadcast_state", "")
            row["broadcast_time"] = meta.get("broadcast_time")
        return {
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total else 1,
        }
    except Exception:
        return {"rows": [], "page": 1, "page_size": page_size, "total": 0, "total_pages": 1}


@app.get("/api/jssc-live-state")
async def api_jssc_live_state() -> dict[str, Any]:
    try:
        rows = query(
            "SELECT state_json FROM pk10_runtime_state WHERE state_key = 'dashboard' LIMIT 1"
        )
        if rows and rows[0].get("state_json"):
            raw = rows[0]["state_json"]
            if isinstance(raw, str):
                return json.loads(raw)
            return raw
    except Exception:
        pass
    return {}


@app.get("/api/jssc-broadcasts")
async def api_jssc_broadcasts(limit: int = 40) -> dict[str, Any]:
    try:
        rows = query(
            """
            SELECT
                DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS draw_date,
                pre_draw_issue,
                draw_issue,
                line_name,
                actionable,
                payload_json,
                DATE_FORMAT(server_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS server_time
            FROM pk10_broadcast_log
            ORDER BY id DESC
            LIMIT %s
            """,
            (int(limit),),
        )
        for row in rows:
            if isinstance(row.get("payload_json"), str):
                try:
                    row["payload_json"] = json.loads(row["payload_json"])
                except Exception:
                    pass
        return {"rows": rows}
    except Exception:
        return {"rows": []}


@app.get("/api/jssc-daily-curve")
async def api_jssc_daily_curve() -> dict[str, Any]:
    try:
        rows = query(
            """
            SELECT
                DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS date,
                COALESCE(total_real_pnl, 0) AS daily_pnl,
                COALESCE(settled_bankroll, 0) AS bankroll
            FROM pk10_daily_equity
            WHERE draw_date >= '2026-04-01'
            ORDER BY draw_date
            """
        )
    except Exception:
        return {"rows": [], "start_bankroll": 1000.0, "status": "unavailable"}
    running = 1000.0
    out: list[dict[str, Any]] = []
    for row in rows:
        running += float(row["daily_pnl"] or 0)
        out.append(
            {
                "date": str(row["date"]),
                "daily_pnl": round(float(row["daily_pnl"] or 0), 2),
                "bankroll": round(float(row["bankroll"] or running), 2),
            }
        )
    return {"rows": out, "start_bankroll": 1000.0}


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>PK10 综合推演</title>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Noto+Sans+SC:wght@400;500;700;900&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f6efe3; --paper: rgba(255,250,241,0.78); --ink: #1f1611;
      --muted: rgba(31,22,17,0.62); --line: rgba(31,22,17,0.12);
      --accent: #cf4f24; --accent-soft: rgba(207,79,36,0.14);
      --success: #147357; --danger: #a62822;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; color: var(--ink);
      background: radial-gradient(circle at 0% 0%, rgba(207,79,36,0.08), transparent 32%),
                  radial-gradient(circle at 100% 100%, rgba(20,115,87,0.08), transparent 28%),
                  linear-gradient(180deg, #f9f4eb 0%, #f2e6d2 100%);
      font-family: 'Noto Sans SC', sans-serif;
    }
    .shell { max-width: 1480px; margin: 0 auto; padding: 24px; }
    header {
      display: flex; justify-content: space-between; align-items: flex-end;
      padding-bottom: 18px; border-bottom: 1px solid var(--line); margin-bottom: 20px;
    }
    h1 { margin: 0; font-family: 'Bebas Neue', cursive; font-size: 52px; letter-spacing: 0.04em; line-height: 1; }
    .sub { color: var(--muted); font-size: 14px; margin-top: 6px; }
    .badge {
      display: inline-flex; align-items: center; min-height: 32px;
      padding: 6px 12px; border: 1px solid var(--line);
      background: var(--paper); font-weight: 800; font-size: 13px;
    }
    .badge.ok { color: var(--success); }
    .badge.warn { color: var(--accent); }
    .badge.bad { color: var(--danger); }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
    section {
      border: 1px solid var(--line); background: var(--paper); padding: 18px;
      border-radius: 4px;
    }
    h2 { margin: 0 0 14px; font-size: 18px; border-bottom: 1px solid var(--line); padding-bottom: 10px; }
    .cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
    .metric { background: var(--bg); padding: 10px 12px; min-height: 60px; border-radius: 2px; }
    .metric span { display: block; color: var(--muted); font-size: 11px; font-weight: 700; }
    .metric strong { display: block; margin-top: 6px; font-size: 19px; }
    .metric.good strong { color: var(--success); }
    .metric.bad strong { color: var(--danger); }
    .metric.warn strong { color: var(--accent); }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { padding: 7px 6px; border-bottom: 1px solid var(--line); text-align: left; }
    th { color: var(--muted); font-size: 11px; position: sticky; top: 0; background: var(--paper); }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .pos { color: var(--success); font-weight: 700; }
    .neg { color: var(--danger); font-weight: 700; }
    .table-wrap { overflow: auto; max-height: 420px; }
    .curve-shell { margin-top: 12px; }
    svg.curve { width: 100%; height: 200px; }
    .curve-legend { display: flex; gap: 16px; font-size: 12px; margin-bottom: 6px; }
    .legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
    .status-bar { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; margin-bottom: 18px; }
    .status-chip {
      border: 1px solid var(--line); background: var(--paper); padding: 8px 10px;
      font-size: 12px; border-radius: 2px;
    }
    .status-chip b { display: block; font-size: 16px; margin-top: 2px; }
    .full-width { grid-column: 1/-1; }
    @media (max-width: 960px) {
      .grid2 { grid-template-columns: 1fr; }
      .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .status-bar { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .shell { padding: 12px; }
      h1 { font-size: 32px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>PK10 综合推演</h1>
        <div class="sub" id="subtitle">JSFT Shadow + JSSC Live · 日级对比</div>
      </div>
      <div id="status" class="badge warn">加载中</div>
    </header>

    <div class="status-bar" id="statusBar"></div>

    <div class="grid2">
      <section>
        <h2>JSFT 影子推演 <span style="font-weight:400;font-size:13px;color:var(--muted)">sum12_cap15 · g13_26_pos · daily85</span></h2>
        <div class="cards" id="jsftCards"></div>
        <div class="table-wrap" id="jsftTable" style="margin-top:14px"></div>
        <details style="margin-top:12px">
          <summary style="cursor:pointer;font-size:13px;color:var(--muted)">投注明细日志（已落库 jsft_bet_log）</summary>
          <div class="table-wrap" id="jsftBetLog" style="margin-top:8px;max-height:300px"></div>
        </details>
      </section>
      <section>
        <h2>JSSC 实盘 <span style="font-weight:400;font-size:13px;color:var(--muted)">face+sum+exact · 日级结算</span></h2>
        <div id="jsscLines" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px"></div>
        <div class="cards" id="jsscCards"></div>
        <div class="table-wrap" id="jsscTable" style="margin-top:14px"></div>
      </section>
    </div>

    <section style="margin-top:18px" class="full-width">
      <h2>JSSC 投注历史</h2>
      <div class="table-wrap" id="jsscBets" style="max-height:480px"></div>
    </section>

    <section style="margin-top:18px" class="full-width">
      <h2>JSSC 播报历史</h2>
      <div class="table-wrap" id="broadcasts" style="max-height:360px"></div>
    </section>

    <section style="margin-top:18px" class="full-width">
      <h2>资金曲线对比</h2>
      <div class="curve-legend">
        <span><span class="legend-dot" style="background:var(--accent)"></span>JSFT</span>
        <span><span class="legend-dot" style="background:var(--ink)"></span>JSSC</span>
      </div>
      <div id="curve"></div>
    </section>
  </main>

  <script>
    const statusEl = document.getElementById('status')
    const subtitleEl = document.getElementById('subtitle')
    const statusBarEl = document.getElementById('statusBar')
    const jsftCardsEl = document.getElementById('jsftCards')
    const jsftTableEl = document.getElementById('jsftTable')
    const jsscCardsEl = document.getElementById('jsscCards')
    const jsscTableEl = document.getElementById('jsscTable')
    const curveEl = document.getElementById('curve')

    const fmt = v => Number(v ?? 0).toFixed(2)
    const signed = v => { const n = Number(v ?? 0); return (n >= 0 ? '+' : '') + n.toFixed(2) }
    const cls = v => Number(v ?? 0) >= 0 ? 'pos' : 'neg'
    const card = (label, value, tone) => `<div class="metric ${tone||''}"><span>${label}</span><strong>${value ?? '—'}</strong></div>`

    function renderCombined(jsft, jssc, jsscLive, bcast, betLog) {
      const jsftOk = jsft && jsft.status === 'ok'
      const jsscOk = jssc && jssc.rows && jssc.rows.length > 0

      if (jsftOk || jsscOk) {
        statusEl.className = 'badge ok'
        statusEl.textContent = '就绪'
        subtitleEl.textContent = 'JSFT Shadow + JSSC Live · 日级对比'
      } else {
        statusEl.className = 'badge warn'
        statusEl.textContent = '等待数据'
      }

      // Status bar
      const tgt = jsftOk ? (jsft.target || {}) : {}
      const gate = jsftOk ? (jsft.core_window?.gate_state || {}) : {}
      const ss = jsftOk ? (jsft.live_shadow_status || {}) : {}
      statusBarEl.innerHTML = [
        `<div class="status-chip"><span>JSFT 窗口</span><b>${gate.active ? '开窗' : '空仓'}</b></div>`,
        `<div class="status-chip"><span>前13日</span><b>${signed(gate.prior13_real||0)}</b></div>`,
        `<div class="status-chip"><span>最新完整日</span><b>${jsftOk ? (jsft.latest_complete_date||'—') : '—'}</b></div>`,
        `<div class="status-chip"><span>Shadow 累计日</span><b>${ss.live_shadow_days||0}</b></div>`,
        `<div class="status-chip"><span>Shadow 13日盈</span><b>${signed(ss.live13_real||0)}</b></div>`,
        `<div class="status-chip"><span>部署级别</span><b>${jsftOk ? (jsft.deployment_level === 'core_shadow' ? '核心影子' : jsft.deployment_level) : '—'}</b></div>`,
      ].join('')

      // JSFT cards
      if (jsftOk) {
        const totals = (jsft.account || {}).totals || {}
        const untotals = ((jsft.account || {}).unconstrained_shadow_result || {}).totals || {}
        const dq = jsft.data_quality_summary || {}
        jsftCardsEl.innerHTML = [
          card('起始积分', fmt(totals.bankroll_start)),
          card('当前积分', fmt(totals.bankroll_current), Number(totals.total_real) >= 0 ? 'good' : 'bad'),
          card('累计盈亏', signed(totals.total_real), Number(totals.total_real) >= 0 ? 'good' : 'bad'),
          card('最大回撤', fmt(totals.max_drawdown), 'bad'),
          card('总下注', totals.total_bets),
          card('命中率', ((totals.hit_rate||0)*100).toFixed(1)+'%'),
          card('异常日数', dq.anomaly_date_count||0, (dq.anomaly_date_count||0) > 0 ? 'warn' : ''),
          card('资金限制', totals.skipped_bets_due_to_bankroll||0, (totals.skipped_bets_due_to_bankroll||0) > 0 ? 'warn' : ''),
        ].join('')

        const daily = (jsft.account || {}).daily || []
        // compute running ledger for each day
        let runningLedger = Number(jsft.account?.totals?.bankroll_start || 1000)
        const ledgerMap = {}
        daily.forEach(r => { runningLedger += Number(r.ledger || 0); ledgerMap[r.date] = runningLedger })
        jsftTableEl.innerHTML = `
          <table>
            <thead><tr><th>日期</th><th>窗</th><th class="num">下注</th><th class="num">命中</th><th class="num">账面</th><th class="num">真实</th><th class="num">账面日末</th><th class="num">日末</th></tr></thead>
            <tbody>${daily.slice().reverse().map(r => `
              <tr>
                <td>${r.date}</td><td>${r.window_active?'开':'空'}</td>
                <td class="num">${r.bets}</td><td class="num">${r.hits}</td>
                <td class="num ${cls(r.ledger)}">${signed(r.ledger)}</td>
                <td class="num ${cls(r.real)}">${signed(r.real)}</td>
                <td class="num ${cls(ledgerMap[r.date] - 1000)}">${fmt(ledgerMap[r.date])}</td>
                <td class="num">${fmt(r.bankroll_end)}</td>
              </tr>
              ${r.bets > 0 && r.tickets && r.tickets.length ? `
              <tr style="background:var(--bg)">
                <td colspan="8" style="padding:4px 8px;font-size:11px">
                  ${r.tickets.map(t => `<span style="display:inline-block;margin:2px 6px 2px 0;white-space:nowrap">
                    #${t.slot_1based} <span class="num">期${t.pre_draw_issue}</span>
                    ${t.hit ? '<span class="pos">✓命中</span>' : '<span class="neg">✗</span>'}
                  </span>`).join('')}
                </td>
              </tr>` : ''}
            `).join('')}</tbody>
          </table>`
      } else {
        jsftCardsEl.innerHTML = '<div class="metric full-width"><span>JSFT</span><strong>数据未就绪</strong></div>'
        jsftTableEl.innerHTML = ''
      }

      // JSSC cards
      if (jsscOk) {
        const rows = jssc.rows || []
        const totalPnl = rows.reduce((s, r) => s + (Number(r.daily_pnl)||0), 0)
        const lastRow = rows[rows.length - 1] || {}
        const pnlValues = rows.map(r => Number(r.daily_pnl)||0)
        let peak = 0, maxDd = 0, running = 0
        for (const v of pnlValues) { running += v; peak = Math.max(peak, running); maxDd = Math.min(maxDd, running - peak) }
        const upDays = pnlValues.filter(v => v > 0).length
        const totalBets = rows.length
        jsscCardsEl.innerHTML = [
          card('起始积分', '1000.00'),
          card('当前积分', fmt((lastRow.bankroll||1000)), totalPnl >= 0 ? 'good' : 'bad'),
          card('累计盈亏', signed(totalPnl), totalPnl >= 0 ? 'good' : 'bad'),
          card('最大回撤', fmt(Math.abs(maxDd)), 'bad'),
          card('记录天数', totalBets),
          card('盈利天数', upDays+'/'+totalBets),
          card('日均盈亏', signed(totalPnl / Math.max(totalBets, 1))),
          card('结算方式', '实盘日结'),
        ].join('')

        jsscTableEl.innerHTML = `
          <table>
            <thead><tr><th>日期</th><th class="num">日盈亏</th><th class="num">日末积分</th></tr></thead>
            <tbody>${rows.slice().reverse().slice(0, 60).map(r => `
              <tr>
                <td>${r.date}</td>
                <td class="num ${cls(r.daily_pnl)}">${signed(r.daily_pnl)}</td>
                <td class="num">${fmt(r.bankroll)}</td>
              </tr>`).join('')}</tbody>
          </table>`
      } else {
        jsscCardsEl.innerHTML = '<div class="metric full-width"><span>JSSC</span><strong>数据未就绪</strong></div>'
        jsscTableEl.innerHTML = ''
      }

      // JSSC line panels (face/sum/exact)
      const jsscLines = document.getElementById('jsscLines')
      if (jsscLive && jsscLive.today_plan) {
        const plan = jsscLive.today_plan
        const lineCard = (name, label, state) => {
          if (!state) return ''
          const pnl = Number(state.provisional_pnl || 0)
          const req = state.requested_slots || 0
          const fund = state.funded_slots || 0
          const exec = state.executed_slots || 0
          const pend = state.pending_slots || 0
          const mult = name === 'exact' ? '固定10' : (state.multiplier_value || 0) + 'x'
          const statusText = state.message || (state.status === 'active' ? '开窗' : state.status === 'cash' ? '空仓' : state.status === 'idle' ? '空闲' : (state.status || ''))
          return `<div class="metric"><span>${label}</span>
            <strong style="font-size:14px;color:${pnl>=0?'var(--success)':'var(--danger)'}">${statusText}</strong>
            <div style="font-size:11px;color:var(--muted);margin-top:4px">
              浮动盈亏 ${signed(pnl)} · 档位 ${mult}<br/>
              计划/可投 ${req}/${fund} · 已执行/待 ${exec}/${pend}
            </div></div>`
        }
        jsscLines.innerHTML = [
          lineCard('face', '双面', plan.face),
          lineCard('sum', '冠亚和', plan.sum),
          lineCard('exact', '定位胆', plan.exact),
        ].filter(Boolean).join('')
      } else {
        jsscLines.innerHTML = ''
      }

      // Broadcast history
      const bcastEl = document.getElementById('broadcasts')
      if (bcast && bcast.rows && bcast.rows.length > 0) {
        bcastEl.innerHTML = `
          <table>
            <thead><tr><th>时间</th><th>日期</th><th>玩法</th><th>触发期</th><th>目标期</th><th>内容</th></tr></thead>
            <tbody>${bcast.rows.map(r => {
              const p = r.payload_json || {}
              const sel = p.selection || {}
              let detail = ''
              if (r.line_name === 'sum' && sel.sum_value != null) detail = '和值 ' + sel.sum_value
              else if (r.line_name === 'face') detail = sel.source || '双面'
              else if (r.line_name === 'exact') detail = '位' + (sel.position_1based||'') + '·号' + (sel.number||'')
              return `<tr>
                <td>${r.server_time||''}</td><td>${r.draw_date||''}</td>
                <td>${r.line_name==='face'?'双面':r.line_name==='sum'?'冠亚和':r.line_name==='exact'?'定位胆':r.line_name}</td>
                <td class="num">${r.pre_draw_issue||''}</td><td class="num">${r.draw_issue||''}</td>
                <td>${detail}${r.actionable?' · 可投':''}</td>
              </tr>`
            }).join('')}</tbody>
          </table>`
      } else {
        bcastEl.innerHTML = '<div class="metric" style="grid-column:1/-1"><span>播报</span><strong>暂无数据</strong></div>'
      }

      // Bet history
      const betEl = document.getElementById('jsscBets')
      if (betLog && betLog.rows && betLog.rows.length > 0) {
        const lineLabel = n => n === 'face' ? '双面' : n === 'sum' ? '冠亚和' : n === 'exact' ? '定位胆' : n
        const statusLabel = s => s === 'settled' ? '已结算' : s === 'executed' ? '已执行' : s === 'pending' ? '待开奖' : s
        const bcastLabel = s => s === 'broadcasted' ? '已播报' : s === 'pending_future' ? '待执行' : s || '—'
        betEl.innerHTML = `
          <table>
            <thead><tr>
              <th>日期</th><th class="num">期号</th><th>期位</th><th>玩法</th><th>状态</th><th>播报</th>
              <th>开奖时间</th><th>号码</th><th>赔率</th><th class="num">金额</th><th class="num">盈亏</th>
            </tr></thead>
            <tbody>${betLog.rows.map(r => {
              const sel = r.selection_json || {}
              let detail = ''
              if (r.line_name === 'sum' && sel.sum_value != null) detail = '和值 ' + sel.sum_value
              else if (r.line_name === 'exact') detail = '位' + (sel.position_1based||'') + '·号' + (sel.number||'')
              else if (r.line_name === 'face') detail = sel.source || ''
              return `<tr>
                <td>${r.draw_date||''}</td>
                <td class="num">${r.pre_draw_issue||''}</td>
                <td class="num">#${r.slot_1based||''}</td>
                <td>${lineLabel(r.line_name)}${detail?' · '+detail:''}</td>
                <td>${statusLabel(r.status)}</td>
                <td>${bcastLabel(r.broadcast_state)}</td>
                <td>${r.pre_draw_time||'—'}</td>
                <td>${r.pre_draw_code||'—'}</td>
                <td>${r.odds_display||''}</td>
                <td class="num">${fmt(r.total_cost)}</td>
                <td class="num ${cls(r.pnl)}">${r.pnl != null ? signed(r.pnl) : '—'}</td>
              </tr>`
            }).join('')}</tbody>
          </table>`
      } else {
        betEl.innerHTML = '<div class="metric" style="grid-column:1/-1"><span>投注</span><strong>暂无数据</strong></div>'
      }

      // Combined curve
      if (jsftOk || jsscOk) {
        const jsftDaily = jsftOk ? ((jsft.account || {}).daily || []) : []
        const jsscRows = jsscOk ? (jssc.rows || []) : []
        const allDates = new Set()
        jsftDaily.forEach(r => allDates.add(r.date))
        jsscRows.forEach(r => allDates.add(r.date))
        const sorted = [...allDates].sort().slice(-60)
        const jsftMap = {}; jsftDaily.forEach(r => { jsftMap[r.date] = Number(r.bankroll_end) || 0 })
        const jsscMap = {}; jsscRows.forEach(r => { jsscMap[r.date] = Number(r.bankroll) || 0 })

        const vals1 = sorted.map(d => jsftMap[d] || null)
        const vals2 = sorted.map(d => jsscMap[d] || null)
        const allVals = [...vals1, ...vals2].filter(v => v != null)
        const minV = Math.min(...allVals, 900), maxV = Math.max(...allVals, 1100)
        const span = Math.max(1, maxV - minV)
        const W = 920, H = 200, P = 30

        const x = i => P + (W - 2*P) * i / Math.max(1, sorted.length - 1)
        const y = v => H - P - (H - 2*P) * (v - minV) / span

        const path1 = sorted.map((d, i) => {
          const v = vals1[i]; if (v == null) return ''
          return `${i===0 || vals1[i-1]==null ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`
        }).filter(s => s).join(' ')
        const path2 = sorted.map((d, i) => {
          const v = vals2[i]; if (v == null) return ''
          return `${i===0 || vals2[i-1]==null ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`
        }).filter(s => s).join(' ')

        const yTicks = [minV, minV + span*0.25, minV + span*0.5, minV + span*0.75, maxV]
        curveEl.innerHTML = `
          <svg viewBox="0 0 ${W} ${H}" class="curve">
            <rect x="0" y="0" width="${W}" height="${H}" fill="var(--paper)" rx="8" />
            ${yTicks.map(v => `<line x1="${P}" x2="${W-P}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--line)" stroke-dasharray="4 4" />`).join('')}
            ${yTicks.map(v => `<text x="${P-4}" y="${y(v).toFixed(1)}" text-anchor="end" font-size="10" fill="var(--muted)" dominant-baseline="middle">${fmt(v)}</text>`).join('')}
            ${path1 ? `<path d="${path1}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" />` : ''}
            ${path2 ? `<path d="${path2}" fill="none" stroke="var(--ink)" stroke-width="2.5" stroke-linecap="round" />` : ''}
          </svg>
          <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted);padding:4px 30px">
            <span>${sorted[0]||''}</span><span>${sorted[Math.floor(sorted.length/2)]||''}</span><span>${sorted[sorted.length-1]||''}</span>
          </div>`
      }
    }

    async function loadAll() {
      try {
        const [jsftRes, jsscRes, jsscLiveRes, bcastRes, betLogRes] = await Promise.all([
          fetch('/api/state', { cache: 'no-store' }).then(r => r.json()),
          fetch('/api/jssc-daily-curve', { cache: 'no-store' }).then(r => r.json()),
          fetch('/api/jssc-live-state', { cache: 'no-store' }).then(r => r.json()),
          fetch('/api/jssc-broadcasts?limit=40', { cache: 'no-store' }).then(r => r.json()),
          fetch('/api/jssc-bet-log?page_size=60', { cache: 'no-store' }).then(r => r.json()),
        ])
        renderCombined(jsftRes, jsscRes, jsscLiveRes, bcastRes, betLogRes)
        loadBetLog()
      } catch (e) {
        statusEl.className = 'badge bad'
        statusEl.textContent = '错误'
        console.error(e)
      }
    }

    async function loadBetLog() {
      try {
        const data = await fetch('/api/jsft-bet-log?page_size=200').then(r => r.json())
        const el = document.getElementById('jsftBetLog')
        if (!el || !data.rows || !data.rows.length) return
        el.innerHTML = `
          <table>
            <thead><tr><th>日期</th><th class="num">期号</th><th class="num">slot</th><th class="num">金额</th><th>结果</th><th class="num">盈亏</th></tr></thead>
            <tbody>${data.rows.map(r => `
              <tr>
                <td>${r.draw_date}</td>
                <td class="num">${r.pre_draw_issue||''}</td>
                <td class="num">#${r.slot_1based}</td>
                <td class="num">${fmt(r.total_cost)}</td>
                <td>${r.outcome_label==='hit'?'<span class="pos">命中</span>':'未中'}</td>
                <td class="num ${cls(r.pnl)}">${signed(r.pnl)}</td>
              </tr>`).join('')}</tbody>
          </table>`
      } catch(e) { console.error(e) }
    }

    loadAll()
    setInterval(loadAll, 60000)
  </script>
</body>
</html>
"""
