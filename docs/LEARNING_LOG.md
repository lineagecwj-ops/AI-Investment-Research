# Learning Log

## 2026-08-01 — Sprint 02 Batch B Research Dashboard

### Completed Features

- 新增 Streamlit `Research` tab，保留既有 `Dashboard`、`Watchlist`、`Comparison` 功能。
- 新增 `src/research_service.py` 作為 deterministic research interpretation boundary。
- Research 頁面依序呈現 Company Overview、Profitability、Growth、Financial Health、Valuation、Market Position、Risk Signals、Research Next Steps。
- Risk Signals 與 Research Next Steps 使用可測試的 deterministic rules，不使用 AI / LLM。
- 新增簡單資料結構：`ResearchObservation`、`ResearchNextStep`、`ResearchReport`。
- Valuation observation 支援 Forward P/E 明顯低於 Trailing P/E 的中性提示。
- Market Position 重用 `calculate_52_week_position()`，並保留 below `0` / above `1` 的資料語意，不在 research logic 強制 clamp。
- 擴充 dashboard formatter：percentage、ratio、price、currency-aware large numbers、N/A。

### Display Notes

- Research page 主要語言為繁體中文，保留英文投資術語。
- Growth 明確標示目前是 Yahoo Finance snapshot，不是本系統自行計算的多年 CAGR。
- Cash / Debt / Cash Flow 顯示保留 currency context，例如 `TWD 1.25T`、`USD 85.40B`。
- Yahoo `debtToEquity` 以 raw ratio-style number 顯示，例如 `35.20`，不轉成百分比。
- Observations 是 research prompts，不是投資建議、評分或 recommendation。

### Testing Notes

- 新增 `tests/test_research_service.py`。
- 覆蓋 profitability missing data、growth 正值 / 負值 / 缺值、valuation observation、market position 正常 / below 0 / above 1 / missing、risk signals、next steps deterministic 與 no recommendation language、partial Stock summary。
- 完整測試：`.venv/bin/python -m unittest discover -s tests`，80 tests passed。

### Manual Validation Notes

- 以 `2330.TW`、`2454.TW`、`NVDA`、`AAPL` 建立 Research report，四支股票皆可完成 Company Overview、Profitability、Growth、Financial Health、Valuation、Market Position、Risk Signals、Research Next Steps。
- 授權網路驗證後，台股 localized display name 正常：`2330.TW` 顯示 `台積電`，`2454.TW` 顯示 `聯發科`。
- Sandbox restricted network 下，TWSE / TPEx localization 會 fallback Yahoo English name；授權網路或 fresh runtime cache 可恢復中文顯示。

### Modified / Added Files

- 新增 `src/research_service.py`
- 新增 `tests/test_research_service.py`
- 新增 `docs/RESEARCH_FRAMEWORK.md`
- 修改 `app.py`
- 修改 `src/dashboard.py`
- 修改 `tests/test_dashboard.py`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Known Limits

- Growth 仍是 Yahoo snapshot，不是 historical CAGR。
- Research Dashboard 尚未有 historical fundamental table，因此無法自行計算多年趨勢。
- 52-week progress bar 為簡單視覺輔助，research logic 保留原始 position 語意。
- Current validation 依賴 Yahoo snapshot 與 local 24-hour cache。

### Code Review Focus

- `src/research_service.py` deterministic observations 與 next steps 是否維持中性語氣。
- `app.py` Research tab 是否只做 UI / display，不直接實作研究規則。
- `src/dashboard.py` formatter 是否正確保留 currency context 與 Yahoo ratio 語意。
- `tests/test_research_service.py` 是否覆蓋 partial data 與 no recommendation language。
- `docs/RESEARCH_FRAMEWORK.md` 是否清楚界定非投資建議與 methodology。

## 2026-08-01 — Sprint 02 Batch A Fundamental Data Foundation

### Completed Features

- Audited Yahoo Finance / `yfinance.Ticker.info` fundamental field availability for `2330.TW`, `2454.TW`, `NVDA`, and `AAPL`.
- Expanded `Stock` with nullable fundamental fields for company overview, profitability, growth, financial health, valuation, and market position.
- Kept Yahoo raw key mapping inside `src/stock_service.py`; Dashboard still receives only `Stock` project fields.
- Added optional field normalization so missing, `None`, non-numeric, and malformed optional Yahoo values become `None` instead of causing query failure.
- Added additive SQLite migration for existing `stocks` cache tables with `ALTER TABLE ADD COLUMN`.
- Added `src/research_metrics.py` with deterministic 52-week position calculation.

### Cache Strategy

- Existing `data/stocks.db` is preserved.
- `initialize_database()` still creates the `stocks` table when missing.
- Existing tables are upgraded in place by adding missing nullable columns.
- Old cache rows remain readable; newly added fields are `None` until the row is refreshed from Yahoo Finance.
- Fundamental snapshot data currently shares the existing 24-hour stock cache TTL.

### Modified / Added Files

- 新增 `docs/FUNDAMENTAL_DATA_AUDIT.md`
- 新增 `src/research_metrics.py`
- 新增 `tests/test_research_metrics.py`
- 修改 `src/models.py`
- 修改 `src/stock_service.py`
- 修改 `src/database.py`
- 修改 `tests/test_stock_service.py`
- 修改 `tests/test_database.py`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Data Quality Notes

- `current_price` remains the minimum required validation boundary.
- Optional fundamental fields are nullable and do not raise `StockServiceError` when missing or malformed.
- `earningsQuarterlyGrowth` was audited and available for the representative symbols, but was not stored in this Batch because `earnings_growth` is sufficient for the current foundation scope.

### Technical Debt

- Price data and fundamental data may need separate freshness policies in a later Batch.
- SQLite currently stores the latest stock snapshot only; there is no historical fundamental table yet.
- Cross-market comparison of cash, debt, and cash flow requires currency-aware presentation in a future Research Dashboard.

### Code Review Focus

- `src/stock_service.py` optional field normalization and Yahoo raw key mapping.
- `src/database.py` additive migration behavior for existing `stocks` tables.
- `src/research_metrics.py` boundary handling for 52-week position.
- `docs/FUNDAMENTAL_DATA_AUDIT.md` field dictionary and known limitations.

## 2026-08-01 — Taiwan Company Name Localization Patch

### Completed Features

- 新增 `src/company_name_service.py` 作為 presentation-only company name localization boundary。
- 台股 display name 優先使用官方繁體中文名稱，不覆寫 Yahoo raw `Stock.company_name`。
- Dashboard stock card、Watchlist query result 與 Comparison Company Name 欄位都透過 `dashboard.py` 的同一套 formatter 使用 localized display helper。
- 上市資料來源使用 TWSE official OpenAPI `opendata/t187ap03_L`。
- 上櫃資料來源使用 TPEx official OpenAPI `mopsfin_t187ap03_O`。
- 若官方資料來源失敗、cache 不存在、或 symbol 找不到中文名稱，fallback 到既有 Yahoo English company name。

### Cache Strategy

- 使用 runtime JSON cache：`data/taiwan_company_names.json`。
- Cache TTL 為 7 days，避免 Streamlit Dashboard 每次 rerun 都重新下載完整台股名稱資料。
- Cache file 已加入 `.gitignore`，不進版本控制。
- 若 cache 過期但官方來源暫時失敗，會嘗試使用既有 stale cache；若沒有可用 cache，回到 Yahoo English company name。

### Modified / Added Files

- 新增 `src/company_name_service.py`
- 新增 `tests/test_company_name_service.py`
- 修改 `src/dashboard.py`
- 修改 `tests/test_dashboard.py`
- 修改 `.gitignore`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Testing Notes

- Tests 使用 mock / fixture 模擬 TWSE 與 TPEx official API response，不依賴 live internet。
- 覆蓋 known TWSE stock、known TPEx stock、unknown Taiwan symbol fallback、US stock English、official source failure fallback、Dashboard helper reuse、Comparison helper reuse。

### Known Limits

- 現有 `symbol_utils.py` 仍保留純數字自動轉 `.TW` 的既有規則；上櫃 localization 會在 stock symbol 已是 `.TWO` 時生效。
- Official API 欄位解析目前支援常見中文欄位名稱與少數英文欄位名稱；若官方 schema 未來改名，需要更新 `company_name_service.py` 的 key list。
- Runtime cache 不保存每個市場的 individual refresh 狀態，只保存合併後的 symbol-name map 與 sources metadata。

## 2026-08-01 — Sprint 01 Batch C

### Completed Features

- Feature 1 — Streamlit Dashboard MVP
  - 新增根目錄 `app.py` 作為 Streamlit application entry point。
  - Dashboard 使用 `st.set_page_config()` 與 wide layout。
  - 保留 `src/main.py` console application，Streamlit 只作為新的 presentation layer。

- Feature 2 — Stock Search
  - Dashboard 支援單一股票與逗號分隔多股票輸入，例如 `2330`、`NVDA`、`2330,NVDA,AAPL`。
  - 股票代號解析重用 `src/symbol_utils.py`。
  - 股票資料查詢重用 `src/stock_service.py`，不在 `app.py` 直接使用 Yahoo Finance 或 SQLite。
  - 股票資訊使用 Streamlit metric、columns、container 呈現。

- Feature 3 — Watchlist UI
  - Dashboard 支援顯示、新增、移除與查詢 Watchlist 股票。
  - Watchlist persistence 重用 `src/watchlist_service.py`，不在 `app.py` 直接讀寫 JSON。
  - `WatchlistDataError` 會以 `st.error()` 顯示，不向一般使用者顯示 Python traceback。

- Feature 4 — Multi-stock Comparison
  - Dashboard 支援手動輸入多股票，或從 Watchlist 選擇多支股票。
  - 比較表格至少包含 Symbol、Company、Current Price、Currency、Market Cap、Trailing PE、Forward PE、EPS、ROE、Sector、Industry。
  - Current Price 保留原始 currency，並提示不可直接作為跨幣別排名。

- Feature 5 — Presentation Helper Tests
  - 新增 `src/dashboard.py`，集中 dashboard formatting、comparison row 與 batch query partial failure handling。
  - 新增 `tests/test_dashboard.py`，避免 automated tests 依賴真正 Yahoo Finance 網路。

### Modified / Added Files

- 新增 `app.py`
- 新增 `src/dashboard.py`
- 新增 `tests/test_dashboard.py`
- 新增 `requirements.txt`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Data Flow Notes

- Dashboard stock query：`app.py` → `symbol_utils.py` → `dashboard.py` → `stock_service.py` → `database.py` / Yahoo Finance → `Stock` → `dashboard.py` formatting → `app.py` display。
- Dashboard Watchlist：`app.py` → `watchlist_service.py` → `data/watchlist.json` → display 或轉交 `stock_service.py` 查詢。
- Comparison：手動輸入與 Watchlist 選取合併去重後，走同一個 batch stock lookup flow。

### Streamlit State Notes

- `st.session_state` 保存 stock search、Watchlist query、comparison 的成功結果與失敗結果。
- 使用 `st.form()` 降低一般 widget rerun 造成的意外重複 query。
- Watchlist add / remove 成功後使用 `st.rerun()` refresh list。

### Software Engineering Concepts

- Presentation Layer
- Service reuse
- Streamlit rerun behavior
- Session state
- Display formatting helpers
- Partial failure handling

### Code Review Focus

- `app.py` 是否只負責 Streamlit UI 與流程，不直接碰 Yahoo Finance、SQLite、JSON。
- `src/dashboard.py` 的格式化規則是否符合 dashboard MVP 需求。
- Watchlist add / remove / query 在 Streamlit rerun 下是否符合日常使用。
- Comparison 對手動輸入與 Watchlist 選取的合併方式是否簡單、可預期。
- `tests/test_dashboard.py` 是否有效保護 display formatting 與 partial failure behavior。

### Known Limits

- Cache visibility 目前只顯示「資料可能使用 24 小時內的本地快取」，尚未揭露每支股票的 cache hit / Yahoo fetch 與 `fetched_at`。
- Taiwan stock localized company name source：`yfinance` 對 `2330.TW` 目前只提供英文 `longName` / `shortName`，未提供可靠繁體中文公司名稱欄位；後續若需要繁中公司名，應評估可靠且可維護的台股公司主檔來源。
- Dashboard 目前沒有 chart、AI analysis、news、portfolio、technical indicator、recommendation engine。
- 無效股票錯誤仍沿用 Batch A / B 的 service error 訊息，尚未細分 invalid symbol 類型。
- Streamlit smoke test 尚未加入 automated tests；目前以 manual validation 搭配 helper tests 驗證。

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
