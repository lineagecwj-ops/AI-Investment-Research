# Historical Price Foundation

## Purpose

Sprint 06 Batch A establishes the daily historical price foundation for future quantitative swing research.

This layer stores normalized daily OHLCV data and provides chronological, no-look-ahead helpers. It does not implement technical indicators, signals, outcomes, backtests, charts, scanners, AI price predictions, or historical hit-rate calculations.

## Domain Model

`HistoricalPriceBar` is a frozen dataclass with:

- `symbol`
- `trading_date`
- raw `open`, `high`, `low`, `close`
- `adjusted_close`
- `volume`
- optional `dividends`
- optional `stock_splits`

The identity of a daily price bar is:

```text
symbol + trading_date
```

`HistoricalPriceSeries` is a frozen dataclass with:

- `symbol`
- `currency`
- chronological `bars`
- timezone-aware UTC `fetched_at`
- `is_stale`
- `source`

The domain model never stores a pandas DataFrame.

## Provider Boundary

`src/historical_price_service.py` owns Yahoo Finance access.

The selected API is:

```text
yfinance.Ticker(symbol).history(...)
```

Default full-history fetch:

```text
period="max", auto_adjust=False, actions=True
```

Explicit range fetch:

```text
start=<inclusive date>, end=<exclusive date passed to Yahoo>
```

The public service API defines both `start` and `end` as inclusive dates. The adapter converts inclusive `end` to Yahoo's exclusive `end` by adding one calendar day.

## Daily OHLCV Semantics

The service stores only provider-returned trading bars. It does not create bars for weekends, holidays, or missing calendar days.

The service does not:

- forward fill prices
- back fill prices
- interpolate OHLC
- fill missing volume with `0`
- invent holiday bars

## Adjustment Strategy

The foundation preserves raw OHLC and `adjusted_close`.

Future technical indicators should use:

```python
get_analysis_close(bar)
```

The contract is:

```text
adjusted_close if available else close
```

This avoids split-related artifacts in close-based technical analysis while keeping raw OHLC auditable.

## SQLite

`initialize_database()` creates `historical_prices`:

```text
symbol TEXT NOT NULL
trading_date TEXT NOT NULL
open REAL
high REAL NOT NULL
low REAL NOT NULL
close REAL NOT NULL
adjusted_close REAL
volume INTEGER
dividends REAL
stock_splits REAL
currency TEXT
fetched_at TEXT NOT NULL
PRIMARY KEY(symbol, trading_date)
```

The database also creates `historical_price_fetch_state`:

```text
symbol TEXT PRIMARY KEY
full_history_fetched INTEGER NOT NULL DEFAULT 0
earliest_date TEXT
latest_date TEXT
fetched_at TEXT NOT NULL
```

Migrations are additive. Existing data is not deleted.

## Cache TTL

Daily historical prices use an independent cache TTL:

```text
12 hours
```

Reasoning:

- Daily bars update more frequently than annual fundamentals.
- Daily bars do not need the same short 24-hour current snapshot semantics.
- A 12-hour TTL gives a practical MVP refresh cadence without introducing exchange-calendar logic in Batch A.

Future work can replace simple TTL with market-calendar-aware freshness.

## Coverage Completeness

Freshness and coverage are separate.

`historical_price_fetch_state` records whether full history has been fetched and what date range is locally covered.
TTL freshness is evaluated from the requested `historical_prices` rows themselves, using the oldest `fetched_at` among returned bars. This prevents a partial refresh from making older cached coverage appear fresh.

If the caller asks for `2018-01-01` through `2026-07-31`, a fresh cache containing only `2022-01-01` through `2026-07-31` does not satisfy the request.

If `start=None`, the service treats the request as default full history and requires `full_history_fetched=True` before using cache.

## Stale Fallback

If Yahoo refresh fails:

- return stale cache with `is_stale=True` when the requested range is available locally
- raise `HistoricalPriceSourceError` or `HistoricalPriceDataError` when no usable cache exists

Raw provider tracebacks are not intended for Dashboard presentation.

## Range Semantics

Public API:

```python
get_historical_prices(symbol, start=None, end=None, force_refresh=False)
```

Semantics:

- `symbol` is normalized by `normalize_stock_symbol()`
- `start` is inclusive
- `end` is inclusive
- `start=None` requests default full history
- `end=None` means no upper bound in the domain request

Database reads apply range filters in SQL, not in the UI.

## Upsert Behavior

Historical price rows use non-destructive upsert by `(symbol, trading_date)`.

If local cache has 2020-2026 and a later provider refresh only returns 2021-2026, the 2020 rows are not deleted.

## Trading-Date Semantics

Yahoo daily indexes can be timezone-aware. The service stores only the provider-local trading date as `datetime.date`.

It does not convert daily timestamps through UTC, which avoids shifting US daily bars to the prior date.

## No Look-Ahead

The helper:

```python
slice_price_series_as_of(series, as_of_date)
```

returns only bars with:

```text
trading_date <= as_of_date
```

This is the Batch A foundation for future chronological backtests.

## Recent Trading Bars

The helper:

```python
get_recent_bars(series, end_date, count)
```

returns the most recent `count` actual trading bars up to `end_date`.

It does not use calendar-day slicing.

## Corporate Actions

The service preserves Yahoo's `Dividends` and `Stock Splits` fields when available.

Batch A does not perform corporate-action research or calculate adjustment factors.

## Data Quality

Rows are retained only when:

- `high`, `low`, and `close` are finite and positive
- `open`, when present, is finite and positive
- `adjusted_close`, when present, is finite and positive
- `high >= low`
- `high >= open` and `low <= open` when `open` exists
- `high >= close` and `low <= close`
- `volume` is not negative

Volume `0` is allowed because the live audit found zero-volume rows in Yahoo historical data.

String numerics, bools, NaN, and infinity do not enter the domain model.

## Duplicate Dates

The service enforces one domain bar per `symbol + trading_date`.

Duplicate provider dates are handled deterministically:

- identical duplicate rows collapse
- conflicting duplicate rows keep the last provider row and record a quality issue

The service does not randomly keep duplicates.

## Current-Day Partial Bar Limitation

Batch A does not store `is_complete`, because Yahoo daily history does not provide a reliable exchange-state field in the audited API shape.

Future backtest code should avoid treating the latest provider bar as completed unless the caller supplies a completed-session `end` date or a market-calendar-aware policy is added.

## Future Layers

Future technical indicator layer:

- may use `get_analysis_close()`
- must preserve no-look-ahead behavior
- must count trading bars, not calendar days

Future backtest layer:

- must define outcomes from future data only after signal date `t`
- must not use future prices or unannounced fundamentals to form features at `t`
- must present historical hit rate as historical hit rate, not future probability, unless validation and calibration are implemented.
