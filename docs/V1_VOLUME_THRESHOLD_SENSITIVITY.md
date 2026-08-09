# V1 Volume Threshold Sensitivity Analysis

本文件記錄 V1 Condition Contribution Research Batch 2：成交量門檻變化測試。

## Purpose

成交量門檻變化測試會固定其他四項 V1 條件，只改變成交量比率門檻，比較不同門檻下的歷史樣本數與歷史後續結果。

這是 historical sensitivity analysis。它不是 threshold optimization、parameter tuning for production、best-threshold search、V1.1 proposal、future probability model、recommendation 或 buy signal。

## Current V1 Baseline

正式 V1 signal definition 仍然是 `technical_example_v1`。

目前正式成交量條件為：

```text
volume_ratio_20 >= 1.20
```

`1.20` 是本研究的 comparison baseline。所有 delta 都相對 `1.20` 計算，不使用相鄰 threshold 差。

## Threshold Grid

Primary research grid 固定為：

```text
0.80
1.00
1.10
1.20
1.30
1.50
```

輸出順序固定為 threshold ascending，不依 Historical Hit Rate、樣本數或 delta 排序。

## Fixed Condition Semantics

每個 historical observation 必須先符合其他四項 V1 條件：

- `analysis_close > sma_20`
- `sma_20 > sma_60`
- `rsi_14 between 50 and 70`
- `distance_to_prior_60d_high >= -0.05`

Batch 2 不重新建立這四項條件 semantics，而是直接重用 Batch 1 diagnostic observation 的 PASS / FAIL trace。只有 `volume_ratio_20` actual numeric value 會用 sensitivity threshold 重新判定：

```text
volume_ratio_20 >= threshold
```

因此 `volume_ratio_20 == 1.20` 在 threshold `1.20` 必須 PASS。

## Observation Identity

Sensitivity analysis 使用與 Batch 1 / Batch 2 相同的 historical observation identity：

- `symbol`
- `trading_date`
- `signal_definition_id`

Threshold 變化不能新增或刪除 underlying research universe 的 observation dates。Threshold 只決定該 observation 是否 qualified for sensitivity bucket。

## Warm-Up And Outcome Reuse

Live validation 使用：

- observation window：`2018-01-01` 到 `2025-12-31`
- warm-up：`60` trading bars
- outcome horizon：`20` trading bars
- outcome definition：`raw_high_breakout_60d_within_20d_v1`

Sensitivity layer 直接使用 Batch 2 attached historical outcome，不重新執行 `evaluate_historical_outcome()`，不重新抓 Yahoo，不按 threshold 重建 technical series。

## Aggregation Semantics

每個 threshold 保存：

- observation count
- `HIT`
- `MISS`
- `INCOMPLETE`
- `NOT_EVALUABLE`
- resolved count
- Historical Hit Rate
- deltas vs `1.20`

Historical Hit Rate denominator 固定為：

```text
HIT / (HIT + MISS)
```

`INCOMPLETE` 與 `NOT_EVALUABLE` 不進 denominator。若 resolved count 為 `0`，Historical Hit Rate 為 `None`。

Aggregate 必須 sum raw `HIT` 與 raw `MISS` 後再計算 Historical Hit Rate。禁止平均各 symbol rates。

## Delta Semantics

Sample change rate 使用：

```text
(observation_count(T) - observation_count(1.20)) / observation_count(1.20)
```

若 baseline count 為 `0`，change rate 為 `None`。

Historical Hit Rate delta 使用 percentage points：

```text
historical_hit_rate(T) - historical_hit_rate(1.20)
```

`1.20` row 的 delta 必須為 `0`。

## Daily Observation Limitation

Result metadata 固定保存：

- `observation_unit = DAILY`
- `overlap_possible = True`

Historical Hit Rate 是歷史每日觀察樣本比例，不是 strategy win rate、independent-trade probability、future probability、prediction accuracy 或 investment recommendation。

## Boundary

本 Batch 不修改：

- `technical_example_v1`
- production `volume_ratio_20 >= 1.20`
- scanner
- technical formulas
- outcome definition
- reference high
- backtest
- Historical Replay
- Walk-Forward Replay
- Replay Analytics
- OOS
- database schema / content
- OpenAI / AI logic

本 Batch 不建立 V1.1，不做 RSI sensitivity，不做 distance sensitivity，不接 dashboard。

較低門檻通常會增加樣本，但是否保留足夠篩選效果，需要進一步研究。歷史命中率變高或變低，不代表該門檻是最佳設定。
