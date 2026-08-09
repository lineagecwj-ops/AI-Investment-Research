# V1 Historical Condition Outcome Comparison

## Purpose

V1 Historical Condition Outcome Comparison is a deterministic Batch 2 research layer.

It connects Batch 1 daily historical condition observations to the existing historical outcome framework and compares descriptive outcomes by:

- `0/5` through `5/5` matched-condition count
- the single missing condition among `4/5` observations
- passed-condition combinations for future extension

It does not modify V1, tune thresholds, rank stocks, recommend trades, estimate future probability, or call AI.

## Observation Unit

The primary unit is a daily diagnostic observation:

```text
symbol + trading_date + signal_definition_id
```

It is not an independent signal event, trade, entry, position, or backtest case.

If the same symbol has three consecutive `4/5` trading dates, Batch 2 evaluates three daily observations. Their future 20-trading-bar windows may overlap, so the result keeps `observation_unit = DAILY` and `overlap_possible = True`.

## Batch 1 To Batch 2 Relationship

Batch 2 does not re-evaluate V1 conditions.

The condition side truth source is Batch 1 `ConditionDiagnosticObservation`, including:

- symbol
- trading date
- signal definition id
- matched condition count
- passed condition ids
- missing condition ids
- source technical snapshot

For the same symbols, signal definition, observation window, and technical data snapshot, Batch 2 source bucket counts must equal Batch 1 evaluated match-count distribution.

## Warm-Up Semantics

Batch 2 fixes diagnostic research-window semantics with deterministic pre-window warm-up:

```text
warmup_trading_bars = 60
```

The comparison helper keeps:

- the last 60 trading bars before `observation_start`
- all bars from `observation_start` through `observation_end`
- the first `outcome_definition.horizon_bars` bars after `observation_end`

Warm-up bars are used only to build technical features. They do not create Batch 1 observations, do not enter denominators, and do not become Batch 2 outcome groups.

Extra unrelated earlier history must not change the observation denominator.

## Observation Window

Observation trading dates are inclusive:

```text
config.start_date <= trading_date <= config.end_date
```

Only evaluated Batch 1 observations enter `0/5` through `5/5` outcome buckets. Batch 1 `NOT_EVALUABLE` observations remain diagnostic traceability and do not enter match-count outcome buckets.

## Post-Window Outcome Data

Outcome evaluation may need bars after the observation window.

For `raw_high_breakout_60d_within_20d_v1`, Batch 2 needs up to 20 trading bars after each observation date. The prepared price series keeps at least the first 20 bars after `observation_end` when available.

This post-window data is for outcome labeling only. It must not change condition evaluation.

## Outcome Semantics

Batch 2 reuses the existing:

```text
raw_high_breakout_60d_within_20d_v1
evaluate_historical_outcome()
```

The raw-high breakout reference high is fixed from the observation-date technical snapshot:

```text
prior_high_60d
```

The reference high is not recalculated from the future outcome window.

## Match-Count Outcome Summary

Each `0/5` through `5/5` bucket reports:

- observation count
- HIT
- MISS
- INCOMPLETE
- NOT_EVALUABLE
- resolved count
- Historical Hit Rate

The invariant is:

```text
HIT + MISS + INCOMPLETE + NOT_EVALUABLE = observation_count
```

## 4/5 Missing-Condition Comparison

All `4/5` observations are grouped by their exactly-one missing condition:

- 股價高於 20 日均線
- 20 日均線高於 60 日均線
- 20 日成交量比率
- RSI 14 日相對強弱指標
- 距離前 60 日高點

Each group reports the same outcome count fields and Historical Hit Rate.

## Historical Hit Rate Denominator

Historical Hit Rate is:

```text
HIT / (HIT + MISS)
```

Resolved samples are:

```text
HIT + MISS
```

`INCOMPLETE` and `NOT_EVALUABLE` are displayed but excluded from the denominator.

If resolved samples are zero, Historical Hit Rate is `None` / `N/A`, not `0%`.

Historical Hit Rate must be shown with resolved sample count. It is a descriptive historical statistic, not future probability, success probability, prediction accuracy, confidence, likelihood, expected return, or strategy win rate.

## Per-Symbol And Aggregate Semantics

The result supports aggregate and per-symbol summaries.

Aggregate Historical Hit Rate is computed from summed observation counts:

```text
sum(HIT) / (sum(HIT) + sum(MISS))
```

It is not an average of symbol-level percentages.

## Scope Boundaries

Batch 2 does not:

- change `technical_example_v1`
- change the `-5%` prior-high threshold
- change volume or RSI thresholds
- change scanner decision logic
- change backtest, replay, walk-forward, replay analytics, OOS, database schema, or AI logic
- create V1.1 or V2
- calculate MFE, MAE, End Return as primary summary fields
- produce probability, recommendation, buy list, score, ranking, or parameter tuning

If `4/5` cases missing only the prior-high condition show different historical outcomes, that remains evidence for later review only.
