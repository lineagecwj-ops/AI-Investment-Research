# Historical Fundamental Data Audit

## Scope

Audit date: 2026-08-02

Provider: Yahoo Finance through `yfinance.Ticker`

Annual source objects:

- `income_stmt`
- `cashflow`
- `balance_sheet`

Representative symbols:

- `2330.TW`
- `2454.TW`
- `NVDA`
- `AAPL`

This audit supports Sprint 03 Batch A. It documents representative Yahoo annual financial statement availability and the MVP normalized fields used by the project.

## Income Statement Aliases

| Project field | Yahoo row label priority | Value type |
| --- | --- | --- |
| `revenue` | `Total Revenue` | numeric amount |
| `gross_profit` | `Gross Profit` | numeric amount |
| `operating_income` | `Operating Income` | numeric amount |
| `net_income` | `Net Income`, `Net Income Common Stockholders` | numeric amount |
| `eps` | `Diluted EPS`, `Basic EPS` | numeric per-share value |

Alias lookup is deterministic. If multiple aliases exist, the first alias in the priority list wins.

## Cashflow Aliases

| Project field | Yahoo row label priority | Value type |
| --- | --- | --- |
| `operating_cash_flow` | `Operating Cash Flow` | numeric amount |
| `capital_expenditure` | `Capital Expenditure` | numeric amount |
| `free_cash_flow` | `Free Cash Flow` | numeric amount |

In the live audit, `Capital Expenditure` was negative for all representative symbols. When Yahoo does not provide `Free Cash Flow`, the MVP derives:

```text
free_cash_flow = operating_cash_flow + capital_expenditure
```

If either input is missing or non-finite, derived `free_cash_flow` is `None`.

## Balance Sheet Aliases

| Project field | Yahoo row label priority | Value type |
| --- | --- | --- |
| `total_assets` | `Total Assets` | numeric amount |
| `total_debt` | `Total Debt` | numeric amount |
| `total_equity` | `Stockholders Equity`, `Total Equity Gross Minority Interest` | numeric amount |
| `cash_and_cash_equivalents` | `Cash And Cash Equivalents`, `Cash Cash Equivalents And Short Term Investments` | numeric amount |

## Representative Availability

| Symbol | Currency context | Raw annual columns | Normalized usable periods | Period years | Notes |
| --- | --- | ---: | ---: | --- | --- |
| `2330.TW` | `TWD` | 5 | 4 | 2022, 2023, 2024, 2025 | Oldest raw column had no modeled MVP values in validation output. |
| `2454.TW` | `TWD` | 5 | 5 | 2021, 2022, 2023, 2024, 2025 | 2021 was partial in validation output; some fields were `N/A`. |
| `NVDA` | `USD` | 5 | 4 | 2023, 2024, 2025, 2026 | Oldest raw column had no modeled MVP values in validation output. |
| `AAPL` | `USD` | 5 | 4 | 2022, 2023, 2024, 2025 | Oldest raw column had no modeled MVP values in validation output. |

## Representative Row Label Audit

All four symbols exposed the following annual row labels in the current yfinance live audit:

- Income statement: `Total Revenue`, `Gross Profit`, `Operating Income`, `Net Income`, `Net Income Common Stockholders`, `Diluted EPS`, `Basic EPS`, `Cost Of Revenue`
- Cashflow: `Operating Cash Flow`, `Capital Expenditure`, `Free Cash Flow`
- Balance sheet: `Total Assets`, `Total Debt`, `Stockholders Equity`, `Total Equity Gross Minority Interest`, `Cash And Cash Equivalents`, `Cash Cash Equivalents And Short Term Investments`

`Cost Of Revenue` was audited but is not stored in the Sprint 03 Batch A MVP model.

## Calculation Rules

Margins are calculated from historical annual statement values, not from Yahoo snapshot margin fields:

```text
gross_margin = gross_profit / revenue
operating_margin = operating_income / revenue
net_margin = net_income / revenue
```

If revenue is missing, zero, or non-finite, or if the numerator is missing or non-finite, the margin is `None`.

## Period Convention

Yahoo annual statement columns are normalized to `period_end` dates. `fiscal_year` is derived from `period_end.year`.

Normalized periods are sorted oldest to newest. This supports future trend rendering without relying on Yahoo column order.

Periods with no modeled MVP field values are filtered out. Partial periods with at least one modeled value are retained.

## Currency Semantics

Historical statement values use Yahoo financial statement currency context. The MVP uses `financialCurrency` when available and falls back to `currency`.

No FX conversion is performed. Raw historical amounts should not be directly compared across currencies.

## SQLite Persistence

Historical fundamentals are stored separately from the current stock snapshot:

- Table: `historical_financials`
- Primary key: `(symbol, period_end)`
- Refresh timestamp: `fetched_at`
- Upsert behavior: non-destructive upsert by `symbol + period_end`

If a future Yahoo response omits an older period, Sprint 03 Batch A does not delete existing rows.

## Cache Policy

Historical fundamentals use an independent 7-day TTL.

Current stock snapshot cache remains 24 hours in the `stocks` table.

If the historical cache is fresh, callers receive SQLite data. If cache is missing or expired, the service refreshes from Yahoo, normalizes statements, and upserts rows. If Yahoo refresh fails and stale cache exists, the service returns stale data with `is_stale=True` and logs the refresh failure.

## Derived YoY Metrics

Sprint 03 Batch A adds deterministic helper functions only:

- Revenue YoY growth
- EPS YoY growth
- Net Income YoY growth through the generic field helper

Formula:

```text
(current - previous) / abs(previous)
```

If previous revenue or net income is missing or zero, growth is `None`. EPS YoY requires previous EPS to be positive; previous EPS less than or equal to zero returns `None`.

## Known Limitations

- Yahoo Finance row labels and annual coverage are provider-controlled and can change.
- Annual data is modeled first; quarterly data is not persisted in this batch.
- The MVP does not build historical charts, trend classification, scoring, AI interpretation, recommendation language, FX conversion, TTM, or competitor comparison.
- `financialCurrency` / `currency` gives currency context, not audited accounting policy detail.
