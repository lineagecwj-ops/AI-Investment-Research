# Learning Log

## 2026-08-01 — Sprint 01 Batch B

### Completed Features

- Feature 1 — SQLite Stock Cache
  - 新增 `src/database.py`，使用 Python standard library `sqlite3` 建立 `data/stocks.db`。
  - Cache TTL 設為 24 hours，以 `fetched_at` 判斷 fresh cache / expired cache。
  - `stock_service.py` 先讀 SQLite cache；cache miss 或 expired 才查詢 Yahoo Finance。
  - Yahoo Finance 成功後會將 `Stock` model 欄位寫入 SQLite，不直接保存 Yahoo raw dictionary。
  - Cache read failure 會 fallback Yahoo Finance；cache write failure 不會阻止成功的 Yahoo query 回傳 `Stock`。

- Feature 2 — Watchlist
  - 新增 `src/watchlist_service.py`，使用 `data/watchlist.json` 保存個人 Watchlist。
  - 支援新增、移除、列出股票。
  - Watchlist 使用既有股票代號 normalize 規則，不允許重複並保留加入順序。
  - 缺檔、空檔與基本 JSON 格式錯誤會友善視為空 Watchlist。

- Feature 3 — Console Menu
  - `src/main.py` 改為簡單 MVP menu。
  - 主選單支援查詢股票、Watchlist 與離開。
  - Watchlist 子選單支援顯示、新增、移除、查詢 Watchlist 股票與返回。
  - Watchlist query 重用既有 `query_stocks()` flow，因此同樣優先使用 SQLite cache。

### Modified / Added Files

- 新增 `src/database.py`
- 新增 `src/watchlist_service.py`
- 新增 `src/symbol_utils.py`
- 新增 `tests/test_database.py`
- 新增 `tests/test_watchlist_service.py`
- 修改 `src/stock_service.py`
- 修改 `src/main.py`
- 修改 `tests/test_main.py`
- 修改 `tests/test_stock_service.py`
- 修改 `.gitignore`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`

### Data Flow Notes

- Cache hit：`main.py` → `stock_service.py` → `database.py` → `Stock` → display。
- Cache miss / expired：`main.py` → `stock_service.py` → Yahoo Finance → `Stock` → `database.py` upsert → display。
- Watchlist：`main.py` → `watchlist_service.py` → `data/watchlist.json`。

### Software Engineering Concepts

- Cache TTL
- SQLite upsert
- Parameterized SQL
- Runtime data vs versioned source
- Persistence boundary
- Cache failure fallback
- Unit testing with temp files and mocks

### Code Review Focus

- `src/database.py` 的 schema、TTL 判斷與 timezone handling 是否足夠簡單且可測。
- `src/stock_service.py` 的 cache read/write failure fallback 是否符合 MVP 可用性需求。
- `src/watchlist_service.py` 對缺檔、空檔與 invalid JSON 的處理是否符合「友善」預期。
- `src/main.py` 的 menu flow 是否仍保持簡單，沒有混入 SQL / JSON persistence。
- `tests/test_stock_service.py` 的 cache hit / miss / expired mock 是否準確保護不依賴真實 Yahoo Finance。

### Known Limits

- Cache 目前只保存最新一次 snapshot，尚未建立歷史價格表。
- Cache failure 目前以 logging warning 記錄，尚未提供使用者可見的 cache 狀態提示。
- Watchlist 目前是單一 JSON list，未保存加入時間、備註或分類。
- Console menu 還是 MVP 互動，尚未進入 Streamlit Dashboard。

## 2026-08-01 — Sprint 01 Batch A

### Completed Features

- Feature 1 — Multiple Stock Query
  - 支援逗號分隔的多股票輸入，例如 `2330,NVDA,AAPL` 與 `2330, NVDA, AAPL`。
  - 保留純數字自動加 `.TW`、英文代號轉大寫、去除前後空白。
  - 加入去重，避免相同股票被重複查詢。

- Feature 2 — Expand Stock Model
  - 擴充 `Stock` dataclass，加入 Yahoo Finance 可提供的公司、價格、估值、獲利與產業欄位。
  - `stock_service.py` 負責 Yahoo raw dictionary 到 `Stock` model 的欄位轉換。
  - console output 使用一致的 `N/A` 顯示缺值，ROE 以百分比呈現。

- Feature 3 — Basic Error Handling
  - 處理空白輸入、查詢失敗、網路錯誤、缺少重要欄位。
  - 多股票查詢時，單一股票失敗不會中止其他股票。
  - 避免對一般使用者顯示完整 Python traceback 或 Yahoo provider raw error。

### Design Notes

- `main.py` 維持 application entry、使用者互動、流程控制與 console presentation。
- `stock_service.py` 維持 Yahoo Finance interaction、raw data conversion 與 Stock model validation。
- `models.py` 只保留 project data model，不引入資料庫、dashboard、watchlist 或 AI。
- 保留既有 `price` 欄位，並同步新增的 `current_price`，降低後續相容性風險。

### Modified Files

- `src/main.py`
- `src/models.py`
- `src/stock_service.py`
- `tests/test_main.py`
- `tests/test_stock_service.py`

### Software Engineering Concepts

- Separation of Concerns
- Data Transfer Object / Project Model
- Input normalization
- Defensive programming
- Exception wrapping
- Partial failure handling
- Unit testing with mocks

### Code Review Focus

- `src/main.py` 的 `parse_stock_symbols()` 是否符合未來多市場代號規則。
- `src/main.py` 的多股票查詢 flow 是否仍保持 presentation 與 application flow 的責任。
- `src/stock_service.py` 的 Yahoo raw key mapping 是否足夠明確且可擴充。
- `src/stock_service.py` 的 `validate_stock()` 對重要欄位的判斷是否符合 MVP。
- 測試是否應在後續補上 integration test 或 fixtures，降低對即時 Yahoo Finance 資料的依賴。

### Known Limits

- 即時查詢仍依賴 Yahoo Finance 可用性與網路狀態。
- 無效股票目前以缺少目前價格作為 MVP 判斷，後續可再細分為更精準的 invalid symbol error。
- 市值、PE、EPS 等數值目前未做千分位或固定小數格式化，僅保持 Yahoo Finance 回傳值的直接呈現。
