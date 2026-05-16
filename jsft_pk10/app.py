from __future__ import annotations

import csv
import json
import os
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


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
TIMEZONE = ZoneInfo(os.getenv("JSFT_TIMEZONE", "Asia/Shanghai"))


app = FastAPI(title=APP_NAME)
_ACCOUNT_CACHE: dict[str, Any] = {"key": None, "expires_at": 0.0, "value": None}


class ShadowLogPayload(BaseModel):
    date: str
    recommended_mode: str = "core"
    active_windows: str = "sum12_cap15"
    would_execute_bets_count: int = CORE_CAP
    account_daily_ledger_shadow: float
    account_daily_real_shadow: float
    account_daily_bonus_shadow: float
    data_quality_ok: bool = True
    notes: str = ""


def db_conn():
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


def replay_selected_rows(expected_count: int) -> list[dict[str, Any]]:
    slots = uniform_slots(expected_count, CORE_CAP)
    placeholders = ",".join(["%s"] * len(slots))
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
            HAVING issue_count >= %s
        ) day_index ON day_index.draw_date = h.draw_date
        WHERE CAST(h.pre_draw_issue - day_index.min_issue + 1 AS SIGNED) IN ({placeholders})
        ORDER BY h.draw_date, slot_1based
    """
    return query(sql, tuple([REPLAY_HISTORY_START, expected_count, *slots]))


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


def daily_gate_state(prior_base_days: list[dict[str, Any]], gate_name: str | None = None) -> dict[str, Any]:
    gate = (gate_name or DAILY_GATE or "always").strip()
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
        active = len(vals) == 7 and sum(vals) > 0.0 and sum(1 for value in vals if value > 0.0) >= 4
        reason = f"prior7_real={sum(vals) if vals else 0.0:.2f}, positive_days={sum(1 for value in vals if value > 0.0)}"
    elif gate == "g10_avg_pos6":
        required_days = 10
        vals = values[-10:] if len(values) >= 10 else []
        active = len(vals) == 10 and sum(vals) > 0.0 and sum(1 for value in vals if value > 0.0) >= 6
        reason = f"prior10_real={sum(vals) if vals else 0.0:.2f}, positive_days={sum(1 for value in vals if value > 0.0)}"
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
        reason = f"unknown gate {gate}; fallback g13_26_pos with prior13_real={sum13:.2f}, prior26_real={sum26:.2f}"
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


def account_replay(expected_count: int) -> dict[str, Any]:
    selected = replay_selected_rows(expected_count)
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
    for draw_date in sorted(by_day):
        rows = sorted(by_day[draw_date], key=lambda item: int(item["slot_1based"]))
        base_day = summarize_base_day(draw_date, rows)
        gate_state = daily_gate_state(base_days)
        base_days.append(base_day)
        if draw_date < REPLAY_START_DATE:
            continue
        latest_gate_state = gate_state
        affordable_bets = max(0, int(bankroll // BASE_STAKE)) if BASE_STAKE > 0 and bankroll > 0 else 0
        funded_rows = rows[: min(len(rows), affordable_bets)] if gate_state["active"] else []
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
        daily_rows.append(
            {
                "date": draw_date,
                "bankroll_start": round(before, 4),
                "bankroll_end": round(bankroll, 4),
                "window_active": bool(gate_state["active"]),
                "gate_reason": gate_state["reason"],
                "prior13_real": gate_state["prior13_real"],
                "prior26_real": gate_state["prior26_real"],
                "requested_bets": int(len(rows) if gate_state["active"] else 0),
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
                "tickets": tickets,
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
        "hit_rate": round(sum(row["hits"] for row in daily_rows) / max(sum(row["bets"] for row in daily_rows), 1), 6),
        "max_drawdown": round(max_drawdown, 4),
        "stake": BASE_STAKE,
        "settlement": "daily_85",
        "window": "sum12_cap15",
        "sum_value": CORE_SUM_VALUE,
        "daily_gate": DAILY_GATE,
        "latest_gate_active": bool(latest_gate_state["active"]) if latest_gate_state else False,
        "next_gate_active": bool(next_gate_state["active"]),
    }
    return {
        "totals": totals,
        "daily": daily_rows,
        "tickets": ticket_rows[-120:],
        "next_gate_state": next_gate_state,
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
    )
    now = time.monotonic()
    if _ACCOUNT_CACHE["key"] == key and _ACCOUNT_CACHE["value"] is not None and now < float(_ACCOUNT_CACHE["expires_at"]):
        return _ACCOUNT_CACHE["value"]
    value = account_replay(expected_count)
    _ACCOUNT_CACHE.update({"key": key, "value": value, "expires_at": now + ACCOUNT_CACHE_SECONDS})
    return value


def issue_counts() -> list[dict[str, Any]]:
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
        LIMIT 120
        """
    )


def latest_summary() -> dict[str, Any]:
    if not table_exists():
        return {
            "table_exists": False,
            "status": "missing_table",
            "message": f"DB table {DB_NAME}.{DB_TABLE} does not exist.",
        }
    counts_desc = issue_counts()
    if not counts_desc:
        return {
            "table_exists": True,
            "status": "empty_table",
            "message": f"DB table {DB_NAME}.{DB_TABLE} exists but has no rows.",
        }
    counts = list(reversed(counts_desc))
    issue_counter = Counter(int(row["issue_count"]) for row in counts if int(row["issue_count"]) > 0)
    inferred_expected = issue_counter.most_common(1)[0][0] if issue_counter else EXPECTED_ISSUES_PER_DAY
    expected_count = EXPECTED_ISSUES_PER_DAY or inferred_expected
    for row in counts:
        row["is_full_day"] = int(row["issue_count"]) >= expected_count
    full_rows = [row for row in counts if row["is_full_day"]]
    latest_seen = counts[-1]
    latest_complete = full_rows[-1] if full_rows else None
    latest_complete_date = latest_complete["draw_date"] if latest_complete else None
    target = target_day(latest_seen, latest_complete_date, expected_count)
    account = cached_account_replay(expected_count)
    gate_state = account.get("next_gate_state", {})
    slots = build_decision_slots(target, latest_seen, expected_count, gate_state)
    return {
        "table_exists": True,
        "status": "ok",
        "db": {
            "host": DB_HOST,
            "port": DB_PORT,
            "name": DB_NAME,
            "table": DB_TABLE,
        },
        "expected_issues_per_day": expected_count,
        "inferred_expected_issues_per_day": inferred_expected,
        "latest_seen": normalize_row(latest_seen),
        "latest_complete_date": latest_complete_date,
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
            "would_execute_bets_count": len([slot for slot in slots if slot["status"] in {"planned", "pending"} and target["actionable"]]),
        },
        "readiness": {
            "mode": "core_shadow",
            "champion_ready": False,
            "reason": "Forward shadow only. Champion requires 13 complete live-shadow days.",
        },
        "account": account,
        "generated_at": datetime.now(TIMEZONE).isoformat(timespec="seconds"),
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


def target_day(latest_seen: dict[str, Any], latest_complete_date: str | None, expected_count: int) -> dict[str, Any]:
    today = datetime.now(TIMEZONE).date().isoformat()
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
        target_date = (datetime.strptime(latest_complete_date, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
        actionable = target_date >= today
        target_kind = "next_after_latest_complete" if actionable else "stale_next_after_latest_complete"
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
    observed_count = int(latest_seen["issue_count"]) if target_is_latest_seen else 0
    min_issue = int(latest_seen["min_issue"]) if target_is_latest_seen and latest_seen.get("min_issue") is not None else None
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
                "window": "sum12_cap15",
                "status": status,
                "expected_issue": min_issue + slot - 1 if min_issue is not None else None,
            }
        )
    return rows


def ensure_shadow_log() -> None:
    if SHADOW_LOG_PATH.exists():
        return
    with SHADOW_LOG_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "created_at",
                "date",
                "recommended_mode",
                "active_windows",
                "would_execute_bets_count",
                "account_daily_ledger_shadow",
                "account_daily_real_shadow",
                "account_daily_bonus_shadow",
                "data_quality_ok",
                "notes",
            ]
        )


def read_shadow_log(limit: int = 100) -> list[dict[str, Any]]:
    ensure_shadow_log()
    with SHADOW_LOG_PATH.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-limit:]


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.get("/api/health")
async def health() -> dict[str, Any]:
    try:
        exists = table_exists()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "generated_at": datetime.now(TIMEZONE).isoformat(timespec="seconds")}
    return {"ok": True, "table_exists": exists, "table": f"{DB_NAME}.{DB_TABLE}"}


@app.get("/api/state")
async def state() -> dict[str, Any]:
    try:
        return latest_summary()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/replay")
async def replay() -> dict[str, Any]:
    try:
        if not table_exists():
            return {"status": "missing_table", "message": f"DB table {DB_NAME}.{DB_TABLE} does not exist."}
        counts_desc = issue_counts()
        issue_counter = Counter(int(row["issue_count"]) for row in counts_desc if int(row["issue_count"]) > 0)
        inferred_expected = issue_counter.most_common(1)[0][0] if issue_counter else EXPECTED_ISSUES_PER_DAY
        expected_count = EXPECTED_ISSUES_PER_DAY or inferred_expected
        return {"status": "ok", **cached_account_replay(expected_count)}
    except Exception as exc:  # noqa: BLE001
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
                datetime.now(TIMEZONE).isoformat(timespec="seconds"),
                payload.date,
                payload.recommended_mode,
                payload.active_windows,
                payload.would_execute_bets_count,
                payload.account_daily_ledger_shadow,
                payload.account_daily_real_shadow,
                payload.account_daily_bonus_shadow,
                int(payload.data_quality_ok),
                payload.notes,
            ]
        )
    return {"ok": True, "rows": read_shadow_log(20)}


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>JSFT 1000积分推演</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #ece7db;
      --paper: #fffdf6;
      --ink: #191916;
      --muted: #6c675d;
      --line: #ded6c7;
      --field: #f3eddf;
      --ok: #146a4d;
      --warn: #a6620b;
      --bad: #a42b25;
      --accent: #0d5e70;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    .shell { max-width: 1360px; margin: 0 auto; padding: 28px; }
    header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: end;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0; font-size: clamp(30px, 5vw, 64px); line-height: 0.95; letter-spacing: 0; }
    .sub { margin-top: 10px; color: var(--muted); font-size: 14px; }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      background: var(--paper);
      font-weight: 800;
      font-size: 13px;
    }
    .badge.ok { color: var(--ok); }
    .badge.warn { color: var(--warn); }
    .badge.bad { color: var(--bad); }
    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
      margin-top: 18px;
    }
    section {
      border: 1px solid var(--line);
      background: var(--paper);
      padding: 18px;
    }
    h2 { margin: 0 0 14px; font-size: 18px; }
    .cards {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .metric { background: var(--field); padding: 12px; min-height: 76px; }
    .metric span { display: block; color: var(--muted); font-size: 12px; font-weight: 700; }
    .metric strong { display: block; margin-top: 8px; font-size: 22px; }
    .metric.good strong { color: var(--ok); }
    .metric.bad strong { color: var(--bad); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; }
    th { color: var(--muted); font-size: 12px; }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .pos { color: var(--ok); font-weight: 800; }
    .neg { color: var(--bad); font-weight: 800; }
    .table-wrap { overflow: auto; max-height: 520px; }
    .slots {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
      gap: 8px;
    }
    .slot {
      border: 1px solid var(--line);
      background: #fbf7ed;
      padding: 10px;
      min-height: 70px;
    }
    .slot.pending, .slot.planned { border-color: rgba(14,95,111,.42); background: #edf7f7; }
    .slot.missed { color: #777; background: #eee8dd; }
    .slot.stale_missed, .slot.stale_unavailable { color: #82786b; background: #eee8dd; }
    .slot b { display: block; font-size: 18px; }
    .slot small { display: block; margin-top: 5px; color: var(--muted); }
    .curve { display: grid; gap: 8px; }
    .bar-row { display: grid; grid-template-columns: 88px 1fr 78px; gap: 10px; align-items: center; font-size: 12px; }
    .bar-track { height: 16px; background: var(--field); border: 1px solid var(--line); position: relative; overflow: hidden; }
    .bar { position: absolute; top: 0; bottom: 0; left: 50%; background: var(--ok); }
    .bar.neg { left: auto; right: 50%; background: var(--bad); }
    .error { border-color: rgba(161,44,35,.36); background: #fff5f1; color: var(--bad); }
    @media (max-width: 900px) {
      .grid2, header { grid-template-columns: 1fr; }
      .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .shell { padding: 16px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>JSFT 1000积分推演</h1>
        <div class="sub">core: 冠亚和 sum=12 / cap15基础曝光 / 日级gate开窗才下 / daily85真实账</div>
      </div>
      <div id="status" class="badge warn">loading</div>
    </header>
    <section style="margin-top:18px">
      <h2>账户总览</h2>
      <div class="cards" id="accountCards"></div>
    </section>
    <div class="grid2">
      <section>
        <h2>今日 / 下一日计划</h2>
        <div class="cards" id="planCards"></div>
      </section>
      <section>
        <h2>资金曲线</h2>
        <div id="curve" class="curve"></div>
      </section>
    </div>
    <section style="margin-top:18px">
      <h2>计划 slot</h2>
      <div id="slots" class="slots"></div>
    </section>
    <section style="margin-top:18px">
      <h2>每天真实情况</h2>
      <div id="daily" class="table-wrap"></div>
    </section>
    <div class="grid2">
      <section>
        <h2>最近数据日</h2>
        <div id="days"></div>
      </section>
      <section>
        <h2>最近票明细</h2>
        <div id="tickets" class="table-wrap"></div>
      </section>
    </div>
  </main>
  <script>
    const statusEl = document.querySelector('#status')
    const accountCardsEl = document.querySelector('#accountCards')
    const planCardsEl = document.querySelector('#planCards')
    const curveEl = document.querySelector('#curve')
    const slotsEl = document.querySelector('#slots')
    const dailyEl = document.querySelector('#daily')
    const daysEl = document.querySelector('#days')
    const ticketsEl = document.querySelector('#tickets')
    const fmt = (value) => Number(value ?? 0).toFixed(2)
    const signed = (value) => {
      const n = Number(value ?? 0)
      return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`
    }
    const cls = (value) => Number(value ?? 0) >= 0 ? 'pos' : 'neg'
    const metric = (label, value, tone = '') => `<div class="metric ${tone}"><span>${label}</span><strong>${value ?? '—'}</strong></div>`
    function badgeClass(state) {
      if (state?.status === 'ok') return 'ok'
      if (state?.table_exists === false) return 'bad'
      return 'warn'
    }
    function render(state) {
      statusEl.className = `badge ${badgeClass(state)}`
      statusEl.textContent = state.status === 'ok' ? 'DATA READY' : (state.status || 'NOT READY')
      if (state.status !== 'ok') {
        accountCardsEl.innerHTML = `<div class="metric error" style="grid-column:1/-1"><span>数据源</span><strong>${state.message || 'JSFT 数据未就绪'}</strong></div>`
        planCardsEl.innerHTML = ''
        curveEl.innerHTML = ''
        slotsEl.innerHTML = ''
        dailyEl.innerHTML = ''
        daysEl.innerHTML = ''
        ticketsEl.innerHTML = ''
        return
      }
      const target = state.target || {}
      const core = state.core_window || {}
      const account = state.account || {}
      const totals = account.totals || {}
      const daily = account.daily || []
      accountCardsEl.innerHTML = [
        metric('起始积分', fmt(totals.bankroll_start)),
        metric('当前积分', fmt(totals.bankroll_current), Number(totals.total_real) >= 0 ? 'good' : 'bad'),
        metric('累计真实盈亏', signed(totals.total_real), Number(totals.total_real) >= 0 ? 'good' : 'bad'),
        metric('最大回撤', fmt(totals.max_drawdown), 'bad'),
        metric('记录天数', totals.day_count),
        metric('开窗天数', `${totals.active_days}/${totals.day_count}`),
        metric('总下注', totals.total_bets),
        metric('命中率', `${((totals.hit_rate || 0) * 100).toFixed(2)}%`)
      ].join('')
      const gate = core.gate_state || {}
      planCardsEl.innerHTML = [
        metric('计划日期', target.date),
        metric('状态', target.actionable ? '可记录' : '数据过期'),
        metric('窗口', gate.active ? '开窗' : '空仓'),
        metric('今日下注数', core.would_execute_bets_count),
        metric('最新完整日', state.latest_complete_date),
        metric('日级gate', core.daily_gate),
        metric('前13日real', signed(gate.prior13_real || 0), Number(gate.prior13_real || 0) >= 0 ? 'good' : 'bad'),
        metric('前26日real', signed(gate.prior26_real || 0), Number(gate.prior26_real || 0) >= 0 ? 'good' : 'bad')
      ].join('')
      slotsEl.innerHTML = (core.decision_slots || []).length ? (core.decision_slots || []).map(slot => `
        <div class="slot ${slot.status}">
          <b>#${slot.slot}</b>
          <small>和值 ${slot.sum_value}</small>
          <small>${slot.status}${slot.expected_issue ? ' · issue ' + slot.expected_issue : ''}</small>
        </div>`).join('') : `<div class="metric" style="grid-column:1/-1"><span>今日窗口</span><strong>不开窗 / 空仓</strong><small>${gate.reason || ''}</small></div>`
      dailyEl.innerHTML = `
        <table>
          <thead><tr><th>日期</th><th>窗口</th><th class="num">下注</th><th class="num">命中</th><th class="num">账面</th><th class="num">真实</th><th class="num">结算差</th><th class="num">日末积分</th></tr></thead>
          <tbody>${daily.slice().reverse().map(row => `
            <tr>
              <td>${row.date}</td>
              <td>${row.window_active ? '开' : '空'}</td>
              <td class="num">${row.bets}</td>
              <td class="num">${row.hits}</td>
              <td class="num ${cls(row.ledger)}">${signed(row.ledger)}</td>
              <td class="num ${cls(row.real)}">${signed(row.real)}</td>
              <td class="num">${signed(row.bonus)}</td>
              <td class="num">${fmt(row.bankroll_end)}</td>
            </tr>`).join('')}</tbody>
        </table>`
      const last = daily.slice(-18)
      const maxAbs = Math.max(1, ...last.map(row => Math.abs(Number(row.real || 0))))
      curveEl.innerHTML = last.map(row => {
        const real = Number(row.real || 0)
        const width = Math.max(2, Math.abs(real) / maxAbs * 50)
        return `<div class="bar-row"><span>${row.date.slice(5)}</span><div class="bar-track"><div class="bar ${real < 0 ? 'neg' : ''}" style="width:${width}%"></div></div><span class="${cls(real)}">${signed(real)}</span></div>`
      }).join('')
      daysEl.innerHTML = `
        <table>
          <thead><tr><th>date</th><th>count</th><th>full</th><th>range</th></tr></thead>
          <tbody>${(state.recent_days || []).map(day => `
            <tr>
              <td>${day.draw_date}</td>
              <td>${day.issue_count}</td>
              <td>${day.is_full_day ? 'yes' : 'no'}</td>
              <td>${day.min_issue || ''} - ${day.max_issue || ''}</td>
            </tr>`).join('')}</tbody>
        </table>`
      ticketsEl.innerHTML = `
        <table>
          <thead><tr><th>时间</th><th>slot</th><th>期号</th><th>结果</th><th class="num">盈亏</th></tr></thead>
          <tbody>${(account.tickets || []).slice().reverse().slice(0, 60).map(row => `
            <tr>
              <td>${row.pre_draw_time}</td>
              <td>#${row.slot_1based}</td>
              <td>${row.pre_draw_issue}</td>
              <td>${row.sum_fs}${row.hit ? ' 命中' : ''}</td>
              <td class="num ${cls(row.ledger)}">${signed(row.ledger)}</td>
            </tr>`).join('')}</tbody>
        </table>`
    }
    async function load() {
      try {
        const response = await fetch('/api/state', { cache: 'no-store' })
        const state = await response.json()
        render(state)
      } catch (error) {
        statusEl.className = 'badge bad'
        statusEl.textContent = 'ERROR'
        accountCardsEl.innerHTML = `<div class="metric error" style="grid-column:1/-1"><span>错误</span><strong>${String(error)}</strong></div>`
      }
    }
    load()
    setInterval(load, 30000)
  </script>
</body>
</html>
"""
