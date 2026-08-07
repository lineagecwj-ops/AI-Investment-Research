# Historical Backtest Engine

## Purpose

Sprint 06 Batch D establishes a deterministic historical backtest aggregation layer.

The engine evaluates a specified `SignalDefinition` and `OutcomeDefinition` on one historical price / technical series pair, then aggregates already-created `HistoricalOutcomeResult` records into a `HistoricalBacktestReport`.

This layer is descriptive historical research. It is not a strategy simulator, future probability model, scanner, ranking engine, dashboard, or AI prediction system.

## Backtest vs Trading Simulation

The backtest engine counts historical market events after frozen signal dates. It does not assume capital, position size, entry fill, exit rule, stop loss, transaction cost, tax, slippage, or portfolio return.

A `HIT` means the configured outcome target occurred inside the historical outcome window. It does not mean a profitable trade was executed.

## Input Layers

The engine consumes:

- `HistoricalPriceSeries`
- `TechnicalIndicatorSeries`
- `SignalDefinition`
- `OutcomeDefinition`
- `BacktestConfig`

The technical series must already be built from the same symbol as the price series. Technical snapshots must correspond to trading dates present in the price series.

## SignalDefinition

Signals are found by `find_signal_events()`.

Signal-date features come only from `TechnicalIndicatorSnapshot` values that were available on that date. The backtest layer does not inspect future prices to decide whether a signal existed.

## OutcomeDefinition

Each filtered `SignalEvent` is evaluated with `evaluate_historical_outcome()`.

Outcome evaluation may inspect bars after the signal date, but only to label the already-frozen historical event. Outcome data does not flow back into the signal.

## Raw vs Filtered Events

`raw_signal_count` is the number of events produced by `find_signal_events()` before date-range and overlap filtering.

`filtered_signal_count` is the number of events that enter outcome evaluation after the inclusive signal-date range filter and overlap policy.

The report also preserves `raw_events` and `evaluated_events` for future cooldown-impact review.

## Cooldown

`BacktestConfig.overlap_policy` supports:

- `ALLOW_ALL`: every date-filtered raw event is evaluated.
- `COOLDOWN`: events are filtered through Batch C `apply_signal_cooldown()`.

Cooldown uses trading-bar distance, not calendar days. It reduces adjacent overlapping events for analysis, but it does not make samples fully independent.

## HIT / MISS / INCOMPLETE / NOT_EVALUABLE

Backtest case status comes directly from `HistoricalOutcomeResult.status`.

The backtest layer does not recompute or override `HIT`, `MISS`, `INCOMPLETE`, or `NOT_EVALUABLE`.

## Resolved Denominator

Resolved outcomes are:

```text
HIT + MISS
```

`INCOMPLETE` and `NOT_EVALUABLE` are excluded from the denominator.

Early `HIT` cases are resolved even when the full outcome window has not yet completed. Incomplete no-hit cases remain excluded.

## Historical Hit Rate

Historical Hit Rate（歷史命中率）is:

```text
HIT / (HIT + MISS)
```

If `resolved_count == 0`, `historical_hit_rate` is `None`.

The raw domain value is an unrounded ratio, such as `0.686`. Future presentation layers may display it as `68.60%`.

Historical Hit Rate is a conditional historical event rate for the specified signal and outcome definitions. It is not future probability, predicted probability, success probability, confidence, likelihood, or expected return.

## Return Aggregates

Return aggregates use only cases with non-`None` values. Missing values are not filled with `0`.

The report stores both average and median values, plus sample counts:

- `max_return_sample_count`
- `max_adverse_sample_count`
- `end_return_sample_count`
- `hit_bar_sample_count`

## MFE / MAE

`max_close_return` is the close-based maximum favorable excursion over a complete outcome window.

`max_adverse_return` is the close-based maximum adverse excursion over a complete outcome window. Negative values stay negative and are not converted to absolute values.

Early hits with incomplete windows can contribute to hit-rate denominator, but their MFE / MAE / end-return values remain `None` until the full window exists.

## End Return

`end_of_window_return` is the analysis-close return on the final bar of the outcome horizon. It is aggregated only when present.

It is not a trade exit return.

## Hit-Bar Metrics

Hit timing uses trading bar index, not calendar days.

For `HIT` cases, the report aggregates:

- `average_hit_bar_index`
- `median_hit_bar_index`

If no hit-bar values exist, both fields are `None`.

## Date Range

`BacktestConfig.start_date` and `end_date` filter signal dates inclusively:

```text
start_date <= signal_date <= end_date
```

When either side is `None`, that side is unbounded.

## Future Outcome Beyond End Date

The backtest `end_date` does not truncate outcome windows.

Example: if `end_date = 2024-12-31` and a signal occurs on `2024-12-20`, the outcome evaluator can still use 2025 future bars if they are present in `HistoricalPriceSeries`.

## Case IDs

`HistoricalBacktestCase.case_id` is deterministic:

```text
symbol|signal_id|signal_date|outcome_definition_id
```

The report `backtest_id` is a deterministic hash of symbol, signal definition, outcome definition, overlap policy, cooldown, and date range. `generated_at` is not part of identity.

## Case Window Helper

`get_backtest_case_price_window()` can return signal-context price bars for future case review:

```text
pre-signal bars + signal date + post-signal bars
```

This is for historical review and future charting only. Displaying future bars after the signal date does not allow future bars to alter signal features.

## Overlap Bias

`ALLOW_ALL` can produce adjacent or overlapping events. Those samples may be highly dependent.

`COOLDOWN` can reduce overlap, but it does not prove statistical independence.

## Survivorship Bias

If users only backtest currently visible or currently listed symbols, results can have survivorship bias. Batch D documents this limitation but does not solve it.

## Data-Source Limitations

Yahoo historical coverage, adjusted-close semantics, raw high / low basis, missing bars, and latest provisional daily bars can affect results. These limitations continue from the historical price and technical indicator foundations.

## No Fundamentals Yet

Batch D does not merge fundamental data.

Future fundamental signals must use point-in-time availability. They must not use facts known today to backfill historical signal dates.

## No Transaction Simulation

Batch D does not model capital, position size, execution, exit, stop loss, commission, tax, slippage, or portfolio-level return.

`HIT` and `MISS` are outcome labels, not winning or losing trades.

## No Out-of-Sample Validation

Batch D is an in-sample descriptive historical aggregation layer. It does not perform train/test split, walk-forward validation, out-of-sample testing, or probability calibration.

## Historical Hit Rate Is Not Probability

The system must not rename `historical_hit_rate` into probability, confidence, likelihood, expected success, or future prediction.

Future probability work would require additional validation, calibration, and out-of-sample methodology.

## Future Scanner / Case Explorer

Future Batch E can build a Swing Opportunity Scanner on top of this deterministic report.

Future Batch F can build Historical Case Explorer / charts using saved cases and optional case price windows.
