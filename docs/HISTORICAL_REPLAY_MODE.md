# Historical Replay Mode

## Purpose

Historical Replay Mode lets the user choose one Replay Date and asks:

```text
If this Swing Research system had been run as of that date, which supplied symbols would have been MATCH?
```

This is deterministic historical research. It is not future probability, AI prediction, parameter optimization, recommendation, or trading simulation.

## Current Scan vs Replay

Current Scan evaluates the latest available technical snapshot.

Historical Replay first slices each symbol's price history to `trading_date <= replay_date`, rebuilds technical indicators from that sliced series, and evaluates the replay signal only on the latest snapshot inside that sliced series.

## Requested Replay Date

`replay_date` is the calendar date requested by the user.

It may be a weekend or holiday.

## Actual Trading Date

`actual_signal_date` is the latest available trading date on or before `replay_date` for each symbol.

Different markets can produce different actual dates for the same requested replay date.

## Price As-Of Slicing

Replay signal calculation uses:

```text
Full HistoricalPriceSeries
    ↓
slice_price_series_as_of(series, replay_date)
```

No signal feature is calculated from bars after the requested replay date.

## Technical As-Of Snapshot

Technical indicators for the replay signal are rebuilt from the sliced price series. The replay snapshot is the last snapshot in that sliced technical series.

## Signal No-Look-Ahead

`evaluate_signal_conditions()` receives only the replay technical snapshot. Future bars cannot change the replay `MATCH` / `NO_MATCH` / `NOT_EVALUABLE` result.

## Point-In-Time Historical Statistics

Historical context for a MATCH candidate uses only historical signal outcomes that were knowable by the replay date.

The backtest may be built from full cached price history for efficiency, but the replay layer filters exposed statistics with a point-in-time knowledge cutoff.

## Outcome Knowledge Cutoff

Each historical case is evaluated independently:

- `HIT` is known only if the first target-hit date is on or before `replay_date`.
- `MISS` is known only if the full horizon's Nth future trading bar is on or before `replay_date`.
- `INCOMPLETE` remains outside the resolved denominator.
- `NOT_EVALUABLE` is counted separately and excluded from the denominator.

## Early HIT Semantics

An early HIT can enter the resolved denominator before the full horizon completes, because the target event was already observable.

## MISS Resolution Semantics

A no-hit case cannot be counted as MISS until the full trading-bar horizon is complete.

## Return-Metric Availability

MFE, MAE, and End Return are included in replay aggregates only when the full horizon was complete by `replay_date`.

An early HIT near the replay date can affect hit-rate denominator while still contributing no return metrics.

## Historical Hit Rate As Of

```text
historical_hit_rate_as_of = HIT_as_of / (HIT_as_of + MISS_as_of)
```

If the resolved denominator is zero, the value is `None`.

## Sample Size As Of

Sample-size status uses `resolved_as_of_count`, not today's full-history resolved count.

## Post-Replay Verification

For replay MATCH candidates, the service also evaluates what happened after the actual signal date using the full price series.

This result is stored as `post_replay_outcome` and must be shown separately from point-in-time research context.

## Future Data Isolation

Replay candidate ranking and as-of context cannot use post-replay HIT / MISS / MFE / MAE / End Return.

Post-replay verification can show those values only in a separate section.

## Ranking Isolation

Replay ranking reuses `swing_research_rank_v1`, but all input values come from `PointInTimeBacktestSummary`.

## Universe Support

Replay service accepts normalized symbols. Manual Input, Watchlist, and Saved Universe resolution stay in UI / orchestration.

## Session State

Replay results remain session-only under the Swing Research session namespace. No SQLite tables are added.

## Rerun Safety

After a replay result is created, candidate selection and detail rendering reuse stored session result and scan-time price cache. They do not fetch prices or rerun scanner logic.

## No Probability

The UI uses `Historical Hit Rate (As Of)`, not probability, confidence, likelihood, or expected chance.

## No Optimization

Replay results do not tune `technical_example_v1` or any outcome definition.

## Walk-Forward Building Block

Single-Date Historical Replay is the source of truth for each period inside Walk-Forward Replay.

Walk-Forward Replay generates requested replay dates and repeatedly calls `HistoricalReplayService`. It must not reimplement replay signal semantics, point-in-time historical statistics, Research Priority ranking, or Post-Replay Outcome verification.

## Multi-Date Boundary

Walk-Forward Replay can aggregate descriptive candidate occurrence counts across periods, but it does not convert repeated candidates into aggregate hit-rate, probability, prediction accuracy, or trading P&L.

## Architecture

```text
Full HistoricalPriceSeries
        ↓
slice as-of Replay Date
        ↓
Replay Technical Snapshot
        ↓
Replay Signal Match
        ↓
Point-in-Time Historical Backtest Summary
        ↓
Replay Research Priority

Full future history
        ↓
separate Post-Replay Outcome Verification

Walk-Forward Replay
        ↓
repeated HistoricalReplayService calls
        ↓
period snapshots and descriptive occurrence counts
```
