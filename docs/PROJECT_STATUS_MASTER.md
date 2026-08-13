# AI Investment Research Project Status Master

Last updated: 2026-08-13, after Phase 8A Portfolio Risk Dashboard Foundation.

## Project Purpose

Project: AI Investment Research

Purpose: 建立可重現、可驗證的 AI 投資研究平台。此文件供未來 ChatGPT / Codex session 快速恢復專案上下文，並避免把已推送狀態、目前工作樹、研究架構與 production scanner 邊界混在一起。

## Information Sources

This status document is based on:

- `git status --short`
- `git rev-parse HEAD`
- `git branch --show-current`
- `git branch -vv`
- `git log --oneline --decorate -n 12`
- repository structure under `docs/`, `src/`, and `tests/`
- existing validation evidence from the Long-Term Growth Phase 7A-7L pushed state
- Phase 8A Portfolio Risk Dashboard Foundation release validation

No network fetch, DB migration, DB schema inspection, or production data query was used to create this document.

## Current Git Status

- Branch: `main`
- Implementation baseline: `0d71d85 feat: add read-only portfolio risk dashboard foundation`
- Documentation status: Phase 8A documentation synchronized after implementation baseline.
- Documentation update status: currently local until pushed.
- Current Phase 7A-7L Long-Term Growth files are committed and pushed.
- Phase 8A Portfolio Risk Dashboard Foundation implementation is committed and pushed at `0d71d85`.

Repository state verification:

- Do not rely on this document for exact current repository HEAD.
- Exact current HEAD must be verified from live Git state with `git rev-parse HEAD`.
- Remote alignment must be verified from live Git state with `git status --short --branch`.
- Recent repository history must be verified from live Git state with `git log --oneline --decorate`.

Important: Long-Term Growth Phase 7A-7L is part of Git history through `f834e40`.
Phase 8A Portfolio Risk Dashboard Foundation is part of Git history at `0d71d85`.

## Recent Pushed History

Latest pushed milestones visible in `git log --oneline --decorate`:

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

## Current AI Platform Architecture

Current intended architecture after Phase 8A:

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

Current limitation:

- `Portfolio Risk（風險檢視）` tab exists.
- There is no formal Artifact Input Contract yet.
- When no `PortfolioRiskDashboardProjection` input is supplied, the UI displays an empty state.
- This empty state is the intended Phase 8A foundation scope, not a bug.

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

Known warnings during full unittest:

- existing offline warnings for external data source refresh
- existing Streamlit bare-mode warnings

These warnings did not fail the test suite.

## Current Working State

Current state:

- Database Separation: complete and pushed
- PDF Export: complete and pushed
- Long-Term Growth: Phase 7L complete, committed, and pushed
- Portfolio Risk Dashboard Foundation: Phase 8A complete, committed, and pushed
- Next planned phase: not assigned in this document

Current committed Long-Term Growth directories include:

- `src/features/`
- `src/targets/`
- `src/datasets/`
- `src/model_framework/`
- `src/evaluation/`
- `src/risk/`
- `src/risk_monitoring/`
- `src/portfolio_dashboard/`
- corresponding tests under `tests/`
- Phase 7 architecture / framework docs under `docs/`

Important: future sessions should still inspect the live working tree before editing, but Phase 7A-7L and Phase 8A are now committed and pushed.

## Future Roadmap

Completed:

- Phase 8A Portfolio Risk Dashboard Foundation

Next planning candidate:

- Portfolio Artifact Input Contract

Future:

- Phase 8B Alert Lifecycle Framework
- Phase 8C AI Model Improvement Foundation

These future items require explicit scope before implementation.

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

## Resume Checklist For Future Sessions

Before continuing from this state:

1. Run `git status --short`.
2. Confirm HEAD is still `f834e400eb5624455596510d0a79aca10f2fd7bd` or inspect any newer commits.
3. Confirm whether Phase 7A-7L files are still committed and whether new worktree changes exist.
4. Inspect the specific next-phase request before editing.
5. Preserve Scanner, PDF Export, Database Separation, Production V1, and V1.1 boundaries unless explicitly authorized.
6. Re-run targeted tests for the touched framework.
7. Re-run full unittest, `compileall`, and `git diff --check` before reporting completion.
