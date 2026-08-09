# AI-Investment-Research Architecture

## Version

v1.0

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

historical_price_service.py
    └── Yahoo daily OHLCV normalization
    └── HistoricalPriceSeries / HistoricalPriceBar
    └── 12-hour SQLite historical price cache
    └── Coverage state for full-history and explicit range requests

technical_indicator_service.py
    └── HistoricalPriceSeries
        ↓
        TechnicalIndicatorService
        ↓
        TechnicalIndicatorSeries
        ↓
        signal_outcome_service.py
        ↓
        SignalEvent
        ↓
        HistoricalOutcomeResult
        ↓
        backtest_service.py
        ↓
        HistoricalBacktestCase
        ↓
        HistoricalBacktestReport
        ↓
        swing_scanner_service.py
        ↓
        SwingOpportunityCandidate
        ↓
        SwingScannerResult
        ↓
        swing_research_dashboard.py
        ↓
        Streamlit Swing Research tab

historical_replay_service.py
    └── Full HistoricalPriceSeries
        ↓
        slice_price_series_as_of(replay_date)
        ↓
        Replay TechnicalIndicatorSeries / latest snapshot
        ↓
        Replay SignalMatch
        ↓
        PointInTimeBacktestSummary
        ↓
        HistoricalReplayCandidate / HistoricalReplayResult
        ↓
        swing_research_dashboard.py
        ↓
        Streamlit Swing Research Historical Replay mode

historical_replay_service.py post-replay verification
    └── Full HistoricalPriceSeries
        ↓
        Replay-day frozen SignalEvent
        ↓
        HistoricalOutcomeResult
        ↓
        Separate Post-Replay Outcome block

walk_forward_replay_service.py
    └── Replay Date Generator
        ↓
        run-local full price-series cache
        ↓
        HistoricalReplayService
        ↓
        WalkForwardReplayPeriod[]
        ↓
        WalkForwardReplaySummary
        ↓
        replay_analytics_service.py
        ↓
        ReplayAnalyticsResult
        ↓
        swing_research_dashboard.py
        ↓
        Dashboard Replay Analytics / Period Detail

out_of_sample_validation_service.py
    └── ValidationPeriodRole / ValidationPeriod
        ↓
        FrozenResearchSpecification / deterministic fingerprint
        ↓
        one run-local full price-series cache across all period roles
        ↓
        DEVELOPMENT Walk-Forward Replay + period-local Replay Analytics
        ↓
        VALIDATION Walk-Forward Replay + period-local Replay Analytics
        ↓
        HOLDOUT Walk-Forward Replay + period-local Replay Analytics
        ↓
        transparent cross-period raw-fact comparison
        ↓
        oos_validation_dashboard.py
        ↓
        Streamlit Swing Research Out-of-Sample Validation mode

signal_condition_diagnostics_service.py
    └── TechnicalIndicatorSeries
        ↓
        Daily V1 condition observations
        ↓
        HistoricalConditionDiagnosticsResult
        ↓
        historical_condition_outcome_service.py
        ↓
        HistoricalConditionOutcomeComparisonResult
        ↓
        swing_research_dashboard.py presentation helpers
        ↓
        app.py Swing Research V1 歷史條件診斷 section

backtest_service.py
    ↓
    historical_case_service.py
    ↓
    historical_case_dashboard.py
    ↓
    Streamlit Historical Cases tab

SwingScannerResult
    ↓
    swing_research_dashboard.py
    ↓
    Candidate Detail
    ↓
    HistoricalBacktestReport
    ↓
    HistoricalCaseService
    ↓
    Historical Cases Preview

signal_outcome_service.py
    └── TechnicalIndicatorSeries / TechnicalIndicatorSnapshot
        ↓
        Signal Evaluation
        ↓
        SignalEvent
        ↓
        Historical Outcome Evaluation
        ↓
        HistoricalOutcomeResult
        ↓
        backtest_service.py
        ↓
        HistoricalBacktestReport

watchlist_service.py
    └── JSON watchlist

dashboard.py
    └── Dashboard presentation helpers
    └── Historical Trends presentation builders and display formatters

research_service.py
    └── Deterministic research interpretation and observations

historical_research_service.py
    └── Deterministic historical trend interpretation and research checklists

historical_interpretation_presentation.py
    └── Historical Interpretation highlights, grouping, and checklist presentation helpers

research_context.py
    └── Structured Research Context builder for AI / export / report inputs

research_context_selector.py
    └── Deterministic AI-ready Research Context subset selector by explicit question type

ai_config.py
    └── Central Grounded AI Research configuration for model, timeout, output-token, and input-length defaults

ai_dashboard.py
    └── AI Research UI presentation helpers, question-type labels, request fingerprinting, evidence formatting, and safe error messages

ai_followup.py
    └── Grounded follow-up research turn/session models, deterministic question routing, suggestion policy, dedupe, turn IDs, and token aggregation

ai_research_service.py
    └── Grounded AI Research service using SelectedResearchContext, OpenAI Responses API, strict structured output, and deterministic grounding validation

research_glossary.py
    └── Beginner research term glossary for Research UI

company_name_service.py
    └── Taiwan official company name localization + JSON cache

company_summary_service.py
    └── Presentation-only company summary localization + JSON cache

models.py
    └── Stock
    └── HistoricalFinancialPeriod
    └── HistoricalFinancialSeries
    └── HistoricalPriceBar
    └── HistoricalPriceSeries
    └── TechnicalIndicatorSnapshot
    └── TechnicalIndicatorSeries
    └── SignalDefinition / TechnicalSignalCondition / SignalMatch
    └── SignalEvent
    └── OutcomeDefinition / HistoricalOutcomeResult

research_metrics.py
    └── Deterministic research metric helpers

historical_financial_service.py
    └── Yahoo annual financial statement normalization + historical fundamentals service

historical_price_service.py
    └── Yahoo daily price history normalization + no-look-ahead price helpers

technical_indicator_service.py
    └── Deterministic technical feature calculation from historical price bars
    └── Causal SMA / EMA / RSI / MACD / ATR / volume / return / prior-window features
    └── No signal, score, outcome, probability, scanner, chart, or persistence

signal_outcome_service.py
    └── Deterministic signal condition evaluation from TechnicalIndicatorSnapshot only
    └── MATCH / NO_MATCH / NOT_EVALUABLE distinction for missing technical features
    └── SignalEvent creation with frozen signal-date feature snapshot and reference levels
    └── Historical outcome labeling from future trading bars after signal date
    └── RAW_HIGH_BREAKOUT and CLOSE_RETURN_TARGET MVP outcomes
    └── HIT / MISS / INCOMPLETE / NOT_EVALUABLE outcome statuses
    └── Overlapping signal cooldown as analysis-time filtering only
    └── No hit-rate aggregation, probability, scanner, dashboard, AI, or persistence

signal_condition_diagnostics_service.py
    └── Deterministic V1 Historical Condition Diagnostics foundation
    └── HistoricalConditionDiagnosticsConfig with inclusive start/end date and fixed SignalDefinition
    └── Per-symbol flow: use injected TechnicalIndicatorSeries or load price once and build technical series once
    └── Per-snapshot flow: reuse evaluate_signal_conditions() and preserve EvaluatedSignalCondition trace
    └── ConditionDiagnosticObservation preserves symbol, trading date, signal id, status, matched condition count, passed/missing/not-evaluable condition ids, evaluated conditions, and source snapshot
    └── Aggregates 0/5 through 5/5 match-count distribution, single-condition pass rates, 4/5 missing-condition summaries, and canonical condition combinations
    └── Separates evaluated observations from NOT_EVALUABLE observations; NOT_EVALUABLE is not counted as 0/5
    └── Provides aggregate and per-symbol summaries without SQLite persistence
    └── No outcome calculation, Historical Hit Rate, backtest, replay, scanner ranking, Yahoo fetch when injected data is supplied, dashboard, probability, recommendation, OpenAI, or database schema change

historical_condition_outcome_service.py
    └── Deterministic V1 Historical Condition Outcome Comparison foundation
    └── Consumes Batch 1 ConditionDiagnosticObservation as the condition-side truth source
    └── Does not re-evaluate V1 conditions or create independent signal events / trades
    └── Prepares deterministic research series with 60 pre-window warm-up trading bars, observation-window bars, and outcome-horizon post-window bars
    └── Reuses raw_high_breakout_60d_within_20d_v1 and evaluate_historical_outcome()
    └── Groups daily observations by 0/5 through 5/5, 4/5 missing condition, and canonical passed-condition combination
    └── Historical Hit Rate denominator fixed as HIT + MISS; INCOMPLETE and NOT_EVALUABLE are excluded
    └── Preserves aggregate and per-symbol summaries; aggregate sums observations rather than averaging symbol rates
    └── Records daily-observation unit and overlap_possible warning
    └── No V1 threshold change, parameter tuning, recommendation, probability, ranking, dashboard, AI, SQLite persistence, or database schema change

condition_contribution_service.py
    └── Deterministic V1 Single Condition Contribution Analysis foundation
    └── Consumes Batch 2 HistoricalConditionOutcomeComparisonResult with attached ConditionOutcomeObservation records
    └── Reuses Batch 1 observation identity and Batch 2 outcome attachment; does not re-evaluate V1 conditions or outcomes
    └── For each canonical V1 condition, compares original 5/5 baseline against baseline plus 4/5 observations where only that target condition is missing
    └── Enforces no duplicate daily observation by symbol, trading date, and signal definition id
    └── Reports baseline, leave-one-out, added observation, added resolved, added HIT / MISS, observation increase rate, and Historical Hit Rate delta in percentage points
    └── Historical Hit Rate denominator remains HIT + MISS; INCOMPLETE and NOT_EVALUABLE are excluded
    └── Preserves aggregate and per-symbol summaries; aggregate sums raw counts rather than averaging symbol-level rates
    └── Records daily-observation unit and overlap_possible warning
    └── No V1 threshold change, V1.1 / V2, threshold sensitivity, recommendation, probability, ranking, dashboard, AI, SQLite persistence, or database schema change

volume_threshold_sensitivity_service.py
    └── Deterministic V1 Volume Threshold Sensitivity Analysis foundation
    └── Consumes Batch 2 HistoricalConditionOutcomeComparisonResult with attached ConditionOutcomeObservation records
    └── Reuses Batch 1 observation identity and Batch 2 outcome attachment; does not re-evaluate V1 conditions or outcomes
    └── Keeps the other four V1 conditions fixed and only applies volume_ratio_20 >= threshold to actual diagnostic snapshot values
    └── Validates finite positive unique thresholds, deterministic ascending output, and required 1.20 current V1 baseline
    └── Reports threshold points for observation count, HIT / MISS / INCOMPLETE / NOT_EVALUABLE, resolved count, Historical Hit Rate, and deltas vs 1.20
    └── Enforces duplicate observation identity, sample-count monotonicity, and qualified-ID subset invariants
    └── Historical Hit Rate denominator remains HIT + MISS; INCOMPLETE and NOT_EVALUABLE are excluded
    └── Preserves aggregate and per-symbol summaries; aggregate sums raw counts rather than averaging symbol-level rates
    └── Records daily-observation unit and overlap_possible warning
    └── No production V1 threshold change, V1.1 / V2, RSI sensitivity, distance sensitivity, recommendation, probability, ranking, dashboard, AI, SQLite persistence, or database schema change

volume_threshold_robustness_service.py
    └── Deterministic V1 Volume Threshold Robustness Analysis foundation
    └── Consumes Batch 2 HistoricalConditionOutcomeComparisonResult with attached ConditionOutcomeObservation records
    └── Reuses Batch 1 observation identity and Batch 2 outcome attachment; does not re-evaluate V1 conditions or outcomes
    └── Fixes candidate thresholds exactly as 1.00, 1.10, and 1.20, with 1.20 retained as formal V1 reference baseline
    └── Keeps the other four V1 conditions fixed and only applies volume_ratio_20 >= threshold to actual diagnostic snapshot values
    └── Reports aggregate daily, per-symbol, per-year, and overlap-reduced summaries
    └── Per-year grouping uses observation trading date year; future 20-bar outcomes may extend beyond the observation year
    └── Overlap-reduced view uses deterministic same-symbol trading-bar index spacing of at least 20 bars
    └── Lower-overlap view is a research sampling view only; it is not an entry rule, cooldown rule, strategy rule, or statistical-independence claim
    └── Historical Hit Rate denominator remains HIT + MISS; INCOMPLETE and NOT_EVALUABLE are excluded
    └── Preserves aggregate raw-count semantics rather than averaging symbol-level or year-level rates
    └── No production V1 threshold change, V1.1 / V2, new threshold grid, RSI sensitivity, distance sensitivity, recommendation, probability, ranking, score, dashboard, AI, SQLite persistence, or database schema change

expanded_volume_threshold_validation_service.py
    └── Deterministic V1 Expanded Symbol Universe Validation foundation
    └── Uses data/stocks.db SQLite mode=ro for universe audit and read-only historical price loading
    └── Freezes a local Taiwan universe before threshold result calculation, using only .TW / .TWO symbols and coverage quality
    └── Preserves original five symbols when coverage is valid, including zero-sample symbols such as 2404.TW
    └── Excludes symbols with explicit reasons such as EXCLUDED_NOT_TAIWAN_UNIVERSE or EXCLUDED_DATA_COVERAGE
    └── Reuses prepare_diagnostic_research_series, HistoricalConditionDiagnosticsService, HistoricalConditionOutcomeComparison, and VolumeThresholdRobustness semantics
    └── Prepares price series, technical series, diagnostics, and outcome attachment at most once per symbol before threshold aggregation
    └── Reports aggregate, per-symbol, per-year, symbol-breadth, overlap-reduced, concentration, old-five comparison, and descriptive classification outputs
    └── Selection never uses Historical Hit Rate, threshold result, scanner result, backtest result, profitability, recommendation, ranking, score, or probability
    └── No production V1 threshold change, V1.1 / V2, dashboard integration, RSI sensitivity, distance sensitivity, scanner, backtest, AI, SQLite persistence, or database schema change

backtest_service.py
    └── Deterministic historical backtest aggregation from existing price, technical, signal, and outcome layers
    └── BacktestConfig with SignalDefinition, OutcomeDefinition, overlap policy, cooldown, and inclusive signal-date range
    └── Raw signal count from find_signal_events()
    └── Filtered signal count after date range and ALLOW_ALL / COOLDOWN policy
    └── HistoricalBacktestCase preserving SignalEvent and HistoricalOutcomeResult identity
    └── HistoricalBacktestReport with HIT / MISS / INCOMPLETE / NOT_EVALUABLE counts
    └── Historical Hit Rate denominator fixed as HIT + MISS
    └── Return aggregates using non-empty metric values only, with sample counts
    └── Trading-bar hit-index aggregation for HIT cases
    └── Stable deterministic backtest_id and case_id
    └── No probability, ranking, scanner, dashboard, AI, transaction simulation, or persistence

swing_scanner_service.py
    └── Deterministic current technical scanner for caller-provided symbol universes
    └── SwingScannerConfig with SignalDefinition, OutcomeDefinition, overlap policy, cooldown, backtest date range, and preferred sample minimum
    └── Per-symbol flow: price history, technical series, latest snapshot, current signal evaluation
    └── Backtest runs only for current MATCH symbols and reuses the existing TechnicalIndicatorSeries
    └── SwingOpportunityCandidate preserving current SignalMatch, HistoricalBacktestReport metrics, freshness, overlap context, sample-size status, and limitations
    └── SwingScannerResult preserving matched candidates, NO_MATCH symbols and lightweight failed-condition details, NOT_EVALUABLE audits, isolated failures, generated_at, and count helpers
    └── Versioned transparent research ranking with rank components and no hidden composite score
    └── No recommendation, buy list, market-wide crawler, dashboard, fundamentals, AI ranking, target price, or transaction simulation

swing_research_dashboard.py
    └── Swing Research Dashboard presentation helpers
    └── Multi-line stock-pool parsing, scan fingerprinting, display formatters, scan summary rows, candidate table rows, condition trace rows, technical snapshot rows, NO_MATCH / NOT_EVALUABLE / failure rows, and case preview helpers
    └── Builds HistoricalCaseView preview only from candidate HistoricalBacktestReport plus scan-time session price-series cache
    └── No Yahoo fetch, SQLite access, OpenAI calls, scanner execution, backtest execution, signal recalculation, outcome recalculation, recommendation, probability, fundamentals, or persistence

historical_replay_service.py
    └── Deterministic single-date Historical As-Of Scan / Replay Mode
    └── HistoricalReplayConfig with replay date, signal / outcome definitions, overlap policy, cooldown, historical start, and preferred resolved samples
    └── Per-symbol replay flow: full price history, as-of price slicing, replay technical snapshot, replay signal evaluation
    └── Actual trading date is per symbol and equals the latest bar on or before requested replay date
    └── PointInTimeBacktestSummary filters historical outcomes by what was knowable at replay date
    └── Early HIT can enter resolved denominator once target-hit date is known
    └── MISS, MFE, MAE, and End Return require the full trading-bar horizon to have completed by replay date
    └── Post-Replay Outcome is stored separately for historical verification only
    └── Reuses swing_research_rank_v1 with point-in-time inputs only
    └── No probability, AI prediction, optimization, walk-forward batch, full-market crawler, or persistence

walk_forward_replay_service.py
    └── Deterministic Multi-Date Walk-Forward Replay orchestration
    └── WalkForwardReplayConfig with inclusive start/end date, Monthly / Weekly frequency, signal / outcome definitions, overlap policy, cooldown, historical start, preferred samples, and max period guard
    └── generate_replay_dates() pure deterministic schedule builder
    └── Monthly replay dates are calendar month ends; Weekly replay dates are Fridays
    └── Loads full HistoricalPriceSeries once per normalized symbol into a run-local cache
    └── Calls HistoricalReplayService for each requested replay date and reuses single-date replay semantics
    └── Preserves WalkForwardReplayPeriod snapshots oldest to newest, including zero-match periods and period-level safe failures
    └── Aggregates descriptive candidate occurrence counts, unique candidate symbols, post-replay outcome counts, and repeated symbol summaries
    └── Does not compute aggregate walk-forward hit rate, probability, prediction accuracy, parameter optimization, strategy P&L, persistence, or AI ranking

replay_analytics_service.py
    └── Deterministic descriptive analytics layer for existing WalkForwardReplayResult
    └── ReplayAnalyticsResult with Stability Summary, Period Summary, Symbol Summary, Candidate Occurrence, Outcome Distribution, and Candidate Set transitions
    └── Computes Candidate Period Share as periods-with-candidates / total periods or symbol occurrences / total periods
    └── Computes longest consecutive candidate appearance by replay period ordering, not calendar gaps
    └── Computes Candidate Set Jaccard Similarity and Candidate Set Turnover between consecutive replay periods
    └── Preserves zero-match periods and period-level failures in period summaries
    └── Separates as-of candidate occurrence / Research Priority from Post-Replay Outcome counts
    └── No Yahoo fetch, HistoricalReplayService call, scanner call, backtest rerun, probability, recommendation, optimization, strategy P&L, persistence, or OpenAI API

out_of_sample_validation_service.py
    └── Deterministic Out-of-Sample Validation Foundation for DEVELOPMENT / VALIDATION / HOLDOUT periods
    └── Validation periods are frozen, non-overlapping, chronological, and use inclusive start/end boundaries
    └── OutOfSampleValidationConfig preserves fixed SignalDefinition, OutcomeDefinition, replay frequency, overlap policy, cooldown, historical start, and minimum resolved samples
    └── FrozenResearchSpecification creates a deterministic fingerprint from materially relevant settings and excludes generated_at
    └── Loads each normalized symbol's full HistoricalPriceSeries once, then reuses the cache across all three period roles
    └── Reuses HistoricalReplayService point-in-time semantics and ReplayAnalyticsService period-local descriptive stability metrics
    └── Period results preserve requested/completed replay periods, candidate period share, unique candidate symbols, candidate occurrences, HIT / MISS / INCOMPLETE / NOT_EVALUABLE counts, Resolved n, and Historical Hit Rate
    └── Historical Hit Rate denominator remains HIT + MISS; INCOMPLETE and NOT_EVALUABLE are excluded and zero resolved samples produce None
    └── Cross-period comparison contains transparent raw differences and candidate-set Jaccard only
    └── No probability model, optimization, hidden score, Buy / Sell / Hold recommendation, position sizing, strategy P&L, persistence, or Batch B dashboard

historical_case_service.py
    └── Deterministic historical case explorer data builder
    └── HistoricalCaseWindowConfig with pre/post trading-bar windows
    └── HistoricalCaseView preserving SignalEvent reference levels, HistoricalOutcomeResult status, first hit, MFE, MAE, and end return
    └── HistoricalCasePricePoint with relative trading-bar indexes and actual OHLCV bars only
    └── HistoricalCaseConditionDetail copied from frozen signal evaluated conditions
    └── Requires signal date to exist in price series; no nearest-date lookup, synthetic bars, outcome recalculation, signal recalculation, probability, ranking, or persistence

historical_case_dashboard.py
    └── Historical Cases presentation helpers
    └── Case request fingerprinting, status filtering, deterministic sorting, case table rows, condition / snapshot rows, display formatting, and Altair chart specs
    └── Chart shows analysis close, raw high trace, frozen reference high, signal marker, and first-hit marker only for HIT cases
    └── No Yahoo fetch, SQLite access, OpenAI calls, signal calculation, outcome calculation, or scanner ranking

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
- AI Research tab orchestration through explicit form submit only
- Store AI Research sessions and verified turns only in `st.session_state`, without SQLite persistence or conversation memory
- Render grounded follow-up suggestions, explicit follow-up form, current turn, previous-turn research history, and session request/token counters
- Render grounded findings, selected evidence, limitations, missing data, validation status, and safe provider metadata
- Reuse existing core services instead of directly accessing Yahoo Finance, SQLite, or JSON
- Render Historical Cases tab through explicit submit only; keep case report / views in `st.session_state`, and rerender filters, sorting, selected case, x-axis mode, and expanders without refetching or rerunning backtests
- Render Swing Research tab through explicit scan submit only; store `SwingScannerResult`, scan fingerprint, last error, and scan-time price-series cache under `swing_research_*`; rerender candidate selection and case preview without refetching prices or rerunning scanner / backtest
- Render Walk-Forward Replay analytics from the existing session-state `WalkForwardReplayResult`; changing expanders, tables, and selected replay period rerenders stored results without refetching prices, rerunning replay, rerunning scanner, or rerunning backtests

---

### dashboard.py

Responsibilities:

- Format Stock values for dashboard display
- Build comparison table rows
- Run batch stock lookup with partial failure handling
- Keep dashboard presentation logic testable outside Streamlit widget callbacks
- Use `company_name_service.py` for presentation-only company display names
- Provide reusable display formatters for percentage, ratio, price, currency-aware large numbers, and N/A
- Build Historical Trends overview, section rows, chart rows, complete historical table rows, missing-data notes, and cache status text from `HistoricalFinancialSeries`
- Reuse `research_metrics.py` historical YoY helpers instead of recalculating YoY in `app.py`

---

### research_context.py

Responsibilities:

- Build a structured `ResearchContext` from already-normalized application/domain models.
- Purely assemble current `Stock`, deterministic `ResearchReport`, optional `HistoricalFinancialSeries`, and optional `HistoricalResearchReport`.
- Preserve current snapshot fields as raw numeric/text values, not UI-formatted strings.
- Group current snapshot data into Company, Market, Profitability, Growth, Financial Health, and Valuation contexts.
- Preserve historical period values, `period_end`, `period_year`, currency, `fetched_at`, and stale-cache status when historical series is supplied.
- Build per-metric source and derived `EvidenceItem` records with deterministic IDs and lineage.
- Link observations to supporting evidence or missing-data records through `ObservationEvidenceLink`.
- Keep explicit structured `missing_data` and `limitations` for current and historical inputs.
- Validate symbol consistency, evidence lineage, duplicate IDs, period consistency, and non-finite numeric values.
- Provide JSON-safe `ResearchContext.to_dict()` serialization.
- Provide the future shared input layer for AI Research Assistant, summary, export, and report generation.

Non-responsibilities:

- Building `ResearchReport` or `HistoricalResearchReport`
- Company-name cache lookup
- Yahoo Finance fetch
- SQLite SQL or persistence
- Streamlit widgets or display formatting
- AI / LLM generation
- Scoring, recommendation, target price, or ranking

---

### research_context_selector.py

Responsibilities:

- Select a deterministic AI-ready subset from an existing `ResearchContext`.
- Accept only explicit `ResearchQuestionType` enum values; do not classify natural-language questions.
- Apply centralized question-type to metric policies for company overview, profitability, growth, financial health, valuation, market position, historical-specific research, risks and attention, next steps, and general research.
- Apply historical window policy: all available annual periods for historical-specific questions, latest 3 periods for current-focused questions, metric-scoped full periods for general research, and no historical fundamentals for market position.
- Close derived evidence lineage recursively so selected derived evidence is never isolated from source evidence.
- Preserve observation traceability through `ObservationEvidenceLink` while selecting only relevant observation links.
- Keep stable observation link IDs independent from list ordering.
- Select and denoise relevant missing-data records without mutating the source `ResearchContext`.
- Select relevant limitations by question type.
- Apply optional `max_evidence` budget through atomic lineage groups.
- Provide JSON-safe `SelectedResearchContext.to_dict()` serialization and selector-specific validation.

Non-responsibilities:

- Yahoo Finance fetch
- SQLite persistence or schema changes
- Building `ResearchContext`, `ResearchReport`, or `HistoricalResearchReport`
- Streamlit rendering
- Natural-language routing
- Prompt generation
- OpenAI / ChatGPT / LLM calls
- Embeddings, vector database, or semantic search
- Buy / Sell / Hold recommendations, target prices, scores, ratings, or rankings

---

### ai_config.py

Responsibilities:

- Keep Grounded AI Research model, timeout, output-token, and input-length defaults in one module.
- Allow `OPENAI_MODEL` environment variable override.
- Avoid scattering model names or output settings across service modules.

Non-responsibilities:

- Reading or storing `OPENAI_API_KEY`
- Instantiating the OpenAI client
- Prompt construction
- Streamlit rendering

---

### ai_dashboard.py

Responsibilities:

- Centralize AI Research question-type labels, helper text, and placeholders for all `ResearchQuestionType` enum values.
- Build deterministic request fingerprints from symbol, question type, question, selected evidence IDs, missing-data IDs, and limitation IDs.
- Format selected evidence values and periods for UI display without mutating raw evidence values.
- Provide human-readable source-type labels for source and derived evidence.
- Resolve derived evidence lineage for presentation and handle missing lineage IDs safely.
- Format safe user-facing AI error messages and technical details without raw prompt, raw response, API key, or traceback leakage.
- Provide a boolean-only API key status helper.

Non-responsibilities:

- Calling OpenAI or any provider client
- Building prompts or structured output schemas
- Selecting Research Context
- Fetching Yahoo Finance or querying SQLite
- Persisting AI answers
- Streamlit widget rendering

---

### ai_followup.py

Responsibilities:

- Define frozen `AIResearchTurn` snapshots and session-level `AIResearchSession`.
- Build deterministic follow-up suggestions from AI next steps, deterministic next steps, missing data, and fallback policy.
- Infer follow-up `ResearchQuestionType` through local keyword rules only.
- Normalize and dedupe suggestion questions without embeddings or fuzzy AI matching.
- Build deterministic turn IDs and aggregate session token usage.

Non-responsibilities:

- Calling OpenAI or any provider
- Selecting `ResearchContext`
- Fetching Yahoo Finance or querying SQLite
- Persisting AI turns
- Rendering Streamlit widgets
- Chat history, conversation memory, embeddings, or AI routing

---

### ai_research_service.py

Responsibilities:

- Generate a structured `GroundedResearchAnswer` from an explicit user question and `SelectedResearchContext`.
- Accept only selected context, not full `ResearchContext`.
- Build an AI-specific payload instead of dumping `SelectedResearchContext.to_dict()`.
- Centralize developer instructions and prompt-injection boundary wording.
- Use OpenAI Responses API with strict JSON Schema structured output through a small client boundary.
- Read `OPENAI_API_KEY` only when the production OpenAI client is instantiated.
- Support test-time client injection so automated tests never call OpenAI, require network, require an API key, or incur billing.
- Parse structured provider output into dataclasses and attach service-generated metadata.
- Validate evidence IDs, empty factual citations, forbidden recommendation language, and minimal explicit percentage consistency.
- Convert configuration, provider, structured-output, and grounding failures into domain exceptions.

Non-responsibilities:

- Selecting context from full `ResearchContext`
- Natural-language question classification
- Yahoo Finance fetch
- SQLite persistence or AI response history
- Streamlit UI rendering
- Web search, file search, code interpreter, or provider tools
- Full natural-language fact checking
- Buy / Sell / Hold recommendations, target prices, scores, ratings, or rankings

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

### historical_research_service.py

Responsibilities:

- Build a deterministic `HistoricalResearchReport` from `HistoricalFinancialSeries`
- Keep historical interpretation rules outside `app.py`, `dashboard.py`, `database.py`, and `historical_financial_service.py`
- Reuse `ResearchObservation` and `ResearchNextStep` explainability structures
- Describe historical facts with `what_happened`, `why_it_matters`, and `what_to_check`
- Check data sufficiency before trend wording
- Reuse `research_metrics.py` consecutive-year semantics instead of creating separate YoY rules
- Compare margin changes in percentage points
- Compare Capital Expenditure spending scale with `abs(capital_expenditure)` because Yahoo commonly reports CapEx as negative cash outflow
- Avoid AI, LLM, buy / sell / hold recommendations, target prices, overall scores, and rating systems

---

### historical_interpretation_presentation.py

Responsibilities:

- Build Historical Highlights from existing deterministic observations
- Keep highlight selection, detailed category grouping, and next-step display cleanup outside `app.py`
- Group Detailed Interpretation by fixed category order
- Deduplicate next-step items by deterministic normalized exact text
- Limit default next-step display while preserving overflow items for collapsed expanders
- Avoid recalculating historical financial metrics or creating scoring / ranking semantics

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

### company_summary_service.py

Responsibilities:

- Build Research page company summary display data without overwriting `Stock.company_summary`
- Prefer Taiwan official public data for Taiwan stocks when usable business-item content is available
- Use TWSE / TPEx company profile data to identify company code, name, industry, and business accounting number
- Use MOEA company registration business items to assemble a short Chinese company introduction
- Fall back to Yahoo Finance English `company_summary` when localized official content is unavailable
- Store a lightweight runtime JSON cache in `data/taiwan_company_summaries.json`
- Avoid AI, LLM, translation APIs, web scraping, SQLite schema changes, and raw model mutation

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

### historical_financial_service.py

Responsibilities:

- Retrieve Yahoo Finance annual `income_stmt`, `cashflow`, and `balance_sheet`
- Keep Yahoo raw financial statement DataFrame handling outside UI and database code
- Normalize statement row labels through centralized alias priority lists
- Build `HistoricalFinancialSeries` and `HistoricalFinancialPeriod`
- Calculate historical margins from annual revenue and income statement values
- Use direct Yahoo `Free Cash Flow` when available
- Derive Free Cash Flow as `Operating Cash Flow + Capital Expenditure` when direct FCF is unavailable
- Sort normalized periods oldest to newest
- Set `period_year` from the year component of `period_end`; this is not official fiscal-year metadata
- Use independent 7-day historical cache before refreshing Yahoo
- Return stale historical cache with `is_stale=True` when Yahoo refresh fails and stale data exists

---

### historical_price_service.py

Responsibilities:

- Retrieve Yahoo Finance daily price history through `Ticker.history()`
- Use `auto_adjust=False` and `actions=True`
- Normalize Yahoo daily rows into immutable `HistoricalPriceBar` objects
- Return chronological `HistoricalPriceSeries` objects
- Normalize timezone-aware Yahoo daily indexes to provider-local `datetime.date`
- Preserve raw OHLC, adjusted close, volume, dividends, and stock splits
- Validate retained bars for finite positive prices, price relationships, and non-negative volume
- Collapse identical duplicate dates and deterministically keep the last conflicting duplicate while recording quality issues
- Use 12-hour price-history cache before refreshing Yahoo
- Use fetch-state coverage metadata so fresh partial cache does not satisfy full-history or wider explicit range requests
- Return stale cache with `is_stale=True` when Yahoo refresh fails and a covered stale range exists
- Provide `get_analysis_close()`, `slice_price_series_as_of()`, and `get_recent_bars()` helpers

Non-responsibilities:

- Technical indicators
- Signals
- Outcomes
- Backtests
- Charts
- Scanner UI
- AI / LLM generation
- Future probability or calibrated probability

---

### database.py

Responsibilities:

- Initialize SQLite database automatically
- Persist Stock model fields in `data/stocks.db`
- Apply simple additive SQLite schema migrations for new Stock snapshot fields
- Return fresh cached Stock data when `fetched_at` is within 24 hours
- Persist historical fundamentals in a separate `historical_financials` table
- Return fresh cached historical fundamentals when `fetched_at` is within 7 days
- Persist daily historical prices in a separate `historical_prices` table
- Persist price-history coverage metadata in `historical_price_fetch_state`
- Persist saved research universes in `research_universes` and ordered membership in `research_universe_symbols`
- Return fresh cached historical prices when requested rows are within 12 hours and range coverage is sufficient
- Preserve stale historical cache rows if Yahoo refresh fails
- Keep SQL persistence details outside `main.py` and `models.py`

---

### watchlist_service.py

Responsibilities:

- Persist Watchlist data in `data/watchlist.json`
- Add, remove, and list normalized stock symbols
- Handle missing, empty, or invalid watchlist files safely

---

### universe_service.py

Responsibilities:

- Persist multiple named research Universes in SQLite
- Keep Universe separate from Watchlist
- Validate required names, optional descriptions, stable ids, timestamps, and symbol membership
- Normalize and dedupe symbols with first-seen order preservation
- Provide create, get, list, update, delete, add, remove, and replace APIs
- Use transactions for multi-table writes
- Raise domain errors instead of raw SQLite errors for user-facing workflows
- Never call Yahoo Finance, OpenAI, scanner, backtest, or AI services during CRUD

---

### universe_dashboard.py

Responsibilities:

- Parse Universe symbol text with the shared normalization path
- Build Universe labels, source snapshots, and source/content fingerprints
- Keep Streamlit formatting helpers separate from SQLite and network access
- Preserve scan-time symbol snapshots for Manual Input, Watchlist, and Saved Universe sources

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
    - HistoricalFinancialPeriod
    - HistoricalFinancialSeries
    - HistoricalPriceBar
    - HistoricalPriceSeries
    - ResearchUniverse

### research_metrics.py

Responsibilities:

- Provide deterministic helper metrics for future research presentation
- Keep derived metrics separate from Yahoo raw mapping and SQLite persistence
- Avoid AI analysis, scoring, or buy / sell judgement
- Calculate deterministic historical YoY growth helpers only for consecutive `period_year` values and without trend classification

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

## Historical Fundamentals Data Flow

```
Caller
   │
   ▼
historical_financial_service.py
   │
   ├── database.py
   │      │
   │      ├── Fresh 7-day cache hit
   │      │      ▼
   │      │   HistoricalFinancialSeries
   │      │
   │      └── Cache missing / expired
   │
   ▼
Yahoo Finance annual statements
   │
   ├── income_stmt
   ├── cashflow
   └── balance_sheet
   │
   ▼
Alias normalization + deterministic derived metrics
   │
   ▼
HistoricalFinancialSeries
   │
   ▼
database.py
   │
   ▼
historical_financials table
```

## Snapshot vs Historical Responsibilities

Current snapshot:

- Model: `Stock`
- Table: `stocks`
- TTL: 24 hours
- Source surface: `yfinance.Ticker.info`
- Scope: latest available price, valuation, profitability, growth, cash/debt, company summary fields

Historical fundamentals:

- Model: `HistoricalFinancialSeries` containing `HistoricalFinancialPeriod`
- Table: `historical_financials`
- TTL: 7 days
- Source surface: annual `income_stmt`, `cashflow`, and `balance_sheet`
- Scope: annual revenue, profit, EPS, margins, cash flow, assets, debt, equity, cash

The Streamlit UI and console UI do not parse Yahoo financial statement DataFrames. Database code does not own Yahoo row label semantics.

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

## Taiwan Company Summary Localization Flow

```
Stock
  │
  ├── Yahoo company_summary remains unchanged
  │
  ▼
app.py Research tab
  │
  ▼
company_summary_service.py
  │
  ├── Fresh JSON cache hit
  │      ▼
  │   Localized display summary
  │
  └── Cache miss / expired
         │
         ├── TWSE / TPEx official company profile
         ├── MOEA company registration business items
         └── data/taiwan_company_summaries.json
```

Company summary localization is presentation-only. `Stock.company_summary` continues to represent the Yahoo Finance `longBusinessSummary` value used by the stock data service and SQLite stock cache.

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

## Research Universe Flow

```
User
   │
   ▼
app.py Universes tab
   │
   ▼
universe_dashboard.py
   │
   ▼
universe_service.py
   │
   ▼
SQLite research_universes / research_universe_symbols
```

Universe CRUD is local-only and does not call Yahoo Finance, OpenAI, scanner, backtest, or signal services.

## Swing Research Source Flow

```
Manual Input / Watchlist / Saved Universe
   │
   ▼
Source resolver in app.py
   │
   ▼
scan-time normalized symbols snapshot
   │
   ▼
SwingScannerService
   │
   ▼
SwingScannerResult + source metadata in session state
```

Watchlist, Universe, and scanner result are separate state concepts. A saved Universe is only a research symbol collection; membership does not imply recommendation, bullishness, prediction, or higher historical hit rate. Scanner result identity includes source mode and resolved symbols, so editing Universe membership after a scan marks the current configuration as different without mutating the stored result.

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
   ├── company_summary_service.py company summary display helper
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

## Streamlit Historical Trends Flow

```
User
   │
   ▼
app.py Historical Trends tab
   │
   ├── symbol_utils.py
   ├── dashboard.py query_stock_batch()
   └── historical_financial_service.py get_historical_financials()
          │
          ├── database.py / 7-day SQLite historical cache
          └── Yahoo Finance annual statements when cache is missing or expired
   │
   ▼
Stock + HistoricalFinancialSeries
   │
   ▼
dashboard.py
   │
   ├── Historical overview display
   ├── Revenue / Earnings / Margins / Cash Flow / Financial Position rows
   ├── Complete formatted historical table
   ├── Chart-ready numeric rows
   └── Missing-data and stale-cache presentation text
   │
   ▼
app.py Streamlit layout and native charts
```

Historical Trends is a presentation layer. `app.py` does not parse Yahoo financial statement DataFrames, handle row aliases, execute SQL, calculate margins, derive Free Cash Flow, or calculate YoY itself.

## Historical Price Foundation Flow

```
Future quantitative research caller
   │
   ▼
historical_price_service.py get_historical_prices()
   │
   ├── symbol_utils.py normalize_stock_symbol()
   ├── database.py historical_prices / historical_price_fetch_state
   └── Yahoo Finance Ticker.history() when cache is missing, expired, or range-incomplete
   │
   ▼
HistoricalPriceSeries
   │
   ├── get_analysis_close()
   ├── slice_price_series_as_of()
   └── get_recent_bars()
   │
   ▼
Future Technical Feature Layer
   │
   ▼
Future Backtest Engine
```

Historical Price Foundation is not connected to Streamlit UI in Batch A. It is separate from current `Stock` snapshot cache and annual `HistoricalFinancialSeries` fundamentals.

Historical Trends keeps these presentation semantics:

- Period labels use `FY ending YYYY-MM-DD`.
- YoY is delegated to `research_metrics.py` and only appears when adjacent period years are consecutive.
- Missing values display as `N/A`; missing EPS is not self-calculated.
- Currency context is preserved and no FX conversion or cross-currency ranking is performed.
- The page displays values and visible trends only; it does not classify a company or metric as improving, deteriorating, strong, weak, good, bad, healthy, or unhealthy.

## Streamlit Historical Interpretation Flow

```
HistoricalFinancialSeries
   │
   ▼
historical_research_service.py
   │
   ├── Revenue observations
   ├── Earnings / EPS observations
   ├── Margin percentage-point observations
   ├── Cash Flow and CapEx spending-scale observations
   ├── Financial Position observations
   ├── Cross-metric observations
   └── Historical Research Next Steps
   │
   ▼
HistoricalResearchReport
   │
   ▼
historical_interpretation_presentation.py
   │
   ├── Historical Highlights
   ├── Detailed Interpretation groups
   └── Display-ready Research Next Steps
   │
   ▼
app.py Historical Trends tab
```

Historical Interpretation is deterministic. It may describe directly supported historical changes such as Revenue declining and later recovering, EPS missing for the latest period, or Capital Expenditure spending scale increasing. Possible business reasons are only rendered as research checklist items.

## Research Context Flow

```
Stock
   │
   ├── research_service.py
   │      └── ResearchReport
   │
   ├── HistoricalFinancialSeries
   │      └── historical_research_service.py
   │             └── HistoricalResearchReport
   │
   ▼
research_context.py
   │
   ├── CurrentSnapshotContext
   ├── FundamentalResearchContext
   ├── HistoricalFinancialsContext
   ├── HistoricalResearchContext
   ├── EvidenceItem
   ├── ObservationEvidenceLink
   ├── ResearchLimitation
   └── MissingDataItem
   │
   ▼
ResearchContext
   │
   ├── Future AI Research Assistant input
   ├── Future Research Summary input
   ├── Future Export input
   └── Future Report generation input
```

Research Context is the application/domain integration boundary for future AI and report workflows. It consumes validated and normalized models only. It does not read Yahoo raw dictionaries, SQLite rows, Streamlit widget state, or UI-formatted strings. Detailed contract: `docs/RESEARCH_CONTEXT.md`.

# Future Modules

Planned modules:

- financial_service.py
- news_service.py
- ai_service.py
- report_service.py
