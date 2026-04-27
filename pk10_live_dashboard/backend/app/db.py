from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterable

import pandas as pd
import pymysql
from pymysql.cursors import DictCursor

from .settings import settings


def connect():
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_pass,
        database=settings.db_name,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=DictCursor,
    )


@contextmanager
def cursor():
    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def query_df(sql: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
    with cursor() as cur:
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def execute(sql: str, params: Iterable[Any] | None = None) -> int:
    with cursor() as cur:
        if params is None:
            rows = cur.execute(sql)
        else:
            rows = cur.execute(sql, params)
    return rows


def executemany(sql: str, rows: list[tuple[Any, ...]]) -> int:
    if not rows:
        return 0
    with cursor() as cur:
        affected = cur.executemany(sql, rows)
    return affected


def _column_exists(table_name: str, column_name: str) -> bool:
    df = query_df(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (settings.db_name, table_name, column_name),
    )
    return not df.empty


def _index_exists(table_name: str, index_name: str) -> bool:
    df = query_df(
        """
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = %s
          AND table_name = %s
          AND index_name = %s
        LIMIT 1
        """,
        (settings.db_name, table_name, index_name),
    )
    return not df.empty


def _ensure_column(table_name: str, column_name: str, definition_sql: str) -> None:
    if _column_exists(table_name, column_name):
        return
    execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition_sql}")


def _ensure_index(table_name: str, index_name: str, definition_sql: str) -> None:
    if _index_exists(table_name, index_name):
        return
    execute(f"ALTER TABLE {table_name} ADD {definition_sql}")


def ensure_runtime_tables() -> None:
    execute(
        """
        CREATE TABLE IF NOT EXISTS pk10_runtime_state (
            state_key VARCHAR(64) PRIMARY KEY,
            state_json JSON NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS pk10_broadcast_log (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            server_time DATETIME NULL,
            draw_date DATE NULL,
            pre_draw_issue BIGINT NULL,
            draw_issue BIGINT NULL,
            latest_slot INT NULL,
            slot_1based INT NULL,
            line_name VARCHAR(32) NOT NULL,
            actionable TINYINT(1) NOT NULL DEFAULT 0,
            payload_json JSON NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_broadcast_issue_slot (draw_date, line_name, draw_issue, slot_1based),
            KEY idx_issue_line (pre_draw_issue, line_name),
            KEY idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS pk10_bet_log (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            draw_date DATE NOT NULL,
            pre_draw_issue BIGINT NULL,
            slot_1based INT NOT NULL,
            line_name VARCHAR(32) NOT NULL,
            status VARCHAR(16) NOT NULL,
            selection_json JSON NOT NULL,
            odds_display VARCHAR(255) NOT NULL,
            stake DECIMAL(12,2) NOT NULL,
            multiplier_value INT NOT NULL,
            ticket_count INT NOT NULL,
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
    execute(
        """
        CREATE TABLE IF NOT EXISTS pk10_daily_equity (
            draw_date DATE PRIMARY KEY,
            settled_bankroll DECIMAL(18,4) NOT NULL,
            total_real_pnl DECIMAL(18,4) NOT NULL,
            face_real_pnl DECIMAL(18,4) NOT NULL,
            sum_real_pnl DECIMAL(18,4) NOT NULL,
            exact_real_pnl DECIMAL(18,4) NOT NULL,
            drawdown_from_peak DECIMAL(18,4) NOT NULL,
            payload_json JSON NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    _ensure_column("pk10_broadcast_log", "slot_1based", "INT NULL AFTER latest_slot")
    execute(
        """
        UPDATE pk10_broadcast_log
        SET slot_1based = CAST(JSON_UNQUOTE(JSON_EXTRACT(payload_json, '$.slot_1based')) AS UNSIGNED)
        WHERE slot_1based IS NULL
          AND JSON_EXTRACT(payload_json, '$.slot_1based') IS NOT NULL
        """
    )
    execute(
        """
        DELETE t1
        FROM pk10_broadcast_log t1
        JOIN pk10_broadcast_log t2
          ON t1.id > t2.id
         AND t1.draw_date <=> t2.draw_date
         AND t1.line_name = t2.line_name
         AND t1.draw_issue <=> t2.draw_issue
         AND t1.slot_1based <=> t2.slot_1based
        """
    )
    _ensure_index(
        "pk10_broadcast_log",
        "uniq_broadcast_issue_slot",
        "UNIQUE KEY uniq_broadcast_issue_slot (draw_date, line_name, draw_issue, slot_1based)",
    )


def write_runtime_state(state_key: str, payload: dict[str, Any]) -> None:
    execute(
        """
        INSERT INTO pk10_runtime_state (state_key, state_json)
        VALUES (%s, CAST(%s AS JSON))
        ON DUPLICATE KEY UPDATE state_json = VALUES(state_json)
        """,
        (state_key, json.dumps(payload, ensure_ascii=False)),
    )


def read_runtime_state(state_key: str) -> dict[str, Any] | None:
    with cursor() as cur:
        cur.execute(
            "SELECT state_json FROM pk10_runtime_state WHERE state_key = %s",
            (state_key,),
        )
        row = cur.fetchone()
    if not row:
        return None
    value = row["state_json"]
    if isinstance(value, dict):
        return value
    return json.loads(value)
