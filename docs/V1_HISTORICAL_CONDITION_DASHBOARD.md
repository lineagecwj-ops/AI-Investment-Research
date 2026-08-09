# V1 Historical Condition Diagnostics Dashboard

## Purpose

The `V1 歷史條件診斷` dashboard integrates the completed Batch 1 diagnostics and Batch 2 outcome comparison into the existing Streamlit `Swing Research` page.

This batch is presentation and UX integration only. It does not add new research semantics.

## Beginner-Facing Structure

The primary UI is Traditional Chinese-first and conclusion-first:

- `V1 條件有效性總覽`
- `哪些條件最常造成差異`
- `哪些 V1 條件本來就比較難符合？`
- collapsed `進階研究資訊`

The top explanation says the dashboard compares historical samples with different numbers of matched V1 technical conditions and checks whether they broke the prior 60-day high within the following 20 trading days.

The safety note says this is descriptive historical statistics, not future probability or a buy recommendation.

## Run Behavior

The section has its own explicit submit button:

```text
執行 V1 歷史診斷
```

Changing selectors, display scope, expanders, charts, or tables does not rerun diagnostics.

The result is stored in Streamlit session state:

- `historical_condition_dashboard_payload`
- `historical_condition_dashboard_fingerprint`
- `historical_condition_dashboard_last_error`
- `historical_condition_dashboard_error_details`

If controls change after a run, the UI shows a stale-result warning and waits for another explicit submit.

## Data Source

The dashboard reads local historical prices from:

```text
data/stocks.db
```

The connection uses SQLite URI `mode=ro`. The dashboard does not initialize, migrate, write, refresh, or clean the database.

If a symbol has no local historical price cache, the UI shows a beginner-friendly error and keeps technical details in a collapsed expander.

## Research Contract

The dashboard reuses existing services:

- `HistoricalConditionDiagnosticsService`
- `compare_historical_condition_outcomes()`
- `prepare_diagnostic_research_series()`
- `build_diagnostic_technical_series()`

The deterministic window contract is:

- warm-up before observation window: `60` trading bars
- observation unit: `DAILY`
- default observation window: `2018-01-01` through `2025-12-31`
- outcome horizon: `20` trading bars
- overlap possible: `True`

Historical Hit Rate is always read from Batch 2 `summary.historical_hit_rate`.

```text
Historical Hit Rate = HIT / (HIT + MISS)
```

`INCOMPLETE` and `NOT_EVALUABLE` are displayed but excluded from the denominator. If resolved samples are zero, the UI displays `N/A`, not `0%`.

## Scope Boundaries

This dashboard does not change:

- V1 signal definition
- V1 thresholds
- PASS / FAIL semantics
- dynamic scale semantics in technical detail visuals
- scanner logic
- signal definitions
- technical formulas
- backtest
- Historical Replay
- Walk-Forward Replay
- OOS
- database schema or database content
- OpenAI / AI logic
- V1.1 or V2

## Default Live Baseline

For:

```text
2330.TW, 0050.TW, 2337.TW, 2404.TW, 2454.TW
2018-01-01 through 2025-12-31
```

The current aggregate run-local baseline is:

```text
total observations = 9716
evaluated observations = 9716
0/5～5/5 observation counts = 1433, 1906, 2368, 3017, 919, 73
0/5～5/5 Historical Hit Rate = 7.89%, 16.47%, 36.87%, 58.67%, 73.23%, 90.41%
```

The current 4/5 missing-condition outcome rows include:

```text
距離前 60 日高點 = 64.67% / n=634
20 日成交量比率 = 89.12% / n=193
RSI 14 日相對強弱指標 = 98.84% / n=86
20 日均線高於 60 日均線 = 100.00% / n=6
股價高於 20 日均線 = N/A / n=0
```

The beginner dashboard presents these rows in canonical V1 condition order, not hit-rate order.
