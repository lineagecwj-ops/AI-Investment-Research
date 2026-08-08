# Historical Case Explorer

## Purpose

Sprint 06 Batch F adds a deterministic Historical Case Explorer for reviewing individual cases from a `HistoricalBacktestReport`.

This layer is a historical case inspection tool. It is not a future prediction model, similar-case probability model, Buy / Sell / Hold recommendation, target price system, scanner ranking, or trading simulator.

## Inputs

The case explorer consumes:

- `HistoricalPriceSeries`
- `HistoricalBacktestReport`
- `HistoricalCaseWindowConfig`

It does not recalculate signal conditions or historical outcomes. Case status comes directly from each `HistoricalBacktestCase.outcome.status`.

## Window Semantics

`HistoricalCaseWindowConfig` is frozen and uses trading-bar counts:

```text
pre_signal_bars = 60
post_signal_bars = 20
```

Both values must be `>= 0`.

The helper `build_case_price_window()` returns actual provider trading bars only:

```text
pre-signal bars + signal bar + post-signal bars
```

For a 60 / 20 window, the maximum length is 81 bars. If earlier or later data is unavailable, the service returns fewer bars and marks:

- `is_window_complete_before=False`
- `is_window_complete_after=False`

It does not forward fill, calendar reindex, weekend fill, holiday fill, interpolate, or create synthetic bars.

## Signal Bar Requirement

The signal date must exist in the price series.

If absent, the service raises `HistoricalCaseDataError`. It does not search for the nearest trading date.

## Relative Trading-Bar Index

Each `HistoricalCasePricePoint` has a `relative_bar_index`:

```text
signal date = 0
previous trading bar = -1
next trading bar = +1
```

A Friday signal followed by a Monday trading session is `+1`, not `+3`.

## Price Basis

The main chart line uses `analysis_close`, which comes from `get_analysis_close(bar)`:

```text
adjusted_close if available else close
```

The raw-high breakout reference and first target hit use raw high basis. The UI explicitly states this distinction so users do not confuse close-based display lines with raw-high outcome triggers.

## Frozen Reference High

`HistoricalCaseView.reference_high` comes from `SignalEvent.reference_high`.

The case explorer does not recalculate prior high from the chart window or future bars. This preserves the reference level known at signal formation time.

## HIT / MISS / INCOMPLETE / NOT_EVALUABLE

`HIT` means the configured historical outcome target occurred inside the configured horizon.

`MISS` means the full horizon was available and the target did not occur.

`INCOMPLETE` means the full no-hit horizon is not available yet.

`NOT_EVALUABLE` means required signal/outcome data was insufficient for evaluation.

`HIT` does not mean profitable trade. `MISS` does not mean losing trade.

## Return Metrics

The case view preserves raw outcome metrics:

- `max_close_return`
- `max_adverse_return`
- `end_of_window_return`

These are close-based historical return metrics. They are not actual trading P&L, exit return, portfolio return, or guaranteed result.

The service keeps raw floats. Formatting and rounding belong to presentation helpers.

## Condition Trace

`HistoricalCaseConditionDetail` is copied from `SignalEvent.evaluated_conditions`.

The explorer does not call `evaluate_signal_conditions()` and does not reinterpret condition status after the fact.

## Streamlit UI

The Streamlit `Historical Cases` tab:

- accepts a single symbol
- uses `technical_example_v1`
- uses `raw_high_breakout_60d_within_20d_v1`
- supports `ALLOW_ALL` and `COOLDOWN`
- accepts an inclusive backtest signal-date range
- runs only after the user presses `建立歷史案例`
- stores the report and case views only in `st.session_state`
- supports status filtering, newest / oldest sorting, relative-bar or actual-date x-axis rendering
- clears only session case results with `清除案例結果`

Changing filters, sorting, chart x-axis, expanders, or case selector does not refetch prices or rerun backtests.

## Chart

The first chart version uses a line chart:

- main line: analysis close
- secondary faint line: raw high
- vertical rule: signal date
- horizontal rule: frozen reference high
- point marker: first target hit for HIT cases only

MISS cases still show the signal date, frozen reference high, horizon context, MFE, MAE, and end return, but they do not show a target-hit marker.

## No Persistence

Batch F does not add SQLite persistence for case views and does not store chart artifacts.

The explorer rebuilds deterministic case views from the price series and backtest report when explicitly requested.
