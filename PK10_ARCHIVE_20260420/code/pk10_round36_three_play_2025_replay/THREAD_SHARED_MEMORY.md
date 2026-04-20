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
