# Swing Opportunity Scanner

## Purpose

Sprint 06 Batch E establishes a deterministic Swing Opportunity Scanner service.

The scanner accepts a caller-provided symbol universe, evaluates the latest available `TechnicalIndicatorSnapshot` for each symbol, and returns the symbols whose current snapshot is `MATCH` for the configured `SignalDefinition`.

This layer returns current research candidates only. It is not a buy list, recommendation list, expected-return rank, trading system, AI ranker, or market-wide crawler.

## Scanner vs Recommendation

`SwingOpportunityCandidate` means the latest technical snapshot currently satisfies the configured research condition.

It does not mean the stock should be bought, added to a watchlist, or expected to rise. It also does not mean a `NO_MATCH` stock is bad or expected to fall.

## Input Universe

The scanner only scans symbols supplied by the caller, such as:

```python
["2330.TW", "2454.TW", "NVDA", "AAPL", "6488.TWO"]
```

Each symbol is normalized with the shared `normalize_stock_symbol()` helper. Duplicate normalized symbols are scanned once in deterministic first-seen order.

Batch E does not include a full-market Taiwan stock, S&P 500, or other universe provider.

## Current Signal Evaluation

Per symbol, the scanner flow is:

```text
HistoricalPriceSeries
    ↓
TechnicalIndicatorSeries
    ↓
latest TechnicalIndicatorSnapshot
    ↓
evaluate_signal_conditions()
```

Only `SignalEvaluationStatus.MATCH` becomes a `SwingOpportunityCandidate`.

## MATCH / NO_MATCH / NOT_EVALUABLE

`MATCH` means all configured signal conditions can be evaluated and pass on the latest snapshot.

`NO_MATCH` means the latest snapshot was evaluable, but at least one signal condition did not pass.

`NOT_EVALUABLE` means required technical features were missing or unusable. It is preserved separately from `NO_MATCH` so insufficient data is not treated as a failed condition.

`SwingScannerResult.no_match_details` preserves a lightweight failed-condition summary for future UI audit without storing full technical snapshots for every non-match symbol.

## Backtest Only For Current MATCH

For performance and semantics, the scanner runs historical backtest only after the latest signal evaluation is `MATCH`.

`NO_MATCH` and `NOT_EVALUABLE` symbols do not run `run_historical_backtest()`.

When a symbol matches, the scanner reuses the already-built `TechnicalIndicatorSeries` for `run_historical_backtest()` instead of rebuilding technical indicators.

## Historical Hit Rate

For each current candidate, the scanner attaches a `HistoricalBacktestReport` using the same:

- `SignalDefinition`
- `OutcomeDefinition`
- `OverlappingSignalPolicy`
- `cooldown_bars`
- backtest signal-date range

Historical Hit Rate is copied from `HistoricalBacktestReport.historical_hit_rate`.

It is a historical condition hit rate for the configured signal and outcome. It is not future probability, expected chance, confidence, likelihood, or prediction.

## Resolved Sample Size

Resolved samples are:

```text
HIT + MISS
```

`INCOMPLETE` and `NOT_EVALUABLE` historical outcomes are counted and preserved, but they are excluded from the Historical Hit Rate denominator.

If `resolved_count == 0`, `historical_hit_rate` is `None`, not `0`.

## Sample Size Status

The scanner assigns a neutral `SampleSizeStatus`:

- `NO_RESOLVED_SAMPLES`
- `BELOW_PREFERRED_MINIMUM`
- `MEETS_PREFERRED_MINIMUM`

The preferred minimum comes from `SwingScannerConfig.minimum_resolved_samples`. It is a research filter / display aid, not a confidence model.

Candidates below the preferred minimum are still returned with a limitation. They are not deleted.

## Research Ranking

Matched candidates are ordered by a deterministic research-priority policy.

The ranking is used only to make a candidate list reproducible and easier to inspect. It is not an expected return rank, buy rank, AI score, hidden composite score, or prediction model.

## Ranking V1

The current policy is versioned as:

```text
swing_research_rank_v1
```

Ordering:

1. `SampleSizeStatus`: `MEETS_PREFERRED_MINIMUM`, then `BELOW_PREFERRED_MINIMUM`, then `NO_RESOLVED_SAMPLES`
2. `historical_hit_rate` descending, with `None` last
3. `resolved_count` descending
4. `median_max_adverse_return` descending, so `-0.02` sorts before `-0.10`
5. `median_max_close_return` descending
6. `median_end_return` descending
7. `symbol` ascending

This prevents a small perfect sample, such as `100% / n=3`, from automatically outranking a larger established sample, such as `70% / n=100`.

Each candidate exposes `rank_components` so future UI can explain the ordering from raw source metrics.

## MAE / MFE / End Return

The scanner does not recalculate return aggregates.

It copies:

- median / average MFE from `max_close_return`
- median / average MAE from `max_adverse_return`
- median / average end return from `end_of_window_return`
- median / average hit trading-bar index

MAE remains signed. It is not converted to absolute loss.

## Overlap Policy

Each candidate preserves:

- `overlap_policy`
- `cooldown_bars`
- backtest `start_date`
- backtest `end_date`

`ALLOW_ALL` candidates carry a limitation that historical events may overlap and are not statistically independent.

`COOLDOWN` candidates carry a limitation that cooldown reduces nearby repeated signals but does not guarantee statistical independence.

## Date Range

The scanner config explicitly stores the backtest signal-date range. The service does not hard-code a default range.

If `backtest_end_date` is `None`, historical signals through all available dates may be evaluated, and recent events can be `INCOMPLETE`.

## Stale Data

If the underlying `HistoricalPriceSeries` came from stale cache, the candidate preserves:

- `source_price_fetched_at`
- `source_price_is_stale`
- a stale-data limitation

The scanner does not hide stale current-signal evidence.

## Provisional Latest Bar

The current match uses the latest available daily technical snapshot.

Yahoo daily data may include an unfinished current-session bar. Batch E therefore sets `is_provisional_possible=True` and includes a structured limitation:

```text
Latest daily bar may be provisional if the current trading session is not complete.
```

The scanner does not claim real-time or completed-session signal status.

## Per-Symbol Failure Isolation

A failure for one symbol is captured as `SwingScanFailure` with:

- `symbol`
- `error_type`
- safe first-line `message`

Raw traceback is not stored. Other symbols continue scanning.

## No Probability

Batch E does not create probability, calibrated probability, confidence interval, p-value, expected return, prediction score, or opportunity score.

Future probability work would require out-of-sample validation and calibration beyond this scanner foundation.

## No Fundamentals Yet

The scanner only uses technical signal definitions.

It does not include ROE, EPS, revenue growth, valuation, news, sentiment, or fundamentals. Future fundamental filters must use point-in-time availability.

## No Market-Wide Universe Yet

The service accepts caller-provided symbols only.

Batch E does not crawl all Taiwan stocks, OTC symbols, S&P 500 constituents, or any full exchange universe.

## Future Dashboard

A future scanner dashboard can render `SwingScannerResult`, current signal traces, rank components, sample status, limitations, and historical backtest summaries.

The dashboard must preserve the same wording boundaries: research candidates, not recommendations.

## Future Case Explorer

Future historical case review can use `HistoricalBacktestReport.cases` and case-window helpers from the backtest layer.

Batch E does not draw charts or retrieve cases in UI.

## Future Point-In-Time Fundamentals

Future fundamental filters must use data available at each historical signal date. They must not backfill today-known financial facts into past signal decisions.

## Future Calibrated Probability

Calibrated probability is explicitly future work and would require methodology that Batch E does not implement.
