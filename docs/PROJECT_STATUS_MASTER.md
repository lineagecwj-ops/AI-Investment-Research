# AI Investment Research Project Status Master

Last updated: 2026-08-14, after Technical Risk v1 Sprint 4C TechnicalRiskSignalProducer Integration.

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

No network fetch, DB migration, DB schema inspection, or production data query was used to create this document.

## Current Git Status

- Branch: `main`
- Implementation baseline: `ed37aea feat: add technical risk signal producer`
- Current full HEAD: `ed37aeaaf326a73f31c36850313a2d5c11d4ff58`
- Remote baseline at synchronization time: `origin/main` points to `ed37aeaaf326a73f31c36850313a2d5c11d4ff58`
- Documentation status: this file is being synchronized after Sprint 4B and Sprint 4C release pushes.
- Documentation update status: currently local until committed and pushed.
- Current Phase 7A-7L Long-Term Growth files are committed and pushed.
- Phase 8A Portfolio Risk Dashboard Foundation implementation is committed and pushed at `0d71d85`.
- Technical Risk v1 OOS research contracts through Research Policy Freeze are committed and pushed through `f568b74`.
- Technical Risk v1 Production Technical Risk Policy Promotion is committed and pushed at `3fa2682`.
- Technical Risk v1 Deterministic Technical Risk Evaluator is committed and pushed at `3deb445`.
- Technical Risk v1 TechnicalRiskSignalProducer Integration is committed and pushed at `ed37aea`.

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

## Current AI Platform Architecture

Current intended architecture after Sprint 4C:

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
TechnicalRiskEvaluator
    |
    v
TechnicalRiskEvaluationResult
    |
    v
TechnicalRiskSignalProducer
    |
    v
ProducedRiskSignal
    |
    v
RiskSignal
```

The platform is research-oriented and artifact-oriented. It is not a trading system.

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

Current production runtime status:

- Technical Risk v1 production core evaluation plus signal generation pipeline is complete through Sprint 4C
- production deployment is not complete
- still not implemented: policy activation, policy persistence, runtime orchestration, scheduler, live execution, DB persistence for Technical Risk outputs, alert delivery, dashboard integration, and end-to-end deployment

Production runtime chain:

```text
RiskSignalProductionInput
+
ProductionTechnicalRiskPolicy
        |
        v
TechnicalRiskEvaluator
        |
        v
TechnicalRiskEvaluationResult
        |
        v
TechnicalRiskSignalProducer
        |
        v
ProducedRiskSignal
        |
        v
RiskSignal
```

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
- Technical Risk v1 production policy promotion does not yet create dashboard-visible technical risk signals.
- Technical Risk evaluator / signal producer / runtime activation are future explicit scope.

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
- input is caller-supplied frozen `RiskFeatureInput` through `RiskSignalProductionInput` plus `ProductionTechnicalRiskPolicy`
- evaluator output is `TechnicalRiskEvaluationResult`
- signal producer output is `ProducedRiskSignal` wrapping Phase 7K `RiskSignal`
- evaluator uses deterministic Decimal context, derived evidence calculation, predicate evaluation, rule hierarchy, and LOW / MEDIUM / HIGH only
- evaluator and signal producer must never emit `CRITICAL` in v1
- evaluator and signal producer must not query DB, yfinance, historical materializer, or OOS dataset
- technical severity is symbol-level technical condition and must not change because of portfolio quantity, whole shares, or fractional shares
- portfolio exposure / quantity belongs to later portfolio aggregation or context, not Technical Risk v1 severity calculation
- Sprint 4D is planned for end-to-end production integration / orchestration specification

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

Current official validation evidence after Sprint 4C:

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
- Technical Risk v1 OOS prerequisites, rule candidate evaluation governance, research policy freeze, production policy promotion, deterministic evaluator, and signal producer integration: complete, committed, and pushed through Sprint 4C
- Next planned Technical Risk phase: Sprint 4D End-to-End Production Integration / Orchestration Specification Review, only after this document synchronization is reviewed

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

Important: future sessions should still inspect the live working tree before editing, but Phase 7A-7L, Phase 8A-8F, and Technical Risk v1 through Sprint 4C are now committed and pushed.

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

Next planning candidate:

- Technical Risk v1 Sprint 4D: End-to-End Production Integration / Orchestration Specification Review

Future:

- Technical Risk v1 production activation / registry / runtime wiring, only after explicit approval
- Technical Risk v1 scheduler, DB persistence, alert delivery, and dashboard integration, only after explicit scope
- Phase 8 Alert Lifecycle Framework
- AI Model Improvement Foundation

These future items require explicit scope before implementation.

## Known Technical Debt / Governance Gaps

Current non-blocking gaps:

- Candidate / threshold methodology contracts still physically live in `risk_oos`; Sprint 4A avoids production runtime importing research code through controlled promotion, but a future neutral shared methodology package may be considered.
- Holdout true single-use has no persistent execution ledger; current protection is governance and immutable artifact lineage, not a system-enforced historical run count.
- Holdout governance does not yet persist alternate holdout inspection, same-period reuse, or post-holdout retuning controls.
- `severity_mapping_version` and `reason_mapping_version` currently only allow v1; if a valid v2 is introduced later, add checksum-delta tests for legal mapping-version changes.
- `ProducedRiskSignal.source_feature_ids` and `ProducedRiskSignal.source_checksums` remain parallel tuple representations; full feature-pair fidelity is protected primarily by `TechnicalRiskEvaluationResult.feature_references` plus `evaluation_checksum`.
- `ProducedRiskSignal` Sprint 4C lineage fields are optional for legacy compatibility; `TechnicalRiskSignalProducer` fills them completely.
- Production policy has no activation registry, persistence, or deployment workflow yet.
- Technical Risk v1 has no runtime orchestration yet.
- Technical Risk v1 has no scheduler or live execution yet.
- Technical Risk v1 output is not persisted to DB yet.
- Technical Risk v1 output is not integrated into dashboard or alert delivery yet.

These gaps are not current blockers for the Sprint 4C synchronized state, but they must not be misrepresented as completed production deployment capability.

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
- Technical Risk v1 `LOW` is a real evaluated low-severity signal, not an evaluation failure.
- Technical Risk v1 evaluation / producer failures must fail closed and must not become silent `LOW`, empty tuples, or failed signal artifacts.
- Do not convert MAE targets into live prediction, recommendation, or trading logic.
- Do not create BUY, SELL, HOLD, ENTRY, EXIT, TARGET PRICE, STOP LOSS, or TRADING SCORE semantics from Technical Risk v1.
- Technical Risk v1 may express technical downside-risk evidence and severity only.

## Resume Checklist For Future Sessions

Before continuing from this state:

1. Run `git status --short`.
2. Confirm HEAD is still `ed37aeaaf326a73f31c36850313a2d5c11d4ff58` or inspect any newer commits.
3. Confirm whether Technical Risk v1 Sprint 4A, Sprint 4B, and Sprint 4C files are still committed and whether new worktree changes exist.
4. Inspect the specific next-phase request before editing.
5. Preserve Scanner, PDF Export, Database Separation, Production V1, V1.1, OOS research, and production policy promotion boundaries unless explicitly authorized.
6. Re-run targeted tests for the touched framework.
7. Re-run full unittest, `compileall`, and `git diff --check` before reporting completion.
8. If starting Technical Risk v1 Sprint 4D, verify it is end-to-end production integration / orchestration specification first, not dashboard, scheduler, DB persistence, deployment, or threshold research unless explicitly scoped.
