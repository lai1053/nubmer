from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value is not None else default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _face_policy_short_label(policy_id: str) -> str:
    for part in str(policy_id).split("__"):
        if part.startswith("oe"):
            return part.split("_", 1)[0]
    return str(policy_id)


def _blackout_label(blackout_start: str, blackout_end: str) -> str:
    start = str(blackout_start or "").strip()
    end = str(blackout_end or "").strip()
    if not start or not end:
        return "无 blackout"
    return f"blackout {start[:5]}-{end[:5]}"


@dataclass(frozen=True)
class StrategyProfile:
    id: str
    label: str
    is_shadow: bool
    face_policy_id: str
    sum_candidate_id: str
    exact_base_gate_id: str
    exact_obs_window: int
    exact_execution_rule: str
    blackout_start: str
    blackout_end: str


@dataclass(frozen=True)
class Settings:
    app_name: str = _env("PK10_APP_NAME", "PK10 Live Dashboard")
    app_env: str = _env("PK10_APP_ENV", "production")
    host: str = _env("PK10_HOST", "127.0.0.1")
    port: int = int(_env("PK10_PORT", "18080"))

    project_root: Path = Path(__file__).resolve().parents[2]
    source_root: Path = Path(__file__).resolve().parents[3]

    auth_store_path: Path = Path(
        _env("PK10_AUTH_STORE", str(Path(__file__).resolve().parents[1] / "auth_users.json"))
    )
    auth_secret: str = _env("PK10_AUTH_SECRET", "change-me-pk10-live-dashboard")
    auth_cookie_name: str = _env("PK10_AUTH_COOKIE_NAME", "pk10_session")
    auth_session_hours: int = int(_env("PK10_AUTH_SESSION_HOURS", "168"))
    auth_cookie_secure: bool = _env_bool("PK10_AUTH_COOKIE_SECURE", False)
    auth_login_event_limit: int = int(_env("PK10_AUTH_LOGIN_EVENT_LIMIT", "2000"))
    bootstrap_admin_username: str = _env("PK10_ADMIN_USER", "admin")
    bootstrap_admin_password: str = _env("PK10_ADMIN_PASSWORD", "admin123456")
    bootstrap_admin_display_name: str = _env("PK10_ADMIN_DISPLAY_NAME", "系统管理员")

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

    primary_label: str = _env("PK10_PRIMARY_LABEL", "")
    face_policy_id: str = _env(
        "PK10_FACE_POLICY_ID",
        "core40_spread_only__exp0_off__oe20_spread_only__cd2",
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

    compare_enabled: bool = _env_bool("PK10_COMPARE_ENABLED", False)
    compare_label: str = _env("PK10_COMPARE_LABEL", "")
    compare_face_policy_id: str = _env(
        "PK10_COMPARE_FACE_POLICY_ID",
        "core40_spread_only__exp0_off__oe40_spread_only__cd2",
    )
    compare_sum_candidate_id: str = _env(
        "PK10_COMPARE_SUM_CANDIDATE_ID",
        _env("PK10_SUM_CANDIDATE_ID", "intraday_1037"),
    )
    compare_exact_base_gate_id: str = _env(
        "PK10_COMPARE_EXACT_BASE_GATE_ID",
        _env("PK10_EXACT_BASE_GATE_ID", "late|big|edge_low|same_top1_prev=all"),
    )
    compare_exact_obs_window: int = int(
        _env(
            "PK10_COMPARE_EXACT_OBS_WINDOW",
            _env("PK10_EXACT_OBS_WINDOW", "192"),
        )
    )
    compare_exact_execution_rule: str = _env(
        "PK10_COMPARE_EXACT_EXECUTION_RULE",
        _env("PK10_EXACT_EXECUTION_RULE", "front_pair_major_consensus_only"),
    )
    compare_blackout_start: str = _env("PK10_COMPARE_BLACKOUT_START", "")
    compare_blackout_end: str = _env("PK10_COMPARE_BLACKOUT_END", "")

    @property
    def primary_profile(self) -> StrategyProfile:
        label = self.primary_label.strip() or (
            f"主策略 / {_blackout_label(self.blackout_start, self.blackout_end)} / "
            f"{_face_policy_short_label(self.face_policy_id)}"
        )
        return StrategyProfile(
            id="primary",
            label=label,
            is_shadow=False,
            face_policy_id=self.face_policy_id,
            sum_candidate_id=self.sum_candidate_id,
            exact_base_gate_id=self.exact_base_gate_id,
            exact_obs_window=self.exact_obs_window,
            exact_execution_rule=self.exact_execution_rule,
            blackout_start=self.blackout_start,
            blackout_end=self.blackout_end,
        )

    @property
    def compare_profile(self) -> StrategyProfile | None:
        if not self.compare_enabled:
            return None
        label = self.compare_label.strip() or (
            f"对照 / {_blackout_label(self.compare_blackout_start, self.compare_blackout_end)} / "
            f"{_face_policy_short_label(self.compare_face_policy_id)}"
        )
        return StrategyProfile(
            id="compare",
            label=label,
            is_shadow=True,
            face_policy_id=self.compare_face_policy_id,
            sum_candidate_id=self.compare_sum_candidate_id,
            exact_base_gate_id=self.compare_exact_base_gate_id,
            exact_obs_window=self.compare_exact_obs_window,
            exact_execution_rule=self.compare_exact_execution_rule,
            blackout_start=self.compare_blackout_start,
            blackout_end=self.compare_blackout_end,
        )

    @property
    def profiles(self) -> tuple[StrategyProfile, ...]:
        compare = self.compare_profile
        if compare is None:
            return (self.primary_profile,)
        return (self.primary_profile, compare)


settings = Settings()
