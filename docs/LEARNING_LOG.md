# Learning Log

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
