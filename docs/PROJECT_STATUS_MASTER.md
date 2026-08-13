# AI Investment Research Project Status Master

Last updated: 2026-08-13, after Long-Term Growth Phase 7K.

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
- existing validation evidence from the Long-Term Growth Phase 7A-7K working state

No network fetch, DB migration, DB schema inspection, or production data query was used to create this document.

## Current Git Status

- Branch: `main`
- HEAD: `677fc52c6de0373f47fe26cfdbb24257742bf25d`
- Latest pushed commit: `677fc52 feat: add swing scanner PDF export`
- Remote tracking: `main` is aligned with `origin/main` at `677fc52`
- Working tree: not clean
- Current Phase 7A-7K Long-Term Growth files are present as untracked working-tree files and have not been committed or pushed.

Important: do not assume Long-Term Growth Phase 7A-7K is already in Git history. The pushed project state currently ends at Swing Scanner PDF Export.

## Recent Pushed History

Latest pushed milestones visible in `git log --oneline --decorate`:

- `677fc52 feat: add swing scanner PDF export`
- `432db3a test: make live cache isolation tests time deterministic`
- `752fd23 docs: document database architecture separation`
- `54132a9 docs: add research snapshot release manifests`
- `61aa5ac test: add database separation and cutover coverage`
- `ff823a6 feat: separate research and live data stores`
- `8a751e8 chore: protect runtime database artifacts`

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
- Database separation is not part of the current uncommitted Long-Term Growth work.

### PDF Export: Swing Scanner PDF Export

Status: complete and pushed.

Architecture boundary:

- PDF Export uses Scan Result Snapshot -> PDF.
- PDF Export must not recalculate scanner results.
- Long-Term Growth and Risk Engine work must not modify PDF Export.

## Long-Term Growth Status

The following phases are present in the current working tree and validation evidence. They are not committed or pushed at the time of this document.

| Phase | Name | Status |
|---|---|---|
| 7A | AI Architecture Design | PASS |
| 7B | Feature Engineering Framework | PASS |
| 7C | Feature Calculation Engine | PASS |
| 7D | Feature Pipeline | PASS |
| 7E | Training Dataset Framework | PASS |
| 7F | Target Generation Framework | PASS |
| 7G | Target Generator | PASS |
| 7H | Training Dataset Builder | PASS |
| 7I | Baseline Model Framework | PASS |
| 7J | OOS Evaluation Framework | PASS |
| 7K | Portfolio Risk Engine Framework | PASS |
| 7L | Risk Monitoring Integration | Pending |

## Current AI Platform Architecture

Current intended architecture after Phase 7K:

```text
Research Snapshot
    |
    v
Feature Pipeline
    |
    v
Feature Artifact

Target Pipeline
    |
    v
Target Artifact

Feature Artifact + Target Artifact
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
```

The platform is research-oriented and artifact-oriented. It is not a trading system.

## Feature Platform Status

Current uncommitted feature framework modules are under `src/features/` and tests under `tests/features/`.

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

Current uncommitted target framework modules are under `src/targets/` and tests under `tests/targets/`.

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

Current uncommitted dataset framework modules are under `src/datasets/` and tests under `tests/datasets/`.

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

Current uncommitted model framework modules are under `src/model_framework/` and tests under `tests/model_framework/`.

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

Current uncommitted OOS evaluation modules are under `src/evaluation/` and tests under `tests/evaluation/`.

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

Current uncommitted risk framework modules are under `src/risk/` and tests under `tests/risk/`.

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

## Database Architecture Status

Known database layers:

- Legacy DB: existing historical / legacy local DB layer.
- Live DB: production / live cache oriented DB layer.
- Research Snapshot: reproducible research snapshot layer.
- Corrected Research Store: corrected research materialization layer.

Current architecture interpretation:

- Research and Live separation is complete in pushed history.
- Long-Term Growth Phase 7A-7K should consume reproducible artifacts and metadata boundaries.
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

Risk Engine:

- performs Portfolio Risk Analysis
- emits risk assessment metadata / artifact
- does not select stocks
- does not trade
- does not produce buy/sell signals
- does not produce investment recommendations

## Validation Evidence

Latest observed validation evidence after Phase 7K:

- Risk tests: `16 tests OK`
- Long-Term Growth framework regression tests: `90 tests OK`
- Full unittest: `1192 tests OK`
- `compileall app.py src tests`: PASS
- `git diff --check`: PASS
- Risk module isolation scan: no `LiveDataStore`, `ResearchDataStore`, scanner service, PDF export service, `sqlite3`, or `yfinance` import in `src/risk`
- DB SHA before / after checks during Phase 7K: unchanged

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
- Long-Term Growth: Phase 7K complete in working tree
- Next planned phase: Phase 7L Risk Monitoring Integration

Current uncommitted Long-Term Growth directories include:

- `src/features/`
- `src/targets/`
- `src/datasets/`
- `src/model_framework/`
- `src/evaluation/`
- `src/risk/`
- corresponding tests under `tests/`
- Phase 7 architecture / framework docs under `docs/`

Important: because these files are untracked, a future session must inspect the live working tree before editing or committing. Do not infer that these files are already part of Git history.

## Future Roadmap

Next:

- Phase 7L: Risk Monitoring Integration

Future directions, not yet implemented in this status document:

- AI Model Improvement
- Portfolio Dashboard
- Alert Framework

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
2. Confirm HEAD is still `677fc52c6de0373f47fe26cfdbb24257742bf25d` or inspect any newer commits.
3. Confirm whether Phase 7A-7K files are still untracked, staged, committed, or changed.
4. Inspect the specific next-phase request before editing.
5. Preserve Scanner, PDF Export, Database Separation, Production V1, and V1.1 boundaries unless explicitly authorized.
6. Re-run targeted tests for the touched framework.
7. Re-run full unittest, `compileall`, and `git diff --check` before reporting completion.
