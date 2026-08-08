# Swing Research Dashboard

## Purpose

Sprint 07 Batch A adds a Streamlit `Swing Research` dashboard workflow that integrates the existing Swing Opportunity Scanner, Historical Backtest Engine, and Historical Case Explorer.

The dashboard is a deterministic research interface. It is not an automatic profitable stock finder, recommendation system, trading signal, future probability model, AI ranker, or portfolio execution tool.

## Daily Workflow

The intended flow is:

```text
Manual Input / Watchlist / Saved Universe
    ↓
Explicit scanner submit
    ↓
SwingScannerResult
    ↓
Candidate table
    ↓
Selected candidate detail
    ↓
HistoricalBacktestReport
    ↓
HistoricalCaseService
    ↓
Historical Cases Preview
```

## Scan Setup

The page accepts caller-provided symbols from an explicit source selector:

- Manual Input
- Watchlist
- Saved Universe

Manual Input remains available and does not require creating a saved Universe.

Saved Universe selection shows the Universe name, symbol count, updated timestamp, and symbol preview. Selecting a Universe does not run the scanner.

Examples:

```text
2330
2454
NVDA
AAPL
6488.TWO
```

Whitespace, newline, comma, semicolon, Chinese comma, and Chinese semicolon separators are accepted. Pure numeric symbols are normalized through the shared symbol helper, so `2330` becomes `2330.TW`.

Saved Universe and Watchlist sources resolve to normalized symbols before scanning. Empty sources show a prompt and do not run the scanner.

The first version uses:

- Signal Definition: `technical_example_v1`
- Outcome Definition: `raw_high_breakout_60d_within_20d_v1`

The service does not hard-code the date range. The UI default is `2018-01-01` to `2025-12-31`.

## Source Snapshot and Fingerprint

Swing Research stores scan-time source metadata in session state:

- `symbol_source_type`
- `source_universe_id`
- `source_universe_name`
- `symbols_snapshot`

The displayed result uses this snapshot, so editing or deleting a Universe later does not mutate an existing scan result.

The dashboard fingerprint includes source mode and resolved normalized symbols, not only a Universe id. If a user scans a Universe with two symbols and later edits it to three symbols, the current configuration differs from the stored result and the UI asks the user to scan again.

Switching Manual Input, Watchlist, or Saved Universe does not automatically scan.

## Current Signal

Current Signal is evaluated only from the latest available `TechnicalIndicatorSnapshot`.

For a selected candidate, the dashboard shows:

- Latest Trading Date
- Analysis Close
- Signal Status
- condition trace copied from `candidate.signal_match`

The condition trace is not recalculated in the dashboard.

## Technical Snapshot

The Current Technical Snapshot expander shows key current features:

- SMA20
- SMA60
- SMA120
- SMA200
- RSI14
- MACD
- MACD Signal
- ATR14 %
- Volume Ratio20
- Return20D
- Return60D
- Distance to Prior60D High

## Historical Backtest

The selected candidate detail shows historical context copied from the candidate and its `HistoricalBacktestReport`:

- Historical Hit Rate
- Resolved Samples
- HIT
- MISS
- INCOMPLETE
- NOT_EVALUABLE
- Raw Signals
- Evaluated Signals
- Backtest Range
- Overlap Policy
- Cooldown

## Historical Hit Rate

Historical Hit Rate is a descriptive historical condition-event ratio:

```text
HIT / (HIT + MISS)
```

`INCOMPLETE` and `NOT_EVALUABLE` are preserved but excluded from the denominator.

The dashboard must show Historical Hit Rate together with Resolved Samples. If there are no resolved samples, Historical Hit Rate is `N/A`, not `0%`.

Historical Hit Rate is not future probability, expected chance, confidence, likelihood, prediction, or recommendation.

## Resolved Samples

Resolved Samples are `HIT + MISS`.

Small samples are displayed neutrally. For example, `100% / n=3` is shown with:

```text
Sample Status: Below Preferred Minimum
```

This does not mean low confidence or unreliable. It only means the resolved sample count is below the user-selected preferred display threshold.

## Research Priority

Candidate rows preserve the scanner service order and display it as `Research Priority`.

Research Priority is inspection order. It is not a recommendation, score, expected-return rank, or trading instruction.

## Sample-Size Tiers

The current ranking policy is:

```text
swing_research_rank_v1
```

Ordering:

```text
Sample-size tier
→ Historical Hit Rate
→ Resolved n
→ Median MAE
→ Median MFE
→ Median End Return
→ Symbol
```

This prevents a small perfect sample such as `100% / n=3` from automatically appearing before a larger sample such as `70% / n=100`.

## MFE / MAE / End Return

MFE, MAE, and End Return are close-based historical return context metrics copied from the historical backtest report.

They are not actual trading profit and loss, portfolio returns, entry or exit rules, or guaranteed outcomes.

A high Historical Hit Rate can coexist with negative Median End Return because target events may occur before the end of the evaluation window. A `HIT` does not imply a positive end-of-window return.

## Historical Cases Preview

Historical Cases Preview builds `HistoricalCaseView` objects from:

```text
candidate.historical_backtest_report
scan-time HistoricalPriceSeries cache
```

It does not rerun the scanner, rerun backtest, recalculate signals, recalculate outcomes, or fetch prices when the user selects a candidate.

The preview shows counts for:

- HIT Cases
- MISS Cases
- INCOMPLETE Cases

The default filter is `Resolved`, which includes both HIT and MISS. Users can also filter to HIT or MISS. The preview limits rows to the latest five cases to avoid rendering too many charts.

## HIT / MISS Semantics

`HIT` means the configured historical outcome target occurred within the configured horizon.

`MISS` means the full horizon was available and the target did not occur.

`HIT` is not a profitable trade. `MISS` is not a losing trade.

The dashboard includes a selection-bias caption reminding users to review both HIT and MISS cases.

## Stale Data

If the scanner candidate was built from stale historical price cache, the selected candidate detail shows a stale-data warning.

## Provisional Latest Bar

The dashboard displays the scanner limitation:

```text
Latest daily bar may be provisional if the trading session is not complete.
```

## Overlap Dependence

`ALLOW_ALL` preserves all matching historical signal events and may include overlapping events.

`COOLDOWN` reduces nearby repeated events but does not guarantee independent samples.

## No Probability

The dashboard does not display future probability, calibrated probability, expected chance, confidence, likelihood, or AI prediction.

Future calibrated probability would require separate out-of-sample validation and calibration work.

## No Recommendation

The dashboard does not provide Buy / Sell / Hold, target price, portfolio action, alert, notification, or execution workflow.

## No Fundamentals Yet

The current scanner is technical-only.

Fundamental conditions are not included yet. Future fundamental filters must use point-in-time availability and must not backfill today-known financial data into historical signal dates.

## Session State

All Swing Research state uses the `swing_research_*` namespace:

- `swing_research_result`
- `swing_research_config_fingerprint`
- `swing_research_last_error`
- `swing_research_price_series_by_symbol`

No SQLite persistence is added.

## Rerun Safety

Only pressing `執行波段掃描` runs the scanner and loads prices.

These actions only rerender existing session results:

- candidate selection
- sorting or filtering
- expanders
- case preview filter
- case selection
- Streamlit rerun

## Clear Behavior

`清除掃描結果` clears only `swing_research_*` session keys.

It does not clear price cache, AI Research state, Historical Cases state, Watchlist state, or SQLite data.

## Light / Dark Theme

The dashboard uses Streamlit and Altair defaults and does not force a dark theme or hard-code global text colors.

## Future Point-In-Time Fundamentals

Future scanner work may add point-in-time fundamental filters after the data availability contract is explicit.

## Future Calibrated Probability

Future probability work is outside Sprint 07 Batch A and must be separate from Historical Hit Rate wording.
