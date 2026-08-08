# Out-of-Sample Validation

## Purpose

Sprint 08 Batch A establishes a deterministic Out-of-Sample Validation Foundation.

It compares the same fixed research specification across three non-overlapping historical periods:

- `DEVELOPMENT`
- `VALIDATION`
- `HOLDOUT`

The goal is to inspect whether fixed rules show similar descriptive historical behavior outside the period used to develop or adjust the rules.

This layer is not a probability model, recommendation engine, trading strategy P&L, or automatic optimization workflow.

## Development / Validation / Holdout

`DEVELOPMENT` is the historical period that may be used while researching or establishing rules.

`VALIDATION` checks whether fixed rules continue to show similar behavior, but validation results must not automatically modify the rules.

`HOLDOUT` is the out-of-sample period. A formal validation run treats Holdout as not participating in signal, outcome, ranking, cooldown, horizon, threshold, or minimum-sample rule creation.

Period boundaries are inclusive:

```text
start_date <= requested replay date <= end_date
```

Because both ends are inclusive, a one-day boundary overlap is rejected.

## Why Holdout Exists

Holdout protects the research process from hidden selection bias.

If Holdout results are used to choose a signal, outcome, cooldown, horizon, threshold, frequency, or ranking rule, the period is no longer a true out-of-sample check.

## Point-In-Time / No-Look-Ahead

The OOS service limits requested replay dates by period. Each replay date still uses `HistoricalReplayService` for point-in-time behavior:

```text
Full HistoricalPriceSeries
        ↓
slice as of requested replay date
        ↓
rebuild technical indicators
        ↓
evaluate replay signal
        ↓
separate post-replay outcome verification
```

Future bars must not change replay signal status, as-of Historical Hit Rate, Research Priority, candidate occurrence, candidate dates, or period-local stability metrics.

## Frozen Research Specification

Each run saves a `FrozenResearchSpecification` containing the materially relevant fixed settings:

- `SignalDefinition`
- `OutcomeDefinition`
- replay frequency
- overlap policy
- cooldown bars
- historical start date
- minimum resolved samples

The specification has a deterministic research fingerprint. `generated_at` is intentionally excluded from the fingerprint.

The same fixed specification must produce the same fingerprint for Development, Validation, and Holdout. If a materially relevant setting changes, the fingerprint changes.

## Historical Hit Rate Semantics

Historical Hit Rate is:

```text
HIT / (HIT + MISS)
```

`Resolved n` is:

```text
HIT + MISS
```

`INCOMPLETE` and `NOT_EVALUABLE` are counted and displayed separately, but excluded from the denominator.

If `Resolved n == 0`, Historical Hit Rate is `None` / `N/A`, not `0%`.

Historical Hit Rate is not win rate, future probability, success probability, prediction accuracy, confidence, likelihood, or expected return.

## Candidate Stability

OOS period results reuse Replay Analytics for descriptive stability metrics:

- candidate occurrence count
- candidate period share
- first / last occurrence
- longest consecutive candidate periods
- candidate-set Jaccard similarity
- candidate-set turnover

These metrics are period-local. Holdout stability uses only Holdout requested replay dates. Development candidate history is not mixed into Holdout stability metrics.

Candidate Period Share is:

```text
periods with candidates / total requested replay periods
```

It is not signal probability or future probability.

## Cross-Period Comparison

The result includes transparent raw-fact comparisons:

- candidate period share difference
- unique candidate symbol count difference
- total candidate occurrence difference
- post-replay outcome count differences
- cross-period candidate-set Jaccard similarity

It does not create validation score, OOS score, quality score, confidence score, robustness score, hidden weighted score, prediction score, or recommendation score.

## Price-Series Reuse

The service loads one full `HistoricalPriceSeries` per normalized symbol and reuses that run-local cache across Development, Validation, and Holdout.

This prevents `periods x replay dates x symbols` repeated provider fetches. `HistoricalReplayService` remains responsible for as-of slicing for each replay date.

If a symbol provider fails, the failure is isolated by inserting an empty stale series for that symbol so the validation run can complete without repeated refetch attempts.

## Sample-Size Limitations

Small samples can produce unstable Historical Hit Rate values. A high ratio with low `Resolved n` should remain descriptive context only.

OOS does not auto-relax thresholds, fabricate fallback candidates, choose the best period, or optimize parameters when a period is sparse.

## Overlap Dependence

`ALLOW_ALL` can include adjacent or overlapping events. `COOLDOWN` reduces nearby repeated signals by trading-bar distance, but does not prove independent samples.

Candidate occurrences across monthly or weekly replay dates may be serially correlated.

## Data Limitations

Results remain subject to:

- Yahoo data-source coverage and adjustment limitations
- missing bars or market holidays
- survivorship bias from caller-provided universes
- current-day provisional data risk
- differences in market calendars for mixed-market symbols

The service does not solve survivorship bias or data-vendor quality limitations.

## Non-Goals

The service foundation does not provide:

- probability model
- future probability
- automatic parameter optimization
- threshold tuning
- best signal / outcome / cooldown / horizon selection
- Buy / Sell / Hold recommendation
- target price
- position sizing
- strategy P&L
- transaction costs
- stop loss optimization
- AI ranking

Sprint 08 Batch B adds a dashboard on top of this foundation. The dashboard remains descriptive: it displays Development / Validation / Holdout comparison, Research Specification Fingerprint, Historical Hit Rate + Resolved n, Candidate Period Share, outcome counts and period-local stability, but it still does not create a validation score, prediction model, optimization workflow, recommendation, or strategy P&L.
