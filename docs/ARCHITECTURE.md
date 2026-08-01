# AI-Investment-Research Architecture

## Version

v0.9

---

# Current Architecture

```
                  Core Services
                       │
             ┌─────────┴─────────┐
             │                   │
         Console UI         Streamlit UI
         src/main.py            app.py
             │                   │
             └─────────┬─────────┘
                       │
                       ▼
               stock_service.py
                       │
            ┌──────────┴──────────┐
            │                     │
       database.py          Yahoo Finance API
            │
            └── SQLite stock cache

watchlist_service.py
    └── JSON watchlist

dashboard.py
    └── Dashboard presentation helpers
    └── Historical Trends presentation builders and display formatters

research_service.py
    └── Deterministic research interpretation and observations

historical_research_service.py
    └── Deterministic historical trend interpretation and research checklists

historical_interpretation_presentation.py
    └── Historical Interpretation highlights, grouping, and checklist presentation helpers

research_context.py
    └── Structured Research Context builder for AI / export / report inputs

research_glossary.py
    └── Beginner research term glossary for Research UI

company_name_service.py
    └── Taiwan official company name localization + JSON cache

company_summary_service.py
    └── Presentation-only company summary localization + JSON cache

models.py
    └── Stock
    └── HistoricalFinancialPeriod
    └── HistoricalFinancialSeries

research_metrics.py
    └── Deterministic research metric helpers

historical_financial_service.py
    └── Yahoo annual financial statement normalization + historical fundamentals service

symbol_utils.py
    └── Stock symbol normalization
```

---

## Responsibilities

### main.py

Responsibilities:

- Program entry point
- Get user input
- Control application flow
- Display results
- Console menu integration

---

### app.py

Responsibilities:

- Streamlit application entry point
- Dashboard page layout and widgets
- Session state for keeping query results across Streamlit reruns
- User-friendly Streamlit messages for stock query and Watchlist errors
- Reuse existing core services instead of directly accessing Yahoo Finance, SQLite, or JSON

---

### dashboard.py

Responsibilities:

- Format Stock values for dashboard display
- Build comparison table rows
- Run batch stock lookup with partial failure handling
- Keep dashboard presentation logic testable outside Streamlit widget callbacks
- Use `company_name_service.py` for presentation-only company display names
- Provide reusable display formatters for percentage, ratio, price, currency-aware large numbers, and N/A
- Build Historical Trends overview, section rows, chart rows, complete historical table rows, missing-data notes, and cache status text from `HistoricalFinancialSeries`
- Reuse `research_metrics.py` historical YoY helpers instead of recalculating YoY in `app.py`

---

### research_context.py

Responsibilities:

- Build a structured `ResearchContext` from already-normalized application/domain models.
- Purely assemble current `Stock`, deterministic `ResearchReport`, optional `HistoricalFinancialSeries`, and optional `HistoricalResearchReport`.
- Preserve current snapshot fields as raw numeric/text values, not UI-formatted strings.
- Group current snapshot data into Company, Market, Profitability, Growth, Financial Health, and Valuation contexts.
- Preserve historical period values, `period_end`, `period_year`, currency, `fetched_at`, and stale-cache status when historical series is supplied.
- Build per-metric source and derived `EvidenceItem` records with deterministic IDs and lineage.
- Link observations to supporting evidence or missing-data records through `ObservationEvidenceLink`.
- Keep explicit structured `missing_data` and `limitations` for current and historical inputs.
- Validate symbol consistency, evidence lineage, duplicate IDs, period consistency, and non-finite numeric values.
- Provide JSON-safe `ResearchContext.to_dict()` serialization.
- Provide the future shared input layer for AI Research Assistant, summary, export, and report generation.

Non-responsibilities:

- Building `ResearchReport` or `HistoricalResearchReport`
- Company-name cache lookup
- Yahoo Finance fetch
- SQLite SQL or persistence
- Streamlit widgets or display formatting
- AI / LLM generation
- Scoring, recommendation, target price, or ranking

---

### research_service.py

Responsibilities:

- Build a deterministic `ResearchReport` from a `Stock`
- Keep research interpretation rules outside `app.py` and Streamlit widget callbacks
- Provide simple data structures: `ResearchObservation`, `ResearchNextStep`, and `ResearchReport`
- Generate structured valuation observations, risk signals, missing-data observations, and research checklist next steps
- Keep each observation split into `what_happened`, `why_it_matters`, and `what_to_check`
- Reuse `research_metrics.calculate_52_week_position()` for 52-week position
- Avoid AI, LLM, buy / sell / hold recommendations, target prices, overall scores, and rating systems

---

### historical_research_service.py

Responsibilities:

- Build a deterministic `HistoricalResearchReport` from `HistoricalFinancialSeries`
- Keep historical interpretation rules outside `app.py`, `dashboard.py`, `database.py`, and `historical_financial_service.py`
- Reuse `ResearchObservation` and `ResearchNextStep` explainability structures
- Describe historical facts with `what_happened`, `why_it_matters`, and `what_to_check`
- Check data sufficiency before trend wording
- Reuse `research_metrics.py` consecutive-year semantics instead of creating separate YoY rules
- Compare margin changes in percentage points
- Compare Capital Expenditure spending scale with `abs(capital_expenditure)` because Yahoo commonly reports CapEx as negative cash outflow
- Avoid AI, LLM, buy / sell / hold recommendations, target prices, overall scores, and rating systems

---

### historical_interpretation_presentation.py

Responsibilities:

- Build Historical Highlights from existing deterministic observations
- Keep highlight selection, detailed category grouping, and next-step display cleanup outside `app.py`
- Group Detailed Interpretation by fixed category order
- Deduplicate next-step items by deterministic normalized exact text
- Limit default next-step display while preserving overflow items for collapsed expanders
- Avoid recalculating historical financial metrics or creating scoring / ranking semantics

---

### research_glossary.py

Responsibilities:

- Provide deterministic beginner glossary content for the Research page
- Keep glossary wording outside `research_service.py`
- Cover one-time items, margin, cash flow, debt, and valuation terminology
- Use Traditional Chinese with key English finance terms preserved

---

### company_name_service.py

Responsibilities:

- Keep Taiwan company name localization outside `app.py` and `stock_service.py`
- Fetch official listed stock names from TWSE OpenAPI `opendata/t187ap03_L`
- Fetch official OTC stock names from TPEx OpenAPI `mopsfin_t187ap03_O`
- Store a lightweight runtime JSON cache in `data/taiwan_company_names.json`
- Return localized display names without overwriting Yahoo `Stock.company_name`
- Fall back to Yahoo company name when official data is unavailable or a symbol is unknown

---

### company_summary_service.py

Responsibilities:

- Build Research page company summary display data without overwriting `Stock.company_summary`
- Prefer Taiwan official public data for Taiwan stocks when usable business-item content is available
- Use TWSE / TPEx company profile data to identify company code, name, industry, and business accounting number
- Use MOEA company registration business items to assemble a short Chinese company introduction
- Fall back to Yahoo Finance English `company_summary` when localized official content is unavailable
- Store a lightweight runtime JSON cache in `data/taiwan_company_summaries.json`
- Avoid AI, LLM, translation APIs, web scraping, SQLite schema changes, and raw model mutation

---

### stock_service.py

Responsibilities:

- Connect to Yahoo Finance
- Retrieve stock information
- Convert raw data into Stock model
- Normalize optional Yahoo fundamental fields into nullable project fields
- Read fresh stock cache before Yahoo Finance lookup
- Write Yahoo Finance result to stock cache when lookup succeeds

---

### historical_financial_service.py

Responsibilities:

- Retrieve Yahoo Finance annual `income_stmt`, `cashflow`, and `balance_sheet`
- Keep Yahoo raw financial statement DataFrame handling outside UI and database code
- Normalize statement row labels through centralized alias priority lists
- Build `HistoricalFinancialSeries` and `HistoricalFinancialPeriod`
- Calculate historical margins from annual revenue and income statement values
- Use direct Yahoo `Free Cash Flow` when available
- Derive Free Cash Flow as `Operating Cash Flow + Capital Expenditure` when direct FCF is unavailable
- Sort normalized periods oldest to newest
- Set `period_year` from the year component of `period_end`; this is not official fiscal-year metadata
- Use independent 7-day historical cache before refreshing Yahoo
- Return stale historical cache with `is_stale=True` when Yahoo refresh fails and stale data exists

---

### database.py

Responsibilities:

- Initialize SQLite database automatically
- Persist Stock model fields in `data/stocks.db`
- Apply simple additive SQLite schema migrations for new Stock snapshot fields
- Return fresh cached Stock data when `fetched_at` is within 24 hours
- Persist historical fundamentals in a separate `historical_financials` table
- Return fresh cached historical fundamentals when `fetched_at` is within 7 days
- Preserve stale historical cache rows if Yahoo refresh fails
- Keep SQL persistence details outside `main.py` and `models.py`

---

### watchlist_service.py

Responsibilities:

- Persist Watchlist data in `data/watchlist.json`
- Add, remove, and list normalized stock symbols
- Handle missing, empty, or invalid watchlist files safely

---

### symbol_utils.py

Responsibilities:

- Normalize stock symbols
- Parse comma-separated stock input

---

### models.py

Responsibilities:

- Define project data models
- Currently contains:

    - Stock
    - HistoricalFinancialPeriod
    - HistoricalFinancialSeries

### research_metrics.py

Responsibilities:

- Provide deterministic helper metrics for future research presentation
- Keep derived metrics separate from Yahoo raw mapping and SQLite persistence
- Avoid AI analysis, scoring, or buy / sell judgement
- Calculate deterministic historical YoY growth helpers only for consecutive `period_year` values and without trend classification

---

# Current Data Flow

```
User
   │
   ▼
main.py or app.py
   │
   ▼
stock_service.py
   │
   ├── database.py
   │      │
   │      ├── Fresh cache hit
   │      │      ▼
   │      │   Stock
   │      │
   │      └── Cache miss / expired
   │
   ▼
Yahoo Finance
   │
   ▼
Stock
   │
   ▼
database.py
   │
   ▼
SQLite cache
   │
   ▼
main.py or app.py
   │
   ▼
Display
```

## Historical Fundamentals Data Flow

```
Caller
   │
   ▼
historical_financial_service.py
   │
   ├── database.py
   │      │
   │      ├── Fresh 7-day cache hit
   │      │      ▼
   │      │   HistoricalFinancialSeries
   │      │
   │      └── Cache missing / expired
   │
   ▼
Yahoo Finance annual statements
   │
   ├── income_stmt
   ├── cashflow
   └── balance_sheet
   │
   ▼
Alias normalization + deterministic derived metrics
   │
   ▼
HistoricalFinancialSeries
   │
   ▼
database.py
   │
   ▼
historical_financials table
```

## Snapshot vs Historical Responsibilities

Current snapshot:

- Model: `Stock`
- Table: `stocks`
- TTL: 24 hours
- Source surface: `yfinance.Ticker.info`
- Scope: latest available price, valuation, profitability, growth, cash/debt, company summary fields

Historical fundamentals:

- Model: `HistoricalFinancialSeries` containing `HistoricalFinancialPeriod`
- Table: `historical_financials`
- TTL: 7 days
- Source surface: annual `income_stmt`, `cashflow`, and `balance_sheet`
- Scope: annual revenue, profit, EPS, margins, cash flow, assets, debt, equity, cash

The Streamlit UI and console UI do not parse Yahoo financial statement DataFrames. Database code does not own Yahoo row label semantics.

## Taiwan Company Name Localization Flow

```
Stock
  │
  ├── Yahoo company_name remains unchanged
  │
  ▼
dashboard.py
  │
  ▼
company_name_service.py
  │
  ├── Fresh JSON cache hit
  │      ▼
  │   Localized display name
  │
  └── Cache miss / expired
         │
         ├── TWSE OpenAPI listed company names
         ├── TPEx OpenAPI OTC company names
         └── data/taiwan_company_names.json
```

Localization is presentation-only. `Stock.company_name` continues to represent the Yahoo Finance raw company name used by the stock data service and SQLite stock cache.

## Taiwan Company Summary Localization Flow

```
Stock
  │
  ├── Yahoo company_summary remains unchanged
  │
  ▼
app.py Research tab
  │
  ▼
company_summary_service.py
  │
  ├── Fresh JSON cache hit
  │      ▼
  │   Localized display summary
  │
  └── Cache miss / expired
         │
         ├── TWSE / TPEx official company profile
         ├── MOEA company registration business items
         └── data/taiwan_company_summaries.json
```

Company summary localization is presentation-only. `Stock.company_summary` continues to represent the Yahoo Finance `longBusinessSummary` value used by the stock data service and SQLite stock cache.

## Streamlit Watchlist Flow

```
User
   │
   ▼
app.py
   │
   ▼
watchlist_service.py
   │
   ▼
data/watchlist.json
   │
   ▼
app.py
   │
   ▼
Display / Query selected symbols through stock_service.py
```

---

## Streamlit Research Flow

```
User
   │
   ▼
app.py Research tab
   │
   ├── symbol_utils.py
   │
   ├── dashboard.py query_stock_batch()
   │
   ▼
stock_service.py
   │
   ├── database.py / SQLite cache
   └── Yahoo Finance API
   │
   ▼
Stock
   │
   ├── dashboard.py display formatters and company localization helper
   ├── company_summary_service.py company summary display helper
   └── research_service.py
          │
          ├── research_metrics.py calculate_52_week_position()
          └── ResearchReport
   │
   └── research_glossary.py glossary dictionary
   │
   ▼
app.py display only
```

Research Dashboard is a presentation / interpretation layer. `app.py` does not implement Yahoo raw field interpretation rules and does not directly generate research observations.

## Streamlit Historical Trends Flow

```
User
   │
   ▼
app.py Historical Trends tab
   │
   ├── symbol_utils.py
   ├── dashboard.py query_stock_batch()
   └── historical_financial_service.py get_historical_financials()
          │
          ├── database.py / 7-day SQLite historical cache
          └── Yahoo Finance annual statements when cache is missing or expired
   │
   ▼
Stock + HistoricalFinancialSeries
   │
   ▼
dashboard.py
   │
   ├── Historical overview display
   ├── Revenue / Earnings / Margins / Cash Flow / Financial Position rows
   ├── Complete formatted historical table
   ├── Chart-ready numeric rows
   └── Missing-data and stale-cache presentation text
   │
   ▼
app.py Streamlit layout and native charts
```

Historical Trends is a presentation layer. `app.py` does not parse Yahoo financial statement DataFrames, handle row aliases, execute SQL, calculate margins, derive Free Cash Flow, or calculate YoY itself.

Historical Trends keeps these presentation semantics:

- Period labels use `FY ending YYYY-MM-DD`.
- YoY is delegated to `research_metrics.py` and only appears when adjacent period years are consecutive.
- Missing values display as `N/A`; missing EPS is not self-calculated.
- Currency context is preserved and no FX conversion or cross-currency ranking is performed.
- The page displays values and visible trends only; it does not classify a company or metric as improving, deteriorating, strong, weak, good, bad, healthy, or unhealthy.

## Streamlit Historical Interpretation Flow

```
HistoricalFinancialSeries
   │
   ▼
historical_research_service.py
   │
   ├── Revenue observations
   ├── Earnings / EPS observations
   ├── Margin percentage-point observations
   ├── Cash Flow and CapEx spending-scale observations
   ├── Financial Position observations
   ├── Cross-metric observations
   └── Historical Research Next Steps
   │
   ▼
HistoricalResearchReport
   │
   ▼
historical_interpretation_presentation.py
   │
   ├── Historical Highlights
   ├── Detailed Interpretation groups
   └── Display-ready Research Next Steps
   │
   ▼
app.py Historical Trends tab
```

Historical Interpretation is deterministic. It may describe directly supported historical changes such as Revenue declining and later recovering, EPS missing for the latest period, or Capital Expenditure spending scale increasing. Possible business reasons are only rendered as research checklist items.

## Research Context Flow

```
Stock
   │
   ├── research_service.py
   │      └── ResearchReport
   │
   ├── HistoricalFinancialSeries
   │      └── historical_research_service.py
   │             └── HistoricalResearchReport
   │
   ▼
research_context.py
   │
   ├── CurrentSnapshotContext
   ├── FundamentalResearchContext
   ├── HistoricalFinancialsContext
   ├── HistoricalResearchContext
   ├── EvidenceItem
   ├── ObservationEvidenceLink
   ├── ResearchLimitation
   └── MissingDataItem
   │
   ▼
ResearchContext
   │
   ├── Future AI Research Assistant input
   ├── Future Research Summary input
   ├── Future Export input
   └── Future Report generation input
```

Research Context is the application/domain integration boundary for future AI and report workflows. It consumes validated and normalized models only. It does not read Yahoo raw dictionaries, SQLite rows, Streamlit widget state, or UI-formatted strings. Detailed contract: `docs/RESEARCH_CONTEXT.md`.

# Future Modules

Planned modules:

- financial_service.py
- news_service.py
- ai_service.py
- report_service.py
