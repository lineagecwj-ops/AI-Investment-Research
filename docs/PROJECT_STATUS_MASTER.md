# AI Investment Research Project Status Master

Last updated: 2026-08-15, after Sprint 6C Portfolio Persistence Integration.

## Project Purpose

Project: AI Investment Research

Purpose: 建立可重現、可驗證的 AI 投資研究平台。此文件供未來 ChatGPT / Codex session 快速恢復專案上下文，並避免把已推送狀態、目前工作樹、研究架構與 production scanner 邊界混在一起。

## Information Sources

This status document is based on:

- `git status --short`
- `git rev-parse HEAD`
- `git branch --show-current`
- `git branch -vv`
- `git log --oneline --decorate -n 40`
- repository structure under `docs/`, `src/`, and `tests/`
- existing validation evidence from the Long-Term Growth Phase 7A-7L pushed state
- Phase 8A Portfolio Risk Dashboard Foundation release validation
- Technical Risk v1 OOS / production contract source inspection under `src/risk_oos/`, `src/risk_evaluation/`, `src/risk_integration/`, and `src/targets/`
- Sprint 4A Production Technical Risk Policy release validation evidence
- Sprint 4B Deterministic Technical Risk Evaluator release validation evidence
- Sprint 4C TechnicalRiskSignalProducer release validation evidence
- Sprint 4D TechnicalRiskProductionService release validation evidence
- Sprint 5A TechnicalRiskArtifactAdapter release validation evidence
- Sprint 5B-1 TechnicalRiskPortfolioEvaluator release validation evidence
- Sprint 5B-2 PortfolioRiskGenerationService Technical Integration Validation release validation evidence
- Sprint 6A-1 RiskArtifactCodec release validation evidence
- Sprint 6A-2 DB-agnostic Artifact Persistence Protocol Contracts release validation evidence
- Sprint 6B-1 SQLite RiskArtifactRepository Core release validation evidence
- Sprint 6B-2A Technical Risk Artifact Query / Index Contracts release validation evidence
- Sprint 6B-2B-1 SQLite Schema v2 + Technical Index Backfill release validation evidence
- Sprint 6B-2B-2 SQLite Technical Query Repository release validation evidence
- Sprint 6B-2B-3 Atomic Technical Artifact Persistence release validation evidence
- Sprint 6C-1 Portfolio Risk Generation Run Record release validation evidence
- Sprint 6C-2 SQLite Schema v3 + Portfolio Risk Generation Run Repository release validation evidence
- Sprint 6C-3 Technical Portfolio Persistence Coordinator + Portfolio-Level Atomic Persistence release validation evidence

No network fetch, DB migration, live DB schema inspection, or production data query was used to create this document.

## Current Git Status

- Branch: `main`
- Implementation baseline: `2486fbb feat: add atomic portfolio risk persistence`
- Current full HEAD: `2486fbb3df0569afb1ba274bbf9d51e73e9dd2c0`
- Remote baseline at synchronization time: `origin/main` points to `2486fbb3df0569afb1ba274bbf9d51e73e9dd2c0`
- Documentation status: this file is being synchronized after Sprint 6C release pushes.
- Documentation update status: currently local until committed and pushed.
- Current Phase 7A-7L Long-Term Growth files are committed and pushed.
- Phase 8A Portfolio Risk Dashboard Foundation implementation is committed and pushed at `0d71d85`.
- Technical Risk v1 OOS research contracts through Research Policy Freeze are committed and pushed through `f568b74`.
- Technical Risk v1 Production Technical Risk Policy Promotion is committed and pushed at `3fa2682`.
- Technical Risk v1 Deterministic Technical Risk Evaluator is committed and pushed at `3deb445`.
- Technical Risk v1 TechnicalRiskSignalProducer Integration is committed and pushed at `ed37aea`.
- Technical Risk v1 End-to-End Production Integration / Orchestration is committed and pushed at `52e0b39`.
- Technical Risk v1 Technical Risk Artifact Adapter is committed and pushed at `10f325b`.
- Technical Risk v1 Technical Risk Portfolio Evaluator is committed and pushed at `6ca59a5`.
- Technical Risk v1 PortfolioRiskGenerationService Technical Integration Validation is committed and pushed at `f25baf7`.
- Sprint 6A-1 RiskArtifactCodec is committed and pushed at `f84c79a`.
- Sprint 6A-2 DB-agnostic Artifact Persistence Protocol Contracts are committed and pushed at `1d57d8e`.
- Sprint 6B-1 SQLite RiskArtifactRepository Core is committed and pushed at `2c20c32`.
- Sprint 6B-2A Technical Risk Artifact Query / Index Contracts are committed and pushed at `8049063`.
- Sprint 6B-2B-1 SQLite Schema v2 + Technical Index Backfill is committed and pushed at `a93681b`.
- Sprint 6B-2B-2 SQLite Technical Query Repository is committed and pushed at `24ca9c7`.
- Sprint 6B-2B-3 Atomic Technical Artifact Persistence is committed and pushed at `5a56172`.
- Sprint 6C-1 Portfolio Risk Generation Run Record Contract + Codec is committed and pushed at `2616478`.
- Sprint 6C-2 SQLite Schema v3 + Portfolio Risk Generation Run Repository is committed and pushed at `b9bd272`.
- Sprint 6C-3 Technical Portfolio Persistence Coordinator + CapturingRiskEvaluator + Portfolio-Level Atomic Persistence is committed and pushed at `2486fbb`.

Repository state verification:

- Do not rely on this document for exact current repository HEAD.
- Exact current HEAD must be verified from live Git state with `git rev-parse HEAD`.
- Remote alignment must be verified from live Git state with `git status --short --branch`.
- Recent repository history must be verified from live Git state with `git log --oneline --decorate`.

Important: Long-Term Growth Phase 7A-7L is part of Git history through `f834e40`.
Phase 8A Portfolio Risk Dashboard Foundation is part of Git history at `0d71d85`.
Technical Risk v1 production policy promotion is part of Git history at `3fa2682`.

## Recent Pushed History

Latest pushed milestones visible in `git log --oneline --decorate`:

- `2486fbb feat: add atomic portfolio risk persistence`
- `b9bd272 feat: add sqlite portfolio risk run repository`
- `2616478 feat: add portfolio risk generation run records`
- `1c7e064 docs: sync project master status through sprint 6b`
- `5a56172 feat: add atomic technical risk artifact persistence`
- `24ca9c7 feat: add sqlite technical risk artifact queries`
- `a93681b feat: add sqlite risk artifact schema v2`
- `8049063 feat: add technical risk artifact query contracts`
- `affceea docs: sync project master status through sprint 6b-1`
- `2c20c32 feat: add sqlite risk artifact repository`
- `1d57d8e feat: add risk artifact persistence contracts`
- `f84c79a feat: add risk artifact codec`
- `f9955c7 docs: sync project master status through sprint 5b`
- `f25baf7 test: validate technical risk portfolio integration`
- `6ca59a5 feat: add technical risk portfolio evaluator`
- `10f325b feat: add technical risk artifact adapter`
- `f025b4a docs: sync project master status through sprint 4d`
- `52e0b39 feat: add technical risk production orchestration`
- `8cf8751 docs: sync project master status through sprint 4c`
- `ed37aea feat: add technical risk signal producer`
- `3deb445 feat: add deterministic technical risk evaluator`
- `dac77f2 docs: sync project master status through sprint 4a`
- `3fa2682 feat: add production technical risk policy promotion`
- `f568b74 feat: add technical risk research policy freeze`
- `62267d3 feat: add holdout confirmation contracts`
- `7e62bfc feat: add validation selection artifact`
- `0834ab9 feat: add validation shortlist contracts`
- `a0842fd feat: add development exploration contracts`
- `2bd310b feat: add technical risk candidate evaluator`
- `136dca8 feat: add technical risk rule candidate contracts`
- `c9ce306 feat: add aligned technical risk oos dataset`
- `8d9f021 feat: add target window lineage`
- `da315d9 feat: add historical risk feature materialization`
- `01c493a feat: add MAE target generators`
- `5d7ec8d feat: add technical as-of close input contract`
- `d62349d feat: add risk evaluation production contracts`
- `cbd6b8b feat: add portfolio risk generation service framework`
- `14b3c51 feat: add portfolio generation contract builders`
- `6f4ffb4 feat: add portfolio state generation contracts`
- `8d638c8 feat: wire portfolio dashboard to artifact provider`
- `75fbec2 feat: add read-only portfolio artifact repository`
- `1ceb765 feat: add risk monitoring artifact serialization contract`
- `d0ece5a feat: add portfolio artifact input contract`
- `29da177 docs: update project status after phase 8a`
- `0d71d85 feat: add read-only portfolio risk dashboard foundation`
- `1f7ba4a docs: update project status after phase 7l`
- `f834e40 feat: add risk monitoring integration framework`
- `3a5f92f docs: update project status master`
- `31c567c feat: add portfolio risk engine framework`
- `f5f3581 feat: add model and oos evaluation framework`
- `384b22b feat: add training dataset framework`
- `9fcd50a feat: add feature and target framework`
- `e15cede docs: add long-term growth architecture documentation`
- `677fc52 feat: add swing scanner PDF export`
- `432db3a test: make live cache isolation tests time deterministic`
- `752fd23 docs: document database architecture separation`
- `54132a9 docs: add research snapshot release manifests`

## Major Milestone Summary

### Phase 6: Database Architecture Separation

Status: complete and pushed.

Included components:

- `DatabasePathConfig`
- `ResearchDataStore`
- `LiveDataStore`
- physical database separation
- corrected Research Store
- runtime DB protection
- release manifests for research snapshots

Current interpretation:

- Research and Live data stores are separated by architecture and tests.
- Production scanner and research snapshot workflows must remain isolated.
- Database separation is preserved by the committed Long-Term Growth work.

### PDF Export: Swing Scanner PDF Export

Status: complete and pushed.

Architecture boundary:

- PDF Export uses Scan Result Snapshot -> PDF.
- PDF Export must not recalculate scanner results.
- Long-Term Growth and Risk Engine work must not modify PDF Export.

## Long-Term Growth Status

The following phases are committed and pushed through `f834e40`.

| Phase | Name | Status |
|---|---|---|
| 7A | AI Architecture Design | Complete / committed / pushed |
| 7B | Feature Engineering Framework | Complete / committed / pushed |
| 7C | Feature Calculation Engine | Complete / committed / pushed |
| 7D | Feature Pipeline | Complete / committed / pushed |
| 7E | Training Dataset Framework | Complete / committed / pushed |
| 7F | Target Generation Framework | Complete / committed / pushed |
| 7G | Target Generator | Complete / committed / pushed |
| 7H | Training Dataset Builder | Complete / committed / pushed |
| 7I | Baseline Model Framework | Complete / committed / pushed |
| 7J | OOS Evaluation Framework | Complete / committed / pushed |
| 7K | Portfolio Risk Engine Framework | Complete / committed / pushed |
| 7L | Risk Monitoring Integration | Complete / PASS |

## Phase 8 Status

| Phase | Name | Status |
|---|---|---|
| 8A | Portfolio Risk Dashboard Foundation | Complete / committed / pushed |
| 8B | Portfolio Artifact Input Contract | Complete / committed / pushed |
| 8C | Risk Monitoring Artifact Serialization | Complete / committed / pushed |
| 8D | Read-only Portfolio Artifact Repository | Complete / committed / pushed |
| 8E | Portfolio Dashboard Artifact Provider Wiring | Complete / committed / pushed |
| 8F | Portfolio State / Portfolio Generation Service Framework | Complete / committed / pushed |

## Technical Risk v1 Status

| Sprint | Name | Status |
|---|---|---|
| Contract Sprint 1 | Risk Evaluation Production Contracts | Complete / committed / pushed |
| Prerequisite Sprint A | Technical as-of close input contract | Complete / committed / pushed |
| Prerequisite Sprint B | MAE Target Generators | Complete / committed / pushed |
| OOS Sprint 1 | Historical Risk Feature Materialization | Complete / committed / pushed |
| OOS Sprint 2A | Target Window Lineage Extension | Complete / committed / pushed |
| OOS Sprint 2B | Aligned Technical Risk OOS Dataset | Complete / committed / pushed |
| Sprint 3A | Candidate / Threshold / Derived Evidence Contracts | Complete / committed / pushed |
| Sprint 3B | Candidate Evaluator | Complete / committed / pushed |
| Sprint 3C-A | Development Exploration Contracts | Complete / committed / pushed |
| Sprint 3C-B1 | Development Shortlist Contracts | Complete / committed / pushed |
| Sprint 3C-B2 | Validation Selection Artifact | Complete / committed / pushed |
| Sprint 3C-C1 | Holdout Confirmation Contracts | Complete / committed / pushed |
| Sprint 3C-C2 | Research Policy Freeze Artifact | Complete / committed / pushed |
| Sprint 4A | Production Technical Risk Policy Contract and Controlled Promotion Boundary | Complete / committed / pushed |
| Sprint 4B | Deterministic Technical Risk Evaluator and Evaluation Result | Complete / committed / pushed |
| Sprint 4C | TechnicalRiskSignalProducer Integration and RiskSignal Projection | Complete / committed / pushed |
| Sprint 4D | End-to-End Production Integration / Orchestration | Complete / committed / pushed |
| Sprint 5A | Technical Risk Artifact Adapter | Complete / committed / pushed |
| Sprint 5B-1 | Technical Risk Portfolio Evaluator / Production Input Provider | Complete / committed / pushed |
| Sprint 5B-2 | PortfolioRiskGenerationService Technical Integration Validation | Complete / committed / pushed |
| Sprint 5B | In-memory Portfolio Generation Technical Risk Integration | Complete / committed / pushed |
| Sprint 6A-1 | RiskArtifactCodec | Complete / committed / pushed |
| Sprint 6A-2 | DB-Agnostic Artifact Persistence Protocol Contracts | Complete / committed / pushed |
| Sprint 6B-1 | SQLite RiskArtifactRepository Core | Complete / committed / pushed |
| Sprint 6B-2A | Technical Risk Artifact Query / Index Contracts | Complete / committed / pushed |
| Sprint 6B-2B-1 | SQLite Schema v2 + Technical Index Backfill | Complete / committed / pushed |
| Sprint 6B-2B-2 | SQLite Technical Query Repository + Verified Read | Complete / committed / pushed |
| Sprint 6B-2B-3 | Atomic Technical Artifact Persistence | Complete / committed / pushed |
| Sprint 6B | Technical Risk SQLite Storage Layer | Complete / committed / pushed |
| Sprint 6C-1 | Portfolio Risk Generation Run Record Contract + Codec | Complete / committed / pushed |
| Sprint 6C-2 | SQLite Schema v3 + Portfolio Run Repository | Complete / committed / pushed |
| Sprint 6C-3 | Technical Portfolio Persistence Coordinator + CapturingRiskEvaluator + Portfolio-Level Atomic Persistence | Complete / committed / pushed |
| Sprint 6C | Portfolio Persistence Integration Capability | Complete / committed / pushed |

## Current AI Platform Architecture

Current intended architecture after Sprint 6C:

```text
Research Snapshot
    |
    v
Feature / Target Pipeline
    |
    v
Training Dataset Framework
    |
    v
Model Framework
    |
    v
OOS Evaluation
    |
    v
Portfolio Risk Engine
    |
    v
Risk Assessment Artifact
    |
    v
Risk Monitoring Framework
    |
    v
RiskMonitoringArtifact
    |
    v
Portfolio Dashboard Projection
    |
    v
Read-only Streamlit View
    |
    v
Portfolio Risk（風險檢視）

Technical Risk v1 research / production path:

Historical Technical Feature Materialization
    |
    v
Aligned Technical Risk OOS Dataset
    |
    v
Candidate / Threshold Contracts
    |
    v
Candidate Evaluator
    |
    v
Development Shortlist
    |
    v
Validation Selection
    |
    v
Holdout Confirmation
    |
    v
Research Policy Freeze
    |
    v
Controlled Production Policy Promotion
    |
    v
ProductionTechnicalRiskPolicy
    |
    v
TechnicalRiskProductionService
    |
    v
TechnicalRiskSignalProducer
    |
    v
TechnicalRiskEvaluator
    |
    v
TechnicalRiskEvaluationResult
    |
    v
ProducedRiskSignal / RiskSignal
    |
    v
RiskAssessment
    |
    v
TechnicalRiskProductionResult
    |
    v
TechnicalRiskArtifactAdapter
    |
    v
RiskEvaluationOutput / RiskArtifact
    |
    v
TechnicalRiskPortfolioEvaluator
    |
    v
PortfolioRiskGenerationService
    |
    v
CapturingRiskEvaluator
    |
    v
RiskArtifact(s)
    |
    v
PortfolioRiskGenerationResult
    |
    v
PortfolioRiskGenerationRunRecord
    |
    v
SQLiteTechnicalPortfolioRiskPersistenceCoordinator
    |
    v
single SQLite transaction
    |
    +--> risk_artifacts
    |
    +--> technical_risk_artifact_index
    |
    +--> portfolio_risk_generation_runs
    |
    v
SQLiteTechnicalRiskArtifactQueryRepository / SQLitePortfolioRiskGenerationRunRepository
```

In-memory generation path remains available and persistence-free:

```text
PortfolioSnapshot
    |
    v
PortfolioRiskGenerationService
    |
    v
existing MonitoringEvaluator
    |
    v
PortfolioRiskGenerationResult
```

Current RiskArtifact and portfolio run storage capability:

```text
RiskArtifact
    |
    v
RiskArtifactCodec
    |
    v
SQLiteTechnicalRiskArtifactPersistenceCoordinator
    |
    v
risk_artifacts
    |
    v
technical_risk_artifact_index
    |
    v
SQLiteTechnicalRiskArtifactQueryRepository

PortfolioRiskGenerationRunRecord
    |
    v
PortfolioRiskGenerationRunRecordCodec
    |
    v
SQLitePortfolioRiskGenerationRunRepository
    |
    v
portfolio_risk_generation_runs
```

The platform is research-oriented and artifact-oriented. It is not a trading system.

Persistence boundary: external portfolio persistence coordination capability exists through Sprint 6C, while `PortfolioRiskGenerationService` itself remains persistence-free and does not import `risk_persistence`. Production risk DB is not created or activated.

## Feature Platform Status

Committed feature framework modules are under `src/features/` and tests under `tests/features/`.

Included components:

- Feature Calculator
- Feature Registry
- Feature Validation
- Feature Checksum
- Feature Artifact
- Feature Artifact Generator
- technical calculator extension under `src/features/calculators/`

Current technical features:

- SMA20
- SMA60
- RSI14
- Volume Ratio

Design boundary:

- Feature calculations are deterministic.
- Current Production V1 technical formulas must not be modified by Long-Term Growth feature framework work.

## Target Platform Status

Committed target framework modules are under `src/targets/` and tests under `tests/targets/`.

Included components:

- Target Definition
- Target Context
- Target Generator
- Target Registry
- Target Artifact
- Target Artifact Generator
- Target Validation
- Target Checksum

Current targets:

- 20D regression
- 60D regression
- 60D classification
- MAE 20D regression: `TARGET_MAE_20D_REG_V1`
- MAE 60D regression: `TARGET_MAE_60D_REG_V1`

MAE v1 semantics:

- `MAE_ND = min(0, min(future_close_t / reference_close - 1))`
- reference price is reference date close
- reference day is excluded
- future window uses the next N trading observations
- price basis is daily close
- favorable-only future paths produce `0`, not a positive target value
- negative value represents downside adverse excursion relative to reference close
- full future window is required

Target window lineage:

- `TargetWindowLineage` exists for future-window targets.
- lineage fields include `target_start_date`, `target_end_date`, and `observations_used`
- window dates are actual trading observation dates, not calendar-day approximations
- `TargetDefinition.requires_window_lineage` is the source of truth for whether target output must include window lineage.
- target artifact checksum contract is `target_checksum_v2`.
- target checksum protects target value, target window lineage, and calculation lineage.

Design boundary:

- Target generation is for historical / research dataset construction.
- It must not be turned into a future prediction or production recommendation layer without explicit future scope.

## Dataset Platform Status

Committed dataset framework modules are under `src/datasets/` and tests under `tests/datasets/`.

Included components:

- Dataset Definition
- Dataset Context
- Dataset Registry
- Dataset Builder
- Dataset Artifact
- Dataset Validation
- Dataset Checksum
- Feature / Target join

Design boundary:

- Dataset construction is metadata-driven and reproducible.
- Feature and target lineage must remain explicit.

## Model Platform Status

Committed model framework modules are under `src/model_framework/` and tests under `tests/model_framework/`.

Included components:

- Model Definition
- Model Context
- Model Registry
- Model Artifact
- Experiment Tracking
- Model Evaluation
- Training interface
- Model Checksum

Current status:

- Baseline model framework exists.
- There is no production model.
- There is no production AI prediction layer.
- The package name is `model_framework` because the existing repository already has `src/models.py`.

## OOS Evaluation Status

Committed OOS evaluation modules are under `src/evaluation/` and tests under `tests/evaluation/`.

Included components:

- OOS Splitter
- Evaluation Definition
- Evaluation Context
- Evaluation Artifact
- Evaluation metrics framework
- Performance Tracker
- Evaluation Checksum

Evaluation design:

- Training period
- Validation period
- Frozen OOS period

Design boundary:

- OOS is an evaluation framework.
- It must not be treated as live prediction, live ranking, or a production trading signal.

## Portfolio Risk Engine Status

Committed risk framework modules are under `src/risk/` and tests under `tests/risk/`.

Included components:

- PortfolioPosition
- RiskDefinition
- RiskContext
- RiskSignal
- RiskAssessment
- RiskRegistry
- RiskArtifact
- RiskArtifactGenerator
- RiskChecksumGenerator

PortfolioPosition support:

- whole share
- fractional share
- `shares` uses `Decimal`

Risk categories:

- Technical Risk
- Fundamental Risk
- Market Risk
- Portfolio Risk

Risk outputs:

- RiskSignal
- RiskAssessment
- RiskArtifact

Risk aggregation:

- deterministic severity aggregation
- current rule: highest ordered severity wins
- supported severities: LOW, MEDIUM, HIGH, CRITICAL

Design boundary:

- Portfolio Risk Engine is not a trading system.
- Portfolio Risk Engine is not a buy/sell engine.
- Portfolio Risk Engine must not generate investment advice.
- Portfolio Risk Engine must not directly read LiveDataStore raw database, sqlite database, Scanner output, or PDF output.

## Risk Evaluation Production Contract Status

Committed risk evaluation production contract modules are under `src/risk_evaluation/` and tests under `tests/risk_evaluation/`.

Included components:

- `RiskFeatureInput`
- `RiskSignalProductionInput`
- `RiskEvaluationPolicy`
- `RiskEvaluationPolicyRegistry`
- `MissingDataPolicy`
- `RiskSignalProducer` Protocol
- `ProducedRiskSignal` lineage wrapper
- `ProductionTechnicalRiskPolicy`
- production technical risk rule / threshold / reason vocabulary
- `TechnicalRiskEvaluationInput`
- `TechnicalRiskDerivedEvidence`
- `TechnicalRiskPredicateState`
- `TechnicalRiskEvaluationResult`
- `TechnicalRiskEvaluator`
- `TechnicalRiskSignalProducer`
- `TechnicalRiskProductionService`
- `TechnicalRiskProductionResult`

Production technical feature vocabulary:

| Feature ID | Feature version |
|---|---|
| `TECH_AS_OF_CLOSE_V1` | `v1` |
| `TECH_SMA20_V1` | `v1` |
| `TECH_SMA60_V1` | `v1` |
| `TECH_RSI14_V1` | `v1` |

Deferred from Technical Risk v1:

- `TECH_VOLUME_RATIO_V1` remains deferred to v1.1 and is not part of the Technical Risk v1 executable required feature set.

RiskFeatureInput boundaries:

- frozen immutable input contract
- explicit `portfolio_id`, `position_id`, `symbol`, `as_of_date`, `feature_date`, `value`, `source_artifact_id`, `source_checksum`, and `calculation_id`
- numeric `Decimal`, `int`, and `float` values are supported
- `bool` values are rejected
- producer must not fetch market data, query DB, or run feature calculation

Technical as-of close semantics:

- `TECH_AS_OF_CLOSE_V1` means the frozen official / selected close observation for the evaluation `as_of_date`
- `feature_version` must be `v1`
- `feature_date` must equal `as_of_date`
- value must be positive
- it must not be interpreted as `average_cost`, latest runtime quote, valuation fallback, or current live quote

RiskSignalProductionInput boundaries:

- frozen per-position production input contract
- deterministic feature ordering
- duplicate feature id / version rejected
- portfolio, position, symbol, `as_of_date`, and `calculation_id` consistency enforced
- source artifact ids and checksums preserve lineage
- input contract does not read any external data

RiskEvaluationPolicy boundaries:

- immutable first-class policy contract
- includes policy id, version, enabled categories, required feature ids, category producer versions, severity rule representation, missing-data policy, and calculation metadata
- exact-version semantics are fail closed
- no latest fallback, default fallback, or silent substitution
- v1 missing-data policy is `FAIL_EVALUATION`
- current policy representation does not invent RSI, SMA, valuation, or fundamental thresholds

Producer protocol boundaries:

- `RiskSignalProducer` is a category-specific Protocol / interface
- `created_at` is caller-injected and must be timezone-aware
- protocol implementation must not call `datetime.now()` internally
- production `TechnicalRiskSignalProducer` exists for Technical Risk v1
- no production `FundamentalRiskSignalProducer`, `MarketRiskSignalProducer`, or `PortfolioRiskSignalProducer` exists yet

ProducedRiskSignal boundary:

- `ProducedRiskSignal` is a lineage wrapper around Phase 7K `RiskSignal`
- it preserves signal, policy id / version, producer version, source feature ids, source checksums, and calculation id
- Sprint 4C adds backward-compatible optional lineage fields: `policy_checksum`, `evaluation_id`, `evaluation_checksum`, `portfolio_id`, `position_id`, `as_of_date`, and `valuation_date`
- legacy producers may omit the new optional lineage fields
- `TechnicalRiskSignalProducer` must fill the extended lineage fields
- `source_feature_ids` and `source_checksums` remain parallel tuple representations; complete feature / checksum pair fidelity is protected primarily by `TechnicalRiskEvaluationResult.feature_references` plus `evaluation_checksum`
- it does not modify `RiskSeverity` or `RiskSignal` semantics

Production / research input separation:

- production `RiskFeatureInput` and research historical / OOS observations are different contracts
- production runtime must not use fake `portfolio_id` or `position_id` to represent research observations
- research OOS dataset rows must not be treated as production runtime inputs

## Technical Risk v1 OOS Research Status

Committed Technical Risk OOS modules are under `src/risk_oos/` and tests under `tests/risk_oos/`.

Historical feature materialization:

- implemented in `src/risk_oos/historical_features.py`
- exact Technical Risk v1 feature set is `TECH_AS_OF_CLOSE_V1`, `TECH_SMA20_V1`, `TECH_SMA60_V1`, and `TECH_RSI14_V1`
- consumes caller-provided frozen historical observations
- does not query DB or yfinance
- evaluation date close is exact for `TECH_AS_OF_CLOSE_V1`
- SMA / RSI lookback uses only observations with `trading_date <= evaluation_date`
- no fake `portfolio_id` or `position_id` is introduced in research materialization
- actual numeric feature values are preserved
- observation id and observation checksum are deterministic
- future leakage is rejected
- insufficient history cannot be rescued by future observations
- symbol isolation is enforced
- exclusions are explicit: `EXCLUDED_MISSING_AS_OF_CLOSE`, `EXCLUDED_INSUFFICIENT_REQUIRED_FEATURE_HISTORY`, `EXCLUDED_INVALID_PRICE`, and `EXCLUDED_FEATURE_CALCULATION_FAILED`

Aligned OOS dataset:

- supported split roles are `DEVELOPMENT`, `VALIDATION`, and `HOLDOUT`
- feature observation date must align with target reference date
- MAE20 and MAE60 targets are both required
- target window leakage guard requires target window end date to be within the split end date
- past feature lookback may cross split start
- future target windows must not cross split end
- upstream feature exclusions are accounted for
- dataset id and checksum are deterministic
- dataset stores frozen raw features, MAE values, and target lineage
- dataset rows do not store derived evidence, severity, candidate, threshold, or production risk signals

Derived technical evidence:

- `close_vs_sma20 = (close - SMA20) / SMA20`
- `close_vs_sma60 = (close - SMA60) / SMA60`
- `relative_sma_spread = (SMA20 - SMA60) / SMA60`
- `RSI14` is used as momentum confirmation evidence
- derived evidence is deterministic and uses `TECH_RISK_DECIMAL_CONTEXT_V1`
- Decimal context precision is `34`
- Decimal rounding is `ROUND_HALF_EVEN`
- Technical Risk arithmetic must not depend on external Decimal context
- Technical Risk arithmetic must not convert Decimal evidence / thresholds to float

Candidate / threshold contracts:

- candidate severities are `LOW`, `MEDIUM`, and `HIGH`
- `CRITICAL` is intentionally excluded from Technical Risk v1 candidate / production policy semantics
- threshold dimensions are exactly `close_vs_sma20_weakness_cutoff`, `close_vs_sma60_weakness_cutoff`, `relative_sma_spread_weakness_cutoff`, and `rsi14_weakness_confirmation_cutoff`
- threshold operator is `LESS_THAN_OR_EQUAL`
- threshold values are protected by threshold checksum
- candidate structural checksum excludes threshold values
- candidate A / B / C / D structures exist for research evaluation:
  - Candidate A: `MEDIUM_TERM_TREND_CENTRIC`
  - Candidate B: `STRUCTURE_FIRST`
  - Candidate C: `EARLY_WARNING_WITH_GUARDRAIL`
  - Candidate D: `STRICT_MULTI_EVIDENCE`
- Candidate C short price weakness alone can form `MEDIUM`, not `HIGH`
- Candidate D `HIGH` requires strict multi-evidence: medium price weakness, trend structure weakness, and momentum weakness confirmation
- no weighted score model is used
- Volume Ratio is excluded from Technical Risk v1 rule candidates

Candidate evaluator:

- evaluates one candidate and one threshold set at a time
- does not perform threshold search, optimization, ranking, winner selection, or `evaluate_best`
- uses deterministic Decimal context: precision `34`, rounding `ROUND_HALF_EVEN`
- MAE targets are used only for research outcome metrics, not for production severity generation
- output metrics include split x severity aggregate evidence
- metrics include `coverage_ratio`
- MAE20 and MAE60 metrics include mean, median, p25, and p75
- quantile contract is `TECH_RISK_QUANTILE_NEAREST_RANK_V1`
- monotonicity statuses are `PASS`, `WARNING`, and `NOT_EVALUABLE`
- empty severity buckets have sample count `0`, coverage `0`, and MAE metrics `None`
- no profit metric, trading score, or binary downside threshold is introduced by the evaluator contract

## Technical Risk v1 Research Governance Status

Development exploration:

- `DevelopmentEvaluationContext` describes a development-only experiment
- `ThresholdCandidateGenerationContract` describes threshold candidate generation metadata
- `TechnicalRiskCandidateSet` describes the candidate structures to explore
- semantic identities and checksums exclude audit timestamps
- no validation selection, holdout evaluation, winner selection, or production policy is created in this layer

Development shortlist:

- `DevelopmentShortlistArtifact` and `DevelopmentShortlistEligiblePair` define the validation-selectable universe
- eligible pairs are the only source of truth for validation selection
- no implicit Cartesian product authorization is allowed

Validation selection:

- `TechnicalRiskValidationSelectionArtifact` records validation selection result
- statuses are `SELECTED`, `NO_VALID_SELECTION`, and `TIE_REQUIRES_METHOD_DECISION`
- exactly one validation evaluation per eligible pair is required
- validation evidence must be `VALIDATION` only
- no automatic ranking, threshold optimization, or hidden search is introduced

Holdout confirmation:

- `TechnicalRiskHoldoutConfirmationArtifact` records holdout confirmation result
- statuses are `CONFIRMED`, `NOT_CONFIRMED`, `REVIEW_REQUIRED`, and `CONTAMINATION_DECLARED`
- holdout evidence must be `HOLDOUT` only
- holdout confirmation uses the exact selected candidate and threshold from validation selection
- no holdout search, optimization, or evaluator rerun is performed by the contract
- `CONTAMINATION_DECLARED` is a governance declaration
- current immutable contract does not truly enforce historical holdout single-use
- known governance gaps remain: historical run count, alternate holdout inspection, same-period reuse, and post-holdout retuning

Research policy freeze:

- `TechnicalRiskPolicyFreezeArtifact` is successful-freeze-only
- status is `FROZEN`
- reason is `RESEARCH_POLICY_FROZEN`
- requires Validation `SELECTED` and Holdout `CONFIRMED`
- stores immutable upstream lineage from validation selection, holdout confirmation, candidate, and threshold contracts
- remains a research artifact, not a production policy
- upstream freeze trust boundary is explicit; the freeze artifact does not claim independent recomputation of all upstream checksums

## Technical Risk v1 Production Policy Promotion Status

Committed production promotion modules are under `src/risk_integration/` with production-native policy contracts under `src/risk_evaluation/`.

Dependency direction:

```text
risk_oos      risk_evaluation
     \          /
      risk_integration
```

`src/risk_evaluation/` must not import `risk_oos` or `risk_integration`; `src/risk_integration/` is the promotion bridge that may depend on both research and production contracts.

Included components:

- `ProductionTechnicalRiskPolicy`
- `ProductionTechnicalRiskRule`
- `ProductionTechnicalRiskThresholdDimension`
- `ProductionTechnicalRiskPredicateId`
- `ProductionTechnicalRiskReasonCode`
- `ProductionTechnicalRiskThresholdOperator`
- `promote_research_freeze_to_production_policy`

Production policy promotion:

- requires actual `TechnicalRiskPolicyFreezeArtifact`
- requires actual candidate object and threshold object
- requires freeze status `FROZEN` and reason `RESEARCH_POLICY_FROZEN`
- preserves exact research freeze / candidate / threshold lineage
- copies frozen rule semantics and frozen threshold values into a production-native immutable policy
- protects copied rule semantics and threshold values by deterministic policy checksum
- does not reconstruct methodology
- does not perform candidate search, threshold search, scoring, ranking, or optimization
- does not automatically activate, deploy, or register a production policy

ProductionTechnicalRiskPolicy boundaries:

- immutable / frozen production policy contract
- deterministic policy id and policy checksum
- source Research Freeze lineage is preserved
- candidate identity and candidate checksum are preserved
- threshold identity and threshold checksum are preserved
- copied frozen rule semantics are preserved
- copied frozen threshold semantics include all four Decimal threshold values
- required feature set is exactly `TECH_AS_OF_CLOSE_V1`, `TECH_SMA20_V1`, `TECH_SMA60_V1`, and `TECH_RSI14_V1`
- required metadata includes derived evidence version, numeric context version, severity mapping version, and reason mapping version
- severity mapping supports `LOW`, `MEDIUM`, and `HIGH`
- `CRITICAL` is rejected for Technical Risk v1
- reason mapping is production-native and neutral
- threshold numeric fidelity is preserved with `Decimal`
- unsupported severity mapping version / reason mapping version fail closed

Current implementation boundary:

- Sprint 4A promotion itself does not evaluate technical risk and does not generate signals
- no activation registry
- no deployment API
- no DB, sqlite, yfinance, feature calculation execution, Risk Engine execution, Risk Monitoring execution, or dashboard integration

## Technical Risk v1 Production Runtime Status

Sprint 4B deterministic evaluator:

- `TechnicalRiskEvaluationInput` combines caller-supplied `RiskSignalProductionInput` with `ProductionTechnicalRiskPolicy`
- `TechnicalRiskEvaluator` resolves and validates the exact required feature set: `TECH_AS_OF_CLOSE_V1`, `TECH_SMA20_V1`, `TECH_SMA60_V1`, and `TECH_RSI14_V1`
- feature id and feature version are both validated; all four production features use version `v1`
- missing required feature fails closed
- semantic arithmetic uses isolated `TECH_RISK_DECIMAL_CONTEXT_V1`
- Decimal context precision is `34`
- Decimal rounding is `ROUND_HALF_EVEN`
- external global Decimal context does not affect evaluator result
- evaluator arithmetic does not convert Decimal evidence or thresholds to float
- derived evidence formulas are:
  - `close_vs_sma20 = (as_of_close - sma20) / sma20`
  - `close_vs_sma60 = (as_of_close - sma60) / sma60`
  - `relative_sma_spread = (sma20 - sma60) / sma60`
- `RSI14` is used directly as momentum predicate input
- required predicates must all be `TRUE` for a rule to match
- optional confirmations are annotations only
- rule precedence is `HIGH` -> `MEDIUM` -> `LOW` fallback
- same-severity matches use smaller `rule_priority`
- Technical Risk v1 evaluator can return `LOW`, `MEDIUM`, or `HIGH`
- `CRITICAL` fails closed in v1

TechnicalRiskEvaluationResult lineage:

- deterministic evaluation id and checksum
- evaluator version and numeric context version
- production policy identity and checksum
- portfolio / position context
- symbol, `as_of_date`, `valuation_date`, and calculation lineage
- feature lineage and source lineage
- derived evidence
- predicate states
- matched rule id and matched rule priority
- severity and reason codes

Sprint 4B responsibility boundary:

- evaluator validates required features, resolves production inputs, computes derived evidence, evaluates predicates, applies rule hierarchy, and produces deterministic evaluation result lineage
- evaluator does not query DB, sqlite, yfinance, historical materializer, OOS dataset, MAE targets, Holdout artifacts, dashboard, or activation state
- evaluator does not create `RiskSignal` or `ProducedRiskSignal`
- technical severity is methodology-driven and must not change because of shares, quantity, or exposure metadata
- per-position lineage can change evaluation identity / checksum without changing technical methodology severity

Sprint 4C TechnicalRiskSignalProducer:

- `TechnicalRiskSignalProducer` is compatible with the `RiskSignalProducer` Protocol
- policy must be caller supplied as an explicit `ProductionTechnicalRiskPolicy`
- generic `RiskEvaluationPolicy` is not accepted as a Technical Risk methodology policy
- `created_at` is caller injected and must be timezone-aware
- producer invokes `TechnicalRiskEvaluator.evaluate()` exactly once
- producer projects `TechnicalRiskEvaluationResult` into `RiskSignal` and `ProducedRiskSignal`
- producer preserves policy, evaluation, portfolio, position, source, date, calculation, and producer lineage
- input / policy / evaluation mismatch fails closed
- source lineage mismatch fails closed
- evaluator error fails closed
- producer does not recalculate derived evidence, predicates, rule matching, rule priority, or severity
- producer does not perform policy lookup, latest fallback, default fallback, registry fallback, activation, deployment, DB access, sqlite access, yfinance access, feature calculation, dashboard integration, scheduler work, OOS access, MAE access, or Holdout access

RiskSignal projection:

- `risk_id` is `TECHNICAL_DOWNSIDE_RISK_V1`
- `category` is `RiskCategory.TECHNICAL`
- severity preserves evaluator result
- `created_at` is the exact caller-supplied timestamp
- Phase 7K `RiskSignal` schema remains unchanged
- trigger reason is deterministic, production-native, neutral, and based on evaluator reason codes
- no buy / sell / hold / entry / exit / target price / stop loss / trading score semantics are introduced

LOW and failure semantics:

- evaluated `LOW` produces exactly one formal `LOW` `RiskSignal`
- evaluated `LOW` is not the same as evaluation failure
- evaluation failure fails closed with producer error
- failure must not become silent `LOW`, empty tuple, or failed signal artifact

Sprint 4D TechnicalRiskProductionService:

- `TechnicalRiskProductionService` consumes one caller-supplied `RiskSignalProductionInput`
- `ProductionTechnicalRiskPolicy` must be caller supplied explicitly
- `created_at` is caller supplied and is passed through to the producer timestamp contract
- service invokes `TechnicalRiskSignalProducer.produce(...)` exactly once per `run(...)`
- service requires exactly one `ProducedRiskSignal`
- zero produced signals fail closed
- multiple produced signals fail closed
- service validates observable produced-signal lineage against input and policy
- service constructs a `RiskAssessment` view using existing `RiskAssessment.from_signals(...)`
- `TechnicalRiskProductionResult` is a frozen immutable contract
- `TechnicalRiskProductionResult` stores only `produced_signal` and `risk_assessment`
- `ProducedRiskSignal` remains the production lineage source of truth
- `RiskAssessment` is an aggregation / operational view, not a complete production-lineage source
- `TechnicalRiskProductionResult` validates that `RiskAssessment.signals` contains exactly `ProducedRiskSignal.signal` once

TechnicalRiskProductionResult lineage:

- full lineage is retained through `TechnicalRiskProductionResult.produced_signal`
- traceable fields include `policy_id`, `policy_version`, and `policy_checksum`
- traceable fields include `evaluation_id` and `evaluation_checksum`
- traceable fields include `portfolio_id`, `position_id`, `as_of_date`, and `valuation_date`
- traceable fields include `source_feature_ids`, `source_checksums`, `calculation_id`, and `producer_version`
- these fields are not duplicated at the result top level

Sprint 4D responsibility boundary:

- service does not directly invoke `TechnicalRiskEvaluator`
- service does not compute derived evidence
- service does not evaluate predicates
- service does not compare thresholds
- service does not apply rule hierarchy
- service does not remap severity
- service does not search, activate, persist, or load policy
- service does not create `RiskArtifact`
- service does not modify `RiskContext` or `RiskSignal` schema
- service does not implement DB persistence, scheduler, live execution, alert delivery, dashboard, or deployment
- service does not support batch input, portfolio batch, multi-position batch, or multi-category orchestration
- higher-level callers may iterate one-input / one-result orchestration in future scoped work

Sprint 4D severity and determinism:

- `LOW`, `MEDIUM`, and `HIGH` preserve upstream Technical Risk semantics
- `LOW` is retained end-to-end: `LOW TechnicalRiskEvaluationResult` -> `LOW RiskSignal` -> `ProducedRiskSignal` -> `TechnicalRiskProductionResult` -> `RiskAssessment`
- `CRITICAL` has no legal Technical Risk v1 production result path and fails closed
- shares, quantity, position size, and exposure do not adjust Technical Risk severity
- same `RiskSignalProductionInput`, `ProductionTechnicalRiskPolicy`, `created_at`, producer version, and evaluator version produce deterministic `ProducedRiskSignal`, `RiskSignal`, `RiskAssessment`, and `TechnicalRiskProductionResult`
- deterministic replay does not imply distributed exactly-once processing, job deduplication, or concurrency locking

Sprint 4D error semantics:

- wrong policy type fails closed
- producer error fails closed and preserves the cause chain when wrapped
- zero or multiple produced signals fail closed
- invalid category fails closed
- `CRITICAL` fails closed
- assessment construction failure fails closed
- observable lineage inconsistency fails closed
- service must not produce silent `LOW`, partial success, picked-first signal, or empty result

Sprint 5A TechnicalRiskArtifactAdapter:

- `TechnicalRiskArtifactAdapter` converts one `TechnicalRiskProductionResult` into one existing `RiskArtifact`
- adapter reuses existing `RiskArtifact`, `RiskChecksumGenerator`, `RiskAssessment`, and `RiskSignal`
- `RiskArtifact`, `RiskContext`, `RiskSignal`, and `PortfolioRiskGenerationService` schemas remain unchanged
- adapter preserves Technical Risk lineage in `RiskArtifact.feature_lineage` and `RiskArtifact.calculation_metadata`
- preserved lineage includes policy id / version / checksum, evaluation id / checksum, portfolio / position, `as_of_date`, `valuation_date`, source feature ids / checksums, calculation id, and producer version
- `ProducedRiskSignal.position_id` is preserved as Technical lineage metadata
- `PortfolioPosition` still has no first-class `position_id`; Sprint 5A does not change that schema
- `LOW`, `MEDIUM`, and `HIGH` are preserved; `CRITICAL` fails closed
- adapter does not implement DB persistence, repository save/load, policy activation, scheduler, dashboard, or deployment

Sprint 5B-1 TechnicalRiskPortfolioEvaluator / Production Input Provider:

- `TechnicalRiskProductionInputProvider` resolves caller-prepared `RiskSignalProductionInput`
- provider must not query DB, yfinance, network, feature calculators, policy lookup, or latest/default activation state
- `ProductionTechnicalRiskPolicy` is explicitly constructor-injected into `TechnicalRiskPortfolioEvaluator`
- `created_at` is caller supplied and timezone-aware
- `TechnicalRiskPortfolioEvaluator` conforms to the existing `RiskEvaluator` seam:
  - `evaluate(position, context, risk_artifact_id) -> RiskEvaluationOutput`
- `PortfolioRiskGenerationService` was not modified in Sprint 5B-1
- evaluator invokes `TechnicalRiskProductionService` exactly once and `TechnicalRiskArtifactAdapter` exactly once
- evaluator does not directly call `TechnicalRiskEvaluator` or `TechnicalRiskSignalProducer`
- evaluator does not duplicate artifact metadata mapping, checksum logic, `RiskAssessment` creation, or severity logic
- position integrity is guarded by comparing incoming `risk_artifact_id` with `build_risk_artifact_id(context.calculation_id, production_input.position_id)`
- this uses `RiskSignalProductionInput.position_id`; it does not derive position identity from symbol or shares

Sprint 5B-2 PortfolioRiskGenerationService Technical Integration Validation:

- Sprint 5B-2 is test-only integration validation
- no production source was modified in Sprint 5B-2
- committed test validates the actual public `PortfolioRiskGenerationService.generate(...)` path
- validated in-memory portfolio path:

```text
PortfolioSnapshot
        |
        v
RiskEvaluationInput
        |
        v
PortfolioRiskGenerationService
        |
        v
TechnicalRiskPortfolioEvaluator
        |
        v
TechnicalRiskProductionInputProvider
        |
        v
TechnicalRiskProductionService
        |
        v
TechnicalRiskArtifactAdapter
        |
        v
RiskEvaluationOutput / RiskArtifact
        |
        v
existing MonitoringEvaluator
        |
        v
PortfolioRiskGenerationResult
```

- existing deterministic processing order remains `(position_id, symbol)`
- multiple positions and same-symbol different positions are validated
- provider mapping is `risk_artifact_id -> RiskSignalProductionInput`, not `symbol -> input`
- same-symbol positions retain distinct artifact ids, `technical_position_id`, and `technical_evaluation_id`
- deterministic replay preserves result status, output ordering, artifact ids / checksums, technical dates, and feature/checksum lineage
- full integration preserves `technical_policy_id`, `technical_policy_version`, `technical_policy_checksum`, `technical_evaluation_id`, `technical_evaluation_checksum`, `technical_position_id`, `technical_as_of_date`, `technical_valuation_date`, `technical_source_feature_ids`, `technical_source_checksums`, `technical_calculation_id`, and `technical_producer_version`
- source feature ids / checksums are validated by exact equality and pairwise fidelity
- whole-share and fractional-share positions pass through the integration path; shares do not change Technical Risk severity, policy, predicate, or evaluation semantics
- `LOW`, `MEDIUM`, and `HIGH` all pass through generation and monitoring; `LOW` is not skipped and is not a failure
- `CRITICAL` still fails closed upstream and is surfaced by the existing `RISK_EVALUATION_FAILED` service status
- risk evaluation fail-fast and monitoring fail-fast semantics are unchanged: after P1 success and P2 failure, P3 is not attempted

Sprint 6A-1 RiskArtifactCodec:

- status: COMPLETE / COMMITTED / PUSHED
- commit: `f84c79a feat: add risk artifact codec`
- public contract includes `RiskArtifactCodec`, `RISK_ARTIFACT_SCHEMA_VERSION_V1`, `RISK_ARTIFACT_CODEC_VERSION_V1`, and `RiskArtifactCodecError`
- codec is generic `RiskArtifact` persistence serialization, not Technical-specific serialization
- canonical JSON uses `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`, and `allow_nan=False`
- persisted envelope fields are `schema_version`, `codec_version`, `artifact`, and `serialization_checksum`
- `serialization_checksum` protects serialized envelope integrity and is distinct from `RiskArtifact.checksum`
- `RiskArtifact.checksum` remains the domain semantic checksum
- encode / decode chain:

```text
RiskArtifact
        |
        v
RiskArtifactCodec.encode(...)
        |
        v
canonical versioned JSON envelope
        |
        v
serialization checksum
        |
        v
RiskArtifactCodec.decode(...)
        |
        v
real RiskSignal / RiskAssessment / RiskArtifact reconstruction
        |
        v
RiskContext reconstruction
        |
        v
RiskArtifact domain checksum verification
```

- decode validates schema and codec version
- decode verifies serialization checksum before domain reconstruction is trusted
- decode reconstructs actual domain dataclasses for `RiskSignal`, `RiskAssessment`, `RiskArtifact`, and checksum-required `RiskContext`
- checksum context is reconstructed from persisted artifact metadata: `feature_lineage.feature_version`, `feature_lineage.model_version`, `calculation_metadata.portfolio_id`, `calculation_metadata.symbol`, `calculation_metadata.analysis_date`, and `calculation_metadata.calculation_id`
- missing checksum context fails closed
- Decimal metadata is preserved without float conversion
- deterministic datetime / date encoding, tuple order preservation, deterministic mapping order, and Unicode round-trip are covered
- unsupported metadata type, non-finite float, unknown schema / codec version, serialization corruption, and domain checksum corruption fail closed

Sprint 6A-2 DB-Agnostic Artifact Persistence Protocol Contracts:

- status: COMPLETE / COMMITTED / PUSHED
- commit: `1d57d8e feat: add risk artifact persistence contracts`
- formal package: `src/risk_persistence/`
- formal dependency direction:

```text
risk_persistence
        |
        v
risk
```

- `risk` must not import `risk_persistence`
- `RiskArtifactRepository` is a generic DB-agnostic Protocol for immutable `RiskArtifact` objects
- current protocol methods are exactly:

```text
save(artifact: RiskArtifact) -> RiskArtifactSaveResult
get_by_artifact_id(artifact_id: str) -> RiskArtifact | None
```

- deliberately absent APIs: query / list, latest / history, update, delete, save_many, transaction API, and resource lifecycle API
- immutable append-only semantics:
  - first save -> `INSERTED`
  - same `artifact_id` + same checksum -> `IDEMPOTENT`
  - same `artifact_id` + different checksum -> `RiskArtifactConflictError`
  - stored corruption -> `RiskArtifactCorruptionError`
  - corruption has priority over idempotent or conflict
  - missing get -> `None`
- `RiskArtifactSaveStatus` vocabulary is `INSERTED` and `IDEMPOTENT`
- `RiskArtifactSaveResult` is frozen and contains `artifact_id`, `checksum`, and `status`
- error hierarchy is `RiskArtifactPersistenceError`, `RiskArtifactConflictError`, and `RiskArtifactCorruptionError`
- no `NotFoundError`, `persisted_at`, repository row DTO, DB-specific import, codec import, or SQLite import exists in the DB-agnostic contract

Sprint 6A overall:

- status: COMPLETE / COMMITTED / PUSHED
- formal architecture:

```text
RiskArtifact
        |
        v
RiskArtifactCodec
        |
        v
DB-agnostic RiskArtifactRepository Protocol
```

- persistence representation contract and repository behavior contract are fixed
- SQLite implementation is not Sprint 6A; SQLite belongs to Sprint 6B-1

Sprint 6B-1 SQLite RiskArtifactRepository Core:

- status: COMPLETE / COMMITTED / PUSHED
- commit: `2c20c32 feat: add sqlite risk artifact repository`
- implementation: `SQLiteRiskArtifactRepository` in `src/risk_persistence/sqlite_repository.py`
- repository uses a caller-supplied SQLite DB path
- intended production path may be `data/production/risk_artifacts.db`
- as of this baseline, production risk DB is NOT CREATED and NOT ACTIVE
- DB ownership identity:
  - `application_id = 0x41494952`
  - `user_version = 1`
- wrong existing DB, unrelated existing DB, unsupported future schema version, or wrong schema shape fails closed
- core physical schema is one table, `risk_artifacts`
- current fields are exactly `artifact_id`, `artifact_checksum`, and `payload_json`
- `artifact_id` is primary key with a non-empty CHECK constraint
- `artifact_checksum` and `payload_json` are NOT NULL with non-empty CHECK constraints
- deliberately absent fields: `portfolio_id`, `position_id`, `technical_position_id`, `symbol`, `severity`, `category`, `analysis_date`, `created_at`, and `serialization_checksum`
- connection behavior:
  - operation-scoped SQLite connections
  - `PRAGMA journal_mode=WAL`
  - `PRAGMA busy_timeout` default `5000 ms`
  - `PRAGMA foreign_keys=ON`
  - no explicit `synchronous=NORMAL/OFF`
  - no thread-safe guarantee is claimed
- save flow:

```text
RiskArtifact
        |
        v
RiskArtifactCodec.encode
        |
        v
RiskArtifactCodec.decode self-validation
        |
        v
BEGIN IMMEDIATE
        |
        v
lookup artifact_id
        |
        v
insert / idempotent / conflict
```

- new artifact returns `INSERTED`
- same valid artifact returns `IDEMPOTENT`
- same id with different valid checksum raises `RiskArtifactConflictError`
- repository does not overwrite, replace, upsert, update, or delete
- existing row verification cannot trust only the DB checksum column
- before idempotent / conflict decisions, stored payload is decoded, serialization checksum is verified, domain checksum is verified, artifact id is cross-checked, and checksum column consistency is cross-checked
- stored corruption raises `RiskArtifactCorruptionError` and has priority over idempotent / conflict
- `get_by_artifact_id` returns `None` for a valid missing id; an existing row is codec-decoded, artifact id / checksum are cross-checked, and corruption fails closed
- tests use `TemporaryDirectory()` and temporary SQLite files
- tests do not create or modify `data/production/risk_artifacts.db`, `data/stocks.db`, `data/live/*`, or `data/research/*`
- generic SQLite repository can round-trip Sprint 5A style Technical `RiskArtifact` lineage, including policy, evaluation, position, as-of / valuation date, source feature ids / checksums, calculation id, and producer version
- repository has no Technical-specific branching

Sprint 6B-2A Technical Risk Artifact Query / Index Contracts:

- status: COMPLETE / COMMITTED / PUSHED
- commit: `8049063 feat: add technical risk artifact query contracts`
- formal contracts include `TechnicalRiskArtifactQueryRepository`, `TechnicalRiskArtifactIndexRecord`, and `RiskArtifactIndexCorruptionError`
- query methods are `get_latest_by_position(...)`, `list_history_by_position(...)`, and `list_latest_by_portfolio(...)`
- Technical projection requires exactly one Technical signal
- `LOW`, `MEDIUM`, and `HIGH` are valid Technical Risk v1 index severities
- `CRITICAL` is rejected for Technical Risk v1 index projection
- position identity uses `portfolio_id` plus `technical_position_id`
- latest ordering is `analysis_date DESC`, `created_at DESC`, then `artifact_id DESC`
- portfolio severity filtering applies after latest selection

Sprint 6B-2B-1 SQLite Schema v2 + Technical Index Backfill:

- status: COMPLETE / COMMITTED / PUSHED
- commit: `a93681b feat: add sqlite risk artifact schema v2`
- SQLite ownership remains `application_id = 0x41494952`
- current SQLite user schema version is `user_version = 2`
- tables are `risk_artifacts` and `technical_risk_artifact_index`
- core `risk_artifacts` table remains `artifact_id`, `artifact_checksum`, and `payload_json`
- Technical projection table is a child table with FK back to `risk_artifacts`
- required B-tree index supports latest Technical artifact lookup by portfolio / position / analysis date / created_at / artifact id
- fresh DB initializes directly to schema v2
- valid v1 DB migrates deterministically to v2
- Technical artifacts are backfilled into the Technical index
- valid non-Technical artifacts are preserved without Technical index rows
- invalid Technical artifacts fail migration closed
- rollback / retry behavior is covered
- generic core repository remains generic and does not become Technical-specific

Sprint 6B-2B-2 SQLite Technical Query Repository + Verified Read:

- status: COMPLETE / COMMITTED / PUSHED
- commit: `24ca9c7 feat: add sqlite technical risk artifact queries`
- implementation: `SQLiteTechnicalRiskArtifactQueryRepository`
- opens SQLite with `mode=ro`
- applies `PRAGMA query_only=ON`
- validates schema v2 read-only
- performs no migration side effect
- supports latest by position, history by position, and latest per position by portfolio
- portfolio latest query uses `ROW_NUMBER()`
- severity filter is applied after latest selection
- ordering is deterministic
- read path uses `LEFT JOIN risk_artifacts`
- full `RiskArtifactCodec` decode is required
- full `TechnicalRiskArtifactIndexRecord` reconstruction is required
- stored index projection must equal reconstructed artifact projection
- core corruption and index corruption fail closed
- whole query fails closed; no partial result set is returned on corruption

Sprint 6B-2B-3 Atomic Technical Artifact Persistence:

- status: COMPLETE / COMMITTED / PUSHED
- commit: `5a56172 feat: add atomic technical risk artifact persistence`
- formal public class: `SQLiteTechnicalRiskArtifactPersistenceCoordinator`
- supporting modules include generic `sqlite_storage` helpers and canonical `sqlite_technical_index` mapper
- formal atomic path:

```text
Technical RiskArtifact
        |
        v
TechnicalRiskArtifactIndexRecord validation
        |
        v
single SQLite connection
        |
        v
BEGIN IMMEDIATE
        |
        v
core RiskArtifact persistence
        |
        v
Technical index persistence
        |
        v
COMMIT
        |
        v
verified Technical query immediately available
```

- `LOW`, `MEDIUM`, and `HIGH` persist atomically to core and Technical index
- `CRITICAL`, non-Technical artifacts, and multiple Technical signals fail closed before rows are written
- new artifact returns `INSERTED`
- same artifact retry returns `IDEMPOTENT`
- generic `SQLiteRiskArtifactRepository` remains generic and does not write the Technical index
- `SQLiteTechnicalRiskArtifactQueryRepository` remains read-only
- core exists + missing index is deterministic write-path completion and returns `IDEMPOTENT`
- orphan index fails closed
- mismatched index fails closed
- core conflict fails closed
- core corruption fails closed
- index failure rolls back the full transaction
- same-symbol multi-position persistence is position-safe
- immediate write-to-query visibility is validated

Sprint 6B overall:

- status: COMPLETE / COMMITTED / PUSHED
- Sprint 6B storage-layer capability is complete
- storage capability chain:

```text
RiskArtifact
        |
        v
RiskArtifactCodec
        |
        v
SQLite core persistence
        |
        v
Technical projection / index
        |
        v
atomic core + Technical index write
        |
        v
verified Technical query
```

- this is storage-layer completion only
- this does not mean `PortfolioRiskGenerationService` automatically persists RiskArtifacts
- production risk DB is still not created or activated

Current production runtime status:

- Technical Risk v1 production core evaluation, signal generation, single-position orchestration, RiskAssessment view, RiskArtifact adapter, existing RiskEvaluator seam integration, in-memory `PortfolioRiskGenerationService` Technical integration validation, `RiskArtifactCodec`, DB-agnostic artifact persistence contracts, SQLite RiskArtifactRepository core, Technical query / index contracts, SQLite schema v3, verified SQLite Technical query, atomic Technical artifact persistence, Portfolio RunRecord contracts, SQLite Portfolio RunRecord repository, and portfolio-level atomic persistence coordination are complete through Sprint 6C
- production deployment is not complete
- still not implemented: production DB creation / activation, production bootstrap / ownership deployment, durable Technical evidence snapshot persistence, monitoring artifact payload SQLite persistence, `ProductionTechnicalRiskPolicy` persistence, policy activation governance, scheduler, live execution, live market fetch, alert delivery, dashboard SQLite integration, and end-to-end deployment

Production runtime chain:

```text
caller
+
RiskSignalProductionInput
+
ProductionTechnicalRiskPolicy
+
caller supplied created_at
        |
        v
TechnicalRiskProductionService
        |
        v
TechnicalRiskSignalProducer
        |
        v
TechnicalRiskEvaluator
        |
        v
ProducedRiskSignal / RiskSignal
        |
        v
RiskAssessment
        |
        v
TechnicalRiskProductionResult
        |
        v
TechnicalRiskArtifactAdapter
        |
        v
RiskEvaluationOutput / RiskArtifact
        |
        v
TechnicalRiskPortfolioEvaluator
        |
        v
PortfolioRiskGenerationService
        |
        v
existing MonitoringEvaluator
        |
        v
PortfolioRiskGenerationResult
```

Current persistence capability chain:

```text
Technical production pipeline
        |
        v
RiskArtifact
        |
        v
RiskArtifactCodec
        |
        v
SQLiteTechnicalRiskArtifactPersistenceCoordinator
        |
        v
risk_artifacts
        |
        v
technical_risk_artifact_index
        |
        v
SQLiteTechnicalRiskArtifactQueryRepository
```

Full in-memory portfolio-to-artifact chain plus persistence capability:

```text
PortfolioSnapshot
        |
        v
PortfolioRiskGenerationService
        |
        v
TechnicalRiskPortfolioEvaluator
        |
        v
TechnicalRiskProductionService
        |
        v
TechnicalRiskArtifactAdapter
        |
        v
RiskArtifact
        |
        v
RiskArtifactCodec
        |
        v
SQLiteTechnicalRiskArtifactPersistenceCoordinator
        |
        v
SQLiteTechnicalRiskArtifactQueryRepository
```

Current portfolio-level persistence capability:

```text
PortfolioSnapshot
        |
        v
PortfolioRiskGenerationService
        |
        v
CapturingRiskEvaluator
        |
        v
RiskArtifact(s)
        |
        v
PortfolioRiskGenerationResult
        |
        v
PortfolioRiskGenerationRunRecord
        |
        v
SQLiteTechnicalPortfolioRiskPersistenceCoordinator
        |
        v
single SQLite transaction
        |
        +--> risk_artifacts
        |
        +--> technical_risk_artifact_index
        |
        +--> portfolio_risk_generation_runs
```

Important boundary:

- SQLite portfolio persistence capability is complete through Sprint 6C
- `PortfolioRiskGenerationService` remains persistence-free; external coordination handles durable persistence
- production risk DB has not been created or activated
- scheduler, live execution, dashboard repository reads, alert delivery, policy persistence, and deployment are not complete

## Risk Monitoring Framework Status

Committed risk monitoring framework modules are under `src/risk_monitoring/` and tests under `tests/risk_monitoring/`.

Included components:

- RiskMonitoringContext
- MonitoringPolicy
- RiskMonitoringEngine
- RiskMonitoringEvent
- AlertCandidate
- RiskMonitoringArtifact
- RiskMonitoringArtifactGenerator
- RiskMonitoringChecksumGenerator
- RiskMonitoringValidator
- MonitoringState
- AlertLevel
- AlertType

Risk Monitoring data flow:

```text
RiskArtifact
    |
    v
RiskMonitoringEngine
    |
    +--> RiskMonitoringEvent
    |
    +--> AlertCandidate metadata
    |
    v
RiskMonitoringArtifact
```

Design boundary:

- Risk Monitoring Framework is metadata-only.
- Risk Monitoring Framework has no dashboard.
- Risk Monitoring Framework has no notification delivery.
- Risk Monitoring Framework does not persist monitoring records to a DB.
- Risk Monitoring Framework does not produce buy/sell/hold/entry/exit semantics.
- Risk Monitoring Framework must not directly read LiveDataStore, ResearchDataStore, sqlite database, Scanner output, or PDF output.

## Portfolio Risk Dashboard Foundation Status

Committed Portfolio Dashboard modules are under `src/portfolio_dashboard/` and tests under `tests/portfolio_dashboard/`.

Included components:

- PortfolioRiskDashboardProjection
- Portfolio Overview view model
- Position Risk view model
- Risk Event rows
- Alert Candidate rows
- Artifact Lineage rows
- artifact compatibility validation
- formatting safety
- forbidden wording safety
- read-only Streamlit view
- `Portfolio Risk（風險檢視）` tab

Portfolio Dashboard data flow:

```text
RiskMonitoringArtifact
    |
    v
Portfolio Dashboard Projection
    |
    v
Read-only Streamlit View
    |
    v
Portfolio Risk（風險檢視）
```

Design boundary:

- Dashboard is read-only.
- Dashboard is artifact-only.
- Dashboard has no DB / sqlite access.
- Dashboard does not use LiveDataStore.
- Dashboard does not use ResearchDataStore.
- Dashboard does not use scanner workflows.
- Dashboard does not use PDF export.
- Dashboard does not use yfinance.
- Dashboard does not call Risk Engine.
- Dashboard does not call Risk Monitoring Engine.
- Dashboard does not recalculate risk.
- Dashboard does not produce trading or investment recommendation semantics.

Current status and limitation:

- `Portfolio Risk（風險檢視）` tab exists.
- Formal Portfolio Artifact Input Contract, read-only artifact repository, and dashboard artifact provider wiring now exist.
- Dashboard remains read-only and artifact-only.
- Technical Risk v1 now creates in-memory `RiskArtifact` output through the portfolio generation path.
- Dashboard Technical Risk view still requires future durable persistence / repository integration before it can load production Technical Risk artifacts.
- Technical Risk runtime activation remains future explicit scope.

## Database Architecture Status

Known database layers:

- Legacy DB: existing historical / legacy local DB layer.
- Live DB: production / live cache oriented DB layer.
- Research Snapshot: reproducible research snapshot layer.
- Corrected Research Store: corrected research materialization layer.

Current architecture interpretation:

- Research and Live separation is complete in pushed history.
- Long-Term Growth Phase 7A-7L should consume reproducible artifacts and metadata boundaries.
- Risk Engine must not create a Risk DB in Phase 7K.
- This master document intentionally does not list full DB SHA values.

## Architecture Boundaries

Production Scanner and AI Research Platform remain separate.

Production Scanner:

- owns production scanning workflow
- owns existing scanner ranking, ordering, and production behavior
- must not be modified by Long-Term Growth framework phases unless explicitly scoped

PDF Export:

- uses Scan Result Snapshot -> PDF
- must not recalculate scanner output
- must not be modified by Risk Engine work

AI Research Platform:

- uses Research Snapshot
- builds Feature Artifact and Target Artifact
- builds Dataset Artifact
- supports Model Framework and OOS Evaluation
- now includes Portfolio Risk Engine framework metadata
- now includes Risk Monitoring Framework metadata
- now includes Portfolio Risk Dashboard Foundation projection / presentation metadata
- now includes Technical Risk v1 OOS research contracts
- now includes Technical Risk v1 controlled production policy promotion
- now includes Technical Risk v1 production evaluator and signal producer core contracts
- now includes Technical Risk v1 production artifact adapter and in-memory portfolio generation integration validation
- now includes RiskArtifact codec, DB-agnostic artifact persistence contracts, SQLite RiskArtifactRepository core, Technical query / index contracts, SQLite schema v2, verified SQLite Technical query, and atomic Technical artifact persistence

Risk Engine:

- performs Portfolio Risk Analysis
- emits risk assessment metadata / artifact
- does not select stocks
- does not trade
- does not produce buy/sell signals
- does not produce investment recommendations

Risk Monitoring Framework:

- consumes RiskArtifact metadata
- emits RiskMonitoringArtifact metadata
- can emit AlertCandidate metadata for review workflows
- does not select stocks
- does not trade
- does not deliver notifications
- does not produce buy/sell/hold/entry/exit semantics

Portfolio Risk Dashboard Foundation:

- consumes RiskMonitoringArtifact metadata through projection input
- renders read-only portfolio risk review, monitoring, alert candidate, and lineage information
- does not read DB or sqlite directly
- does not use LiveDataStore, ResearchDataStore, scanner, PDF export, or yfinance
- does not call Risk Engine or Risk Monitoring Engine
- does not recalculate risk
- does not produce trading or investment recommendation semantics

Technical Risk v1 Research:

- consumes historical feature / target artifacts and OOS dataset rows
- evaluates frozen candidate and threshold combinations for research methodology selection
- uses Development -> Validation -> Holdout governance
- can freeze a confirmed research policy artifact
- does not create production `RiskSignal`
- does not deploy or activate a production policy
- does not provide trading, buy / sell / hold, entry, or exit semantics

Technical Risk v1 Production Policy Promotion:

- consumes a frozen research policy artifact through `src/risk_integration/`
- emits an immutable production-native `ProductionTechnicalRiskPolicy`
- keeps `src/risk_evaluation/` independent from `risk_oos`
- does not instantiate a production evaluator or signal producer
- does not query DB, sqlite, yfinance, scanner, PDF export, dashboard, Risk Engine, or Risk Monitoring

Technical Risk v1 Production Runtime:

- Sprint 4B deterministic Technical Risk Evaluator / Evaluation Result scope is complete
- Sprint 4C TechnicalRiskSignalProducer integration is complete
- Sprint 4D TechnicalRiskProductionService / TechnicalRiskProductionResult orchestration scope is complete
- Sprint 5A TechnicalRiskArtifactAdapter scope is complete
- Sprint 5B-1 TechnicalRiskPortfolioEvaluator / Production Input Provider scope is complete
- Sprint 5B-2 actual PortfolioRiskGenerationService Technical integration validation is complete
- Sprint 6A-1 RiskArtifactCodec scope is complete
- Sprint 6A-2 DB-agnostic RiskArtifactRepository contract scope is complete
- Sprint 6B-1 SQLite RiskArtifactRepository core scope is complete
- Sprint 6B-2A Technical Risk Artifact Query / Index Contracts scope is complete
- Sprint 6B-2B-1 SQLite Schema v2 + Technical Index Backfill scope is complete
- Sprint 6B-2B-2 SQLite Technical Query Repository + Verified Read scope is complete
- Sprint 6B-2B-3 Atomic Technical Artifact Persistence scope is complete
- Sprint 6B storage-layer capability is complete
- Sprint 6C-1 Portfolio Risk Generation Run Record Contract + Codec scope is complete
- Sprint 6C-2 SQLite Schema v3 + Portfolio Run Repository scope is complete
- Sprint 6C-3 Technical Portfolio Persistence Coordinator + CapturingRiskEvaluator + Portfolio-Level Atomic Persistence scope is complete
- Sprint 6C portfolio persistence integration capability is complete
- input is caller-supplied frozen `RiskFeatureInput` through `RiskSignalProductionInput` plus `ProductionTechnicalRiskPolicy`
- evaluator output is `TechnicalRiskEvaluationResult`
- signal producer output is `ProducedRiskSignal` wrapping Phase 7K `RiskSignal`
- production service output is `TechnicalRiskProductionResult`
- artifact adapter output is existing `RiskArtifact`
- portfolio evaluator output is existing `RiskEvaluationOutput`
- production service creates a `RiskAssessment` aggregation view from the produced `RiskSignal`
- `ProducedRiskSignal` remains the lineage source of truth
- evaluator uses deterministic Decimal context, derived evidence calculation, predicate evaluation, rule hierarchy, and LOW / MEDIUM / HIGH only
- evaluator and signal producer must never emit `CRITICAL` in v1
- evaluator, signal producer, production service, artifact adapter, and portfolio evaluator must not query DB, yfinance, historical materializer, or OOS dataset
- technical severity is symbol-level technical condition and must not change because of portfolio quantity, whole shares, or fractional shares
- portfolio exposure / quantity belongs to later portfolio aggregation or context, not Technical Risk v1 severity calculation
- full in-memory `PortfolioRiskGenerationService` integration is validated
- external portfolio persistence coordination can durably save captured Technical RiskArtifacts, Technical index rows, and Portfolio RunRecords in one SQLite transaction
- policy activation, production DB activation, scheduler, dashboard integration, alert delivery, monitoring artifact payload persistence, and deployment remain planned future scope

Sprint 6C Portfolio Persistence Integration / Run-Level Persistence Record:

- status: COMPLETE / COMMITTED / PUSHED
- Sprint 6C-1 `PortfolioRiskGenerationRunRecord` contract and codec:
  - identity is `calculation_id`
  - status reuses `PortfolioRiskGenerationStatus`
  - lifecycle fields are `attempted_position_ids`, `risk_evaluated_position_ids`, `succeeded_position_ids`, and `failed_position_ids`
  - RiskArtifact refs store `position_id`, `artifact_id`, and `artifact_checksum`
  - monitoring refs store `position_id` and `artifact_id`
  - durable issues and warnings are retained
  - `created_at` is caller-injected and timezone-aware
  - `record_checksum` is canonical and semantic
  - DB-agnostic `PortfolioRiskGenerationRunRepository` exposes exact methods `save(record)` and `get_by_calculation_id(calculation_id)`
  - run repository semantics are `INSERTED`, `IDEMPOTENT`, conflict, corruption, and persistence errors
- Sprint 6C-2 SQLite schema / repository:
  - schema current version is `user_version = 3`
  - `application_id` remains `0x41494952`
  - current tables are `risk_artifacts`, `technical_risk_artifact_index`, and `portfolio_risk_generation_runs`
  - `portfolio_risk_generation_runs` columns are exactly `calculation_id`, `record_checksum`, and `payload_json`
  - `payload_json` stores the full `PortfolioRiskGenerationRunRecordCodec` envelope
  - fresh DB initializes directly to schema v3
  - v2 DB migrates atomically to v3
  - v1 DB migrates stepwise through v2 to v3
  - v2 -> v3 does not backfill historical RunRecords because existing artifacts cannot reliably reconstruct attempted, risk_evaluated, succeeded, failed, issues, warnings, monitoring refs, or caller-injected `created_at`
  - standalone `SQLitePortfolioRiskGenerationRunRepository` does not validate referenced RiskArtifact existence; referential integrity is enforced by the portfolio-level coordinator
- Sprint 6C-3 Technical portfolio persistence coordinator:
  - `CapturingRiskEvaluator` wraps an existing `RiskEvaluator`, captures successful `RiskArtifact` outputs, preserves evaluation order, keeps run-scoped state, and propagates delegate failures
  - `SQLiteTechnicalPortfolioRiskPersistenceCoordinator` is SQLite-specific and Technical-specific
  - it creates `PortfolioRiskGenerationService` through the existing injection seam with `CapturingRiskEvaluator`
  - `PortfolioRiskGenerationService` itself remains persistence-free and does not import `risk_persistence`
  - generation completes before the SQLite persistence transaction starts
  - persistence uses a single SQLite connection and one `BEGIN IMMEDIATE`
  - captured Technical RiskArtifacts, Technical index projections, and the Portfolio RunRecord commit together
  - canonical `MONITORING_FAILED` lifecycle example: P1 risk evaluation succeeds and monitoring succeeds; P2 risk evaluation succeeds but monitoring fails; P3 is not attempted because generation fails fast after P2
  - in that `MONITORING_FAILED` example, RunRecord lifecycle fields are `attempted_position_ids = (P1, P2)`, `risk_evaluated_position_ids = (P1, P2)`, `succeeded_position_ids = (P1)`, `failed_position_ids = (P2)`, `risk_artifact_refs = (P1, P2)`, `monitoring_artifact_refs = (P1)`, and `status = MONITORING_FAILED`
  - in that `MONITORING_FAILED` example, P1 RiskArtifact, P2 RiskArtifact, Technical index projections, and the `MONITORING_FAILED` RunRecord persist in the same portfolio-level SQLite transaction; P1 monitoring artifact reference is recorded, P2 monitoring artifact reference is not recorded because monitoring failed, and P3 is not evaluated or persisted
  - `risk_evaluated_position_ids` is not equivalent to `succeeded_position_ids`; a position can pass risk evaluation and still be failed because monitoring failed, so `risk_evaluated_position_ids` and `failed_position_ids` can overlap
  - any persistence failure rolls back the whole persistence transaction
  - unexpected generation exceptions propagate unchanged and do not write RiskArtifacts, Technical index rows, or RunRecords
  - same deterministic generation plus same `created_at` replays idempotently
  - same calculation_id and artifacts with different `created_at` conflicts because `created_at` is part of the RunRecord checksum
  - existing RunRecord referencing missing core RiskArtifact is durable corruption and fail closed; core exists plus missing Technical index remains deterministic index completion
  - monitoring artifact payload persistence is out of scope; only monitoring artifact ids for successful monitoring positions are recorded
  - `TechnicalRiskEvidenceSnapshot` remains out of scope
  - production risk DB remains not created and not activated

## Validation Evidence

Latest observed validation evidence after Phase 7K:

- Risk tests: `16 tests OK`
- Long-Term Growth framework regression tests: `90 tests OK`
- Full unittest: `1192 tests OK`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- Risk module isolation scan: no `LiveDataStore`, `ResearchDataStore`, scanner service, PDF export service, `sqlite3`, or `yfinance` import in `src/risk`
- DB SHA before / after checks during Phase 7K: unchanged

Latest observed validation evidence after Phase 7L:

- Risk monitoring tests: `15 tests OK`
- Full unittest: `1207 tests OK`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- Risk monitoring module isolation scan: no `LiveDataStore`, `ResearchDataStore`, scanner service, PDF export service, `sqlite3`, or `yfinance` import in `src/risk_monitoring`

Latest observed validation evidence after Phase 8A:

- Portfolio Dashboard projection tests: `16 tests OK`
- Portfolio Dashboard Streamlit view tests: `6 tests OK`
- Existing dashboard regression tests: `46 tests OK`
- Risk monitoring regression tests: `15 tests OK`
- Full unittest: `1229 tests OK`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- Portfolio Dashboard module isolation scan: no `LiveDataStore`, `ResearchDataStore`, scanner service, PDF export service, `sqlite3`, `yfinance`, Risk Engine, or Risk Monitoring Engine import in `src/portfolio_dashboard`

Existing pushed validation evidence includes:

- Database separation tests and cutover coverage in pushed history.
- Live cache isolation timing stabilization in pushed history.
- Swing Scanner PDF Export pushed at `677fc52`.

Latest observed validation evidence after Sprint 4A:

- Risk evaluation tests: `33 tests OK`
- Risk integration tests: `33 tests OK`
- Risk OOS tests: `231 tests OK`
- Risk tests: `16 tests OK`
- Features tests: `31 tests OK`
- Targets tests: `42 tests OK`
- Datasets tests: `16 tests OK`
- Portfolio generation tests: `44 tests OK`
- Full unittest: `1684 tests OK`
- official full-suite command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t .`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- source boundary scan: PASS
- production runtime does not import `risk_oos`
- `src/risk_evaluation/` does not import `risk_oos` or `risk_integration`
- Sprint 4A intentionally left `docs/PROJECT_STATUS_MASTER.md` unchanged until this synchronization

Latest observed validation evidence after Sprint 4B:

- Risk evaluation tests: `51 tests OK`
- Risk integration tests: `33 tests OK`
- Risk OOS tests: `231 tests OK`
- Risk tests: `16 tests OK`
- Features tests: `31 tests OK`
- Targets tests: `42 tests OK`
- Datasets tests: `16 tests OK`
- Portfolio generation tests: `44 tests OK`
- Full unittest: `1702 tests OK`
- official full-suite command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t .`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- source boundary scan: PASS

Latest observed validation evidence after Sprint 4C:

- Risk evaluation tests: `65 tests OK`
- Risk integration tests: `33 tests OK`
- Risk OOS tests: `231 tests OK`
- Risk tests: `16 tests OK`
- Features tests: `31 tests OK`
- Targets tests: `42 tests OK`
- Datasets tests: `16 tests OK`
- Portfolio generation tests: `44 tests OK`
- Full unittest: `1716 tests OK`
- official full-suite command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t .`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- source boundary scan: PASS
- non-blocking warnings were observed for TWSE / TPEx offline refresh, Yahoo stale cache, and Streamlit bare-mode execution

Historical validation evidence after Sprint 4D:

- Risk evaluation tests: `78 tests OK`
- Risk integration tests: `33 tests OK`
- Risk OOS tests: `231 tests OK`
- Risk tests: `16 tests OK`
- Features tests: `31 tests OK`
- Targets tests: `42 tests OK`
- Datasets tests: `16 tests OK`
- Portfolio generation tests: `44 tests OK`
- Full unittest: `1729 tests OK`
- official full-suite command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t .`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- source boundary scan: PASS
- non-blocking warnings were observed for TWSE / TPEx offline refresh, Yahoo stale cache, and Streamlit bare-mode execution

Historical validation evidence after Sprint 5B:

- Portfolio generation tests: `86 tests OK`
- Risk evaluation tests: `78 tests OK`
- Risk integration tests: `33 tests OK`
- Risk OOS tests: `231 tests OK`
- Risk tests: `16 tests OK`
- Features tests: `31 tests OK`
- Targets tests: `42 tests OK`
- Datasets tests: `16 tests OK`
- Full unittest: `1771 tests OK`
- official full-suite command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t .`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- source boundary scan: PASS
- non-blocking warnings were observed for TWSE / TPEx offline refresh, Yahoo stale cache, and Streamlit bare-mode execution

Current official validation evidence after Sprint 6C:

- Risk persistence tests: `225 tests OK`
- Risk tests: `40 tests OK`
- Portfolio generation tests: `86 tests OK`
- Risk evaluation tests: `78 tests OK`
- Risk integration tests: `33 tests OK`
- Risk OOS tests: `231 tests OK`
- Features tests: `31 tests OK`
- Targets tests: `42 tests OK`
- Datasets tests: `16 tests OK`
- Portfolio artifacts tests: `35 tests OK`
- Full unittest: `2020 tests OK`
- official full-suite command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t .`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- source boundary scan: PASS
- production DB safety: PASS
- non-blocking warnings were observed for TWSE / TPEx offline refresh, Yahoo stale cache, and Streamlit bare-mode execution

Known warnings during full unittest:

- existing offline warnings for external data source refresh
- existing Yahoo stale cache warnings
- existing Streamlit bare-mode warnings

These warnings did not fail the test suite.

## Current Working State

Current state:

- Database Separation: complete and pushed
- PDF Export: complete and pushed
- Long-Term Growth: Phase 7L complete, committed, and pushed
- Portfolio Risk Dashboard Foundation: Phase 8A complete, committed, and pushed
- Portfolio Artifact Input / Repository / Dashboard Artifact Provider framework: complete, committed, and pushed
- Portfolio State / Portfolio Generation Service Framework: complete, committed, and pushed
- Risk Evaluation Production Contract: complete, committed, and pushed
- Technical Risk v1 OOS prerequisites, rule candidate evaluation governance, research policy freeze, production policy promotion, deterministic evaluator, signal producer integration, single-position production orchestration, Technical Risk artifact adapter, Technical Risk portfolio evaluator, full in-memory `PortfolioRiskGenerationService` integration validation, RiskArtifact codec, DB-agnostic artifact persistence contracts, SQLite RiskArtifactRepository core, Technical query / index contracts, SQLite schema v3, verified SQLite Technical query, atomic Technical artifact persistence, Portfolio RunRecord contracts, SQLite Portfolio RunRecord repository, and portfolio-level atomic persistence coordination: complete, committed, and pushed through Sprint 6C
- Sprint 6C Portfolio Persistence Integration / Run-Level Persistence Record implementation chain: complete, committed, and pushed
- Next planned Technical Risk phase after documentation review / commit / validation / push: productionization specification review, unless a narrower sprint is explicitly scoped

Current committed Long-Term Growth directories include:

- `src/features/`
- `src/targets/`
- `src/datasets/`
- `src/model_framework/`
- `src/evaluation/`
- `src/risk/`
- `src/risk_monitoring/`
- `src/portfolio_dashboard/`
- `src/portfolio_state/`
- `src/portfolio_generation/`
- `src/portfolio_artifacts/`
- `src/risk_evaluation/`
- `src/risk_oos/`
- `src/risk_integration/`
- corresponding tests under `tests/`
- Phase 7 architecture / framework docs under `docs/`

Important: future sessions should still inspect the live working tree before editing, but Phase 7A-7L, Phase 8A-8F, and Technical Risk v1 through Sprint 6C are now committed and pushed.

## Future Roadmap

Completed:

- Phase 8A Portfolio Risk Dashboard Foundation
- Portfolio Artifact Input Contract
- Risk Monitoring Artifact Serialization Contract
- Read-only Portfolio Artifact Repository
- Portfolio Dashboard Artifact Provider Wiring
- Portfolio State Generation Contracts
- Portfolio Generation Contract Builders
- Portfolio Risk Generation Service Framework
- Risk Evaluation Production Contract
- Technical as-of close input contract
- MAE target generators and target window lineage
- Historical Technical Risk Feature Materialization
- Aligned Technical Risk OOS Dataset
- Technical Risk rule candidate / threshold / derived evidence contracts
- Technical Risk candidate evaluator
- Development exploration contracts
- Development shortlist and validation selection contracts
- Holdout confirmation contracts
- Research policy freeze artifact
- Production Technical Risk Policy Promotion
- Deterministic Technical Risk Evaluator / Evaluation Result
- TechnicalRiskSignalProducer integration and RiskSignal projection
- TechnicalRiskProductionService orchestration and TechnicalRiskProductionResult
- TechnicalRiskArtifactAdapter and RiskArtifact lineage adaptation
- TechnicalRiskPortfolioEvaluator and caller-prepared production input provider seam
- PortfolioRiskGenerationService Technical integration validation
- RiskArtifactCodec
- DB-agnostic RiskArtifactRepository Protocol
- SQLite RiskArtifactRepository core
- Technical Risk Artifact Query / Index Contracts
- SQLite schema v2 and Technical index backfill
- SQLite Technical query repository and verified read path
- Atomic Technical artifact persistence
- Portfolio Risk Generation RunRecord contract and canonical codec
- SQLite schema v3 and Portfolio RunRecord repository
- Technical portfolio persistence coordinator, CapturingRiskEvaluator, and portfolio-level atomic persistence

Next planning candidate:

- PROJECT_STATUS_MASTER document review, documentation commit, release validation, and push

Future:

- Productionization specification review, including production DB bootstrap / activation, runtime invocation, scheduler boundary, dashboard read-side integration, alert delivery boundary, and safe deployment boundary
- Sprint 6D Policy Persistence / Activation Governance
- Technical Risk v1 scheduler / live execution, only after explicit scope
- Technical Risk v1 dashboard / alert integration, only after durable persistence and explicit scope
- Phase 8 Alert Lifecycle Framework
- AI Model Improvement Foundation

These future items require explicit scope before implementation.

## Production Persistence Roadmap

Persistence Contract Specification Review has been implemented through Sprint 6A and Sprint 6B:

- Sprint 6A-1 `RiskArtifactCodec`: COMPLETE / COMMITTED / PUSHED
- Sprint 6A-2 DB-agnostic `RiskArtifactRepository` Protocol: COMPLETE / COMMITTED / PUSHED
- Sprint 6B-1 `SQLiteRiskArtifactRepository` Core: COMPLETE / COMMITTED / PUSHED
- Sprint 6B-2A Technical Risk Artifact Query / Index Contracts: COMPLETE / COMMITTED / PUSHED
- Sprint 6B-2B-1 SQLite Schema v2 + Technical Index Backfill: COMPLETE / COMMITTED / PUSHED
- Sprint 6B-2B-2 SQLite Technical Query Repository + Verified Read: COMPLETE / COMMITTED / PUSHED
- Sprint 6B-2B-3 Atomic Technical Artifact Persistence: COMPLETE / COMMITTED / PUSHED
- production DB activation and portfolio workflow persistence integration remain future scope

Recommended durable source of truth:

- primary durable production record should be `RiskArtifact`
- `RiskArtifact` can support basic Dashboard summary fields: portfolio / position, symbol, severity, trigger reason, `as_of_date`, `valuation_date`, policy lineage, evaluation lineage, source lineage, calculation lineage, and checksum
- `RiskArtifact` alone is not enough for full Technical evidence detail
- future persistence should consider `RiskArtifact` plus a minimal `TechnicalRiskEvidenceSnapshot`
- Technical evidence snapshot should preserve feature values used, derived evidence, predicate states, matched rule, severity, reason codes, and evaluation checksum
- `ProducedRiskSignal` should not be separately persisted unless a future requirement proves it is not just duplication
- full `ProductionTechnicalRiskPolicy` persistence is a separate future boundary, not part of the artifact repository sprint

Planned persistence DB boundary:

- SQLite is acceptable for v1 production persistence
- planned production risk DB may be `data/production/risk_artifacts.db`
- that database has not been created or activated
- Technical Risk artifact persistence must not use `data/stocks.db`
- Technical Risk artifact persistence must not use `LiveDataStore`
- Technical Risk artifact persistence must not use `ResearchDataStore`

Implemented artifact and portfolio run persistence semantics through Sprint 6C:

- append-only / immutable artifact persistence
- first save returns `INSERTED`
- same `artifact_id` + same `checksum` returns `IDEMPOTENT`
- same `artifact_id` + different `checksum` fails closed as `RiskArtifactConflictError`
- stored corruption fails closed as `RiskArtifactCorruptionError`
- corruption takes priority over idempotent / conflict
- missing `get_by_artifact_id` returns `None`
- no silent overwrite
- repository read verifies codec serialization checksum, domain checksum, artifact id, and checksum-column consistency
- Technical Risk index projection requires exactly one Technical signal
- `LOW`, `MEDIUM`, and `HIGH` Technical artifacts persist atomically
- `CRITICAL`, non-Technical artifacts, and multiple Technical signals fail closed on the Technical persistence path
- Technical query repository verifies core artifact decode and Technical index projection equality
- atomic Technical persistence writes core artifact and Technical index in one transaction
- write-path missing-index completion is deterministic and idempotent
- orphan index, mismatched index, core conflict, core corruption, and index failure fail closed
- Portfolio RunRecord contract stores attempted, risk_evaluated, succeeded, failed, RiskArtifact refs, monitoring refs, issues, warnings, and caller-injected timezone-aware `created_at`
- RunRecord codec preserves a canonical versioned JSON envelope and semantic `record_checksum`
- Portfolio RunRecord repository saves by `calculation_id` and supports `save(record)` plus `get_by_calculation_id(calculation_id)`
- same `calculation_id` + same `record_checksum` returns `IDEMPOTENT`
- same `calculation_id` + different valid RunRecord fails closed as `PortfolioRiskGenerationRunConflictError`
- stored invalid RunRecord fails closed as `PortfolioRiskGenerationRunCorruptionError`
- Technical portfolio persistence coordinator persists captured RiskArtifacts, Technical index projections, and Portfolio RunRecord in one transaction
- risk evaluation failure can durably persist prior successful RiskArtifacts plus a failure RunRecord
- monitoring failure can durably persist RiskArtifacts whose risk evaluation already succeeded, even if monitoring failed
- in the canonical `MONITORING_FAILED` lifecycle, P1 complete and P2 risk-success / monitoring-failure gives attempted = P1, P2; risk_evaluated = P1, P2; succeeded = P1; failed = P2; RiskArtifact refs = P1, P2; monitoring refs = P1 only; P3 is not attempted or persisted
- `risk_evaluated` and `succeeded` are intentionally distinct because `risk_evaluated` and failed positions can overlap when monitoring fails after risk evaluation succeeds
- validation failure persists a RunRecord only
- unexpected generation exception writes no RiskArtifacts, Technical index rows, or RunRecord
- same deterministic generation and same `created_at` replays idempotently
- same calculation_id and artifacts with different `created_at` conflicts because `created_at` participates in the RunRecord checksum
- existing RunRecord referencing missing core RiskArtifact is durable corruption and is not auto-repaired

Current SQLite storage scope:

- core table: `risk_artifacts`
- Technical projection table: `technical_risk_artifact_index`
- Portfolio run table: `portfolio_risk_generation_runs`
- current schema: `user_version = 3`
- `portfolio_risk_generation_runs` columns are `calculation_id`, `record_checksum`, and `payload_json`
- verified read APIs exist through `SQLiteTechnicalRiskArtifactQueryRepository`
- verified RunRecord reads exist through `SQLitePortfolioRiskGenerationRunRepository`
- latest by position, history by position, and latest per position by portfolio are available for Technical artifacts
- no automatic production DB activation or scheduler wiring
- `PortfolioRiskGenerationService` remains persistence-free
- no dashboard read-side query contract

Future Dashboard minimum query targets:

1. latest Technical Risk per held position
2. all HIGH Technical Risk positions
3. Technical Risk history by position
4. artifact detail by artifact id

Future Dashboard access should be read-only repository access. Dashboard / alert integration is not implemented yet.

## Known Technical Debt / Governance Gaps

Current non-blocking gaps:

- Candidate / threshold methodology contracts still physically live in `risk_oos`; Sprint 4A avoids production runtime importing research code through controlled promotion, but a future neutral shared methodology package may be considered.
- Holdout true single-use has no persistent execution ledger; current protection is governance and immutable artifact lineage, not a system-enforced historical run count.
- Holdout governance does not yet persist alternate holdout inspection, same-period reuse, or post-holdout retuning controls.
- `severity_mapping_version` and `reason_mapping_version` currently only allow v1; if a valid v2 is introduced later, add checksum-delta tests for legal mapping-version changes.
- `ProducedRiskSignal.source_feature_ids` and `ProducedRiskSignal.source_checksums` remain parallel tuple representations; full feature-pair fidelity is protected primarily by `TechnicalRiskEvaluationResult.feature_references` plus `evaluation_checksum`.
- `ProducedRiskSignal` Sprint 4C lineage fields are optional for legacy compatibility; `TechnicalRiskSignalProducer` fills them completely.
- `RiskAssessment` is an aggregation / operational view and does not preserve complete `ProducedRiskSignal` lineage.
- `RiskContext` still does not contain `position_id` or `valuation_date`; Sprint 5A / 5B did not change Phase 7K core schemas.
- `PortfolioPosition` still has no first-class `position_id`; Technical Risk position lineage is preserved through `RiskSignalProductionInput.position_id` and `ProducedRiskSignal.position_id` metadata.
- Production policy has no activation registry, persistence, or deployment workflow yet.
- Technical Risk v1 has no Dashboard read-side repository contract yet.
- Technical Risk v1 has no durable Technical evidence snapshot yet.
- Technical Risk v1 has no `ProductionTechnicalRiskPolicy` persistence yet.
- Technical Risk v1 production risk DB has not been created or activated yet.
- Technical Risk v1 has no scheduler or live execution yet.
- Technical Risk v1 portfolio persistence capability exists through an external coordinator, but it is not production-activated or scheduled.
- Technical Risk v1 has no monitoring artifact payload SQLite persistence yet.
- Technical Risk v1 output is not integrated into dashboard or alert delivery yet.

These gaps are not current blockers for the Sprint 6C synchronized state, but they must not be misrepresented as completed production deployment capability.

## Important Design Rules

Hard rules to preserve:

- Do not modify Production V1 without explicit scope.
- Do not modify V1.1 without explicit scope.
- Do not modify scanner ranking, ordering, or technical formulas without explicit scope.
- Do not let Risk Engine directly read raw Live DB.
- Do not let Risk Engine query sqlite database directly.
- Do not let PDF Export recalculate scanner output.
- Keep research reproducibility.
- Keep version lineage.
- Keep checksum validation.
- Keep Research / Live separation.
- Keep artifact boundaries explicit.
- Do not create trading systems, automatic orders, buy/sell signals, or investment advice in framework-only phases.
- Technical Risk v1 is downside-risk monitoring, not stock selection.
- Technical Risk v1 production policy must not use Volume Ratio until v1.1 scope explicitly adds it.
- Technical Risk v1 must not emit `CRITICAL` in v1.
- Technical Risk v1 production runtime must not import `risk_oos`.
- Research policy freeze artifacts are research artifacts, not production policies.
- Controlled promotion may create a production policy contract, but it must not imply activation or deployment.
- `TechnicalRiskEvaluator` and `TechnicalRiskSignalProducer` exist, but they must not imply activation, scheduling, DB persistence, dashboard integration, or deployment.
- `TechnicalRiskProductionService`, `TechnicalRiskArtifactAdapter`, `TechnicalRiskPortfolioEvaluator`, and the external Sprint 6C portfolio persistence coordinator exist, and in-memory `PortfolioRiskGenerationService` integration plus portfolio persistence capability are validated; this must not imply production DB activation, policy activation, scheduling, dashboard integration, alert delivery, or deployment.
- Technical Risk v1 `LOW` is a real evaluated low-severity signal, not an evaluation failure.
- Technical Risk v1 evaluation / producer failures must fail closed and must not become silent `LOW`, empty tuples, or failed signal artifacts.
- Technical Risk v1 service failures must fail closed and must not become silent `LOW`, partial success, picked-first signal, or empty result.
- Do not convert MAE targets into live prediction, recommendation, or trading logic.
- Do not create BUY, SELL, HOLD, ENTRY, EXIT, TARGET PRICE, STOP LOSS, or TRADING SCORE semantics from Technical Risk v1.
- Technical Risk v1 may express technical downside-risk evidence and severity only.

## Resume Checklist For Future Sessions

Before continuing from this state:

1. Run `git status --short`.
2. Confirm HEAD is still `2486fbb3df0569afb1ba274bbf9d51e73e9dd2c0` or inspect any newer commits.
3. Confirm whether Technical Risk v1 through Sprint 6C files are still committed and whether new worktree changes exist.
4. Inspect the specific next-phase request before editing.
5. Preserve Scanner, PDF Export, Database Separation, Production V1, V1.1, OOS research, and production policy promotion boundaries unless explicitly authorized.
6. Re-run targeted tests for the touched framework.
7. Re-run full unittest, `compileall`, and `git diff --check` before reporting completion.
8. Complete PROJECT_STATUS_MASTER review / commit / release validation / push before starting the next implementation sprint.
9. If starting the next Technical Risk v1 productionization work, first run a specification review and preserve the distinction between completed portfolio persistence capability and incomplete production DB activation, policy activation, scheduler, dashboard, alert delivery, deployment, or threshold research unless explicitly scoped.
