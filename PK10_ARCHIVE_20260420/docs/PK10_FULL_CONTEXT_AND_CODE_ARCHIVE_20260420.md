# PK10 全量推理、冻结窗口依据与工程代码归档

生成时间：2026-04-20 16:00:00 +08:00

## 1. 归档目的

这个单文件用于把本轮 `PK10` 项目的三类核心信息合并归档到一个地方：

- 推理过程与关键决策时间线
- 当前冻结窗口与资金口径依据
- 当前用于回放、部署和线上运行的工程源码

说明：

- 本文件收录的是**自研源码、部署配置、回放脚本、共享记忆**。
- 不收录 `node_modules`、`dist`、`__pycache__`、图片/CSV 等生成产物。
- 不收录线上真实 `.env`、Basic Auth 密码、SSH 私钥等敏感信息。
- 线上最新口径以本文件“冻结窗口依据”和“最新模拟口径”章节为准。

## 2. 项目当前冻结口径

### 2.1 当前线上/回放口径

- 窗口预热：`2026-01-01`
- 模拟投注：`2026-04-01`
- 数据库：`xyft_lottery_data.pks_history`
- 历史补数接口：`https://www.1682010.co/api/pks/getPksHistoryList.do?date=YYYY-MM-DD&lotCode=10037`
- 即时接口：`https://api.apiose188.com/pks/getLotteryPksInfo.do?lotCode=10037`
- 共享资金池：`1000` 起步
- 基础投注：`10`
- blackout：每天 `06:00-07:00` 不投注

### 2.2 三条冻结线

#### 双面 face

- 冻结窗口：`core40_spread_only__exp0_off__oe40_spread_only__cd2`
- 语义：`round35` 稳健部署版 + `round37` 的 `06:00-07:00` issue 过滤口径
- 资金推进：**日级马丁** `1 -> 2 -> 4 -> 5`
- 冷却：`cd2`
- 当前 live 面板只在该日 `mode != cash` 时落真实投注

#### 冠亚和 sum

- 冻结窗口：`intraday_1037`
- 日内判窗：前 `192` 期结束后判断当天是否是可做窗口
- 当前赔率口径：**扣除本金后的净赢档** `41 / 20 / 12 / 10 / 7.5`
- 资金推进：**日级马丁** `1 -> 2 -> 4 -> 5`
- 同一天所有和值投注槽位共用同一日档位，不做同日逐笔翻倍

#### 定位胆 exact

- 冻结窗口：`late|big|edge_low|same_top1_prev=all + obs=192 + front_pair_major_consensus_only`
- 日内观测窗：`obs = 192`
- 晚段目标位：围绕 `577 / 961 / 1152` 这类固定晚段槽位执行
- 投注方式：**固定注 10**，不做马丁

## 3. 冻结窗口依据

### 3.1 双面冻结依据

双面线最终冻结为 `core40_spread_only__exp0_off__oe40_spread_only__cd2`，依据来自此前单线推演与部署验证：

- `round35` 稳健部署版确认该策略为当前可用主策略
- `round37` 额外证明：如果把 `06:00-07:00` 的 issue 在样本层先删除，再构建日级 `slot/spread/gate/cooldown`，得到的表现优于简单下单层 blackout
- 因此 live 版对双面沿用 `round37` 风格过滤，而不是仅在下单时跳过该小时

### 3.2 冠亚和冻结依据

冠亚和线最终保留 `intraday_1037`，依据是：

- 这是此前长期跟踪的主 intraday 结构线
- 判窗依赖前 `192` 期的日内走势，而不是等全天 `1152` 期结束
- 在 live/dashboard 对齐时，曾出现“同日逐笔翻倍”和“1-2-4-8-16”错误实现，后续已经统一修正回：
  - 日级马丁 `1-2-4-5`
  - 同一交易日所有和值槽位共用同一日档位
- 后续又按你的要求把赔率统一改成扣本金后的净赢档 `41 / 20 / 12 / 10 / 7.5`

### 3.3 定位胆冻结依据

定位胆线最终冻结为 `late|big|edge_low|same_top1_prev=all + obs=192 + front_pair_major_consensus_only`，依据是：

- 早期整合时一度误接到了 `center + singleton_exact_q75` 规则，导致四玩法联动结论失真
- 之后根据你给出的单线对账结果回溯，确认冻结主规则应为 `edge_low + front_pair_major_consensus_only`
- 在进一步对比后发现：定位胆做马丁会显著放大风险，而固定 `10` 对组合更稳，因此 live 版固定为 `10`

## 4. 推理过程与关键决策时间线

### 4.1 初始三玩法联合回放

先完成了 `大小/单双 + 冠亚和` 的联合回放，并得到：

- `2025` 全年独立起跑
- `2026-01-01 -> 2026-04-12` 独立起跑
- 承接 `2025` 年末资金的连续资金曲线
- 全量公共区间 `2025-01-06 -> 2026-04-12` 的总利润

这一阶段明确了两个和值版本：

- 稳健版：`intraday_1007`
- 进攻版：`intraday_1037`

### 4.2 明确“窗口期”的时间语义

后续把“窗口期”拆成了两类：

- 周/日级的可执行窗口
- 日内前缀判窗

关键结论：

- `冠亚和`：前 `192` 期结束后判窗，当天后续才决定是否做
- `定位胆`：同样不是全天收盘才知道，而是围绕 `obs=192` 的日内前缀切点来做晚段固定槽位
- `双面`：不是等当天日内走势，而是靠前视历史、rolling gate、cooldown 决定当日 `cash/active`

### 4.3 加入定位胆并纠正规则接错问题

把 `定位胆` 纳入联合推演后，最开始接错了规则，导致和其它线程对不上。随后完成了两件事：

- 把 `定位胆` 改回冻结主规则 `edge_low + consensus`
- 重新与 `双面`、`冠亚和` 做共享资金池对齐

这一步确认：

- 旧的 `four_play_*exactdw_001*` 结果应作废
- 对齐后的组合才是可继续部署和讨论的版本

### 4.4 定位胆风险重评估

在 `2025-01-01 -> 2026-01-01` 的黑名单口径回放中，进一步对比了：

- `定位胆单线固定注`
- `定位胆单线马丁`
- `共享池里带定位胆`
- `共享池里去掉定位胆`
- `共享池里定位胆改回固定10`

最终结论是：

- 定位胆单线并不强
- 在共享池里如果也做马丁，会显著增加资金压力
- 固定 `10` 明显优于马丁版
- 因此 live 面板采用：`face/sum` 做马丁，`定位胆` 固定注

### 4.5 实时 dashboard 部署

随后把整套策略部署到 `ssh tengxun`：

- 后端：FastAPI + 轮询 + SSE
- 前端：Vite React 中文仪表盘
- 反代：nginx `:5173`
- 托管：pm2
- 数据源：Docker MySQL + 两个 PK10 API

后续又做了多轮语义修正，包括：

- 页面中文文案统一：`双面 / 冠亚和 / 定位胆`
- 投注历史分页、表头、开奖号码、开奖时间
- 播报记录支持按期开奖号搜索
- 修复 `冠亚和` 和 `定位胆` 历史期号错挂问题
- 把播报历史从“状态快照流”改造成“真实可投注指令流”

### 4.6 最新起算口径调整

最近一次调整把 live 面板改成两段式：

- 窗口预热：`2026-01-01`
- 模拟投注：`2026-04-01`

含义是：

- `2026-01-01 ~ 2026-03-31` 只用于重建窗口、冷却、马丁上下文
- 不计入模拟资金曲线
- `2026-04-01` 才作为真钱模拟起点，初始资金重新从 `1000` 起跑

## 5. 当前线上结构说明

### 5.1 系统职责拆分

- `strategy.py`：所有玩法的上下文构建、窗口判断、下注清单、共享资金池回放
- `runtime.py`：轮询数据库/API、刷新快照、写入日表/投注/播报日志
- `main.py`：对外 API 与分页接口
- `App.jsx`：前端仪表盘、曲线、投注历史、播报历史

### 5.2 当前日志语义

- `pk10_bet_log`：投注账本；既能展示已播报执行，也能展示当天还未触发的未来待执行单
- `pk10_broadcast_log`：只保留**真实可投注播报**，不再记录“窗口开启/空仓/无票”状态快照
- `pk10_daily_equity`：按模拟起点裁剪后的日维资金曲线
- `pk10_runtime_state`：当前快照、资金、状态、最新期号

## 6. 归档范围

本文件直接内嵌以下源码：

- live dashboard README
- backend 源码与部署配置
- frontend 源码
- round36 系列核心回放脚本
- 本线程共享记忆文件

## 7. 工程源码附录


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/README.md`

```markdown
# PK10 Live Dashboard

部署目标：

- 后端：`FastAPI`，监听 `127.0.0.1:18080`
- 前端：`Vite React`，最终由 `nginx` 直接服务
- 公网入口：`http://<host>:5173`
- 权限：`Basic Auth`
- 进程托管：`pm2`
- 静态目录建议发布到：`/var/www/pk10-live`
- Basic Auth 文件建议放到：`/etc/nginx/pk10-live.htpasswd`

核心冻结口径：

- `face`: `core40_spread_only__exp0_off__oe40_spread_only__cd2`
- `sum`: `intraday_1037`
- `exact`: `late|big|edge_low|same_top1_prev=all + obs=192 + front_pair_major_consensus_only`
- 资金池：`1000 / 10 / shared bankroll`
- `face/sum`: 马丁 `1-2-4-5`
- `exact`: 固定 `10`
- blackout: `06:00-07:00`

主要路径：

- 后端入口：`backend/app/main.py`
- 前端入口：`frontend/src/App.jsx`
- pm2 配置：`deploy/ecosystem.config.cjs`
- nginx 配置：`deploy/pk10.nginx.conf`
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/backend/requirements.txt`

```text
fastapi==0.116.1
uvicorn[standard]==0.35.0
pymysql==1.1.1
pandas==2.3.1
numpy==2.3.2
requests==2.32.4
python-dotenv==1.1.1
cryptography==45.0.6
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/backend/app/__init__.py`

```python
"""PK10 live dashboard backend package."""
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/backend/app/settings.py`

```python
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
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/backend/app/db.py`

```python
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
            line_name VARCHAR(32) NOT NULL,
            actionable TINYINT(1) NOT NULL DEFAULT 0,
            payload_json JSON NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/backend/app/strategy.py`

```python
from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from datetime import time
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .db import query_df
from .settings import settings


NEGATIVE_DISCOUNT = 0.85
SUM_NET_ODDS = (
    41.0,
    41.0,
    20.0,
    20.0,
    12.0,
    12.0,
    10.0,
    10.0,
    7.5,
    10.0,
    10.0,
    12.0,
    12.0,
    20.0,
    20.0,
    41.0,
    41.0,
)


def next_multiplier(current: int, max_multiplier: int, last_real_pnl: float) -> int:
    if last_real_pnl < 0.0:
        if current < 2:
            return min(2, max_multiplier)
        if current < 4:
            return min(4, max_multiplier)
        return min(5, max_multiplier)
    return 1


def settle_real(book_pnl_units: float) -> float:
    return float(book_pnl_units if book_pnl_units >= 0.0 else book_pnl_units * NEGATIVE_DISCOUNT)


def daily85(book_pnl_units: float) -> float:
    return settle_real(book_pnl_units)


def martingale_double_ladder(level_count: int) -> tuple[int, ...]:
    max_multiplier = max(1, int(level_count))
    ladder = [1]
    while ladder[-1] < max_multiplier:
        ladder.append(min(ladder[-1] * 2, max_multiplier))
    return tuple(ladder)


def next_ladder_multiplier(current: int, ladder: tuple[int, ...], last_real_pnl: float) -> int:
    if not ladder:
        return 1
    if last_real_pnl >= 0.0:
        return int(ladder[0])
    if current in ladder:
        index = ladder.index(current)
    else:
        index = 0
    return int(ladder[min(index + 1, len(ladder) - 1)])


def sum_net_odds_for_index(sum_index: int) -> float:
    return float(SUM_NET_ODDS[int(sum_index)])


def sum_net_odds_for_value(sum_value: int) -> float:
    return sum_net_odds_for_index(int(sum_value) - 3)


def sum_book_units(sum_index: int, hit: int | bool) -> float:
    return float(sum_net_odds_for_index(sum_index) if int(hit) == 1 else -1.0)


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class StrategyModules:
    round9: Any
    round16: Any
    round35: Any
    sum_vmod: Any
    sum_rmod: Any
    sum_intraday: Any
    number_window: Any
    source_root: Path

    @classmethod
    def load(cls, source_root: Path) -> "StrategyModules":
        number_dir = source_root / "tmp_number_validation"
        if str(number_dir) not in sys.path:
            sys.path.insert(0, str(number_dir))
        return cls(
            round9=import_module(
                source_root / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py",
                "pk10_live_round9",
            ),
            round16=import_module(
                source_root / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py",
                "pk10_live_round16",
            ),
            round35=import_module(
                source_root / "pk10_round35_daily_deployment_refinement" / "pk10_round35_daily_deployment_refinement.py",
                "pk10_live_round35",
            ),
            sum_vmod=import_module(
                source_root / "pk10_number_sum_validation" / "pk10_number_sum_validation.py",
                "pk10_live_sum_validation",
            ),
            sum_rmod=import_module(
                source_root / "pk10_number_sum_validation" / "pk10_number_sum_refinement.py",
                "pk10_live_sum_refinement",
            ),
            sum_intraday=import_module(
                source_root / "pk10_number_sum_validation" / "pk10_number_sum_intraday_gate.py",
                "pk10_live_sum_intraday",
            ),
            number_window=import_module(
                source_root / "tmp_number_validation" / "pk10_number_daily_window_validation.py",
                "pk10_live_number_window",
            ),
            source_root=source_root,
        )


@dataclass
class ReplayResult:
    daily_df: pd.DataFrame
    summary: dict[str, Any]
    end_bankroll: float
    end_face_multiplier: int
    end_sum_multiplier: int
    peak_bankroll: float
    min_bankroll: float
    max_drawdown: float
    sum_bet_rows: list[dict[str, Any]]


def parse_time_of_day(text: str | None) -> time | None:
    value = str(text or "").strip()
    if not value:
        return None
    return pd.Timestamp(f"2000-01-01 {value}").time()


def mysql_position_expr(position: int) -> str:
    return (
        "CAST("
        f"SUBSTRING_INDEX(SUBSTRING_INDEX(pre_draw_code, ',', {position}), ',', -1)"
        " AS UNSIGNED)"
    )


def load_issue_history_from_db(date_start: str, date_end: str | None = None) -> pd.DataFrame:
    filters = ["pre_draw_code IS NOT NULL", "pre_draw_code <> ''", f"draw_date >= '{date_start}'"]
    if date_end:
        filters.append(f"draw_date <= '{date_end}'")
    pos_cols = ",\n        ".join(f"{mysql_position_expr(i)} AS pos{i}" for i in range(1, 11))
    sql = f"""
    SELECT
        DATE_FORMAT(draw_date, '%Y-%m-%d') AS draw_date,
        DATE_FORMAT(pre_draw_time, '%Y-%m-%d %H:%i:%s') AS pre_draw_time,
        pre_draw_issue,
        {pos_cols}
    FROM {settings.db_table}
    WHERE {' AND '.join(filters)}
    ORDER BY draw_date, pre_draw_time, pre_draw_issue
    """
    df = query_df(sql)
    if df.empty:
        return df
    df["draw_date"] = pd.to_datetime(df["draw_date"])
    df["pre_draw_time"] = pd.to_datetime(df["pre_draw_time"])
    df["pre_draw_issue"] = df["pre_draw_issue"].astype(np.int64)
    for idx in range(1, 11):
        df[f"pos{idx}"] = df[f"pos{idx}"].astype(np.uint8)
    return df


def normalize_issue_df(issue_df: pd.DataFrame) -> pd.DataFrame:
    work = issue_df.copy()
    work["draw_date"] = pd.to_datetime(work["draw_date"]).dt.normalize()
    if "pre_draw_time" in work.columns:
        work["draw_ts"] = pd.to_datetime(work["pre_draw_time"])
    else:
        work["draw_ts"] = pd.to_datetime(work["draw_date"])
    work = work.sort_values(["draw_date", "draw_ts", "pre_draw_issue"]).reset_index(drop=True)
    return work


def build_schedule_frame(issue_df: pd.DataFrame) -> pd.DataFrame:
    work = normalize_issue_df(issue_df)
    work["slot_1based"] = work.groupby("draw_date").cumcount() + 1
    return work[
        [
            "draw_date",
            "draw_ts",
            "pre_draw_issue",
            "slot_1based",
        ]
    ].copy()


def filter_blackout(issue_df: pd.DataFrame, blackout_start: time | None, blackout_end: time | None) -> pd.DataFrame:
    if blackout_start is None or blackout_end is None:
        return normalize_issue_df(issue_df)
    work = normalize_issue_df(issue_df)
    time_values = work["draw_ts"].dt.time
    return work.loc[~((time_values >= blackout_start) & (time_values < blackout_end))].reset_index(drop=True)


def _extended_week_meta(work: pd.DataFrame) -> tuple[pd.DataFrame, int, pd.DataFrame]:
    if work.empty:
        raise RuntimeError("No rows available for extended-week preprocessing")
    day_counts = work.groupby("draw_date").size().sort_index()
    expected_per_day = int(day_counts.mode().iloc[0])
    last_date = pd.Timestamp(day_counts.index.max())
    keep_dates = set(day_counts[day_counts == expected_per_day].index.tolist())
    keep_dates.add(last_date)
    work = work[work["draw_date"].isin(keep_dates)].copy()
    work["issue_idx_in_day"] = work.groupby("draw_date").cumcount()
    iso = work["draw_date"].dt.isocalendar()
    work["iso_year"] = iso["year"].astype(int)
    work["iso_week"] = iso["week"].astype(int)
    work["week_id"] = work["iso_year"].astype(str) + "-W" + work["iso_week"].astype(str).str.zfill(2)
    week_days = work.groupby("week_id")["draw_date"].nunique()
    complete_week_ids = set(week_days[week_days == 7].index.tolist())
    ordered = (
        work.groupby("week_id", sort=True)["draw_date"]
        .agg(["min", "max", "nunique"])
        .rename(columns={"min": "first_date", "max": "last_date", "nunique": "n_days"})
        .reset_index()
        .sort_values("first_date")
        .reset_index(drop=True)
    )
    keep_week_ids = [wid for wid in ordered["week_id"].tolist() if wid in complete_week_ids]
    tail_week_id = str(ordered.iloc[-1]["week_id"])
    if tail_week_id not in keep_week_ids:
        keep_week_ids.append(tail_week_id)
    ordered = ordered[ordered["week_id"].isin(keep_week_ids)].copy().reset_index(drop=True)
    ordered["week_start"] = ordered["first_date"] - pd.to_timedelta(ordered["first_date"].dt.weekday, unit="D")
    ordered["week_end"] = ordered["week_start"] + pd.Timedelta(days=6)
    work = work[work["week_id"].isin(keep_week_ids)].copy()
    work["week_id"] = pd.Categorical(work["week_id"], categories=ordered["week_id"].tolist(), ordered=True)
    work = work.sort_values(["week_id", "draw_date", "issue_idx_in_day"]).reset_index(drop=True)
    return work, expected_per_day, ordered[["week_id", "week_start", "week_end"]].copy()


def _fill_extended_cube(
    work: pd.DataFrame,
    expected_per_day: int,
    week_meta: pd.DataFrame,
    value_columns: list[str],
    dtype: Any,
) -> tuple[np.ndarray, np.ndarray]:
    tail_shape = (len(value_columns),) if len(value_columns) > 1 else ()
    shape = (len(week_meta), 7, expected_per_day) + tail_shape
    cube = np.zeros(shape, dtype=dtype)
    mask = np.zeros((len(week_meta), 7, expected_per_day), dtype=bool)
    week_lookup = {str(row.week_id): idx for idx, row in week_meta.iterrows()}
    values = work[value_columns].to_numpy(dtype=dtype)
    for row_idx, row in enumerate(work.itertuples(index=False)):
        week_idx = week_lookup[str(row.week_id)]
        day_idx = int((pd.Timestamp(row.draw_date) - pd.Timestamp(week_meta.iloc[week_idx]["week_start"])).days)
        slot_idx = int(row.issue_idx_in_day)
        if day_idx < 0 or day_idx >= 7 or slot_idx < 0 or slot_idx >= expected_per_day:
            continue
        mask[week_idx, day_idx, slot_idx] = True
        if len(value_columns) == 1:
            cube[week_idx, day_idx, slot_idx] = values[row_idx][0]
        else:
            cube[week_idx, day_idx, slot_idx, :] = values[row_idx]
    return cube, mask


def build_extended_face_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = filter_blackout(issue_df, parse_time_of_day(settings.blackout_start), parse_time_of_day(settings.blackout_end))
    pos_cols = [f"pos{i}" for i in range(1, 11)]
    big_cols = [f"is_big_{i}" for i in range(1, 11)]
    work[big_cols] = (work[pos_cols].to_numpy(dtype=np.uint8) >= 6).astype(np.uint8)
    work["big_count"] = work[big_cols].sum(axis=1)
    work = work[work["big_count"] == 5].copy()
    work, expected_per_day, week_meta = _extended_week_meta(work)
    big_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, big_cols, np.uint8)
    weekly_exact_counts = big_cube.sum(axis=1).astype(np.uint16)
    slot_to_decile = ((np.arange(expected_per_day) * 10) // expected_per_day).astype(np.int8)
    weekly_decile_counts = np.zeros((len(week_meta), 10, 10), dtype=np.uint16)
    exposures_decile = np.zeros(10, dtype=np.uint16)
    for decile in range(10):
        slot_selector = slot_to_decile == decile
        exposures_decile[decile] = int(slot_selector.sum() * 7)
        weekly_decile_counts[:, decile, :] = weekly_exact_counts[:, slot_selector, :].sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    train_mask = week_end <= np.datetime64(mods.round9.TRAIN_END)
    test_mask = week_start >= np.datetime64(mods.round9.TEST_START)
    if bool(train_mask.any()):
        position_train_rates = big_cube[train_mask].mean(axis=(0, 1, 2))
    else:
        position_train_rates = big_cube.mean(axis=(0, 1, 2))
    desc = np.argsort(-position_train_rates)
    asc = np.argsort(position_train_rates)
    bundle = mods.round9.DatasetBundle(
        big_cube=big_cube,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        slot_to_decile=slot_to_decile,
        weekly_exact_counts=weekly_exact_counts,
        weekly_decile_counts=weekly_decile_counts,
        exposures_exact=np.full(expected_per_day, 7, dtype=np.uint16),
        exposures_decile=exposures_decile,
        train_mask_fixed_split=train_mask,
        test_mask_fixed_split=test_mask,
        static_pair_big_pos=int(desc[0]),
        static_pair_small_pos=int(asc[0]),
    )
    return bundle, slot_mask, build_schedule_frame(work)


def build_extended_odd_even_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = filter_blackout(issue_df, parse_time_of_day(settings.blackout_start), parse_time_of_day(settings.blackout_end))
    pos_cols = [f"pos{i}" for i in range(1, 11)]
    odd_cols = [f"is_odd_{i}" for i in range(1, 11)]
    work[odd_cols] = (work[pos_cols].to_numpy(dtype=np.uint8) % 2 == 1).astype(np.uint8)
    work["odd_count"] = work[odd_cols].sum(axis=1)
    work = work[work["odd_count"] == 5].copy()
    work, expected_per_day, week_meta = _extended_week_meta(work)
    odd_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, odd_cols, np.uint8)
    weekly_exact_counts = odd_cube.sum(axis=1).astype(np.uint16)
    slot_to_decile = ((np.arange(expected_per_day) * 10) // expected_per_day).astype(np.int8)
    weekly_decile_counts = np.zeros((len(week_meta), 10, 10), dtype=np.uint16)
    exposures_decile = np.zeros(10, dtype=np.uint16)
    for decile in range(10):
        slot_selector = slot_to_decile == decile
        exposures_decile[decile] = int(slot_selector.sum() * 7)
        weekly_decile_counts[:, decile, :] = weekly_exact_counts[:, slot_selector, :].sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    train_mask = week_end <= np.datetime64(mods.round16.TRAIN_END)
    test_mask = week_start >= np.datetime64(mods.round16.TEST_START)
    if bool(train_mask.any()):
        position_train_rates = odd_cube[train_mask].mean(axis=(0, 1, 2))
    else:
        position_train_rates = odd_cube.mean(axis=(0, 1, 2))
    desc = np.argsort(-position_train_rates)
    asc = np.argsort(position_train_rates)
    bundle = mods.round9.DatasetBundle(
        big_cube=odd_cube,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        slot_to_decile=slot_to_decile,
        weekly_exact_counts=weekly_exact_counts,
        weekly_decile_counts=weekly_decile_counts,
        exposures_exact=np.full(expected_per_day, 7, dtype=np.uint16),
        exposures_decile=exposures_decile,
        train_mask_fixed_split=train_mask,
        test_mask_fixed_split=test_mask,
        static_pair_big_pos=int(desc[0]),
        static_pair_small_pos=int(asc[0]),
    )
    return bundle, slot_mask, build_schedule_frame(work)


def build_extended_sum_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = normalize_issue_df(issue_df)
    work["sum_value"] = (work["pos1"].astype(np.uint8) + work["pos2"].astype(np.uint8)).astype(np.uint8)
    work["sum_idx"] = (work["sum_value"] - 3).astype(np.uint8)
    work, expected_per_day, week_meta = _extended_week_meta(work)
    sum_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, ["sum_idx"], np.uint8)
    weekly_sum_counts = np.zeros((len(week_meta), expected_per_day, 17), dtype=np.uint16)
    for sum_index in range(17):
        weekly_sum_counts[:, :, sum_index] = (sum_cube == sum_index).sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    bundle = mods.sum_vmod.SumBundle(
        sum_cube=sum_cube,
        weekly_sum_counts=weekly_sum_counts,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        train_mask_fixed_split=week_end <= np.datetime64(mods.sum_vmod.TRAIN_END),
        test_mask_fixed_split=week_start >= np.datetime64(mods.sum_vmod.TEST_START),
        raw_rows=int(len(work)),
        complete_rows=int(len(work)),
        expected_per_day=expected_per_day,
        complete_days=int(work["draw_date"].nunique()),
        sample_min_date=str(work["draw_date"].min().date()),
        sample_max_date=str(work["draw_date"].max().date()),
    )
    return bundle, slot_mask, build_schedule_frame(work)


def build_extended_number_bundle(mods: StrategyModules, issue_df: pd.DataFrame):
    work = normalize_issue_df(issue_df)
    pos_cols = [f"pos{i}" for i in range(1, 11)]
    work["big_count"] = (work[pos_cols].to_numpy(dtype=np.uint8) >= 6).sum(axis=1)
    work = work[work["big_count"] == 5].copy()
    work, expected_per_day, week_meta = _extended_week_meta(work)
    number_cube, slot_mask = _fill_extended_cube(work, expected_per_day, week_meta, pos_cols, np.uint8)
    big_cube = (number_cube >= 6).astype(np.uint8)
    weekly_exact_counts = big_cube.sum(axis=1).astype(np.uint16)
    slot_to_decile = ((np.arange(expected_per_day) * 10) // expected_per_day).astype(np.int8)
    weekly_decile_counts = np.zeros((len(week_meta), 10, 10), dtype=np.uint16)
    exposures_decile = np.zeros(10, dtype=np.uint16)
    for decile in range(10):
        slot_selector = slot_to_decile == decile
        exposures_decile[decile] = int(slot_selector.sum() * 7)
        weekly_decile_counts[:, decile, :] = weekly_exact_counts[:, slot_selector, :].sum(axis=1)
    week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    week_end = week_meta["week_end"].to_numpy(dtype="datetime64[ns]")
    train_mask = week_end <= np.datetime64(mods.round9.TRAIN_END)
    test_mask = week_start >= np.datetime64(mods.round9.TEST_START)
    if bool(train_mask.any()):
        position_train_rates = big_cube[train_mask].mean(axis=(0, 1, 2))
    else:
        position_train_rates = big_cube.mean(axis=(0, 1, 2))
    desc = np.argsort(-position_train_rates)
    asc = np.argsort(position_train_rates)
    weekly_number_counts = np.zeros((len(week_meta), expected_per_day, 10, 10), dtype=np.uint8)
    for number in range(1, 11):
        weekly_number_counts[..., number - 1] = (number_cube == number).sum(axis=1).astype(np.uint8)
    round9_bundle = mods.round9.DatasetBundle(
        big_cube=big_cube,
        week_ids=week_meta["week_id"].to_numpy(dtype=object),
        week_start=week_start,
        week_end=week_end,
        week_labels=week_meta["week_start"].dt.strftime("%Y-%m-%d").to_numpy(dtype=object),
        n_slots=expected_per_day,
        slot_to_decile=slot_to_decile,
        weekly_exact_counts=weekly_exact_counts,
        weekly_decile_counts=weekly_decile_counts,
        exposures_exact=np.full(expected_per_day, 7, dtype=np.uint16),
        exposures_decile=exposures_decile,
        train_mask_fixed_split=train_mask,
        test_mask_fixed_split=test_mask,
        static_pair_big_pos=int(desc[0]),
        static_pair_small_pos=int(asc[0]),
    )
    bundle = mods.number_window.NumberBundle(
        round9_bundle=round9_bundle,
        number_cube=number_cube,
        weekly_number_counts=weekly_number_counts,
    )
    return bundle, slot_mask, build_schedule_frame(work)


def load_sum_candidate_row(mods: StrategyModules, candidate_id: str) -> pd.Series:
    paths = (
        mods.source_root
        / "pk10_number_sum_validation"
        / "number_sum_intraday_gate_outputs_local_pks_3306_20260417"
        / "intraday_gate_summary.csv",
        mods.source_root
        / "pk10_number_sum_validation"
        / "number_sum_intraday_gate_outputs_db6y_daily85"
        / "intraday_gate_summary.csv",
    )
    for path in paths:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        matched = df[df["candidate_id"] == candidate_id].copy()
        if not matched.empty:
            return matched.iloc[0]
    raise RuntimeError(f"Missing sum candidate row: {candidate_id}")


def gate_is_on(day_row: pd.Series | dict[str, Any], candidate_row: pd.Series) -> bool:
    requested_slots = float(day_row["requested_slots"])
    if requested_slots <= 0.0:
        return False
    if float(day_row["selected_mean_edge"]) > float(candidate_row["mean_edge_cap"]):
        return False
    gate_family = str(candidate_row["gate_family"])
    raw_high = float(day_row["preview_raw_high_bias"])
    mid_share = float(day_row["preview_mid_share"])
    mean_sum = float(day_row["preview_mean_sum"])
    if gate_family == "high_only":
        return raw_high >= float(candidate_row["raw_high_threshold"])
    if gate_family == "high_mean":
        return raw_high >= float(candidate_row["raw_high_threshold"]) and mean_sum >= float(candidate_row["mean_sum_threshold"])
    if gate_family == "high_mid":
        return raw_high >= float(candidate_row["raw_high_threshold"]) and mid_share >= float(candidate_row["mid_share_threshold"])
    if gate_family == "mid_only":
        return mid_share >= float(candidate_row["mid_share_threshold"])
    raise ValueError(f"Unknown gate family: {gate_family}")


def face_mode_components(mode: str) -> tuple[str, ...]:
    if mode == "core":
        return ("core",)
    if mode == "core_plus_expansion":
        return ("core", "exp")
    if mode == "core_plus_oe":
        return ("core", "oe")
    if mode == "core_plus_expansion_plus_oe":
        return ("core", "exp", "oe")
    return tuple()


def face_payload_ticket_count(payload: dict[str, Any]) -> int:
    big_n = len(payload["big_positions"])
    small_n = len(payload["small_positions"])
    if big_n == 1 and small_n == 1:
        return 2
    return 4


def face_payload_book_units(issue_row: pd.Series | dict[str, Any], payload: dict[str, Any]) -> tuple[float, int, str]:
    numbers = np.array([int(issue_row[f"pos{i}"]) for i in range(1, 11)], dtype=np.int16)
    big_flags = (numbers >= 6).astype(np.int16)
    big_positions = [int(x) - 1 for x in payload["big_positions"]]
    small_positions = [int(x) - 1 for x in payload["small_positions"]]
    if len(big_positions) == 1 and len(small_positions) == 1:
        top = int(big_flags[big_positions[0]])
        bottom = int(big_flags[small_positions[0]])
        ledger = float((1995 * (top + 1 - bottom) - 2000) / 1000.0)
        hits = int(top + (1 - bottom))
        label = "双中" if hits == 2 else ("单中" if hits == 1 else "双失")
        return ledger, hits, label
    top = big_flags[big_positions]
    bottom = big_flags[small_positions]
    hits = int(top.sum() + (len(small_positions) - bottom.sum()))
    ledger = float((1995 * hits - 4000) / 1000.0)
    label = f"{hits}/4中"
    return ledger, hits, label


def schedule_maps(schedule_df: pd.DataFrame) -> dict[str, dict[int, dict[str, Any]]]:
    out: dict[str, dict[int, dict[str, Any]]] = {}
    if schedule_df.empty:
        return out
    work = schedule_df.copy()
    work["date_key"] = pd.to_datetime(work["draw_date"]).dt.strftime("%Y-%m-%d")
    for day, group in work.groupby("date_key", sort=False):
        out[day] = {
            int(row.slot_1based): {
                "issue": int(row.pre_draw_issue),
                "draw_ts": pd.Timestamp(row.draw_ts),
            }
            for row in group.itertuples(index=False)
        }
    return out


def build_face_context(mods: StrategyModules, issue_df: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, Any]:
    bundle, _slot_mask, schedule_df = build_extended_face_bundle(mods, issue_df)
    round9 = mods.round9
    round16 = mods.round16
    round35 = mods.round35
    bs_core = round35.make_candidate(
        round9,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=15,
        gap_threshold=0.0125,
    )
    bs_exp = round35.make_candidate(
        round9,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=18,
        gap_threshold=0.0025,
    )
    bs_signal_states, bs_uniform, bs_balanced = round35.build_signal_states(round9, bundle, [bs_core, bs_exp])
    bs_core_series = round9.evaluate_candidate_series(bs_core, bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9.evaluate_candidate_series(bs_exp, bundle, bs_signal_states, bs_uniform, bs_balanced)
    round9.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle, _oe_mask, _oe_schedule = build_extended_odd_even_bundle(mods, issue_df)
    oe_cfg = round35.make_candidate(
        round9,
        line_name="odd_even_oemap47_gated",
        strategy_family="quartet_fixed_map",
        map_name="OEMAP_47_vs_29",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=10,
        gap_threshold=0.0025,
    )
    oe_signal_states, oe_uniform, oe_balanced = round35.build_signal_states(round9, oe_bundle, [oe_cfg])
    oe_series = round9.evaluate_candidate_series(oe_cfg, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    week_starts = [pd.Timestamp(x).strftime("%Y-%m-%d") for x in pd.to_datetime(bundle.week_start)]
    core_daily = round35.build_component_daily(bundle, bs_core_series, week_starts, "core")
    exp_daily = round35.build_component_daily(bundle, bs_exp_series, week_starts, "exp")
    oe_daily = round35.build_component_daily(oe_bundle, oe_series, week_starts, "oe")

    df = core_daily[
        ["week_start", "date", "day_index_in_week", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]
    ].rename(
        columns={
            "daily_ledger_unit": "core_ledger_unit",
            "daily_bets": "core_bets",
            "daily_implied_spread": "core_implied_spread",
        }
    )
    df = df.merge(
        exp_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={
                "daily_ledger_unit": "exp_ledger_unit",
                "daily_bets": "exp_bets",
                "daily_implied_spread": "exp_implied_spread",
            }
        ),
        on="date",
        how="left",
    )
    df = df.merge(
        oe_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={
                "daily_ledger_unit": "oe_ledger_unit",
                "daily_bets": "oe_bets",
                "daily_implied_spread": "oe_implied_spread",
            }
        ),
        on="date",
        how="left",
    )
    df = df.fillna(0.0)
    df["day_index"] = range(1, len(df) + 1)
    trace = round35.simulate_policy(
        df=df,
        policy_id=settings.face_policy_id,
        core_cfg=(40, "spread_only"),
        exp_cfg=(0, "off"),
        oe_cfg=(40, "spread_only"),
        cooldown_days=2,
    )[1]
    trace["date"] = pd.to_datetime(trace["date"])
    trace["face_base_real_pnl"] = trace["policy_real_unit"].astype(float) * float(settings.base_stake)
    series_map = {"core": bs_core_series, "exp": bs_exp_series, "oe": oe_series}
    plan_by_date: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for week_idx, week_start in enumerate(pd.to_datetime(bundle.week_start)):
        week_key = pd.Timestamp(week_start).strftime("%Y-%m-%d")
        for day_offset in range(7):
            date_key = (pd.Timestamp(week_start) + pd.Timedelta(days=day_offset)).strftime("%Y-%m-%d")
            plan_by_date.setdefault(date_key, {"core": [], "exp": [], "oe": []})
            for source_name, series in series_map.items():
                payloads = series["selected_positions_meta"][week_idx]
                if payloads is None:
                    continue
                items: list[dict[str, Any]] = []
                for slot, big_positions, small_positions in payloads:
                    items.append(
                        {
                            "source": source_name,
                            "slot_1based": int(slot) + 1,
                            "big_positions": list(big_positions),
                            "small_positions": list(small_positions),
                            "ticket_count": 2 if len(big_positions) == 1 and len(small_positions) == 1 else 4,
                            "odds_display": (
                                "双面双票 | 双中 +1.99 | 单中 -0.01 | 双失 -2.00"
                                if len(big_positions) == 1 and len(small_positions) == 1
                                else "双面四票 | 4中 +3.98 | 3中 +1.99 | 2中 -0.01 | 1中 -2.00 | 0中 -4.00"
                            ),
                        }
                    )
                plan_by_date[date_key][source_name] = items
    return {
        "trace_df": trace,
        "plan_by_date": plan_by_date,
        "schedule_df": schedule_df,
        "schedule_map": schedule_maps(schedule_df),
        "current_date": current_date.strftime("%Y-%m-%d"),
    }


def build_sum_context(mods: StrategyModules, issue_df: pd.DataFrame) -> dict[str, Any]:
    bundle, _slot_mask, schedule_df = build_extended_sum_bundle(mods, issue_df)
    candidate_row = load_sum_candidate_row(mods, settings.sum_candidate_id)
    baseline_lookup = {cfg.name: cfg for cfg in mods.sum_intraday.baseline_configs()}
    baseline = baseline_lookup[str(candidate_row["baseline_name"])]
    preview_cut = int(candidate_row["preview_cut"])
    base_series, detail_df = mods.sum_intraday.build_intraday_base_series(
        mods.sum_vmod,
        mods.sum_rmod,
        bundle,
        baseline,
        preview_cut,
    )
    if detail_df.empty or "date" not in detail_df.columns:
        raw_schedule = build_schedule_frame(issue_df)
        return {
            "bundle": bundle,
            "candidate_row": candidate_row,
            "grouped": pd.DataFrame(
                columns=[
                    "date",
                    "split",
                    "requested_slots",
                    "selected_score",
                    "selected_mean_edge",
                    "selected_symmetry_gap",
                    "preview_raw_high_bias",
                    "preview_mid_share",
                    "preview_mean_sum",
                    "sum_active",
                ]
            ),
            "picks_by_date": {},
            "schedule_df": raw_schedule,
            "schedule_map": schedule_maps(raw_schedule),
            "baseline": baseline,
            "choice_state": mods.sum_rmod.build_choice_state(
                mods.sum_vmod,
                mods.sum_rmod.build_full_signal_state(
                    vmod=mods.sum_vmod,
                    bundle=bundle,
                    lookback_weeks=baseline.lookback_weeks,
                    prior_strength=baseline.prior_strength,
                    score_mode=baseline.score_mode,
                ),
                baseline.allowed_sums,
            ),
            "preview_cut": preview_cut,
        }
    detail_df["date"] = pd.to_datetime(detail_df["date"])
    raw_schedule = build_schedule_frame(issue_df)
    blackout_start = parse_time_of_day(settings.blackout_start)
    blackout_end = parse_time_of_day(settings.blackout_end)
    raw_schedule["allowed_trade"] = True
    if blackout_start and blackout_end:
        times = raw_schedule["draw_ts"].dt.time
        raw_schedule["allowed_trade"] = ~((times >= blackout_start) & (times < blackout_end))
    allowed_lookup = raw_schedule[["draw_date", "slot_1based", "allowed_trade"]].rename(columns={"draw_date": "date"})
    allowed_detail = detail_df.merge(allowed_lookup, left_on=["date", "slot"], right_on=["date", "slot_1based"], how="left")
    allowed_detail["allowed_trade"] = allowed_detail["allowed_trade"].fillna(True).astype(bool)
    allowed_detail = allowed_detail[allowed_detail["allowed_trade"]].copy()
    allowed_detail["sum_value"] = allowed_detail["sum_value"].astype(int)
    allowed_detail["hit"] = allowed_detail["hit"].astype(int)
    allowed_detail["book_pnl"] = np.where(
        allowed_detail["hit"] == 1,
        allowed_detail["sum_value"].map(lambda value: sum_net_odds_for_value(int(value))),
        -1.0,
    )
    allowed_detail["real_pnl"] = allowed_detail["book_pnl"].map(settle_real)
    preview_grouped = (
        detail_df.groupby(["date", "split"], as_index=False)
        .agg(
            selected_score=("score_value", "mean"),
            selected_mean_edge=("mean_edge_value", "mean"),
            selected_symmetry_gap=("symmetry_gap_value", "mean"),
            preview_raw_high_bias=("preview_raw_high_bias", "mean"),
            preview_mid_share=("preview_mid_share", "mean"),
            preview_mean_sum=("preview_mean_sum", "mean"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    allowed_counts = (
        allowed_detail.groupby(["date", "split"], as_index=False)
        .agg(requested_slots=("slot", "size"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    grouped = preview_grouped.merge(allowed_counts, on=["date", "split"], how="left")
    grouped["requested_slots"] = grouped["requested_slots"].fillna(0).astype(int)
    grouped["sum_active"] = grouped.apply(lambda row: gate_is_on(row, candidate_row), axis=1)
    picks = allowed_detail.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in picks.groupby("date")}
    signal_state = mods.sum_rmod.build_full_signal_state(
        vmod=mods.sum_vmod,
        bundle=bundle,
        lookback_weeks=baseline.lookback_weeks,
        prior_strength=baseline.prior_strength,
        score_mode=baseline.score_mode,
    )
    choice_state = mods.sum_rmod.build_choice_state(mods.sum_vmod, signal_state, baseline.allowed_sums)
    return {
        "bundle": bundle,
        "candidate_row": candidate_row,
        "grouped": grouped,
        "picks_by_date": picks_by_date,
        "schedule_df": raw_schedule,
        "schedule_map": schedule_maps(raw_schedule),
        "baseline": baseline,
        "choice_state": choice_state,
        "preview_cut": preview_cut,
    }


def build_exact_context(mods: StrategyModules, issue_df: pd.DataFrame) -> dict[str, Any]:
    bundle, _slot_mask, schedule_df = build_extended_number_bundle(mods, issue_df)
    candidate = mods.number_window.build_dynamic_pair_candidate(mods.round9)
    counts, exposures = mods.round9.get_bucket_counts(bundle.round9_bundle, candidate.bucket_model)
    signal_state = mods.round9.compute_signal_state(
        counts=counts,
        exposures=exposures,
        lookback_weeks=candidate.lookback_weeks,
        prior_strength=candidate.prior_strength,
        score_model=candidate.score_model,
    )
    subgroup_state_df = mods.number_window.build_fixed_slot_state_tables(
        bundle=bundle,
        round9=mods.round9,
        signal_state=signal_state,
        candidate=candidate,
        late_slots=mods.number_window.parse_csv_ints(mods.number_window.DEFAULT_LATE_SLOTS),
        control_slots=mods.number_window.parse_csv_ints(mods.number_window.DEFAULT_CONTROL_SLOTS),
        half_prior_strength=mods.number_window.DEFAULT_HALF_PRIOR_STRENGTH,
    )
    front_state_df = mods.number_window.build_daily_front_state(
        bundle=bundle,
        subgroup_state_df=subgroup_state_df,
        obs_windows=mods.number_window.OBS_WINDOWS,
        round9=mods.round9,
    )
    rule_state_df = mods.number_window.build_daily_rule_state(front_state_df)
    filtered = rule_state_df[
        (rule_state_df["base_gate_id"] == settings.exact_base_gate_id)
        & (rule_state_df["obs_window"] == settings.exact_obs_window)
    ].copy()
    rule_col = f"rule_{settings.exact_execution_rule}"
    filtered["execute_exact"] = filtered[rule_col].astype(bool)
    filtered["selected_number_exec"] = filtered.apply(
        lambda row: mods.number_window.selected_number_for_rule(settings.exact_execution_rule, row),
        axis=1,
    )
    filtered["exact_hit_exec"] = (
        filtered["execute_exact"] & (filtered["target_number"] == filtered["selected_number_exec"])
    ).astype(int)
    filtered["cell_book_pnl_units"] = filtered["exact_hit_exec"].map(
        lambda hit: float(settings.exact_net_win) if int(hit) == 1 else -1.0
    )
    filtered["day_date"] = pd.to_datetime(filtered["day_date"])
    raw_schedule = build_schedule_frame(issue_df)
    blackout_start = parse_time_of_day(settings.blackout_start)
    blackout_end = parse_time_of_day(settings.blackout_end)
    raw_schedule["allowed_trade"] = True
    if blackout_start and blackout_end:
        times = raw_schedule["draw_ts"].dt.time
        raw_schedule["allowed_trade"] = ~((times >= blackout_start) & (times < blackout_end))
    active_cells = filtered[filtered["execute_exact"]].copy()
    slot_lookup = raw_schedule[["draw_date", "slot_1based", "allowed_trade"]].rename(columns={"draw_date": "day_date"})
    active_cells = active_cells.merge(slot_lookup, on=["day_date", "slot_1based"], how="left")
    active_cells["allowed_trade"] = active_cells["allowed_trade"].fillna(True).astype(bool)
    active_cells = active_cells[active_cells["allowed_trade"]].copy()
    split_frame = filtered[["day_date", "split"]].drop_duplicates().copy()
    grouped = (
        active_cells.groupby(["day_date", "split"], as_index=False)
        .agg(
            issue_exposures=("execute_exact", "sum"),
            exact_hits_count=("exact_hit_exec", "sum"),
        )
        .sort_values("day_date")
        .reset_index(drop=True)
    )
    grouped = split_frame.merge(grouped, on=["day_date", "split"], how="left")
    grouped["issue_exposures"] = grouped["issue_exposures"].fillna(0).astype(int)
    grouped["exact_hits_count"] = grouped["exact_hits_count"].fillna(0).astype(int)
    picks_by_date = {
        pd.Timestamp(day): frame.sort_values(["slot_1based"], kind="stable").reset_index(drop=True)
        for day, frame in active_cells.groupby("day_date")
    }
    return {
        "bundle": bundle,
        "grouped": grouped,
        "picks_by_date": picks_by_date,
        "schedule_df": raw_schedule,
        "schedule_map": schedule_maps(raw_schedule),
        "subgroup_state_df": subgroup_state_df,
    }


def replay_shared_bankroll(
    mods: StrategyModules,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    face_ctx: dict[str, Any],
    sum_ctx: dict[str, Any],
    exact_ctx: dict[str, Any],
) -> ReplayResult:
    date_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    face_frame = face_ctx["trace_df"]
    face_frame = face_frame[(face_frame["date"] >= sim_start) & (face_frame["date"] <= sim_end)].copy()
    sum_grouped = sum_ctx["grouped"].copy()
    sum_grouped["date"] = pd.to_datetime(sum_grouped["date"])
    exact_grouped = exact_ctx["grouped"].copy()
    exact_grouped["date"] = pd.to_datetime(exact_grouped["day_date"])

    sum_daily = date_range.merge(sum_grouped, on="date", how="left")
    sum_daily["split"] = sum_daily["split"].fillna("out_of_sample_gap")
    for col in [
        "requested_slots",
        "selected_score",
        "selected_mean_edge",
        "selected_symmetry_gap",
        "preview_raw_high_bias",
        "preview_mid_share",
        "preview_mean_sum",
    ]:
        sum_daily[col] = sum_daily[col].fillna(0.0)
    sum_daily["sum_active"] = sum_daily.apply(lambda row: gate_is_on(row, sum_ctx["candidate_row"]), axis=1)

    exact_daily = date_range.merge(
        exact_grouped[["date", "split", "issue_exposures", "exact_hits_count"]],
        on="date",
        how="left",
    )
    exact_daily["split"] = exact_daily["split"].fillna("out_of_sample_gap")
    exact_daily["issue_exposures"] = exact_daily["issue_exposures"].fillna(0).astype(int)
    exact_daily["exact_hits_count"] = exact_daily["exact_hits_count"].fillna(0).astype(int)

    combined = (
        date_range.merge(face_frame, on="date", how="left")
        .merge(sum_daily, on="date", how="left")
        .merge(exact_daily[["date", "issue_exposures", "exact_hits_count"]], on="date", how="left")
    )
    combined["mode"] = combined["mode"].fillna("cash")
    combined["face_base_real_pnl"] = combined["face_base_real_pnl"].fillna(0.0)
    combined["policy_bets"] = combined["policy_bets"].fillna(0.0)
    combined["issue_exposures"] = combined["issue_exposures"].fillna(0).astype(int)
    combined["exact_hits_count"] = combined["exact_hits_count"].fillna(0).astype(int)

    bankroll = float(settings.bankroll_start)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0
    face_multiplier = 1
    sum_multiplier = 1
    rows: list[dict[str, Any]] = []
    sum_bet_rows: list[dict[str, Any]] = []

    for _, row in combined.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll
        face_active = str(row["mode"]) != "cash"
        applied_face_multiplier = face_multiplier if face_active else 0
        face_real = float(row["face_base_real_pnl"]) * applied_face_multiplier

        sum_requested_slots = int(row["requested_slots"]) if bool(row["sum_active"]) else 0
        affordable_sum_slots = max(0, int(bankroll_before // (float(settings.base_stake) * sum_multiplier))) if sum_multiplier > 0 else 0
        sum_funded_slots = min(sum_requested_slots, affordable_sum_slots)
        sum_book_units = 0.0
        sum_real = 0.0
        if sum_funded_slots > 0:
            picks = sum_ctx["picks_by_date"].get(day, pd.DataFrame()).head(sum_funded_slots).copy()
            sum_book_units = float(picks["book_pnl"].sum()) if not picks.empty else 0.0
            sum_real = settle_real(sum_book_units * sum_multiplier) * float(settings.base_stake)

        exact_requested_slots = int(row["issue_exposures"])
        affordable_exact_slots = max(0, int(bankroll_before // float(settings.base_stake)))
        exact_funded_slots = min(exact_requested_slots, affordable_exact_slots)
        exact_book_units = 0.0
        exact_real = 0.0
        if exact_funded_slots > 0:
            picks = exact_ctx["picks_by_date"].get(day, pd.DataFrame()).head(exact_funded_slots).copy()
            exact_book_units = float(picks["cell_book_pnl_units"].sum()) if not picks.empty else 0.0
            exact_real = settle_real(exact_book_units) * float(settings.base_stake)

        total_real = face_real + sum_real + exact_real
        bankroll += total_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)
        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "face_mode": str(row["mode"]),
                "face_active": face_active,
                "face_executed_bets": int(row["policy_bets"]),
                "face_multiplier": applied_face_multiplier,
                "face_real_pnl": face_real,
                "sum_active": bool(sum_requested_slots > 0),
                "sum_requested_slots": sum_requested_slots,
                "sum_affordable_slots": affordable_sum_slots,
                "sum_funded_slots": sum_funded_slots,
                "sum_multiplier": sum_multiplier if sum_requested_slots > 0 else 0,
                "sum_book_pnl_units": sum_book_units,
                "sum_real_pnl": sum_real,
                "exact_active": bool(exact_requested_slots > 0),
                "exact_requested_slots": exact_requested_slots,
                "exact_affordable_slots": affordable_exact_slots,
                "exact_funded_slots": exact_funded_slots,
                "exact_multiplier": 1 if exact_requested_slots > 0 else 0,
                "exact_book_pnl_units": exact_book_units,
                "exact_real_pnl": exact_real,
                "total_real_pnl": total_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
            }
        )
        if face_active:
            face_multiplier = next_multiplier(face_multiplier, settings.max_multiplier, face_real)
        if sum_funded_slots > 0:
            sum_multiplier = next_multiplier(sum_multiplier, settings.max_multiplier, sum_real)

    daily_df = pd.DataFrame(rows)
    summary = {
        "sim_start": str(sim_start.date()),
        "sim_end": str(sim_end.date()),
        "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]) if not daily_df.empty else float(settings.bankroll_start),
        "net_profit": float(daily_df["total_real_pnl"].sum()) if not daily_df.empty else 0.0,
        "peak_bankroll": float(peak),
        "min_bankroll": float(min_bankroll),
        "max_drawdown": float(max_drawdown),
        "face_profit": float(daily_df["face_real_pnl"].sum()) if not daily_df.empty else 0.0,
        "sum_profit": float(daily_df["sum_real_pnl"].sum()) if not daily_df.empty else 0.0,
        "exact_profit": float(daily_df["exact_real_pnl"].sum()) if not daily_df.empty else 0.0,
    }
    return ReplayResult(
        daily_df=daily_df,
        summary=summary,
        end_bankroll=float(daily_df["bankroll_after_day"].iloc[-1]) if not daily_df.empty else float(settings.bankroll_start),
        end_face_multiplier=face_multiplier,
        end_sum_multiplier=sum_multiplier,
        peak_bankroll=float(peak),
        min_bankroll=float(min_bankroll),
        max_drawdown=float(max_drawdown),
        sum_bet_rows=sum_bet_rows,
    )


def current_day_issue_maps(issue_df: pd.DataFrame, current_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_day = normalize_issue_df(issue_df)
    raw_day = raw_day[raw_day["draw_date"] == current_date].copy().reset_index(drop=True)
    raw_day["slot_1based"] = np.arange(1, len(raw_day) + 1)
    face_day = filter_blackout(raw_day, parse_time_of_day(settings.blackout_start), parse_time_of_day(settings.blackout_end)).copy()
    face_day["slot_1based"] = np.arange(1, len(face_day) + 1)
    return raw_day, face_day


def build_live_sum_plan(mods: StrategyModules, sum_ctx: dict[str, Any], raw_day: pd.DataFrame) -> dict[str, Any]:
    preview_cut = int(sum_ctx["preview_cut"])
    latest_slot = int(len(raw_day))
    current_week_idx = int(len(sum_ctx["bundle"].week_start) - 1)
    score = sum_ctx["choice_state"].score[current_week_idx].astype(np.float64)
    order = np.argsort(-score, kind="stable")
    blocked_slots = set(int(x) for x in sum_ctx["baseline"].slot_blacklist)
    selected_slots = [int(slot) for slot in order if slot not in blocked_slots and score[slot] > 0.0][: int(sum_ctx["baseline"].daily_issue_cap)]
    if latest_slot < preview_cut:
        return {
            "status": "waiting_preview",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": f"等待前 {preview_cut} 期完成判窗",
        }
    day_sum_values = (raw_day["pos1"].astype(int) + raw_day["pos2"].astype(int)).to_numpy(dtype=np.int16)
    preview_values = day_sum_values[:preview_cut]
    tradable_slots = [slot for slot in selected_slots if slot >= preview_cut and slot < len(score)]
    metrics = {
        "requested_slots": len(tradable_slots),
        "selected_mean_edge": float(np.mean(sum_ctx["choice_state"].mean_edge[current_week_idx, tradable_slots])) if tradable_slots else 0.0,
        "preview_raw_high_bias": float(np.mean(preview_values > 11) - np.mean(preview_values < 11)),
        "preview_mid_share": float(np.mean((preview_values >= 9) & (preview_values <= 13))),
        "preview_mean_sum": float(np.mean(preview_values)),
    }
    if not tradable_slots or not gate_is_on(metrics, sum_ctx["candidate_row"]):
        return {
            "status": "no_window",
            "latest_slot": latest_slot,
            "requested_slots": len(tradable_slots),
            "picks": [],
            "message": "当前和值无可投注选项",
            **metrics,
        }
    picks: list[dict[str, Any]] = []
    for slot in tradable_slots:
        slot_1based = int(slot + 1)
        issue_row = raw_day[raw_day["slot_1based"] == slot_1based]
        issue_value = int(issue_row["pre_draw_issue"].iloc[0]) if not issue_row.empty else None
        sum_index = int(sum_ctx["choice_state"].sum_idx[current_week_idx, slot])
        picks.append(
            {
                "slot_1based": slot_1based,
                "pre_draw_issue": issue_value,
                "sum_value": int(mods.sum_vmod.INDEX_TO_SUM[sum_index]),
                "sum_index": sum_index,
                "score_value": float(sum_ctx["choice_state"].score[current_week_idx, slot]),
                "odds_display": f"和值 {int(mods.sum_vmod.INDEX_TO_SUM[sum_index])} | 净赢 {sum_net_odds_for_index(sum_index):.1f}",
            }
        )
    picks = sorted(picks, key=lambda item: (-item["score_value"], item["slot_1based"]))
    return {
        "status": "active",
        "latest_slot": latest_slot,
        "requested_slots": len(picks),
        "picks": picks,
        "message": "和值窗口已开启",
        **metrics,
    }


def build_live_exact_plan(mods: StrategyModules, exact_ctx: dict[str, Any], raw_day: pd.DataFrame) -> dict[str, Any]:
    latest_slot = int(len(raw_day))
    if latest_slot < settings.exact_obs_window:
        return {
            "status": "waiting_preview",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": f"等待前 {settings.exact_obs_window} 期完成判窗",
        }
    current_week_idx = int(len(exact_ctx["bundle"].round9_bundle.week_start) - 1)
    current_rows = exact_ctx["subgroup_state_df"][
        (exact_ctx["subgroup_state_df"]["base_gate_id"] == settings.exact_base_gate_id)
        & (exact_ctx["subgroup_state_df"]["block_start_week_idx"] <= current_week_idx)
        & (exact_ctx["subgroup_state_df"]["block_end_week_idx"] >= current_week_idx)
    ].copy()
    if current_rows.empty:
        return {
            "status": "no_window",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": "当前定位胆无可投注选项",
        }
    picks: list[dict[str, Any]] = []
    number_matrix = raw_day[[f"pos{i}" for i in range(1, 11)]].to_numpy(dtype=np.int16)
    for row in current_rows.itertuples(index=False):
        slot_1based = int(row.slot_1based)
        if slot_1based <= settings.exact_obs_window or slot_1based > exact_ctx["bundle"].round9_bundle.n_slots:
            continue
        prefix_seq = number_matrix[: settings.exact_obs_window, int(row.position)].astype(int)
        group_numbers = [int(x) for x in json.loads(row.group_numbers_json)]
        prefix_group_hits = int(np.isin(prefix_seq, group_numbers).sum())
        if prefix_group_hits <= 0:
            continue
        num_a, num_b = group_numbers
        count_a = int(np.sum(prefix_seq == num_a))
        count_b = int(np.sum(prefix_seq == num_b))
        block_selected = int(row.selected_number)
        if count_a > count_b:
            prefix_major = num_a
        elif count_b > count_a:
            prefix_major = num_b
        elif block_selected in (num_a, num_b):
            prefix_major = block_selected
        else:
            prefix_major = min(num_a, num_b)
        if prefix_major != block_selected:
            continue
        issue_row = raw_day[raw_day["slot_1based"] == slot_1based]
        issue_value = int(issue_row["pre_draw_issue"].iloc[0]) if not issue_row.empty else None
        picks.append(
            {
                "slot_1based": slot_1based,
                "pre_draw_issue": issue_value,
                "number": int(prefix_major),
                "other": int(num_b if prefix_major == num_a else num_a),
                "position_1based": int(row.position_1based),
                "odds_display": f"定位胆 {int(prefix_major)} | 净赢 {float(settings.exact_net_win):.1f}",
            }
        )
    picks = sorted(picks, key=lambda item: item["slot_1based"])
    if not picks:
        return {
            "status": "no_window",
            "latest_slot": latest_slot,
            "requested_slots": 0,
            "picks": [],
            "message": "当前定位胆无可投注选项",
        }
    return {
        "status": "active",
        "latest_slot": latest_slot,
        "requested_slots": len(picks),
        "picks": picks,
        "message": "定位胆窗口已开启",
    }


def build_live_face_plan(face_ctx: dict[str, Any], face_day: pd.DataFrame, current_date: pd.Timestamp) -> dict[str, Any]:
    date_key = current_date.strftime("%Y-%m-%d")
    trace_row = face_ctx["trace_df"][face_ctx["trace_df"]["date"] == current_date]
    if trace_row.empty:
        return {"status": "cash", "mode": "cash", "latest_slot": int(len(face_day)), "picks": [], "message": "双面今日空仓"}
    mode = str(trace_row.iloc[0]["mode"])
    components = face_mode_components(mode)
    if not components:
        return {"status": "cash", "mode": mode, "latest_slot": int(len(face_day)), "picks": [], "message": "双面今日空仓"}
    by_source = face_ctx["plan_by_date"].get(date_key, {})
    picks: list[dict[str, Any]] = []
    for source in components:
        for item in by_source.get(source, []):
            row = dict(item)
            issue_row = face_day[face_day["slot_1based"] == row["slot_1based"]]
            row["pre_draw_issue"] = int(issue_row["pre_draw_issue"].iloc[0]) if not issue_row.empty else None
            picks.append(row)
    picks = sorted(picks, key=lambda item: (item["slot_1based"], item["source"]))
    return {
        "status": "active" if picks else "cash",
        "mode": mode,
        "latest_slot": int(len(face_day)),
        "picks": picks,
        "message": "双面可执行" if picks else "双面今日空仓",
    }


def allocate_live_line(line_name: str, start_bankroll: float, multiplier_value: int, picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if line_name == "face":
        funded = picks
    else:
        affordable = max(0, int(start_bankroll // (float(settings.base_stake) * multiplier_value)))
        funded = picks[:affordable]
    for item in funded:
        item["multiplier_value"] = multiplier_value
        item["stake"] = float(settings.base_stake) * multiplier_value
        item["ticket_count"] = int(item.get("ticket_count", 1))
        item["total_cost"] = item["stake"] * item["ticket_count"]
    return funded


def simulate_sum_settled_day(
    day_picks: pd.DataFrame,
    starting_multiplier: int,
    bankroll_before: float,
    schedule_map: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, float]:
    if day_picks.empty:
        return [], starting_multiplier, 0.0
    ladder = martingale_double_ladder(settings.max_multiplier)
    current_multiplier = int(starting_multiplier)
    cumulative_cost = 0.0
    events: list[dict[str, Any]] = []
    for pick in day_picks.sort_values(["slot", "score_value"], ascending=[True, False]).itertuples(index=False):
        stake = float(settings.base_stake) * current_multiplier
        total_cost = stake
        if cumulative_cost + total_cost > float(bankroll_before):
            break
        cumulative_cost += total_cost
        slot_1based = int(pick.slot) + 1
        issue_meta = schedule_map.get(slot_1based, {})
        book_points = float(pick.book_pnl) * stake
        events.append(
            {
                "draw_date": pd.Timestamp(pick.date).strftime("%Y-%m-%d"),
                "pre_draw_issue": issue_meta.get("issue"),
                "slot_1based": slot_1based,
                "line_name": "sum",
                "status": "settled",
                "selection_json": {"sum_value": int(pick.sum_value)},
                "odds_display": f"和值 {int(pick.sum_value)} | 净赢 {sum_net_odds_for_value(int(pick.sum_value)):.1f}",
                "stake": stake,
                "multiplier_value": current_multiplier,
                "ticket_count": 1,
                "total_cost": total_cost,
                "hit_count": int(pick.hit),
                "outcome_label": "命中" if int(pick.hit) == 1 else "未中",
                "pnl": book_points,
                "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
            }
        )
        current_multiplier = next_ladder_multiplier(current_multiplier, ladder, book_points)
    total_book_points = float(sum(item["pnl"] for item in events))
    return events, current_multiplier, total_book_points


def simulate_live_sum_day(
    day_picks: pd.DataFrame,
    starting_multiplier: int,
    bankroll_before: float,
    latest_slot: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, float]:
    if day_picks.empty:
        return [], [], starting_multiplier, 0.0
    ladder = martingale_double_ladder(settings.max_multiplier)
    current_multiplier = int(starting_multiplier)
    cumulative_cost = 0.0
    executed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    provisional_book_points = 0.0
    for pick in day_picks.sort_values(["slot_1based", "score_value"], ascending=[True, False]).itertuples(index=False):
        stake = float(settings.base_stake) * current_multiplier
        total_cost = stake
        if cumulative_cost + total_cost > float(bankroll_before):
            break
        cumulative_cost += total_cost
        payload = {
            "slot_1based": int(pick.slot_1based),
            "pre_draw_issue": pick.pre_draw_issue,
            "sum_value": int(pick.sum_value),
            "sum_index": int(pick.sum_index),
            "score_value": float(pick.score_value),
            "odds_display": f"和值 {int(pick.sum_value)} | 净赢 {sum_net_odds_for_value(int(pick.sum_value)):.1f}",
            "multiplier_value": current_multiplier,
            "stake": stake,
            "ticket_count": 1,
            "total_cost": total_cost,
        }
        if int(pick.slot_1based) <= int(latest_slot):
            book_units = float(pick.book_pnl)
            book_points = book_units * stake
            executed.append(
                {
                    **payload,
                    "status": "executed",
                    "hit_count": int(pick.hit),
                    "outcome_label": "命中" if int(pick.hit) == 1 else "未中",
                    "book_pnl_units": book_units,
                    "book_pnl": book_points,
                }
            )
            provisional_book_points += book_points
            current_multiplier = next_ladder_multiplier(current_multiplier, ladder, book_points)
        else:
            pending.append({**payload, "status": "pending"})
    return executed, pending, current_multiplier, provisional_book_points


def finalize_live_state(
    mods: StrategyModules,
    current_date: pd.Timestamp,
    raw_day: pd.DataFrame,
    face_day: pd.DataFrame,
    replay: ReplayResult,
    face_ctx: dict[str, Any],
    sum_ctx: dict[str, Any],
    exact_ctx: dict[str, Any],
    live_payload: dict[str, Any],
) -> dict[str, Any]:
    face_plan = build_live_face_plan(face_ctx, face_day, current_date)
    sum_plan = build_live_sum_plan(mods, sum_ctx, raw_day)
    exact_plan = build_live_exact_plan(mods, exact_ctx, raw_day)
    settled_bankroll = replay.end_bankroll
    face_funded = allocate_live_line("face", settled_bankroll, replay.end_face_multiplier, face_plan["picks"])
    sum_funded = allocate_live_line("sum", settled_bankroll, replay.end_sum_multiplier, sum_plan["picks"])
    exact_funded = allocate_live_line("exact", settled_bankroll, 1, exact_plan["picks"])

    raw_issue_lookup = {int(row.slot_1based): row for row in raw_day.itertuples(index=False)}
    face_issue_lookup = {int(row.slot_1based): row for row in face_day.itertuples(index=False)}
    face_latest_slot = int(len(face_day))
    raw_latest_slot = int(len(raw_day))

    face_executed, face_pending = [], []
    face_book_units = 0.0
    for item in face_funded:
        target = face_issue_lookup.get(int(item["slot_1based"]))
        if target is None or int(item["slot_1based"]) > face_latest_slot:
            face_pending.append(item)
            continue
        ledger, hit_count, label = face_payload_book_units(pd.Series(target._asdict()), item)
        enriched = {
            **item,
            "status": "executed",
            "hit_count": hit_count,
            "outcome_label": label,
            "book_pnl_units": ledger,
            "book_pnl": ledger * item["stake"],
        }
        face_book_units += ledger
        face_executed.append(enriched)
    face_real = daily85(face_book_units * replay.end_face_multiplier) * float(settings.base_stake) if face_funded else 0.0

    sum_executed, sum_pending = [], []
    sum_book_units_total = 0.0
    for item in sum_funded:
        target = raw_issue_lookup.get(int(item["slot_1based"]))
        if target is None or int(item["slot_1based"]) > raw_latest_slot:
            sum_pending.append(item)
            continue
        sum_index = int(item["sum_index"])
        hit = int(int(target.pos1) + int(target.pos2) == int(mods.sum_vmod.INDEX_TO_SUM[sum_index]))
        book_units = sum_book_units(sum_index, hit)
        enriched = {
            **item,
            "status": "executed",
            "hit_count": hit,
            "outcome_label": "命中" if hit else "未中",
            "book_pnl_units": book_units,
            "book_pnl": book_units * item["stake"],
        }
        sum_book_units_total += book_units
        sum_executed.append(enriched)
    sum_real = settle_real(sum_book_units_total * replay.end_sum_multiplier) * float(settings.base_stake) if sum_funded else 0.0

    exact_executed, exact_pending = [], []
    exact_book_units = 0.0
    for item in exact_funded:
        target_slot = int(item["slot_1based"]) + 1
        target = raw_issue_lookup.get(target_slot)
        if target is None or target_slot > raw_latest_slot:
            exact_pending.append(item)
            continue
        number = int(item["number"])
        target_row = pd.Series(target._asdict())
        position_1based = int(item["position_1based"])
        actual_number = int(target_row[f"pos{position_1based}"])
        hit = int(number == actual_number)
        book_units = float(settings.exact_net_win if hit else -1.0)
        enriched = {
            **item,
            "pre_draw_issue": int(target.pre_draw_issue),
            "status": "executed",
            "hit_count": hit,
            "outcome_label": "命中" if hit else f"未中({actual_number})",
            "book_pnl_units": book_units,
            "book_pnl": book_units * item["stake"],
        }
        exact_book_units += book_units
        exact_executed.append(enriched)
    exact_real = settle_real(exact_book_units) * float(settings.base_stake) if exact_funded else 0.0

    total_provisional = float(face_real + sum_real + exact_real)
    current_actions: list[dict[str, Any]] = []
    next_issue = int(live_payload["drawIssue"]) if live_payload.get("drawIssue") else None
    next_raw_slot = raw_latest_slot + 1
    next_face_slot = face_latest_slot + 1

    def maybe_append(line_name: str, candidates: list[dict[str, Any]], target_slot: int | None) -> None:
        if target_slot is None:
            return
        for item in candidates:
            if int(item["slot_1based"]) != int(target_slot):
                continue
            current_actions.append(
                {
                    "line_name": line_name,
                    "draw_issue": next_issue,
                    "slot_1based": int(item["slot_1based"]),
                    "stake": float(item["stake"]),
                    "multiplier_value": int(item["multiplier_value"]),
                    "ticket_count": int(item["ticket_count"]),
                    "total_cost": float(item["total_cost"]),
                    "selection": {
                        key: item[key]
                        for key in ("sum_value", "number", "other", "position_1based", "big_positions", "small_positions", "source")
                        if key in item
                    },
                    "odds_display": item["odds_display"],
                }
            )

    next_face_allowed = True
    draw_time = pd.Timestamp(live_payload["drawTime"]) if live_payload.get("drawTime") else None
    blackout_start = parse_time_of_day(settings.blackout_start)
    blackout_end = parse_time_of_day(settings.blackout_end)
    if draw_time is not None and blackout_start and blackout_end:
        next_face_allowed = not (blackout_start <= draw_time.time() < blackout_end)

    maybe_append("face", face_pending, next_face_slot if next_face_allowed else None)
    maybe_append("sum", sum_pending, next_raw_slot)
    maybe_append("exact", exact_pending, next_raw_slot)

    return {
        "settled_bankroll": settled_bankroll,
        "today_provisional_pnl": total_provisional,
        "estimated_close_bankroll": settled_bankroll + total_provisional,
        "current_actions": current_actions,
        "face": {
            "mode": face_plan["mode"],
            "multiplier_value": replay.end_face_multiplier,
            "requested_slots": len(face_plan["picks"]),
            "funded_slots": len(face_funded),
            "executed_slots": len(face_executed),
            "pending_slots": len(face_pending),
            "provisional_pnl": face_real,
            "status": face_plan["status"],
            "message": face_plan["message"],
            "executed": face_executed,
            "pending": face_pending,
        },
        "sum": {
            "multiplier_value": replay.end_sum_multiplier,
            "requested_slots": sum_plan["requested_slots"],
            "funded_slots": len(sum_funded),
            "executed_slots": len(sum_executed),
            "pending_slots": len(sum_pending),
            "provisional_pnl": sum_real,
            "status": sum_plan["status"],
            "message": sum_plan["message"],
            "executed": sum_executed,
            "pending": sum_pending,
        },
        "exact": {
            "multiplier_value": 1,
            "requested_slots": exact_plan["requested_slots"],
            "funded_slots": len(exact_funded),
            "executed_slots": len(exact_executed),
            "pending_slots": len(exact_pending),
            "provisional_pnl": exact_real,
            "status": exact_plan["status"],
            "message": exact_plan["message"],
            "executed": exact_executed,
            "pending": exact_pending,
        },
    }


def build_historical_bet_rows(
    mods: StrategyModules,
    replay: ReplayResult,
    face_ctx: dict[str, Any],
    sum_ctx: dict[str, Any],
    exact_ctx: dict[str, Any],
    current_live: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    settled_df = replay.daily_df
    face_schedule = face_ctx["schedule_map"]
    sum_schedule = sum_ctx["schedule_map"]
    exact_schedule = exact_ctx["schedule_map"]
    market = current_live.get("market", {})
    simulation_start = pd.Timestamp(settings.simulation_start_date).strftime("%Y-%m-%d")

    def current_live_issue_for_raw(slot_1based: int) -> int | None:
        latest_issue = market.get("pre_draw_issue")
        latest_slot = market.get("raw_latest_slot")
        if latest_issue is None or latest_slot is None:
            return None
        return int(latest_issue) - int(latest_slot) + int(slot_1based)

    for row in settled_df.itertuples(index=False):
        date_key = pd.Timestamp(row.date).strftime("%Y-%m-%d")
        face_components = face_mode_components(str(row.face_mode))
        for source_name in face_components:
            for item in face_ctx["plan_by_date"].get(date_key, {}).get(source_name, []):
                issue_meta = face_schedule.get(date_key, {}).get(int(item["slot_1based"]))
                if not issue_meta:
                    continue
                rows.append(
                    {
                        "draw_date": date_key,
                        "pre_draw_issue": issue_meta["issue"],
                        "slot_1based": int(item["slot_1based"]),
                        "line_name": "face",
                        "status": "settled",
                        "selection_json": {
                            "source": source_name,
                            "big_positions": item["big_positions"],
                            "small_positions": item["small_positions"],
                        },
                        "odds_display": item["odds_display"],
                        "stake": float(settings.base_stake) * int(row.face_multiplier or 1),
                        "multiplier_value": int(row.face_multiplier or 1),
                        "ticket_count": int(item["ticket_count"]),
                        "total_cost": float(settings.base_stake) * int(row.face_multiplier or 1) * int(item["ticket_count"]),
                        "hit_count": None,
                        "outcome_label": None,
                        "pnl": None,
                        "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
                    }
                )
        if int(row.sum_funded_slots) > 0:
            picks = sum_ctx["picks_by_date"].get(pd.Timestamp(row.date), pd.DataFrame()).head(int(row.sum_funded_slots))
            for pick in picks.itertuples(index=False):
                slot_1based = int(pick.slot) + 1
                issue_meta = sum_schedule.get(date_key, {}).get(slot_1based)
                if not issue_meta:
                    continue
                rows.append(
                    {
                        "draw_date": date_key,
                        "pre_draw_issue": issue_meta["issue"],
                        "slot_1based": slot_1based,
                        "line_name": "sum",
                        "status": "settled",
                        "selection_json": {"sum_value": int(pick.sum_value)},
                        "odds_display": f"和值 {int(pick.sum_value)} | 净赢 {sum_net_odds_for_value(int(pick.sum_value)):.1f}",
                        "stake": float(settings.base_stake) * int(row.sum_multiplier or 1),
                        "multiplier_value": int(row.sum_multiplier or 1),
                        "ticket_count": 1,
                        "total_cost": float(settings.base_stake) * int(row.sum_multiplier or 1),
                        "hit_count": int(pick.hit),
                        "outcome_label": "命中" if int(pick.hit) == 1 else "未中",
                        "pnl": float(pick.book_pnl) * float(settings.base_stake) * int(row.sum_multiplier or 1),
                        "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
                    }
                )
        if int(row.exact_funded_slots) > 0:
            picks = exact_ctx["picks_by_date"].get(pd.Timestamp(row.date), pd.DataFrame()).head(int(row.exact_funded_slots))
            for pick in picks.itertuples(index=False):
                issue_meta = exact_schedule.get(date_key, {}).get(int(pick.slot_1based))
                if not issue_meta:
                    continue
                rows.append(
                    {
                        "draw_date": date_key,
                        "pre_draw_issue": issue_meta["issue"],
                        "slot_1based": int(pick.slot_1based),
                        "line_name": "exact",
                        "status": "settled",
                        "selection_json": {
                            "number": int(pick.selected_number_exec),
                            "other": (
                                None
                                if not hasattr(pick, "prefix_other_number") or pd.isna(pick.prefix_other_number)
                                else int(pick.prefix_other_number)
                            ),
                            "position_1based": int(pick.position_1based),
                        },
                        "odds_display": f"定位胆 {int(pick.selected_number_exec)} | 净赢 {float(settings.exact_net_win):.1f}",
                        "stake": float(settings.base_stake),
                        "multiplier_value": 1,
                        "ticket_count": 1,
                        "total_cost": float(settings.base_stake),
                        "hit_count": int(pick.exact_hit_exec),
                        "outcome_label": "命中" if int(pick.exact_hit_exec) == 1 else "未中",
                        "pnl": float(pick.cell_book_pnl_units) * float(settings.base_stake),
                        "meta_json": {"basis": "book", "pre_draw_code": issue_meta.get("pre_draw_code")},
                    }
                )
    current_date_key = str(current_live["market"]["current_date"])
    if current_date_key >= simulation_start:
        for line_name in ("face", "sum", "exact"):
            line_state = current_live[line_name]
            for bucket_name in ("executed", "pending"):
                status = "executed" if bucket_name == "executed" else "pending"
                for item in line_state[bucket_name]:
                    row_issue = item.get("pre_draw_issue")
                    if line_name in {"sum", "exact"} and row_issue is None:
                        row_issue = current_live_issue_for_raw(int(item["slot_1based"])) or row_issue
                    rows.append(
                        {
                            "draw_date": current_date_key,
                            "pre_draw_issue": row_issue,
                            "slot_1based": int(item["slot_1based"]),
                            "line_name": line_name,
                            "status": status,
                            "selection_json": {
                                key: item[key]
                                for key in ("sum_value", "number", "other", "position_1based", "big_positions", "small_positions", "source")
                                if key in item
                            },
                            "odds_display": item["odds_display"],
                            "stake": float(item["stake"]),
                            "multiplier_value": int(item["multiplier_value"]),
                            "ticket_count": int(item["ticket_count"]),
                            "total_cost": float(item["total_cost"]),
                            "hit_count": item.get("hit_count"),
                            "outcome_label": item.get("outcome_label"),
                            "pnl": item.get("book_pnl"),
                            "meta_json": {"basis": "book"},
                        }
                    )
    rows.sort(key=lambda item: (item["draw_date"], item["pre_draw_issue"] or 0, item["line_name"], item["slot_1based"]))
    return rows


def serialize_daily_curve(daily_df: pd.DataFrame) -> list[dict[str, Any]]:
    if daily_df.empty:
        return []
    return [
        {
            "date": pd.Timestamp(row.date).strftime("%Y-%m-%d"),
            "settled_bankroll": float(row.bankroll_after_day),
            "total_real_pnl": float(row.total_real_pnl),
            "face_real_pnl": float(row.face_real_pnl),
            "sum_real_pnl": float(row.sum_real_pnl),
            "exact_real_pnl": float(row.exact_real_pnl),
            "drawdown_from_peak": float(row.drawdown_from_peak),
        }
        for row in daily_df.itertuples(index=False)
    ]


def build_runtime_context(mods: StrategyModules, issue_df: pd.DataFrame) -> dict[str, Any]:
    if issue_df.empty:
        raise RuntimeError("Issue history is empty")
    current_date = pd.Timestamp(issue_df["draw_date"].max()).normalize()
    current_day_complete = len(issue_df[issue_df["draw_date"] == current_date]) >= int(issue_df.groupby("draw_date").size().mode().iloc[0])
    settled_end = current_date if current_day_complete else current_date - pd.Timedelta(days=1)
    face_ctx = build_face_context(mods, issue_df, current_date)
    sum_ctx = build_sum_context(mods, issue_df)
    exact_ctx = build_exact_context(mods, issue_df)
    simulation_start = pd.Timestamp(settings.simulation_start_date)
    if settled_end < simulation_start:
        replay = ReplayResult(
            daily_df=pd.DataFrame(),
            summary={"face_profit": 0.0, "sum_profit": 0.0, "exact_profit": 0.0},
            end_bankroll=float(settings.bankroll_start),
            end_face_multiplier=1,
            end_sum_multiplier=1,
            peak_bankroll=float(settings.bankroll_start),
            min_bankroll=float(settings.bankroll_start),
            max_drawdown=0.0,
            sum_bet_rows=[],
        )
    else:
        replay = replay_shared_bankroll(
            mods=mods,
            sim_start=simulation_start,
            sim_end=settled_end,
            face_ctx=face_ctx,
            sum_ctx=sum_ctx,
            exact_ctx=exact_ctx,
        )
    return {
        "current_date": current_date,
        "current_day_complete": current_day_complete,
        "face_ctx": face_ctx,
        "sum_ctx": sum_ctx,
        "exact_ctx": exact_ctx,
        "replay": replay,
    }


def snapshot_from_context(mods: StrategyModules, issue_df: pd.DataFrame, live_payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    current_date = pd.Timestamp(context["current_date"])
    current_day_complete = bool(context["current_day_complete"])
    face_ctx = context["face_ctx"]
    sum_ctx = context["sum_ctx"]
    exact_ctx = context["exact_ctx"]
    replay: ReplayResult = context["replay"]
    raw_day, face_day = current_day_issue_maps(issue_df, current_date)
    live_state = finalize_live_state(mods, current_date, raw_day, face_day, replay, face_ctx, sum_ctx, exact_ctx, live_payload)
    market = {
        "server_time": str(live_payload.get("serverTime", "")),
        "current_date": current_date.strftime("%Y-%m-%d"),
        "pre_draw_issue": int(live_payload["preDrawIssue"]) if live_payload.get("preDrawIssue") is not None else None,
        "draw_issue": int(live_payload["drawIssue"]) if live_payload.get("drawIssue") is not None else None,
        "pre_draw_code": str(live_payload.get("preDrawCode", "")),
        "draw_time": str(live_payload.get("drawTime", "")),
        "raw_latest_slot": int(len(raw_day)),
        "face_latest_slot": int(len(face_day)),
        "issues_per_day": int(issue_df.groupby("draw_date").size().mode().iloc[0]),
        "current_day_complete": bool(current_day_complete),
    }
    daily_curve = serialize_daily_curve(replay.daily_df)
    if not current_day_complete:
        daily_curve.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "settled_bankroll": float(live_state["estimated_close_bankroll"]),
                "total_real_pnl": float(live_state["today_provisional_pnl"]),
                "face_real_pnl": float(live_state["face"]["provisional_pnl"]),
                "sum_real_pnl": float(live_state["sum"]["provisional_pnl"]),
                "exact_real_pnl": float(live_state["exact"]["provisional_pnl"]),
                "drawdown_from_peak": float((live_state["estimated_close_bankroll"]) - max(replay.peak_bankroll, live_state["estimated_close_bankroll"])),
                "provisional": True,
            }
        )
    contributions = {
        "settled": {
            "face": float(replay.summary.get("face_profit", 0.0)),
            "sum": float(replay.summary.get("sum_profit", 0.0)),
            "exact": float(replay.summary.get("exact_profit", 0.0)),
        },
        "today_provisional": {
            "face": float(live_state["face"]["provisional_pnl"]),
            "sum": float(live_state["sum"]["provisional_pnl"]),
            "exact": float(live_state["exact"]["provisional_pnl"]),
        },
    }
    current_actions = live_state["current_actions"]
    if not current_actions:
        current_actions = [
            {"line_name": "face", "draw_issue": market["draw_issue"], "message": live_state["face"]["message"]},
            {"line_name": "sum", "draw_issue": market["draw_issue"], "message": live_state["sum"]["message"]},
            {"line_name": "exact", "draw_issue": market["draw_issue"], "message": live_state["exact"]["message"]},
        ]
    snapshot = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "ranges": {
            "history_start_date": settings.history_start_date,
            "simulation_start_date": settings.simulation_start_date,
        },
        "market": market,
        "totals": {
            "settled_bankroll": float(live_state["settled_bankroll"]),
            "today_provisional_pnl": float(live_state["today_provisional_pnl"]),
            "estimated_close_bankroll": float(live_state["estimated_close_bankroll"]),
            "peak_bankroll": float(replay.peak_bankroll),
            "min_bankroll": float(replay.min_bankroll),
            "max_drawdown": float(replay.max_drawdown),
        },
        "contributions": contributions,
        "line_state": {
            "face": {key: value for key, value in live_state["face"].items() if key not in {"executed", "pending"}},
            "sum": {key: value for key, value in live_state["sum"].items() if key not in {"executed", "pending"}},
            "exact": {key: value for key, value in live_state["exact"].items() if key not in {"executed", "pending"}},
        },
        "today_plan": {
            "face": live_state["face"],
            "sum": live_state["sum"],
            "exact": live_state["exact"],
        },
        "current_actions": current_actions,
        "daily_curve": daily_curve,
        "replay": replay,
        "bet_rows": build_historical_bet_rows(mods, replay, face_ctx, sum_ctx, exact_ctx, {"market": market, **live_state}),
    }
    return snapshot


def build_snapshot(mods: StrategyModules, issue_df: pd.DataFrame, live_payload: dict[str, Any]) -> dict[str, Any]:
    context = build_runtime_context(mods, issue_df)
    return snapshot_from_context(mods, issue_df, live_payload, context)
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/backend/app/runtime.py`

```python
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
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/backend/app/main.py`

```python
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
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/deploy/ecosystem.config.cjs`

```javascript
module.exports = {
  apps: [
    {
      name: 'pk10-live-dashboard',
      cwd: '/root/pk10/pk10_live_dashboard/backend',
      script: '/bin/bash',
      args: '-lc "set -a && source /root/pk10/.env && exec /root/pk10/pk10_live_dashboard/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18080"',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_restarts: 10,
      env: {
        PYTHONUNBUFFERED: '1'
      }
    }
  ]
}
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/deploy/pk10.nginx.conf`

```nginx
server {
    listen 5173;
    server_name _;

    auth_basic "PK10 Live Dashboard";
    auth_basic_user_file /etc/nginx/pk10-live.htpasswd;

    root /var/www/pk10-live;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /events/stream {
        proxy_pass http://127.0.0.1:18080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        add_header Cache-Control no-cache;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/frontend/package.json`

```json
{
  "name": "pk10-live-dashboard",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.1.1",
    "react-dom": "^19.1.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.0.2",
    "vite": "^7.1.3"
  }
}
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/frontend/vite.config.js`

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173
  }
})
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/frontend/src/main.jsx`

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/frontend/src/App.jsx`

```jsx
import { useEffect, useMemo, useRef, useState } from 'react'

const API = ''
const CURVE_START_DATE = '2026-04-01'
const BET_PAGE_SIZE = 40
const LINE_LABELS = {
  face: '双面',
  sum: '冠亚和',
  exact: '定位胆'
}

function lineLabel(lineName) {
  return LINE_LABELS[lineName] || lineName || '未知'
}

function fmtNumber(value) {
  const num = Number(value ?? 0)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
}

function parseMaybeJson(value) {
  if (!value) return null
  if (typeof value === 'object') return value
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function selectionSummary(row) {
  const selection = parseMaybeJson(row.selection_json) || row.selection || {}
  if (row.line_name === 'sum' && selection.sum_value != null) {
    return `和值 ${selection.sum_value}`
  }
  if (row.line_name === 'exact' && selection.number != null) {
    return `位置 ${selection.position_1based} · 号码 ${selection.number}`
  }
  if (row.line_name === 'face') {
    const parts = []
    if (selection.source) parts.push(selection.source)
    if (Array.isArray(selection.big_positions) && selection.big_positions.length) parts.push(`大位 ${selection.big_positions.join(',')}`)
    if (Array.isArray(selection.small_positions) && selection.small_positions.length) parts.push(`小位 ${selection.small_positions.join(',')}`)
    return parts.join(' / ') || '双面票型'
  }
  return '未识别票型'
}

function lineSelection(row, targetLine) {
  if (row.line_name !== targetLine) return '—'
  return selectionSummary(row)
}

function statusLabel(status) {
  if (status === 'settled') return '已结算'
  if (status === 'executed') return '已执行'
  if (status === 'pending') return '待开奖'
  return status || '未知'
}

function broadcastStateLabel(value) {
  if (value === 'broadcasted') return '已播报执行'
  if (value === 'pending_future') return '未触发待执行'
  return '未知'
}

function broadcastStatusLabel(row) {
  const payload = parseMaybeJson(row.payload_json) || {}
  const message = String(payload.message || '')
  if (row.actionable) return '可投'
  if (message.includes('等待前') || message.includes('判窗')) return '等待判窗'
  if (message.includes('窗口已开启')) return '窗口开启'
  if (message.includes('空仓') || message.includes('无可投注选项')) return '无票'
  return '观察中'
}

function broadcastContentSummary(row) {
  const payload = parseMaybeJson(row.payload_json) || {}
  const selection = payload.selection || {}
  if (row.actionable) {
    const parts = []
    if (payload.slot_1based != null) parts.push(`期位 ${payload.slot_1based}`)
    if (row.line_name === 'sum' && selection.sum_value != null) {
      parts.push(`和值 ${selection.sum_value}`)
    }
    if (row.line_name === 'exact' && selection.position_1based != null && selection.number != null) {
      parts.push(`位置 ${selection.position_1based} · 号码 ${selection.number}`)
    }
    if (row.line_name === 'face') {
      if (selection.source) parts.push(selection.source)
      if (Array.isArray(selection.big_positions) && selection.big_positions.length) parts.push(`大位 ${selection.big_positions.join(',')}`)
      if (Array.isArray(selection.small_positions) && selection.small_positions.length) parts.push(`小位 ${selection.small_positions.join(',')}`)
    }
    if (payload.total_cost != null) parts.push(`${fmtNumber(payload.total_cost)} 分`)
    else if (payload.stake != null) parts.push(`${fmtNumber(payload.stake)} 分`)
    return parts.join(' · ') || '可投'
  }
  return payload.message || '无播报内容'
}

function useDashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [curveRows, setCurveRows] = useState([])
  const [betPage, setBetPage] = useState(1)
  const [betScope, setBetScope] = useState('all')
  const [broadcastPage, setBroadcastPage] = useState(1)
  const [broadcastIssueQuery, setBroadcastIssueQuery] = useState('')
  const [broadcastIssueInput, setBroadcastIssueInput] = useState('')
  const [betPageData, setBetPageData] = useState({
    rows: [],
    page: 1,
    page_size: BET_PAGE_SIZE,
    total: 0,
      total_pages: 1,
      has_prev: false,
      has_next: false,
      scope: 'all',
      counts: { all: 0, broadcasted: 0, pending_future: 0 }
    })
  const [broadcastPageData, setBroadcastPageData] = useState({
    rows: [],
    page: 1,
    page_size: BET_PAGE_SIZE,
    total: 0,
    total_pages: 1,
    has_prev: false,
    has_next: false
  })
  const betPageRef = useRef(1)
  const betScopeRef = useRef('all')
  const broadcastPageRef = useRef(1)
  const broadcastIssueRef = useRef('')

  useEffect(() => {
    betPageRef.current = betPage
  }, [betPage])

  useEffect(() => {
    betScopeRef.current = betScope
  }, [betScope])

  useEffect(() => {
    broadcastPageRef.current = broadcastPage
  }, [broadcastPage])

  useEffect(() => {
    broadcastIssueRef.current = broadcastIssueQuery
  }, [broadcastIssueQuery])

  async function refreshSnapshot() {
    const [dashboardRes, curveRes] = await Promise.all([
      fetch(`${API}/api/dashboard`).then((res) => res.json()),
      fetch(`${API}/api/curve/daily?start_date=${CURVE_START_DATE}`).then((res) => res.json())
    ])
    setDashboard(dashboardRes)
    setCurveRows(curveRes.rows ?? [])
  }

  async function refreshBets(targetPage, targetScope = betScopeRef.current) {
    const page = Math.max(1, Number(targetPage || 1))
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(BET_PAGE_SIZE),
      scope: String(targetScope || 'all')
    })
    const betRes = await fetch(`${API}/api/history/bets?${query.toString()}`).then((res) => res.json())
    setBetPageData({
      rows: betRes.rows ?? [],
      page: betRes.page ?? page,
      page_size: betRes.page_size ?? BET_PAGE_SIZE,
      total: betRes.total ?? 0,
      total_pages: betRes.total_pages ?? 1,
      has_prev: Boolean(betRes.has_prev),
      has_next: Boolean(betRes.has_next),
      scope: betRes.scope ?? targetScope ?? 'all',
      counts: betRes.counts ?? { all: 0, broadcasted: 0, pending_future: 0 }
    })
  }

  async function refreshBroadcasts(targetPage, targetIssue = broadcastIssueRef.current) {
    const page = Math.max(1, Number(targetPage || 1))
    const issue = String(targetIssue || '').trim()
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(BET_PAGE_SIZE)
    })
    if (issue) query.set('issue', issue)
    const broadcastRes = await fetch(`${API}/api/history/broadcasts?${query.toString()}`).then((res) => res.json())
    setBroadcastPageData({
      rows: broadcastRes.rows ?? [],
      page: broadcastRes.page ?? page,
      page_size: broadcastRes.page_size ?? BET_PAGE_SIZE,
      total: broadcastRes.total ?? 0,
      total_pages: broadcastRes.total_pages ?? 1,
      has_prev: Boolean(broadcastRes.has_prev),
      has_next: Boolean(broadcastRes.has_next),
      issue: broadcastRes.issue ?? issue
    })
  }

  useEffect(() => {
    refreshSnapshot()
    refreshBets(1, 'all')
    refreshBroadcasts(1, '')
    const sse = new EventSource(`${API}/events/stream`)
    sse.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload?.payload) {
          setDashboard(payload.payload)
        } else {
          setDashboard(payload)
        }
      } catch {
        // Ignore parse errors and force a full refetch below.
      }
      refreshSnapshot()
      refreshBets(betPageRef.current, betScopeRef.current)
      refreshBroadcasts(broadcastPageRef.current, broadcastIssueRef.current)
    }
    return () => sse.close()
  }, [])

  useEffect(() => {
    refreshBets(betPage, betScope)
  }, [betPage, betScope])

  useEffect(() => {
    refreshBroadcasts(broadcastPage, broadcastIssueQuery)
  }, [broadcastPage, broadcastIssueQuery])

  return {
    dashboard,
    curveRows,
    betPageData,
    betPage,
    setBetPage,
    betScope,
    setBetScope,
    broadcastPageData,
    broadcastPage,
    setBroadcastPage,
    setBroadcastIssueQuery,
    broadcastIssueInput,
    setBroadcastIssueInput
  }
}

function MiniStat({ label, value, accent, note }) {
  return (
    <div className="mini-stat">
      <div className="mini-label">{label}</div>
      <div className={`mini-value ${accent || ''}`}>{value}</div>
      {note ? <div className="mini-note">{note}</div> : null}
    </div>
  )
}

function EquityCurve({ rows, startDate }) {
  const data = rows ?? []
  const width = 920
  const height = 280
  const padding = 28

  const { path, bars } = useMemo(() => {
    if (!data.length) return { path: '', bars: [] }
    const values = data.map((row) => Number(row.settled_bankroll ?? 0))
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = Math.max(1, max - min)
    const x = (index) => padding + ((width - padding * 2) * index) / Math.max(1, data.length - 1)
    const y = (value) => height - padding - ((height - padding * 2) * (value - min)) / span
    const curve = data
      .map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(2)} ${y(Number(row.settled_bankroll ?? 0)).toFixed(2)}`)
      .join(' ')
    const pnlBars = data.map((row, index) => {
      const pnl = Number(row.total_real_pnl ?? 0)
      const barHeight = Math.min(60, Math.abs(pnl) * 0.9)
      return {
        x: x(index) - 2,
        y: pnl >= 0 ? height - padding - barHeight : height - padding,
        h: barHeight,
        color: pnl >= 0 ? '#cf4f24' : '#111111'
      }
    })
    return { path: curve, bars: pnlBars }
  }, [data])

  if (!data.length) return <div className="empty">暂无资金曲线</div>

  return (
    <div className="curve-shell">
      <div className="curve-meta">展示区间：{startDate} 起</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="curve-svg">
        <rect x="0" y="0" width={width} height={height} rx="18" fill="rgba(255,255,255,0.02)" />
        {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
          <line
            key={ratio}
            x1={padding}
            x2={width - padding}
            y1={padding + (height - padding * 2) * ratio}
            y2={padding + (height - padding * 2) * ratio}
            stroke="rgba(27, 18, 12, 0.12)"
            strokeDasharray="6 6"
          />
        ))}
        {bars.map((bar, index) => (
          <rect key={index} x={bar.x} y={bar.y} width="4" height={bar.h} fill={bar.color} opacity="0.48" rx="2" />
        ))}
        <path d={path} fill="none" stroke="#111111" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <div className="curve-axis">
        {data.filter((_, index) => index % Math.max(1, Math.floor(data.length / 7)) === 0).map((row) => (
          <span key={row.date}>{row.date}</span>
        ))}
      </div>
    </div>
  )
}

function ActionCard({ item }) {
  const selection = item.selection || {}
  return (
    <article className="action-card">
      <div className="action-head">
        <span className="chip chip-alert">{lineLabel(item.line_name)}</span>
        <span className="action-issue">下期 {item.draw_issue}</span>
      </div>
      <div className="action-title">期位 {item.slot_1based}</div>
      <div className="action-body">
        {'sum_value' in selection ? <span>和值 {selection.sum_value}</span> : null}
        {'number' in selection ? <span>号码 {selection.number}</span> : null}
        {'position_1based' in selection ? <span>位置 {selection.position_1based}</span> : null}
        {'source' in selection ? <span>{selection.source}</span> : null}
        {'big_positions' in selection ? <span>大位 {selection.big_positions.join(',')}</span> : null}
        {'small_positions' in selection ? <span>小位 {selection.small_positions.join(',')}</span> : null}
      </div>
      <div className="action-money">{fmtNumber(item.total_cost)} 分</div>
      <div className="action-note">{item.odds_display}</div>
    </article>
  )
}

function LinePanel({ label, state, fixedStake = false }) {
  const requested = state?.requested_slots ?? 0
  const funded = state?.funded_slots ?? 0
  const executed = state?.executed_slots ?? 0
  const pending = state?.pending_slots ?? 0

  return (
    <section className="line-panel">
      <div className="line-header">
        <div>
          <div className="line-name">{label}</div>
          <div className="line-message">{state?.message || '无数据'}</div>
        </div>
        <div className="line-badge">{state?.status || 'idle'}</div>
      </div>
      <div className="line-grid">
        <MiniStat label="档位" value={fixedStake ? '固定 10' : `${state?.multiplier_value ?? 0}x`} />
        <MiniStat label="请求" value={requested} />
        <MiniStat label="成交" value={funded} />
        <MiniStat label="已执行" value={executed} />
        <MiniStat label="待执行" value={pending} />
        <MiniStat label="浮动盈亏" value={fmtNumber(state?.provisional_pnl)} accent={Number(state?.provisional_pnl) >= 0 ? 'positive' : 'negative'} />
      </div>
    </section>
  )
}

function BroadcastHistory({ pageData, onPageChange, issueInput, onIssueInputChange, onIssueSubmit, onIssueClear }) {
  const rows = pageData.rows || []

  return (
    <section className="history-card history-card-wide">
      <div className="history-heading">
        <div>
          <div className="history-title">播报记录历史</div>
          <div className="history-subhead">这里只保留 2026-04-20 起真实可执行的投注播报，不再记录窗口开启、空仓或等待判窗这类状态快照。</div>
        </div>
        <form className="history-search" onSubmit={onIssueSubmit}>
          <label className="history-search-label" htmlFor="broadcast-issue-search">按期号直查</label>
          <div className="history-search-row">
            <input
              id="broadcast-issue-search"
              className="history-search-input"
              inputMode="numeric"
              placeholder="输入 33984657 或 33984658"
              value={issueInput}
              onChange={(event) => onIssueInputChange(event.target.value)}
            />
            <button type="submit" className="search-button">检索</button>
            <button type="button" className="search-button ghost" onClick={onIssueClear}>清空</button>
          </div>
        </form>
      </div>
      <div className="history-table-shell">
        {rows.length === 0 ? <div className="empty">{pageData.issue ? `未找到与 ${pageData.issue} 相关的播报` : '暂无记录'}</div> : null}
        {rows.length > 0 ? (
          <table className="bet-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>日期</th>
                <th>玩法</th>
                <th>触发开奖期号</th>
                <th>播报目标期号</th>
                <th>状态</th>
                <th>播报内容</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const payload = parseMaybeJson(row.payload_json) || {}
                return (
                  <tr key={`broadcast-${row.id}`}>
                    <td>{row.server_time || '—'}</td>
                    <td>{row.draw_date || '—'}</td>
                    <td>{lineLabel(row.line_name)}</td>
                    <td>{row.pre_draw_issue || '—'}</td>
                    <td>{row.draw_issue || '—'}</td>
                    <td>{broadcastStatusLabel(row)}</td>
                    <td>{broadcastContentSummary(row)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : null}
      </div>
      <Pagination
        page={pageData.page || 1}
        totalPages={pageData.total_pages || 1}
        total={pageData.total || 0}
        hasPrev={pageData.has_prev}
        hasNext={pageData.has_next}
        onChange={onPageChange}
      />
    </section>
  )
}

function ContributionInline({ contribution }) {
  return (
    <section className="contribution-inline">
      <strong>分项贡献：</strong>
      <span>双面已结算 {fmtNumber(contribution?.settled?.face)}</span>
      <span>冠亚和已结算 {fmtNumber(contribution?.settled?.sum)}</span>
      <span>定位胆已结算 {fmtNumber(contribution?.settled?.exact)}</span>
      <span>双面今日浮动 {fmtNumber(contribution?.today_provisional?.face)}</span>
      <span>冠亚和今日浮动 {fmtNumber(contribution?.today_provisional?.sum)}</span>
      <span>定位胆今日浮动 {fmtNumber(contribution?.today_provisional?.exact)}</span>
    </section>
  )
}

function buildPaginationItems(page, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }
  if (page <= 4) {
    return [1, 2, 3, 4, 5, 'ellipsis-right', totalPages]
  }
  if (page >= totalPages - 3) {
    return [1, 'ellipsis-left', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages]
  }
  return [1, 'ellipsis-left', page - 1, page, page + 1, 'ellipsis-right', totalPages]
}

function Pagination({ page, totalPages, total, onChange, hasPrev, hasNext }) {
  const pageItems = buildPaginationItems(page, totalPages)

  return (
    <div className="pagination">
      <div className="pagination-summary">第 {page} / {totalPages} 页，共 {total} 条</div>
      <div className="pagination-actions">
        <button type="button" className="page-button" disabled={!hasPrev} onClick={() => onChange(page - 1)}>
          上一页
        </button>
        {pageItems.map((value) =>
          typeof value === 'number' ? (
            <button
              type="button"
              key={value}
              className={`page-button ${value === page ? 'active' : ''}`}
              onClick={() => onChange(value)}
            >
              {value}
            </button>
          ) : (
            <span key={value} className="page-ellipsis">
              …
            </span>
          )
        )}
        <button type="button" className="page-button" disabled={!hasNext} onClick={() => onChange(page + 1)}>
          下一页
        </button>
      </div>
    </div>
  )
}

function BetHistory({ pageData, onPageChange, betScope, onScopeChange }) {
  const rows = pageData.rows || []
  const counts = pageData.counts || { all: 0, broadcasted: 0, pending_future: 0 }

  return (
    <section className="history-card history-card-wide">
      <div className="history-heading">
        <div>
          <div className="history-title">投注历史记录</div>
          <div className="history-subhead">
            只展示 2026-04-20 起的模拟账本。已播报执行 {counts.broadcasted ?? 0} 条，未触发待执行 {counts.pending_future ?? 0} 条。
          </div>
        </div>
        <div className="scope-tabs">
          {[
            ['all', '全部'],
            ['broadcasted', '已播报'],
            ['pending_future', '未触发待执行']
          ].map(([value, label]) => (
            <button
              type="button"
              key={value}
              className={`scope-tab ${betScope === value ? 'active' : ''}`}
              onClick={() => {
                onPageChange(1)
                onScopeChange(value)
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="history-table-shell">
        {rows.length === 0 ? <div className="empty">暂无记录</div> : null}
        {rows.length > 0 ? (
          <table className="bet-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>开奖期号</th>
                <th>期位</th>
                <th>双面</th>
                <th>冠亚和</th>
                <th>定位胆</th>
                <th>状态</th>
                <th>播报状态</th>
                <th>播报时间</th>
                <th>开奖时间</th>
                <th>开奖号码</th>
                <th>赔率说明</th>
                <th>投注金额</th>
                <th>盈亏</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`bet-${row.id}`}>
                  <td>{row.draw_date}</td>
                  <td>{row.pre_draw_issue || '—'}</td>
                  <td>期位 {row.slot_1based}</td>
                  <td>{lineSelection(row, 'face')}</td>
                  <td>{lineSelection(row, 'sum')}</td>
                  <td>{lineSelection(row, 'exact')}</td>
                  <td>{statusLabel(row.status)}</td>
                  <td>{broadcastStateLabel(row.broadcast_state)}</td>
                  <td>{row.broadcast_time || '—'}</td>
                  <td>{row.pre_draw_time || '—'}</td>
                  <td>{row.pre_draw_code || '—'}</td>
                  <td>{row.odds_display}</td>
                  <td>{fmtNumber(row.total_cost)} 分</td>
                  <td className={row.pnl == null ? '' : Number(row.pnl) >= 0 ? 'positive-text' : 'negative-text'}>
                    {row.pnl == null ? '—' : `${fmtNumber(row.pnl)} 分`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
      <Pagination
        page={pageData.page || 1}
        totalPages={pageData.total_pages || 1}
        total={pageData.total || 0}
        hasPrev={pageData.has_prev}
        hasNext={pageData.has_next}
        onChange={onPageChange}
      />
    </section>
  )
}

export default function App() {
  const {
    dashboard,
    curveRows,
    betPageData,
    betPage,
    setBetPage,
    betScope,
    setBetScope,
    broadcastPageData,
    broadcastPage,
    setBroadcastPage,
    setBroadcastIssueQuery,
    broadcastIssueInput,
    setBroadcastIssueInput
  } = useDashboard()

  if (!dashboard) {
    return <div className="loading">正在拉取 PK10 实时积分面板…</div>
  }

  const currentActions = dashboard.current_actions || []
  const todayPlan = dashboard.today_plan || {}
  const totals = dashboard.totals || {}
  const market = dashboard.market || {}
  const contribution = dashboard.contributions || {}
  const ranges = dashboard.ranges || {}
  const simulationStartDate = ranges.simulation_start_date || CURVE_START_DATE
  const historyStartDate = ranges.history_start_date || '2026-01-01'

  function handleBroadcastIssueSubmit(event) {
    event.preventDefault()
    setBroadcastPage(1)
    setBroadcastIssueQuery(String(broadcastIssueInput || '').trim())
  }

  function handleBroadcastIssueClear() {
    setBroadcastIssueInput('')
    setBroadcastPage(1)
    setBroadcastIssueQuery('')
  }

  return (
    <main className="page">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">PK10 LIVE / SHARED BANKROLL</p>
          <h1>三线共享资金池实时面板</h1>
          <p className="hero-text">
            双面与冠亚和都走日级马丁 1-2-4-5，定位胆固定 10。窗口预热从 {historyStartDate} 开始，模拟投注从 {simulationStartDate} 开始；页面每次拿到最新开奖后，都会同步刷新当前积分、待执行动作和真实可投播报。
          </p>
        </div>
        <div className="hero-right">
          <div className="hero-badge">blackout 06:00-07:00</div>
          <div className="hero-market">
            <span>当前期开奖 {market.pre_draw_issue}</span>
            <span>下期开奖 {market.draw_issue}</span>
            <span>serverTime {market.server_time}</span>
            <span>窗口预热 {historyStartDate} 起</span>
            <span>模拟投注 {simulationStartDate} 起</span>
          </div>
        </div>
      </header>

      <section className="hero-metrics">
        <MiniStat label="已结算总积分" value={fmtNumber(totals.settled_bankroll)} accent="primary" />
        <MiniStat label="今日浮盈" value={fmtNumber(totals.today_provisional_pnl)} accent={Number(totals.today_provisional_pnl) >= 0 ? 'positive' : 'negative'} />
        <MiniStat label="若此刻收盘" value={fmtNumber(totals.estimated_close_bankroll)} accent="primary" />
        <MiniStat label="峰值回撤" value={fmtNumber(totals.max_drawdown)} accent="negative" />
        <MiniStat label="最低资金" value={fmtNumber(totals.min_bankroll)} />
        <MiniStat label="峰值资金" value={fmtNumber(totals.peak_bankroll)} />
      </section>

      <ContributionInline contribution={contribution} />

      <section className="layout">
        <div className="main-column">
          <section className="card card-actions">
            <div className="section-head">
              <div>
                <div className="section-eyebrow">CURRENT ACTIONS</div>
                <h2>投注播报</h2>
              </div>
              <div className="section-note">如果当前没有可执行窗口，这里会明确显示“无可投注选项”。</div>
            </div>
            <div className="action-grid">
              {currentActions.some((item) => item.slot_1based) ? (
                currentActions.filter((item) => item.slot_1based).map((item) => <ActionCard key={`${item.line_name}-${item.slot_1based}`} item={item} />)
              ) : (
                <div className="empty hero-empty">无可投注选项</div>
              )}
            </div>
          </section>

          <section className="card">
            <div className="section-head">
              <div>
                <div className="section-eyebrow">BANKROLL CURVE</div>
                <h2>日维资金曲线</h2>
              </div>
              <div className="section-note">从 {simulationStartDate} 起展示，含今日 provisional 标记。</div>
            </div>
            <EquityCurve rows={curveRows} startDate={simulationStartDate} />
          </section>

          <div className="three-grid">
            <LinePanel label="双面" state={todayPlan.face} />
            <LinePanel label="冠亚和" state={todayPlan.sum} />
            <LinePanel label="定位胆" state={todayPlan.exact} fixedStake />
          </div>

          <BetHistory pageData={betPageData} onPageChange={setBetPage} page={betPage} betScope={betScope} onScopeChange={setBetScope} />
          <BroadcastHistory
            pageData={broadcastPageData}
            onPageChange={setBroadcastPage}
            page={broadcastPage}
            issueInput={broadcastIssueInput}
            onIssueInputChange={setBroadcastIssueInput}
            onIssueSubmit={handleBroadcastIssueSubmit}
            onIssueClear={handleBroadcastIssueClear}
          />
        </div>
      </section>
    </main>
  )
}
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_live_dashboard/frontend/src/styles.css`

```css
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Noto+Sans+SC:wght@400;500;700;900&display=swap');

:root {
  --bg: #f6efe3;
  --paper: rgba(255, 250, 241, 0.78);
  --ink: #1f1611;
  --muted: rgba(31, 22, 17, 0.62);
  --line: rgba(31, 22, 17, 0.12);
  --accent: #cf4f24;
  --accent-soft: rgba(207, 79, 36, 0.14);
  --success: #147357;
  --danger: #a62822;
  --shadow: 0 24px 80px rgba(33, 20, 10, 0.12);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  background:
    radial-gradient(circle at 0% 0%, rgba(207, 79, 36, 0.08), transparent 32%),
    radial-gradient(circle at 100% 100%, rgba(20, 115, 87, 0.08), transparent 28%),
    linear-gradient(180deg, #f9f4eb 0%, #f2e6d2 100%);
  font-family: 'Noto Sans SC', sans-serif;
}

.page {
  position: relative;
  padding: 32px;
  overflow: hidden;
}

.ambient {
  position: absolute;
  width: 420px;
  height: 420px;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.65;
  pointer-events: none;
}

.ambient-left {
  top: -120px;
  left: -120px;
  background: rgba(207, 79, 36, 0.16);
}

.ambient-right {
  right: -120px;
  bottom: 0;
  background: rgba(20, 115, 87, 0.12);
}

.hero,
.card,
.line-panel,
.mini-stat,
.history-card {
  backdrop-filter: blur(12px);
}

.hero {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 24px;
  padding: 28px 30px;
  border: 1px solid rgba(31, 22, 17, 0.08);
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(255, 248, 240, 0.92), rgba(248, 234, 214, 0.74));
  box-shadow: var(--shadow);
}

.eyebrow,
.section-eyebrow {
  margin: 0 0 8px;
  color: var(--accent);
  letter-spacing: 0.24em;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.hero h1,
.section-head h2,
.line-name {
  font-family: 'Bebas Neue', cursive;
  letter-spacing: 0.04em;
}

.hero h1 {
  margin: 0;
  font-size: clamp(48px, 7vw, 88px);
  line-height: 0.92;
}

.hero-text {
  max-width: 54ch;
  font-size: 15px;
  line-height: 1.75;
  color: var(--muted);
}

.hero-right {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
}

.hero-badge {
  padding: 12px 18px;
  border-radius: 999px;
  background: var(--ink);
  color: white;
  font-weight: 700;
}

.hero-market {
  display: grid;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
  text-align: right;
}

.hero-metrics {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.mini-stat {
  padding: 18px;
  border-radius: 22px;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: 0 10px 30px rgba(20, 12, 7, 0.06);
}

.mini-label,
.mini-note,
.section-note,
.line-message,
.history-sub,
.history-time,
.action-note,
.curve-axis span {
  color: var(--muted);
}

.mini-value {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 900;
  letter-spacing: -0.04em;
}

.mini-value.primary {
  color: var(--ink);
}

.mini-value.positive {
  color: var(--success);
}

.mini-value.negative {
  color: var(--danger);
}

.layout {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  margin-top: 18px;
}

.main-column {
  display: grid;
  gap: 18px;
}

.contribution-inline {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin-top: 14px;
  padding: 0 4px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}

.contribution-inline strong {
  color: var(--ink);
}

.card,
.history-card,
.line-panel {
  border: 1px solid var(--line);
  border-radius: 28px;
  background: var(--paper);
  box-shadow: 0 18px 48px rgba(24, 15, 8, 0.08);
}

.card {
  padding: 22px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}

.section-head h2 {
  margin: 0;
  font-size: 32px;
  line-height: 1;
}

.section-note {
  max-width: 34ch;
  text-align: right;
  font-size: 13px;
  line-height: 1.5;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.action-card {
  padding: 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.56);
  border: 1px solid rgba(31, 22, 17, 0.1);
}

.action-head,
.line-header,
.contribution-row,
.history-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chip {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.chip-alert {
  background: var(--accent-soft);
  color: var(--accent);
}

.action-issue,
.line-badge {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
}

.action-title {
  margin-top: 14px;
  font-size: 28px;
  font-weight: 900;
}

.action-body {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 10px;
  font-size: 14px;
}

.action-money {
  margin-top: 18px;
  font-size: 26px;
  font-weight: 900;
}

.curve-shell {
  margin-top: 16px;
  border-radius: 22px;
  padding: 12px 12px 0;
  background: rgba(255, 255, 255, 0.42);
}

.curve-meta {
  padding: 4px 12px 10px;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.curve-svg {
  width: 100%;
  height: auto;
}

.curve-axis {
  display: flex;
  justify-content: space-between;
  padding: 0 12px 14px;
  font-size: 12px;
}

.three-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.line-panel {
  padding: 18px;
}

.line-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.line-name {
  font-size: 28px;
}

.history-card {
  padding: 18px;
}

.history-card-wide {
  padding-bottom: 16px;
}

.history-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}

.history-search {
  display: grid;
  gap: 8px;
  min-width: min(100%, 420px);
}

.history-search-label {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  text-align: right;
}

.history-search-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.history-search-input {
  flex: 1 1 220px;
  min-width: 180px;
  padding: 11px 14px;
  border: 1px solid rgba(31, 22, 17, 0.12);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  color: var(--ink);
  font: inherit;
  font-size: 14px;
  outline: none;
  transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
}

.history-search-input:focus {
  border-color: rgba(207, 79, 36, 0.52);
  box-shadow: 0 0 0 4px rgba(207, 79, 36, 0.12);
}

.search-button {
  padding: 10px 14px;
  border: 1px solid var(--ink);
  border-radius: 999px;
  background: var(--ink);
  color: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 140ms ease, opacity 140ms ease, background 140ms ease, border-color 140ms ease;
}

.search-button:hover {
  transform: translateY(-1px);
}

.search-button.ghost {
  border-color: rgba(31, 22, 17, 0.16);
  background: rgba(255, 255, 255, 0.76);
  color: var(--ink);
}

.history-title {
  margin-bottom: 0;
  font-family: 'Bebas Neue', cursive;
  font-size: 28px;
  letter-spacing: 0.04em;
}

.scope-tabs {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.scope-tab {
  padding: 9px 14px;
  border: 1px solid rgba(31, 22, 17, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
}

.scope-tab:hover {
  transform: translateY(-1px);
  border-color: rgba(31, 22, 17, 0.28);
}

.scope-tab.active {
  background: var(--ink);
  color: #fff;
  border-color: var(--ink);
}

.history-subhead {
  max-width: 32ch;
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted);
  text-align: right;
}

.history-table {
  display: grid;
  gap: 10px;
  max-height: 360px;
  overflow: auto;
}

.history-table-shell {
  margin-top: 6px;
  max-height: 420px;
  overflow: auto;
  border: 1px solid rgba(31, 22, 17, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.42);
}

.history-row {
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(31, 22, 17, 0.08);
}

.history-row-bet {
  grid-template-columns: minmax(0, 1.1fr) repeat(3, minmax(0, 0.55fr)) 140px;
  align-items: center;
}

.bet-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1280px;
  font-size: 13px;
}

.bet-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 12px 14px;
  text-align: left;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--muted);
  text-transform: uppercase;
  background: rgba(246, 239, 227, 0.96);
  border-bottom: 1px solid rgba(31, 22, 17, 0.12);
}

.bet-table tbody td {
  padding: 13px 14px;
  vertical-align: top;
  border-bottom: 1px solid rgba(31, 22, 17, 0.08);
}

.bet-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.36);
}

.history-main {
  font-weight: 800;
}

.history-meta {
  font-size: 13px;
  font-weight: 700;
}

.history-stack {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
}

.history-stack-strong {
  font-weight: 700;
  color: var(--ink);
}

.positive-text {
  color: var(--success);
}

.negative-text {
  color: var(--danger);
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}

.pagination-summary {
  font-size: 13px;
  color: var(--muted);
}

.pagination-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.page-button {
  padding: 8px 12px;
  border: 1px solid rgba(31, 22, 17, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
}

.page-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: rgba(31, 22, 17, 0.28);
}

.page-button.active {
  background: var(--ink);
  color: white;
  border-color: var(--ink);
}

.page-button:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.page-ellipsis {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  color: var(--muted);
  font-size: 16px;
  font-weight: 800;
}

@media (max-width: 980px) {
  .history-heading {
    align-items: stretch;
  }

  .history-search {
    min-width: 0;
  }

  .history-search-label {
    text-align: left;
  }

  .history-search-row {
    justify-content: stretch;
    flex-wrap: wrap;
  }

  .history-search-input {
    min-width: 0;
    width: 100%;
  }
}

.empty {
  padding: 24px;
  border-radius: 18px;
  border: 1px dashed rgba(31, 22, 17, 0.16);
  color: var(--muted);
}

.hero-empty {
  background: rgba(255, 255, 255, 0.4);
}

.loading {
  display: grid;
  place-items: center;
  min-height: 100vh;
  font-size: 18px;
}

@media (max-width: 1200px) {
  .hero,
  .layout,
  .three-grid,
  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .hero-right,
  .section-note,
  .history-subhead {
    align-items: flex-start;
    text-align: left;
  }

  .history-row-bet {
    grid-template-columns: 1fr;
  }

  .pagination {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 760px) {
  .page {
    padding: 18px;
  }

  .hero {
    padding: 22px;
  }

  .hero h1 {
    font-size: 56px;
  }

  .mini-value {
    font-size: 24px;
  }

  .history-heading {
    flex-direction: column;
    align-items: flex-start;
  }

  .scope-tabs {
    justify-content: flex-start;
  }
}
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_three_play_2025_replay.py`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ROUND30_DAILY = (
    ROOT_DIR
    / "pk10_round30_daily85_exact_transfer"
    / "round30_outputs"
    / "round30_transfer_daily.csv"
)

SUM_OUTPUT_DIR = (
    ROOT_DIR
    / "pk10_number_sum_validation"
    / "number_sum_intraday_gate_outputs_db6y_daily85"
)
SUM_GATE_SUMMARY = SUM_OUTPUT_DIR / "intraday_gate_summary.csv"

NEGATIVE_DISCOUNT = 0.85
BS_SCENARIO = "bs_guardrail_daily85"
BS_OE_SCENARIO = "bs_plus_oe_mode_non_cash_daily85"
BS_SOURCE_STAKE = 50.0
DEFAULT_SIM_START = "2025-01-01"
DEFAULT_SIM_END = "2025-12-31"
DEFAULT_BANKROLL = 1000.0
DEFAULT_BASE_STAKE = 10.0
DEFAULT_SUM_CANDIDATE = "intraday_1007"
DEFAULT_MAX_MULTIPLIER = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a shared-bankroll three-play PK10 path for calendar year 2025.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--sum-candidate-id", default=DEFAULT_SUM_CANDIDATE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    return parser.parse_args()


def next_multiplier(current: int, max_multiplier: int, last_real_pnl: float) -> int:
    if last_real_pnl < 0.0:
        if current < 2:
            return min(2, max_multiplier)
        if current < 4:
            return min(4, max_multiplier)
        return min(5, max_multiplier)
    return 1


def settle_real(book_pnl_units: float) -> float:
    if book_pnl_units >= 0.0:
        return float(book_pnl_units)
    return float(book_pnl_units * NEGATIVE_DISCOUNT)


def load_bs_oe_frame(sim_start: pd.Timestamp, sim_end: pd.Timestamp, base_stake: float) -> pd.DataFrame:
    scale = base_stake / BS_SOURCE_STAKE
    raw = pd.read_csv(ROUND30_DAILY, parse_dates=["date"])
    keep = raw[raw["scenario"].isin([BS_SCENARIO, BS_OE_SCENARIO])].copy()
    pivot = (
        keep.pivot_table(index="date", columns="scenario", values="daily_real_pnl", aggfunc="first")
        .sort_index()
        .fillna(0.0)
    )
    date_range = pd.date_range(sim_start, sim_end, freq="D")
    pivot = pivot.reindex(date_range, fill_value=0.0)
    bs_base = pivot.get(BS_SCENARIO, pd.Series(0.0, index=date_range)).astype(float) * scale
    combo_base = pivot.get(BS_OE_SCENARIO, pd.Series(0.0, index=date_range)).astype(float) * scale
    out = pd.DataFrame(
        {
            "date": date_range,
            "bs_base_real_pnl": bs_base.values,
            "oe_base_real_pnl": (combo_base - bs_base).values,
        }
    )
    return out


def gate_is_on(day_row: pd.Series, candidate_row: pd.Series) -> bool:
    if float(day_row["requested_slots"]) <= 0.0:
        return False
    if float(day_row["selected_mean_edge"]) > float(candidate_row["mean_edge_cap"]):
        return False

    gate_family = str(candidate_row["gate_family"])
    raw_high = float(day_row["preview_raw_high_bias"])
    mid_share = float(day_row["preview_mid_share"])
    mean_sum = float(day_row["preview_mean_sum"])

    if gate_family == "high_only":
        return raw_high >= float(candidate_row["raw_high_threshold"])
    if gate_family == "high_mean":
        return raw_high >= float(candidate_row["raw_high_threshold"]) and mean_sum >= float(candidate_row["mean_sum_threshold"])
    if gate_family == "high_mid":
        return raw_high >= float(candidate_row["raw_high_threshold"]) and mid_share >= float(candidate_row["mid_share_threshold"])
    if gate_family == "mid_only":
        return mid_share >= float(candidate_row["mid_share_threshold"])
    raise ValueError(f"Unknown gate family: {gate_family}")


def load_sum_inputs(
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    candidate_id: str,
) -> tuple[pd.Series, pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    summary_df = pd.read_csv(SUM_GATE_SUMMARY)
    matched = summary_df[summary_df["candidate_id"] == candidate_id].copy()
    if matched.empty:
        raise ValueError(f"Missing intraday candidate: {candidate_id}")
    candidate_row = matched.iloc[0]

    baseline_name = str(candidate_row["baseline_name"])
    preview_cut = int(candidate_row["preview_cut"])
    detail_path = SUM_OUTPUT_DIR / f"{baseline_name}_cut{preview_cut}_intraday_detail.csv"
    detail_df = pd.read_csv(detail_path, parse_dates=["date"])

    grouped = (
        detail_df.groupby(["date", "split"], as_index=False)
        .agg(
            requested_slots=("slot", "size"),
            selected_score=("score_value", "mean"),
            selected_mean_edge=("mean_edge_value", "mean"),
            selected_symmetry_gap=("symmetry_gap_value", "mean"),
            preview_raw_high_bias=("preview_raw_high_bias", "mean"),
            preview_mid_share=("preview_mid_share", "mean"),
            preview_mean_sum=("preview_mean_sum", "mean"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    grouped["active"] = grouped.apply(lambda row: gate_is_on(row, candidate_row), axis=1)

    date_range = pd.date_range(sim_start, sim_end, freq="D")
    daily_frame = pd.DataFrame({"date": date_range}).merge(grouped, on="date", how="left")
    daily_frame["split"] = daily_frame["split"].fillna("out_of_sample_gap")
    for col in [
        "requested_slots",
        "selected_score",
        "selected_mean_edge",
        "selected_symmetry_gap",
        "preview_raw_high_bias",
        "preview_mid_share",
        "preview_mean_sum",
    ]:
        daily_frame[col] = daily_frame[col].fillna(0.0)
    daily_frame["active"] = daily_frame["active"].fillna(False).astype(bool)

    sorted_details = detail_df.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in sorted_details.groupby("date")}
    return candidate_row, daily_frame, picks_by_date


def replay_three_play(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)
    max_multiplier = max(1, int(args.max_multiplier))

    bs_oe_frame = load_bs_oe_frame(sim_start=sim_start, sim_end=sim_end, base_stake=float(args.base_stake))
    sum_candidate_row, sum_frame, sum_picks_by_date = load_sum_inputs(
        sim_start=sim_start,
        sim_end=sim_end,
        candidate_id=args.sum_candidate_id,
    )

    combined = bs_oe_frame.merge(sum_frame, on="date", how="left")

    bankroll = float(args.start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0
    bs_multiplier = 1
    sum_multiplier = 1
    skipped_sum_due_to_cash = 0

    bs_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    sum_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    rows: list[dict[str, object]] = []

    for _, row in combined.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll

        bs_base_real = float(row["bs_base_real_pnl"])
        oe_base_real = float(row["oe_base_real_pnl"])
        bs_active = abs(bs_base_real) > 1e-12
        applied_bs_multiplier = bs_multiplier if bs_active else 0
        bs_real = bs_base_real * applied_bs_multiplier
        oe_real = oe_base_real
        if bs_active:
            bs_ladder_counts[bs_multiplier] += 1

        sum_requested_slots = int(row["requested_slots"]) if bool(row["active"]) else 0
        sum_funded_slots = 0
        sum_book_units = 0.0
        sum_real = 0.0
        affordable_sum_slots = int(bankroll_before // (float(args.base_stake) * sum_multiplier)) if sum_multiplier > 0 else 0

        if sum_requested_slots > 0:
            sum_funded_slots = min(sum_requested_slots, affordable_sum_slots)
            if sum_funded_slots > 0:
                picks = sum_picks_by_date.get(day, pd.DataFrame()).head(sum_funded_slots).copy()
                sum_book_units = float(picks["book_pnl"].sum()) if not picks.empty else 0.0
                sum_real = settle_real(sum_book_units * sum_multiplier) * float(args.base_stake)
                sum_ladder_counts[sum_multiplier] += 1
            else:
                skipped_sum_due_to_cash += 1

        total_real = bs_real + oe_real + sum_real
        bankroll += total_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "bs_active": bs_active,
                "bs_base_real_pnl": bs_base_real,
                "bs_multiplier": applied_bs_multiplier,
                "bs_real_pnl": bs_real,
                "oe_real_pnl": oe_real,
                "sum_active": bool(sum_requested_slots > 0),
                "sum_requested_slots": sum_requested_slots,
                "sum_affordable_slots": affordable_sum_slots,
                "sum_funded_slots": sum_funded_slots,
                "sum_multiplier": sum_multiplier if sum_requested_slots > 0 else 0,
                "sum_book_pnl_units": sum_book_units,
                "sum_real_pnl": sum_real,
                "total_real_pnl": total_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
                "sum_preview_raw_high_bias": float(row["preview_raw_high_bias"]),
                "sum_preview_mid_share": float(row["preview_mid_share"]),
                "sum_preview_mean_sum": float(row["preview_mean_sum"]),
            }
        )

        if bs_active:
            bs_multiplier = next_multiplier(bs_multiplier, max_multiplier=max_multiplier, last_real_pnl=bs_real)
        if sum_funded_slots > 0:
            sum_multiplier = next_multiplier(sum_multiplier, max_multiplier=max_multiplier, last_real_pnl=sum_real)

    daily_df = pd.DataFrame(rows)
    daily_df["month"] = daily_df["date"].dt.to_period("M").astype(str)
    monthly_df = (
        daily_df.groupby("month", as_index=False)
        .agg(
            bs_real_pnl=("bs_real_pnl", "sum"),
            oe_real_pnl=("oe_real_pnl", "sum"),
            sum_real_pnl=("sum_real_pnl", "sum"),
            total_real_pnl=("total_real_pnl", "sum"),
            bs_active_days=("bs_active", "sum"),
            sum_active_days=("sum_active", "sum"),
            sum_funded_slots=("sum_funded_slots", "sum"),
            month_end_bankroll=("bankroll_after_day", "last"),
            min_drawdown_from_peak=("drawdown_from_peak", "min"),
        )
    )

    summary_df = pd.DataFrame(
        [
            {
                "sim_start": str(sim_start.date()),
                "sim_end": str(sim_end.date()),
                "start_bankroll": float(args.start_bankroll),
                "base_stake": float(args.base_stake),
                "max_multiplier": max_multiplier,
                "sum_candidate_id": args.sum_candidate_id,
                "sum_gate_family": str(sum_candidate_row["gate_family"]),
                "sum_baseline_name": str(sum_candidate_row["baseline_name"]),
                "sum_preview_cut": int(sum_candidate_row["preview_cut"]),
                "days_in_simulation": int(daily_df.shape[0]),
                "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
                "net_profit": float(daily_df["total_real_pnl"].sum()),
                "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / float(args.start_bankroll) - 1.0) * 100.0),
                "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
                "min_bankroll": float(daily_df["bankroll_after_day"].min()),
                "max_drawdown": float(max_drawdown),
                "bs_profit": float(daily_df["bs_real_pnl"].sum()),
                "oe_profit": float(daily_df["oe_real_pnl"].sum()),
                "sum_profit": float(daily_df["sum_real_pnl"].sum()),
                "bs_active_days": int(daily_df["bs_active"].sum()),
                "sum_active_days": int(daily_df["sum_active"].sum()),
                "sum_funded_slots": int(daily_df["sum_funded_slots"].sum()),
                "skipped_sum_due_to_cash": skipped_sum_due_to_cash,
                "bs_days_1x": bs_ladder_counts[1],
                "bs_days_2x": bs_ladder_counts[2],
                "bs_days_4x": bs_ladder_counts[4],
                "bs_days_5x": bs_ladder_counts[5],
                "sum_days_1x": sum_ladder_counts[1],
                "sum_days_2x": sum_ladder_counts[2],
                "sum_days_4x": sum_ladder_counts[4],
                "sum_days_5x": sum_ladder_counts[5],
            }
        ]
    )
    return daily_df, monthly_df, summary_df


def write_report(path: Path, summary: pd.Series, monthly_df: pd.DataFrame) -> None:
    lines: list[str] = []
    lines.append("# Round36 Three-Play 2025 Replay")
    lines.append("")
    lines.append("- Shared bankroll across `big/small + odd/even + number-sum`.")
    lines.append("- Big/small uses `1x -> 2x -> 4x -> 5x`.")
    lines.append("- Odd/even stays fixed `1x` and is taken from the deployed `round32` daily mix.")
    lines.append("- Number-sum uses the intraday gate candidate listed in the summary, with its own independent `1x -> 2x -> 4x -> 5x` ladder.")
    lines.append("- `round32` source trace is linearly rescaled from stake `50` to stake `10`; this preserves the existing day-level settlement logic.")
    lines.append("")
    lines.append("## Summary")
    lines.append(
        f"- period `{summary['sim_start']} -> {summary['sim_end']}`, start bankroll `{summary['start_bankroll']:.2f}`, "
        f"base stake `{summary['base_stake']:.2f}`, final bankroll `{summary['final_bankroll']:.2f}`, "
        f"net profit `{summary['net_profit']:.2f}`, ROI `{summary['roi_on_start_bankroll_pct']:.2f}%`."
    )
    lines.append(
        f"- peak `{summary['peak_bankroll']:.2f}`, min bankroll `{summary['min_bankroll']:.2f}`, "
        f"max drawdown `{summary['max_drawdown']:.2f}`."
    )
    lines.append(
        f"- contribution split: BS `{summary['bs_profit']:.2f}`, OE `{summary['oe_profit']:.2f}`, "
        f"SUM `{summary['sum_profit']:.2f}`."
    )
    lines.append(
        f"- BS ladder days `1x={int(summary['bs_days_1x'])}, 2x={int(summary['bs_days_2x'])}, 4x={int(summary['bs_days_4x'])}, 5x={int(summary['bs_days_5x'])}`."
    )
    lines.append(
        f"- SUM ladder days `1x={int(summary['sum_days_1x'])}, 2x={int(summary['sum_days_2x'])}, 4x={int(summary['sum_days_4x'])}, 5x={int(summary['sum_days_5x'])}`."
    )
    lines.append("")
    lines.append("## Monthly")
    for _, row in monthly_df.iterrows():
        lines.append(
            f"- `{row['month']}` total `{row['total_real_pnl']:.2f}` "
            f"(BS `{row['bs_real_pnl']:.2f}`, OE `{row['oe_real_pnl']:.2f}`, SUM `{row['sum_real_pnl']:.2f}`), "
            f"month-end bankroll `{row['month_end_bankroll']:.2f}`."
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    daily_df, monthly_df, summary_df = replay_three_play(args)
    summary = summary_df.iloc[0]
    sim_start_txt = str(pd.Timestamp(args.sim_start).date())
    sim_end_txt = str(pd.Timestamp(args.sim_end).date())

    stem = (
        f"three_play_{args.sum_candidate_id}_bankroll_{int(args.start_bankroll)}"
        f"_stake_{int(args.base_stake)}_m{int(args.max_multiplier)}_{sim_start_txt}_{sim_end_txt}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    monthly_path = OUTPUT_DIR / f"{stem}_monthly.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    report_path = OUTPUT_DIR / f"{stem}_report.md"

    daily_df.to_csv(daily_path, index=False)
    monthly_df.to_csv(monthly_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    write_report(report_path, summary=summary, monthly_df=monthly_df)

    print(report_path)
    print(summary_path)
    print(monthly_path)
    print(daily_path)


if __name__ == "__main__":
    main()
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_aligned_shared_bankroll_replay.py`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import time
import importlib.util
import math
import os
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ROUND36_FILE = BASE_DIR / "pk10_round36_three_play_2025_replay.py"
ROUND35_FILE = ROOT_DIR / "pk10_round35_daily_deployment_refinement" / "pk10_round35_daily_deployment_refinement.py"
ROUND35_TRACE = (
    ROOT_DIR
    / "pk10_round35_daily_deployment_refinement"
    / "round35_outputs"
    / "round35_best_trace.csv"
)
ROUND9_FILE = ROOT_DIR / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py"
ROUND16_FILE = ROOT_DIR / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py"

SUM_VALIDATION_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_validation.py"
SUM_REFINEMENT_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_refinement.py"
SUM_INTRADAY_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_intraday_gate.py"
NUMBER_WINDOW_FILE = ROOT_DIR / "tmp_number_validation" / "pk10_number_daily_window_validation.py"
NUMBER_WINDOW_DIR = NUMBER_WINDOW_FILE.parent

SUM_OUTPUT_CANDIDATE_PATHS = (
    ROOT_DIR / "pk10_number_sum_validation" / "number_sum_intraday_gate_outputs_local_pks_3306_20260417" / "intraday_gate_summary.csv",
    ROOT_DIR / "pk10_number_sum_validation" / "number_sum_intraday_gate_outputs_db6y_daily85" / "intraday_gate_summary.csv",
)

DEFAULT_SIM_START = "2026-04-06"
DEFAULT_SIM_END = "2026-04-12"
DEFAULT_QUERY_START = "2024-01-01"
DEFAULT_QUERY_END = "2026-04-12"
DEFAULT_BANKROLL = 1000.0
DEFAULT_BASE_STAKE = 10.0
DEFAULT_MAX_MULTIPLIER = 5
DEFAULT_FACE_POLICY_ID = "core40_spread_only__exp0_off__oe40_spread_only__cd2"
DEFAULT_SUM_CANDIDATE = "intraday_1037"
DEFAULT_EXACT_WINDOW_ID = "exactdw_frozen_edge_low_consensus_obs192"
DEFAULT_EXACT_BASE_GATE_ID = "late|big|edge_low|same_top1_prev=all"
DEFAULT_EXACT_OBS_WINDOW = 192
DEFAULT_EXACT_EXECUTION_RULE = "front_pair_major_consensus_only"
DEFAULT_EXACT_NET_WIN = 8.9
DEFAULT_EXACT_STAKING_MODE = "martingale"
DEFAULT_BLACKOUT_START = ""
DEFAULT_BLACKOUT_END = ""

SOURCE_DB_HOST = os.environ.get("PK10_SOURCE_DB_HOST", "127.0.0.1")
SOURCE_DB_PORT = int(os.environ.get("PK10_SOURCE_DB_PORT", "3306"))
SOURCE_DB_USER = os.environ.get("PK10_SOURCE_DB_USER", "root")
SOURCE_DB_PASS = os.environ.get("PK10_SOURCE_DB_PASS", "")
SOURCE_DB_NAME = os.environ.get("PK10_SOURCE_DB_NAME", "xyft_lottery_data")
SOURCE_TABLE = os.environ.get("PK10_SOURCE_TABLE", "pks_history")


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay an aligned shared-bankroll PK10 path for face + sum + exact.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--query-start", default=DEFAULT_QUERY_START)
    parser.add_argument("--query-end", default=DEFAULT_QUERY_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    parser.add_argument("--face-policy-id", default=DEFAULT_FACE_POLICY_ID)
    parser.add_argument("--sum-candidate-id", default=DEFAULT_SUM_CANDIDATE)
    parser.add_argument("--exact-window-id", default=DEFAULT_EXACT_WINDOW_ID)
    parser.add_argument("--exact-base-gate-id", default=DEFAULT_EXACT_BASE_GATE_ID)
    parser.add_argument("--exact-obs-window", type=int, default=DEFAULT_EXACT_OBS_WINDOW)
    parser.add_argument("--exact-execution-rule", default=DEFAULT_EXACT_EXECUTION_RULE)
    parser.add_argument("--exact-net-win", type=float, default=DEFAULT_EXACT_NET_WIN)
    parser.add_argument("--exact-staking-mode", choices=("martingale", "fixed"), default=DEFAULT_EXACT_STAKING_MODE)
    parser.add_argument("--blackout-start", default=DEFAULT_BLACKOUT_START)
    parser.add_argument("--blackout-end", default=DEFAULT_BLACKOUT_END)
    return parser.parse_args()


def load_issue_history(vmod, query_start: str, query_end: str) -> pd.DataFrame:
    return vmod.load_issue_history_from_db(
        db_host=SOURCE_DB_HOST,
        db_port=SOURCE_DB_PORT,
        db_user=SOURCE_DB_USER,
        db_pass=SOURCE_DB_PASS,
        db_name=SOURCE_DB_NAME,
        table=SOURCE_TABLE,
        date_start=query_start,
        date_end=query_end,
    )


def parse_time_of_day(text: str) -> time | None:
    value = str(text).strip()
    if not value:
        return None
    return pd.Timestamp(f"2000-01-01 {value}").time()


def complete_week_query_end(sim_end: pd.Timestamp, requested_query_end: str) -> pd.Timestamp:
    requested = pd.Timestamp(requested_query_end)
    week_end = sim_end + pd.Timedelta(days=int(6 - sim_end.weekday()))
    return max(requested, week_end)


def build_issue_schedule_frame(issue_df: pd.DataFrame) -> pd.DataFrame:
    work = issue_df.copy()
    work["draw_date"] = pd.to_datetime(work["draw_date"], format="%Y-%m-%d")
    time_text = work["pre_draw_time"].astype(str).str.extract(r"(\d{2}:\d{2}:\d{2})", expand=False)
    time_text = time_text.fillna(work["pre_draw_time"].astype(str))
    work["draw_ts"] = pd.to_datetime(
        work["draw_date"].dt.strftime("%Y-%m-%d") + " " + time_text,
        format="%Y-%m-%d %H:%M:%S",
    )
    work = work.sort_values(["draw_date", "draw_ts", "pre_draw_issue"]).reset_index(drop=True)
    day_counts = work.groupby("draw_date").size()
    expected_per_day = int(day_counts.mode().iloc[0])
    complete_days = day_counts[day_counts == expected_per_day].index
    work = work[work["draw_date"].isin(complete_days)].copy()
    work["issue_idx_in_day"] = work.groupby("draw_date").cumcount()
    work["slot_1based"] = work["issue_idx_in_day"] + 1
    iso = work["draw_date"].dt.isocalendar()
    work["iso_year"] = iso["year"].astype(int)
    work["iso_week"] = iso["week"].astype(int)
    work["week_id"] = work["iso_year"].astype(str) + "-W" + work["iso_week"].astype(str).str.zfill(2)
    week_days = work.groupby("week_id")["draw_date"].nunique()
    complete_weeks = week_days[week_days == 7].index
    work = work[work["week_id"].isin(complete_weeks)].copy()
    valid_week_ids = (
        work.groupby("week_id", sort=True)["draw_date"]
        .min()
        .sort_values()
        .index
        .tolist()
    )
    work["week_id"] = pd.Categorical(work["week_id"], categories=valid_week_ids, ordered=True)
    work = work.sort_values(["week_id", "draw_date", "issue_idx_in_day"]).reset_index(drop=True)
    return work[["draw_date", "draw_ts", "issue_idx_in_day", "slot_1based", "week_id"]].copy()


def build_allowed_trade_lookup(
    schedule_df: pd.DataFrame,
    blackout_start: time | None,
    blackout_end: time | None,
) -> pd.DataFrame:
    out = schedule_df.copy()
    out["allowed_trade"] = True
    if blackout_start is not None and blackout_end is not None:
        times = out["draw_ts"].dt.time
        out["allowed_trade"] = ~((times >= blackout_start) & (times < blackout_end))
    out["date"] = pd.to_datetime(out["draw_date"])
    return out[["date", "draw_ts", "issue_idx_in_day", "slot_1based", "week_id", "allowed_trade"]].copy()


def build_allowed_mask_cube(allowed_lookup: pd.DataFrame, bundle) -> pd.DataFrame:
    week_meta = (
        allowed_lookup.groupby("week_id", sort=True)["date"]
        .agg(["min", "max", "nunique"])
        .rename(columns={"min": "week_start", "max": "week_end", "nunique": "n_days"})
        .reset_index()
        .sort_values("week_start")
        .reset_index(drop=True)
    )
    if int(week_meta["n_days"].min()) != 7 or int(week_meta["n_days"].max()) != 7:
        raise RuntimeError("Allowed-trade lookup does not contain complete weeks only")
    expected_rows = len(week_meta) * 7 * int(bundle.n_slots)
    if len(allowed_lookup) != expected_rows:
        raise RuntimeError(f"Allowed-trade lookup row count mismatch: got {len(allowed_lookup)}, expected {expected_rows}")
    schedule_week_start = week_meta["week_start"].to_numpy(dtype="datetime64[ns]")
    if len(schedule_week_start) != len(bundle.week_start) or not (schedule_week_start == bundle.week_start).all():
        raise RuntimeError("Allowed-trade lookup week alignment mismatch with face bundle")
    return allowed_lookup["allowed_trade"].to_numpy(dtype=bool).reshape(len(week_meta), 7, int(bundle.n_slots))


def parse_face_policy_id(policy_id: str) -> tuple[tuple[int, str], tuple[int, str], tuple[int, str], int]:
    parts = policy_id.split("__")
    if len(parts) != 4:
        raise RuntimeError(f"Unsupported face policy id: {policy_id}")
    core_part, exp_part, oe_part, cd_part = parts
    if not (core_part.startswith("core") and exp_part.startswith("exp") and oe_part.startswith("oe") and cd_part.startswith("cd")):
        raise RuntimeError(f"Unsupported face policy id: {policy_id}")

    def parse_leg(text: str, prefix: str) -> tuple[int, str]:
        tail = text[len(prefix):]
        number_text, family = tail.split("_", 1)
        return int(number_text), family

    core_cfg = parse_leg(core_part, "core")
    exp_cfg = parse_leg(exp_part, "exp")
    oe_cfg = parse_leg(oe_part, "oe")
    cooldown = int(cd_part[2:])
    return core_cfg, exp_cfg, oe_cfg, cooldown


def load_sum_candidate_row(candidate_id: str) -> pd.Series:
    for path in SUM_OUTPUT_CANDIDATE_PATHS:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        matched = df[df["candidate_id"] == candidate_id].copy()
        if not matched.empty:
            return matched.iloc[0]
    raise RuntimeError(f"Missing sum intraday candidate row for {candidate_id}")


def aggregate_sum_daily(detail_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    detail = detail_df.copy()
    detail["date"] = pd.to_datetime(detail["date"])
    grouped = (
        detail.groupby(["date", "split"], as_index=False)
        .agg(
            requested_slots=("slot", "size"),
            selected_score=("score_value", "mean"),
            selected_mean_edge=("mean_edge_value", "mean"),
            selected_symmetry_gap=("symmetry_gap_value", "mean"),
            preview_raw_high_bias=("preview_raw_high_bias", "mean"),
            preview_mid_share=("preview_mid_share", "mean"),
            preview_mean_sum=("preview_mean_sum", "mean"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    picks = detail.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in picks.groupby("date")}
    return grouped, picks_by_date


def day_ledger_from_positions_with_mask(
    week_cube,
    selected_positions_meta,
    week_allowed_mask,
) -> tuple[pd.Series, pd.Series]:
    daily_ledger = pd.Series(0.0, index=range(week_cube.shape[0]), dtype=float)
    daily_bets = pd.Series(0.0, index=range(week_cube.shape[0]), dtype=float)
    if selected_positions_meta is None:
        return daily_ledger, daily_bets
    for payload in selected_positions_meta:
        if not payload:
            continue
        slot_idx = int(payload[0])
        active_days = week_allowed_mask[:, slot_idx].astype(float)
        if active_days.sum() <= 0.0:
            continue
        big_positions = [int(x) - 1 for x in payload[1]]
        small_positions = [int(x) - 1 for x in payload[2]]
        if len(big_positions) == 1 and len(small_positions) == 1:
            top = week_cube[:, slot_idx, big_positions[0]].astype("int16")
            bottom = week_cube[:, slot_idx, small_positions[0]].astype("int16")
            daily_ledger += active_days * ((1995 * (top + 1 - bottom) - 2000) / 1000.0)
            daily_bets += active_days * 2.0
        elif len(big_positions) == 2 and len(small_positions) == 2:
            top = week_cube[:, slot_idx][:, big_positions].astype("int16")
            bottom = week_cube[:, slot_idx][:, small_positions].astype("int16")
            hits = top.sum(axis=1) + (2 - bottom.sum(axis=1))
            daily_ledger += active_days * ((1995 * hits - 4000) / 1000.0)
            daily_bets += active_days * 4.0
        else:
            raise ValueError(f"Unsupported payload: {payload}")
    return daily_ledger, daily_bets


def build_component_daily_with_mask(bundle, series: dict[str, object], week_starts: list[str], line_name: str, allowed_mask_cube) -> pd.DataFrame:
    lookup = {pd.Timestamp(ws).strftime("%Y-%m-%d"): idx for idx, ws in enumerate(bundle.week_start)}
    rows: list[dict[str, object]] = []
    for week_start in week_starts:
        week_idx = lookup[week_start]
        week_cube = bundle.big_cube[week_idx]
        week_allowed = allowed_mask_cube[week_idx]
        daily_ledger, daily_bets = day_ledger_from_positions_with_mask(week_cube, series["selected_positions_meta"][week_idx], week_allowed)
        for day_offset in range(7):
            ledger = float(daily_ledger.iloc[day_offset])
            bets = float(daily_bets.iloc[day_offset])
            issues = float(bets / 4.0) if bets > 0 else 0.0
            implied_spread = (ledger / issues + 0.01) / 3.99 if issues > 0 else float("nan")
            rows.append(
                {
                    "line_name": line_name,
                    "week_start": week_start,
                    "date": (pd.Timestamp(week_start) + pd.Timedelta(days=day_offset)).strftime("%Y-%m-%d"),
                    "day_index_in_week": day_offset + 1,
                    "daily_ledger_unit": ledger,
                    "daily_bets": bets,
                    "daily_implied_spread": implied_spread,
                }
            )
    return pd.DataFrame(rows)


def build_face_frame(
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_stake: float,
    policy_id: str,
) -> pd.DataFrame:
    trace_df = pd.read_csv(ROUND35_TRACE, parse_dates=["date"])
    matched = trace_df[trace_df["policy_id"] == policy_id].copy()
    if matched.empty:
        raise RuntimeError(f"Missing round35 trace rows for policy_id={policy_id}")

    matched = matched[(matched["date"] >= sim_start) & (matched["date"] <= sim_end)].copy()
    if matched.empty:
        raise RuntimeError(f"No round35 rows for {policy_id} in {sim_start.date()} -> {sim_end.date()}")

    date_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    matched = date_range.merge(
        matched[["date", "week_start", "day_index_in_week", "mode", "policy_real_unit", "policy_bets"]],
        on="date",
        how="left",
    )
    matched["mode"] = matched["mode"].fillna("cash")
    matched["policy_real_unit"] = matched["policy_real_unit"].fillna(0.0)
    matched["policy_bets"] = matched["policy_bets"].fillna(0.0)
    matched["face_base_real_pnl"] = matched["policy_real_unit"].astype(float) * float(base_stake)
    return matched


def build_face_frame_from_issue_history(
    round35_mod,
    round9_mod,
    round16_mod,
    issue_df: pd.DataFrame,
    allowed_lookup: pd.DataFrame,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_stake: float,
    policy_id: str,
) -> pd.DataFrame:
    bs_bundle = round9_mod.preprocess_history(issue_df)
    allowed_mask_cube = build_allowed_mask_cube(allowed_lookup, bs_bundle)

    bs_core = round35_mod.make_candidate(
        round9_mod,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=15,
        gap_threshold=0.0125,
    )
    bs_exp = round35_mod.make_candidate(
        round9_mod,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=18,
        gap_threshold=0.0025,
    )
    bs_signal_states, bs_uniform, bs_balanced = round35_mod.build_signal_states(round9_mod, bs_bundle, [bs_core, bs_exp])
    bs_core_series = round9_mod.evaluate_candidate_series(bs_core, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9_mod.evaluate_candidate_series(bs_exp, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)

    round9_mod.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle = round16_mod.preprocess_odd_even(round9_mod, issue_df)
    if len(oe_bundle.week_start) != len(bs_bundle.week_start) or not (oe_bundle.week_start == bs_bundle.week_start).all():
        raise RuntimeError("Odd/even bundle week alignment mismatch with face bundle")
    oe_cfg = round35_mod.make_candidate(
        round9_mod,
        line_name="odd_even_oemap47_gated",
        strategy_family="quartet_fixed_map",
        map_name="OEMAP_47_vs_29",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=10,
        gap_threshold=0.0025,
    )
    oe_signal_states, oe_uniform, oe_balanced = round35_mod.build_signal_states(round9_mod, oe_bundle, [oe_cfg])
    oe_series = round9_mod.evaluate_candidate_series(oe_cfg, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    week_starts = [pd.Timestamp(x).strftime("%Y-%m-%d") for x in pd.to_datetime(bs_bundle.week_start)]
    core_daily = build_component_daily_with_mask(bs_bundle, bs_core_series, week_starts, "core", allowed_mask_cube)
    exp_daily = build_component_daily_with_mask(bs_bundle, bs_exp_series, week_starts, "exp", allowed_mask_cube)
    oe_daily = build_component_daily_with_mask(oe_bundle, oe_series, week_starts, "oe", allowed_mask_cube)

    df = core_daily[["week_start", "date", "day_index_in_week", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
        columns={"daily_ledger_unit": "core_ledger_unit", "daily_bets": "core_bets", "daily_implied_spread": "core_implied_spread"}
    )
    df = df.merge(
        exp_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={"daily_ledger_unit": "exp_ledger_unit", "daily_bets": "exp_bets", "daily_implied_spread": "exp_implied_spread"}
        ),
        on="date",
        how="left",
    )
    df = df.merge(
        oe_daily[["date", "daily_ledger_unit", "daily_bets", "daily_implied_spread"]].rename(
            columns={"daily_ledger_unit": "oe_ledger_unit", "daily_bets": "oe_bets", "daily_implied_spread": "oe_implied_spread"}
        ),
        on="date",
        how="left",
    )
    df = df.fillna(0.0)
    df["day_index"] = range(1, len(df) + 1)

    core_cfg, exp_cfg, oe_cfg_parsed, cooldown_days = parse_face_policy_id(policy_id)
    _, trace = round35_mod.simulate_policy(df, policy_id, core_cfg, exp_cfg, oe_cfg_parsed, cooldown_days)
    trace["date"] = pd.to_datetime(trace["date"])
    matched = trace[(trace["date"] >= sim_start) & (trace["date"] <= sim_end)].copy()
    matched["face_base_real_pnl"] = matched["policy_real_unit"].astype(float) * float(base_stake)
    return matched[["date", "week_start", "day_index_in_week", "mode", "policy_real_unit", "policy_bets", "face_base_real_pnl"]].reset_index(drop=True)


def build_sum_inputs(
    vmod,
    rmod,
    intraday_mod,
    issue_df: pd.DataFrame,
    candidate_row: pd.Series,
    allowed_lookup: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    sum_bundle = vmod.preprocess_exact_sum(issue_df)
    baseline_lookup = {cfg.name: cfg for cfg in intraday_mod.baseline_configs()}
    baseline_name = str(candidate_row["baseline_name"])
    preview_cut = int(candidate_row["preview_cut"])
    if baseline_name not in baseline_lookup:
        raise RuntimeError(f"Missing sum baseline config: {baseline_name}")
    _, detail_df = intraday_mod.build_intraday_base_series(vmod, rmod, sum_bundle, baseline_lookup[baseline_name], preview_cut)
    detail_df["date"] = pd.to_datetime(detail_df["date"])

    preview_grouped = (
        detail_df.groupby(["date", "split"], as_index=False)
        .agg(
            selected_score=("score_value", "mean"),
            selected_mean_edge=("mean_edge_value", "mean"),
            selected_symmetry_gap=("symmetry_gap_value", "mean"),
            preview_raw_high_bias=("preview_raw_high_bias", "mean"),
            preview_mid_share=("preview_mid_share", "mean"),
            preview_mean_sum=("preview_mean_sum", "mean"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )

    allowed_detail = detail_df
    if allowed_lookup is not None:
        slot_lookup = allowed_lookup[["date", "issue_idx_in_day", "allowed_trade"]].rename(columns={"issue_idx_in_day": "slot"})
        allowed_detail = detail_df.merge(slot_lookup, on=["date", "slot"], how="left")
        allowed_detail["allowed_trade"] = allowed_detail["allowed_trade"].fillna(True).astype(bool)
        allowed_detail = allowed_detail[allowed_detail["allowed_trade"]].copy()

    allowed_counts = (
        allowed_detail.groupby(["date", "split"], as_index=False)
        .agg(requested_slots=("slot", "size"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    grouped = preview_grouped.merge(allowed_counts, on=["date", "split"], how="left")
    grouped["requested_slots"] = grouped["requested_slots"].fillna(0).astype(int)
    picks = allowed_detail.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in picks.groupby("date")}
    return grouped, picks_by_date


def build_exact_inputs(
    number_window_mod,
    round9_mod,
    issue_df: pd.DataFrame,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_gate_id: str,
    obs_window: int,
    execution_rule: str,
    exact_net_win: float,
    allowed_lookup: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    bundle = number_window_mod.preprocess_number_history(issue_df, round9_mod)
    candidate = number_window_mod.build_dynamic_pair_candidate(round9_mod)
    counts, exposures = round9_mod.get_bucket_counts(bundle.round9_bundle, candidate.bucket_model)
    signal_state = round9_mod.compute_signal_state(
        counts=counts,
        exposures=exposures,
        lookback_weeks=candidate.lookback_weeks,
        prior_strength=candidate.prior_strength,
        score_model=candidate.score_model,
    )
    subgroup_state_df = number_window_mod.build_fixed_slot_state_tables(
        bundle=bundle,
        round9=round9_mod,
        signal_state=signal_state,
        candidate=candidate,
        late_slots=number_window_mod.parse_csv_ints(number_window_mod.DEFAULT_LATE_SLOTS),
        control_slots=number_window_mod.parse_csv_ints(number_window_mod.DEFAULT_CONTROL_SLOTS),
        half_prior_strength=number_window_mod.DEFAULT_HALF_PRIOR_STRENGTH,
    )
    front_state_df = number_window_mod.build_daily_front_state(
        bundle=bundle,
        subgroup_state_df=subgroup_state_df,
        obs_windows=number_window_mod.OBS_WINDOWS,
        round9=round9_mod,
    )
    rule_state_df = number_window_mod.build_daily_rule_state(front_state_df)

    filtered = rule_state_df[
        (rule_state_df["base_gate_id"] == base_gate_id)
        & (rule_state_df["obs_window"] == obs_window)
    ].copy()
    if filtered.empty:
        raise RuntimeError("Exact daily-window rule_state is empty for the selected frozen candidate")

    rule_col = f"rule_{execution_rule}"
    if rule_col not in filtered.columns:
        raise RuntimeError(f"Missing exact execution rule column: {rule_col}")

    filtered["execute_exact"] = filtered[rule_col].astype(bool)
    filtered["selected_number_exec"] = filtered.apply(
        lambda row: number_window_mod.selected_number_for_rule(execution_rule, row),
        axis=1,
    )
    filtered["exact_hit_exec"] = (
        filtered["execute_exact"] & (filtered["target_number"] == filtered["selected_number_exec"])
    ).astype(int)
    filtered["cell_book_pnl_units"] = filtered["exact_hit_exec"].map(
        lambda hit: float(exact_net_win) if int(hit) == 1 else -1.0
    )
    filtered["day_date"] = pd.to_datetime(filtered["day_date"])

    active_cells = filtered[filtered["execute_exact"]].copy()
    if allowed_lookup is not None:
        slot_lookup = allowed_lookup[["date", "slot_1based", "allowed_trade"]].rename(columns={"date": "day_date"})
        active_cells = active_cells.merge(slot_lookup, on=["day_date", "slot_1based"], how="left")
        active_cells["allowed_trade"] = active_cells["allowed_trade"].fillna(True).astype(bool)
        active_cells = active_cells[active_cells["allowed_trade"]].copy()

    split_frame = filtered[["day_date", "split"]].drop_duplicates().copy()
    grouped = (
        active_cells.groupby(["day_date", "split"], as_index=False)
        .agg(
            issue_exposures=("execute_exact", "sum"),
            exact_hits_count=("exact_hit_exec", "sum"),
        )
        .sort_values("day_date")
        .reset_index(drop=True)
    )
    grouped = split_frame.merge(grouped, on=["day_date", "split"], how="left")
    grouped["issue_exposures"] = grouped["issue_exposures"].fillna(0).astype(int)
    grouped["exact_hits_count"] = grouped["exact_hits_count"].fillna(0).astype(int)
    picks_by_date = {
        pd.Timestamp(day): frame.sort_values(["slot_1based"], kind="stable").reset_index(drop=True)
        for day, frame in active_cells.groupby("day_date")
    }

    full_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    daily_frame = full_range.merge(grouped.rename(columns={"day_date": "date"}), on="date", how="left")
    daily_frame["split"] = daily_frame["split"].fillna("out_of_sample_gap")
    daily_frame["issue_exposures"] = daily_frame["issue_exposures"].fillna(0).astype(int)
    daily_frame["exact_hits_count"] = daily_frame["exact_hits_count"].fillna(0).astype(int)
    return daily_frame, picks_by_date


def build_svg(series_df: pd.DataFrame, output_path: Path, title: str) -> None:
    width, height = 1200, 520
    left, right, top, bottom = 70, 30, 40, 55
    inner_w = width - left - right
    inner_h = height - top - bottom

    all_values = series_df["bankroll_after_day"].astype(float).tolist()
    min_v = min(all_values)
    max_v = max(all_values)
    if math.isclose(min_v, max_v):
        min_v -= 1.0
        max_v += 1.0
    pad = (max_v - min_v) * 0.08
    min_v -= pad
    max_v += pad

    def x_at(idx: int, n: int) -> float:
        if n <= 1:
            return left + inner_w / 2.0
        return left + inner_w * idx / (n - 1)

    def y_at(value: float) -> float:
        return top + inner_h * (1.0 - (value - min_v) / (max_v - min_v))

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='white' />",
        f"<text x='{left}' y='24' font-size='18' font-family='Arial, sans-serif' fill='#111827'>{title}</text>",
        f"<line x1='{left}' y1='{top + inner_h}' x2='{left + inner_w}' y2='{top + inner_h}' stroke='#9ca3af' stroke-width='1' />",
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + inner_h}' stroke='#9ca3af' stroke-width='1' />",
    ]

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        value = min_v + (max_v - min_v) * frac
        y = y_at(value)
        lines.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left + inner_w}' y2='{y:.2f}' stroke='#e5e7eb' stroke-width='1' />")
        lines.append(f"<text x='{left - 10}' y='{y + 4:.2f}' text-anchor='end' font-size='11' font-family='Arial, sans-serif' fill='#4b5563'>{value:.1f}</text>")

    for idx, day in enumerate(series_df["date"].dt.strftime("%m-%d").tolist()):
        lines.append(f"<text x='{x_at(idx, len(series_df)):.2f}' y='{top + inner_h + 20}' text-anchor='middle' font-size='11' font-family='Arial, sans-serif' fill='#4b5563'>{day}</text>")

    points = " ".join(
        f"{x_at(i, len(series_df)):.2f},{y_at(v):.2f}"
        for i, v in enumerate(series_df["bankroll_after_day"].astype(float).tolist())
    )
    lines.append(f"<polyline fill='none' stroke='#1d4ed8' stroke-width='2.5' points='{points}' />")
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def replay_shared_bankroll(
    round36_mod,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    start_bankroll: float,
    base_stake: float,
    max_multiplier: int,
    face_policy_id: str,
    face_frame: pd.DataFrame,
    sum_candidate_row: pd.Series,
    sum_grouped: pd.DataFrame,
    sum_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    exact_frame: pd.DataFrame,
    exact_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    exact_window_id: str,
    exact_base_gate_id: str,
    exact_obs_window: int,
    exact_execution_rule: str,
    exact_net_win: float,
    exact_staking_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    full_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})

    sum_daily = full_range.merge(sum_grouped, on="date", how="left")
    sum_daily["split"] = sum_daily["split"].fillna("out_of_sample_gap")
    for col in [
        "requested_slots",
        "selected_score",
        "selected_mean_edge",
        "selected_symmetry_gap",
        "preview_raw_high_bias",
        "preview_mid_share",
        "preview_mean_sum",
    ]:
        sum_daily[col] = sum_daily[col].fillna(0.0)
    sum_daily["sum_active"] = sum_daily.apply(lambda row: round36_mod.gate_is_on(row, sum_candidate_row), axis=1)

    combined = (
        full_range.merge(face_frame, on="date", how="left")
        .merge(sum_daily, on="date", how="left")
        .merge(exact_frame, on="date", how="left")
    )
    combined["mode"] = combined["mode"].fillna("cash")
    combined["face_base_real_pnl"] = combined["face_base_real_pnl"].fillna(0.0)
    combined["policy_bets"] = combined["policy_bets"].fillna(0.0)
    combined["issue_exposures"] = combined["issue_exposures"].fillna(0).astype(int)
    combined["exact_hits_count"] = combined["exact_hits_count"].fillna(0).astype(int)

    bankroll = float(start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0

    face_multiplier = 1
    sum_multiplier = 1
    exact_multiplier = 1

    face_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    sum_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    exact_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    skipped_sum_due_to_cash = 0
    skipped_exact_due_to_cash = 0

    rows: list[dict[str, object]] = []
    for _, row in combined.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll

        face_active = str(row["mode"]) != "cash"
        applied_face_multiplier = face_multiplier if face_active else 0
        face_real = float(row["face_base_real_pnl"]) * applied_face_multiplier
        if face_active:
            face_ladder_counts[face_multiplier] += 1

        sum_requested_slots = int(row["requested_slots"]) if bool(row["sum_active"]) else 0
        sum_funded_slots = 0
        sum_book_units = 0.0
        sum_real = 0.0
        affordable_sum_slots = max(0, int(bankroll_before // (base_stake * sum_multiplier))) if sum_multiplier > 0 else 0
        if sum_requested_slots > 0:
            sum_funded_slots = min(sum_requested_slots, affordable_sum_slots)
            if sum_funded_slots > 0:
                picks = sum_picks_by_date.get(day, pd.DataFrame()).head(sum_funded_slots).copy()
                sum_book_units = float(picks["book_pnl"].sum()) if not picks.empty else 0.0
                sum_real = round36_mod.settle_real(sum_book_units * sum_multiplier) * base_stake
                sum_ladder_counts[sum_multiplier] += 1
            else:
                skipped_sum_due_to_cash += 1

        exact_requested_slots = int(row["issue_exposures"])
        exact_funded_slots = 0
        exact_book_units = 0.0
        exact_real = 0.0
        effective_exact_multiplier = 1 if exact_staking_mode == "fixed" else exact_multiplier
        affordable_exact_slots = max(0, int(bankroll_before // (base_stake * effective_exact_multiplier))) if effective_exact_multiplier > 0 else 0
        if exact_requested_slots > 0:
            exact_funded_slots = min(exact_requested_slots, affordable_exact_slots)
            if exact_funded_slots > 0:
                exact_picks = exact_picks_by_date.get(day, pd.DataFrame()).head(exact_funded_slots).copy()
                exact_book_units = float(exact_picks["cell_book_pnl_units"].sum()) if not exact_picks.empty else 0.0
                exact_real = round36_mod.settle_real(exact_book_units * effective_exact_multiplier) * base_stake
                exact_ladder_counts[effective_exact_multiplier] += 1
            else:
                skipped_exact_due_to_cash += 1

        total_real = face_real + sum_real + exact_real
        bankroll += total_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "face_mode": str(row["mode"]),
                "face_active": face_active,
                "face_executed_bets": int(row["policy_bets"]),
                "face_multiplier": applied_face_multiplier,
                "face_real_pnl": face_real,
                "sum_active": bool(sum_requested_slots > 0),
                "sum_requested_slots": sum_requested_slots,
                "sum_affordable_slots": affordable_sum_slots,
                "sum_funded_slots": sum_funded_slots,
                "sum_multiplier": sum_multiplier if sum_requested_slots > 0 else 0,
                "sum_book_pnl_units": sum_book_units,
                "sum_real_pnl": sum_real,
                "exact_active": bool(exact_requested_slots > 0),
                "exact_requested_slots": exact_requested_slots,
                "exact_affordable_slots": affordable_exact_slots,
                "exact_funded_slots": exact_funded_slots,
                "exact_multiplier": effective_exact_multiplier if exact_requested_slots > 0 else 0,
                "exact_book_pnl_units": exact_book_units,
                "exact_real_pnl": exact_real,
                "total_real_pnl": total_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
                "sum_preview_raw_high_bias": float(row["preview_raw_high_bias"]),
                "sum_preview_mid_share": float(row["preview_mid_share"]),
                "sum_preview_mean_sum": float(row["preview_mean_sum"]),
            }
        )

        if face_active:
            face_multiplier = round36_mod.next_multiplier(face_multiplier, max_multiplier=max_multiplier, last_real_pnl=face_real)
        if sum_funded_slots > 0:
            sum_multiplier = round36_mod.next_multiplier(sum_multiplier, max_multiplier=max_multiplier, last_real_pnl=sum_real)
        if exact_funded_slots > 0 and exact_staking_mode == "martingale":
            exact_multiplier = round36_mod.next_multiplier(exact_multiplier, max_multiplier=max_multiplier, last_real_pnl=exact_real)

    daily_df = pd.DataFrame(rows)
    summary_df = pd.DataFrame(
        [
            {
                "sim_start": str(sim_start.date()),
                "sim_end": str(sim_end.date()),
                "start_bankroll": start_bankroll,
                "base_stake": base_stake,
                "max_multiplier": max_multiplier,
                "source_table": SOURCE_TABLE,
                "face_policy_id": str(face_policy_id),
                "sum_candidate_id": str(sum_candidate_row["candidate_id"]),
                "sum_gate_family": str(sum_candidate_row["gate_family"]),
                "sum_baseline_name": str(sum_candidate_row["baseline_name"]),
                "sum_preview_cut": int(sum_candidate_row["preview_cut"]),
                "exact_window_id": str(exact_window_id),
                "exact_base_gate_id": str(exact_base_gate_id),
                "exact_obs_window": int(exact_obs_window),
                "exact_execution_rule": str(exact_execution_rule),
                "exact_net_win": float(exact_net_win),
                "exact_staking_mode": str(exact_staking_mode),
                "days_in_simulation": int(daily_df.shape[0]),
                "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
                "net_profit": float(daily_df["total_real_pnl"].sum()),
                "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / start_bankroll - 1.0) * 100.0),
                "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
                "min_bankroll": float(daily_df["bankroll_after_day"].min()),
                "max_drawdown": float(max_drawdown),
                "face_profit": float(daily_df["face_real_pnl"].sum()),
                "sum_profit": float(daily_df["sum_real_pnl"].sum()),
                "exact_profit": float(daily_df["exact_real_pnl"].sum()),
                "face_active_days": int(daily_df["face_active"].sum()),
                "sum_active_days": int(daily_df["sum_active"].sum()),
                "exact_active_days": int(daily_df["exact_active"].sum()),
                "sum_funded_slots": int(daily_df["sum_funded_slots"].sum()),
                "exact_funded_slots": int(daily_df["exact_funded_slots"].sum()),
                "skipped_sum_due_to_cash": skipped_sum_due_to_cash,
                "skipped_exact_due_to_cash": skipped_exact_due_to_cash,
                "face_days_1x": face_ladder_counts[1],
                "face_days_2x": face_ladder_counts[2],
                "face_days_4x": face_ladder_counts[4],
                "face_days_5x": face_ladder_counts[5],
                "sum_days_1x": sum_ladder_counts[1],
                "sum_days_2x": sum_ladder_counts[2],
                "sum_days_4x": sum_ladder_counts[4],
                "sum_days_5x": sum_ladder_counts[5],
                "exact_days_1x": exact_ladder_counts[1],
                "exact_days_2x": exact_ladder_counts[2],
                "exact_days_4x": exact_ladder_counts[4],
                "exact_days_5x": exact_ladder_counts[5],
            }
        ]
    )
    return daily_df, summary_df


def main() -> None:
    global args
    args = parse_args()
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)
    blackout_start = parse_time_of_day(args.blackout_start)
    blackout_end = parse_time_of_day(args.blackout_end)
    effective_query_end = complete_week_query_end(sim_end, args.query_end)

    if str(NUMBER_WINDOW_DIR) not in sys.path:
        sys.path.insert(0, str(NUMBER_WINDOW_DIR))

    round36_mod = import_module(ROUND36_FILE, "round36_for_round36_aligned")
    round35_mod = import_module(ROUND35_FILE, "round35_for_round36_aligned")
    round9_mod = import_module(ROUND9_FILE, "round9_for_round36_aligned")
    round16_mod = import_module(ROUND16_FILE, "round16_for_round36_aligned")
    vmod = import_module(SUM_VALIDATION_FILE, "sum_validation_for_round36_aligned")
    rmod = import_module(SUM_REFINEMENT_FILE, "sum_refinement_for_round36_aligned")
    intraday_mod = import_module(SUM_INTRADAY_FILE, "sum_intraday_for_round36_aligned")
    number_window_mod = import_module(NUMBER_WINDOW_FILE, "number_daily_window_for_round36_aligned")

    issue_df = load_issue_history(vmod, query_start=args.query_start, query_end=str(effective_query_end.date()))
    if issue_df.empty:
        raise RuntimeError("Issue history query returned no rows")

    allowed_lookup = build_allowed_trade_lookup(
        build_issue_schedule_frame(issue_df),
        blackout_start=blackout_start,
        blackout_end=blackout_end,
    )

    if blackout_start is None or blackout_end is None:
        face_frame = build_face_frame(
            sim_start=sim_start,
            sim_end=sim_end,
            base_stake=float(args.base_stake),
            policy_id=args.face_policy_id,
        )
    else:
        face_frame = build_face_frame_from_issue_history(
            round35_mod=round35_mod,
            round9_mod=round9_mod,
            round16_mod=round16_mod,
            issue_df=issue_df,
            allowed_lookup=allowed_lookup,
            sim_start=sim_start,
            sim_end=sim_end,
            base_stake=float(args.base_stake),
            policy_id=args.face_policy_id,
        )
    sum_candidate_row = load_sum_candidate_row(args.sum_candidate_id)
    sum_grouped, sum_picks_by_date = build_sum_inputs(
        vmod=vmod,
        rmod=rmod,
        intraday_mod=intraday_mod,
        issue_df=issue_df,
        candidate_row=sum_candidate_row,
        allowed_lookup=allowed_lookup if blackout_start is not None and blackout_end is not None else None,
    )
    exact_frame, exact_picks_by_date = build_exact_inputs(
        number_window_mod=number_window_mod,
        round9_mod=round9_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
        base_gate_id=args.exact_base_gate_id,
        obs_window=int(args.exact_obs_window),
        execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        allowed_lookup=allowed_lookup if blackout_start is not None and blackout_end is not None else None,
    )

    daily_df, summary_df = replay_shared_bankroll(
        round36_mod=round36_mod,
        sim_start=sim_start,
        sim_end=sim_end,
        start_bankroll=float(args.start_bankroll),
        base_stake=float(args.base_stake),
        max_multiplier=max(1, int(args.max_multiplier)),
        face_policy_id=args.face_policy_id,
        face_frame=face_frame,
        sum_candidate_row=sum_candidate_row,
        sum_grouped=sum_grouped,
        sum_picks_by_date=sum_picks_by_date,
        exact_frame=exact_frame,
        exact_picks_by_date=exact_picks_by_date,
        exact_window_id=args.exact_window_id,
        exact_base_gate_id=args.exact_base_gate_id,
        exact_obs_window=int(args.exact_obs_window),
        exact_execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        exact_staking_mode=args.exact_staking_mode,
    )

    blackout_tag = ""
    if blackout_start is not None and blackout_end is not None:
        blackout_tag = f"_blackout_{args.blackout_start.replace(':', '')}_{args.blackout_end.replace(':', '')}"

    stem = (
        f"aligned_face_{args.face_policy_id}"
        f"__sum_{args.sum_candidate_id}"
        f"__exact_{args.exact_window_id}_{args.exact_staking_mode}"
        f"_bankroll_{int(args.start_bankroll)}_stake_{int(args.base_stake)}"
        f"_m{int(args.max_multiplier)}{blackout_tag}_pks_history_{sim_start.date()}_{sim_end.date()}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    curve_path = OUTPUT_DIR / f"{stem}_curve.svg"

    daily_df.to_csv(daily_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    build_svg(
        daily_df,
        curve_path,
        title=(
            f"Aligned Shared Bankroll Curve | {sim_start.date()} -> {sim_end.date()} | "
            f"{args.face_policy_id} + {args.sum_candidate_id} + {args.exact_window_id}"
        ),
    )

    print(summary_path)
    print(daily_path)
    print(curve_path)


if __name__ == "__main__":
    main()
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_four_play_interval_replay.py`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ROUND30_FILE = ROOT_DIR / "pk10_round30_daily85_exact_transfer" / "pk10_round30_daily85_exact_transfer.py"
ROUND9_FILE = ROOT_DIR / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py"
ROUND16_FILE = ROOT_DIR / "pk10_round16_odd_even_transfer_validation" / "pk10_round16_odd_even_transfer_validation.py"
ROUND36_FILE = BASE_DIR / "pk10_round36_three_play_2025_replay.py"

SUM_VALIDATION_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_validation.py"
SUM_REFINEMENT_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_refinement.py"
SUM_INTRADAY_FILE = ROOT_DIR / "pk10_number_sum_validation" / "pk10_number_sum_intraday_gate.py"

NUMBER_WINDOW_FILE = ROOT_DIR / "tmp_number_validation" / "pk10_number_daily_window_validation.py"
NUMBER_WINDOW_DIR = NUMBER_WINDOW_FILE.parent

SUM_OUTPUT_CANDIDATE_PATHS = (
    ROOT_DIR / "pk10_number_sum_validation" / "number_sum_intraday_gate_outputs_local_pks_3306_20260417" / "intraday_gate_summary.csv",
    ROOT_DIR / "pk10_number_sum_validation" / "number_sum_intraday_gate_outputs_db6y_daily85" / "intraday_gate_summary.csv",
)

DEFAULT_SIM_START = "2026-04-06"
DEFAULT_SIM_END = "2026-04-12"
DEFAULT_QUERY_START = "2024-01-01"
DEFAULT_QUERY_END = "2026-04-12"
DEFAULT_BANKROLL = 1000.0
DEFAULT_BASE_STAKE = 10.0
DEFAULT_MAX_MULTIPLIER = 5
DEFAULT_SUM_CANDIDATE = "intraday_1007"

SOURCE_DB_HOST = "127.0.0.1"
SOURCE_DB_PORT = 3306
SOURCE_DB_USER = "root"
SOURCE_DB_PASS = ""
SOURCE_DB_NAME = "xyft_lottery_data"
SOURCE_TABLE = "pks_history"

EXACT_DAILY_WINDOW_ID = "exactdw_001"
EXACT_BASE_GATE_ID = "late|big|center|same_top1_prev=all"
EXACT_OBS_WINDOW = 192
EXACT_EXECUTION_RULE = "front_singleton_exact_q75_only"
EXACT_NET_WIN = 8.9


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a shared-bankroll four-play PK10 interval with number daily window.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--query-start", default=DEFAULT_QUERY_START)
    parser.add_argument("--query-end", default=DEFAULT_QUERY_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    parser.add_argument("--sum-candidate-id", default=DEFAULT_SUM_CANDIDATE)
    return parser.parse_args()


def week_starts_for_interval(sim_start: pd.Timestamp, sim_end: pd.Timestamp) -> list[str]:
    day_range = pd.date_range(sim_start, sim_end, freq="D")
    starts = sorted({(day - pd.Timedelta(days=int(day.weekday()))).strftime("%Y-%m-%d") for day in day_range})
    return starts


def load_issue_history(vmod, query_start: str, query_end: str) -> pd.DataFrame:
    return vmod.load_issue_history_from_db(
        db_host=SOURCE_DB_HOST,
        db_port=SOURCE_DB_PORT,
        db_user=SOURCE_DB_USER,
        db_pass=SOURCE_DB_PASS,
        db_name=SOURCE_DB_NAME,
        table=SOURCE_TABLE,
        date_start=query_start,
        date_end=query_end,
    )


def load_sum_candidate_row(candidate_id: str) -> pd.Series:
    for path in SUM_OUTPUT_CANDIDATE_PATHS:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        matched = df[df["candidate_id"] == candidate_id].copy()
        if not matched.empty:
            return matched.iloc[0]
    raise RuntimeError(f"Missing sum intraday candidate row for {candidate_id}")


def aggregate_sum_daily(detail_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    detail = detail_df.copy()
    detail["date"] = pd.to_datetime(detail["date"])
    grouped = (
        detail.groupby(["date", "split"], as_index=False)
        .agg(
            requested_slots=("slot", "size"),
            selected_score=("score_value", "mean"),
            selected_mean_edge=("mean_edge_value", "mean"),
            selected_symmetry_gap=("symmetry_gap_value", "mean"),
            preview_raw_high_bias=("preview_raw_high_bias", "mean"),
            preview_mid_share=("preview_mid_share", "mean"),
            preview_mean_sum=("preview_mean_sum", "mean"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    picks = detail.sort_values(["date", "score_value", "slot"], ascending=[True, False, True]).copy()
    picks_by_date = {pd.Timestamp(day): frame.reset_index(drop=True) for day, frame in picks.groupby("date")}
    return grouped, picks_by_date


def build_bs_oe_frame(
    round30_mod,
    round9_mod,
    round16_mod,
    issue_df: pd.DataFrame,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    base_stake: float,
) -> pd.DataFrame:
    week_starts = week_starts_for_interval(sim_start, sim_end)

    bs_bundle = round9_mod.preprocess_history(issue_df)
    bs_core = round30_mod.make_round9_candidate(
        round9_mod,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=15,
        gap_threshold=0.0125,
    )
    bs_expansion = round30_mod.make_round9_candidate(
        round9_mod,
        line_name="slow_static_quartet",
        strategy_family="quartet_fixed_map",
        map_name="M4_72_vs_910",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=18,
        gap_threshold=0.0025,
    )
    bs_signal_states, bs_uniform, bs_balanced = round30_mod.build_signal_states(round9_mod, bs_bundle, [bs_core, bs_expansion])
    bs_core_series = round9_mod.evaluate_candidate_series(bs_core, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)
    bs_exp_series = round9_mod.evaluate_candidate_series(bs_expansion, bs_bundle, bs_signal_states, bs_uniform, bs_balanced)

    round9_mod.ROUND4_MAP_LIBRARY["OEMAP_47_vs_29"] = ((3, 6), (1, 8))
    oe_bundle = round16_mod.preprocess_odd_even(round9_mod, issue_df)
    oe_candidate = round30_mod.make_round9_candidate(
        round9_mod,
        line_name="odd_even_oemap47_gated",
        strategy_family="quartet_fixed_map",
        map_name="OEMAP_47_vs_29",
        bucket_model="exact_slot",
        score_model="beta_shrunk_rate",
        lookback_weeks=26,
        holding_weeks=4,
        prior_strength=20,
        selector_family="daily_gap_topk",
        daily_issue_cap=10,
        gap_threshold=0.0025,
    )
    oe_signal_states, oe_uniform, oe_balanced = round30_mod.build_signal_states(round9_mod, oe_bundle, [oe_candidate])
    oe_series = round9_mod.evaluate_candidate_series(oe_candidate, oe_bundle, oe_signal_states, oe_uniform, oe_balanced)

    policy_df = round30_mod.read_round10_policy(ROOT_DIR)
    policy_df = policy_df[policy_df["week_start"].isin(week_starts)].copy().reset_index(drop=True)
    oe_gate_df = round30_mod.read_round21_gate_trace(ROOT_DIR)
    oe_gate_df = oe_gate_df[oe_gate_df["week_start"].isin(week_starts)].copy().reset_index(drop=True)
    if policy_df.empty or oe_gate_df.empty:
        raise RuntimeError(f"Missing weekly policy rows for interval weeks: {week_starts}")

    bs_core_daily = round30_mod.build_daily_component_trace(bs_bundle, bs_core_series, policy_df, "bs_core")
    bs_exp_daily = round30_mod.build_daily_component_trace(bs_bundle, bs_exp_series, policy_df, "bs_expansion")
    oe_daily = round30_mod.build_daily_component_trace(oe_bundle, oe_series, oe_gate_df, "oe_mode_non_cash_base")

    bs_mode_map = policy_df.set_index("week_start")["mode"].to_dict()
    bs_rows: list[dict[str, object]] = []
    for week in policy_df["week_start"].tolist():
        core_week = round30_mod.apply_daily85(bs_core_daily[bs_core_daily["week_start"] == week].copy())
        exp_week = round30_mod.apply_daily85(bs_exp_daily[bs_exp_daily["week_start"] == week].copy())
        mode = bs_mode_map[week]
        for day in range(1, 8):
            core_row = core_week[core_week["day_index_in_week"] == day].iloc[0]
            exp_row = exp_week[exp_week["day_index_in_week"] == day].iloc[0]
            if mode == "core":
                real = float(core_row["daily_real_unit"])
            elif mode == "core_plus_expansion":
                real = float(core_row["daily_real_unit"] + exp_row["daily_real_unit"])
            else:
                real = 0.0
            bs_rows.append({"date": pd.Timestamp(core_row["date"]), "bs_real_unit": real})
    bs_daily = pd.DataFrame(bs_rows)

    oe_active_map = oe_gate_df.set_index("week_start")["active"].astype(int).to_dict()
    oe_rows: list[dict[str, object]] = []
    for week in oe_gate_df["week_start"].tolist():
        oe_week = round30_mod.apply_daily85(oe_daily[oe_daily["week_start"] == week].copy())
        active = oe_active_map[week] == 1
        for day in range(1, 8):
            oe_row = oe_week[oe_week["day_index_in_week"] == day].iloc[0]
            real = float(oe_row["daily_real_unit"]) if active else 0.0
            oe_rows.append({"date": pd.Timestamp(oe_row["date"]), "oe_real_unit": real})
    oe_daily_frame = pd.DataFrame(oe_rows)

    out = bs_daily.merge(oe_daily_frame, on="date", how="left")
    out["oe_real_unit"] = out["oe_real_unit"].fillna(0.0)
    out["bs_base_real_pnl"] = out["bs_real_unit"] * (base_stake / round30_mod.STAKE_PER_BET)
    out["oe_base_real_pnl"] = out["oe_real_unit"] * (base_stake / round30_mod.STAKE_PER_BET)
    out = out[(out["date"] >= sim_start) & (out["date"] <= sim_end)].copy()
    return out[["date", "bs_base_real_pnl", "oe_base_real_pnl"]].sort_values("date").reset_index(drop=True)


def build_sum_inputs(vmod, rmod, intraday_mod, issue_df: pd.DataFrame, candidate_row: pd.Series) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    sum_bundle = vmod.preprocess_exact_sum(issue_df)
    baseline_lookup = {cfg.name: cfg for cfg in intraday_mod.baseline_configs()}
    baseline_name = str(candidate_row["baseline_name"])
    preview_cut = int(candidate_row["preview_cut"])
    if baseline_name not in baseline_lookup:
        raise RuntimeError(f"Missing sum baseline config: {baseline_name}")
    _, detail_df = intraday_mod.build_intraday_base_series(vmod, rmod, sum_bundle, baseline_lookup[baseline_name], preview_cut)
    return aggregate_sum_daily(detail_df)


def build_exact_inputs(number_window_mod, round9_mod, issue_df: pd.DataFrame, sim_start: pd.Timestamp, sim_end: pd.Timestamp) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.DataFrame]]:
    bundle = number_window_mod.preprocess_number_history(issue_df, round9_mod)
    candidate = number_window_mod.build_dynamic_pair_candidate(round9_mod)
    counts, exposures = round9_mod.get_bucket_counts(bundle.round9_bundle, candidate.bucket_model)
    signal_state = round9_mod.compute_signal_state(
        counts=counts,
        exposures=exposures,
        lookback_weeks=candidate.lookback_weeks,
        prior_strength=candidate.prior_strength,
        score_model=candidate.score_model,
    )
    subgroup_state_df = number_window_mod.build_fixed_slot_state_tables(
        bundle=bundle,
        round9=round9_mod,
        signal_state=signal_state,
        candidate=candidate,
        late_slots=number_window_mod.parse_csv_ints(number_window_mod.DEFAULT_LATE_SLOTS),
        control_slots=number_window_mod.parse_csv_ints(number_window_mod.DEFAULT_CONTROL_SLOTS),
        half_prior_strength=number_window_mod.DEFAULT_HALF_PRIOR_STRENGTH,
    )
    front_state_df = number_window_mod.build_daily_front_state(
        bundle=bundle,
        subgroup_state_df=subgroup_state_df,
        obs_windows=number_window_mod.OBS_WINDOWS,
        round9=round9_mod,
    )
    rule_state_df = number_window_mod.build_daily_rule_state(front_state_df)

    filtered = rule_state_df[
        (rule_state_df["base_gate_id"] == EXACT_BASE_GATE_ID)
        & (rule_state_df["obs_window"] == EXACT_OBS_WINDOW)
    ].copy()
    if filtered.empty:
        raise RuntimeError("Exact daily-window rule_state is empty for fixed candidate")

    rule_col = f"rule_{EXACT_EXECUTION_RULE}"
    if rule_col not in filtered.columns:
        raise RuntimeError(f"Missing exact execution rule column: {rule_col}")

    filtered["execute_exact"] = filtered[rule_col].astype(bool)
    filtered["selected_number_exec"] = filtered.apply(
        lambda row: number_window_mod.selected_number_for_rule(EXACT_EXECUTION_RULE, row),
        axis=1,
    )
    filtered["exact_hit_exec"] = (
        filtered["execute_exact"] & (filtered["target_number"] == filtered["selected_number_exec"])
    ).astype(int)
    filtered["cell_book_pnl_units"] = filtered["exact_hit_exec"].map(lambda hit: EXACT_NET_WIN if int(hit) == 1 else -1.0)
    filtered["day_date"] = pd.to_datetime(filtered["day_date"])

    active_cells = filtered[filtered["execute_exact"]].copy()
    grouped = (
        active_cells.groupby(["day_date", "split"], as_index=False)
        .agg(
            issue_exposures=("execute_exact", "sum"),
            exact_hits_count=("exact_hit_exec", "sum"),
        )
        .sort_values("day_date")
        .reset_index(drop=True)
    )
    picks_by_date = {pd.Timestamp(day): frame.sort_values(["slot_1based"], kind="stable").reset_index(drop=True) for day, frame in active_cells.groupby("day_date")}

    full_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})
    daily_frame = full_range.merge(grouped.rename(columns={"day_date": "date"}), on="date", how="left")
    daily_frame["split"] = daily_frame["split"].fillna("out_of_sample_gap")
    daily_frame["issue_exposures"] = daily_frame["issue_exposures"].fillna(0).astype(int)
    daily_frame["exact_hits_count"] = daily_frame["exact_hits_count"].fillna(0).astype(int)
    return daily_frame, picks_by_date


def build_svg(series_map: dict[str, pd.DataFrame], output_path: Path, title: str) -> None:
    width, height = 1200, 520
    left, right, top, bottom = 70, 30, 40, 55
    inner_w = width - left - right
    inner_h = height - top - bottom
    colors = ["#1d4ed8", "#dc2626", "#0f766e", "#7c3aed"]

    all_values: list[float] = []
    for df in series_map.values():
        all_values.extend(df["bankroll_after_day"].astype(float).tolist())
    min_v = min(all_values)
    max_v = max(all_values)
    if math.isclose(min_v, max_v):
        min_v -= 1.0
        max_v += 1.0
    pad = (max_v - min_v) * 0.08
    min_v -= pad
    max_v += pad

    def x_at(idx: int, n: int) -> float:
        if n <= 1:
            return left + inner_w / 2.0
        return left + inner_w * idx / (n - 1)

    def y_at(value: float) -> float:
        return top + inner_h * (1.0 - (value - min_v) / (max_v - min_v))

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='white' />",
        f"<text x='{left}' y='24' font-size='18' font-family='Arial, sans-serif' fill='#111827'>{title}</text>",
        f"<line x1='{left}' y1='{top + inner_h}' x2='{left + inner_w}' y2='{top + inner_h}' stroke='#9ca3af' stroke-width='1' />",
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + inner_h}' stroke='#9ca3af' stroke-width='1' />",
    ]

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        value = min_v + (max_v - min_v) * frac
        y = y_at(value)
        lines.append(f"<line x1='{left}' y1='{y:.2f}' x2='{left + inner_w}' y2='{y:.2f}' stroke='#e5e7eb' stroke-width='1' />")
        lines.append(f"<text x='{left - 10}' y='{y + 4:.2f}' text-anchor='end' font-size='11' font-family='Arial, sans-serif' fill='#4b5563'>{value:.1f}</text>")

    sample_df = next(iter(series_map.values()))
    for idx, day in enumerate(sample_df["date"].dt.strftime("%m-%d").tolist()):
        lines.append(f"<text x='{x_at(idx, len(sample_df)):.2f}' y='{top + inner_h + 20}' text-anchor='middle' font-size='11' font-family='Arial, sans-serif' fill='#4b5563'>{day}</text>")

    legend_x = left + 10
    legend_y = top + 10
    for idx, (label, df) in enumerate(series_map.items()):
        color = colors[idx % len(colors)]
        points = " ".join(
            f"{x_at(i, len(df)):.2f},{y_at(v):.2f}" for i, v in enumerate(df["bankroll_after_day"].astype(float).tolist())
        )
        lines.append(f"<polyline fill='none' stroke='{color}' stroke-width='2.5' points='{points}' />")
        ly = legend_y + idx * 18
        lines.append(f"<line x1='{legend_x}' y1='{ly}' x2='{legend_x + 20}' y2='{ly}' stroke='{color}' stroke-width='2.5' />")
        lines.append(f"<text x='{legend_x + 28}' y='{ly + 4}' font-size='12' font-family='Arial, sans-serif' fill='#111827'>{label}</text>")

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def replay_four_play(
    round36_mod,
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    start_bankroll: float,
    base_stake: float,
    max_multiplier: int,
    sum_candidate_row: pd.Series,
    bs_oe_frame: pd.DataFrame,
    sum_grouped: pd.DataFrame,
    sum_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    exact_frame: pd.DataFrame,
    exact_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    full_range = pd.DataFrame({"date": pd.date_range(sim_start, sim_end, freq="D")})

    sum_daily = full_range.merge(sum_grouped, on="date", how="left")
    sum_daily["split"] = sum_daily["split"].fillna("out_of_sample_gap")
    for col in [
        "requested_slots",
        "selected_score",
        "selected_mean_edge",
        "selected_symmetry_gap",
        "preview_raw_high_bias",
        "preview_mid_share",
        "preview_mean_sum",
    ]:
        sum_daily[col] = sum_daily[col].fillna(0.0)
    sum_daily["active"] = sum_daily.apply(lambda row: round36_mod.gate_is_on(row, sum_candidate_row), axis=1)

    combined = (
        full_range.merge(bs_oe_frame, on="date", how="left")
        .merge(sum_daily, on="date", how="left", suffixes=("", "_sum"))
        .merge(exact_frame, on="date", how="left")
    )
    combined["bs_base_real_pnl"] = combined["bs_base_real_pnl"].fillna(0.0)
    combined["oe_base_real_pnl"] = combined["oe_base_real_pnl"].fillna(0.0)
    combined["issue_exposures"] = combined["issue_exposures"].fillna(0).astype(int)
    combined["exact_hits_count"] = combined["exact_hits_count"].fillna(0).astype(int)

    bankroll = float(start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0

    bs_multiplier = 1
    sum_multiplier = 1
    exact_multiplier = 1

    bs_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    sum_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    exact_ladder_counts = {1: 0, 2: 0, 4: 0, 5: 0}
    skipped_sum_due_to_cash = 0
    skipped_exact_due_to_cash = 0

    rows: list[dict[str, object]] = []
    for _, row in combined.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll

        bs_base_real = float(row["bs_base_real_pnl"])
        oe_base_real = float(row["oe_base_real_pnl"])
        bs_active = abs(bs_base_real) > 1e-12
        applied_bs_multiplier = bs_multiplier if bs_active else 0
        bs_real = bs_base_real * applied_bs_multiplier
        oe_real = oe_base_real
        if bs_active:
            bs_ladder_counts[bs_multiplier] += 1

        sum_requested_slots = int(row["requested_slots"]) if bool(row["active"]) else 0
        sum_funded_slots = 0
        sum_book_units = 0.0
        sum_real = 0.0
        affordable_sum_slots = int(bankroll_before // (base_stake * sum_multiplier)) if sum_multiplier > 0 else 0
        if sum_requested_slots > 0:
            sum_funded_slots = min(sum_requested_slots, affordable_sum_slots)
            if sum_funded_slots > 0:
                picks = sum_picks_by_date.get(day, pd.DataFrame()).head(sum_funded_slots).copy()
                sum_book_units = float(picks["book_pnl"].sum()) if not picks.empty else 0.0
                sum_real = round36_mod.settle_real(sum_book_units * sum_multiplier) * base_stake
                sum_ladder_counts[sum_multiplier] += 1
            else:
                skipped_sum_due_to_cash += 1

        exact_requested_slots = int(row["issue_exposures"])
        exact_funded_slots = 0
        exact_book_units = 0.0
        exact_real = 0.0
        affordable_exact_slots = int(bankroll_before // (base_stake * exact_multiplier)) if exact_multiplier > 0 else 0
        if exact_requested_slots > 0:
            exact_funded_slots = min(exact_requested_slots, affordable_exact_slots)
            if exact_funded_slots > 0:
                exact_picks = exact_picks_by_date.get(day, pd.DataFrame()).head(exact_funded_slots).copy()
                exact_book_units = float(exact_picks["cell_book_pnl_units"].sum()) if not exact_picks.empty else 0.0
                exact_real = round36_mod.settle_real(exact_book_units * exact_multiplier) * base_stake
                exact_ladder_counts[exact_multiplier] += 1
            else:
                skipped_exact_due_to_cash += 1

        total_real = bs_real + oe_real + sum_real + exact_real
        bankroll += total_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "bs_active": bs_active,
                "bs_multiplier": applied_bs_multiplier,
                "bs_real_pnl": bs_real,
                "oe_real_pnl": oe_real,
                "sum_active": bool(sum_requested_slots > 0),
                "sum_requested_slots": sum_requested_slots,
                "sum_affordable_slots": affordable_sum_slots,
                "sum_funded_slots": sum_funded_slots,
                "sum_multiplier": sum_multiplier if sum_requested_slots > 0 else 0,
                "sum_book_pnl_units": sum_book_units,
                "sum_real_pnl": sum_real,
                "exact_active": bool(exact_requested_slots > 0),
                "exact_requested_slots": exact_requested_slots,
                "exact_affordable_slots": affordable_exact_slots,
                "exact_funded_slots": exact_funded_slots,
                "exact_multiplier": exact_multiplier if exact_requested_slots > 0 else 0,
                "exact_book_pnl_units": exact_book_units,
                "exact_real_pnl": exact_real,
                "total_real_pnl": total_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
                "sum_preview_raw_high_bias": float(row["preview_raw_high_bias"]),
                "sum_preview_mid_share": float(row["preview_mid_share"]),
                "sum_preview_mean_sum": float(row["preview_mean_sum"]),
            }
        )

        if bs_active:
            bs_multiplier = round36_mod.next_multiplier(bs_multiplier, max_multiplier=max_multiplier, last_real_pnl=bs_real)
        if sum_funded_slots > 0:
            sum_multiplier = round36_mod.next_multiplier(sum_multiplier, max_multiplier=max_multiplier, last_real_pnl=sum_real)
        if exact_funded_slots > 0:
            exact_multiplier = round36_mod.next_multiplier(exact_multiplier, max_multiplier=max_multiplier, last_real_pnl=exact_real)

    daily_df = pd.DataFrame(rows)
    summary_df = pd.DataFrame(
        [
            {
                "sim_start": str(sim_start.date()),
                "sim_end": str(sim_end.date()),
                "start_bankroll": start_bankroll,
                "base_stake": base_stake,
                "max_multiplier": max_multiplier,
                "source_table": SOURCE_TABLE,
                "sum_candidate_id": str(sum_candidate_row["candidate_id"]),
                "sum_gate_family": str(sum_candidate_row["gate_family"]),
                "sum_baseline_name": str(sum_candidate_row["baseline_name"]),
                "sum_preview_cut": int(sum_candidate_row["preview_cut"]),
                "exact_daily_window_id": EXACT_DAILY_WINDOW_ID,
                "exact_base_gate_id": EXACT_BASE_GATE_ID,
                "exact_obs_window": EXACT_OBS_WINDOW,
                "exact_execution_rule": EXACT_EXECUTION_RULE,
                "exact_net_win": EXACT_NET_WIN,
                "days_in_simulation": int(daily_df.shape[0]),
                "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
                "net_profit": float(daily_df["total_real_pnl"].sum()),
                "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / start_bankroll - 1.0) * 100.0),
                "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
                "min_bankroll": float(daily_df["bankroll_after_day"].min()),
                "max_drawdown": float(max_drawdown),
                "bs_profit": float(daily_df["bs_real_pnl"].sum()),
                "oe_profit": float(daily_df["oe_real_pnl"].sum()),
                "sum_profit": float(daily_df["sum_real_pnl"].sum()),
                "exact_profit": float(daily_df["exact_real_pnl"].sum()),
                "bs_active_days": int(daily_df["bs_active"].sum()),
                "sum_active_days": int(daily_df["sum_active"].sum()),
                "exact_active_days": int(daily_df["exact_active"].sum()),
                "sum_funded_slots": int(daily_df["sum_funded_slots"].sum()),
                "exact_funded_slots": int(daily_df["exact_funded_slots"].sum()),
                "skipped_sum_due_to_cash": skipped_sum_due_to_cash,
                "skipped_exact_due_to_cash": skipped_exact_due_to_cash,
                "bs_days_1x": bs_ladder_counts[1],
                "bs_days_2x": bs_ladder_counts[2],
                "bs_days_4x": bs_ladder_counts[4],
                "bs_days_5x": bs_ladder_counts[5],
                "sum_days_1x": sum_ladder_counts[1],
                "sum_days_2x": sum_ladder_counts[2],
                "sum_days_4x": sum_ladder_counts[4],
                "sum_days_5x": sum_ladder_counts[5],
                "exact_days_1x": exact_ladder_counts[1],
                "exact_days_2x": exact_ladder_counts[2],
                "exact_days_4x": exact_ladder_counts[4],
                "exact_days_5x": exact_ladder_counts[5],
            }
        ]
    )
    return daily_df, summary_df


def main() -> None:
    args = parse_args()
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)

    if str(NUMBER_WINDOW_DIR) not in sys.path:
        sys.path.insert(0, str(NUMBER_WINDOW_DIR))

    round30_mod = import_module(ROUND30_FILE, "round30_for_round36_four_play")
    round9_mod = import_module(ROUND9_FILE, "round9_for_round36_four_play")
    round16_mod = import_module(ROUND16_FILE, "round16_for_round36_four_play")
    round36_mod = import_module(ROUND36_FILE, "round36_for_round36_four_play")
    vmod = import_module(SUM_VALIDATION_FILE, "sum_validation_for_round36_four_play")
    rmod = import_module(SUM_REFINEMENT_FILE, "sum_refinement_for_round36_four_play")
    intraday_mod = import_module(SUM_INTRADAY_FILE, "sum_intraday_for_round36_four_play")
    number_window_mod = import_module(NUMBER_WINDOW_FILE, "number_daily_window_for_round36_four_play")

    issue_df = load_issue_history(vmod, query_start=args.query_start, query_end=args.query_end)
    if issue_df.empty:
        raise RuntimeError("Issue history query returned no rows")

    sum_candidate_row = load_sum_candidate_row(args.sum_candidate_id)
    bs_oe_frame = build_bs_oe_frame(
        round30_mod=round30_mod,
        round9_mod=round9_mod,
        round16_mod=round16_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
        base_stake=float(args.base_stake),
    )
    sum_grouped, sum_picks_by_date = build_sum_inputs(
        vmod=vmod,
        rmod=rmod,
        intraday_mod=intraday_mod,
        issue_df=issue_df,
        candidate_row=sum_candidate_row,
    )
    exact_frame, exact_picks_by_date = build_exact_inputs(
        number_window_mod=number_window_mod,
        round9_mod=round9_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
    )

    daily_df, summary_df = replay_four_play(
        round36_mod=round36_mod,
        sim_start=sim_start,
        sim_end=sim_end,
        start_bankroll=float(args.start_bankroll),
        base_stake=float(args.base_stake),
        max_multiplier=max(1, int(args.max_multiplier)),
        sum_candidate_row=sum_candidate_row,
        bs_oe_frame=bs_oe_frame,
        sum_grouped=sum_grouped,
        sum_picks_by_date=sum_picks_by_date,
        exact_frame=exact_frame,
        exact_picks_by_date=exact_picks_by_date,
    )

    stem = (
        f"four_play_{args.sum_candidate_id}_{EXACT_DAILY_WINDOW_ID}"
        f"_bankroll_{int(args.start_bankroll)}_stake_{int(args.base_stake)}"
        f"_m{int(args.max_multiplier)}_pks_history_{sim_start.date()}_{sim_end.date()}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    daily_df.to_csv(daily_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    print(summary_path)
    print(daily_path)


if __name__ == "__main__":
    main()
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_exact_single_line_replay.py`

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALIGNED_FILE = BASE_DIR / "pk10_round36_aligned_shared_bankroll_replay.py"
ROUND36_FILE = BASE_DIR / "pk10_round36_three_play_2025_replay.py"
ROUND9_FILE = BASE_DIR.parent / "pk10_round9_m4_deployment_refinement" / "pk10_round9_m4_deployment_refinement.py"
SUM_VALIDATION_FILE = BASE_DIR.parent / "pk10_number_sum_validation" / "pk10_number_sum_validation.py"
NUMBER_WINDOW_FILE = BASE_DIR.parent / "tmp_number_validation" / "pk10_number_daily_window_validation.py"
NUMBER_WINDOW_DIR = NUMBER_WINDOW_FILE.parent

DEFAULT_SIM_START = "2025-01-01"
DEFAULT_SIM_END = "2026-01-01"
DEFAULT_QUERY_START = "2024-01-01"
DEFAULT_QUERY_END = "2026-01-01"
DEFAULT_BANKROLL = 1000.0
DEFAULT_BASE_STAKE = 10.0
DEFAULT_MAX_MULTIPLIER = 5
DEFAULT_STAKING_MODE = "martingale_1245"
DEFAULT_MAX_FUNDED_SLOTS_PER_DAY = 0
DEFAULT_EXACT_WINDOW_ID = "exactdw_frozen_edge_low_consensus_obs192"
DEFAULT_EXACT_BASE_GATE_ID = "late|big|edge_low|same_top1_prev=all"
DEFAULT_EXACT_OBS_WINDOW = 192
DEFAULT_EXACT_EXECUTION_RULE = "front_pair_major_consensus_only"
DEFAULT_EXACT_NET_WIN = 8.9
DEFAULT_BLACKOUT_START = "06:00:00"
DEFAULT_BLACKOUT_END = "07:00:00"


def import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay the frozen PK10 exact daily-window rule as a single-line bankroll.")
    parser.add_argument("--sim-start", default=DEFAULT_SIM_START)
    parser.add_argument("--sim-end", default=DEFAULT_SIM_END)
    parser.add_argument("--query-start", default=DEFAULT_QUERY_START)
    parser.add_argument("--query-end", default=DEFAULT_QUERY_END)
    parser.add_argument("--start-bankroll", type=float, default=DEFAULT_BANKROLL)
    parser.add_argument("--base-stake", type=float, default=DEFAULT_BASE_STAKE)
    parser.add_argument("--max-multiplier", type=int, default=DEFAULT_MAX_MULTIPLIER)
    parser.add_argument(
        "--staking-mode",
        choices=("fixed", "martingale_linear", "martingale_1245"),
        default=DEFAULT_STAKING_MODE,
    )
    parser.add_argument(
        "--max-funded-slots-per-day",
        type=int,
        default=DEFAULT_MAX_FUNDED_SLOTS_PER_DAY,
        help="Cap funded exact slots per active day; 0 means no extra cap.",
    )
    parser.add_argument("--exact-window-id", default=DEFAULT_EXACT_WINDOW_ID)
    parser.add_argument("--exact-base-gate-id", default=DEFAULT_EXACT_BASE_GATE_ID)
    parser.add_argument("--exact-obs-window", type=int, default=DEFAULT_EXACT_OBS_WINDOW)
    parser.add_argument("--exact-execution-rule", default=DEFAULT_EXACT_EXECUTION_RULE)
    parser.add_argument("--exact-net-win", type=float, default=DEFAULT_EXACT_NET_WIN)
    parser.add_argument("--blackout-start", default=DEFAULT_BLACKOUT_START)
    parser.add_argument("--blackout-end", default=DEFAULT_BLACKOUT_END)
    return parser.parse_args()


def next_multiplier(current: int, staking_mode: str, max_multiplier: int, last_real_pnl: float) -> int:
    if staking_mode == "fixed":
        return 1
    if last_real_pnl < 0.0:
        if staking_mode == "martingale_linear":
            return min(current + 1, max_multiplier)
        if staking_mode == "martingale_1245":
            if current < 2:
                return min(2, max_multiplier)
            if current < 4:
                return min(4, max_multiplier)
            return min(8, max_multiplier)
    return 1


def replay_exact_single_line(
    round36_mod,
    exact_frame: pd.DataFrame,
    exact_picks_by_date: dict[pd.Timestamp, pd.DataFrame],
    sim_start: pd.Timestamp,
    sim_end: pd.Timestamp,
    start_bankroll: float,
    base_stake: float,
    staking_mode: str,
    max_multiplier: int,
    max_funded_slots_per_day: int,
    exact_window_id: str,
    exact_base_gate_id: str,
    exact_obs_window: int,
    exact_execution_rule: str,
    exact_net_win: float,
    blackout_start: str,
    blackout_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bankroll = float(start_bankroll)
    peak = bankroll
    min_bankroll = bankroll
    max_drawdown = 0.0
    exact_multiplier = 1
    skipped_exact_due_to_cash = 0
    exact_ladder_counts = {mult: 0 for mult in range(1, max_multiplier + 1)}

    rows: list[dict[str, object]] = []
    for _, row in exact_frame.iterrows():
        day = pd.Timestamp(row["date"])
        bankroll_before = bankroll
        exact_requested_slots = int(row["issue_exposures"])
        exact_funded_slots = 0
        exact_book_units = 0.0
        exact_real = 0.0
        affordable_exact_slots = max(0, int(bankroll_before // (base_stake * exact_multiplier))) if exact_multiplier > 0 else 0
        if exact_requested_slots > 0:
            cap_slots = exact_requested_slots
            if max_funded_slots_per_day > 0:
                cap_slots = min(cap_slots, max_funded_slots_per_day)
            exact_funded_slots = min(cap_slots, affordable_exact_slots)
            if exact_funded_slots > 0:
                exact_picks = exact_picks_by_date.get(day, pd.DataFrame()).head(exact_funded_slots).copy()
                exact_book_units = float(exact_picks["cell_book_pnl_units"].sum()) if not exact_picks.empty else 0.0
                exact_real = round36_mod.settle_real(exact_book_units * exact_multiplier) * base_stake
                exact_ladder_counts[int(exact_multiplier)] += 1
            else:
                skipped_exact_due_to_cash += 1

        bankroll += exact_real
        peak = max(peak, bankroll)
        min_bankroll = min(min_bankroll, bankroll)
        drawdown = bankroll - peak
        max_drawdown = min(max_drawdown, drawdown)

        rows.append(
            {
                "date": day,
                "bankroll_before_day": bankroll_before,
                "exact_active": bool(exact_requested_slots > 0),
                "exact_requested_slots": exact_requested_slots,
                "exact_affordable_slots": affordable_exact_slots,
                "exact_funded_slots": exact_funded_slots,
                "exact_multiplier": exact_multiplier if exact_requested_slots > 0 else 0,
                "exact_book_pnl_units": exact_book_units,
                "exact_real_pnl": exact_real,
                "bankroll_after_day": bankroll,
                "running_peak_bankroll": peak,
                "drawdown_from_peak": drawdown,
            }
        )

        if exact_funded_slots > 0:
            exact_multiplier = next_multiplier(
                exact_multiplier,
                staking_mode=staking_mode,
                max_multiplier=max_multiplier,
                last_real_pnl=exact_real,
            )

    daily_df = pd.DataFrame(rows)
    summary_row = {
        "sim_start": str(sim_start.date()),
        "sim_end": str(sim_end.date()),
        "start_bankroll": start_bankroll,
        "base_stake": base_stake,
        "staking_mode": staking_mode,
        "max_multiplier": max_multiplier,
        "max_funded_slots_per_day": max_funded_slots_per_day,
        "exact_window_id": exact_window_id,
        "exact_base_gate_id": exact_base_gate_id,
        "exact_obs_window": int(exact_obs_window),
        "exact_execution_rule": exact_execution_rule,
        "exact_net_win": float(exact_net_win),
        "blackout_start": blackout_start,
        "blackout_end": blackout_end,
        "days_in_simulation": int(daily_df.shape[0]),
        "final_bankroll": float(daily_df["bankroll_after_day"].iloc[-1]),
        "net_profit": float(daily_df["exact_real_pnl"].sum()),
        "roi_on_start_bankroll_pct": float((daily_df["bankroll_after_day"].iloc[-1] / start_bankroll - 1.0) * 100.0),
        "peak_bankroll": float(daily_df["running_peak_bankroll"].max()),
        "min_bankroll": float(daily_df["bankroll_after_day"].min()),
        "max_drawdown": float(max_drawdown),
        "exact_profit": float(daily_df["exact_real_pnl"].sum()),
        "exact_active_days": int(daily_df["exact_active"].sum()),
        "exact_requested_slots": int(daily_df["exact_requested_slots"].sum()),
        "exact_funded_slots": int(daily_df["exact_funded_slots"].sum()),
        "skipped_exact_due_to_cash": skipped_exact_due_to_cash,
    }
    for mult in range(1, max_multiplier + 1):
        summary_row[f"exact_days_{mult}x"] = exact_ladder_counts.get(mult, 0)
    summary_df = pd.DataFrame([summary_row])
    return daily_df, summary_df


def main() -> None:
    global args
    args = parse_args()
    sim_start = pd.Timestamp(args.sim_start)
    sim_end = pd.Timestamp(args.sim_end)

    if str(NUMBER_WINDOW_DIR) not in sys.path:
        sys.path.insert(0, str(NUMBER_WINDOW_DIR))

    aligned_mod = import_module(ALIGNED_FILE, "round36_aligned_exact_single")
    round36_mod = import_module(ROUND36_FILE, "round36_exact_single")
    round9_mod = import_module(ROUND9_FILE, "round9_exact_single")
    vmod = import_module(SUM_VALIDATION_FILE, "sum_validation_exact_single")
    number_window_mod = import_module(NUMBER_WINDOW_FILE, "number_window_exact_single")

    effective_query_end = aligned_mod.complete_week_query_end(sim_end, args.query_end)
    issue_df = aligned_mod.load_issue_history(vmod, query_start=args.query_start, query_end=str(effective_query_end.date()))
    if issue_df.empty:
        raise RuntimeError("Issue history query returned no rows")

    blackout_start = aligned_mod.parse_time_of_day(args.blackout_start)
    blackout_end = aligned_mod.parse_time_of_day(args.blackout_end)
    allowed_lookup = aligned_mod.build_allowed_trade_lookup(
        aligned_mod.build_issue_schedule_frame(issue_df),
        blackout_start=blackout_start,
        blackout_end=blackout_end,
    )

    exact_frame, exact_picks_by_date = aligned_mod.build_exact_inputs(
        number_window_mod=number_window_mod,
        round9_mod=round9_mod,
        issue_df=issue_df,
        sim_start=sim_start,
        sim_end=sim_end,
        base_gate_id=args.exact_base_gate_id,
        obs_window=int(args.exact_obs_window),
        execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        allowed_lookup=allowed_lookup,
    )

    daily_df, summary_df = replay_exact_single_line(
        round36_mod=round36_mod,
        exact_frame=exact_frame,
        exact_picks_by_date=exact_picks_by_date,
        sim_start=sim_start,
        sim_end=sim_end,
        start_bankroll=float(args.start_bankroll),
        base_stake=float(args.base_stake),
        staking_mode=args.staking_mode,
        max_multiplier=max(1, int(args.max_multiplier)),
        max_funded_slots_per_day=max(0, int(args.max_funded_slots_per_day)),
        exact_window_id=args.exact_window_id,
        exact_base_gate_id=args.exact_base_gate_id,
        exact_obs_window=int(args.exact_obs_window),
        exact_execution_rule=args.exact_execution_rule,
        exact_net_win=float(args.exact_net_win),
        blackout_start=args.blackout_start,
        blackout_end=args.blackout_end,
    )

    blackout_tag = ""
    if blackout_start is not None and blackout_end is not None:
        blackout_tag = f"_blackout_{args.blackout_start.replace(':', '')}_{args.blackout_end.replace(':', '')}"

    if args.staking_mode == DEFAULT_STAKING_MODE and int(args.max_multiplier) == DEFAULT_MAX_MULTIPLIER:
        staking_tag = f"_m{int(args.max_multiplier)}"
    elif args.staking_mode == "fixed":
        staking_tag = "_fixed"
    else:
        staking_tag = f"_{args.staking_mode}_max{int(args.max_multiplier)}"
    cap_tag = "" if int(args.max_funded_slots_per_day) <= 0 else f"_cap{int(args.max_funded_slots_per_day)}"

    stem = (
        f"exact_single_line_{args.exact_window_id}"
        f"_bankroll_{int(args.start_bankroll)}_stake_{int(args.base_stake)}"
        f"{staking_tag}{cap_tag}{blackout_tag}_pks_history_{sim_start.date()}_{sim_end.date()}"
    )
    daily_path = OUTPUT_DIR / f"{stem}_daily.csv"
    summary_path = OUTPUT_DIR / f"{stem}_summary.csv"
    curve_path = OUTPUT_DIR / f"{stem}_curve.svg"

    daily_df.to_csv(daily_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    aligned_mod.build_svg(
        daily_df.rename(columns={"exact_real_pnl": "total_real_pnl"}),
        curve_path,
        title=f"Exact Single-Line Curve | {sim_start.date()} -> {sim_end.date()} | {args.exact_window_id}",
    )

    print(summary_path)
    print(daily_path)
    print(curve_path)


if __name__ == "__main__":
    main()
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/render_round36_curves.py`

```python
#!/usr/bin/env python3
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "round36_outputs"


@dataclass(frozen=True)
class CurveSpec:
    label: str
    daily_path: Path
    color: str


@dataclass(frozen=True)
class StitchedCurveSpec:
    label: str
    daily_paths: tuple[Path, ...]
    color: str


CURVES = [
    CurveSpec(
        label="稳健版 intraday_1007",
        daily_path=OUTPUT_DIR / "three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
        color="#2563eb",
    ),
    CurveSpec(
        label="进攻版 intraday_1037",
        daily_path=OUTPUT_DIR / "three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
        color="#dc2626",
    ),
]


STITCHED_CURVES = [
    StitchedCurveSpec(
        label="稳健版 intraday_1007",
        daily_paths=(
            OUTPUT_DIR / "three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
            OUTPUT_DIR / "three_play_intraday_1007_bankroll_11823_stake_10_m5_2026-01-01_2026-04-12_daily.csv",
        ),
        color="#2563eb",
    ),
    StitchedCurveSpec(
        label="进攻版 intraday_1037",
        daily_paths=(
            OUTPUT_DIR / "three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv",
            OUTPUT_DIR / "three_play_intraday_1037_bankroll_17169_stake_10_m5_2026-01-01_2026-04-12_daily.csv",
        ),
        color="#dc2626",
    ),
]


def load_curve_paths(paths: tuple[Path, ...] | list[Path]) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    day_index = 0
    for path in paths:
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                day_index += 1
                rows.append(
                    {
                        "day_index": day_index,
                        "date": row["date"],
                        "bankroll_after_day": float(row["bankroll_after_day"]),
                        "drawdown_from_peak": float(row["drawdown_from_peak"]),
                        "total_real_pnl": float(row["total_real_pnl"]),
                    }
                )
    return rows


def load_curve(spec: CurveSpec) -> list[dict[str, float | int | str]]:
    return load_curve_paths((spec.daily_path,))


def load_stitched_curve(spec: StitchedCurveSpec) -> list[dict[str, float | int | str]]:
    return load_curve_paths(spec.daily_paths)


def x_scale(day_index: int, total_days: int, left: float, plot_w: float) -> float:
    if total_days <= 1:
        return left
    return left + (day_index - 1) * plot_w / (total_days - 1)


def y_scale(value: float, lo: float, hi: float, top: float, height: float) -> float:
    if hi == lo:
        return top + height / 2
    frac = (value - lo) / (hi - lo)
    return top + height - frac * height


def build_path(
    values: list[float],
    lo: float,
    hi: float,
    top: float,
    height: float,
    left: float,
    plot_w: float,
) -> str:
    total_days = len(values)
    parts: list[str] = []
    for idx, value in enumerate(values, start=1):
        x = x_scale(idx, total_days, left, plot_w)
        y = y_scale(value, lo, hi, top, height)
        parts.append(f"{'M' if idx == 1 else 'L'} {x:.2f} {y:.2f}")
    return " ".join(parts)


def add_grid(
    lines: list[str],
    left: float,
    top: float,
    plot_w: float,
    plot_h: float,
    lo: float,
    hi: float,
    day_labels: list[tuple[int, str]],
) -> None:
    lines.append(
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" rx="14" fill="#ffffff" stroke="#d1d5db"/>'
    )
    for i in range(5):
        frac = i / 4
        y = top + frac * plot_h
        value = hi - frac * (hi - lo)
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e7eb" stroke-dasharray="4 4"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#6b7280">{value:.0f}</text>'
        )
    total_days = day_labels[-1][0]
    for day_index, label in day_labels:
        x = x_scale(day_index, total_days, left, plot_w)
        lines.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#f3f4f6"/>'
        )
        lines.append(
            f'<text x="{x:.2f}" y="{top + plot_h + 20:.2f}" text-anchor="middle" font-size="12" fill="#6b7280">{label}</text>'
        )


def build_date_labels(
    rows: list[dict[str, float | int | str]],
    labels: list[tuple[str, str]],
) -> list[tuple[int, str]]:
    date_to_idx = {str(row["date"]): int(row["day_index"]) for row in rows}
    out: list[tuple[int, str]] = []
    for date_text, label in labels:
        day_index = date_to_idx.get(date_text)
        if day_index is not None:
            out.append((day_index, label))
    return out


def add_vertical_marker(
    lines: list[str],
    day_index: int,
    total_days: int,
    left: float,
    plot_w: float,
    top: float,
    plot_h: float,
    label: str,
) -> None:
    x = x_scale(day_index, total_days, left, plot_w)
    lines.append(
        f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#94a3b8" stroke-width="1.6" stroke-dasharray="6 6"/>'
    )
    lines.append(
        f'<text x="{x + 8:.2f}" y="{top + 18:.2f}" font-size="12" fill="#475569">{label}</text>'
    )


def build_comparison_svg(curves: list[tuple[CurveSpec, list[dict[str, float | int | str]]]]) -> Path:
    width = 1400
    height = 860
    left = 92
    right = 52
    top1 = 92
    panel_h = 260
    gap = 110
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [
        float(row["bankroll_after_day"])
        for _, rows in curves
        for row in rows
    ]
    drawdown_values = [
        float(row["drawdown_from_peak"])
        for _, rows in curves
        for row in rows
    ]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = [
        (1, "D1"),
        (32, "D32"),
        (91, "D91"),
        (182, "D182"),
        (274, "D274"),
        (365, "D365"),
    ]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">Round36 两版本资金曲线（日维度）</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">本金 1000 / 基投 10 / 大小马丁5层 + 单双固定1x + 和值独立马丁5层</text>',
    ]

    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)

    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')

    legend_x = width - 280
    legend_y = 42
    for i, (spec, rows) in enumerate(curves):
        y = legend_y + i * 24
        lines.append(
            f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 30}" y2="{y}" stroke="{spec.color}" stroke-width="4" stroke-linecap="round"/>'
        )
        lines.append(
            f'<text x="{legend_x + 40}" y="{y + 4}" font-size="13" fill="#334155">{spec.label}</text>'
        )

        bankroll_path = build_path(
            [float(row["bankroll_after_day"]) for row in rows],
            bank_lo,
            bank_hi,
            top1,
            panel_h,
            left,
            plot_w,
        )
        drawdown_path = build_path(
            [float(row["drawdown_from_peak"]) for row in rows],
            dd_lo,
            dd_hi,
            top2,
            panel_h,
            left,
            plot_w,
        )
        lines.append(
            f'<path d="{bankroll_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        lines.append(
            f'<path d="{drawdown_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )

        final_row = rows[-1]
        final_x = x_scale(int(final_row["day_index"]), len(rows), left, plot_w)
        final_y = y_scale(float(final_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
        lines.append(
            f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
        )
        lines.append(
            f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(final_row["bankroll_after_day"]):.0f}</text>'
        )

    lines.append("</svg>")

    output_path = OUTPUT_DIR / "round36_two_version_daily_curve_comparison.svg"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_single_svg(spec: CurveSpec, rows: list[dict[str, float | int | str]]) -> Path:
    width = 1320
    height = 720
    left = 92
    right = 52
    top1 = 92
    panel_h = 220
    gap = 90
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [float(row["bankroll_after_day"]) for row in rows]
    drawdown_values = [float(row["drawdown_from_peak"]) for row in rows]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = [
        (1, "D1"),
        (32, "D32"),
        (91, "D91"),
        (182, "D182"),
        (274, "D274"),
        (365, "D365"),
    ]

    bank_path = build_path(bankroll_values, bank_lo, bank_hi, top1, panel_h, left, plot_w)
    dd_path = build_path(drawdown_values, dd_lo, dd_hi, top2, panel_h, left, plot_w)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">{spec.label} 资金曲线（日维度）</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">X 轴为 2025 年日序列，Y 轴分别为资金余额与相对峰值回撤</text>',
    ]
    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)
    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')
    lines.append(
        f'<path d="{bank_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    lines.append(
        f'<path d="{dd_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    last_row = rows[-1]
    final_x = x_scale(int(last_row["day_index"]), len(rows), left, plot_w)
    final_y = y_scale(float(last_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
    lines.append(
        f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
    )
    lines.append(
        f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(last_row["bankroll_after_day"]):.0f}</text>'
    )
    lines.append("</svg>")

    output_name = f"{spec.daily_path.stem}_curve.svg"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_overlay_svg(spec: CurveSpec, rows: list[dict[str, float | int | str]]) -> Path:
    width = 1320
    height = 620
    left = 92
    right = 78
    top = 96
    bottom = 84
    plot_w = width - left - right
    plot_h = height - top - bottom

    pnl_values = [float(row["total_real_pnl"]) for row in rows]
    bankroll_values = [float(row["bankroll_after_day"]) for row in rows]

    pnl_lo = min(min(pnl_values), 0.0)
    pnl_hi = max(max(pnl_values), 0.0)
    if pnl_lo == pnl_hi:
        pnl_hi = pnl_lo + 1.0

    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    if bank_lo == bank_hi:
        bank_hi = bank_lo + 1.0

    total_days = len(rows)
    day_labels = [
        (1, "D1"),
        (32, "D32"),
        (91, "D91"),
        (182, "D182"),
        (274, "D274"),
        (365, "D365"),
    ]
    zero_y = y_scale(0.0, pnl_lo, pnl_hi, top, plot_h)
    bar_step = plot_w / max(total_days, 1)
    bar_w = max(1.2, min(3.0, bar_step * 0.72))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">{spec.label} 日盈亏 + 资金曲线</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">左轴为日盈亏，右轴为日终资金；柱状按天，折线为累计资金</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" rx="14" fill="#ffffff" stroke="#d1d5db"/>',
    ]

    for i in range(6):
        frac = i / 5
        y = top + frac * plot_h
        pnl_value = pnl_hi - frac * (pnl_hi - pnl_lo)
        bank_value = bank_hi - frac * (bank_hi - bank_lo)
        lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e7eb" stroke-dasharray="4 4"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#6b7280">{pnl_value:.0f}</text>'
        )
        lines.append(
            f'<text x="{left + plot_w + 12}" y="{y + 4:.2f}" font-size="12" fill="#64748b">{bank_value:.0f}</text>'
        )

    lines.append(
        f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + plot_w}" y2="{zero_y:.2f}" stroke="#94a3b8" stroke-width="1.4"/>'
    )

    for day_index, label in day_labels:
        x = x_scale(day_index, total_days, left, plot_w)
        lines.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#f3f4f6"/>'
        )
        lines.append(
            f'<text x="{x:.2f}" y="{top + plot_h + 22:.2f}" text-anchor="middle" font-size="12" fill="#6b7280">{label}</text>'
        )

    for row in rows:
        day_index = int(row["day_index"])
        pnl = float(row["total_real_pnl"])
        x = x_scale(day_index, total_days, left, plot_w)
        y = y_scale(pnl, pnl_lo, pnl_hi, top, plot_h)
        rect_x = x - bar_w / 2
        rect_y = min(y, zero_y)
        rect_h = max(1.0, abs(zero_y - y))
        fill = "#16a34a" if pnl >= 0 else "#dc2626"
        lines.append(
            f'<rect x="{rect_x:.2f}" y="{rect_y:.2f}" width="{bar_w:.2f}" height="{rect_h:.2f}" fill="{fill}" opacity="0.55"/>'
        )

    bankroll_path = build_path(
        bankroll_values,
        bank_lo,
        bank_hi,
        top,
        plot_h,
        left,
        plot_w,
    )
    lines.append(
        f'<path d="{bankroll_path}" fill="none" stroke="{spec.color}" stroke-width="3.0" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    legend_x = width - 300
    legend_y = 42
    lines.append(
        f'<rect x="{legend_x}" y="{legend_y - 12}" width="12" height="12" fill="#16a34a" opacity="0.55"/>'
    )
    lines.append(
        f'<text x="{legend_x + 18}" y="{legend_y - 2}" font-size="12" fill="#334155">正日盈亏</text>'
    )
    lines.append(
        f'<rect x="{legend_x + 92}" y="{legend_y - 12}" width="12" height="12" fill="#dc2626" opacity="0.55"/>'
    )
    lines.append(
        f'<text x="{legend_x + 110}" y="{legend_y - 2}" font-size="12" fill="#334155">负日盈亏</text>'
    )
    lines.append(
        f'<line x1="{legend_x + 188}" y1="{legend_y - 6}" x2="{legend_x + 220}" y2="{legend_y - 6}" stroke="{spec.color}" stroke-width="3" stroke-linecap="round"/>'
    )
    lines.append(
        f'<text x="{legend_x + 228}" y="{legend_y - 2}" font-size="12" fill="#334155">资金曲线</text>'
    )

    last_row = rows[-1]
    final_x = x_scale(int(last_row["day_index"]), total_days, left, plot_w)
    final_y = y_scale(float(last_row["bankroll_after_day"]), bank_lo, bank_hi, top, plot_h)
    lines.append(
        f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
    )
    lines.append(
        f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(last_row["bankroll_after_day"]):.0f}</text>'
    )
    lines.append("</svg>")

    output_name = f"{spec.daily_path.stem}_pnl_overlay.svg"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_stitched_comparison_svg(
    curves: list[tuple[StitchedCurveSpec, list[dict[str, float | int | str]]]]
) -> Path:
    width = 1440
    height = 860
    left = 92
    right = 52
    top1 = 92
    panel_h = 260
    gap = 110
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [
        float(row["bankroll_after_day"])
        for _, rows in curves
        for row in rows
    ]
    drawdown_values = [
        float(row["drawdown_from_peak"])
        for _, rows in curves
        for row in rows
    ]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = build_date_labels(
        curves[0][1],
        [
            ("2025-01-01", "2025-01"),
            ("2025-04-01", "2025-04"),
            ("2025-07-01", "2025-07"),
            ("2025-10-01", "2025-10"),
            ("2026-01-01", "2026-01"),
            ("2026-04-12", "2026-04-12"),
        ],
    )
    total_days = len(curves[0][1])
    year_switch_idx = next(
        int(row["day_index"]) for row in curves[0][1] if str(row["date"]) == "2026-01-01"
    )

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">Round36 两版本连续资金曲线</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">区间 2025-01-01 到 2026-04-12，2026 段按承接 2025 年末资金继续滚动</text>',
    ]

    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)
    add_vertical_marker(lines, year_switch_idx, total_days, left, plot_w, top1, panel_h, "2026 续接起点")
    add_vertical_marker(lines, year_switch_idx, total_days, left, plot_w, top2, panel_h, "2026 续接起点")

    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')

    legend_x = width - 280
    legend_y = 42
    for i, (spec, rows) in enumerate(curves):
        y = legend_y + i * 24
        lines.append(
            f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 30}" y2="{y}" stroke="{spec.color}" stroke-width="4" stroke-linecap="round"/>'
        )
        lines.append(
            f'<text x="{legend_x + 40}" y="{y + 4}" font-size="13" fill="#334155">{spec.label}</text>'
        )

        bankroll_path = build_path(
            [float(row["bankroll_after_day"]) for row in rows],
            bank_lo,
            bank_hi,
            top1,
            panel_h,
            left,
            plot_w,
        )
        drawdown_path = build_path(
            [float(row["drawdown_from_peak"]) for row in rows],
            dd_lo,
            dd_hi,
            top2,
            panel_h,
            left,
            plot_w,
        )
        lines.append(
            f'<path d="{bankroll_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        lines.append(
            f'<path d="{drawdown_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )

        final_row = rows[-1]
        final_x = x_scale(int(final_row["day_index"]), len(rows), left, plot_w)
        final_y = y_scale(float(final_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
        lines.append(
            f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
        )
        lines.append(
            f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(final_row["bankroll_after_day"]):.0f}</text>'
        )

    lines.append("</svg>")

    output_path = OUTPUT_DIR / "round36_two_version_continuous_2025-01-01_2026-04-12_curve_comparison.svg"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_stitched_single_svg(spec: StitchedCurveSpec, rows: list[dict[str, float | int | str]]) -> Path:
    width = 1360
    height = 720
    left = 92
    right = 52
    top1 = 92
    panel_h = 220
    gap = 90
    top2 = top1 + panel_h + gap
    plot_w = width - left - right

    bankroll_values = [float(row["bankroll_after_day"]) for row in rows]
    drawdown_values = [float(row["drawdown_from_peak"]) for row in rows]
    bank_lo = min(bankroll_values)
    bank_hi = max(bankroll_values)
    dd_lo = min(drawdown_values)
    dd_hi = 0.0
    day_labels = build_date_labels(
        rows,
        [
            ("2025-01-01", "2025-01"),
            ("2025-04-01", "2025-04"),
            ("2025-07-01", "2025-07"),
            ("2025-10-01", "2025-10"),
            ("2026-01-01", "2026-01"),
            ("2026-04-12", "2026-04-12"),
        ],
    )
    year_switch_idx = next(int(row["day_index"]) for row in rows if str(row["date"]) == "2026-01-01")

    bank_path = build_path(bankroll_values, bank_lo, bank_hi, top1, panel_h, left, plot_w)
    dd_path = build_path(drawdown_values, dd_lo, dd_hi, top2, panel_h, left, plot_w)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="92" y="42" font-size="28" font-weight="700" fill="#0f172a">{spec.label} 连续资金曲线</text>',
        '<text x="92" y="68" font-size="14" fill="#475569">区间 2025-01-01 到 2026-04-12，2026 段按承接 2025 年末资金续算</text>',
    ]
    add_grid(lines, left, top1, plot_w, panel_h, bank_lo, bank_hi, day_labels)
    add_grid(lines, left, top2, plot_w, panel_h, dd_lo, dd_hi, day_labels)
    add_vertical_marker(lines, year_switch_idx, len(rows), left, plot_w, top1, panel_h, "2026 续接起点")
    add_vertical_marker(lines, year_switch_idx, len(rows), left, plot_w, top2, panel_h, "2026 续接起点")
    lines.append(f'<text x="{left}" y="{top1 - 16}" font-size="16" font-weight="600" fill="#0f172a">资金曲线</text>')
    lines.append(f'<text x="{left}" y="{top2 - 16}" font-size="16" font-weight="600" fill="#0f172a">回撤曲线</text>')
    lines.append(
        f'<path d="{bank_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    lines.append(
        f'<path d="{dd_path}" fill="none" stroke="{spec.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    last_row = rows[-1]
    final_x = x_scale(int(last_row["day_index"]), len(rows), left, plot_w)
    final_y = y_scale(float(last_row["bankroll_after_day"]), bank_lo, bank_hi, top1, panel_h)
    lines.append(
        f'<circle cx="{final_x:.2f}" cy="{final_y:.2f}" r="4.8" fill="{spec.color}" stroke="#ffffff" stroke-width="2"/>'
    )
    lines.append(
        f'<text x="{final_x + 10:.2f}" y="{final_y - 8:.2f}" font-size="12" fill="{spec.color}">{float(last_row["bankroll_after_day"]):.0f}</text>'
    )
    lines.append("</svg>")

    candidate_id = spec.label.split()[-1]
    output_path = OUTPUT_DIR / f"three_play_{candidate_id}_continuous_2025-01-01_2026-04-12_curve.svg"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    loaded = [(spec, load_curve(spec)) for spec in CURVES]
    stitched_loaded = [(spec, load_stitched_curve(spec)) for spec in STITCHED_CURVES]
    outputs = [build_comparison_svg(loaded)]
    outputs.append(build_stitched_comparison_svg(stitched_loaded))
    outputs.extend(build_single_svg(spec, rows) for spec, rows in loaded)
    outputs.extend(build_stitched_single_svg(spec, rows) for spec, rows in stitched_loaded)
    outputs.extend(build_overlay_svg(spec, rows) for spec, rows in loaded)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
```


---

## Source: `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/THREAD_SHARED_MEMORY.md`

```markdown
# Thread Shared Memory

更新时间：2026-04-19

## 目标

本线程围绕 `PK10` 三玩法联合推演展开，口径为：

- `大小` 使用 `round30/32` 已验证窗口，按日级 `1x -> 2x -> 4x -> 5x` 马丁。
- `单双` 沿用现有已验证版本，固定 `1x`，不单独新造马丁。
- `冠亚和值` 使用 `pk10_number_sum_validation` 的 `intraday gate` 候选，独立 `1x -> 2x -> 4x -> 5x` 马丁。
- 三条线共用一条总资金曲线，同一天允许同时投注。

当前主编排脚本：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_three_play_2025_replay.py`

当前画图脚本：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/render_round36_curves.py`


## 数据源与限制

三玩法共同可用的公共日期区间，不是取最早数据库日期，而是取三条源数据的交集。

关键源数据：

- `大小/单双` 日级源：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round30_daily85_exact_transfer/round30_outputs/round30_transfer_daily.csv`
- `和值` 候选总表：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_number_sum_validation/number_sum_intraday_gate_outputs_db6y_daily85/intraday_gate_summary.csv`
- `和值` 明细基线：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_number_sum_validation/number_sum_intraday_gate_outputs_db6y_daily85/base_stable_020_cut192_intraday_detail.csv`

已确认的日期范围：

- `round30_transfer_daily.csv`：`2025-01-06 -> 2026-04-12`
- `base_stable_020_cut192_intraday_detail.csv`：`2020-10-05 -> 2026-04-12`

因此三玩法联合回放的全量公共区间为：

- `2025-01-06 -> 2026-04-12`


## 关键策略口径

### 1. 三玩法联合回放口径

- 本金默认：`1000`
- 基投默认：`10`
- `大小`：使用 `round30` 的 `bs_guardrail_daily85`
- `大小+单双` 混合源：`bs_plus_oe_mode_non_cash_daily85`
- `大小单双` 原始日结果来自 stake `50`，联合回放时线性缩放为 stake `10`
- `大小` 马丁更新依据：仅按 `大小` 自身盈亏推进
- `单双` 固定 `1x`
- `和值` 使用入选 candidate 的日内筛窗结果，拥有独立马丁档位

### 2. 和值窗口识别

`和值` 不是等当天 `1152` 期结束后才知道，而是用日内前缀判窗。

当前两个主要版本：

- `intraday_1007`
  - `preview_cut = 192`
  - `gate_family = high_mid`
  - 条件：
    - `preview_raw_high_bias >= 0.02`
    - `preview_mid_share >= 0.46`
    - `selected_mean_edge <= 0.96`
- `intraday_1037`
  - `preview_cut = 192`
  - `gate_family = mid_only`
  - 条件：
    - `preview_mid_share >= 0.44`
    - `selected_mean_edge <= 0.96`

结论：

- 前 `192` 期结束后，就知道当天后续是不是和值窗口。
- 不需要等 `1152` 期全部结束。

### 3. 定位胆窗口识别

`定位胆` 不是整天只判一次窗，而是按日内观测切点判断晚段固定槽位是否出手。

代码里关键常量：

- `late_slots = 577, 961, 1152`
- `control_slots = 193, 385, 769`
- `obs_windows = 192, 384, 576`

执行理解：

- 最早在 `第192期结束后` 开始找机会
- 后续在 `第384期`、`第576期` 可做更晚的再确认
- 真正目标是 `577 / 961 / 1152`
- `193 / 385 / 769` 是控制槽位，不是最终实盘目标


## 已完成的核心结果

### A. 2025 全年独立起跑

区间：

- `2025-01-01 -> 2025-12-31`

稳健版 `intraday_1007`

- 期末资金：`11823.4025`
- 净利润：`10823.4025`
- ROI：`1082.34025%`
- 最大回撤：`-1136.455`
- 最低资金：`367.0`
- 贡献：
  - `大小 6993.2475`
  - `单双 1347.155`
  - `和值 2483.0`
- 实际投注天数：`178`

进攻版 `intraday_1037`

- 期末资金：`17169.9025`
- 净利润：`16169.9025`
- ROI：`1616.99025%`
- 最大回撤：`-1710.0`
- 最低资金：`966.0`
- 贡献：
  - `大小 6993.2475`
  - `单双 1347.155`
  - `和值 7829.5`
- 实际投注天数：`329`

对应新命名日表：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv`
- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily.csv`

### B. 2026-01-01 到 2026-04-12 独立起跑

区间：

- `2026-01-01 -> 2026-04-12`

稳健版 `intraday_1007`

- 期末资金：`12391.8675`
- 净利润：`11391.8675`
- ROI：`1139.18675%`
- 最大回撤：`-1850.565`
- 最低资金：`897.4425`

进攻版 `intraday_1037`

- 期末资金：`13677.8675`
- 净利润：`12677.8675`
- ROI：`1267.78675%`
- 最大回撤：`-2054.565`
- 最低资金：`871.9425`

### C. 2026-01-01 到 2026-04-12 承接 2025 年末资金

稳健版 `intraday_1007`

- 起始资金：`11823.4025`
- 期末资金：`23215.27`
- 区间净利润：`11391.8675`
- 区间收益率：`96.35016231579705%`
- 最低资金：`11720.845`
- 最大回撤：`-1850.565`

文件：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1007_bankroll_11823_stake_10_m5_2026-01-01_2026-04-12_daily.csv`

进攻版 `intraday_1037`

- 起始资金：`17169.9025`
- 期末资金：`29847.77`
- 区间净利润：`12677.8675`
- 区间收益率：`73.83773728476339%`
- 最低资金：`17041.845`
- 最大回撤：`-2054.565`

文件：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1037_bankroll_17169_stake_10_m5_2026-01-01_2026-04-12_daily.csv`

### D. 全量公共区间总利润

区间：

- `2025-01-06 -> 2026-04-12`
- 共 `462` 天

稳健版 `intraday_1007`

- 总利润：`22545.27`
- 期末资金：`23545.27`
- ROI：`2254.53%`
- 最大回撤：`-1850.57`
- 最低资金：`337.00`
- 实际投注天数：`278`
- `大小/单双` 活跃天数：`196`
- `和值` 活跃天数：`145`
- `和值 funded slots`：`408`
- `skipped_sum_due_to_cash = 0`

文件：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-06_2026-04-12_summary.csv`
- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-06_2026-04-12_daily.csv`

进攻版 `intraday_1037`

- 总利润：`27983.77`
- 期末资金：`28983.77`
- ROI：`2798.38%`
- 最大回撤：`-2054.57`
- 最低资金：`817.00`
- 实际投注天数：`427`
- `大小/单双` 活跃天数：`196`
- `和值` 活跃天数：`408`
- `和值 funded slots`：`1129`
- `skipped_sum_due_to_cash = 0`

文件：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-06_2026-04-12_summary.csv`
- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-06_2026-04-12_daily.csv`

解释：

- 如果只看已通过接受条件的主版本，应优先用 `intraday_1007`
- `intraday_1037` 利润更高，但候选表里 `acceptance_met = False`


## 已生成图表

### 2025 日维度图

- 两版本对比：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/round36_two_version_daily_curve_comparison.svg`
- 稳健版：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily_curve.svg`
- 进攻版：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily_curve.svg`
- 日盈亏叠加图：
  - `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1007_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily_pnl_overlay.svg`
  - `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1037_bankroll_1000_stake_10_m5_2025-01-01_2025-12-31_daily_pnl_overlay.svg`

### 2025 + 2026 连续图

- 两版本连续对比图：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/round36_two_version_continuous_2025-01-01_2026-04-12_curve_comparison.svg`
- 稳健版连续图：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1007_continuous_2025-01-01_2026-04-12_curve.svg`
- 进攻版连续图：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/three_play_intraday_1037_continuous_2025-01-01_2026-04-12_curve.svg`


## 已修复事项

早前存在一个输出命名问题：

- 旧文件名 `..._2025_daily.csv` 曾被 `2026-01-01 -> 2026-04-12` 的重跑结果覆盖

现状：

- 主回放脚本已修正为输出带真实区间日期后缀的文件名
- 2025 年两版日表已重新补跑，正确文件名带 `2025-01-01_2025-12-31`

后续读取时，优先用新命名文件，不要再依赖旧的 `..._2025_daily.csv`


## 当前推荐口径

如果其它线程要继续往下做，默认建议：

- 主策略口径：`intraday_1007`
- 全量联合区间：`2025-01-06 -> 2026-04-12`
- 主结果：总利润 `22545.27`

如果需要更激进的对照：

- 可同时引用 `intraday_1037`
- 但必须明确标注：`acceptance_met = False`


## 可直接复用的命令

稳健版全量公共区间：

```bash
/tmp/lottery-codex-venv/bin/python /Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_three_play_2025_replay.py \
  --sim-start 2025-01-06 \
  --sim-end 2026-04-12 \
  --start-bankroll 1000 \
  --base-stake 10 \
  --max-multiplier 5 \
  --sum-candidate-id intraday_1007
```

进攻版全量公共区间：

```bash
/tmp/lottery-codex-venv/bin/python /Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_three_play_2025_replay.py \
  --sim-start 2025-01-06 \
  --sim-end 2026-04-12 \
  --start-bankroll 1000 \
  --base-stake 10 \
  --max-multiplier 5 \
  --sum-candidate-id intraday_1037
```

重新画图：

```bash
python3 /Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/render_round36_curves.py
```


## 2026-04-06 到 2026-04-12 四玩法整合

本轮在既有 `大小 + 单双 + 和值` 基础上，追加了 `定位胆` 日维窗口线，形成四玩法联合回放。

### 定位胆固定主候选

来源：

- `/Users/binlonglai/Desktop/code/lottery-code/python/tmp_number_validation/pk10_number_daily_window_validation.py`

冻结口径：

- `exactdw_001`
- `base_gate_id = late|big|center|same_top1_prev=all`
- `obs_window = 192`
- `execution_rule = front_singleton_exact_q75_only`
- `net_win = 8.9`
- 候选选择已用 `<= 2026-04-12` 数据做过去未来核对，主候选未变化

### 四玩法脚本

- 新脚本：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_four_play_interval_replay.py`

说明：

- 数据源使用 `pks_history`
- 查询区间默认 `2024-01-01 -> 2026-04-12`
- `大小` 独立马丁 `1/2/4/5`
- `单双` 固定 1x
- `和值` 独立马丁 `1/2/4/5`
- `定位胆` 独立马丁 `1/2/4/5`
- 四条线共用一条总资金曲线

### 四玩法区间结果

区间：

- `2026-04-06 -> 2026-04-12`

稳健版 `intraday_1007 + exactdw_001`

- 期末资金：`1149.83785`
- 净利润：`149.83785`
- 最大回撤：`-67.90345`
- 分项：`大小 21.3264`、`单双 -5.48855`、`和值 244.5`、`定位胆 -110.5`

进攻版 `intraday_1037 + exactdw_001`

- 期末资金：`1190.33785`
- 净利润：`190.33785`
- 最大回撤：`-218.24735`
- 分项：`大小 21.3264`、`单双 -5.48855`、`和值 285.0`、`定位胆 -110.5`

### 四玩法输出文件

- 两版本对比图：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/round36_four_play_two_version_pks_history_2026-04-06_2026-04-12_curve_comparison.svg`
- 稳健版日表：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/four_play_intraday_1007_exactdw_001_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_daily.csv`
- 稳健版汇总：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/four_play_intraday_1007_exactdw_001_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_summary.csv`
- 稳健版曲线：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/four_play_intraday_1007_exactdw_001_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_curve.svg`
- 进攻版日表：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/four_play_intraday_1037_exactdw_001_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_daily.csv`
- 进攻版汇总：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/four_play_intraday_1037_exactdw_001_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_summary.csv`
- 进攻版曲线：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/four_play_intraday_1037_exactdw_001_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_curve.svg`


## 2026-04-06 到 2026-04-12 对齐版整合更正

上面“四玩法整合”一节里的 `exactdw_001` 结果，后续已确认 **不是最终对齐口径**，原因有两点：

- `双面` 接的是旧 `round30/21` 线，不是已确认部署版 `round35`
- `定位胆` 接的是自动筛出的 `exactdw_001`，不是其它线程已冻结主规则

本线程后续已改为按其它线程对齐后的正式口径重算：

- `双面`：
  `core40_spread_only__exp0_off__oe40_spread_only__cd2`
- `冠亚和`：
  `intraday_1037`
- `定位胆`：
  `late|big|edge_low|same_top1_prev=all`
  `obs=192`
  `front_pair_major_consensus_only`
- 三条线都按独立 `1x -> 2x -> 4x -> 5x` 马丁推进
- 三条线共用一条总资金曲线

### 对齐版结果

区间：

- `2026-04-06 -> 2026-04-12`
- `本金 1000`
- `基投 10`
- `马丁上限 5`
- 数据源：`xyft_lottery_data.pks_history`

结果：

- 期末资金：`1769.6425`
- 净利润：`769.6425`
- ROI：`76.96425%`
- 峰值资金：`1924.7675`
- 最低资金：`1257.3675`
- 最大回撤：`-155.125`

分项：

- `双面`：`+230.6425`
- `冠亚和`：`+285.0`
- `定位胆`：`+254.0`

倍数分布：

- `双面`：`1x=3天, 2x=1天`
- `冠亚和`：`1x=3天, 2x=2天, 4x=1天, 5x=1天`
- `定位胆`：`1x=4天, 2x=1天, 4x=1天, 5x=1天`

### 对齐版脚本与输出

- 脚本：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_aligned_shared_bankroll_replay.py`
- 汇总：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/aligned_face_core40_spread_only__exp0_off__oe40_spread_only__cd2__sum_intraday_1037__exact_exactdw_frozen_edge_low_consensus_obs192_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_summary.csv`
- 日表：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/aligned_face_core40_spread_only__exp0_off__oe40_spread_only__cd2__sum_intraday_1037__exact_exactdw_frozen_edge_low_consensus_obs192_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_daily.csv`
- 曲线：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/aligned_face_core40_spread_only__exp0_off__oe40_spread_only__cd2__sum_intraday_1037__exact_exactdw_frozen_edge_low_consensus_obs192_bankroll_1000_stake_10_m5_pks_history_2026-04-06_2026-04-12_curve.svg`


## 2025-01-01 到 2026-01-01 黑名单时段回放

当前对齐版脚本已扩展支持**时段禁投**：

- 黑名单时段：每天 `06:00:00 -> 07:00:00`
- 口径：该时段**不下注**，但不改变 `冠亚和 / 定位胆` 的日内观察窗口定义
- `双面` 不是简单读旧日表，而是回到 `pks_history` 期级别重建日收益，再重新跑 `round35` 部署策略

脚本：

- `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/pk10_round36_aligned_shared_bankroll_replay.py`

区间：

- `2025-01-01 -> 2026-01-01`
- `本金 1000`
- `基投 10`
- `马丁上限 5`

黑名单版结果：

- 期末资金：`12587.105`
- 净利润：`11587.105`
- ROI：`1158.7105%`
- 峰值资金：`13299.3425`
- 最低资金：`46.5`
- 最大回撤：`-2532.5`

黑名单版分项：

- `双面`：`+3735.605`
- `冠亚和`：`+7138.0`
- `定位胆`：`+713.5`

黑名单版输出：

- 汇总：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/aligned_face_core40_spread_only__exp0_off__oe40_spread_only__cd2__sum_intraday_1037__exact_exactdw_frozen_edge_low_consensus_obs192_bankroll_1000_stake_10_m5_blackout_060000_070000_pks_history_2025-01-01_2026-01-01_summary.csv`
- 日表：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/aligned_face_core40_spread_only__exp0_off__oe40_spread_only__cd2__sum_intraday_1037__exact_exactdw_frozen_edge_low_consensus_obs192_bankroll_1000_stake_10_m5_blackout_060000_070000_pks_history_2025-01-01_2026-01-01_daily.csv`
- 曲线：
  `/Users/binlonglai/Desktop/code/lottery-code/python/pk10_round36_three_play_2025_replay/round36_outputs/aligned_face_core40_spread_only__exp0_off__oe40_spread_only__cd2__sum_intraday_1037__exact_exactdw_frozen_edge_low_consensus_obs192_bankroll_1000_stake_10_m5_blackout_060000_070000_pks_history_2025-01-01_2026-01-01_curve.svg`

补充对照：

- 同区间**不加黑名单**时，期末资金是 `7753.4725`
- 所以 `06:00-07:00` 禁投后，期末资金提升了 `+4833.6325`
```
