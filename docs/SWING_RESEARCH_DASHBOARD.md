# Swing Research Dashboard

## Purpose

Sprint 07 Batch A adds a Streamlit `Swing Research` dashboard workflow that integrates the existing Swing Opportunity Scanner, Historical Backtest Engine, and Historical Case Explorer.

The dashboard is a deterministic research interface. It is not an automatic profitable stock finder, recommendation system, trading signal, future probability model, AI ranker, or portfolio execution tool.

Sprint 07 Batch C adds `Historical Replay` as a second scan mode inside the same page. It is a single-date as-of replay workflow.

Sprint 07 Batch D adds `Walk-Forward Replay` as a third scan mode. It repeats Single-Date Historical Replay across a date schedule and reports descriptive period / occurrence counts. It is not walk-forward prediction accuracy, strategy validation, or replay performance scoring.

Sprint 08 Batch B adds `Out-of-Sample Validation` as another explicit mode inside the same page. It compares Development / Validation / Holdout OOS results for one frozen research specification. It is descriptive validation visualization, not a validation score, model-selection workflow, optimization tool, prediction engine, or strategy P&L review.

## Daily Workflow

The intended flow is:

```text
Manual Input / Watchlist / Saved Universe
    ↓
Explicit scanner submit
    ↓
SwingScannerResult
    ↓
Technical Condition Detail for MATCH / NO_MATCH
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

Historical Replay flow:

```text
Scan Mode: Historical Replay
    ↓
Replay Date + Manual Input / Watchlist / Saved Universe
    ↓
Explicit replay submit
    ↓
HistoricalReplayResult
    ↓
Replay Candidate Table
    ↓
Signal Snapshot As Of
    ↓
Historical Context Available As Of Replay Date
    ↓
Separate Post-Replay Outcome verification
```

Walk-Forward Replay flow:

```text
Scan Mode: Walk-Forward Replay
    ↓
Start Date + End Date + Frequency + Source
    ↓
Explicit walk-forward submit
    ↓
WalkForwardReplayResult
    ↓
Period Timeline
    ↓
Candidate Frequency
    ↓
Selected Replay Period
    ↓
Single-Date Historical Replay result detail
```

Out-of-Sample Validation flow:

```text
Scan Mode: Out-of-Sample Validation
    ↓
Development / Validation / Holdout ranges + Frequency + Source
    ↓
Explicit validation submit
    ↓
OutOfSampleValidationResult
    ↓
Research Specification Fingerprint
    ↓
Period Summary + Cross-Period Comparison
    ↓
Period-local Candidate Stability
```

V1 Historical Condition Diagnostics dashboard flow:

```text
Swing Research
    ↓
V1 歷史條件診斷 section
    ↓
Stock scope + observation date range
    ↓
Explicit 執行 V1 歷史診斷 submit
    ↓
Read data/stocks.db with SQLite mode=ro
    ↓
Batch 1 HistoricalConditionDiagnosticsResult
    ↓
Batch 2 HistoricalConditionOutcomeComparisonResult
    ↓
Beginner-first summary, 0/5～5/5 chart, 4/5 missing-condition table,
single-condition pass-rate table, collapsed advanced metadata
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

Historical Replay uses `Replay Date` instead of Current Scan's backtest end date. Its historical start date defaults to `2018-01-01`, and each symbol resolves its own actual trading date on or before the requested replay date.

Walk-Forward Replay uses `Start Date`, `End Date`, `Frequency`, and `Historical Start`. The default frequency is `MONTHLY`. The user must press `執行 Walk-Forward Replay`; changing dates, frequency, period selector, or table state does not run the workflow.

Out-of-Sample Validation uses:

- Development Start / End
- Validation Start / End
- Holdout Start / End
- Replay Frequency
- Historical Start
- Overlap Policy
- Cooldown Bars when applicable
- Preferred Resolved Sample Minimum

The default split is editable and is not described as optimized. The user must press `執行樣本外驗證`; changing setup fields, expanders, charts, or tables does not run validation.

The `V1 歷史條件診斷` section uses a separate explicit button, `執行 V1 歷史診斷`. Changing the display scope, expanders, chart/table state, or other selectors only renders the stored `historical_condition_dashboard_*` session-state payload and does not rerun diagnostics, reload Yahoo, rerun scanner, rerun replay, rerun OOS, or write SQLite.

The default diagnostic stock scope is the current research set:

- `2330.TW`
- `0050.TW`
- `2337.TW`
- `2404.TW`
- `2454.TW`

The default observation window is `2018-01-01` through `2025-12-31`.

## Source Snapshot and Fingerprint

Swing Research stores scan-time source metadata in session state:

- `symbol_source_type`
- `source_universe_id`
- `source_universe_name`
- `symbols_snapshot`

The displayed result uses this snapshot, so editing or deleting a Universe later does not mutate an existing scan result.

The dashboard fingerprint includes source mode and resolved normalized symbols, not only a Universe id. If a user scans a Universe with two symbols and later edits it to three symbols, the current configuration differs from the stored result and the UI asks the user to scan again.

The fingerprint also includes `scan_mode`. In Historical Replay it includes `replay_date`; in Walk-Forward Replay it includes frequency, replay date range, historical start, and source symbols.

Out-of-Sample Validation uses a separate UI request fingerprint stored as `oos_validation_fingerprint`. It is not the same as the service-level Research Specification Fingerprint. The UI request fingerprint detects stale displayed results when the user changes dashboard inputs without pressing `執行樣本外驗證`.

Switching Manual Input, Watchlist, or Saved Universe does not automatically scan.

Switching between Current, Historical Replay, Walk-Forward Replay, and Out-of-Sample Validation does not automatically scan. If a stored Swing result came from another mode, the UI displays a mode mismatch warning. If OOS validation inputs changed, the UI displays that the current result came from a previous validation setup.

The V1 historical condition diagnostics dashboard stores:

- `historical_condition_dashboard_payload`
- `historical_condition_dashboard_fingerprint`
- `historical_condition_dashboard_last_error`
- `historical_condition_dashboard_error_details`

The fingerprint includes normalized symbols, observation start/end, signal id, outcome id, warm-up bars, and outcome horizon. If controls change after a run, the UI shows a stale-result warning and waits for another explicit submit.

## V1 Historical Condition Diagnostics Dashboard

The section title shown to users is `V1 歷史條件診斷`.

The primary explanation is beginner-first:

```text
這裡會比較歷史上符合不同數量 V1 技術條件的樣本，
觀察之後 20 個交易日內，
是否突破當時的前 60 日高點。
```

The neutral safety note is:

```text
這是歷史樣本的描述性統計，不是未來上漲機率，也不是買進建議。
```

The dashboard has three visible layers:

- `V1 條件有效性總覽`：0/5～5/5 Historical Hit Rate chart and table, always with resolved `n`.
- `哪些條件最常造成差異`：4/5 missing-condition outcome comparison, displayed in canonical V1 condition order rather than hit-rate order.
- `進階研究資訊`：collapsed HIT / MISS / INCOMPLETE / NOT_EVALUABLE counts, observation unit, overlap metadata, warm-up bars, outcome horizon, signal id, and outcome id.

The single-condition pass-rate block is labeled `哪些 V1 條件本來就比較難符合？`. Pass rate means the condition was individually true among evaluable samples. A low pass rate does not mean the condition is bad.

The Dashboard reuses Batch 1 and Batch 2 service contracts:

- condition diagnostics reuse `technical_example_v1` and `evaluate_signal_conditions()`
- outcome comparison reuses `raw_high_breakout_60d_within_20d_v1` and `evaluate_historical_outcome()`
- Historical Hit Rate uses `summary.historical_hit_rate`, which is `HIT / (HIT + MISS)`
- zero resolved samples display `N/A`, not `0%`
- warm-up is `60` trading bars before observation start
- outcome horizon is `20` trading bars after each observation
- observation unit is `DAILY`
- overlap possible is `True`

The Dashboard uses a read-only SQLite connection (`mode=ro`) to `data/stocks.db`. It does not initialize or migrate the database, fetch Yahoo, write cache rows, add tables, update research semantics, change thresholds, change scanner logic, change signal definitions, change technical formulas, run backtests, run replay, run OOS, or call OpenAI / AI logic.

For the five default symbols and `2018-01-01` to `2025-12-31`, the current run-local expected aggregate is:

```text
total observations = 9716
0/5～5/5 observation counts = 1433, 1906, 2368, 3017, 919, 73
0/5～5/5 Historical Hit Rate = 7.89%, 16.47%, 36.87%, 58.67%, 73.23%, 90.41%
```

## Current Signal

Current Signal is evaluated only from the latest available `TechnicalIndicatorSnapshot`.

After `掃描結果摘要`, the dashboard shows `技術條件明細`.

The stock selector includes all scan-time current technical evaluations that completed as `MATCH` or `NO_MATCH`. A stock does not need to be a matched candidate before its technical condition detail can be inspected. `NOT_EVALUABLE` and `FAILED` are not displayed as complete technical details.

The detail view shows:

- `符合 X / 5 項技術條件`
- beginner-friendly categories: `趨勢`, `成交量`, `動能`, `接近前高程度`
- actual technical values from scan-time `SignalMatch.feature_snapshot`
- V1 thresholds
- PASS / FAIL copied from `SignalMatch.evaluated_conditions`
- neutral gap-to-threshold text
- independent beginner visual bars for volume activity, RSI momentum, and distance to prior 60-day high
- beginner explanations
- developer traceability for `technical_example_v1`, scanner status, and raw metric names

`X / 5` is a factual count only. It is not a score, recommendation, expected return, or future probability.

The three visual bars use separate scales because the metrics have different units:

- volume ratio shows current value vs V1 threshold `1.20`
- RSI shows current value within the standard `0-100` RSI domain and highlights V1 range `50-70`
- distance to prior 60-day high shows current percentage distance, V1 threshold `-5%`, and `0%` as the prior-high reference

The detailed technical condition table remains visible and is not replaced by the visual bars.

The dashboard does not fetch Yahoo, rerun scanner, rerun backtest, rerun replay, or rerun OOS validation when the user changes the technical detail selector.

For a selected candidate, the dashboard shows:

- Latest Trading Date
- Analysis Close
- Signal Status
- condition trace copied from `candidate.signal_match`

The condition trace is not recalculated in the dashboard.

## Historical Replay Signal

Replay signal is displayed as `Signal Snapshot As Of`, not `Current Signal`.

The page shows both:

- Requested Replay Date
- Actual Trading Date

The actual date can differ by symbol because market calendars differ.

Replay signal features come from a technical series rebuilt from price bars on or before the replay date.

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

In Out-of-Sample Validation mode, Historical Hit Rate is always displayed with `Resolved n` for each period. If `Resolved n == 0`, the dashboard displays `N/A`, not `0%`.

The OOS comparison table displays percentage differences as percentage points, for example `+33.78 percentage points`, and does not display relative change in the MVP.

## Historical Context As Of

Replay mode displays `Historical Hit Rate (As Of)` and `Resolved n (As Of)`.

These values are built from point-in-time historical statistics:

- HIT is counted only when its first target-hit date was known by the replay date.
- MISS is counted only when the full trading-bar horizon had completed by the replay date.
- MFE, MAE, and End Return are aggregated only from cases whose full horizon had completed by the replay date.
- Future signal dates are excluded from replay historical context.

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

In Historical Replay, Research Priority reuses `swing_research_rank_v1`, but the rank inputs are point-in-time values only. Post-Replay Outcome is not a rank input.

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

Historical Replay renders post-replay verification as a separate outcome block and a single Replay Outcome Case Chart. The chart can contain future bars after the signal date, but those bars are not used for the replay signal or ranking.

## Walk-Forward Summary

Walk-Forward Replay displays:

- Total Replay Periods
- Periods With Candidates
- Periods Without Candidates
- Unique Candidate Symbols
- Total Candidate Occurrences
- Candidate Period Share
- Post-Replay outcome occurrence counts

It intentionally does not display Walk-Forward Hit Rate, Win Rate, Prediction Accuracy, or Probability.

Candidate Period Share means the share of replay periods with at least one research candidate. It is not future probability.

## Period Timeline

The period timeline shows:

- Replay Date
- Scanned
- MATCH
- NO_MATCH
- NOT_EVALUABLE
- FAILED
- Candidate Symbols

Zero-match periods are preserved and shown as normal periods.

## Period Detail

Selecting a period reuses the Single-Date Historical Replay result UI. The dashboard does not recompute signal logic or historical statistics in the walk-forward layer.

If a period has zero MATCH candidates, the UI shows that no symbols matched for that replay period.

## Candidate Frequency

Candidate Frequency shows repeated candidate occurrences by symbol:

- Symbol
- Candidate Occurrences
- Candidate Period Share
- First Appearance
- Last Appearance
- Longest Consecutive Periods
- Best / Median / Worst Research Priority
- Post-Replay HIT
- Post-Replay MISS
- Post-Replay INCOMPLETE
- Post-Replay NOT_EVALUABLE

The table is occurrence-based and must not be read as independent-sample probability.

## Candidate Set Stability

Candidate Set Stability compares each consecutive pair of replay periods:

- Previous Replay Date
- Current Replay Date
- Previous Candidate Count
- Current Candidate Count
- Shared Candidates
- Candidate Set Similarity
- Candidate Set Turnover

Similarity is Jaccard similarity across candidate symbol sets. Turnover is `1 - similarity`. These values describe candidate-set stability only and are not portfolio turnover or probability.

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

Historical Replay uses `Historical Hit Rate (As Of)` and `Post-Replay Outcome`; it does not use `Replay Probability` or `Prediction Result`.

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
- `swing_research_source_context`
- `swing_research_result_mode`
- `swing_research_replay_date`

No SQLite persistence is added.

## Rerun Safety

Only pressing `執行波段掃描` or `執行 Replay Scan` runs the scanner / replay service and loads prices.

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
