from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pymysql


DB_HOST = os.getenv("JSFT_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("JSFT_DB_PORT", "3307"))
DB_USER = os.getenv("JSFT_DB_USER", "root")
DB_PASS = os.getenv("JSFT_DB_PASS", "")
DB_NAME = os.getenv("JSFT_DB_NAME", "xyft_lottery_data")
DB_TABLE = os.getenv("JSFT_DB_TABLE", "jsft_pks_history")
HISTORY_API_URL = os.getenv(
    "JSFT_HISTORY_API_URL",
    "https://www.1682010.co/api/pks/getPksHistoryList.do",
)
LOT_CODE = os.getenv("JSFT_LOT_CODE", "10035")
TIMEZONE = ZoneInfo(os.getenv("JSFT_TIMEZONE", "Asia/Shanghai"))
APP_ROOT = Path(__file__).resolve().parent
LOG_DIR = APP_ROOT / "data"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def db_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def fetch_history_rows(target_date: str) -> list[dict[str, Any]]:
    url = HISTORY_API_URL + "?" + urllib.parse.urlencode({"date": target_date, "lotCode": LOT_CODE})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JSFT PK10 Shadow"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    result = payload.get("result")
    if isinstance(result, dict):
        rows = result.get("data") or []
    elif isinstance(result, list):
        rows = result
    else:
        rows = []
    rows = [row for row in rows if row.get("preDrawIssue") and row.get("preDrawTime")]
    return sorted(rows, key=lambda row: (str(row["preDrawTime"]), int(row["preDrawIssue"])))


def latest_db_date() -> date | None:
    with db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT MAX(draw_date) AS max_date FROM {DB_TABLE}")
            row = cursor.fetchone() or {}
    value = row.get("max_date")
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def replace_day(target_date: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    insert_sql = f"""
        INSERT INTO {DB_TABLE} (
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
    with db_conn() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"DELETE FROM {DB_TABLE} WHERE draw_date = %s", (target_date,))
                cursor.executemany(insert_sql, values)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return len(values)


def date_range(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update JSFT PK10 history table from 168 history API")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--days-back", type=int, default=2, help="Also refresh recent N days to complete partial days")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    today = datetime.now(TIMEZONE).date()
    latest = latest_db_date()
    if args.start_date:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    elif latest is None:
        start = today
    else:
        start = max(latest - timedelta(days=max(args.days_back, 0)), date(2020, 1, 1))
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else today
    if start > end:
        start = end

    log_rows: list[dict[str, Any]] = []
    for day in date_range(start, end):
        day_str = day.isoformat()
        try:
            rows = fetch_history_rows(day_str)
            count = replace_day(day_str, rows)
            status = "updated" if count else "empty"
            message = ""
        except Exception as exc:  # noqa: BLE001
            count = 0
            status = "error"
            message = str(exc)
        item = {
            "updated_at": datetime.now(TIMEZONE).isoformat(timespec="seconds"),
            "date": day_str,
            "status": status,
            "count": count,
            "message": message,
        }
        log_rows.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)

    with (LOG_DIR / "jsft_history_update_last.json").open("w", encoding="utf-8") as handle:
        json.dump({"rows": log_rows}, handle, ensure_ascii=False, indent=2)
    return 1 if any(row["status"] == "error" for row in log_rows) else 0


if __name__ == "__main__":
    sys.exit(main())
