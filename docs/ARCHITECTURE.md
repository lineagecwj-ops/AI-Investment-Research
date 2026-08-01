# AI-Investment-Research Architecture

## Version

v0.4

---

# Current Architecture

```
main.py
    │
    ▼
stock_service.py
    │
    ├── database.py
    │       └── SQLite stock cache
    │
    └── Yahoo Finance API

watchlist_service.py
    └── JSON watchlist

models.py
    └── Stock

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

### stock_service.py

Responsibilities:

- Connect to Yahoo Finance
- Retrieve stock information
- Convert raw data into Stock model
- Read fresh stock cache before Yahoo Finance lookup
- Write Yahoo Finance result to stock cache when lookup succeeds

---

### database.py

Responsibilities:

- Initialize SQLite database automatically
- Persist Stock model fields in `data/stocks.db`
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

---

# Current Data Flow

```
User
   │
   ▼
main.py
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
main.py
   │
   ▼
Display
```

---

# Future Modules

Planned modules:

- financial_service.py
- news_service.py
- ai_service.py
- report_service.py
- dashboard.py
