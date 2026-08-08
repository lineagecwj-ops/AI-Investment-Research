# Replay Analytics & Stability Review

## Purpose

Replay Analytics & Stability Review is a deterministic descriptive layer on top of `WalkForwardReplayResult`.

It asks:

```text
Across existing walk-forward replay periods, how did candidate appearances, candidate-set stability, Research Priority, and Post-Replay Outcome counts behave?
```

It does not fetch prices, build indicators, rerun Historical Replay, rerun backtests, train models, optimize parameters, or persist analytics to SQLite.

## Input Contract

The analytics service consumes an already-created `WalkForwardReplayResult`:

```text
WalkForwardReplayResult
        ↓
replay_analytics_service.py
        ↓
ReplayAnalyticsResult
```

The service is network-free and has no provider, replay, scanner, or backtest hooks.

## Descriptive Analytics Semantics

`ReplayAnalyticsResult` contains:

- `ReplayStabilitySummary`
- `ReplayPeriodSummary`
- `ReplaySymbolSummary`
- `ReplayCandidateOccurrence`
- `ReplayOutcomeDistribution`

All result models are frozen dataclasses and do not store pandas DataFrames.

## Candidate Period Share

At the stability-summary level:

```text
periods_with_candidates / total_period_count
```

At the symbol-summary level:

```text
candidate_occurrence_count / total_period_count
```

Candidate Period Share is only the share of replay periods with at least one candidate, or the share of replay periods where a symbol appeared as a candidate. It is not future probability, signal probability, prediction accuracy, confidence, or likelihood.

## Consecutive Occurrence Semantics

`longest_consecutive_candidate_periods` uses the ordered replay period sequence in the result.

It does not infer continuity from calendar-day or calendar-month gaps. This keeps the same logic valid for Weekly and Monthly replay frequencies.

## Candidate Set Jaccard Similarity

For each consecutive pair of replay periods:

```text
previous candidate set = A
current candidate set = B
similarity = |A intersect B| / |A union B|
```

When both sets are empty, similarity is `1.0` because the candidate set did not change.

## Candidate Set Turnover

Candidate Set Turnover is:

```text
1 - Candidate Set Jaccard Similarity
```

It measures candidate-set stability only. It is not portfolio turnover, trading turnover, or strategy churn.

## Research Priority Stability

Occurrence rows preserve `research_priority_rank` when it exists on replay candidates.

Symbol summaries report:

- Best Research Priority
- Median Research Priority
- Worst Research Priority

These ranks are computed only from candidate appearances. Post-Replay Outcome does not change Research Priority rank history and is not used to reorder candidates.

## Post-Replay Outcome Separation

Candidate status comes from the replay date as-of signal result.

Post-Replay Outcome is later historical verification and is counted separately as:

- HIT
- MISS
- INCOMPLETE
- NOT_EVALUABLE

These are counts only. The analytics layer does not create Walk-Forward Hit Rate, success rate, win rate, predictive accuracy, strategy P&L, or any probability field.

## Future-Information Boundary

The analytics result can contain both as-of candidate occurrence fields and Post-Replay Outcome counts, but the two categories remain separate:

- As-of fields: candidate occurrence, requested replay date, actual signal date, Research Priority rank.
- Post-replay fields: outcome status counts and distribution.

Future outcome data must not mutate candidate occurrence, candidate dates, Candidate Period Share, consecutive appearance counts, or Research Priority rank history.

## Empty Periods

Zero-MATCH periods are preserved in period summaries and the dashboard timeline.

The layer supports:

- Zero replay periods
- All periods with zero MATCH
- Zero candidate occurrences
- All outcomes incomplete
- All outcomes not evaluable
- Mixed outcome statuses
- Period-level failures

It does not relax signals, tune thresholds, fabricate candidates, or hide empty periods.

## Ordering

Ordering is deterministic:

- Period summaries: requested replay date ascending
- Occurrences: requested replay date ascending, Research Priority ascending, symbol ascending
- Symbol summaries: candidate occurrence count descending, longest consecutive periods descending, symbol ascending

## Non-Goals

This layer does not provide:

- Future probability
- Upward-move probability
- Confidence score
- Prediction score
- Opportunity score
- Buy / Sell / Hold
- Recommendation
- Target price
- Expected return prediction
- Aggregate Walk-Forward Hit Rate
- Strategy win rate
- Trading P&L
- Portfolio P&L
- Transaction costs
- Position sizing
- Stop loss
- Take profit
- Sharpe ratio
- Sortino ratio
- Max drawdown
- Equity curve
- Parameter optimization
- Threshold tuning
- Signal optimization
- Cooldown optimization
- Best parameter search
- ML / AI ranking
- OpenAI API calls
- Fundamentals merge
- Scheduled scan
- Background job
- SQLite analytics persistence

## Known Limitations

- Results depend on selected universe.
- Results depend on `SignalDefinition`.
- Results depend on `OutcomeDefinition`.
- Results depend on replay frequency.
- Candidate appearances may be serially correlated.
- Overlapping historical windows are not independent.
- Survivorship bias remains possible.
- Yahoo data-source limitations remain.
- Current system does not establish future probability.
- Descriptive occurrence frequency is not predictive probability.
- Post-Replay Outcome counts are not strategy P&L.
- No statistical significance testing yet.
- No confidence intervals yet.
- No out-of-sample model selection.
- No parameter optimization.
