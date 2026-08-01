# AI-Investment-Research Architecture

## Version

v0.7

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

research_service.py
    └── Deterministic research interpretation and observations

research_glossary.py
    └── Beginner research term glossary for Research UI

company_name_service.py
    └── Taiwan official company name localization + JSON cache

models.py
    └── Stock

research_metrics.py
    └── Deterministic research metric helpers

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

### stock_service.py

Responsibilities:

- Connect to Yahoo Finance
- Retrieve stock information
- Convert raw data into Stock model
- Normalize optional Yahoo fundamental fields into nullable project fields
- Read fresh stock cache before Yahoo Finance lookup
- Write Yahoo Finance result to stock cache when lookup succeeds

---

### database.py

Responsibilities:

- Initialize SQLite database automatically
- Persist Stock model fields in `data/stocks.db`
- Apply simple additive SQLite schema migrations for new Stock snapshot fields
- Return fresh cached Stock data when `fetched_at` is within 24 hours
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

### research_metrics.py

Responsibilities:

- Provide deterministic helper metrics for future research presentation
- Keep derived metrics separate from Yahoo raw mapping and SQLite persistence
- Avoid AI analysis, scoring, or buy / sell judgement

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

# Future Modules

Planned modules:

- financial_service.py
- news_service.py
- ai_service.py
- report_service.py
