# Fundamental Data Audit

## Scope

Audit date: 2026-08-01

Provider: Yahoo Finance through `yfinance.Ticker(symbol).info`

Representative symbols:

- `2330.TW` — Taiwan Semiconductor Manufacturing Company Limited
- `2454.TW` — MediaTek Inc.
- `NVDA` — NVIDIA Corporation
- `AAPL` — Apple Inc.

This audit supports Sprint 02 Batch A. It is a representative availability check, not a guarantee that every Yahoo Finance symbol has every field.

## Field Dictionary

| Research area | Yahoo raw key | Project field | Meaning | Value type observed | Representative availability |
| --- | --- | --- | --- | --- | --- |
| Company Overview | `longBusinessSummary` | `company_summary` | Company business description | `str` | Present for all 4 symbols |
| Company Overview | `longName` / `shortName` | `company_name` | Yahoo company name | `str` | Present for all 4 symbols |
| Price | `currentPrice` / `regularMarketPrice` | `current_price` | Current market price | `float` | Present for all 4 symbols |
| Price | `currency` | `currency` | Trading currency | `str` | Present for all 4 symbols |
| Valuation | `marketCap` | `market_cap` | Market capitalization | `int` | Present for all 4 symbols |
| Valuation | `trailingPE` | `trailing_pe` | Trailing P/E ratio | `float` | Present for all 4 symbols |
| Valuation | `forwardPE` | `forward_pe` | Forward P/E ratio | `float` | Present for all 4 symbols |
| Valuation | `trailingEps` | `trailing_eps` | Trailing EPS | `float` | Present for all 4 symbols |
| Valuation | `priceToBook` | `price_to_book` | Price-to-book ratio | `float` | Present for all 4 symbols |
| Profitability | `returnOnEquity` | `return_on_equity` | Return on equity | `float` | Present for all 4 symbols |
| Profitability | `grossMargins` | `gross_margin` | Gross margin | `float` | Present for all 4 symbols |
| Profitability | `operatingMargins` | `operating_margin` | Operating margin | `float` | Present for all 4 symbols |
| Profitability | `profitMargins` | `net_margin` | Net profit margin | `float` | Present for all 4 symbols |
| Growth | `revenueGrowth` | `revenue_growth` | Revenue growth | `float` | Present for all 4 symbols |
| Growth | `earningsGrowth` | `earnings_growth` | Earnings growth | `float` | Present for all 4 symbols |
| Growth | `earningsQuarterlyGrowth` | Not stored | Quarterly earnings growth, overlaps current `earningsGrowth` need | `float` | Present for all 4 symbols |
| Financial Health | `totalCash` | `total_cash` | Total cash | `int` | Present for all 4 symbols |
| Financial Health | `totalDebt` | `total_debt` | Total debt | `int` | Present for all 4 symbols |
| Financial Health | `debtToEquity` | `debt_to_equity` | Debt-to-equity ratio | `float` | Present for all 4 symbols |
| Financial Health | `operatingCashflow` | `operating_cash_flow` | Operating cash flow | `int` | Present for all 4 symbols |
| Financial Health | `freeCashflow` | `free_cash_flow` | Free cash flow | `int` | Present for all 4 symbols |
| Market Position | `fiftyTwoWeekHigh` | `fifty_two_week_high` | 52-week high price | `float` | Present for all 4 symbols |
| Market Position | `fiftyTwoWeekLow` | `fifty_two_week_low` | 52-week low price | `float` | Present for all 4 symbols |
| Market Position | `fiftyDayAverage` | `fifty_day_average` | 50-day average price | `float` | Present for all 4 symbols |
| Market Position | `twoHundredDayAverage` | `two_hundred_day_average` | 200-day average price | `float` | Present for all 4 symbols |
| Classification | `sector` | `sector` | Yahoo sector classification | `str` | Present for all 4 symbols |
| Classification | `industry` | `industry` | Yahoo industry classification | `str` | Present for all 4 symbols |

## Representative Coverage

All audited fields above were present for `2330.TW`, `2454.TW`, `NVDA`, and `AAPL` during the 2026-08-01 live audit. None of the four representative stocks showed missing values for the selected fields.

However, Yahoo Finance coverage is provider-controlled and may vary by market, symbol type, ETF, index, newly listed company, or temporary provider issue. All new fundamental fields are therefore stored as nullable project fields.

## Validation Snapshot

| Symbol | Fields with values | Fields as N/A |
| --- | --- | --- |
| `2330.TW` | `company_summary`, `gross_margin`, `operating_margin`, `net_margin`, `revenue_growth`, `earnings_growth`, `total_cash`, `total_debt`, `debt_to_equity`, `operating_cash_flow`, `free_cash_flow`, `price_to_book`, `fifty_two_week_high`, `fifty_two_week_low`, `fifty_day_average`, `two_hundred_day_average` | None in audited fields |
| `2454.TW` | `company_summary`, `gross_margin`, `operating_margin`, `net_margin`, `revenue_growth`, `earnings_growth`, `total_cash`, `total_debt`, `debt_to_equity`, `operating_cash_flow`, `free_cash_flow`, `price_to_book`, `fifty_two_week_high`, `fifty_two_week_low`, `fifty_day_average`, `two_hundred_day_average` | None in audited fields |
| `NVDA` | `company_summary`, `gross_margin`, `operating_margin`, `net_margin`, `revenue_growth`, `earnings_growth`, `total_cash`, `total_debt`, `debt_to_equity`, `operating_cash_flow`, `free_cash_flow`, `price_to_book`, `fifty_two_week_high`, `fifty_two_week_low`, `fifty_day_average`, `two_hundred_day_average` | None in audited fields |
| `AAPL` | `company_summary`, `gross_margin`, `operating_margin`, `net_margin`, `revenue_growth`, `earnings_growth`, `total_cash`, `total_debt`, `debt_to_equity`, `operating_cash_flow`, `free_cash_flow`, `price_to_book`, `fifty_two_week_high`, `fifty_two_week_low`, `fifty_day_average`, `two_hundred_day_average` | None in audited fields |

## Known Limitations

- `yfinance.Ticker.info` is a convenient provider surface, but Yahoo can change keys, omit values, or return malformed values.
- The current project model keeps only a latest snapshot in SQLite; it does not yet store historical fundamentals.
- Price data and fundamental data currently share the same 24-hour cache TTL. Future batches may need different freshness policies.
- Cash flow, debt, and cash values are stored in the currency/context returned by Yahoo Finance; cross-market comparisons need currency awareness.
- No AI analysis, buy/sell recommendation, valuation judgement, or scoring is attached to these fields.
