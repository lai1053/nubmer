from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value is not None else default


@dataclass(frozen=True)
class Settings:
    app_name: str = _env("PK10_APP_NAME", "PK10 Live Dashboard")
    app_env: str = _env("PK10_APP_ENV", "production")
    host: str = _env("PK10_HOST", "127.0.0.1")
    port: int = int(_env("PK10_PORT", "18080"))

    project_root: Path = Path(__file__).resolve().parents[2]
    source_root: Path = Path(__file__).resolve().parents[3]

    db_host: str = _env("PK10_DB_HOST", "127.0.0.1")
    db_port: int = int(_env("PK10_DB_PORT", "3307"))
    db_user: str = _env("PK10_DB_USER", "root")
    db_pass: str = _env("PK10_DB_PASS", "123456")
    db_name: str = _env("PK10_DB_NAME", "xyft_lottery_data")
    db_table: str = _env("PK10_DB_TABLE", "pks_history")

    lot_code: str = _env("PK10_LOT_CODE", "10037")
    history_api_url: str = _env(
        "PK10_HISTORY_API_URL",
        "https://www.1682010.co/api/pks/getPksHistoryList.do",
    )
    live_api_url: str = _env(
        "PK10_LIVE_API_URL",
        "https://api.apiose188.com/pks/getLotteryPksInfo.do",
    )
    poll_seconds: int = int(_env("PK10_POLL_SECONDS", "5"))
    history_start_date: str = _env("PK10_HISTORY_START_DATE", _env("PK10_START_DATE", "2026-01-01"))
    simulation_start_date: str = _env(
        "PK10_SIMULATION_START_DATE",
        _env("PK10_REPLAY_START_DATE", "2026-04-20"),
    )

    bankroll_start: float = float(_env("PK10_BANKROLL_START", "1000"))
    base_stake: float = float(_env("PK10_BASE_STAKE", "10"))
    max_multiplier: int = int(_env("PK10_MAX_MULTIPLIER", "5"))
    blackout_start: str = _env("PK10_BLACKOUT_START", "06:00:00")
    blackout_end: str = _env("PK10_BLACKOUT_END", "07:00:00")

    face_policy_id: str = _env(
        "PK10_FACE_POLICY_ID",
        "core40_spread_only__exp0_off__oe40_spread_only__cd2",
    )
    sum_candidate_id: str = _env("PK10_SUM_CANDIDATE_ID", "intraday_1037")
    exact_base_gate_id: str = _env(
        "PK10_EXACT_BASE_GATE_ID",
        "late|big|edge_low|same_top1_prev=all",
    )
    exact_obs_window: int = int(_env("PK10_EXACT_OBS_WINDOW", "192"))
    exact_execution_rule: str = _env(
        "PK10_EXACT_EXECUTION_RULE",
        "front_pair_major_consensus_only",
    )
    exact_net_win: float = float(_env("PK10_EXACT_NET_WIN", "8.9"))


settings = Settings()
