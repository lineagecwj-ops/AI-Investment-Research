# Research Context

## Purpose

Research Context is the structured application/domain boundary for future AI Research Assistant, Research Summary, Export, and Report generation workflows.

The goal is to give future AI workflows deterministic, validated, traceable inputs instead of asking AI to infer meaning from Yahoo raw dictionaries, SQLite rows, Streamlit widget state, chart data, or UI-formatted strings.

## Architecture Boundary

`src/research_context.py` consumes existing normalized domain models:

- `Stock`
- `ResearchReport`
- `HistoricalFinancialSeries`
- `HistoricalResearchReport`

It does not:

- fetch Yahoo Finance data
- query or write SQLite
- read Streamlit state
- call company-name cache helpers
- build charts
- use AI / LLM
- generate Buy / Sell / Hold recommendations, target price, score, rating, or ranking

## Pure Builder Contract

Core builder:

```python
build_research_context(
    *,
    stock: Stock,
    research_report: ResearchReport,
    historical_series: HistoricalFinancialSeries | None = None,
    historical_research_report: HistoricalResearchReport | None = None,
    display_name: str | None = None,
    generated_at: datetime | None = None,
) -> ResearchContext
```

The caller must build `ResearchReport` and `HistoricalResearchReport` before calling this builder. This keeps data acquisition, deterministic interpretation, and context assembly separate.

`generated_at` can be injected for deterministic tests and reproducible exports. If omitted, the builder uses current UTC time. Whole serialized contexts may differ when `generated_at` differs, but evidence IDs, missing-data IDs, observation links, and evidence lineage remain deterministic for the same input data.

## Context Structure

`ResearchContext` contains:

- `symbol`
- `display_name`
- `currency`
- `generated_at`
- `current_snapshot`
- `fundamental_research`
- `historical_financials`
- `historical_research`
- `evidence`
- `observation_links`
- `limitations`
- `missing_data`

Current snapshot is grouped into:

- `CompanyContext`
- `MarketContext`
- `ProfitabilityContext`
- `GrowthContext`
- `FinancialHealthContext`
- `ValuationContext`

Historical financials preserve annual period values, `period_end`, `period_year`, currency, `fetched_at`, and stale-cache status.

## Evidence Model

`EvidenceItem` is per-metric:

- `id`
- `category`
- `metric`
- `value`
- `unit`
- `currency`
- `period_end`
- `period_year`
- `source`
- `source_type`
- `derived_from`
- `note`

Evidence stores raw normalized values, not UI-formatted values.

## Evidence ID Convention

Current source evidence:

```text
current:<metric>
current:return_on_equity
current:forward_pe
current:current_price
```

Historical source evidence:

```text
historical:<metric>:YYYY-MM-DD
historical:revenue:2025-12-31
historical:eps:2024-12-31
```

Historical IDs use `period_end`, not only `period_year`, so fiscal periods such as NVIDIA `2026-01-31` and Apple `2025-09-30` remain unambiguous.

Derived evidence:

```text
derived:52_week_position
derived:revenue_yoy:2025-12-31
derived:eps_yoy:2025-12-31
```

IDs do not use UUIDs, randomness, or `generated_at`.

## Raw vs Derived Evidence

Source evidence has `source_type="source"` and empty `derived_from`.

Derived evidence has `source_type="derived"` and non-empty `derived_from` references to existing evidence IDs.

Current derived evidence:

- `derived:52_week_position`

Historical derived evidence:

- `derived:revenue_yoy:<period_end>`
- `derived:eps_yoy:<period_end>`

Revenue YoY and EPS YoY reuse existing consecutive-year semantics from `research_metrics.py`. EPS YoY is not created when previous EPS is less than or equal to zero.

## Observation Traceability

The context does not modify `ResearchObservation`. Instead, it uses `ObservationEvidenceLink` as an external mapping:

- `id`
- `observation_scope`
- `observation_index`
- `category`
- `metric`
- `evidence_ids`
- `missing_data_ids`

Current examples:

- Forward P/E lower than Trailing P/E links to `current:trailing_pe` and `current:forward_pe`.
- Negative Revenue Growth links to `current:revenue_growth`.
- Negative Earnings Growth links to `current:earnings_growth` and, when present, `current:revenue_growth`.
- Debt greater than Cash links to `current:total_debt` and `current:total_cash`.
- Price below 200-day average links to `current:current_price` and `current:two_hundred_day_average`.

Historical Revenue observations link to available `derived:revenue_yoy:<period_end>` evidence. The derived YoY evidence then links to raw annual Revenue evidence.

Missing EPS observations link to `MissingDataItem` IDs instead of creating fake EPS evidence.

## Missing Data

`MissingDataItem` is structured:

- `id`
- `area`
- `metric`
- `period_end`
- `period_year`
- `reason`
- `impact`
- `source`

Current missing ID:

```text
missing:current:return_on_equity
```

Historical missing ID:

```text
missing:historical:eps:2025-12-31
```

Missing raw values do not create `value=None` source evidence. They are represented by missing-data records.

YoY unavailability is separated from provider missing values. For example, previous EPS less than or equal to zero is recorded as a calculation limitation reason, not as a Yahoo missing value.

## Limitations

`ResearchLimitation` contains:

- `id`
- `category`
- `message`
- `scope`

Global limitations:

- annual historical data only
- no quarterly / TTM historical data
- no FX conversion

Context-specific limitations:

- no historical series
- stale historical data
- missing critical research fields
- insufficient historical periods
- current / historical currency mismatch

Company-summary and MOEA localization limitations are only appropriate when the context receives enough input to know that a fallback happened.

## Currency Semantics

The context preserves provider currency values. It does not perform FX conversion.

If `Stock.currency` and `HistoricalFinancialSeries.currency` are both present and differ, the builder keeps the context and adds `context:currency_mismatch`. It does not raise because cross-source currency differences are a research limitation, not necessarily corrupt data.

## Symbol Validation

The builder validates symbol consistency across:

- `Stock.symbol`
- `ResearchReport.stock.symbol`
- `HistoricalFinancialSeries.symbol`
- `HistoricalResearchReport.series.symbol`

Mismatch raises `ResearchContextError`.

## Serialization

`ResearchContext.to_dict()` returns JSON-safe data:

- `date` becomes `YYYY-MM-DD`
- `datetime` becomes ISO 8601
- `tuple` becomes list
- dataclass instances become dicts
- `None` is preserved

`json.dumps(context.to_dict())` must succeed.

## Validation

The builder validates:

- evidence IDs are non-empty
- evidence IDs are unique
- missing-data IDs are non-empty
- missing-data IDs are unique
- observation links reference existing evidence and missing-data IDs
- derived evidence references existing source evidence
- source evidence does not have `derived_from`
- period `period_end.year` matches `period_year`
- no `NaN`, `+inf`, or `-inf` values exist anywhere in the context

Invalid context raises `ResearchContextError`.

## Historical Highlights

Historical Highlights are excluded by design. They are presentation-level selection from deterministic historical observations. Keeping them out of Research Context avoids duplicated observation data and UI-specific bloat.

## Future AI Boundary

Future AI workflows should consume `ResearchContext.to_dict()` or an equivalent serialized context, not raw provider payloads or UI state.

AI must use `evidence`, `observation_links`, `missing_data`, and `limitations` to identify what supports each observation and what remains unknown.

## No Recommendation Policy

Research Context does not create investment recommendations. It does not introduce Buy / Sell / Hold, target price, score, rating, ranking, or recommendation semantics.
