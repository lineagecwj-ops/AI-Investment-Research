# Signal & Outcome Framework

## Purpose

Sprint 06 Batch C establishes the deterministic boundary between signal definitions and historical outcome labels.

This layer does not calculate Historical Hit Rate, probability, confidence, rankings, scanner output, dashboard views, AI predictions, Buy / Sell / Hold recommendations, or target-price recommendations.

## Signal vs Outcome

Signal evaluation uses only a `TechnicalIndicatorSnapshot` for the signal date. It can inspect only features that were available as of that trading date.

Historical outcome evaluation may inspect future price bars, but only to assign a historical label to an already-frozen `SignalEvent`. Future bars must not modify the signal event or its feature snapshot.

Architecture flow:

```text
TechnicalIndicatorSeries
        ↓
Signal Evaluation
        ↓
SignalEvent
        ↓
Historical Outcome Evaluation
        ↓
HistoricalOutcomeResult
        ↓
future Backtest Aggregation
        ↓
Historical Hit Rate
```

## No-Look-Ahead Boundary

`evaluate_signal_conditions(snapshot, signal_definition)` is pure and deterministic. It does not use AI, network, SQLite, scanner state, future price bars, or outcome labels.

`evaluate_historical_outcome(signal_event, price_series, outcome_definition)` uses only bars with:

```text
bar.trading_date > signal_event.signal_date
```

The signal date bar is Day 0 and is excluded from future outcome windows.

## SignalDefinition

`SignalDefinition` is a stable, versioned collection of deterministic conditions:

- `id`
- `name`
- `conditions`
- `minimum_required_features`
- `description`

It must not contain probability, score, confidence, recommendation, target price, or Historical Hit Rate fields.

If any `minimum_required_features` value is missing or non-finite, the whole signal evaluation is `NOT_EVALUABLE`, even when all explicit conditions are individually matched.

Signal IDs must be stable and versioned, such as `technical_example_v1`. If a future version changes the condition semantics, it should use a new ID, such as `technical_example_v2`.

## Condition Evaluation

`TechnicalSignalCondition` supports:

- `>`
- `>=`
- `<`
- `<=`
- `==`
- `between`

Conditions support metric-to-constant comparison and metric-to-metric comparison through `secondary_metric`, for example:

```text
sma_20 > sma_60
```

There is no `eval()` and no arbitrary Python expression parsing.

`between` is inclusive:

```text
lower <= value <= upper
```

Boolean values are supported only for equality. Booleans are not treated as numeric values for ordered comparisons.

## MATCH / NO_MATCH / NOT_EVALUABLE

Signal evaluation status is:

- `MATCH`: all conditions are evaluable and matched.
- `NO_MATCH`: all required data is present, but at least one condition failed.
- `NOT_EVALUABLE`: at least one required metric, comparison metric, or condition value is missing or non-finite.

Missing data is not treated as `False`.

Each `EvaluatedSignalCondition` preserves traceability:

- metric
- actual value
- operator
- expected value or secondary metric value
- condition status
- matched result

## SignalEvent

Only a `MATCH` can become a `SignalEvent`.

`SignalEvent` freezes:

- `symbol`
- `signal_id`
- `signal_date`
- `signal_analysis_close`
- `signal_raw_close`
- `reference_high`
- `reference_low`
- `evaluation_status`
- `feature_snapshot`
- `evaluated_conditions`

The default reference fields are `prior_high_60d` and `prior_low_60d` from the signal-date snapshot.

## OutcomeDefinition

`OutcomeDefinition` is also stable and versioned. Batch C supports:

- `RAW_HIGH_BREAKOUT`
- `CLOSE_RETURN_TARGET`

Supported horizons are 5, 10, 20, and 40 trading bars. The MVP default is 20 trading bars.

Example IDs:

- `raw_high_breakout_60d_within_20d_v1`
- `close_return_5pct_within_20d_v1`

## Trading-Bar Horizon

Outcome windows use actual future trading bars, not calendar days:

```text
future bars = next 1 ... N trading bars after signal date
```

A Friday signal's first future bar is the next trading session, not Saturday.

For a 20-bar horizon, the evaluator inspects at most the first 20 future trading bars. A target hit on bar 21 is not counted for a 20-bar outcome.

## Frozen Reference Level

`RAW_HIGH_BREAKOUT` uses the reference high frozen in `SignalEvent`, usually the signal-date `prior_high_60d`.

The reference is not recalculated with future bars, and it is not a full-sample high.

## Raw-High Breakout Semantics

Batch C core new-high outcome is:

```text
future raw high > frozen raw prior high
```

The comparison is strict `>`. Equal high is not a breakout.

Only the first target hit date and bar index are saved.

## Return Target Semantics

`CLOSE_RETURN_TARGET` uses analysis-close basis:

```text
future analysis_close / signal_analysis_close - 1 >= target_return
```

Return target uses `>=` because the threshold is a return target, not a breakout level.

## Basis Separation

Raw-high breakout stays on raw high / raw prior high basis.

Close return stays on analysis-close / signal analysis-close basis, where analysis close is:

```text
adjusted_close if available else close
```

Batch C intentionally does not mix raw prior high with analysis close into a single close-breakout boolean. A future close-breakout outcome should first define an analysis-price prior-high reference.

## HIT / MISS / INCOMPLETE

Historical outcome status is:

- `HIT`: a target was observed inside the available future bars.
- `MISS`: the full horizon is available and no target was hit.
- `INCOMPLETE`: no target has been hit yet, and fewer than `horizon_bars` future bars are available.
- `NOT_EVALUABLE`: required outcome reference or basis data is missing.

Future Historical Hit Rate denominators should use only `HIT + MISS` and exclude `INCOMPLETE` and `NOT_EVALUABLE`. Batch C documents this rule but does not compute hit rate.

## Early-Hit Semantics

If a target is hit on future bar 5 but only 10 future bars are currently available for a 20-bar outcome, the result is already `HIT`.

If no target is hit and only 10 future bars are available, the result is `INCOMPLETE`.

## MFE / MAE

`max_close_return` and `max_adverse_return` are close-based observed return metrics over the full outcome window.

They are populated only when the full horizon is available. For early hits with an incomplete window, hit metadata is saved, but MFE / MAE and end-of-window return remain `None`.

Tie behavior is deterministic: Python's first max / min keeps the earliest date.

These fields are not called profit, loss, or portfolio drawdown.

## End-Of-Window Return

`end_of_window_return` is the analysis-close return on the Nth future trading bar.

It is populated only when exactly enough future bars exist for the requested horizon.

## Missing Reference Behavior

If a raw-high breakout outcome requires `reference_high` but the signal event does not have it, the result is `NOT_EVALUABLE`.

The evaluator does not guess, recalculate from the full sample, or treat the missing reference as a miss.

## Overlapping Signals

Raw event extraction uses `ALLOW_ALL` semantics. Every matched event can be preserved as raw event history.

Cooldown is a deterministic post-processing helper for analysis views. It must not permanently delete raw events.

## Cooldown

`apply_signal_cooldown(events, trading_calendar, cooldown_bars=N)` keeps the first event for the same `symbol + signal_id` and drops later events within the next `N` trading bars.

The helper requires a trading calendar from price bars, technical snapshots, or an explicit date sequence. It does not use calendar-day arithmetic.

## Incomplete Latest Samples

Historical outcomes near the latest available data often have fewer than the requested future bars. Those cases are `INCOMPLETE` unless the target has already been observed.

The latest Yahoo daily bar can still be a provisional current-session bar. Historical backtest use should prefer completed-session data policies.

## No Hit Rate In Batch C

Batch C does not calculate:

- success count
- failure count
- success rate
- hit rate
- probability
- confidence
- expected win rate

Historical Hit Rate is reserved for a future backtest aggregation layer and must be computed only from historical `HistoricalOutcomeResult` records.

## Future Backtest Engine

Future Batch D work may build scanner, event collection, aggregation, denominator policy, and Historical Hit Rate reporting on top of these models.

That future layer should consume `SignalEvent` and `HistoricalOutcomeResult` without changing their historical semantics.
