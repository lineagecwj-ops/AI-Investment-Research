# Walk-Forward Replay

## Purpose

Walk-Forward Replay is a deterministic multi-date historical research simulation.

It asks:

```text
If this Swing Research system had been opened at each requested replay date, what would it have shown?
```

It is not a probability model, strategy backtest, trading simulator, portfolio backtest, prediction accuracy report, model training run, or parameter optimization workflow.

## Single Replay vs Walk-Forward

Single-Date Historical Replay remains the source of truth for one replay date.

Walk-Forward Replay only generates a schedule, calls `HistoricalReplayService` repeatedly, preserves each period result, and aggregates descriptive occurrence counts.

## Replay Schedule

`WalkForwardReplayConfig` accepts:

- `start_date`
- `end_date`
- `frequency`
- `signal_definition`
- `outcome_definition`
- `overlap_policy`
- `cooldown_bars`
- `historical_start_date`
- `preferred_resolved_samples`

The date range is inclusive.

## Monthly Semantics

Monthly replay dates are calendar month ends inside the inclusive range.

If `start_date=2024-01-20`, the first January replay date is still `2024-01-31`.

If `end_date=2024-03-15`, `2024-03-31` is excluded because it is after the end date.

## Weekly Semantics

Weekly replay dates are Fridays inside the inclusive range.

No global exchange calendar is used.

## Requested vs Actual Date

The requested replay date is a calendar date.

Each symbol still resolves its own actual trading date through Single-Date Historical Replay: the latest available `trading_date <= requested_replay_date`.

## Point-In-Time Correctness

For every period:

- Replay signal uses only prices available by that replay date.
- Historical Hit Rate (As Of) uses only outcomes knowable by that replay date.
- Research Priority uses only point-in-time historical statistics.
- Post-Replay Outcome is separate historical verification.
- Later periods do not mutate earlier period results.

## Candidate Occurrences

If the same symbol appears as a candidate in January, February, and March, that is three candidate occurrences.

`unique_candidate_symbols` remains one.

## Repeated-Candidate Dependence

Repeated replay candidates are correlated observations.

They are not independent trials and must not be summarized as a simple independent hit-rate sample.

## Summary

`WalkForwardReplaySummary` reports counts:

- Replay periods
- Periods with and without MATCH
- Candidate occurrences
- Unique candidate symbols
- Post-Replay HIT / MISS / INCOMPLETE / NOT_EVALUABLE occurrences
- Per-symbol candidate frequency

It intentionally does not expose Walk-Forward Hit Rate, win rate, probability, or prediction accuracy.

## Post-Replay Outcome

Every MATCH candidate preserves a Post-Replay Outcome from the underlying Single-Date Replay result.

This can use future bars after the walk-forward `end_date`; `end_date` limits replay dates, not outcome verification.

## Price-Series Reuse

Walk-Forward Replay loads full price history once per normalized symbol into a run-local memory cache.

Each period reuses the cached `HistoricalPriceSeries` through `HistoricalReplayService.replay_scan(..., price_series_by_symbol=...)`.

## Session State

Dashboard results are session-only. No SQLite table or persistent replay result store is added.

Changing period selectors, sorting tables, selecting candidates, expanding details, or rendering charts must not rerun walk-forward execution.

## Performance Guard

The service defaults to `MAX_REPLAY_PERIODS = 120`.

Requests beyond that safety limit raise a config error before partial results are produced.

## No Parameter Optimization

Walk-forward frequency is a replay cadence only.

The service does not tune signal thresholds, outcome horizons, overlap policy, cooldown bars, or frequency based on results.

## No Trading P&L

There is no entry rule, exit rule, capital allocation, position sizing, transaction cost, portfolio return, equity curve, Sharpe ratio, max drawdown, or profit factor.

Strategy simulation would be a separate future layer.

## Architecture

```text
Replay Date Generator
        ↓
run-local full price-series cache
        ↓
HistoricalReplayService
        ↓
WalkForwardReplayPeriod[]
        ↓
WalkForwardReplaySummary
        ↓
Dashboard Timeline / Period Detail
```
