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

目前版本：V1.0 — Daily Swing Research Ready

V1.0 已完成 Daily Swing Research 的正式研究流程基礎：

- Historical Price Foundation
- Technical Indicator Foundation
- Signal & Outcome Framework
- Historical Backtest Engine
- Swing Opportunity Scanner
- Historical Case Explorer
- Swing Research Dashboard
- Research Universe Management
- Historical Replay
- Walk-Forward Replay
- Replay Analytics
- Out-of-Sample Validation
- OOS Validation Dashboard

重要限制：

- 本專案是 research tool，不是 investment recommendation system。
- Historical Hit Rate 是歷史條件事件比例，不是 future probability。
- 目前不做 automatic parameter optimization。
- 目前不計算 strategy P&L。
- 目前尚未建立 calibrated probability model。
- Swing scanner 目前尚未合併 fundamental data。

V1.0 的主要 daily-research UI 採用繁體中文術語呈現操作、狀態、表格欄位與 helper text；internal IDs、enum values、service contracts 與 research semantics 仍維持英文原值，方便追溯與測試。

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

Saved Research Universes 可建立多個命名股票池，資料儲存在 SQLite `research_universes` / `research_universe_symbols`。Universe 是研究標的集合，不是推薦清單、Buy list、未來機率或投資建議。

## macOS Quick Launch

可使用本機雙擊啟動器開啟 Dashboard，避免手動開 Terminal 輸入啟動指令。

建置方式：

```bash
launcher/build_mac_app.sh
```

產生的 app 位於：

```text
dist/AI Investment Research.app
```

雙擊後會檢查 `localhost:8501` 是否已有 Streamlit server。若已啟動，會直接開啟瀏覽器；若尚未啟動，會使用專案內 `.venv/bin/python` 背景啟動 `app.py`，等待 ready 後開啟 `http://localhost:8501`。Generated app bundle 位於 ignored `dist/`，不提交到 Git。詳細說明見 `launcher/README.md`。

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
- `Swing Research`：波段研究整合頁；支援 Manual Input、Watchlist 與 Saved Universe symbol source，按下執行後才掃描 resolved symbols。Current Scan 顯示 summary、MATCH / NO_MATCH 技術條件明細、current MATCH candidates、Historical Hit Rate + Resolved Samples、MFE / MAE / End Return、Research Priority、current signal condition trace、technical snapshot 與少量 Historical Cases Preview。技術條件明細只顯示 scan-time actual values、V1 thresholds、既有 PASS / FAIL 與中性 gap，不重新抓 Yahoo、不重新掃描、不重新 backtest，也不是 score、future probability 或 recommendation。Historical Replay 讓使用者指定單一 Replay Date，顯示 Requested Replay Date、各 symbol 的 Actual Trading Date、Historical Hit Rate (As Of) 與獨立的 Post-Replay Outcome 事後驗證。Walk-Forward Replay 會依 Monthly 或 Weekly schedule 重複執行 Single-Date Historical Replay，顯示 period timeline、candidate occurrence counts 與 repeated candidate frequency。Out-of-Sample Validation 會在明確按下 `執行樣本外驗證` 後，比較 Development / Validation / Holdout 三段固定 research specification 的 descriptive validation facts、Research Specification Fingerprint、Historical Hit Rate + Resolved n、Candidate Period Share、outcome counts 與 period-local candidate stability。此頁不是自動獲利股票搜尋器，也不提供投資建議、未來機率、prediction accuracy 或交易指令。
- `Replay Analytics`：在 Walk-Forward Replay 成功結果下方顯示 Stability Summary、Candidate Occurrence、Period Timeline、Candidate Set Stability 與 Post-Replay Outcome Counts。這是 existing replay result 的描述性 analytics，不重新抓 Yahoo、不重新 replay、不重新 backtest，也不提供 future probability、recommendation、strategy P&L 或 optimization。
- `Universes`：自訂研究股票池管理頁；可建立、編輯名稱 / description / symbols、刪除 Universe，CRUD 全程只使用 local SQLite，不呼叫 Yahoo 或 OpenAI。
- `Historical Cases`：單一股票 historical case explorer；按下建立後才執行 price / technical / backtest / case-view workflow，顯示 HIT / MISS / INCOMPLETE / NOT_EVALUABLE 歷史案例、analysis-close chart、raw-high reference / hit marker、signal condition trace 與 signal-date technical snapshot。
- `Watchlist`：顯示、新增、移除與查詢 Watchlist 股票。
- `Comparison`：輸入多股票或從 Watchlist 選擇多支股票，使用表格呈現比較資料。

Research 頁面使用 deterministic / explainable rules 產生 observations 與 next steps，不使用 OpenAI API、ChatGPT API 或其他 LLM。系統不提供 Buy / Sell / Hold recommendation、target price 或 overall stock score；頁面上的 observations 是 research prompts，不是投資建議。

Historical Trends 頁面使用 Yahoo Finance annual financial statements 與 7-day SQLite historical cache。Period End 顯示為 `FY ending YYYY-MM-DD`，避免把 NVIDIA / Apple 等非 12/31 年結日誤讀為完整曆年；YoY 只在相鄰年度連續時顯示，缺資料顯示 `N/A`，不補 0、不自行計算 Yahoo 未提供的 EPS。Historical Interpretation 使用固定規則整理 What happened、Why it matters、What to check next，不使用 AI / LLM、不產生 Buy / Sell / Hold、target price、score 或 rating。

Dashboard 與 console application 共用既有 service layer：

- 股票代號 normalization 與 parsing：`src/symbol_utils.py`
- Yahoo Finance 查詢與 SQLite cache：`src/stock_service.py`、`src/database.py`
- Watchlist persistence：`src/watchlist_service.py`
- Saved Research Universe persistence：`src/universe_service.py`
- Universe UI helpers：`src/universe_dashboard.py`
- Research interpretation：`src/research_service.py`
- Historical interpretation：`src/historical_research_service.py`
- Historical fundamentals normalization and cache：`src/historical_financial_service.py`
- Historical daily price normalization and cache：`src/historical_price_service.py`
- Technical indicator feature calculation：`src/technical_indicator_service.py`
- Signal and historical outcome definition：`src/signal_outcome_service.py`
- Historical backtest aggregation：`src/backtest_service.py`
- Swing opportunity scanner foundation：`src/swing_scanner_service.py`
- Historical case explorer：`src/historical_case_service.py`、`src/historical_case_dashboard.py`
- Historical replay mode：`src/historical_replay_service.py`
- Walk-forward replay mode：`src/walk_forward_replay_service.py`
- Replay analytics stability review：`src/replay_analytics_service.py`
- Out-of-sample validation foundation：`src/out_of_sample_validation_service.py`
- OOS validation dashboard helpers：`src/oos_validation_dashboard.py`

Research methodology 詳見 `docs/RESEARCH_FRAMEWORK.md`。
Historical Trends methodology 詳見 `docs/HISTORICAL_TREND_DASHBOARD.md`。
Historical Interpretation methodology 詳見 `docs/HISTORICAL_INTERPRETATION_FRAMEWORK.md`。
Grounded AI Research foundation 詳見 `docs/AI_GROUNDED_RESEARCH.md`。
AI Research Dashboard integration 詳見 `docs/AI_RESEARCH_DASHBOARD.md`。
Historical Price Data audit 詳見 `docs/HISTORICAL_PRICE_DATA_AUDIT.md`。
Historical Price Foundation 詳見 `docs/HISTORICAL_PRICE_FOUNDATION.md`。
Technical Indicator Foundation 詳見 `docs/TECHNICAL_INDICATOR_FOUNDATION.md`。
Signal & Outcome Framework 詳見 `docs/SIGNAL_OUTCOME_FRAMEWORK.md`。
Historical Backtest Engine 詳見 `docs/HISTORICAL_BACKTEST_ENGINE.md`。
Swing Opportunity Scanner 詳見 `docs/SWING_OPPORTUNITY_SCANNER.md`。
Historical Case Explorer 詳見 `docs/HISTORICAL_CASE_EXPLORER.md`。
Swing Research Dashboard 詳見 `docs/SWING_RESEARCH_DASHBOARD.md`。
Technical Condition Detail 詳見 `docs/TECHNICAL_CONDITION_DETAIL.md`。
Universe Management 詳見 `docs/UNIVERSE_MANAGEMENT.md`。
Historical Replay Mode 詳見 `docs/HISTORICAL_REPLAY_MODE.md`。
Walk-Forward Replay 詳見 `docs/WALK_FORWARD_REPLAY.md`。
Replay Analytics & Stability Review 詳見 `docs/REPLAY_ANALYTICS_STABILITY.md`。
Out-of-Sample Validation 詳見 `docs/OUT_OF_SAMPLE_VALIDATION.md`。
OOS Validation Dashboard 詳見 `docs/OOS_VALIDATION_DASHBOARD.md`。

Dashboard 不直接查詢 Yahoo Finance、不直接讀寫 SQLite，也不直接讀寫 Watchlist JSON。

## Historical Price Foundation

Sprint 06 Batch A 新增 daily historical price foundation，供未來 Quantitative Swing Research 使用。

目前範圍只包含 Yahoo daily OHLCV normalization、SQLite cache、12-hour price-history TTL、range coverage state、stale fallback、data-quality filtering、corporate-action fields、as-of slicing 與 recent N trading-bars helper。

此 foundation 不包含 RSI、MACD、moving average signal、backtest、scanner、candlestick chart、AI price prediction、Historical Hit Rate 或 Future Probability。未來 technical analysis 的 close contract 為 `adjusted_close if available else close`，並且任何 as-of research 必須只使用 `trading_date <= as_of_date` 的 bars。

## Technical Indicator Foundation

Sprint 06 Batch B 新增 deterministic technical indicator foundation，從 `HistoricalPriceSeries` 計算 SMA、EMA、RSI、MACD、ATR、volume ratio、return、prior high / low 與 distance features。

本層只產生 technical features / measurements，不產生 Buy / Sell / Hold、technical score、probability、hit rate、success / failure outcome、scanner 或 backtest。所有 as-of technical snapshot 都必須遵守 no-look-ahead，只使用 `trading_date <= as_of_date` 的 price bars。

## Signal & Outcome Framework

Sprint 06 Batch C 新增 deterministic signal / historical outcome foundation。

Signal layer 只用 signal date 當下的 `TechnicalIndicatorSnapshot` 評估條件，並區分 `MATCH`、`NO_MATCH`、`NOT_EVALUABLE`。Historical outcome layer 才能使用 signal date 之後的 future trading bars，產生 `HIT`、`MISS`、`INCOMPLETE` 或 `NOT_EVALUABLE` 的歷史標籤。

本層目前只支援 raw-high breakout 與 close-return target 的 MVP outcome，不計算 Historical Hit Rate、不產生 probability、confidence、scanner、ranking、dashboard、AI prediction 或投資建議。

## Historical Backtest Engine

Sprint 06 Batch D 新增 deterministic historical backtest aggregation foundation。

Backtest engine 會從 `HistoricalPriceSeries`、`TechnicalIndicatorSeries`、`SignalDefinition` 與 `OutcomeDefinition` 建立 raw signal events、套用指定 overlap policy，並把 Batch C 的 `HistoricalOutcomeResult` 聚合為 `HistoricalBacktestReport`。

Historical Hit Rate（歷史命中率）的 denominator 固定為 `HIT + MISS`，排除 `INCOMPLETE` 與 `NOT_EVALUABLE`。本層不做 future probability、scanner ranking、dashboard、AI prediction、position sizing、transaction cost、stop loss、exit rule 或 strategy P&L。

## Swing Opportunity Scanner

Sprint 06 Batch E 新增 deterministic Swing Opportunity Scanner foundation。

Scanner 接受 caller 提供的一批 symbols，使用最新 available `TechnicalIndicatorSnapshot` 評估指定 `SignalDefinition`，只把目前 `MATCH` 的股票建立為 `SwingOpportunityCandidate`。每個 candidate 會附上相同 config 下的 `HistoricalBacktestReport`、Historical Hit Rate、resolved sample size、MFE / MAE / end-return aggregates、overlap policy、date range、data freshness 與 provisional latest-bar limitation。

Scanner 排序是 versioned research-priority ordering，不是 buy rank、prediction score、hidden composite score 或上漲機率。`NO_MATCH` 只代表目前不符合該 signal definition，`NOT_EVALUABLE` 只代表資料不足或 feature 不可用。

## Historical Case Explorer

Sprint 06 Batch F 新增 deterministic Historical Case Explorer。

Case Explorer 消費 `HistoricalBacktestReport.cases`，為每個歷史 signal/outcome case 建立 chart-ready price window、relative trading-bar index、frozen reference high、first hit metadata、MFE / MAE / end return、signal condition trace 與 signal-date technical snapshot summary。

Streamlit `Historical Cases` tab 採 explicit button workflow；只有按下 `建立歷史案例` 才會讀取 historical prices、建立 technical indicators、執行 backtest 並產生 case views。Filter、sort、case selector、expander 與 chart x-axis toggle 只 render `st.session_state` 中既有結果，不會自動重新 fetch 或 rerun backtest。

`HIT` 只代表指定 historical outcome target 在 horizon 內觸發；`MISS` 只代表完整 horizon 內沒有觸發。這不是交易損益分類，也不是 future probability、prediction、Buy / Sell / Hold 或進出場建議。

## Swing Research Dashboard

Sprint 07 Batch A 新增 deterministic Swing Research Dashboard integration。

此頁把既有 Swing Opportunity Scanner、Historical Backtest Engine 與 Historical Case Explorer 串成單一日常研究 workflow：

```text
輸入股票池
→ 明確按下執行波段掃描
→ 查看 MATCH / NO_MATCH / NOT_EVALUABLE / FAILED summary
→ 查看 Candidate Table
→ 選擇 current MATCH candidate
→ 查看 Current Signal、Historical Backtest Context、Technical Snapshot
→ 查看 Historical Cases Preview 與單張 relative trading-bar chart
```

Scanner 只在使用者按下 `執行波段掃描` 時執行。候選選取、case preview filter、case selection、expander 與 Streamlit rerun 都只重 render `swing_research_*` session state，不會重新抓 Yahoo 或 rerun scanner。

Historical Hit Rate 必須和 Resolved Samples 一起閱讀。它是歷史條件事件比例，不是未來發生機率、confidence、likelihood、AI prediction 或投資建議。Research Priority 是研究檢視順序，不是 recommendation 或交易排序。

## Historical Replay Mode

Sprint 07 Batch C 新增 deterministic Historical As-Of Scan / Replay Mode。

Replay Mode 使用使用者指定的 calendar Replay Date，但每支股票保存自己的 Actual Trading Date，也就是 `trading_date <= replay_date` 的最新可用交易日。Replay signal 只從 as-of sliced price series 重建 technical snapshot；Replay 當時可知的 historical statistics 只包含 replay date 以前已知的 outcomes。Early HIT 可以進入 resolved denominator；MISS 與 MFE / MAE / End Return 必須等完整 trading-bar horizon 已在 replay date 前走完。

Post-Replay Outcome 是獨立事後驗證區塊，不會進入 Research Priority、Historical Hit Rate (As Of)、sample-size status 或其他 ranking inputs。本功能不做 probability、AI prediction、parameter optimization、multi-date walk-forward 或 full market crawler。

## Walk-Forward Replay

Sprint 07 Batch D 新增 Multi-Date Walk-Forward Replay。

Walk-Forward Replay 使用日期產生器建立 Monthly 或 Weekly requested replay dates，並對每一期完整重用 Single-Date `HistoricalReplayService`。Monthly 使用 calendar month end；Weekly 使用 Friday；actual trading date 仍由每支股票在單期 replay 中各自決定。

Walk-forward 結果保存 period timeline、每期 MATCH / NO_MATCH / NOT_EVALUABLE / FAILED counts、candidate occurrences、unique candidate symbols、Post-Replay outcome occurrence counts 與 per-symbol repeated candidate summary。同一 symbol 可在多期重複出現，這些 candidate occurrences 是相關觀察，不是獨立樣本，因此本層不提供 aggregate hit-rate、probability、prediction accuracy 或 trading P&L。

## Out-of-Sample Validation

Sprint 08 Batch A 新增 Out-of-Sample Validation Foundation。

OOS validation 使用固定的 `SignalDefinition`、`OutcomeDefinition`、replay frequency、overlap policy、cooldown 與 minimum resolved samples，比較 `DEVELOPMENT`、`VALIDATION` 與 `HOLDOUT` 三個互不重疊期間的 Walk-Forward Replay / Replay Analytics 結果。三段 period boundaries 為 inclusive，且 Development → Validation → Holdout 必須依時間順序排列。

每次 run 會建立 deterministic frozen research fingerprint，且 `generated_at` 不進 fingerprint。三段結果必須使用相同 fingerprint，表示它們是同一套固定研究規格。OOS service 只限制 requested replay dates；每個 replay date 的 point-in-time signal 與 Historical Hit Rate (As Of) semantics 仍由 `HistoricalReplayService` 保證。

OOS result 保存 candidate period share、unique candidate symbols、candidate occurrences、period-local stability analytics、Post-Replay HIT / MISS / INCOMPLETE / NOT_EVALUABLE counts、Resolved n 與 Historical Hit Rate。Historical Hit Rate denominator 固定為 `HIT + MISS`；`INCOMPLETE` 與 `NOT_EVALUABLE` 不進 denominator，且 zero resolved samples 顯示為 `None` / `N/A`。

Sprint 08 Batch B 在 Streamlit `Swing Research` tab 新增 Out-of-Sample Validation dashboard。它只呈現 descriptive validation facts，不建立 validation score、prediction accuracy、future probability、parameter optimization、Buy / Sell / Hold recommendation 或 strategy P&L。

## Universe Management

Sprint 07 Batch B 新增 Saved Research Universes。

Universe 是使用者指定的 research symbol collection，可建立多個命名股票池並保存 symbol order。Universe 與 Watchlist 分離：Watchlist 仍是單一個人觀察清單，Universe 則是多個命名研究集合。

Universe CRUD 使用 local SQLite，不呼叫 Yahoo Finance、OpenAI 或任何外部服務。Swing Research 選擇 Saved Universe 或 Watchlist 時不會自動掃描；只有按下 `執行波段掃描` 才會執行 scanner。Scan result 會保存當次 symbols snapshot，因此 Universe 後續編輯或刪除不會改寫舊結果。

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
