# Learning Log

## 2026-08-09 — V1 Historical Condition Diagnostics Batch 1

### Completed Features

- 新增 `src/signal_condition_diagnostics_service.py`，建立 deterministic V1 historical condition diagnostics foundation。
- 新增 frozen models：`HistoricalConditionDiagnosticsConfig`、`ConditionDiagnosticObservation`、`ConditionPassSummary`、`MatchCountDistributionRow`、`MissingConditionSummary`、`ConditionCombinationSummary`、`SymbolConditionDiagnosticsSummary` 與 `HistoricalConditionDiagnosticsResult`。
- Diagnostics 逐 historical `TechnicalIndicatorSnapshot` 重用既有 `evaluate_signal_conditions()`，不平行重寫 `technical_example_v1` 五項條件。
- Result 保存 aggregate 與 per-symbol summaries，包含 0/5～5/5 distribution、single-condition pass rate、4/5 missing condition distribution 與 canonical condition combinations。
- `NOT_EVALUABLE` observation 保留 traceability，但不當成 `0/5`，也不進 evaluated denominator。
- 擴充 `src/ui_terminology.py`，集中 `V1 歷史條件診斷`、`歷史條件命中分布`、`符合條件數`、`單一條件通過率`、`未符合條件`、`條件組合` 等繁中 terminology 與 beginner explanations。
- 新增 `docs/V1_HISTORICAL_CONDITION_DIAGNOSTICS.md`，並更新 README 與 ARCHITECTURE。

### Safety Notes

- 本 Batch 不修改 `technical_example_v1`、signal / outcome definition、scanner threshold、scanner decision logic、technical formulas、backtest、ranking、Historical Replay、Walk-Forward Replay、Replay Analytics、OOS、database schema 或 OpenAI / AI logic。
- Batch 1 不計算 HIT / MISS、Historical Hit Rate、MFE、MAE、End Return、future breakout 或 future probability。
- `符合條件數` 只是 factual condition count，不是 score、Buy Score、Opportunity Score、Win Rate、Recommendation、買點、買進建議或預測成功率。
- Service 使用 injected `TechnicalIndicatorSeries` 時不抓 Yahoo；若由 service 載入 symbol，每個 symbol 只建立一次 technical series 再逐日期評估。

## 2026-08-08 — V1.0 Post-Release UX Technical Condition Detail

### Beginner Visual Bars Update

- `技術條件明細` 的 `視覺化理解` 改為三個獨立 beginner-friendly visual bars：`成交量活躍度`、`RSI 動能`、`接近前高程度`。
- 三個 visual 不再共用單一 numeric axis；成交量比率、RSI、距離前高分別使用自己的 deterministic scale / domain。
- 每個 visual 顯示 scan-time current value、V1 threshold / range、既有 scanner PASS / FAIL status、neutral gap 與短白話說明。
- 完整詳細表格仍保留，visual 只作為 beginner education layer。
- 本次不新增 score、probability、recommendation、買點、值得買、即將突破或任何 AI analysis。

### Completed Features

- Current Scan `掃描結果摘要` 後新增 `技術條件明細`，支援 `MATCH` 與 `NO_MATCH` 股票查看完整技術條件。
- `SwingScannerResult` 新增 scan-time `current_signal_details`，保存既有 `SignalMatch` trace，讓 `NO_MATCH` 也能顯示 actual technical values、V1 thresholds 與 condition PASS / FAIL。
- 新增 beginner-friendly condition detail helper，顯示 `符合 X / 5 項技術條件`、`趨勢`、`成交量`、`動能`、`接近前高程度`、actual value vs threshold、neutral gap、RSI / volume ratio / distance-to-high visual marker rows、指標說明與 developer traceability。
- 新增 focused coverage 驗證 `NO_MATCH` detail 不跑 backtest、actual values 來自 scan-time snapshot、PASS / FAIL 來自 scanner condition status、missing metric 顯示 `N/A`、primary rows 不暴露 raw snake_case、helper 不 fetch Yahoo / rerun scanner / rerun backtest、helper 不 mutation result。
- 新增 `docs/TECHNICAL_CONDITION_DETAIL.md`，並更新 README 與 Swing Research Dashboard 文件。

### Safety Notes

- 本次只做 presentation / education UX；沒有修改 `technical_example_v1`、signal / outcome definition、technical calculation formulas、scanner thresholds、ranking、historical backtest、replay、walk-forward replay、OOS、database schema 或 OpenAI logic。
- `符合 X / 5` 只是 factual condition count，不是 Buy Score、Opportunity Score、future probability、recommendation 或交易排序。
- Gap 只顯示距離門檻的中性數值，不轉換成成功機率、買點、預期報酬或建議。

## 2026-08-08 — V1.0 Daily Swing Research Ready

### Release Readiness

- Production readiness review completed for baseline `25029dc1fb46b30710d9b03e0732608e8b34635e`.
- Full test suite passed with 746 tests.
- `compileall`, `git diff --check`, secret / runtime safety, DB startup / migration, Streamlit startup, navigation smoke, and Swing Current Scan smoke all passed.
- No production blocker was found.
- Current baseline is ready to be designated `V1.0 — Daily Swing Research Ready`.

### Operating Notes

- V1.0 begins the real-world usage period for Daily Swing Research.
- Future changes should be driven by observed usage, workflow friction, review evidence, and production safety needs rather than feature accumulation.
- Preserve current signal / outcome / ranking / replay / OOS semantics unless a future usage review identifies a concrete reason to change them.

## 2026-08-08 — Sprint 08 Batch B OOS Validation Dashboard

### Completed Features

- 新增 `src/oos_validation_dashboard.py`，負責 OOS dashboard formatters、period summary rows、cross-period comparison rows、percentage-point deltas、symbol presence table、period-local stability rows、chart-ready data、safe failure rows、source snapshot helper 與 deterministic UI request fingerprint。
- Streamlit `Swing Research` 新增 `Out-of-Sample Validation` scan mode，支援 Manual / Watchlist / Saved Universe source、Development / Validation / Holdout date inputs、Monthly / Weekly replay frequency、Overlap Policy、Cooldown、Historical Start 與 Preferred Resolved Sample Minimum。
- OOS validation 只在使用者按下 `執行樣本外驗證` 時執行；selector、expander、chart、table 與 rerun 都只 render `oos_validation_*` session-state result。
- 結果頁顯示 Research Specification Fingerprint、Same Specification Across All Periods、Frozen Research Specification、三段 period summary、Cross-Period Comparison、Factual Observations、Candidate Count chart、Candidate Period Share chart、Historical Hit Rate + Resolved n chart、Outcome Counts、Cross-Period Symbol Presence、period-local Candidate Stability 與 Safe Failure Summary。
- 新增 `tests/test_oos_validation_dashboard.py`，以 focused tests 鎖住 formatter、zero resolved N/A、n display、comparison order、outcome counts、missing symbols、zero candidates、neutral observations、fingerprint、source snapshot、zero replay dates、safe failures 與 chart data defaults。

### Safety Notes

- Historical Hit Rate 仍是 `HIT / (HIT + MISS)`，畫面固定和 `Resolved n` 一起呈現；zero resolved 顯示 `N/A`。
- Candidate Period Share 顯示 numerator / denominator / percentage，並明確說明它不是未來機率或訊號品質。
- Difference columns 只顯示 raw differences；percentage metrics 使用 percentage points，不做 relative change。
- Dashboard 不建立 validation score、robustness score、hidden score、parameter optimization、AI interpretation、prediction accuracy、Buy / Sell / Hold recommendation 或 strategy P&L。
- 清除樣本外驗證結果只清 `oos_validation_*` session state，不清 Swing Research、Universes、Watchlist、AI Research 或 price cache。
- 本 Batch 是 planned V1.0 release review 前的 validation visualization layer，不直接宣布 V1.0 production ready。

### Modified / Added Files

- 新增 `src/oos_validation_dashboard.py`
- 新增 `tests/test_oos_validation_dashboard.py`
- 新增 `docs/OOS_VALIDATION_DASHBOARD.md`
- 修改 `app.py`
- 修改 `tests/test_dashboard.py`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`
- 修改 `docs/OUT_OF_SAMPLE_VALIDATION.md`
- 修改 `docs/SWING_RESEARCH_DASHBOARD.md`

## 2026-08-08 — Sprint 08 Batch A Out-of-Sample Validation Foundation

### Completed Features

- 新增 `src/out_of_sample_validation_service.py`，提供 deterministic OOS validation foundation。
- 新增 `ValidationPeriodRole`、`ValidationPeriod`、`FrozenResearchSpecification`、`OutOfSampleValidationConfig`、`OutOfSamplePeriodResult`、`CrossPeriodComparison` 與 `OutOfSampleValidationResult`。
- 支援 `DEVELOPMENT`、`VALIDATION`、`HOLDOUT` 三個 frozen period roles，period start/end 為 inclusive，並拒絕 overlap、反向日期與 Development → Validation → Holdout 順序錯誤。
- 建立 deterministic research fingerprint，保存 fixed SignalDefinition、OutcomeDefinition、replay frequency、overlap policy、cooldown、historical start 與 minimum resolved samples；`generated_at` 不進 fingerprint。
- OOS run 會對 normalized symbols 載入一次 full `HistoricalPriceSeries`，並跨三段 period roles 共用 cache；每個 replay date 仍交由 `HistoricalReplayService` 保證 point-in-time semantics。
- 每個 period result 保存 requested/completed replay periods、candidate period share、unique candidate symbols、candidate occurrences、Post-Replay HIT / MISS / INCOMPLETE / NOT_EVALUABLE counts、Resolved n 與 Historical Hit Rate。
- Period-local stability analytics 直接 reuse `ReplayAnalyticsService`，不混入其他 period 的 candidate history。
- Cross-period comparison 只保存 transparent raw-fact differences 與 candidate-set Jaccard similarity，不建立 hidden score。
- Provider failure 會隔離為該 symbol 的 empty stale price series，避免 validation run 崩潰或每期重複 refetch。

### Safety Notes

- Historical Hit Rate denominator 維持 `HIT + MISS`；`INCOMPLETE` 與 `NOT_EVALUABLE` 只保留為 count，不進 denominator。
- `Resolved n == 0` 時 Historical Hit Rate 為 `None` / `N/A`，不是 `0%`。
- Holdout result 不會回流修改 Development / Validation result、signal / outcome definition、cooldown、frequency、minimum samples 或 ranking rule。
- 本 Batch 不做 probability model、parameter optimization、threshold tuning、best signal / outcome / cooldown / horizon selection、Buy / Sell / Hold recommendation、position sizing、strategy P&L、full dashboard 或 Batch B。

### Modified / Added Files

- 新增 `src/out_of_sample_validation_service.py`
- 新增 `tests/test_out_of_sample_validation_service.py`
- 新增 `docs/OUT_OF_SAMPLE_VALIDATION.md`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Testing Notes

- 新增 `tests/test_out_of_sample_validation_service.py`，覆蓋 period validation、inclusive overlap rejection、deterministic fingerprint、generated_at exclusion、relevant setting sensitivity、三段 result separation、replay date separation、price loader reuse、zero candidates、zero resolved samples、INCOMPLETE / NOT_EVALUABLE denominator exclusion、candidate period share、period-local analytics、Holdout mutation safety、Validation mutation safety、fixed fingerprint、no optimization / recommendation fields、mixed-market symbols、provider failure isolation 與 deterministic ordering。

## 2026-08-08 — Sprint 07 Batch E Replay Analytics & Stability Review

### Completed Features

- 新增 `src/replay_analytics_service.py`，提供 deterministic analytics layer，直接消費既有 `WalkForwardReplayResult`。
- 新增 frozen `ReplayAnalyticsConfig`、`ReplayPeriodSummary`、`ReplaySymbolSummary`、`ReplayCandidateOccurrence`、`ReplayOutcomeDistribution`、`ReplayCandidateSetTransition`、`ReplayStabilitySummary` 與 `ReplayAnalyticsResult`。
- Period-level analytics 保留所有 replay periods，包含 zero-MATCH periods、candidate symbols、NO_MATCH / NOT_EVALUABLE / FAILED counts 與 Post-Replay Outcome counts。
- Symbol-level analytics 計算 candidate occurrence count、first / last appearance、Candidate Period Share、longest consecutive candidate periods、Research Priority rank best / median / worst 與 Post-Replay Outcome distribution。
- Consecutive appearance 使用 walk-forward result 的 replay period ordering，不使用 calendar-day 或 month gap 推斷。
- Candidate Set Stability 以 consecutive period candidate set 計算 Jaccard Similarity 與 Candidate Set Turnover；兩期皆 empty 時 similarity = 1.0、turnover = 0.0。
- Swing Research 的 Walk-Forward Replay 結果下方新增 Replay Analytics 區塊：Stability Summary、Candidate Occurrence、Period Timeline、Candidate Set Stability 與 Post-Replay Outcome Counts。

### Design Notes

- Batch E 是 existing replay result 的描述性 analytics layer，不抓 Yahoo、不重新 Historical Replay、不重新 scanner、不重新 backtest、不新增 persistence。
- Candidate Period Share 是有 candidate 的 replay periods 比例，或單一 symbol 出現於 replay periods 的比例，不是 future probability。
- Research Priority stability 只反映 replay 當時 candidate ordering；Post-Replay Outcome 不會回頭改 candidate occurrence、candidate dates、consecutive appearance 或 rank history。
- Post-Replay Outcome Counts 是事後驗證資訊，不建立 aggregate Walk-Forward Hit Rate、success rate、accuracy、win rate、strategy P&L 或 prediction metric。
- Dashboard table / expander / selector rerun 只 render session-state result 和 analytics helper，不觸發 provider、replay 或 backtest。

### Modified / Added Files

- 新增 `src/replay_analytics_service.py`
- 新增 `tests/test_replay_analytics_service.py`
- 新增 `docs/REPLAY_ANALYTICS_STABILITY.md`
- 修改 `src/swing_research_dashboard.py`
- 修改 `tests/test_swing_research_dashboard.py`
- 修改 `app.py`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/LEARNING_LOG.md`

### Known Limits

- Replay Analytics 仍是 session-only，沒有 SQLite persistence。
- 無 statistical significance testing、confidence intervals 或 out-of-sample model selection。
- Candidate appearances 可能序列相關，overlapping historical windows 不保證獨立。
- 結果仍受 selected universe、SignalDefinition、OutcomeDefinition、replay frequency、survivorship bias 與 Yahoo data-source limitations 影響。
- 本 Batch 不做 probability model、recommendation engine、strategy simulator、parameter optimization、ML / AI ranking、scheduled scan 或下一個 Batch。

## 2026-08-08 — Sprint 07 Batch D Multi-Date Walk-Forward Replay

### Completed Features

- 新增 `src/walk_forward_replay_service.py`，提供 deterministic Multi-Date Walk-Forward Replay orchestration。
- 新增 frozen `WalkForwardReplayConfig`、`WalkForwardReplayPeriod`、`WalkForwardReplayResult`、`WalkForwardReplaySummary` 與 `WalkForwardSymbolSummary`。
- `generate_replay_dates()` 支援 `MONTHLY` 與 `WEEKLY`：Monthly 使用 calendar month end；Weekly 使用 Friday；date range inclusive。
- Walk-forward 每期完整重用 `HistoricalReplayService`，不重新實作 replay signal、as-of historical statistics、Research Priority 或 Post-Replay Outcome。
- Walk-forward run 開始時每個 normalized symbol 載入 full `HistoricalPriceSeries` 一次，並透過 run-local memory cache 傳入每期 replay。
- Summary 顯示 period counts、candidate occurrences、unique candidate symbols、Post-Replay outcome occurrence counts 與 repeated symbol summaries。
- Swing Research 新增第三種 `Scan Mode`：Current / Historical Replay / Walk-Forward Replay，並加入 Period Timeline、Period Detail 與 Candidate Frequency。

### Design Notes

- Walk-forward repeated replay 是 historical research simulation，不是 trade strategy backtest。
- Candidate occurrences 是相關觀察；同一 symbol 可在相鄰 replay periods 重複出現，不能直接當成獨立樣本。
- 本 Batch 不建立 aggregate walk-forward hit-rate、probability、prediction accuracy、win rate 或 trading P&L。
- `end_date` 只限制 requested replay dates；Post-Replay Outcome 仍可使用 end date 之後已存在的 future bars 進行事後驗證。
- Period results 以 tuple 保存 oldest to newest；後續 period 不應 mutation 先前 period snapshot。
- Frequency 是 replay cadence，不是 optimization target；不得用 Monthly vs Weekly 結果選出「最佳頻率」。

### Modified / Added Files

- 新增 `src/walk_forward_replay_service.py`
- 新增 `tests/test_walk_forward_replay_service.py`
- 新增 `docs/WALK_FORWARD_REPLAY.md`
- 修改 `src/historical_replay_service.py`
- 修改 `app.py`
- 修改 `src/swing_research_dashboard.py`
- 修改 `tests/test_swing_research_dashboard.py`
- 修改 `tests/test_dashboard.py`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/SWING_RESEARCH_DASHBOARD.md`
- 修改 `docs/HISTORICAL_REPLAY_MODE.md`
- 修改 `docs/LEARNING_LOG.md`

### Known Limits

- Walk-forward result 仍是 session-only，沒有 SQLite persistence。
- UI 沒有 cancel / resume / background job。
- Weekly 已在 service 與 UI 開放，但沒有 market-specific holiday calendar；actual trading date 仍交由 per-symbol Single-Date Replay 決定。
- 本 Batch 不做 rank movement chart、frequency optimization、aggregate probability 或 strategy simulator。

## 2026-08-08 — Sprint 07 Batch C Historical As-Of Replay

### Completed Features

- 新增 `src/historical_replay_service.py`，提供 deterministic single-date Historical Replay scan。
- 新增 frozen `HistoricalReplayConfig`，保存 replay date、signal / outcome definition、overlap policy、cooldown、historical start date 與 preferred resolved samples。
- Replay service 接受 caller 已解析的 symbols，不負責 Manual / Watchlist / Saved Universe source resolution。
- Replay Date 是使用者指定的 calendar date；Actual Trading Date 是每支股票 `trading_date <= replay_date` 的最新 available bar。
- Replay signal path 使用 `slice_price_series_as_of()` 後的 price series 重建 technical indicators，避免 future bars 影響 replay signal。
- 新增 `PointInTimeBacktestSummary`：HIT 只在 first target-hit date 已知時進 denominator；MISS 只在完整 trading-bar horizon 已完成時進 denominator；MFE / MAE / End Return 只使用完整 horizon 已知的 cases。
- Replay MATCH candidate 另建 `post_replay_outcome`，只作為事後驗證，不進入 Historical Hit Rate (As Of)、Resolved n (As Of)、SampleSizeStatus 或 Research Priority。
- Swing Research 增加 `Scan Mode`：Current / Historical Replay，Replay mode 使用明確 `Replay Date` 與 `執行 Replay Scan`。

### Design Notes

- Replay 比單純 date slicing 更難，因為 historical statistics 自身也會洩漏未來。
- Early HIT 已經可以知道 outcome status，但完整 horizon 前的 MFE / MAE / End Return 仍不可用。
- MISS 不能靠 today full-history 倒灌；必須等 replay date 當時已經走完整個 trading-bar horizon。
- Ranking reuse `swing_research_rank_v1` 是可行的，但 rank inputs 必須全部來自 point-in-time summary。
- Post-Replay Outcome 是「回放後實際結果」，不是 prediction result 或系統預測成功。

### Modified / Added Files

- 新增 `src/historical_replay_service.py`
- 新增 `tests/test_historical_replay_service.py`
- 新增 `docs/HISTORICAL_REPLAY_MODE.md`
- 修改 `app.py`
- 修改 `src/swing_research_dashboard.py`
- 修改 `tests/test_swing_research_dashboard.py`
- 修改 `tests/test_dashboard.py`
- 修改 `README.md`
- 修改 `docs/ARCHITECTURE.md`
- 修改 `docs/SWING_RESEARCH_DASHBOARD.md`
- 修改 `docs/LEARNING_LOG.md`

### Known Limits

- 本批只支援 single-date replay。
- 尚未做 monthly / daily walk-forward replay。
- 尚未做 replay result persistence、DB schema、alert、AI prediction、parameter optimization 或 full market crawler。
- Replay outcome chart 使用既有 Historical Case chart builder 顯示單一事後驗證案例；future bars 不得影響 replay signal / ranking。

## 2026-08-08 — Sprint 07 Batch B Universe Management

### Completed Features

- 新增 frozen `ResearchUniverse` domain model，包含 stable `id`、required `name`、optional `description`、ordered normalized `symbols`、UTC `created_at` / `updated_at` 與 `symbol_count`。
- 新增 SQLite tables：`research_universes` 與 `research_universe_symbols`，由 `initialize_database()` additive 建立，並以 `position` 保存使用者 symbol order。
- 新增 `src/universe_service.py`，集中 Universe CRUD、domain validation、case-insensitive duplicate name rejection、transactional multi-table writes、explicit membership delete 與 corruption checks。
- 新增 `src/universe_dashboard.py`，集中 symbol text parser、Universe labels、source snapshot、content fingerprint 與 form helper；不含 SQL、Yahoo、OpenAI 或 scanner calls。
- Streamlit 新增 `Universes` tab，可建立、編輯、刪除自訂研究股票池；刪除需明確勾選確認。
- Swing Research `Scan Setup` 新增 `Symbol Source`，支援 Manual Input、Watchlist、Saved Universe；Manual Input 保留原本 multi-line workflow。
- Swing Research 保存 scan-time source snapshot，包含 source type、Universe id/name 與當次 normalized symbols，避免 Universe 編輯或刪除後改寫舊結果。
- Scan fingerprint 加入 source mode 與 resolved normalized symbols，Universe membership 改變後會提示目前設定與已存結果不同。

### Safety Notes

- Universe 與 Watchlist 分離：Watchlist 是單一個人觀察清單，Universe 是多個命名 research symbol collections。
- Universe membership 不代表看多、推薦、Buy list、AI 選股、預測上漲或較高勝率。
- Universe CRUD 全程 local-only，不呼叫 Yahoo Finance、OpenAI、scanner、backtest、signal 或 outcome services。
- Empty Universe 允許保存，但 Swing Research 不會對 zero-symbol Universe 執行 scanner。
- 本 Batch 不新增全市場 crawler、built-in index universe、自動產業分類、AI Universe generation、CSV export、定時掃描或 alerts。
- 未修改 `swing_research_rank_v1`、`technical_example_v1`、`raw_high_breakout_60d_within_20d_v1` 或 Historical Hit Rate denominator。

### Testing Notes

- 新增 `tests/test_universe_service.py`，覆蓋 table creation、create/read/list/update/add/remove/replace/delete、empty universe、duplicate name、timestamp stability、symbol normalization / dedupe / order、cascade cleanup、not found、validation 與 corrupt data detection。
- 新增 `tests/test_universe_dashboard.py`，覆蓋 parser、labels、updated-at formatting、source snapshot、source/content fingerprint、form defaults、large-universe warning helper 與 length helper。
- 擴充 `tests/test_database.py`、`tests/test_swing_research_dashboard.py` 與 `tests/test_dashboard.py`，確認 Universe tables、source-mode fingerprint、content-change fingerprint、Swing Research source selector 與 Universe management entry。

## 2026-08-08 — Sprint 07 Batch A Swing Research Dashboard Integration

### Completed Features

- 新增 `src/swing_research_dashboard.py`，集中 Swing Research Dashboard 的 display formatter、scan fingerprint、candidate table、condition trace、technical snapshot、NO_MATCH / NOT_EVALUABLE / failure detail 與 Historical Cases Preview helper。
- Streamlit 新增 `Swing Research` tab，作為 Swing Scanner、Historical Backtest Context 與 Historical Cases Preview 的整合入口；既有 `Historical Cases` tab 保留 standalone access。
- Scan Setup 支援 multi-line / comma / semicolon 股票池輸入，並沿用 shared symbol normalization。
- UI 第一版固定使用 `technical_example_v1` 與 `raw_high_breakout_60d_within_20d_v1`，並以 expander 顯示 signal / outcome definition。
- Scanner 只在使用者明確按下 `執行波段掃描` 時執行；candidate select、case preview filter、case selector、expander 與 Streamlit rerun 都只重 render session result。
- 新增 `swing_research_*` session namespace：`swing_research_result`、`swing_research_config_fingerprint`、`swing_research_last_error`、`swing_research_price_series_by_symbol`。
- Scan-time price loader wrapper 收集每支股票的 `HistoricalPriceSeries`，供後續 case preview 使用；candidate select 不重新 fetch Yahoo，也不 rerun scanner / backtest。
- Candidate table 顯示 Research Priority、Historical Hit Rate、Resolved n、HIT / MISS、Median MFE / MAE / End Return、Median Hit Bars、Sample Status、Overlap Policy 與 stale state。
- Candidate detail 明確分離 Current Signal、Historical Backtest Context 與 Historical Cases Preview。
- Current Signal condition trace 直接來自 `candidate.signal_match`，technical snapshot 顯示當前 key technical features。
- Historical Backtest Context 同時顯示 Historical Hit Rate 與 Resolved Samples，並保留 HIT / MISS / INCOMPLETE / NOT_EVALUABLE、Raw Signals、Evaluated Signals、range、overlap 與 cooldown。
- Historical Cases Preview 由 `candidate.historical_backtest_report` + scan-time price-series cache 建立 `HistoricalCaseView`，支援 Resolved / HIT / MISS filter，預設 Resolved，最多列最新 5 筆，並重用 `historical_case_dashboard.py` 的 summary rows、case labels 與 Altair chart。
- 新增 `docs/SWING_RESEARCH_DASHBOARD.md`，並更新 README / Architecture。

### Safety Notes

- Historical Hit Rate 是歷史條件事件比例，不代表未來發生機率；UI 必須同時顯示 Resolved Samples。
- `100% / n=3` 仍顯示為 small sample context，不因完美比例自動優先於較大的 resolved sample。
- Research Priority 是研究檢視順序，不是 recommendation、交易排序、hidden score 或 AI ranking。
- `HIT` 不代表 profitable trade；`MISS` 不代表 losing trade。
- 高 Historical Hit Rate 可能和負 Median End Return 並存，因為 target event 可能在 evaluation window 結束前發生。
- `ALLOW_ALL` 可能包含 overlap events；`COOLDOWN` 降低 nearby repeated events，但不保證統計獨立。
- `清除掃描結果` 只清 `swing_research_*` session state，不碰 SQLite price cache、AI Research、Historical Cases standalone state 或 Watchlist。
- Zero-match 是有效結果；Dashboard 不自動放寬條件、不提供 nearest match、不調整 threshold。
- 本 Batch 不新增 technical indicators、signal threshold、outcome definition、probability model、AI ranking、fundamental merge、market-wide crawler、alerts、portfolio action 或下一個 Batch。

### Testing Notes

- 新增 `tests/test_swing_research_dashboard.py`，覆蓋 multi-line parsing、fingerprint sensitivity、formatter、sample status labels、candidate table order / fields、selector label、zero-match summary、condition trace、technical snapshot、NO_MATCH / NOT_EVALUABLE / failure rows、case preview from session price cache、missing price cache no-fetch behavior、Resolved / HIT / MISS filter、case counts、latest-five limit 與 source-level banned wording。
- 擴充 `tests/test_dashboard.py`，確認 `Swing Research` tab 與 `Historical Cases` tab 同時存在、Swing Research 使用 explicit submit / session result / clear button、必要 wording 存在且禁止 wording 不出現在 Swing Research source 區段。

## 2026-08-08 — Sprint 06 Batch F Historical Case Explorer

### Completed Features

- 新增 `src/historical_case_service.py`，建立 deterministic Historical Case Explorer service，消費 `HistoricalPriceSeries` 與 `HistoricalBacktestReport`。
- 新增 frozen `HistoricalCaseWindowConfig`，使用 `pre_signal_bars` / `post_signal_bars` 交易 bar 數，不使用 calendar days，並拒絕負數設定。
- 新增 frozen `HistoricalCaseView`，保存 case id、symbol、currency、signal / outcome id、signal date、signal analysis / raw close、frozen reference high / low、outcome status、first hit metadata、MFE / MAE / end return、horizon context、window completeness、price points、condition details 與 signal-date technical snapshot summary。
- 新增 frozen `HistoricalCasePricePoint`，保存 actual OHLCV bars、`analysis_close`、relative trading-bar index、signal marker、first-hit marker 與 before / after signal label。
- 新增 frozen `HistoricalCaseConditionDetail`，直接從 `SignalEvent.evaluated_conditions` 複製 metric、actual、operator、expected / secondary、status 與 matched，不重新 evaluate。
- 新增 `build_case_price_window()`，要求 signal date 必須存在於 price series；若不存在 raise `HistoricalCaseDataError`，不找 nearest date。
- Price window 只回傳實際 provider trading bars；不 forward fill、calendar reindex、weekend / holiday fill、interpolate 或建立 synthetic bars。
- Relative index 使用 trading-bar index；Friday signal 後的 Monday 是 `+1`，不是 calendar `+3`。
- Reference high 使用 frozen `SignalEvent.reference_high`；case service 不用 chart window 或 future bars 重新計算 prior high。
- 新增 `src/historical_case_dashboard.py`，集中處理 Historical Cases UI formatter、case request fingerprint、status filter、sort、case selector label、summary table、condition table、snapshot table 與 Altair chart spec。
- Chart 第一版使用 line chart：analysis close 主線、raw high 淡線、frozen reference high rule、signal date rule、HIT case first-hit point；MISS 不顯示 first-hit marker。
- Streamlit 新增 `Historical Cases` tab，使用單一 symbol、`technical_example_v1`、`raw_high_breakout_60d_within_20d_v1`、ALLOW_ALL / COOLDOWN、backtest date range 與 pre/post bars。
- UI 只有按下 `建立歷史案例` 才讀取 historical prices、建立 technical indicators、執行 backtest 與建立 case views；filter、sort、x-axis toggle、case selector、expander 不會重新 fetch / backtest。
- Case result 只保存在 `st.session_state`；`清除案例結果` 只清 session result，不刪 SQLite price cache 或其他資料。
- UI 顯示 Historical Hit Rate context、resolved / HIT / MISS / INCOMPLETE counts、overlap policy、cooldown bars、range context、price-basis explanation、condition trace 與 technical snapshot。

### Safety Notes

- Historical Case Explorer 是歷史案例檢視工具，不是 future prediction、similar-case probability、scanner ranking、Buy / Sell / Hold、target price、entry / exit signal、profit guarantee 或交易模擬。
- `HIT` 只代表指定 HistoricalOutcomeDefinition 在 horizon 內觸發 target event；不代表 profitable trade。
- `MISS` 只代表完整 horizon 內 target event 未觸發；不代表 losing trade。
- `INCOMPLETE` 明確保留，不會被畫成 `MISS`。
- Historical Hit Rate 是 descriptive historical event rate，不是未來發生機率。
- MFE / MAE / end return 是 close-based historical return metrics，不是實際交易損益。
- Service 層保留 raw float，百分比與 rounding 只在 UI formatter 處理。
- Case Explorer 不重新 evaluate signal conditions、不重新 evaluate historical outcomes、不改 threshold、不做 ranking、不抓 OpenAI、不做 full-market scan、不新增 persistence。

### Testing Notes

- 新增 `tests/test_historical_case_service.py`，覆蓋 config validation、actual-bar window、signal-date required、trading-bar relative index、signal marker、analysis close helper、pre/post completeness、HIT marker、MISS no marker、frozen reference high、condition copy-through、snapshot summary、raw metric preservation、oldest-to-newest order、symbol / signal / outcome / identity mismatch、NOT_EVALUABLE window 與 zero-window behavior。
- 新增 `tests/test_historical_case_dashboard.py`，覆蓋 percentage / price formatting、snapshot percentage formatting、resolved / status filter、sort、neutral selector label、summary rows、condition rows、snapshot rows、request fingerprint、HIT chart layer、MISS no-hit layer、relative-bar axis 與 actual-date axis。
- 擴充 `tests/test_dashboard.py`，確認 `Historical Cases` tab、explicit `建立歷史案例` submit、session-state result、clear result 與禁止 scanner / buy-sell wording。

## 2026-08-08 — Sprint 06 Batch E Swing Opportunity Scanner

### Completed Features

- 新增 `src/swing_scanner_service.py`，建立 deterministic Swing Opportunity Scanner service，輸入 caller-provided symbols 與 `SwingScannerConfig`。
- 新增 frozen `SwingScannerConfig`，保存 `SignalDefinition`、`OutcomeDefinition`、`overlap_policy`、`cooldown_bars`、backtest signal-date range、`minimum_resolved_samples`、`force_refresh`，並提供 deterministic `scanner_config_id`。
- 新增 frozen `SwingOpportunityCandidate`，保存 current `SignalMatch`、latest trading date、latest technical snapshot、`HistoricalBacktestReport`、Historical Hit Rate、resolved / HIT / MISS / INCOMPLETE / NOT_EVALUABLE counts、raw / filtered signal counts、median / average MFE、MAE、end return、hit bars、freshness、overlap context、sample-size status、rank components 與 limitations。
- 新增 frozen `SwingScannerResult`，保存 requested symbols、unique normalized symbols、matched candidates、NO_MATCH symbols 與 lightweight failed-condition details、NOT_EVALUABLE audits、isolated failures、timezone-aware UTC `generated_at` 與 count helpers。
- 新增 `SampleSizeStatus`：`NO_RESOLVED_SAMPLES`、`BELOW_PREFERRED_MINIMUM`、`MEETS_PREFERRED_MINIMUM`。Preferred minimum 是 research display threshold，不是 confidence model。
- Scanner 每支股票先建立 price history、technical series、latest snapshot 與 current signal evaluation；只有 latest `MATCH` 才執行 historical backtest。
- MATCH candidate 的 backtest 會重用同一個 `TechnicalIndicatorSeries`，避免 NO_MATCH 股票或 MATCH 股票重複計算不必要 backtest work。
- Per-symbol failure isolation：單一 symbol provider / data / config failure 會保存 `SwingScanFailure`，其他 symbols 繼續掃描；failure message 只保存安全第一行，不保存 traceback。
- 新增 versioned research ranking policy `swing_research_rank_v1`，使用 transparent tier + lexicographic ordering，不產生 hidden composite number。
- Ranking V1 先依 sample-size tier，再依 Historical Hit Rate、resolved count、median MAE、median MFE、median end return、symbol 排序；`None` hit rate 排最後，MAE 以原始負數 descending 排序。
- Candidate 和 result 均保存 latest daily bar may be provisional limitation；stale price series 會傳到 candidate limitation。
- 新增 `docs/SWING_OPPORTUNITY_SCANNER.md`，並更新 README / Architecture。

### Safety Notes

- Current signal evidence 和 historical backtest statistics 明確分離；Historical Hit Rate 不會回流改變 current MATCH / NO_MATCH / NOT_EVALUABLE。
- `100% / n=3` 不應直接比 `70% / n=100` 更優先；Batch E 用 sample-size tier 避免 small sample 在 ranking 中過度主導。
- Research ranking 只是 candidate inspection priority，不是 prediction score、buy rank、expected return rank、AI ranking 或機率模型。
- `NO_MATCH` 只表示 latest snapshot 不符合指定 `SignalDefinition`，不是 negative forecast，也不是股票不好。
- `NOT_EVALUABLE` 和 `NO_MATCH` 分開保存，避免資料不足被誤解為條件失敗。
- `ALLOW_ALL` 可能含有相鄰或重疊樣本；`COOLDOWN` 只能降低 nearby repeated signals，不能保證統計獨立。
- Yahoo latest daily bar 可能是 current-session provisional bar；scanner 不宣稱 real-time signal 或 completed-session signal。
- 本 Batch 不新增 dashboard、chart、case explorer、fundamentals、full-market universe crawler、watchlist automation、AI model、portfolio sizing、target price、transaction simulation 或 parameter optimization。

### Testing Notes

- 新增 `tests/test_swing_scanner_service.py`，覆蓋 empty universe、duplicate normalization、MATCH backtest once、NO_MATCH no backtest、NO_MATCH failed-condition summary、NOT_EVALUABLE no backtest、empty technical series、failure isolation、safe failure message、blank symbol failure、all no-match、all-fail result、count invariant、metric copy-through、current match traceability、stale propagation、provisional warning、shared backtest config、sample-size statuses、zero resolved history、small sample retention、ranking tiers / hit-rate / resolved / MAE / MFE / end-return / symbol tie-breaks、input-order independence、one-based research rank、rank policy version、rank components、config ID determinism、overlap limitations、config validation、frozen candidate、UTC timestamp 與 no probability / confidence score fields。
- Targeted tests：`.venv/bin/python -m unittest tests.test_swing_scanner_service`，43 tests passed。

## 2026-08-08 — Sprint 06 Batch D Historical Backtest Engine

### Completed Features

- 新增 `src/backtest_service.py`，建立 deterministic Historical Backtest Engine，輸入既有 `HistoricalPriceSeries`、`TechnicalIndicatorSeries`、`SignalDefinition`、`OutcomeDefinition` 與 `BacktestConfig`。
- 新增 frozen `BacktestConfig`，明確保存 `overlap_policy`、`cooldown_bars`、`start_date` 與 `end_date`；`COOLDOWN` 必須有正數 cooldown，`ALLOW_ALL` 不接受 ambiguous cooldown。
- 新增 frozen `HistoricalBacktestCase`，保存 `SignalEvent` 與 `HistoricalOutcomeResult`，case status 直接來自 outcome status，不重算。
- 新增 frozen `HistoricalBacktestReport`，保存 raw / filtered signal counts、HIT / MISS / INCOMPLETE / NOT_EVALUABLE counts、resolved count、Historical Hit Rate、return aggregates、hit-bar aggregates、sample counts、raw events、evaluated events 與 cases。
- Historical Hit Rate denominator 固定為 `HIT + MISS`；`INCOMPLETE` 與 `NOT_EVALUABLE` 不進 denominator。
- Early `HIT` 即使 full horizon 尚未完成，也進 resolved denominator；但缺少完整-window 的 MFE / MAE / end return 仍不進 return aggregate。
- Return aggregation 僅使用非 `None` metric；不把缺值補 `0`。MFE 使用 `max_close_return`，MAE 使用 `max_adverse_return` 並保留負號，end return 使用 `end_of_window_return`。
- Hit timing 使用 trading bar index，不平均 calendar days。
- Date range 只 filter signal dates；outcome evaluation 仍可使用 backtest `end_date` 之後的 future bars。
- `COOLDOWN` 重用 Batch C `apply_signal_cooldown()`，不重新發明 overlap filtering。
- 新增 deterministic `backtest_id` 與 `case_id`，不包含 `generated_at` 或 random UUID。
- 新增 `get_backtest_case_price_window()`，供未來 Historical Case Explorer 使用；這是 review helper，不讓 future bars 回流 signal features。

### Safety Notes

- 本 Batch 不新增 dashboard、scanner、ranking、AI prediction、future probability、confidence、likelihood、position sizing、transaction cost、stop loss、exit rule、portfolio return 或 SQLite persistence。
- `HIT` / `MISS` 是 historical outcome label，不是 winning trade / losing trade，也不是 Buy / Sell / Hold recommendation。
- `ALLOW_ALL` 可能包含高度相鄰或重疊樣本；`COOLDOWN` 只能降低 overlap，不能保證統計獨立。
- 若只用目前可查或仍上市股票回測，可能有 survivorship bias；Yahoo coverage、adjusted-close semantics、raw high / low basis 與 provisional latest daily bar 仍是 data-source limitations。
- 未來若加入 fundamentals，必須使用 point-in-time availability，不能用今天已知財報回填歷史 signal date。
- Batch D 是 descriptive historical in-sample aggregation，尚未做 train/test split、walk-forward、out-of-sample validation 或 probability calibration。

### Testing Notes

- 新增 `tests/test_backtest_service.py`，覆蓋 empty、all hit、all miss、mixed denominator、incomplete exclusion、not evaluable exclusion、only incomplete、early hit、return mean / median、sample counts、hit bar median、case property splits、case sorting、stable IDs、config validation、symbol mismatch、technical date mismatch、ALLOW_ALL、COOLDOWN、date range、outcome beyond end date、no-signal report 與 case window helper。

## 2026-08-08 — Sprint 06 Batch C Signal & Outcome Definition

### Push Blocker Fix

- 修正 `minimum_required_features` completeness precedence：任一 minimum required feature 缺失或 non-finite 時，final `SignalMatch.status` 必須是 `NOT_EVALUABLE`、`matched=False`，即使 explicit conditions 全部 individually `MATCH`。
- 新增 required feature 不在 conditions、required feature present、required missing + condition failure、non-finite required feature、`find_signal_events()` 排除 `NOT_EVALUABLE`、invalid signal analysis close return target、cooldown unsorted input determinism regression coverage。
- 本修正只調整 signal completeness propagation，未修改 RAW_HIGH_BREAKOUT、CLOSE_RETURN_TARGET、HIT / MISS / INCOMPLETE、MFE / MAE、horizon 或 cooldown semantics。

### Completed Features

- 新增 `SignalConditionOperator`、`SignalEvaluationStatus`、`OverlappingSignalPolicy`、`OutcomeType` 與 `OutcomeEvaluationStatus`，明確分離 signal 評估狀態與 historical outcome 標籤。
- 新增 frozen signal domain models：`TechnicalSignalCondition`、`EvaluatedSignalCondition`、`SignalDefinition`、`SignalMatch`、`SignalEvent` 與 `SignalEvaluationAudit`。
- 新增 frozen outcome domain models：`OutcomeDefinition` 與 `HistoricalOutcomeResult`。
- 新增 `src/signal_outcome_service.py`，提供 pure deterministic `evaluate_signal_conditions()`，只讀 signal-date `TechnicalIndicatorSnapshot`，不讀 future bars、不查 DB、不呼叫 network、不使用 AI。
- condition model 支援 `>`、`>=`、`<`、`<=`、`==` 與 inclusive `between`，並支援 metric-to-metric comparison，例如 `sma_20 > sma_60`；不使用 `eval()`。
- missing feature policy 明確區分 `NOT_EVALUABLE`，避免把資料不足誤當 `False`。
- `SignalEvent` 只由 `MATCH` 建立，並 freeze `signal_analysis_close`、`signal_raw_close`、`reference_high`、`reference_low`、feature snapshot 與 condition trace。
- 新增 `get_future_bars_after()`，future outcome window 嚴格從 `trading_date > signal_date` 開始，依 trading bars 計數，不使用 calendar days。
- 新增 `RAW_HIGH_BREAKOUT` outcome：future raw high strict `>` frozen raw prior high，equal high 不算突破，只保存 first hit。
- 新增 `CLOSE_RETURN_TARGET` outcome：future analysis close / signal analysis close - 1 `>= target_return`，只在 analysis-close basis 上運算。
- 新增 `HIT` / `MISS` / `INCOMPLETE` / `NOT_EVALUABLE` semantics；early hit 即使 horizon 未滿也可 resolved as `HIT`，未 hit 且 horizon 不足才是 `INCOMPLETE`。
- MFE / MAE / end-of-window return 只在完整 horizon 可用時填值，避免把 observed-so-far 誤解為完整窗口。
- 新增 `apply_signal_cooldown()` 作為 analysis-time filtering helper；raw event extraction 預設保留全部事件，不永久刪除 overlapping raw events。
- 新增中性 sample signal `technical_example_v1`、raw-high sample outcome `raw_high_breakout_60d_within_20d_v1` 與 close-return sample outcome `close_return_5pct_within_20d_v1`，ID 固定且具版本語意。

### Safety Notes

- 本 Batch 不計算 Historical Hit Rate、success_count、success_rate、probability、confidence、expected win rate、scanner、ranking、dashboard、AI prediction、fundamental filter、portfolio logic、Buy / Sell / Hold 或 target recommendation。
- Raw-high breakout 僅比較 raw future high 與 frozen raw prior high；Batch C 不把 raw prior high 與 analysis close 混成 close-breakout boolean。
- Close return metrics 僅使用 analysis close basis，和 raw high / low basis 分開。
- Historical outcome 可以看 future bars，但只產生歷史標籤，不得回流修改 signal feature snapshot 或 signal event。
- 未來 Batch D 的 Historical Hit Rate denominator 應只包含 `HIT + MISS`，排除 `INCOMPLETE` 與 `NOT_EVALUABLE`；Batch C 只文件化，不計算聚合百分比。

### Testing Notes

- 新增 `tests/test_signal_outcome_service.py`，覆蓋 all-match、condition failure、missing required feature、unknown metric、metric-vs-metric、inclusive between、boolean equality、bool ordered comparison rejection、non-finite defensive handling、unsupported between shape、condition traceability、SignalEvent freeze、non-match event rejection、event extraction and same-day de-duplication、audit counts、future window extraction、strict raw-high breakout、equal high miss、20-bar horizon no-peek、0 future bars incomplete、early-hit resolution、incomplete metrics empty、MFE / MAE / end return、close-return basis、missing reference `NOT_EVALUABLE`、completion helper、batch evaluator without aggregation、cooldown trading-bar distance、raw vs filtered event preservation、sample stable IDs、future mutation no-look-ahead、different future outcome labels, invalid horizon, and frozen domain models。
- Targeted tests：`.venv/bin/python -m unittest tests.test_signal_outcome_service`，37 tests passed。

## 2026-08-08 — Sprint 06 Batch B Technical Indicator Foundation

### Completed Features

- 新增 `TechnicalIndicatorSnapshot` 與 frozen `TechnicalIndicatorSeries`，讓 technical feature domain model 與 pandas DataFrame 分離。
- 新增 `src/technical_indicator_service.py`，從 `HistoricalPriceSeries` deterministic 計算 SMA5 / 10 / 20 / 60 / 120 / 200、EMA12 / EMA26、RSI14、MACD、ATR14、volume SMA / ratio、5D / 20D / 60D return、20D return volatility、rolling high / low、prior high / low、distance、range position 與中性 boolean facts。
- close-only 指標一律使用 Batch A `get_analysis_close()`，也就是 `adjusted_close if available else close`。
- ATR、rolling high / low、prior high / low 採 raw high / low；ATR previous close 採 raw close，避免在 high / low 尚未有明確 provider-adjusted basis 時自行產生 unsupported adjusted high / low。
- `volume_ratio_20` 固定為 current volume / previous 20 trading bars average volume，denominator 不包含今日。
- prior-window features 透過 `shift(1)` 排除 current bar；52-week technical features 明確採 252 trading bars approximation。
- `build_technical_indicator_snapshot()` 先用 `slice_price_series_as_of()`，因此非交易日 as-of 會使用當時最後可用交易 bar，早於最早資料則回傳 `None`。

### Safety Notes

- 本 Batch 只產生 features / measurements，不產生 Buy / Sell / Hold、bullish / bearish score、opportunity score、probability、hit rate、success / failure label、future return、target price、scanner、backtest、chart、news、sentiment 或 fundamental merge。
- Full-series implementation 只使用 causal rolling / EMA / `shift(1)`；禁止 backfill、future shift、centered windows。
- Latest Yahoo daily bar 仍可能是 current-session partial bar；latest technical snapshot 可能是 provisional，future backtest 應使用 completed-session policy。
- Technical indicators 不寫入 SQLite；本 Batch 未新增 technical indicator table 或 Dashboard tab。

### Testing Notes

- 新增 `tests/test_technical_indicator_service.py`，覆蓋 immutable domain model、registry labels、SMA full-window warm-up、EMA `adjust=False` warm-up、Wilder RSI reference / edge cases、MACD reference、ATR raw OHLC / raw close basis、volume ratio denominator 排除今日、returns by trading bars、sample return volatility、prior high 排除今日、52-week 252-bar approximation、as-of non-trading date、before-earliest `None`、full-series vs as-of consistency、future data mutation、append future bars、insufficient history、non-finite output guard、中性欄位命名與 source-level no-backfill / no-negative-shift guard。
- Targeted tests：`.venv/bin/python -m unittest tests.test_technical_indicator_service`，35 tests passed。

## 2026-08-02 — Sprint 06 Batch A Historical Price Data Foundation

### Completed Features

- 新增 `HistoricalPriceBar` 與 frozen `HistoricalPriceSeries`，讓 daily price history 和 current `Stock` snapshot 分離；日線 identity 固定為 `symbol + trading_date`。
- 新增 `src/historical_price_service.py`，使用 Yahoo `Ticker.history()` 取得 daily OHLCV，採 `auto_adjust=False`、`actions=True`，保存 raw OHLC、`adjusted_close`、volume、dividends、stock splits。
- 新增 `HistoricalPriceQuality` audit summary，normalization 會過濾 NaN、inf、string numeric、bool、非正價格、價格關係違反與負 volume；volume `0` 保留。
- Duplicate trading date 採 deterministic 策略：identical duplicate collapse，conflicting duplicate 記 quality issue 並保留最後一筆 provider row。
- 新增 `historical_prices` SQLite table，primary key 為 `(symbol, trading_date)`，upsert refresh 不會刪除 provider 本次沒有回傳的舊 bars。
- 新增 `historical_price_fetch_state`，區分 cache freshness 與 range coverage completeness；`start=None` 代表 default full history，必須有 full-history fetch state 才能用 cache 滿足。
- 新增 12-hour historical price cache TTL，獨立於 current stock 24-hour cache 與 historical fundamentals 7-day cache。
- 新增 stale fallback：Yahoo refresh 失敗且 covered stale cache 存在時，回傳 `is_stale=True` 的 `HistoricalPriceSeries`。
- 新增 `get_analysis_close()`，未來 technical analysis close contract 為 `adjusted_close if available else close`。
- 新增 `slice_price_series_as_of()`，任何 as-of research 只回傳 `trading_date <= as_of_date` 的 bars，作為 no-look-ahead 基礎。
- 新增 `get_recent_bars()`，依實際 trading bars 數量回傳最近 N 筆，不用 calendar days 假裝 trading-day count。
- 新增文件 `docs/HISTORICAL_PRICE_DATA_AUDIT.md` 與 `docs/HISTORICAL_PRICE_FOUNDATION.md`，並更新 README / Architecture。

### Audit Notes

- Live Yahoo audit 顯示 `2330.TW`、`2454.TW`、`6488.TWO` daily index 為 `Asia/Taipei`，`NVDA`、`AAPL` 為 `America/New_York`；domain model 只取 provider-local `.date()`，不做 UTC conversion，避免美股日期 shift。
- `auto_adjust=False` 回傳 `Open`、`High`、`Low`、`Close`、`Adj Close`、`Volume`、`Dividends`、`Stock Splits`；`auto_adjust=True` 會移除 `Adj Close` 並讓 OHLC 已調整。
- AAPL 2020 split 與 NVDA 2024 split audit 確認 `auto_adjust=True` close 與 `Adj Close` 對齊；因此 Batch A 保留 raw OHLC + adjusted close，不自行計算調整因子。
- Live audit 有零成交量 rows，尤其台股與 `.TWO`，因此 `volume = 0` 不視為 invalid；負 volume 才過濾。

### Safety Notes

- 本 Batch 未新增 RSI、MACD、moving average、ATR、Bollinger、signal、outcome label、Historical Hit Rate、probability、backtest、scanner、chart、candlestick、AI price prediction 或 Buy / Sell / Hold recommendation。
- Batch A 不判定 current-session latest daily bar 是否完成，因 Yahoo daily history 沒有可靠 market-state metadata；未來 backtest 應由 caller 提供 completed-session `end` 或導入 market-calendar-aware freshness。
- Historical Hit Rate 未來仍只能稱為 historical hit rate；在 out-of-sample、walk-forward validation 與 probability calibration 前，不得稱為 future probability。

### Testing Notes

- 新增 `tests/test_historical_price_service.py`，覆蓋 chronological normalization、timezone date normalization、empty frame、NaN / inf / non-positive price、price relationship、negative vs zero volume、string numeric / bool coercion、duplicate dates、MultiIndex rejection、analysis close、as-of no-look-ahead、recent N trading bars、Yahoo adapter call shape、network error mapping、cache hit、symbol normalization、stale fallback 與 no-cache provider failure。
- 擴充 `tests/test_database.py`，覆蓋 historical price table / fetch-state table creation、insert/read、range read、12-hour TTL、stale read、upsert、non-destructive refresh、coverage completeness、full-history state、latest date helper、legacy additive migration。

### Recovery Review Notes

- Sprint 06 Batch A recovery review confirmed `historical_price_fetch_state` should represent coverage, not freshness for every retained row. Freshness is now evaluated from the requested rows' oldest `fetched_at`, so a partial refresh cannot make older coverage appear fresh.
- Boundary tests now explicitly cover `None`, bool price values, missing required price fields, negative `adjusted_close`, and missing optional `Open`.

## 2026-08-02 — Sprint 05 Batch C Grounded Follow-up Research Workflow

### Completed Features

- 新增 `src/ai_followup.py`，建立 `FollowUpResearchSuggestion`、frozen `AIResearchTurn`、session-only `AIResearchSession`、deterministic turn ID、suggestion dedupe、question routing、fallback suggestion policy 與 token usage aggregation。
- AI Research tab 從單一 result 升級為 session research log；每個 session 最多 5 個 successful verified turns。
- Initial research 成功後才建立新 session；新股票 request 失敗時不會先清掉舊 session。
- Follow-up suggestions 顯示在目前 answer 下方，來源可包含 AI `next_steps`、missing data 與 deterministic fallback，但只作為下一步研究問題，不作為 factual evidence。
- 「使用這個問題」只填入 follow-up form 與預選 question type，不呼叫 provider。
- Follow-up submit 會重新建立 stock / historical data、`ResearchContext`、`SelectedResearchContext`，再發出新的 stateless Grounded AI request。
- Turn history 顯示目前研究結果與先前研究結果；previous turns collapsed，並保存各自的 selected evidence snapshot。
- Clear action 升級為「清除 AI 研究工作階段」，只清 session、draft、last error 與 request counter，不刪 API key、不碰 SQLite。
- Session header 顯示 successful turn count、session API request count 與 token usage aggregation。

### Safety Notes

- 本 Batch 未新增 free chat、conversation memory、`previous_response_id`、OpenAI conversation object、streaming、web search、RAG、embeddings、vector DB、AI router、scheduled/background AI call 或 AI SQLite persistence。
- Previous AI answer summary / findings / next steps 不會進入下一輪 provider payload；下一輪 factual grounding 只來自 new `SelectedResearchContext`。
- Failed follow-up 不 append turn，也不顯示未驗證 raw answer；previous verified turns 仍保留。
- API key 仍只由 provider client 讀取環境變數；turn/session 不保存 raw provider response、Authorization header 或 secret。

### Testing Notes

- 新增 `tests/test_ai_followup.py`，覆蓋中英文 deterministic routing、unknown fallback、suggestion priority、dedupe、5 item limit、fallback suggestions、missing-data suggestion、turn ID、frozen turn、hard 5-turn limit、failed-turn preservation、clear reset、token aggregation、previous answer isolation、new context snapshot、same-question explicit resubmit、secret/raw-response exclusion。
- Targeted tests：`.venv/bin/python -m unittest tests.test_ai_followup`，21 tests passed。
- Regression tests：`.venv/bin/python -m unittest tests.test_ai_dashboard`，8 tests passed；`.venv/bin/python -m unittest tests.test_ai_research_service`，43 tests passed。

## 2026-08-02 — Sprint 05 Batch B Grounded AI Research Dashboard Integration

### Completed Features

- 新增 Streamlit `AI Research` tab，獨立於 deterministic `Research` / `Historical Trends`，避免固定規則輸出與 AI answer 混淆。
- AI Research 使用單一股票、explicit `ResearchQuestionType`、使用者研究問題與 `st.form()` submit。
- OpenAI API request 只在明確按下 `產生 AI 研究` 後執行；初始 render、widget change、expander、rerun 與 clear result 不會自動呼叫 provider。
- 新增 `st.session_state["ai_research_result"]` 保存上一份 answer / selected context / metadata / error；rerun 直接重新 render session result。
- 新增 `src/ai_dashboard.py`，集中管理 question-type label / help / placeholder、request fingerprint、evidence formatting、source-type label、derived lineage helper、safe error message 與 API key boolean status。
- AI tab orchestration 會建立 `ResearchReport`、`HistoricalFinancialSeries`、`HistoricalResearchReport`、`ResearchContext`、`SelectedResearchContext`，再呼叫既有 `generate_grounded_research_answer()`。
- Answer UI 顯示 header、AI Summary、Grounded Findings、Evidence expander、Limitations、Missing Information、Research Next Steps、validation badges、selected context preview 與 provider metadata。
- Evidence UI 只 lookup `SelectedResearchContext.selected_evidence`，不回查 SQLite、不重抓 Yahoo、不 dump full context JSON。
- Derived evidence 顯示 `Derived Evidence（衍生資料）` 與 `Derived from` source evidence detail；缺少 citation / lineage 時 defensive 顯示 unavailable。
- API key status 僅顯示 Configured / Not configured，不顯示 key prefix、suffix、length 或 value，也不提供 UI key input。

### Safety Notes

- 本 Batch 未新增 AI answer SQLite persistence、AI table、conversation memory、chat input、streaming、web search、RAG、embeddings、vector DB、model selector、scheduled/background AI request。
- Request fingerprint 不包含 API key，也不作為自動 cache key；使用者明確再次 submit 時允許新的 provider request。
- Grounding / numeric / structured-output validation fail 時，未驗證 answer 不會顯示給使用者。
- Provider metadata 只顯示 model、response ID、generated_at 與 token usage；不顯示 raw prompt、raw payload、raw response、headers 或 secrets。
- Historical stale cache 會在 AI answer header 顯示 warning；AI tab 不宣稱 real-time analysis。

### Testing Notes

- 新增 `tests/test_ai_dashboard.py`，覆蓋 14 個 question type label / help、fingerprint determinism / input sensitivity / secret exclusion、evidence formatting、period / source-type labels、derived lineage safe resolution、safe error messages、incomplete response technical detail 與 API key boolean status。
- Targeted tests：`.venv/bin/python -m unittest tests.test_ai_dashboard`，7 tests passed。
- AI service regression：`.venv/bin/python -m unittest tests.test_ai_research_service`，40 tests passed。
- Compile validation：`.venv/bin/python -m py_compile app.py src/ai_dashboard.py src/ai_research_service.py` passed。

## 2026-08-02 — Sprint 05 Batch A Numeric Grounding Diagnostics Patch

### Completed Features

- 新增 `AINumericGroundingError`，專門表示 explicit percentage claim 與 cited evidence numeric candidates 不一致。
- Numeric diagnostic error 保存安全資訊：offending finding statement、extracted percentage claims、cited evidence IDs、normalized cited percentage candidates。
- Percentage validator 改為 metric-aware，只讓 percentage-capable evidence 參與比對，避免任意 numeric evidence 造成誤判。
- 多個 percentage claims / 多個 citations 採用 any-candidate matching：每個 claim 至少匹配其中一筆 cited percentage candidate；不要求 claim 與 evidence 順序一致。
- 保留 `0.2` percentage-point tolerance，不放寬 tolerance。
- 支援 signed negative percentage，例如 `-21.02%`；wrong sign 會 fail。
- 加入狹窄 deterministic decline-word rule，讓 `下降 21.02%` 可對應負向 evidence；此規則不是大型中文 NLP。
- `debt_to_equity` 視為 provider percentage-scale raw data，不把 `1.2` 自動轉成 `120%`。
- Developer instructions 小幅補強：百分比應使用 cited evidence 的 numeric value 或正常 rounding，不要自行計算不存在於 derived evidence 的 percentage。

### Live Smoke Context

- 第四次 live smoke：provider `status = completed`，usage 為 `input_tokens = 3533`、`output_tokens = 852`、`reasoning_tokens = 0`、`total_tokens = 4385`。
- Structured Output validation pass，citation grounding pass。
- Numeric validation fail：`Percentage claim is not supported by cited numeric evidence`。
- 因此目前 live-provider blocker 已從 token budget 轉為 numeric factual consistency validation。

### Safety Notes

- 本 patch 未重跑 live OpenAI API。
- 本 patch 未放寬 numeric validator、未提高 tolerance、未修改 Structured Output schema、citation policy、forbidden-output policy、ResearchContext、selector、UI 或 SQLite。
- Structured Outputs 只保證 schema，不保證 factual correctness；目前 numeric guard 僅覆蓋 explicit `%` claims。
- 非百分比數字，例如 TWD amounts、EPS、P/E、price-to-book，以及 percentage-point deltas，仍列為 future technical debt。

### Testing Notes

- AI service tests 新增 percentage validation matrix：single valid / invalid、multiple claims / citations、one invalid among valid claims、reversed evidence order、duplicate claims、signed negative、wrong sign、decline wording、percentage-point tolerance、non-percentage statements、missing percentage-capable evidence、one matching evidence among many、unknown evidence remains citation-layer failure。

## 2026-08-02 — Sprint 05 Batch A Reasoning Budget Optimization Patch

### Completed Features

- 新增 `DEFAULT_REASONING_EFFORT = "minimal"` 與 `DEFAULT_TEXT_VERBOSITY = "low"`，集中於 `src/ai_config.py`。
- Production Responses API request 會傳入 `reasoning={"effort": "minimal"}`，並保留 strict structured output：`text={"verbosity": "low", "format": ...}`。
- 保留 `DEFAULT_MAX_OUTPUT_TOKENS = 2400`，不再單純提高 output-token ceiling。
- Developer instructions 保留 concise contract，並補充只回傳 required structured answer、不要在 schema 外加入不必要說明。
- `AIIncompleteResponseError` 新增安全 diagnostics：`reasoning_tokens` 與 `cached_input_tokens`。
- `AIResponseMetadata` 新增 `reasoning_tokens` 與 `cached_input_tokens`，讓 completed response 也可比較 reasoning effort 與 visible answer token 行為。

### Rationale

- Live smoke attempt 1：`max_output_tokens = 1200`、`status = incomplete`、`reason = max_output_tokens`、`output_tokens = 1152`。
- Live smoke attempt 2：`max_output_tokens = 2400`、`status = incomplete`、`reason = max_output_tokens`、`output_tokens = 2400`。
- 因此策略不是繼續無限制提高 token cap，而是先降低 reasoning / verbosity token 使用。
- Grounded Research 是 constrained synthesis：question type 已 deterministic、context selection 已 deterministic、evidence 已 normalized、observations 已 deterministic、output 使用 strict schema，且後續仍有 deterministic grounding / numeric / forbidden-output validation。

### SDK Audit

- Installed `openai 2.52.0` 的 `responses.create()` signature 支援 `reasoning` argument。
- SDK type definitions 顯示 reasoning effort 支援 `none`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`，且 `Reasoning` 標註適用於 `gpt-5` 與 o-series models。
- SDK type definitions 顯示 `text.verbosity` 支援 `low`、`medium`、`high`。
- SDK `ResponseUsage.output_tokens_details.reasoning_tokens` 與 `input_tokens_details.cached_tokens` 可作為安全 token diagnostics。

### Safety Notes

- 本 patch 未修改 `ResearchContext`、selector、Structured Output schema、grounding validation、numeric validation、forbidden-output validation、citation policy、OpenAI model、UI 或 SQLite。
- 本 patch 沒有執行新的 live OpenAI request，也沒有 push。

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
