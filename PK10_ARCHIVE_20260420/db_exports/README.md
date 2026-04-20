# DB Exports

本目录收录本轮 `PK10` 项目的数据库导出，分为两部分：

- `schema_relevant_tables.sql`
  - 只包含相关表结构，不包含数据。
- `recent_week_data_2026-04-14_to_2026-04-20.sql`
  - 包含最近一周的数据导出。

## 表范围

- `pks_history`
- `pk10_runtime_state`
- `pk10_broadcast_log`
- `pk10_bet_log`
- `pk10_daily_equity`

## 数据时间范围

本次“最近一周”按 `2026-04-14 -> 2026-04-20` 导出。

说明：

- `pks_history`
  - 按 `draw_date` 过滤到 `2026-04-14 -> 2026-04-20`
  - 其中 `2026-04-20` 为当日实时库快照，可能是未完结自然日
- `pk10_broadcast_log`
  - 按 `draw_date` 过滤到 `2026-04-14 -> 2026-04-20`
- `pk10_bet_log`
  - 按 `draw_date` 过滤到 `2026-04-14 -> 2026-04-20`
- `pk10_daily_equity`
  - 按 `draw_date` 过滤到 `2026-04-14 -> 2026-04-20`
  - 当前表里实际存在的是截至导出时已落库的日记录
- `pk10_runtime_state`
  - 该表没有 `draw_date`
  - 因此导出的是导出时刻的当前状态快照

## 导出来源

- 数据库：`xyft_lottery_data`
- 宿主：`ssh tengxun`
- MySQL：Docker 容器 `xyft-mysql`
