from __future__ import annotations

import asyncio
import json
from math import ceil
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import db
from .auth import auth_store, create_session_token, get_current_user, require_admin
from .runtime import runtime
from .settings import settings


app = FastAPI(title=settings.app_name)

HISTORY_ISSUE_TABLES = {
    "jssc": settings.db_table,
    "jsft": "jsft_pks_history",
}


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "viewer"
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


def _parse_json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _history_issue_table(code: str) -> str:
    table_name = HISTORY_ISSUE_TABLES.get(str(code or "").strip().lower())
    if not table_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code 只支持 jssc 或 jsft",
        )
    return table_name


def _table_exists(table_name: str) -> bool:
    result = db.query_df(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_name = %s
        LIMIT 1
        """,
        (settings.db_name, table_name),
    )
    return not result.empty


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_hours * 3600,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.auth_cookie_name, path="/")


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _login_context(request: Request) -> dict[str, str]:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    ip_address = forwarded_for.split(",", 1)[0].strip()
    if not ip_address and request.client:
        ip_address = request.client.host
    return {
        "ip_address": ip_address,
        "user_agent": request.headers.get("user-agent", ""),
    }


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


@app.post("/api/auth/login")
async def api_auth_login(payload: LoginRequest, request: Request, response: Response) -> dict:
    user = auth_store.authenticate(payload.username, payload.password, _login_context(request))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
        )
    _set_session_cookie(response, create_session_token(user))
    return {"user": user}


@app.post("/api/auth/logout")
async def api_auth_logout(response: Response) -> dict:
    _clear_session_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
async def api_auth_me(user: dict[str, Any] = Depends(get_current_user)) -> dict:
    return {"user": user}


@app.get("/api/admin/users")
async def api_admin_users(_: dict[str, Any] = Depends(require_admin)) -> dict:
    return {"users": auth_store.list_users()}


@app.get("/api/admin/login-events")
async def api_admin_login_events(
    user_id: str = "",
    limit: int = 100,
    _: dict[str, Any] = Depends(require_admin),
) -> dict:
    return {"events": auth_store.list_login_events(user_id=user_id, limit=limit)}


@app.post("/api/admin/users")
async def api_admin_create_user(
    payload: UserCreateRequest,
    _: dict[str, Any] = Depends(require_admin),
) -> dict:
    try:
        user = auth_store.create_user(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            role=payload.role,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return {"user": user}


@app.patch("/api/admin/users/{user_id}")
async def api_admin_update_user(
    user_id: str,
    payload: UserUpdateRequest,
    _: dict[str, Any] = Depends(require_admin),
) -> dict:
    changes = payload.dict(exclude_unset=True)
    try:
        user = auth_store.update_user(user_id, changes)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return {"user": user}


@app.delete("/api/admin/users/{user_id}")
async def api_admin_delete_user(
    user_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict:
    if str(current_user.get("id")) == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录用户",
        )
    try:
        auth_store.delete_user(user_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return {"ok": True}


@app.get("/api/dashboard")
async def api_dashboard(_: dict[str, Any] = Depends(get_current_user)) -> dict:
    return await runtime.get_snapshot()


@app.get("/api/curve/daily")
async def api_curve_daily(
    start_date: str = settings.simulation_start_date,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict:
    snapshot = await runtime.get_snapshot()
    rows = snapshot.get("daily_curve", [])
    if start_date:
        rows = [row for row in rows if str(row.get("date", "")) >= start_date]
    return {"rows": rows, "start_date": start_date}


@app.get("/api/history/broadcasts")
async def api_history_broadcasts(
    page: int = 1,
    page_size: int = 40,
    issue: str = "",
    _: dict[str, Any] = Depends(get_current_user),
) -> dict:
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
async def api_history_bets(
    page: int = 1,
    page_size: int = 40,
    scope: str = "all",
    _: dict[str, Any] = Depends(get_current_user),
) -> dict:
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


@app.get("/api/history/issues")
async def api_history_issues(
    date: str,
    code: str,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict:
    date = str(date or "").strip()
    code = str(code or "").strip().lower()
    if not date or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date 和 code 不能为空",
        )

    table_name = _history_issue_table(code)
    if not _table_exists(table_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据表 {table_name} 不存在",
        )

    sql = f"""
    SELECT
        id,
        DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS draw_date,
        pre_draw_issue,
        DATE_FORMAT(pre_draw_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS pre_draw_time,
        pre_draw_code,
        sum_fs,
        sum_big_small,
        sum_single_double,
        first_dt,
        second_dt,
        third_dt,
        fourth_dt,
        fifth_dt,
        group_code,
        raw_json,
        DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
    FROM {table_name}
    WHERE draw_date = %s
    ORDER BY pre_draw_time, pre_draw_issue
    """
    rows = db.query_df(sql, params=(date,)).to_dict(orient="records")
    for row in rows:
        row["raw_json"] = _parse_json_field(row.get("raw_json"))

    return {
        "date": date,
        "code": code,
        "table": table_name,
        "rows": rows,
        "count": len(rows),
    }


@app.get("/api/history/by-code")
async def api_history_by_code(
    date: str,
    code: str,
    source_code: str = "jssc",
    _: dict[str, Any] = Depends(get_current_user),
) -> dict:
    date = str(date or "").strip()
    code = str(code or "").strip()
    source_code = str(source_code or "").strip().lower()
    if not date or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date 和 code 不能为空",
        )

    table_name = _history_issue_table(source_code)

    issue_sql = f"""
    SELECT
        DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS draw_date,
        pre_draw_issue,
        DATE_FORMAT(pre_draw_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS pre_draw_time,
        pre_draw_code,
        sum_fs,
        sum_big_small,
        sum_single_double,
        first_dt,
        second_dt,
        third_dt,
        fourth_dt,
        fifth_dt,
        group_code
    FROM {table_name}
    WHERE draw_date = %s
      AND pre_draw_code = %s
    ORDER BY pre_draw_time, pre_draw_issue
    """
    issues = db.query_df(issue_sql, params=(date, code)).to_dict(orient="records")
    issue_ids = [int(row["pre_draw_issue"]) for row in issues if row.get("pre_draw_issue") is not None]
    if not issue_ids:
        return {
            "date": date,
            "code": code,
            "issues": [],
            "bets": [],
            "broadcasts": [],
            "counts": {"issues": 0, "bets": 0, "broadcasts": 0},
        }

    issue_placeholders = ", ".join(["%s"] * len(issue_ids))
    bet_sql = f"""
    SELECT
        id,
        DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS draw_date,
        pre_draw_issue,
        slot_1based,
        line_name,
        status,
        selection_json,
        odds_display,
        stake,
        multiplier_value,
        ticket_count,
        total_cost,
        hit_count,
        outcome_label,
        pnl,
        meta_json,
        DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
    FROM pk10_bet_log
    WHERE draw_date = %s
      AND pre_draw_issue IN ({issue_placeholders})
    ORDER BY pre_draw_issue DESC, id DESC
    """
    bet_params: list[object] = [date, *issue_ids]
    bets = db.query_df(bet_sql, params=tuple(bet_params)).to_dict(orient="records")
    for row in bets:
        row["selection_json"] = _parse_json_field(row.get("selection_json"))
        row["meta_json"] = _parse_json_field(row.get("meta_json"))

    broadcast_sql = f"""
    SELECT
        id,
        DATE_FORMAT(server_time, '%%Y-%%m-%%d %%H:%%i:%%s') AS server_time,
        DATE_FORMAT(draw_date, '%%Y-%%m-%%d') AS draw_date,
        pre_draw_issue,
        draw_issue,
        latest_slot,
        slot_1based,
        line_name,
        actionable,
        payload_json,
        DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
    FROM pk10_broadcast_log
    WHERE draw_date = %s
      AND (
        pre_draw_issue IN ({issue_placeholders})
        OR draw_issue IN ({issue_placeholders})
      )
    ORDER BY id DESC
    """
    broadcast_params: list[object] = [date, *issue_ids, *issue_ids]
    broadcasts = db.query_df(broadcast_sql, params=tuple(broadcast_params)).to_dict(orient="records")
    for row in broadcasts:
        row["payload_json"] = _parse_json_field(row.get("payload_json"))

    return {
        "date": date,
        "code": code,
        "source_code": source_code,
        "table": table_name,
        "issues": issues,
        "bets": bets,
        "broadcasts": broadcasts,
        "counts": {
            "issues": len(issues),
            "bets": len(bets),
            "broadcasts": len(broadcasts),
        },
    }


def _proxy_jsft_shadow(path: str) -> dict[str, Any]:
    import requests as _requests

    url = f"{settings.jsft_shadow_base_url.rstrip('/')}{path}"
    headers: dict[str, str] = {"Accept": "application/json"}
    token = settings.jsft_shadow_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = _requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except _requests.exceptions.ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JSFT shadow service unreachable: {exc}",
        ) from exc
    except _requests.exceptions.Timeout as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"JSFT shadow service timeout: {exc}",
        ) from exc
    except _requests.exceptions.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JSFT shadow service error: {exc}",
        ) from exc


@app.get("/api/jsft-shadow/state")
async def api_jsft_shadow_state(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _proxy_jsft_shadow("/api/state")


@app.get("/api/jsft-shadow/replay")
async def api_jsft_shadow_replay(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _proxy_jsft_shadow("/api/replay")


@app.get("/api/jsft-shadow/data-quality")
async def api_jsft_shadow_data_quality(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _proxy_jsft_shadow("/api/data-quality")


@app.get("/api/jsft-shadow/shadow-status")
async def api_jsft_shadow_shadow_status(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _proxy_jsft_shadow("/api/shadow/status")


@app.get("/events/stream")
async def sse_stream(_: dict[str, Any] = Depends(get_current_user)) -> StreamingResponse:
    queue = await runtime.subscribe()

    async def event_generator():
        try:
            snapshot = await runtime.get_snapshot()
            yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            await runtime.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
