# PK10 Archive 2026-04-20

这个目录把本轮 `PK10` 项目的核心资料整合在一个文件夹里，方便整体查看、打包或迁移。

## 目录结构

- `docs/`
  - 推理过程、冻结窗口依据、工程源码单文件总档
- `code/`
  - 当前使用中的关键工程代码
- `db_exports/`
  - 相关表结构与最近一周数据导出

## 核心入口

- 总档：
  - `docs/PK10_FULL_CONTEXT_AND_CODE_ARCHIVE_20260420.md`
- live dashboard 工程：
  - `code/pk10_live_dashboard/`
- round36 回放与整合脚本：
  - `code/pk10_round36_three_play_2025_replay/`
- 数据库导出：
  - `db_exports/schema_relevant_tables.sql`
  - `db_exports/recent_week_data_2026-04-14_to_2026-04-20.sql`

## 当前冻结口径

- 窗口预热：`2026-01-01`
- 模拟投注：`2026-04-01`
- 双面：`core40_spread_only__exp0_off__oe40_spread_only__cd2`
- 冠亚和：`intraday_1037`
- 定位胆：`late|big|edge_low|same_top1_prev=all + obs=192 + front_pair_major_consensus_only`
- 资金池：`1000 / 10 / shared bankroll`
- 马丁：
  - `face`: `1-2-4-5`
  - `sum`: `1-2-4-5`
  - `exact`: 固定 `10`
- blackout：每天 `06:00-07:00` 不投注
