from __future__ import annotations

import asyncio
import json
from math import ceil

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from . import db
from .runtime import runtime
from .settings import settings


app = FastAPI(title=settings.app_name)


@app.on_event("startup")
async def on_startup() -> None:
    await runtime.startup()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await runtime.shutdown()


@app.get("/api/health")
async def api_health() -> dict:
    snapshot = await runtime.get_snapshot()
    return {
        "status": "ok",
        "generated_at": snapshot.get("generated_at"),
        "pre_draw_issue": snapshot.get("market", {}).get("pre_draw_issue"),
    }


@app.get("/api/dashboard")
async def api_dashboard() -> dict:
    return await runtime.get_snapshot()


@app.get("/api/curve/daily")
async def api_curve_daily(start_date: str = settings.simulation_start_date) -> dict:
    snapshot = await runtime.get_snapshot()
    rows = snapshot.get("daily_curve", [])
    if start_date:
        rows = [row for row in rows if str(row.get("date", "")) >= start_date]
    return {"rows": rows, "start_date": start_date}


@app.get("/api/history/broadcasts")
async def api_history_broadcasts(page: int = 1, page_size: int = 40, issue: str = "") -> dict:
    page = max(1, int(page))
    page_size = max(10, min(200, int(page_size)))
    offset = (page - 1) * page_size
    issue = str(issue or "").strip()
    where_sql = ""
    params: list[object] = []
    if issue:
        if not issue.isdigit():
            return {
                "rows": [],
                "page": 1,
                "page_size": page_size,
                "total": 0,
                "total_pages": 1,
                "has_prev": False,
                "has_next": False,
                "issue": issue,
            }
        where_sql = "WHERE (pre_draw_issue = %s OR draw_issue = %s)"
        params.extend([int(issue), int(issue)])

    if where_sql:
        where_sql = f"{where_sql} AND draw_date >= %s"
    else:
        where_sql = "WHERE draw_date >= %s"
    params.append(settings.simulation_start_date)

    total_sql = f"SELECT COUNT(*) AS total FROM pk10_broadcast_log {where_sql}"
    total_row = db.query_df(total_sql, params=tuple(params) if params else None)
    total = int(total_row.iloc[0]["total"]) if not total_row.empty else 0
    sql = f"""
    SELECT
        id,
        DATE_FORMAT(server_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS server_time,
        DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS draw_date,
        pre_draw_issue,
        draw_issue,
        latest_slot,
        line_name,
        actionable,
        payload_json,
        DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
    FROM pk10_broadcast_log
    {where_sql}
    ORDER BY id DESC
    LIMIT %s OFFSET %s
    """
    query_params = [*params, page_size, offset]
    rows = db.query_df(sql, params=tuple(query_params)).to_dict(orient="records")
    total_pages = max(1, ceil(total / page_size)) if total else 1
    return {
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "issue": issue,
    }


@app.get("/api/history/bets")
async def api_history_bets(page: int = 1, page_size: int = 40, scope: str = "all") -> dict:
    page = max(1, int(page))
    page_size = max(10, min(200, int(page_size)))
    offset = (page - 1) * page_size
    sql = """
    SELECT
        b.id,
        DATE_FORMAT(b.draw_date, '%%Y-%%m-%%d') AS draw_date,
        b.pre_draw_issue,
        DATE_FORMAT(h.pre_draw_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS pre_draw_time,
        h.pre_draw_code,
        b.slot_1based,
        b.line_name,
        b.status,
        b.selection_json,
        b.odds_display,
        b.stake,
        b.multiplier_value,
        b.ticket_count,
        b.total_cost,
        b.hit_count,
        b.outcome_label,
        b.pnl,
        b.meta_json,
        DATE_FORMAT(b.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
    FROM pk10_bet_log b
    LEFT JOIN """ + settings.db_table + """ h
      ON h.pre_draw_issue = b.pre_draw_issue
    WHERE b.draw_date >= %s
    ORDER BY b.draw_date DESC, b.pre_draw_issue DESC, b.id DESC
    """
    rows = db.query_df(sql, params=(settings.simulation_start_date,)).to_dict(orient="records")
    valid_scopes = {"all", "broadcasted", "pending_future"}
    scope = scope if scope in valid_scopes else "all"
    for row in rows:
        meta = row.get("meta_json")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        elif not isinstance(meta, dict):
            meta = {}
        row["meta_json"] = meta
        row["broadcast_state"] = meta.get("broadcast_state", "pending_future")
        row["broadcast_time"] = meta.get("broadcast_time")
        row["trigger_issue"] = meta.get("trigger_issue")
    counts = {
        "broadcasted": sum(1 for row in rows if row.get("broadcast_state") == "broadcasted"),
        "pending_future": sum(1 for row in rows if row.get("broadcast_state") == "pending_future"),
    }
    counts["all"] = counts["broadcasted"] + counts["pending_future"]
    if scope != "all":
        rows = [row for row in rows if row.get("broadcast_state") == scope]
    total = len(rows)
    rows = rows[offset : offset + page_size]
    total_pages = max(1, ceil(total / page_size)) if total else 1
    return {
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "scope": scope,
        "counts": counts,
    }


@app.get("/events/stream")
async def sse_stream() -> StreamingResponse:
    queue = await runtime.subscribe()

    async def event_generator():
        try:
            snapshot = await runtime.get_snapshot()
            yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            await runtime.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
