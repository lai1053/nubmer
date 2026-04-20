from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
import requests

from . import db
from .settings import settings
from .strategy import (
    StrategyModules,
    build_runtime_context,
    load_issue_history_from_db,
    normalize_issue_df,
    snapshot_from_context,
)


def _jsonify(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if is_dataclass(value):
        return _jsonify(asdict(value))
    return value


class LiveRuntime:
    def __init__(self) -> None:
        self.modules = StrategyModules.load(settings.source_root)
        self.snapshot: dict[str, Any] = {
            "generated_at": None,
            "market": {},
            "totals": {},
            "contributions": {},
            "line_state": {},
            "today_plan": {},
            "current_actions": [],
            "daily_curve": [],
        }
        self._lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()
        self._queues: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_pre_draw_issue: int | None = None
        self._issue_df: pd.DataFrame | None = None
        self._context: dict[str, Any] | None = None
        self._context_date: str | None = None

    async def startup(self) -> None:
        db.ensure_runtime_tables()
        persisted = db.read_runtime_state("dashboard")
        if persisted:
            curve = persisted.get("daily_curve") or []
            first_date = str(curve[0].get("date")) if curve else None
            if first_date is not None and first_date < settings.simulation_start_date:
                persisted = None
        async with self._lock:
            if persisted:
                persisted.setdefault("market", {})
                persisted["market"]["refreshing"] = True
                persisted["market"]["message"] = "沿用上次快照启动，后台正在刷新最新状态。"
                self.snapshot = persisted
            else:
                self.snapshot["market"] = {
                    "status": "warming_up",
                    "message": "首轮上下文预热中，历史曲线与投注记录会在后台生成。",
                }
        asyncio.create_task(self.refresh_all(force_issue_log=True))
        self._task = asyncio.create_task(self._poll_loop())

    async def shutdown(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                live_payload = self.fetch_live_payload()
                current_issue = int(live_payload["preDrawIssue"])
                if self._last_pre_draw_issue != current_issue:
                    self.upsert_latest_issue(live_payload)
                    await self.refresh_all(force_issue_log=True, live_payload=live_payload)
                    self._last_pre_draw_issue = current_issue
            except Exception as exc:  # noqa: BLE001
                async with self._lock:
                    self.snapshot.setdefault("market", {})
                    self.snapshot["market"]["last_error"] = str(exc)
            await asyncio.sleep(settings.poll_seconds)

    def fetch_history_rows(self, target_date: str) -> list[dict[str, Any]]:
        response = requests.get(
            settings.history_api_url,
            params={"date": target_date, "lotCode": settings.lot_code},
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 PK10 Live Dashboard"},
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload["result"]["data"])

    def fetch_live_payload(self) -> dict[str, Any]:
        response = requests.get(
            settings.live_api_url,
            params={"lotCode": settings.lot_code},
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 PK10 Live Dashboard"},
        )
        response.raise_for_status()
        payload = response.json()
        return dict(payload["result"]["data"])

    def replace_day_history(self, target_date: str, rows: list[dict[str, Any]]) -> None:
        db.execute(f"DELETE FROM {settings.db_table} WHERE draw_date = %s", (target_date,))
        insert_sql = f"""
        INSERT INTO {settings.db_table} (
            draw_date,
            pre_draw_time,
            pre_draw_issue,
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
            raw_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = [
            (
                target_date,
                row["preDrawTime"],
                int(row["preDrawIssue"]),
                row["preDrawCode"],
                int(row["sumFS"]),
                int(row["sumBigSamll"]),
                int(row["sumSingleDouble"]),
                int(row["firstDT"]),
                int(row["secondDT"]),
                int(row["thirdDT"]),
                int(row["fourthDT"]),
                int(row["fifthDT"]),
                int(row.get("groupCode", 1)),
                json.dumps(row, ensure_ascii=False),
            )
            for row in rows
        ]
        db.executemany(insert_sql, values)

    def upsert_latest_issue(self, payload: dict[str, Any]) -> None:
        target_date = str(payload["preDrawDate"])
        db.execute(f"DELETE FROM {settings.db_table} WHERE pre_draw_issue = %s", (int(payload["preDrawIssue"]),))
        db.execute(
            f"""
            INSERT INTO {settings.db_table} (
                draw_date,
                pre_draw_time,
                pre_draw_issue,
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
                raw_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                target_date,
                payload["preDrawTime"],
                int(payload["preDrawIssue"]),
                payload["preDrawCode"],
                int(payload["sumFS"]),
                int(payload["sumBigSamll"]),
                int(payload["sumSingleDouble"]),
                int(payload["firstDT"]),
                int(payload["secondDT"]),
                int(payload["thirdDT"]),
                int(payload["fourthDT"]),
                int(payload["fifthDT"]),
                int(payload.get("groupCode", 1)),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def append_live_issue_to_cache(self, payload: dict[str, Any]) -> None:
        if self._issue_df is None:
            return
        row = {
            "draw_date": pd.Timestamp(payload["preDrawDate"]),
            "pre_draw_time": pd.Timestamp(payload["preDrawTime"]),
            "pre_draw_issue": int(payload["preDrawIssue"]),
            "pre_draw_code": str(payload["preDrawCode"]),
            "sum_fs": int(payload["sumFS"]),
            "sum_big_small": int(payload["sumBigSamll"]),
            "sum_single_double": int(payload["sumSingleDouble"]),
            "first_dt": int(payload["firstDT"]),
            "second_dt": int(payload["secondDT"]),
            "third_dt": int(payload["thirdDT"]),
            "fourth_dt": int(payload["fourthDT"]),
            "fifth_dt": int(payload["fifthDT"]),
            "group_code": int(payload.get("groupCode", 1)),
        }
        for index, key in enumerate(
            ["firstNum", "secondNum", "thirdNum", "fourthNum", "fifthNum", "sixthNum", "seventhNum", "eighthNum", "ninthNum", "tenthNum"],
            start=1,
        ):
            row[f"pos{index}"] = int(payload[key])
        work = self._issue_df[self._issue_df["pre_draw_issue"] != row["pre_draw_issue"]].copy()
        work = pd.concat([work, pd.DataFrame([row])], ignore_index=True)
        work = work.sort_values(["draw_date", "pre_draw_time", "pre_draw_issue"]).reset_index(drop=True)
        self._issue_df = work

    def sync_missing_history(self, live_payload: dict[str, Any] | None = None) -> None:
        latest = db.query_df(f"SELECT MAX(draw_date) AS max_date FROM {settings.db_table}")
        max_date = latest.iloc[0]["max_date"] if not latest.empty else None
        today = pd.Timestamp(live_payload["preDrawDate"] if live_payload else pd.Timestamp.now()).date()
        if pd.isna(max_date):
            start_day = pd.Timestamp(settings.history_start_date).date()
        else:
            start_day = pd.Timestamp(max_date).date()
        day = start_day
        while day <= today:
            rows = self.fetch_history_rows(day.isoformat())
            if rows:
                self.replace_day_history(day.isoformat(), rows)
            day += timedelta(days=1)

    def persist_daily_equity(self, daily_curve: list[dict[str, Any]]) -> None:
        db.execute("DELETE FROM pk10_daily_equity")
        rows = []
        for item in daily_curve:
            if item.get("provisional"):
                continue
            if str(item["date"]) < settings.simulation_start_date:
                continue
            rows.append(
                (
                    item["date"],
                    item["settled_bankroll"],
                    item["total_real_pnl"],
                    item["face_real_pnl"],
                    item["sum_real_pnl"],
                    item["exact_real_pnl"],
                    item["drawdown_from_peak"],
                    json.dumps(item, ensure_ascii=False),
                )
            )
        db.executemany(
            """
            INSERT INTO pk10_daily_equity (
                draw_date,
                settled_bankroll,
                total_real_pnl,
                face_real_pnl,
                sum_real_pnl,
                exact_real_pnl,
                drawdown_from_peak,
                payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )

    def _selection_signature(self, selection: dict[str, Any] | None) -> str:
        selection = selection or {}
        compact = {key: value for key, value in selection.items() if value is not None}
        return json.dumps(compact, ensure_ascii=False, sort_keys=True)

    def build_broadcast_views(
        self,
        bet_rows: list[dict[str, Any]],
        snapshot: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        market = snapshot.get("market", {})
        simulation_start = settings.simulation_start_date
        if self._issue_df is None or self._issue_df.empty:
            work = pd.DataFrame()
        else:
            work = normalize_issue_df(self._issue_df)
        if work.empty:
            issue_meta_by_issue: dict[int, dict[str, Any]] = {}
            prev_meta_by_issue: dict[int, dict[str, Any] | None] = {}
        else:
            work["slot_1based"] = work.groupby("draw_date").cumcount() + 1
            issue_meta_by_issue = {}
            prev_meta_by_issue = {}
            for _, day_group in work.groupby("draw_date", sort=False):
                day_rows = list(day_group.itertuples(index=False))
                prev_row = None
                for row in day_rows:
                    meta = {
                        "draw_date": pd.Timestamp(row.draw_date).strftime("%Y-%m-%d"),
                        "pre_draw_time": pd.Timestamp(row.draw_ts).strftime("%Y-%m-%d %H:%M:%S"),
                        "slot_1based": int(row.slot_1based),
                    }
                    issue = int(row.pre_draw_issue)
                    issue_meta_by_issue[issue] = meta
                    prev_meta_by_issue[issue] = None if prev_row is None else {
                        "issue": int(prev_row.pre_draw_issue),
                        "draw_date": pd.Timestamp(prev_row.draw_date).strftime("%Y-%m-%d"),
                        "pre_draw_time": pd.Timestamp(prev_row.draw_ts).strftime("%Y-%m-%d %H:%M:%S"),
                        "slot_1based": int(prev_row.slot_1based),
                    }
                    prev_row = row

        actionable_rows = [row for row in snapshot.get("current_actions", []) if row.get("slot_1based")]
        action_by_full_key = {}
        action_by_loose_key = {}
        for action in actionable_rows:
            selection_sig = self._selection_signature(action.get("selection"))
            full_key = (
                str(action.get("line_name") or ""),
                int(action.get("draw_issue") or 0),
                int(action.get("slot_1based") or 0),
                selection_sig,
            )
            loose_key = (
                str(action.get("line_name") or ""),
                int(action.get("slot_1based") or 0),
                selection_sig,
            )
            action_by_full_key[full_key] = action
            action_by_loose_key[loose_key] = action

        annotated_rows: list[dict[str, Any]] = []
        broadcast_rows: list[dict[str, Any]] = []
        for item in bet_rows:
            draw_date = str(item.get("draw_date") or "")
            if draw_date < simulation_start:
                continue
            row = dict(item)
            selection_json = row.get("selection_json") or {}
            selection_sig = self._selection_signature(selection_json if isinstance(selection_json, dict) else {})
            target_issue = row.get("pre_draw_issue")
            full_key = (
                str(row.get("line_name") or ""),
                int(target_issue or 0),
                int(row.get("slot_1based") or 0),
                selection_sig,
            )
            loose_key = (
                str(row.get("line_name") or ""),
                int(row.get("slot_1based") or 0),
                selection_sig,
            )
            matched_action = action_by_full_key.get(full_key) or action_by_loose_key.get(loose_key)
            if target_issue is None and matched_action is not None:
                target_issue = matched_action.get("draw_issue")
                row["pre_draw_issue"] = target_issue

            status = str(row.get("status") or "")
            is_broadcasted = status in {"settled", "executed"} or matched_action is not None
            trigger_issue = None
            broadcast_time = None
            latest_slot = None
            if matched_action is not None and int(matched_action.get("draw_issue") or 0) == int(market.get("draw_issue") or 0):
                trigger_issue = market.get("pre_draw_issue")
                broadcast_time = market.get("server_time")
                latest_slot = market.get("raw_latest_slot")
            elif target_issue is not None:
                prev_meta = prev_meta_by_issue.get(int(target_issue))
                if prev_meta is not None:
                    trigger_issue = prev_meta.get("issue")
                    broadcast_time = prev_meta.get("pre_draw_time")
                    latest_slot = prev_meta.get("slot_1based")

            meta_json = row.get("meta_json") or {}
            if not isinstance(meta_json, dict):
                meta_json = {}
            meta_json.update(
                {
                    "broadcast_state": "broadcasted" if is_broadcasted else "pending_future",
                    "broadcast_time": broadcast_time,
                    "trigger_issue": trigger_issue,
                }
            )
            row["meta_json"] = meta_json
            annotated_rows.append(row)

            if not is_broadcasted or target_issue is None:
                continue
            payload = {
                "line_name": row.get("line_name"),
                "slot_1based": int(row.get("slot_1based") or 0),
                "selection": selection_json if isinstance(selection_json, dict) else {},
                "stake": float(row.get("stake") or 0.0),
                "multiplier_value": int(row.get("multiplier_value") or 0),
                "ticket_count": int(row.get("ticket_count") or 0),
                "total_cost": float(row.get("total_cost") or 0.0),
                "odds_display": row.get("odds_display"),
                "status": row.get("status"),
            }
            broadcast_rows.append(
                {
                    "server_time": broadcast_time,
                    "draw_date": draw_date or issue_meta_by_issue.get(int(target_issue), {}).get("draw_date"),
                    "pre_draw_issue": trigger_issue,
                    "draw_issue": int(target_issue),
                    "latest_slot": latest_slot,
                    "line_name": row.get("line_name"),
                    "actionable": 1,
                    "payload_json": payload,
                }
            )
        broadcast_rows.sort(
            key=lambda item: (
                str(item.get("server_time") or ""),
                int(item.get("draw_issue") or 0),
                str(item.get("line_name") or ""),
            )
        )
        return annotated_rows, broadcast_rows

    def persist_bet_rows(self, bet_rows: list[dict[str, Any]]) -> None:
        db.execute("DELETE FROM pk10_bet_log")
        rows = [
            (
                item["draw_date"],
                item.get("pre_draw_issue"),
                item["slot_1based"],
                item["line_name"],
                item["status"],
                json.dumps(item["selection_json"], ensure_ascii=False),
                item["odds_display"],
                item["stake"],
                item["multiplier_value"],
                item["ticket_count"],
                item["total_cost"],
                item.get("hit_count"),
                item.get("outcome_label"),
                item.get("pnl"),
                json.dumps(item.get("meta_json", {}), ensure_ascii=False),
            )
            for item in bet_rows
            if str(item.get("draw_date") or "") >= settings.simulation_start_date
        ]
        db.executemany(
            """
            INSERT INTO pk10_bet_log (
                draw_date,
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
                meta_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )

    def persist_broadcast_rows(self, broadcast_rows: list[dict[str, Any]]) -> None:
        db.execute("DELETE FROM pk10_broadcast_log")
        rows = [
            (
                item.get("server_time") or None,
                item.get("draw_date") or None,
                item.get("pre_draw_issue"),
                item.get("draw_issue"),
                item.get("latest_slot"),
                item.get("line_name"),
                1,
                json.dumps(item.get("payload_json", {}), ensure_ascii=False),
            )
            for item in broadcast_rows
            if str(item.get("draw_date") or "") >= settings.simulation_start_date
        ]
        db.executemany(
            """
            INSERT INTO pk10_broadcast_log (
                server_time,
                draw_date,
                pre_draw_issue,
                draw_issue,
                latest_slot,
                line_name,
                actionable,
                payload_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )

    async def refresh_all(self, force_issue_log: bool = False, live_payload: dict[str, Any] | None = None) -> None:
        async with self._refresh_lock:
            public_snapshot = await asyncio.to_thread(self._refresh_sync, force_issue_log, live_payload)
            async with self._lock:
                self.snapshot = public_snapshot
                for queue in list(self._queues):
                    try:
                        queue.put_nowait({"type": "dashboard", "payload": public_snapshot})
                    except asyncio.QueueFull:
                        pass

    def _refresh_sync(self, force_issue_log: bool = False, live_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        live_payload = live_payload or self.fetch_live_payload()
        live_date = str(live_payload["preDrawDate"])
        need_full_rebuild = self._issue_df is None or self._context is None or self._context_date != live_date
        if need_full_rebuild:
            self.sync_missing_history(live_payload)
            self._issue_df = load_issue_history_from_db(settings.history_start_date)
            self._context = build_runtime_context(self.modules, self._issue_df)
            self._context_date = live_date
        self.append_live_issue_to_cache(live_payload)
        snapshot = snapshot_from_context(self.modules, self._issue_df, live_payload, self._context)
        public_snapshot = {k: v for k, v in snapshot.items() if k not in {"replay", "bet_rows"}}
        public_snapshot = _jsonify(public_snapshot)
        annotated_bet_rows, broadcast_rows = self.build_broadcast_views(_jsonify(snapshot["bet_rows"]), public_snapshot)
        self.persist_daily_equity(public_snapshot["daily_curve"])
        self.persist_bet_rows(annotated_bet_rows)
        if force_issue_log:
            self.persist_broadcast_rows(broadcast_rows)
        db.write_runtime_state("dashboard", public_snapshot)
        return public_snapshot

    async def get_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return self.snapshot

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        async with self._lock:
            self._queues.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._queues.discard(queue)


runtime = LiveRuntime()
