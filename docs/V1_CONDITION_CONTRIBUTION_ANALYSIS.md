# V1 Condition Contribution Analysis

## Purpose

V1 Condition Contribution Analysis 是 deterministic historical diagnostics layer。

Primary 中文名稱是：

```text
單一條件影響分析
```

Advanced metadata 可使用英文研究術語：

```text
Leave-One-Out Condition Analysis
```

本分析回答：

```text
如果固定其他 V1 條件，只假設某一個 V1 條件不再作為必要條件，
歷史每日觀察樣本數與後續 HIT / MISS 結果如何改變？
```

這是 historical evidence / diagnostics。它不是 parameter tuning、threshold optimization、strategy optimization、prediction、future probability、recommendation、buy signal 或 V1.1 proposal。

## Source Layers

此 layer 直接使用 Batch 2 `HistoricalConditionOutcomeComparisonResult`。

Condition side 來自 Batch 1：

- `ConditionDiagnosticObservation`
- symbol
- trading date
- signal definition id
- matched condition count
- passed condition ids
- missing condition ids
- source technical snapshot

Outcome side 來自 Batch 2：

- `ConditionOutcomeObservation`
- attached `HistoricalOutcomeResult`
- existing `evaluate_historical_outcome()` semantics

單一條件影響分析本身只做 filter、group、aggregate。它不重新抓 Yahoo、不重建 technical series、不重新 evaluate V1 conditions、不重新 evaluate outcomes。

## Observation Semantics

Observation unit 是 daily diagnostic observation：

```text
symbol + trading_date + signal_definition_id
```

它不是 signal event、trade、entry、position、backtest trade 或 independent experiment。

Consecutive daily observations may share overlapping future 20-trading-bar windows, so result metadata preserves:

```text
observation_unit = DAILY
overlap_possible = True
```

這代表每日觀察樣本不能解讀成相同數量的獨立交易。

## Warm-Up Contract

此 layer 不定義新的 date-extension algorithm。

Live research preparation must continue to use Batch 2 deterministic helper:

```text
prepare_diagnostic_research_series()
```

Current deterministic contract:

```text
observation window = 2018-01-01 through 2025-12-31 inclusive
warmup_trading_bars = 60
outcome_horizon_bars = 20
```

Warm-up bars are used only for technical indicator calculation. They do not create diagnostic observations, do not enter distribution denominators, and do not enter leave-one-out sample denominators.

Post-window bars are used only for historical outcome evaluation. They do not create observations outside the observation window.

## Leave-One-Out Definition

For each canonical V1 condition, the leave-one-out qualified set is:

```text
original 5/5 baseline observations
+
4/5 observations where the only missing condition is the target condition
```

Example:

```text
Assume volume condition is not required
=
price > SMA20 PASS
SMA20 > SMA60 PASS
RSI condition PASS
distance-to-high condition PASS
volume condition not used as qualification requirement
```

This is not a new production signal. It is a historical counterfactual diagnostic grouping.

The implementation enforces uniqueness by:

```text
symbol + trading_date + signal_definition_id
```

Within a leave-one-out group, the same daily observation cannot be counted twice.

## Baseline

Baseline is the original complete V1 `5/5` group from Batch 2 outcome-attached observations.

For every condition comparison, baseline fields are copied from the same baseline summary:

- observation count
- HIT
- MISS
- INCOMPLETE
- NOT_EVALUABLE
- resolved count
- Historical Hit Rate

## Historical Hit Rate

Historical Hit Rate is:

```text
HIT / (HIT + MISS)
```

Resolved samples are:

```text
HIT + MISS
```

`INCOMPLETE` and `NOT_EVALUABLE` are preserved as counts, but excluded from the denominator.

If resolved samples are zero, Historical Hit Rate is `None` / `N/A`, not `0%`。

Historical Hit Rate change is expressed in percentage points:

```text
leave_one_out_historical_hit_rate - baseline_historical_hit_rate
```

multiplied by `100`。

It is not relative percentage change.

## Aggregate Semantics

Aggregate counts are raw summed observations and statuses.

Aggregate Historical Hit Rate is:

```text
sum(HIT) / (sum(HIT) + sum(MISS))
```

It is not the average of per-symbol Historical Hit Rates.

## Per-Symbol Support

The result preserves per-symbol comparison rows in the same canonical condition order.

This allows later robustness research to inspect whether a result is dominated by one symbol. This Batch does not start robustness analysis.

## Canonical Condition Order

All output rows preserve canonical V1 condition order:

1. 股價高於 20 日均線
2. 20 日均線高於 60 日均線
3. 20 日成交量比率
4. RSI 14 日相對強弱指標
5. 距離前 60 日高點

Rows are not sorted by Historical Hit Rate, sample count, delta, or any best / worst concept.

## Interpretation Limits

歷史命中率是歷史樣本的描述性統計，不是未來發生機率，也不是買進建議。

單一條件影響分析是在固定其他 V1 條件下，觀察取消某一條件要求後，歷史樣本數與歷史結果如何變化。

較高的歷史命中率不代表該條件應被移除。

較低的歷史命中率也不代表該條件一定有效。

目前 daily observations 可能具有重疊的未來觀察區間，不能解讀成相同數量的獨立交易。

## Explicit Boundaries

This Batch does not:

- change `technical_example_v1`
- change V1 thresholds
- change `evaluate_signal_conditions()`
- change technical formulas
- change scanner logic
- change outcome definition
- change `evaluate_historical_outcome()`
- change reference-high semantics
- change the 20-trading-bar horizon
- change backtest, Historical Replay, Walk-Forward Replay, Replay Analytics, OOS, database schema, database content, or AI logic
- create V1.1 or V2
- run threshold sensitivity
- create dashboard UI
- produce probability, recommendation, ranking, score, best condition, optimal threshold, buy signal, or AI analysis
