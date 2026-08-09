# V1 Historical Condition Diagnostics

## Purpose

V1 Historical Condition Diagnostics is a deterministic Batch 1 foundation for inspecting how often historical technical snapshots satisfy the fixed V1 condition structure.

It answers descriptive condition-structure questions only:

- how many of the five V1 conditions each evaluated historical observation satisfied
- the 0/5 through 5/5 distribution
- each single condition's historical pass rate
- which condition is most often missing among 4/5 observations
- which condition combinations most often appear together

## Batch 1 Scope

Batch 1 builds service models, summaries, Traditional Chinese terminology, tests, and documentation.

It does not add Streamlit dashboard integration, SQLite persistence, AI analysis, prediction, recommendation, or V1.1 / V2 rule work.

## V1 Is Not Modified

Diagnostics reuse the existing `SignalDefinition` and `evaluate_signal_conditions()` path. The fixed `technical_example_v1` conditions remain:

| Primary label | Internal condition |
| --- | --- |
| 股價高於 20 日均線 | `analysis_close > sma_20` |
| 20 日均線高於 60 日均線 | `sma_20 > sma_60` |
| 20 日成交量比率 | `volume_ratio_20 >= 1.20` |
| RSI 14 日相對強弱指標 | `rsi_14 between 50 and 70` |
| 距離前 60 日高點 | `distance_to_prior_60d_high >= -0.05` |

The diagnostics layer does not reimplement these comparisons with parallel `if` statements.

## 0/5 Through 5/5

Each evaluated historical observation records the factual count of matched V1 conditions:

```text
matched_condition_count / total_condition_count
```

This is `符合條件數`, not a score. It is not Buy Score, Opportunity Score, win rate, future probability, recommendation, ranking, or trading instruction.

The match-count distribution reports observation counts and shares for `0/5` through `5/5`. Share denominator is evaluated observations only.

## Single Condition Pass Rate

Each condition summary reports:

- condition id
- Traditional Chinese display name
- passed count
- failed count
- evaluated count
- pass rate

Pass rate is:

```text
passed_count / evaluated_count
```

If `evaluated_count == 0`, pass rate is `None`, not `0%`.

## 4/5 Missing Condition

The 4/5 missing-condition summary only looks at observations that satisfy exactly four of the five V1 conditions.

Each 4/5 observation should have exactly one missing condition. The summary counts which final condition is most often missing.

If there are no 4/5 observations, the summary safely returns an empty missing-condition list and `total_4_of_5_count == 0`.

## Condition Combination

Condition combinations group observations by the set of passed condition ids.

Combination ordering is canonical and deterministic according to the fixed V1 signal-definition condition order, so `A+B+D` and `D+A+B` are treated as the same combination.

Combination share also uses evaluated observations as the denominator.

## NOT_EVALUABLE

Historical diagnostics must not turn insufficient technical history or missing required features into `0/5`.

If `evaluate_signal_conditions()` returns `NOT_EVALUABLE`, the observation is preserved for traceability but excluded from:

- match-count distribution denominator
- condition pass-rate denominator
- 4/5 missing-condition analysis
- condition-combination share denominator

The result reports evaluated observations and not-evaluable observations separately.

## Traditional Chinese UX Terminology

Primary terminology lives in `src/ui_terminology.py`:

| Internal phrase | Primary label |
| --- | --- |
| Historical Condition Diagnostics | V1 歷史條件診斷 |
| Match Count Distribution | 歷史條件命中分布 |
| Matched Conditions | 符合條件數 |
| Condition Pass Rate | 單一條件通過率 |
| Missing Condition | 未符合條件 |
| Most Common Missing Condition | 最常缺少的條件 |
| Condition Combination | 條件組合 |
| Evaluated Observations | 可評估歷史樣本 |
| Not Evaluable | 無法評估 |
| Observation Count | 歷史樣本數 |
| Share | 占可評估樣本比例 |

Primary labels do not expose raw metric ids such as `analysis_close`, `sma_20`, or `distance_to_prior_60d_high`.

## No Historical Outcome In Batch 1

Batch 1 does not compute:

- HIT
- MISS
- Historical Hit Rate
- MFE
- MAE
- End Return
- future breakout
- future probability

Batch 2 may connect condition diagnostics to historical outcomes. That future work must remain separate from this Batch 1 foundation.

## Run-Local Result

The result is in-memory and run-local. Batch 1 does not add SQLite tables or database schema changes.

When caller supplies `TechnicalIndicatorSeries` objects, the diagnostics service does not fetch Yahoo data. When the service loads symbols itself, it builds each symbol's `TechnicalIndicatorSeries` once and evaluates each historical snapshot within the inclusive date range.
