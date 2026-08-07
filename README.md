# AI-Investment-Research

## 專案簡介

AI-Investment-Research 是一個結合 AI 與投資研究的個人專案。

本專案的目標不是建立自動交易系統，而是建立一套能協助整理、分析與理解投資資訊的 AI 研究平台。

---

## 專案目標

- 建立每日投資研究流程
- 整合公開市場資料
- 利用 AI 協助分析資訊
- 建立可持續擴充的投資研究工具

---

## 開發理念

本專案採用 Incremental Development（漸進式開發）。

每次只完成一小部分功能，經過驗證後再持續擴充。

---

## 目前進度

- ✅ 建立 Git Repository
- ✅ 建立 GitHub Repository
- ✅ 建立 VS Code 開發環境
- ✅ 建立 Project Prompt
- ✅ 建立 README
- ✅ 建立 Console MVP
- ✅ 建立 Streamlit Dashboard MVP

---

## 專案狀態

目前版本：v0.1

---

## MVP 使用方式

安裝 runtime dependencies：

```bash
.venv/bin/python -m pip install -r requirements.txt
```

使用專案虛擬環境執行主程式：

```bash
.venv/bin/python src/main.py
```

主選單目前提供：

```text
1. 查詢股票
2. Watchlist
3. 離開
```

選擇 `1. 查詢股票` 後，可輸入單一股票代號：

```text
2330
NVDA
```

也可用逗號一次查詢多支股票：

```text
2330,NVDA,AAPL
2330, NVDA, AAPL
```

純數字股票代號會自動加上 `.TW`，英文股票代號會自動轉為大寫。

股票查詢會先檢查本機 SQLite cache。若 24 小時內已有 fresh cache，會直接使用本機資料；若沒有資料或 cache 已過期，才查詢 Yahoo Finance 並更新 cache。

Watchlist 可新增、移除、列出股票，資料儲存在 `data/watchlist.json`。SQLite cache 儲存在 `data/stocks.db`。這兩個檔案屬於 runtime / personal data，不提交到 Git。

## Dashboard 使用方式

使用 Streamlit 啟動 Dashboard：

```bash
.venv/bin/streamlit run app.py
```

Dashboard 目前提供：

- `Dashboard`：股票搜尋，可輸入單一股票或逗號分隔多股票，顯示公司、價格、市值、PE、EPS、ROE、Sector、Industry。
- `Research`：單一股票研究頁，依照 Company Overview、Profitability、Growth、Financial Health、Valuation、Market Position、Risk Signals、Research Next Steps 整理 fundamental snapshot。
- `Historical Trends`：單一股票年度歷史趨勢頁，呈現 Revenue、Earnings / EPS、Margins、Cash Flow、Financial Position、deterministic historical interpretation 與完整 historical table。
- `AI Research`：單一股票 grounded AI 研究頁；使用 explicit question type、使用者問題、Selected Research Context 與 OpenAI Responses API 產生具 evidence citations 的 structured answer，並支援 session-only grounded follow-up research workflow。
- `Watchlist`：顯示、新增、移除與查詢 Watchlist 股票。
- `Comparison`：輸入多股票或從 Watchlist 選擇多支股票，使用表格呈現比較資料。

Research 頁面使用 deterministic / explainable rules 產生 observations 與 next steps，不使用 OpenAI API、ChatGPT API 或其他 LLM。系統不提供 Buy / Sell / Hold recommendation、target price 或 overall stock score；頁面上的 observations 是 research prompts，不是投資建議。

Historical Trends 頁面使用 Yahoo Finance annual financial statements 與 7-day SQLite historical cache。Period End 顯示為 `FY ending YYYY-MM-DD`，避免把 NVIDIA / Apple 等非 12/31 年結日誤讀為完整曆年；YoY 只在相鄰年度連續時顯示，缺資料顯示 `N/A`，不補 0、不自行計算 Yahoo 未提供的 EPS。Historical Interpretation 使用固定規則整理 What happened、Why it matters、What to check next，不使用 AI / LLM、不產生 Buy / Sell / Hold、target price、score 或 rating。

Dashboard 與 console application 共用既有 service layer：

- 股票代號 normalization 與 parsing：`src/symbol_utils.py`
- Yahoo Finance 查詢與 SQLite cache：`src/stock_service.py`、`src/database.py`
- Watchlist persistence：`src/watchlist_service.py`
- Research interpretation：`src/research_service.py`
- Historical interpretation：`src/historical_research_service.py`
- Historical fundamentals normalization and cache：`src/historical_financial_service.py`
- Historical daily price normalization and cache：`src/historical_price_service.py`

Research methodology 詳見 `docs/RESEARCH_FRAMEWORK.md`。
Historical Trends methodology 詳見 `docs/HISTORICAL_TREND_DASHBOARD.md`。
Historical Interpretation methodology 詳見 `docs/HISTORICAL_INTERPRETATION_FRAMEWORK.md`。
Grounded AI Research foundation 詳見 `docs/AI_GROUNDED_RESEARCH.md`。
AI Research Dashboard integration 詳見 `docs/AI_RESEARCH_DASHBOARD.md`。
Historical Price Data audit 詳見 `docs/HISTORICAL_PRICE_DATA_AUDIT.md`。
Historical Price Foundation 詳見 `docs/HISTORICAL_PRICE_FOUNDATION.md`。

Dashboard 不直接查詢 Yahoo Finance、不直接讀寫 SQLite，也不直接讀寫 Watchlist JSON。

## Historical Price Foundation

Sprint 06 Batch A 新增 daily historical price foundation，供未來 Quantitative Swing Research 使用。

目前範圍只包含 Yahoo daily OHLCV normalization、SQLite cache、12-hour price-history TTL、range coverage state、stale fallback、data-quality filtering、corporate-action fields、as-of slicing 與 recent N trading-bars helper。

此 foundation 不包含 RSI、MACD、moving average signal、backtest、scanner、candlestick chart、AI price prediction、Historical Hit Rate 或 Future Probability。未來 technical analysis 的 close contract 為 `adjusted_close if available else close`，並且任何 as-of research 必須只使用 `trading_date <= as_of_date` 的 bars。

## Grounded AI Research Foundation

目前已建立第一版 Grounded AI Research service boundary，並已接入 Streamlit AI Research tab；AI answer 仍不會寫入 SQLite。

此 layer 使用 `SelectedResearchContext` 作為唯一 AI input，透過 OpenAI Responses API strict structured output 產生 `GroundedResearchAnswer`，並在回傳前做 deterministic grounding validation。Production 使用 `OPENAI_API_KEY`，tests 使用 fake client，不需要 network 或 API key。

## AI Research Dashboard 使用方式

AI Research tab 需要在啟動 Dashboard 前設定 `OPENAI_API_KEY` 環境變數。系統只檢查是否已設定，不會在 UI 顯示、輸入或保存 API key。

```bash
.venv/bin/streamlit run app.py
```

在 `AI Research` tab 輸入單一股票、選擇 Research Question Type、輸入研究問題，並明確按下 `產生 AI 研究` 後才會呼叫 OpenAI API。此操作可能產生 API 使用費用。

延伸研究不是自由聊天。每一輪都會重新依研究類型挑選可追溯資料，再發出新的 Grounded AI request；上一輪 AI answer 不會成為下一輪 factual source。

AI answer 只保存在 `st.session_state`，不寫入 SQLite，也不建立聊天記憶或對話紀錄。展開 evidence、切換非 AI 控制或 Streamlit rerun 不會自動重新呼叫 OpenAI API。

AI Follow-up Research workflow 詳見 `docs/AI_FOLLOWUP_RESEARCH.md`。
