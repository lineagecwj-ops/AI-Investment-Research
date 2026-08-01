# AI-Investment-Research Architecture

## Version

v0.3

---

# Current Architecture

```
main.py
    │
    ▼
stock_service.py
    │
    ▼
Yahoo Finance API

models.py
    └── Stock
```

---

## Responsibilities

### main.py

Responsibilities:

- Program entry point
- Get user input
- Control application flow
- Display results

---

### stock_service.py

Responsibilities:

- Connect to Yahoo Finance
- Retrieve stock information
- Convert raw data into Stock model

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
   ▼
Yahoo Finance
   │
   ▼
Stock
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

- database.py
- financial_service.py
- news_service.py
- ai_service.py
- report_service.py
- dashboard.py