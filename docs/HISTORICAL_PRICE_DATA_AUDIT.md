# Historical Price Data Audit

## Scope

Sprint 06 Batch A audited Yahoo Finance daily price history for:

- `2330.TW`
- `2454.TW`
- `NVDA`
- `AAPL`
- `6488.TWO`

The audit was read-only and used `yfinance.Ticker(symbol).history(period="max", actions=True)` with both `auto_adjust=False` and `auto_adjust=True`.

## Provider API Decision

The historical price foundation uses `Ticker.history()`, not `yfinance.download()`.

Reasons:

- Stable single-symbol API boundary for the current project architecture.
- Direct support for `period="max"`, `start`, and `end`.
- Avoids the `download()` MultiIndex column shape for Batch A.
- Allows explicit `auto_adjust=False` and `actions=True`.

## Adjustment Strategy

The service uses:

```text
auto_adjust = False
actions = True
```

This preserves raw OHLC, `Adj Close`, `Dividends`, and `Stock Splits`.

Future technical indicators should use `adjusted_close if available else close` through `get_analysis_close()`. This avoids stock split artifacts in price-series analysis while retaining raw OHLC for auditability. The project does not calculate its own adjustment factors in Batch A.

## Yahoo Column Behavior

With `auto_adjust=False`, Yahoo returned:

```text
Open, High, Low, Close, Adj Close, Volume, Dividends, Stock Splits
```

With `auto_adjust=True`, Yahoo returned adjusted OHLC and did not return `Adj Close`:

```text
Open, High, Low, Close, Volume, Dividends, Stock Splits
```

## Timezone Behavior

Daily indexes were timezone-aware:

- Taiwan listed stocks: `Asia/Taipei`
- US listed stocks: `America/New_York`

The domain model stores only `datetime.date` from the provider's local daily index value. It does not convert the timestamp through UTC, so a US daily bar is not shifted to the prior date.

## Live Coverage Snapshot

Audit date: 2026-08-02.

| Symbol | Timezone | Earliest | Latest | Rows | Duplicate Dates | Zero Volume | Negative Volume | NaN Counts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `2330.TW` | `Asia/Taipei` | 2000-01-04 | 2026-07-31 | 6608 | 0 | 109 | 0 | 0 |
| `2454.TW` | `Asia/Taipei` | 2001-07-23 | 2026-07-31 | 6204 | 0 | 72 | 0 | 0 |
| `NVDA` | `America/New_York` | 1999-01-22 | 2026-07-31 | 6923 | 0 | 0 | 0 | 0 |
| `AAPL` | `America/New_York` | 1980-12-12 | 2026-07-31 | 11500 | 0 | 1 | 0 | 0 |
| `6488.TWO` | `Asia/Taipei` | 2014-10-30 | 2026-07-31 | 2859 | 0 | 11 | 0 | 0 |

All audited symbols had finite positive OHLC and adjusted close values in the `auto_adjust=False` result.

## Latest Bars Snapshot

Latest three bars from the audit:

- `2330.TW`: 2026-07-29 close 2200.0, 2026-07-30 close 2205.0, 2026-07-31 close 2425.0.
- `2454.TW`: 2026-07-29 close 3150.0, 2026-07-30 close 3235.0, 2026-07-31 close 3555.0.
- `NVDA`: 2026-07-29 close 190.00999450683594, 2026-07-30 close 195.0399932861328, 2026-07-31 close 200.75.
- `AAPL`: 2026-07-29 close 338.19000244140625, 2026-07-30 close 333.42999267578125, 2026-07-31 close 308.9100036621094.
- `6488.TWO`: 2026-07-29 close 864.0, 2026-07-30 close 778.0, 2026-07-31 close 855.0.

## Split Audit

`AAPL` around its 2020 split:

- `2020-08-31` had `Stock Splits = 4.0`.
- Raw close was `129.0399932861328`.
- Adjusted close was `125.16539001464844`.
- `auto_adjust=True` close matched the adjusted close.

`NVDA` around its 2024 split:

- `2024-06-10` had `Stock Splits = 10.0`.
- Raw close was `121.79000091552734`.
- Adjusted close was `121.57960510253906`.
- `auto_adjust=True` close matched the adjusted close.

This confirms the Batch A strategy: preserve raw OHLC and adjusted close, and use adjusted close for future technical-analysis close semantics.

## Current-Day Partial Bar Policy

Yahoo daily history may include the provider's latest daily row. The Batch A service preserves provider bars as returned and documents that the latest row can be a current-session partial bar if queried during market hours.

Backtest code in future batches should request an explicit `end` date that represents the latest completed session, or apply a market-calendar-aware completed-session policy before slicing. Batch A does not infer exchange market state.

## Known Limitations

- No exchange holiday calendar is used yet.
- No precise current-session completion flag is stored.
- No synthetic weekend or holiday bars are created.
- No forward fill, back fill, or interpolation is performed.
- No corporate-action adjustment factors are calculated by the project.
