# V1 Volume Threshold Robustness Analysis

本文件記錄 V1 Condition Contribution Research Batch 3：成交量門檻穩健性分析。

## Research Purpose

Batch 3 只回答一個 historical robustness question：

成交量門檻從正式 V1 的 `volume_ratio_20 >= 1.20` 降至 `1.10` 或 `1.00` 時，Batch 2 看到的樣本增加與 Historical Hit Rate 表現，是否在不同股票、不同年份，以及降低 daily overlap influence 後仍然存在。

這不是 threshold optimization、parameter tuning decision、V1.1 design、trading recommendation、future probability estimation 或 AI prediction。

## Candidate Thresholds

Batch 3 固定只研究：

- `1.00`
- `1.10`
- `1.20`

其中 `1.20` 是 formal V1 reference baseline。`1.00` 與 `1.10` 只是 research candidates，不是正式門檻。

Batch 3 不測 `0.80`、`1.30`、`1.50`，也不建立新的 threshold grid。Batch 2 已完成 broader sensitivity；Batch 3 是 robustness confirmation。

## Data Contract

Batch 3 使用與 Batch 1 / Batch 2 完全一致的 data semantics：

- Symbols：`2330.TW`、`0050.TW`、`2337.TW`、`2404.TW`、`2454.TW`
- Observation window：`2018-01-01` through `2025-12-31` inclusive
- Warm-up：60 trading bars before observation window
- Outcome horizon：20 trading bars after observation date
- Outcome reference：observation-date snapshot `prior_high_60d`
- Historical Hit Rate denominator：`HIT / (HIT + MISS)`
- `INCOMPLETE` 與 `NOT_EVALUABLE` 保留 counts，但不進 denominator

## Architecture

Batch 3 新增 `src/volume_threshold_robustness_service.py`。

Service flow：

```text
prepared historical series
        ↓
Batch 1 diagnostics
        ↓
Batch 2 attached outcomes
        ↓
Volume Threshold Sensitivity
        ↓
Volume Threshold Robustness Analysis
```

Robustness service 直接 consume Batch 2 `HistoricalConditionOutcomeComparisonResult` with attached `ConditionOutcomeObservation` records。

它不重新抓 Yahoo、不 reload SQLite、不重建 technical series、不重新跑 Batch 1 diagnostics、不重新執行 `evaluate_historical_outcome()`，也不修改 V1 signal definition、technical formula、outcome semantics、scanner、backtest、Historical Replay、Walk-Forward、OOS、database schema 或 OpenAI / AI logic。

## Per-Symbol Robustness

Per-symbol summary 對每個 symbol 與 threshold 保存：

- observation count
- HIT
- MISS
- INCOMPLETE
- NOT_EVALUABLE
- resolved count
- Historical Hit Rate
- Historical Hit Rate delta vs `1.20` in percentage points
- observation count delta vs `1.20`
- observation count change rate vs `1.20`

Aggregate Historical Hit Rate 使用 raw counts 加總後的 `sum(HIT) / sum(HIT + MISS)`，不是 average per-symbol hit rates。

Per-symbol output 只保存 factual comparison，不建立 winner、best threshold、rank、score 或 recommendation。

## Per-Year Robustness

Per-year summary 以 observation trading date calendar year 分組，年份固定為 `2018` through `2025`。

Year 是 observation date year。Future 20-bar outcome 可以延伸到下一年度，但 observation 仍屬於原本 observation year。

小樣本必須保留 resolved sample count。`100% / n=2` 只能視為 small-sample historical observation，不能描述成最穩、最好或最有效。

## Overlap-Reduced Methodology

Batch 3 保留原始 daily result，另外建立降低樣本重疊的 observation subset。

Deterministic spacing rule：

1. 對每個 `symbol + threshold`，依 trading date ascending 排序 qualified observations。
2. 選第一個 qualified observation。
3. 後續 qualified observation 必須距離上一個已選 observation 至少 20 個 trading-bar indices，才可以再次選入。
4. Spacing 使用同一 symbol 的 daily outcome observation trading-bar index，不使用 calendar-day distance。

Selected observation identity 固定為：

- symbol
- trading_date
- signal_definition_id

同樣 input 必須產生相同 selected IDs。沒有 random sampling、bootstrap 或 shuffle。

## Overlap Interpretation

本文件使用「降低樣本重疊」，不是「完全獨立樣本」。

20 trading-bar spacing 只降低同一 symbol 連續 observation 的 future-window overlap。它不能證明 statistical independence，也不能把 selected samples 解讀成獨立交易樣本。

Daily observations are not trades。Historical Hit Rate 是 descriptive historical evidence，不是 future probability、prediction accuracy、buy signal、sell signal 或 investment recommendation。

## Live Read-Only Validation

Live validation 使用 `data/stocks.db` 的 SQLite URI `mode=ro` 讀取 `historical_prices`，不初始化、不 migrate、不寫 DB、不 Yahoo refetch、不 network fallback。

DB audit：

- Size：`7,327,744` bytes
- mtime epoch：`1786251269`
- SHA-256：`dcd65c9f2e579164728eaadbbc7b6926f3d6513bcdcac2cb36154bc8961f9aa5`
- `PRAGMA integrity_check`：`ok`

Before and after validation metadata matched exactly.

## Aggregate Daily Results

| Threshold | n | HIT | MISS | INCOMPLETE | NOT_EVALUABLE | Resolved | Historical Hit Rate | Delta vs 1.20 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 114 | 105 | 9 | 0 | 0 | 114 | 92.11% | +1.69 pp |
| 1.10 | 96 | 88 | 8 | 0 | 0 | 96 | 91.67% | +1.26 pp |
| 1.20 | 73 | 66 | 7 | 0 | 0 | 73 | 90.41% | 0.00 pp |

Daily baseline invariant PASS：Batch 3 reproduced the required Batch 2 baseline counts for `1.00`、`1.10`、`1.20`。

## Per-Symbol Live Results

| Symbol | Threshold | n | HIT | MISS | Resolved | Historical Hit Rate | Delta vs 1.20 | n Delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2330.TW | 1.00 | 55 | 53 | 2 | 55 | 96.36% | +0.07 pp | +28 |
| 2330.TW | 1.10 | 41 | 40 | 1 | 41 | 97.56% | +1.26 pp | +14 |
| 2330.TW | 1.20 | 27 | 26 | 1 | 27 | 96.30% | 0.00 pp | 0 |
| 0050.TW | 1.00 | 34 | 32 | 2 | 34 | 94.12% | -1.53 pp | +11 |
| 0050.TW | 1.10 | 30 | 28 | 2 | 30 | 93.33% | -2.32 pp | +7 |
| 0050.TW | 1.20 | 23 | 22 | 1 | 23 | 95.65% | 0.00 pp | 0 |
| 2337.TW | 1.00 | 17 | 12 | 5 | 17 | 70.59% | +1.84 pp | +1 |
| 2337.TW | 1.10 | 17 | 12 | 5 | 17 | 70.59% | +1.84 pp | +1 |
| 2337.TW | 1.20 | 16 | 11 | 5 | 16 | 68.75% | 0.00 pp | 0 |
| 2404.TW | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2404.TW | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2404.TW | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2454.TW | 1.00 | 8 | 8 | 0 | 8 | 100.00% | 0.00 pp | +1 |
| 2454.TW | 1.10 | 8 | 8 | 0 | 8 | 100.00% | 0.00 pp | +1 |
| 2454.TW | 1.20 | 7 | 7 | 0 | 7 | 100.00% | 0.00 pp | 0 |

## Per-Year Live Results

| Year | Threshold | n | HIT | MISS | Resolved | Historical Hit Rate | Delta vs 1.20 | n Delta |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2018 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2018 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2019 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2019 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2019 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2020 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2020 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2020 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2021 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2021 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2021 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2022 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2022 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2022 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 2023 | 1.00 | 7 | 6 | 1 | 7 | 85.71% | +5.71 pp | +2 |
| 2023 | 1.10 | 6 | 5 | 1 | 6 | 83.33% | +3.33 pp | +1 |
| 2023 | 1.20 | 5 | 4 | 1 | 5 | 80.00% | 0.00 pp | 0 |
| 2024 | 1.00 | 28 | 27 | 1 | 28 | 96.43% | +1.43 pp | +8 |
| 2024 | 1.10 | 24 | 23 | 1 | 24 | 95.83% | +0.83 pp | +4 |
| 2024 | 1.20 | 20 | 19 | 1 | 20 | 95.00% | 0.00 pp | 0 |
| 2025 | 1.00 | 79 | 72 | 7 | 79 | 91.14% | +1.56 pp | +31 |
| 2025 | 1.10 | 66 | 60 | 6 | 66 | 90.91% | +1.33 pp | +18 |
| 2025 | 1.20 | 48 | 43 | 5 | 48 | 89.58% | 0.00 pp | 0 |

## Overlap-Reduced Live Results

| Threshold | Daily n | Reduced n | Daily HIT | Daily MISS | Daily Resolved | Daily HHR | Reduced HIT | Reduced MISS | Reduced Resolved | Reduced HHR | Delta vs 1.20 | Spacing |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1.00 | 114 | 36 | 105 | 9 | 114 | 92.11% | 32 | 4 | 36 | 88.89% | +4.51 pp | PASS |
| 1.10 | 96 | 35 | 88 | 8 | 96 | 91.67% | 31 | 4 | 35 | 88.57% | +4.20 pp | PASS |
| 1.20 | 73 | 32 | 66 | 7 | 73 | 90.41% | 27 | 5 | 32 | 84.38% | 0.00 pp | PASS |

Selected-ID spacing invariant PASS。

## Factual Robustness Notes

In aggregate daily results, both `1.00` and `1.10` had higher historical hit rates than `1.20` while increasing sample counts.

Per-symbol, `1.00` had a higher historical rate than `1.20` for 2 symbols, lower for 1 symbol, equal for 1 symbol, and unavailable for 1 symbol with zero resolved samples.

Per-year, years with resolved samples were `2023`、`2024`、`2025`; `1.00` was higher than `1.20` in 3 / 3 resolved years, and `1.10` was higher than `1.20` in 3 / 3 resolved years.

After reducing same-symbol daily overlap with 20 trading-bar spacing, `1.00` historical hit rate was `88.89%` and `1.20` was `84.38%`; `1.10` was `88.57%` and `1.20` was `84.38%`.

These are factual historical observations only. They do not imply that `1.00` or `1.10` should replace `1.20`, and they do not identify a best threshold.
