# Technical Indicator Foundation

## Purpose

Sprint 06 Batch B establishes deterministic technical features on top of `HistoricalPriceSeries`.

This layer calculates measurements only. It does not produce Buy / Sell / Hold recommendations, target prices, scores, probabilities, historical hit rates, success labels, future returns, scanners, charts, or backtests.

## Technical Feature vs Signal

Indicators in this layer are factual features, such as moving averages, RSI, MACD, ATR, volume ratio, prior highs, returns, and distance to prior highs.

Interpretation thresholds and signal rules, such as RSI overbought / oversold or breakout signal definitions, belong to a future signal layer.

## Analysis Price

Close-based indicators use `get_analysis_close(bar)` from `historical_price_service.py`:

```text
adjusted_close if available else close
```

This applies to SMA, EMA, RSI, MACD, return features, return volatility, and close-based distance calculations.

## Raw High / Low Basis

Yahoo `auto_adjust=False` preserves raw OHLC and adjusted close. Batch B does not calculate unsupported adjusted high / low values.

ATR, rolling highs, rolling lows, prior highs, and prior lows use raw high / low. ATR true range uses raw high, raw low, and previous raw close so the true-range calculation stays on a consistent OHLC basis.

Because dividend adjustment is reflected in adjusted close but not raw high / low, ATR and high / low range features can have a basis difference from close-only adjusted features. This is documented instead of hidden by a project-generated adjustment factor.

## No Look-Ahead

Any technical snapshot for date `t` may use only bars with:

```text
bar.trading_date <= t
```

`build_technical_indicator_snapshot(series, as_of_date)` first calls `slice_price_series_as_of()` and then calculates features from the sliced bars. If `as_of_date` is not a trading date, the snapshot uses the latest available trading bar before or on that date. If `as_of_date` is before the earliest bar, it returns `None`.

Full-series generation uses only causal operations: rolling windows, `ewm(adjust=False)`, and `shift(1)` for prior-window features. It does not use centered windows, backfill, or future shifts.

## SMA

SMA windows are 5, 10, 20, 60, 120, and 200 trading bars.

Formula:

```text
mean(latest N analysis_close values including current bar)
```

Warm-up: fewer than `N` bars returns `None`. Partial-window averages are not emitted.

## EMA

EMA windows are 12 and 26 trading bars.

Formula uses pandas-compatible exponential moving average:

```text
span = N
adjust = False
```

Warm-up: the recursive EMA is calculated causally from the first close, but values are considered usable only after at least `N` bars. Earlier values are emitted as `None`.

## RSI

RSI 14 uses Wilder RSI on analysis-close changes.

Warm-up: RSI requires 14 price changes, so at least 15 trading bars are needed.

Edge cases:

- average loss = 0 and average gain > 0: RSI = 100
- average gain = 0 and average loss > 0: RSI = 0
- both average gain and average loss are 0: RSI = 50

## MACD

MACD uses:

```text
EMA12 - EMA26
```

Signal uses EMA9 of the available MACD values with `adjust=False`.

Warm-up:

- EMA12 requires 12 bars.
- EMA26 requires 26 bars.
- MACD requires both EMA12 and EMA26.
- MACD signal requires 9 MACD values.
- MACD histogram requires both MACD and signal.

## ATR

ATR 14 uses raw OHLC basis.

True range:

```text
max(
  high - low,
  abs(high - previous raw close),
  abs(low - previous raw close)
)
```

For the first bar, true range is `high - low` because no previous close exists. ATR uses Wilder smoothing over 14 true-range values.

`atr_14_pct` is:

```text
atr_14 / analysis_close
```

when `analysis_close > 0`.

## Volume SMA / Ratio

`volume_sma_20` is the average of the latest 20 volume values including the current bar. Zero volume is valid. If any volume in the 20-bar window is missing, the value is `None`.

`volume_ratio_20` is:

```text
current volume / previous 20 trading bars average volume
```

The current bar is excluded from the denominator. If the previous 20-volume average is zero or missing, the ratio is `None`.

## Returns

Return features are 5D, 20D, and 60D:

```text
current analysis_close / analysis_close N trading bars ago - 1
```

They use trading-bar counts, not calendar days. Future returns are intentionally not part of this model.

## Prior Highs / Lows

Rolling high / low fields include the current bar.

Prior high / low fields exclude the current bar through `shift(1)`:

- `prior_high_20d`
- `prior_high_60d`
- `prior_high_252d`
- `prior_low_20d`
- `prior_low_60d`

This supports future factual questions such as whether today's close is above the previous 60 trading bars' high.

## Distance Features

Distance to prior highs is:

```text
analysis_close / prior_high - 1
```

Values are not clamped. A negative value means the close is below the prior high; a positive value means it is above the prior high.

`position_in_prior_60d_range` is:

```text
(analysis_close - prior_60d_low) / (prior_60d_high - prior_60d_low)
```

It is not clamped. If the range denominator is zero, the value is `None`.

## 52-Week Approximation

Batch B defines 52-week technical features as 252 trading bars. This is a practical approximation, not an exchange-calendar exact one-year date range.

## Warm-Up Semantics

Insufficient history produces `None` for the affected feature only. A new listing with 30 bars can have SMA20 but still have `None` for SMA60, SMA120, and SMA200.

## Missing Data Behavior

No close, volume, high, or low values are interpolated, forward filled, or backfilled.

If a feature's required window includes missing data, that feature is `None`. Other features in the same snapshot may still be available.

All numeric outputs must be finite. NaN or infinity is converted to `None`.

## Causal Vectorization

The full-series implementation may use vectorized calculations when the operation is causal. Allowed examples include rolling windows, `ewm(adjust=False)`, and `shift(1)`.

The test suite locks full-series vs as-of consistency and verifies that appending future extreme bars does not change past snapshots.

## Partial Current Bar Limitation

Batch A documents that the latest Yahoo daily bar may be a current-session partial bar. Batch B can calculate a latest snapshot, but latest technical values may be provisional if the latest source bar is not a completed trading session.

Future backtest code should avoid using provisional bars unless a completed-session policy is supplied.

## No Persistence

Batch B does not create a SQLite technical indicator table. Technical features are deterministic from historical price bars and can be rebuilt.

## Future Signal Layer

A future signal layer may define thresholds, factual conditions, or named signal snapshots. That layer must remain separate from these raw technical measurements.

## Future Backtest Layer

A future backtest layer may define outcomes using future bars after the feature date. Future outcome data must not enter `TechnicalIndicatorSnapshot`.
