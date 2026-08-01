# Historical Trend Dashboard

## Scope

Historical Trends is a Streamlit presentation layer for annual historical fundamentals.

It uses the `HistoricalFinancialSeries` and `HistoricalFinancialPeriod` models created by the historical fundamentals service. It does not add AI / LLM analysis, recommendation language, technical analysis, quarterly analysis, TTM, FX conversion, competitor benchmarking, valuation percentile, or trend classification.

## Page Structure

The page is available as `Historical Trends` in the Streamlit Dashboard.

Current sections:

1. Historical overview
2. Revenue（營收）Trend
3. Earnings（獲利）Trend
4. Margins（利潤率趨勢）
5. Cash Flow（現金流趨勢）
6. Financial Position（財務結構）
7. Historical Table（完整年度資料）

The page supports single-symbol research first. It stores the selected current stock snapshot, historical series, and query failures in `st.session_state` so normal reruns, expanders, and tab interaction do not immediately repeat Yahoo provider requests.

## Historical Metrics

Revenue:

- Revenue
- Revenue YoY

Earnings:

- Net Income
- EPS
- EPS YoY

Margins:

- Gross Margin
- Operating Margin
- Net Margin

Cash Flow:

- Operating Cash Flow
- Capital Expenditure
- Free Cash Flow

Financial Position:

- Total Assets
- Total Debt
- Total Equity
- Cash and Cash Equivalents

Complete table:

- Period End
- Revenue
- Revenue YoY
- Gross Profit
- Operating Income
- Net Income
- EPS
- EPS YoY
- Gross Margin
- Operating Margin
- Net Margin
- Operating Cash Flow
- Capital Expenditure
- Free Cash Flow
- Total Assets
- Total Debt
- Total Equity
- Cash

## Period End Semantics

Historical periods come from Yahoo Finance annual financial statement columns. The project normalizes those columns to `period_end`.

`period_year` is derived from the year component of `period_end`. It is not official fiscal-year metadata.

The UI labels periods as:

```text
FY ending YYYY-MM-DD
```

This is important for companies such as NVIDIA and Apple, where annual fiscal periods may end on dates such as `2026-01-31` or `2025-09-30`, not `12/31`.

## YoY Policy

YoY is calculated by `research_metrics.py`, not by `app.py`.

Revenue YoY and EPS YoY are shown only when adjacent periods have consecutive `period_year` values. If the prior period is missing, the current year is not consecutive, or the required values are missing, YoY displays as `N/A`.

The first available period always has `N/A` YoY because there is no prior period in the displayed series.

## Missing Data Policy

Missing values display as `N/A`.

The dashboard does not:

- Fill missing values with `0`
- Render raw Python `None`
- Render `NaN`
- Self-calculate EPS when Yahoo Finance does not provide EPS
- Draw missing YoY as `0%`

When EPS is missing for a period, the page displays a note that Yahoo Finance currently does not provide EPS for that period.

When an entire metric group has insufficient data, the page shows:

```text
目前可取得的歷史資料不足，暫不顯示趨勢。
```

## CapEx Negative Sign Explanation

Yahoo Finance commonly reports `Capital Expenditure` as a negative value because it represents cash outflow.

The UI explains that capital expenditure usually means spending on long-term assets such as plants, equipment, or infrastructure. A value such as `-100B` should not be read as a company losing `100B`.

The dashboard does not change Batch A Free Cash Flow logic. If Yahoo provides direct `Free Cash Flow`, the service uses that value. If future data requires derived FCF, that derivation remains owned by `historical_financial_service.py`.

## Currency Policy

Historical financial amounts preserve Yahoo Finance currency context.

The dashboard displays currency with compact values, for example:

```text
TWD 1.25T
USD 85.40B
```

No FX conversion is performed. The page does not rank or compare values across stocks or currencies.

## No Trend Classification Policy

This Batch only presents historical values, YoY values, visible period labels, and missing-data context.

It does not automatically produce words such as:

- improving
- deteriorating
- strong
- weak
- healthy
- unhealthy
- good
- bad

It also does not produce Buy / Sell / Hold, target price, overall score, or recommendation text.

## Implementation Boundaries

`app.py` owns Streamlit widgets, layout, native charts, and session state.

`src/dashboard.py` owns Historical Trends presentation helpers:

- Historical overview display
- Cache status display text
- Missing-data notes
- Formatted section rows
- Formatted complete table rows
- Chart-ready numeric rows
- Period End / currency / EPS / YoY formatting

`src/historical_financial_service.py` owns Yahoo annual statement retrieval, row aliases, margin calculation, FCF source / derivation, period normalization, and 7-day historical cache integration.

`src/database.py` owns SQLite persistence.

## Known Limitations

- Yahoo Finance row availability can change.
- Annual data only; quarterly, TTM, and fiscal-calendar metadata are not modeled.
- `period_year` is derived from `period_end` and is not a provider-supplied formal fiscal year label.
- Streamlit native charts are intentionally simple and use raw numeric values; formatted labels are provided in tables.
- Historical cache freshness is exposed at series level, based on the latest cached row timestamp.
- The page does not interpret whether a visible trend is favorable or unfavorable.
