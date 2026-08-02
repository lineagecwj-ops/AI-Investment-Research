# Learning Log

## 2026-08-02 — Sprint 05 Batch A Output Token Budget Fix

### Completed Features

- 將 `DEFAULT_MAX_OUTPUT_TOKENS` 從 `1200` 調整為 `2400`。
- 調整理由來自第二次 live smoke validation 的可診斷結果：`status = incomplete`、`incomplete_details.reason = max_output_tokens`、`input_tokens = 3515`、`output_tokens = 1152`、`total_tokens = 4667`，且當時 configured `max_output_tokens = 1200`。
- `2400` 提供約 2x MVP headroom，避免 strict structured response 在完成前被截斷；這是 output ceiling，不是要求模型一定輸出 2400 tokens。
- 保留既有 concise developer instructions：summary 2-4 short sentences、findings 3-5 concise items、limitations / missing_information / next_steps up to 3 concise items each。

### Safety Notes

- 本 patch 只修改 output token budget，未修改 `ResearchContext`、selector、Structured Output schema、grounding validation、numeric validation、forbidden-output validation、citation policy、OpenAI model、UI 或 SQLite。
- `AIIncompleteResponseError` diagnostics 保留不變，未來若 2400 仍不足，仍可保留 response ID、reason 與 usage。
- 本 patch 沒有執行新的 live OpenAI request，也沒有 push。

### Testing Notes

- AI service tests 明確確認 `DEFAULT_MAX_OUTPUT_TOKENS == 2400`，且 production generation path 會把 `max_output_tokens = 2400` 傳入 client boundary。

## 2026-08-02 — Sprint 05 Batch A Incomplete Response Diagnostics Patch

### Completed Features

- 新增 `AIIncompleteResponseError`，專門表示 OpenAI Responses API 回傳 `status == "incomplete"` 的 structured-output 中止狀態。
- Incomplete domain error 只保留安全 diagnostics：`response_id`、`incomplete_details.reason`、`input_tokens`、`output_tokens`、`total_tokens`。
- `reason == "max_output_tokens"` 會明確表示 output token budget exhausted before structured response completed。
- `reason == "content_filter"` 會明確表示 provider safety interruption，不會誤判成 token shortage。
- `incomplete_details` 或 usage 缺失時，回傳 generic safe incomplete error，不輸出 raw provider response。
- Developer instructions 小幅收斂 structured answer 長度：summary 2-4 short sentences、findings 3-5 concise items、limitations / missing_information / next_steps up to 3 concise items each。
- `DEFAULT_MAX_OUTPUT_TOKENS` 當時維持 `1200`，因第一次 live smoke test 的舊版程式未保留 `incomplete_details.reason`，當時不能確認 root cause 是 token budget。

### Safety Notes

- 本 patch 未修改 `ResearchContext`、selector、grounding rules、numeric validation、forbidden-output policy、Streamlit UI 或 provider tools。
- Error string 不包含 API key、full payload、partial output、raw response JSON 或 headers。
- Live smoke failure policy 維持：遇到 authentication、quota、rate limit、provider error、structured output error、refusal、grounding / numeric / forbidden validation failure 時回報並停止，不自動 retry。
- 本 patch 沒有重新執行 live OpenAI request。

### Testing Notes

- `tests/test_ai_research_service.py` 新增 incomplete response coverage：max output tokens、response ID preservation、usage preservation、content filter distinction、missing incomplete details、secret / payload non-leakage、completed response path unchanged。
- SDK audit 使用 installed `openai 2.52.0` type definitions 確認 `Response` 具備 `id`、`status`、`incomplete_details`、`usage`、`output`，且 `IncompleteDetails.reason` 支援 `max_output_tokens` / `content_filter`。

## 2026-08-02 — Sprint 05 Batch A Grounded AI Research Foundation

### Completed Features

- 新增 `src/ai_config.py`，集中管理 Grounded AI Research 的 default model、max output tokens、timeout 與 question length guard。
- 新增 `src/ai_research_service.py`，建立第一版 Grounded AI Research service boundary。
- AI service API 接受 `question` 與 `SelectedResearchContext`，不接受完整 `ResearchContext`，也不自行做 selection。
- Production client boundary 使用 OpenAI Responses API，並以 `text.format` 的 strict `json_schema` 要求 structured output。
- 新增 `GroundedResearchAnswer`、`GroundedFinding` 與 `AIResponseMetadata` dataclass，避免 AI 只回傳一大段 Markdown。
- 新增 AI-specific payload builder，只傳 symbol、display name、question type、selected evidence、selected observations、selected missing data、selected limitations、next-step hints 與 period metadata。
- Developer instructions 集中於 AI service，明確限制模型只能使用 selected context、不得新增不存在數字、不得忽略 missing data / limitations、不得產生 Buy / Sell / Hold、target price、score、rating 或 investment recommendation，並要求繁體中文與保留重要英文 financial terminology。
- 新增 deterministic grounding validation：檢查 symbol / question type、finding evidence IDs 不可空白、citation 必須存在於 selected evidence、duplicate IDs normalize、unknown citation reject、forbidden recommendation language reject。
- 加入最小 explicit percentage claim guard，針對 statement 中明確百分比與 cited numeric evidence 做 deterministic consistency check。
- 新增 domain exceptions：`AIResearchError`、`AIConfigurationError`、`AIProviderError`、`AIStructuredOutputError`、`AIGroundingError`。
- `OPENAI_API_KEY` 只在 production client 初始化時讀取；缺少時 raise 清楚錯誤，不印出 secret。
- 測試全部使用 fake client，不需要 network、API key 或 OpenAI billing。
- `requirements.txt` 新增 `openai>=1.99.0`；`.gitignore` 新增 `.env` 與 `.env.*`。
- 新增 `docs/AI_GROUNDED_RESEARCH.md` 記錄 architecture boundary、payload、structured output、validation、error handling 與 non-goals。
- Runtime validation / hardening：安裝 project requirements 後確認 `openai 2.52.0` 與 `pydantic 2.13.4`，並完成 `openai` / `OpenAI` import validation。
- Installed SDK introspection 確認 `OpenAI(api_key=..., timeout=...)` 與 Responses API `responses.create(model=..., input=..., text=..., max_output_tokens=..., store=...)` call shape 可用。
- Production Responses API request 明確加入 `store=False`，維持本 Batch stateless、不保存 provider conversation state。
- Parser 新增 refusal content detection，若 provider 回傳 refusal item，轉成 `AIRefusalError`。
- Provider error mapping 補強 authentication、timeout、rate-limit、connection、status 與 generic provider failure 的 domain exception boundary。

### Safety Notes

- 本 Batch 未接 Streamlit UI，未新增 AI answer SQLite persistence，未建立 conversation database。
- AI request 不提供 web search、file search、code interpreter、function tools 或任何外部工具。
- AI service 不查 Yahoo、不讀 SQLite、不讀完整 ResearchContext、不做 natural-language question classification。
- Citation existence validation 不等於完整 factual verification；目前只額外加入明確 percentage claim 的最小 deterministic guard。
- Forbidden output validation 對 summary、findings、next steps 生效；limitations 中允許出現「本回答不提供 Buy / Sell recommendation」這類 disclaimer。
- Runtime validation 沒有呼叫 OpenAI live API；若後續要做 paid smoke test，需另開明確任務。

### Testing Notes

- 新增 `tests/test_ai_research_service.py`，覆蓋 config override、missing API key、AI-specific payload、fake client generation、strict JSON Schema request、invalid structured response、unknown evidence citation、empty factual citation、unsupported percentage claim、forbidden recommendation language、limitations disclaimer allowance。
- Targeted tests：`.venv/bin/python -m unittest tests.test_ai_research_service`，10 tests passed。
- Full tests：`.venv/bin/python -m unittest discover -s tests`，243 tests passed。
- Hardening 後 `tests.test_ai_research_service` 擴充至 22 tests，新增 request guards、selected-context evidence guard、duplicate citation normalization、outside-selected citation rejection、multi-evidence citation acceptance、prompt-injection structural boundary、provider refusal parsing、fallback SDK-like output parsing、provider error mapping、`store=False` request boundary、與個別 forbidden output terms。

## 2026-08-02 — Sprint 04 Batch B AI-Ready Context Selection

### Completed Features

- 新增 `src/research_context_selector.py`，建立 deterministic AI-ready context selection layer。
- Selector 從既有 `ResearchContext` 選出 `SelectedResearchContext`，不複製完整 context，不查 Yahoo、不讀 SQLite、不碰 UI。
- 新增 `ResearchQuestionType` enum，支援 company overview、profitability、growth、financial health、valuation、market position、五種 historical-specific question、risks and attention、research next steps、general research。
- 新增 `ResearchSelectionRequest`，包含 explicit question type、optional `max_evidence`、以及 observation / missing-data / limitation include flags。
- 集中管理 metric groups 與 question-type policy，避免 selector logic 把 metric 名稱散落在大量 ad hoc branches。
- 建立 historical window policy：historical-specific 保留所有可用年度；current-focused question 保留最新 3 個 relevant historical periods；market position 不帶 historical fundamentals；general research 在 metric scope 內保留完整年度。
- Derived evidence selection 會透過 recursive lineage closure 自動包含 `derived_from` source evidence，並偵測 circular lineage。
- Evidence budget 以 atomic lineage group 套用，避免 budget 把 derived evidence 與 source lineage 拆開。
- Observation selection 改為依 question type、metric relevance、evidence links 與 missing-data links 選取，不再全量帶入 observations。
- `ObservationEvidenceLink.id` 改為 stable semantic ID，不再依賴 list index；`observation_index` 只保留作為 source observation lookup pointer。
- Missing-data selection 根據 metric / period / linked observation relevance 選取，並在 selected context 內 deterministic denoise，例如 source EPS missing 可取代同期間 EPS YoY missing。
- Limitation selection 依 question type 過濾；market position 不帶 annual-only / no-quarterly historical limitation，historical-specific questions 會保留 historical data scope limitations。
- `SelectedResearchContext.to_dict()` 保持 JSON-safe，`ResearchQuestionType` 序列化為 stable string。

### Safety Notes

- 本 Batch 未新增 OpenAI API、ChatGPT API、LLM、prompt template、embedding、vector DB、semantic search、natural-language classifier、AI summary 或 AI recommendation。
- 本 Batch 未修改 Yahoo fetch、SQLite schema、cache TTL、Streamlit UI、dashboard presentation、historical normalization 或 deterministic interpretation rules。
- Selector 不產生 Buy / Sell / Hold、target price、score、rating 或 recommendation。
- Source `ResearchContext.evidence`、`missing_data`、`limitations` 不被 selector mutate。

### Testing Notes

- 新增 `tests/test_research_context_selector.py`，覆蓋 question type stable values、invalid request、Growth、Valuation、Market Position、historical-specific periods、lineage closure、circular lineage、stable observation ID、missing-data denoise、limitation selection、evidence budget、general research subset、serialization、validation 與 no recommendation language。
- 更新 `tests/test_research_context.py` 相關 expectation，確認 observation links 在 `generated_at` 改變時仍 deterministic。
- 新增 `docs/RESEARCH_CONTEXT_SELECTION.md`，記錄 selection boundary、policy、validation 與未來 routing / prompt boundary。

## 2026-08-02 — Sprint 04 Batch A Research Context Foundation

### Completed Features

- 新增 `src/research_context.py`，建立未來 AI Research Assistant、Research Summary、Export、Report generation 共用的 `ResearchContext`。
- Research Context 從已標準化的 `Stock`、`ResearchReport`、`HistoricalFinancialSeries`、`HistoricalResearchReport` 組裝，不直接讀 Yahoo raw dictionary、SQLite row 或 Streamlit widget state。
- Current Snapshot 拆成 Company、Market、Profitability、Growth、Financial Health、Valuation，保留 raw numeric / text values，不使用 UI formatted string 作為 source-of-truth。
- Historical Context 保留 periods、`period_end`、`period_year`、currency、`fetched_at` 與 stale-cache 狀態。
- `EvidenceItem` 改為 per-metric evidence，使用 deterministic IDs，例如 `current:return_on_equity`、`historical:revenue:2025-12-31`、`derived:revenue_yoy:2025-12-31`。
- Derived evidence 保留 `derived_from` lineage，52-week position 連回 current price / 52-week low / 52-week high；Revenue YoY / EPS YoY 連回相鄰 fiscal-period raw evidence。
- 新增 `ObservationEvidenceLink`，不修改既有 `ResearchObservation` dataclass，但在 context 中建立 observation → evidence / missing-data 的外部 traceability mapping。
- `MissingDataItem` 擴充為 structured model，包含 deterministic ID、metric、period、reason、impact 與 source。
- `ResearchLimitation` 擴充為 structured model，分 global limitations 與 context-specific limitations。
- `ResearchContext.to_dict()` 提供 JSON-safe serialization，date / datetime 轉 ISO、tuple 轉 list、`None` 保留。
- Core builder 改為 pure assembler：必須由 caller 傳入 `ResearchReport`，不自行呼叫 research builders、不做 company-name cache lookup、不做 IO。

### Safety Notes

- 本 Batch 未修改 Yahoo fetch、SQLite schema、database cache TTL、Streamlit UI、dashboard formatters、deterministic research rules 或 historical interpretation rules。
- Context builder 不使用 AI / LLM，不產生 Buy / Sell / Hold、target price、score、rating 或 recommendation。
- Missing historical series 會明確進入 `missing_data` 與 `limitations`，不假裝 historical context 已完成。
- Symbol mismatch 會 raise `ResearchContextError`；current / historical currency mismatch 不 raise，但會建立 context limitation。
- Context validation 會阻止 NaN / inf、duplicate evidence IDs、broken derived lineage、broken observation links 與 period year mismatch。

### Testing Notes

- `tests/test_research_context.py` 擴充至 28 tests，覆蓋 pure builder、partial/no-history context、symbol mismatch、currency mismatch、per-metric source evidence、derived evidence、missing-data semantics、observation traceability、serialization、non-finite rejection 與 determinism。
- 新增 `docs/RESEARCH_CONTEXT.md`，記錄 context contract、evidence ID convention、derived lineage、missing data、limitations、serialization 與 validation。

## 2026-08-02 — Sprint 03 Batch C Historical Interpretation UX Polish

### Completed Features

- 新增 `src/historical_interpretation_presentation.py`，把 Historical Interpretation 的 UX selection / grouping / checklist cleanup 從 `app.py` 抽出。
- Historical Interpretation 改為三層 progressive disclosure：Historical Highlights、Detailed Interpretation、Research Next Steps。
- Historical Highlights 從既有 deterministic observations 選取 factual summaries，預設最多 6 項，不建立 score、ranking 或 recommendation。
- Detailed Interpretation 依固定 category order 分組，使用 collapsed `st.expander()`，避免使用者一進區塊就看到大量 observation cards。
- Detailed Interpretation 上方新增顏色說明：藍色是一般歷史資料觀察，黃色是值得進一步確認的研究項目，不代表負面訊號或投資建議。
- Research Next Steps 改為 presentation-level category grouping，使用 trim / lowercase English / exact normalized match 去重，每 category 預設顯示最多 3 項，整頁預設最多 10 個 visible items，overflow 放在 `查看更多研究項目` expander。
- 補上 2454-like Revenue pattern：Revenue 前期下降後連續兩年回升時，產生單一 factual observation，讓 Highlights 可概括 FY2023 decline 與 FY2024 / FY2025 recovery。

### Safety Notes

- 本 UX polish 未修改 Yahoo parsing、SQLite schema、historical cache TTL、YoY calculation、Margin calculation、FCF calculation、CapEx calculation 或 period_year semantics。
- Highlight builder consume existing `HistoricalResearchReport.observations`，不重新查詢資料，也不建立第二套 financial calculation rules。
- Next Steps 去重只做 deterministic normalized exact match，不使用 AI / LLM 或 semantic deduplication。
- FY2026 仍是 fiscal-period label，不描述為 calendar year 或 future forecast。

### Testing Notes

- 新增 `tests/test_historical_interpretation_presentation.py`，覆蓋 highlights count/order/determinism、2454-like recovery highlight、NVDA FY2026 wording、category grouping、attention explanation、next-step dedupe / limit / overflow 與 language safety。
- 更新 `tests/test_historical_research_service.py`，覆蓋 Revenue 前期下降後連續回升 observation。

## 2026-08-02 — Sprint 03 Batch C Historical Trend Interpretation

### Completed Features

- 新增 `src/historical_research_service.py`，建立 deterministic Historical Interpretation layer。
- Historical Interpretation 直接消化 `HistoricalFinancialSeries`，輸出 `HistoricalResearchReport`，並重用 `ResearchObservation` / `ResearchNextStep` 的 explainability contract。
- Revenue observations 支援 latest increase / decline、連續兩期增加、連續兩期下降、前期下降後回升、前期增加後下降、年度 gap 與資料不足。
- Earnings observations 支援 Revenue / Net Income 同向或方向不同、EPS / Net Income 同向、EPS 下降後回升、EPS 連續下降與 latest EPS unavailable。
- Margin observations 使用 percentage-point change，例如 `49.64%` 到 `47.50%` 描述為下降 `2.14 percentage points`，不使用相對百分比誤導。
- Cash Flow observations 支援 OCF / FCF positive or negative、consecutive positive FCF、FCF turns negative、FCF recovery，並以 `abs(capital_expenditure)` 比較 CapEx 現金支出規模。
- Financial Position observations 描述 Cash、Total Debt、Total Assets、Total Equity 的歷史變化；cross-metric observations 限縮在同期間可比較的 Revenue vs Net Income、Revenue vs Operating Margin、Net Income vs FCF、Cash vs Debt。
- Historical Trends UI 新增集中式 `Historical Interpretation（歷史趨勢解讀）` 區塊，放在圖表與 section tables 之後、完整 historical table 之前。

### Safety Notes

- Interpretation 不使用 OpenAI / ChatGPT / LLM，不產生 Buy / Sell / Hold、target price、score、rating 或 overall financial judgment。
- Missing values 不補 `0`；少於 2 個有效年度不建立 trend conclusion。
- 年度 gap 透過 `research_metrics.are_consecutive_years()` 判斷，不建立跨缺漏年度的 consecutive trend。
- `FY2026` 只代表 `period_year` label，不描述為 calendar year 2026。

### Documentation

- 新增 `docs/HISTORICAL_INTERPRETATION_FRAMEWORK.md`。
- 更新 `README.md`、`docs/ARCHITECTURE.md`、`docs/HISTORICAL_TREND_DASHBOARD.md`。

## 2026-08-02 — Sprint 03 Batch B Historical Chart X-axis Label Patch

### Completed Features

- Historical Trends 共用 chart renderer 的 X-axis 套用 `labelAngle=0`。
- Revenue、Net Income、EPS、Margins、Cash Flow、Financial Position charts 皆沿用同一個水平 fiscal-period label 設定。
- Visible chart labels 維持 compact `FY YYYY` format；table labels 與 tooltip `Period End` 仍保留完整 `FY ending YYYY-MM-DD`。
- 本 patch 未修改 period semantics、SQLite、historical data logic、YoY、currency、table formatting 或 tooltip period-end data。

### Testing Notes

- 更新 `tests/test_dashboard.py`，確認 Historical chart X-axis 設定 `labelAngle=0`。

## 2026-08-02 — Sprint 03 Batch B Historical Trend Dashboard UX Polish

### Completed Features

- Historical charts 改用 compact X-axis period labels，例如 `FY 2025`，避免完整 `FY ending YYYY-MM-DD` 造成圖表擁擠。
- Chart tooltip/detail data 保留完整 `Period End`，tables 仍維持 `FY ending YYYY-MM-DD`。
- Earnings 區塊拆成 `Net Income Trend` 與 `EPS Trend` 兩張圖，避免不同尺度共用同一 numeric y-axis；沒有使用 dual-axis chart。
- Missing EPS 在 chart data 中保持 missing，不轉為 `0`。
- Margin charts 維持 raw decimal values，但 visible y-axis 以 percentage 顯示。
- Revenue、Net Income、Cash Flow、Financial Position charts 的 visible y-axis 使用 compact monetary units，並在 axis title 保留 currency context。
- 本 Polish 只改 presentation layer，未修改 historical data fetching、persistence、models、cache semantics、YoY calculation rules、research logic 或 historical financial calculations。

### Testing Notes

- 擴充 `tests/test_dashboard.py`，覆蓋 compact chart period labels、table exact FY-ending labels、Net Income / EPS separate chart datasets、missing EPS remains missing、margin percentage axis formatting、monetary chart raw value preservation。
- Targeted dashboard tests：`.venv/bin/python -m unittest tests.test_dashboard`，36 tests passed。

## 2026-08-02 — Sprint 03 Batch B Historical Trend Dashboard

### Completed Features

- 新增 Streamlit `Historical Trends` tab，保留既有 `Dashboard`、`Research`、`Watchlist`、`Comparison`。
- Historical Trends 支援單一股票研究，查詢 current stock snapshot 與 annual historical fundamentals，並將結果保存在 `st.session_state`。
- 頁面頂部顯示 Symbol、localized company name、historical currency、available annual periods、period range、available periods 與 cache / stale status。
- Revenue 區塊顯示 annual revenue 與 Revenue YoY；YoY 沿用 `research_metrics.py`，只比較連續年度。
- Earnings 區塊顯示 Net Income、EPS 與 EPS YoY；EPS 缺值顯示 `N/A` 與 Yahoo Finance 未提供資料提示，不自行計算。
- Margins 區塊顯示 Gross Margin、Operating Margin、Net Margin，並加入 beginner-friendly 說明與 no direct good / bad judgement wording。
- Cash Flow 區塊顯示 Operating Cash Flow、Capital Expenditure、Free Cash Flow，並明確說明 Yahoo CapEx 負值常代表 cash outflow。
- Financial Position 區塊顯示 Total Assets、Total Debt、Total Equity、Cash，保留 currency context。
- 新增完整 historical table，格式化 Period End、currency amount、percentage、EPS、YoY 與 `N/A`，避免 raw `None` / `NaN` 出現在使用者可見表格。
- `src/dashboard.py` 新增 Historical Trends presentation builders，讓 `app.py` 不解析 Yahoo DataFrame、不處理 row aliases、不執行 SQL、不計算 FCF / margins / YoY。

### Testing Notes

- 擴充 `tests/test_dashboard.py`，覆蓋 overview、currency、stale status、Revenue / EPS YoY、non-consecutive gap YoY `N/A`、missing EPS、partial margin data、negative CapEx display、financial position missing values、NVDA / AAPL-like period labels、full table ordering、no `None` / `NaN` visible、insufficient series。
- Automated tests 不依賴 live Yahoo network。

### Documentation

- 新增 `docs/HISTORICAL_TREND_DASHBOARD.md`。
- 更新 `README.md` 與 `docs/ARCHITECTURE.md`，記錄 Historical Trends scope、data flow、Period End、YoY、missing-data、currency、CapEx 與 no trend classification policy。

### Known Limits

- 本 Batch 不新增 AI / LLM、automatic trend interpretation、recommendation、overall score、target price、quarterly analysis、TTM、FX conversion、technical indicators 或 competitor benchmarking。
- Streamlit native charts 以清楚可讀為主，格式化值由 table 呈現。
- Historical cache freshness 仍是 series-level 狀態。
- Yahoo Finance annual statement coverage 與 row availability 由 provider 控制。

## 2026-08-02 — Sprint 03 Batch A Historical Fundamental Data Foundation

### Completed Features

- 新增 `HistoricalFinancialPeriod` 與 `HistoricalFinancialSeries`，讓 current `Stock` snapshot 與多年 annual financial records 分開。
- 新增 `src/historical_financial_service.py`，集中處理 Yahoo annual `income_stmt`、`cashflow`、`balance_sheet` 的 row label alias normalization。
- Historical margins 由 annual statement 自行計算，不使用 Yahoo snapshot margin。
- Free Cash Flow 優先使用 Yahoo `Free Cash Flow`；缺值時依 live audit 的 CapEx 負值語意，用 `Operating Cash Flow + Capital Expenditure` deterministic derivation。
- 新增 `historical_financials` SQLite table，使用 `(symbol, period_end)` primary key，採 non-destructive upsert。
- Historical fundamentals 使用獨立 7-day TTL；current stock snapshot 仍維持 24-hour TTL。
- Yahoo refresh failure 且 stale historical cache 存在時，回傳 stale series 並標記 `is_stale=True`。
- 新增 deterministic YoY helpers：Revenue、EPS、Net Income through generic field helper；只在 `period_year` 連續時才計算，不做 improving / deteriorating classification。
- `HistoricalFinancialPeriod.period_year` 代表由 `period_end` 取出的年份，不是 Yahoo 官方 fiscal year metadata。

### Live Data Audit Notes

- 代表股票：`2330.TW`、`2454.TW`、`NVDA`、`AAPL`。
- 四支股票目前 raw annual statement columns 皆為 5 個年度。
- Normalized usable MVP periods：`2330.TW` 4、`2454.TW` 5、`NVDA` 4、`AAPL` 4。
- `Capital Expenditure` 在四支代表股票皆為負數，與 Yahoo direct `Free Cash Flow = Operating Cash Flow + Capital Expenditure` 一致。
- 台股 currency context 為 `TWD`，美股為 `USD`；本 Batch 不做 FX conversion。

### Testing Notes

- 新增 `tests/test_historical_financial_service.py`，覆蓋 annual statement parsing、alias priority、missing row、empty DataFrame、NaN、margin、FCF、period sorting、duplicate period、partial data、Yahoo fetch mock、fresh/expired/stale cache API。
- 擴充 `tests/test_database.py`，覆蓋 historical table 初始化、upsert、read、TTL、stale read、stock cache unaffected、legacy `fiscal_year` table migration。
- 擴充 `tests/test_research_metrics.py`，覆蓋 Revenue / EPS / Net Income YoY helper 與 missing-year gap。
- Automated tests 使用 mocked DataFrame 與 temporary SQLite，不依賴 live Yahoo network。

### Modified / Added Files

- 新增 `src/historical_financial_service.py`
- 新增 `tests/test_historical_financial_service.py`
- 新增 `docs/HISTORICAL_FUNDAMENTAL_DATA_AUDIT.md`
- 修改 `src/models.py`
- 修改 `src/database.py`
- 修改 `src/research_metrics.py`
- 修改 `tests/test_database.py`
- 修改 `tests/test_research_metrics.py`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Known Limits

- 本 Batch 不新增 Research UI、chart、technical analysis、AI / LLM、Buy / Sell / Hold、quarterly persistence、TTM 或 FX conversion。
- Yahoo row labels 與 historical coverage 由 provider 控制，文件中的代表性 audit 不是全市場保證。
- Partial period 會保留；完全沒有 MVP modeled value 的 raw annual column 會被 filtered out。
- Provider Capital Expenditure sign convention must be validated before relying on derived FCF where Yahoo direct FCF is unavailable.
- Historical series freshness currently uses the latest row `fetched_at`; per-row freshness is not separately exposed to callers.

## 2026-08-02 — Sprint 02 Batch C MOEA Runtime Integration Patch

### Completed Features

- 修正 MOEA 公司登記資料 parser，支援 real API schema：top-level company record 內的 nested `Cmp_Business` list，並從每個 item 讀取 `Business_Item_Desc`。
- 保留舊式 top-level `Business_Item_Desc` parsing 作為 backward-compatible support。
- 空值、malformed nested item、重複營業項目會被忽略或去重，並保留原始順序。
- 改善 MOEA transport / response error 訊息，區分 TLS certificate verification、HTTP、invalid JSON、response type、schema parse / no business item 等失敗原因。
- TWSE `產業別` 若為純數字 code，例如 `24`，不再顯示成「屬於 24 產業」；本 Patch 不新增產業 code mapping。

### TLS Notes

- 在目前 Python runtime 中，MOEA HTTPS endpoint 仍發生 `SSL: CERTIFICATE_VERIFY_FAILED` / `Missing Subject Key Identifier`。
- 使用 `certifi` CA bundle 仍無法通過該 endpoint 的憑證驗證。
- 程式沒有關閉 SSL verification；MOEA transport failure 時維持 Yahoo Finance English fallback。

### Testing Notes

- `tests/test_company_summary_service.py` fixture 已改成 nested `Cmp_Business` real schema。
- 新增測試涵蓋 2454-like / 2330-like nested response、empty / missing / malformed nested data、duplicate `Business_Item_Desc`、flat field backward compatibility。
- Tests 不依賴 live network。

### Modified Files

- 修改 `src/company_summary_service.py`
- 修改 `tests/test_company_summary_service.py`
- 修改 `docs/COMPANY_SUMMARY_LOCALIZATION.md`
- 修改 `docs/LEARNING_LOG.md`

## 2026-08-01 — Sprint 02 Batch C Company Summary Semantics Patch

### Completed Features

- 將台股官方中文 summary 的 UI 標題改為「公司登記業務概覽」，避免把登記營業項目誤讀為完整公司簡介。
- 官方中文內容旁新增明確資料說明：內容來自台灣官方公司登記與公開基本資料，僅用於了解公司登記業務範圍，不代表各項業務實際營收占比、主要產品或核心業務。
- 官方完整內容 expander 改為「查看完整登記營業項目」。
- 若 `Stock.company_summary` 有 Yahoo Finance 原始英文介紹，Research Company Overview 一律提供「查看 Yahoo Finance 詳細公司介紹」expander。
- `Stock.company_summary`、SQLite `company_summary`、Yahoo `longBusinessSummary` mapping 皆未修改。

### Testing Notes

- 更新 `tests/test_company_summary_service.py`，覆蓋 official localized summary 與 Yahoo original detailed summary 同時保留。
- 測試明確禁止把官方登記資料描述為「主要從事」。
- 測試確認 disclaimer 包含登記業務範圍、非實際營收占比、非主要產品、非核心業務語意。

### Modified Files

- 修改 `src/company_summary_service.py`
- 修改 `app.py`
- 修改 `tests/test_company_summary_service.py`
- 修改 `docs/COMPANY_SUMMARY_LOCALIZATION.md`
- 修改 `docs/LEARNING_LOG.md`

## 2026-08-01 — Sprint 02 Batch C UX Localization Patch

### Completed Features

- Research 頁面使用者可見文字移除 `snapshot`、`growth snapshot`、`fundamental snapshot` 等偏工程詞彙，改為「目前資料」、「目前可取得的基本面資料」、「Yahoo Finance 提供的近期成長數據」。
- 保留研究安全語意：近期成長數據不代表多年長期趨勢，negative earnings growth 仍明確說明不能直接判定原因。
- 新增 `src/company_summary_service.py`，提供 presentation-only company summary display helper。
- Company Overview 改為預設顯示短版「公司簡介」，完整內容放入 `查看完整公司介紹` expander。
- 台股公司簡介優先使用官方公開資料整理，不覆寫 `Stock.company_summary`、不修改 SQLite cache、不改 Yahoo Finance mapping。

### Source Audit

- TWSE listed company profile：`https://openapi.twse.com.tw/v1/opendata/t187ap03_L`
- TPEx OTC company profile：`https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O`
- MOEA company registration business items：`https://data.gcis.nat.gov.tw/od/data/api/236EE382-4942-41A9-BD03-CA0709025E7C`
- TWSE / TPEx profile 可提供公司代號、公司名稱、產業別、統編等欄位；MOEA 公司登記資料可用統編取得營業項目。
- 本 Patch 未做通用英文到繁中機器翻譯；若沒有可靠中文內容，會顯示 Yahoo Finance 英文介紹。

### Testing Notes

- 新增 `tests/test_company_summary_service.py`。
- 更新 `tests/test_research_service.py`，確認 user-facing source 不再包含 `snapshot`，並保留「不代表多年長期趨勢」與「不能直接判定原因」。
- Tests 使用 mock official responses，不依賴 live network。

### Modified / Added Files

- 新增 `src/company_summary_service.py`
- 新增 `tests/test_company_summary_service.py`
- 新增 `docs/COMPANY_SUMMARY_LOCALIZATION.md`
- 修改 `.gitignore`
- 修改 `app.py`
- 修改 `src/dashboard.py`
- 修改 `src/research_service.py`
- 修改 `tests/test_research_service.py`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Known Limits

- 官方營業項目不是完整自然語言公司介紹；目前是 beginner-friendly official business-item summary。
- 非台股或缺少官方營業項目時，仍 fallback Yahoo Finance 英文原文。
- Runtime cache `data/taiwan_company_summaries.json` 不進 Git。

### Code Review Focus

- `src/company_summary_service.py` 是否只處理 presentation localization，不改 raw model / cache semantics。
- `app.py` Company Overview 是否避免長文佔滿首屏。
- `src/research_service.py` / `src/dashboard.py` 使用者可見文字是否自然且仍保留 data-safety meaning。

## 2026-08-01 — Sprint 02 Batch C Research Explainability

### Completed Features

- 將 `ResearchObservation` 從單一 `message` 改為三段式結構：`what_happened`、`why_it_matters`、`what_to_check`。
- Valuation observation 與 Risk Signals 使用同一個 structured observation contract。
- Risk Signals 負責說明目前 snapshot 發現什麼、為什麼值得研究、下一步查什麼。
- Research Next Steps 改為彙整式 checklist，不再重複 Risk Signal 的完整說明文字。
- 改善 negative earnings growth：若 `revenue_growth` 有值，Observation 會一起顯示 Revenue Growth 作為 snapshot context；若缺值則不補寫營收 context。
- 新增 `src/research_glossary.py`，提供固定 deterministic glossary。
- Research UI 新增「研究名詞說明」expander，涵蓋一次性 / 非經常性項目、Margin、Cash Flow、Debt、Valuation。

### Safety Notes

- `what_happened` 只描述目前資料直接支持的 snapshot 事實。
- `why_it_matters` 只說明研究價值，不把可能原因寫成公司事實。
- Tests 覆蓋 causal wording protection、no recommendation language、snapshot safety、Risk Signal / Next Step 去重。
- 本 Batch 未新增 AI / LLM、News、historical fundamental database、technical indicators、portfolio 或 SQLite schema 變更。

### Testing Notes

- 新增 / 更新 `tests/test_research_service.py`，涵蓋 structured observation、negative earnings context、glossary、partial data 與 renderer source checks。

### Modified / Added Files

- 新增 `src/research_glossary.py`
- 修改 `src/research_service.py`
- 修改 `app.py`
- 修改 `tests/test_research_service.py`
- 修改 `docs/RESEARCH_FRAMEWORK.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Known Limits

- Checklist 仍是研究待辦，系統尚未有 historical fundamental table 可直接回答歷史趨勢問題。
- Glossary 是固定內容，沒有搜尋、分類樹或使用者自訂條目。
- Snapshot context 仍依賴 Yahoo Finance 欄位可用性；缺值時會保留 N/A 與資料限制。

### Code Review Focus

- `src/research_service.py` 的 deterministic wording 是否仍符合 explainability contract。
- `tests/test_research_service.py` 的 safety tests 是否覆蓋足夠的 forbidden wording 與 recommendation terms。
- `app.py` renderer 是否只顯示 structured observation，不回到 free-form message。
- `src/research_glossary.py` 是否維持 beginner-friendly 且不過度延伸。

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
- Yahoo `debtToEquity` raw numeric value 以百分比尺度解讀，Research page 顯示同一數值加 `%`，例如 `15.174` 顯示為 `15.17%`，不乘以 `100`。
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
