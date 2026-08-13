# Long-Term Growth AI Research Platform Architecture Phase 7A

Phase 7A is architecture design only.

This document does not implement an AI model, Feature Store, Target Store,
Training DB, training pipeline, market-data fetch, scanner change, database
schema change, migration, PDF Export change, or runtime Database Separation
change.

## 1. Scope

Allowed in this phase:

- architecture documentation;
- design review of future Long-Term Growth AI boundaries;
- read-only repository inspection.

Out of scope:

- production code changes;
- scanner logic changes;
- technical formula changes;
- Production V1 changes;
- V1.1 changes;
- ranking or ordering changes;
- PDF Export changes;
- Database Separation runtime changes;
- database schema or data mutation;
- Yahoo, yfinance, provider, or network fetch;
- commit or push.

## 2. Current Project State

Current HEAD for this design review:

```text
677fc52c6de0373f47fe26cfdbb24257742bf25d
```

Current runtime architecture:

```text
ResearchDataStore
  -> Corrected Research Snapshot v2

LiveDataStore
  -> data/live/stocks_live.db

Scanner
  -> Scan Result Snapshot
  -> PDF Export
```

The current Database Architecture Separation work establishes the research
foundation for future Long-Term Growth AI work. The AI platform must build on
the immutable Research Snapshot boundary and must not train from the mutable
Live Store.

PDF Export remains DB-agnostic:

```text
Scan Result Snapshot -> PDF Export
```

## 3. Target Architecture Overview

Future Long-Term Growth AI pipeline:

```text
Research Snapshot
  -> Feature Engineering
  -> Feature Store
  -> Target Definition
  -> Training Dataset
  -> Model Training
  -> Model Registry
  -> Prediction
  -> OOS Validation
  -> Portfolio Risk Engine
```

Layer responsibilities:

| Layer | Responsibility |
| --- | --- |
| Research Snapshot | Immutable historical evidence source with snapshot identity, semantic checksum, and lineage. |
| Feature Engineering | Deterministic transformation from snapshot data to feature values. |
| Feature Store | Versioned registry of feature definitions, formulas, calculation metadata, and generated feature artifacts. |
| Target Definition | Fixed, versioned definition of future outcomes and horizons. |
| Training Dataset | Point-in-time join of feature artifacts and target artifacts with leakage controls. |
| Model Training | Future controlled training job using only approved training datasets. |
| Model Registry | Versioned model metadata, lineage, metrics, OOS result, approval state, and rollback reference. |
| Prediction | Future inference output from an approved model version and known feature version. |
| OOS Validation | Frozen out-of-sample evaluation isolated from model selection and tuning. |
| Portfolio Risk Engine | Converts model outputs and non-model risk signals into downside warning levels without buy/sell advice. |

## 4. Research Data Foundation

AI training must not use `LiveDataStore` directly.

Training source must be:

```text
Released Research Snapshot
  -> ResearchDataStore
  -> derived feature and target artifacts
```

A Research Snapshot is immutable historical evidence. It must answer:

- which `snapshot_id` was used;
- which `snapshot_version` was used;
- which physical materialization version was used;
- which semantic checksum was verified;
- which lineage produced the snapshot;
- which provider vintage, price basis, universe, and research window are represented.

Minimum required identity fields:

```text
snapshot_id
snapshot_version
materialization_version
semantic_checksum
source_database_sha256
manifest_path
lineage
created_at
research_window_start
research_window_end
price_data_start
price_data_end
```

Reasoning:

- immutable snapshots prevent silent data mutation;
- semantic checksums prevent storage-only identity from hiding research-meaning drift;
- explicit lineage allows features, targets, datasets, and models to be reproduced;
- AI training from mutable live cache would create future data leakage and
  untraceable result drift.

## 5. Feature Store Design

Phase 7A defines only the concept. It does not create a Feature Store database.

The future Feature Store should manage:

```text
feature_definition_id
feature_name
feature_version
feature_formula
source_snapshot_id
source_snapshot_version
source_semantic_checksum
calculation_date
code_version
feature_artifact_id
feature_artifact_checksum
feature_owner
feature_status
notes
```

Feature groups:

| Group | Example features |
| --- | --- |
| Technical | `RSI14`, `SMA20`, `SMA60`, `volume_ratio` |
| Fundamental | `EPS_growth`, `ROE`, `margin`, `revenue_growth` |
| Valuation | `PE`, `PB`, `yield` |

Design rules:

- feature definitions are versioned separately from feature artifacts;
- a formula change creates a new feature version;
- a source snapshot change creates a new feature artifact;
- a code change that can affect output must be recorded in `code_version`;
- feature values are never recomputed silently under the same artifact ID;
- feature artifacts must remain reproducible from the stated snapshot, formula,
  and code version.

## 6. Feature Lineage

Every feature must answer:

- source data;
- source snapshot;
- formula;
- formula version;
- code version;
- calculation date;
- artifact checksum.

Example:

```text
feature_definition_id: RSI14_v1
feature_name: RSI14
feature_version: v1
source: Research Snapshot v1
source_snapshot_id: research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
source_semantic_checksum: a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
formula: technical_indicator.py RSI14 definition v1
calculated_at: 2026-xx-xx
code_version: future commit SHA
feature_artifact_checksum: future checksum
```

Lineage validation must fail closed when any expected snapshot identity,
semantic checksum, formula version, or artifact checksum does not match.

## 7. Target Store Design

Phase 7A defines only target concepts. It does not create a Target Store
database or target-generation pipeline.

AI targets must be fixed before training and must be versioned.

Initial horizons:

| Horizon | Trading days | Purpose |
| --- | ---: | --- |
| Short-term | 20 | tactical movement research |
| Medium | 60 | intermediate trend research |
| Long-term | 252 | long-term growth research |

Supported target types:

| Type | Example output |
| --- | --- |
| Classification | `Positive`, `Neutral`, `Negative` |
| Regression | `future_return_percent` |

Minimum target metadata:

```text
target_definition_id
target_version
horizon_trading_days
target_type
label_rule
return_basis
observation_window_start
observation_window_end
evaluation_cutoff
source_snapshot_id
source_snapshot_version
source_semantic_checksum
target_artifact_id
target_artifact_checksum
created_at
code_version
```

Target rules:

- a target definition cannot be changed after a model is trained against it;
- a threshold change creates a new target version;
- target creation must use only future bars permitted by the fixed horizon and
  evaluation cutoff;
- incomplete future horizons must be explicitly represented rather than treated
  as negative outcomes.

## 8. Training Dataset Design

Training Dataset means:

```text
Training Dataset = Feature Artifact + Target Artifact + point-in-time join rules
```

Minimum metadata:

```text
training_dataset_id
training_dataset_version
feature_artifact_ids
target_artifact_id
source_snapshot_id
source_semantic_checksum
observation_window_start
observation_window_end
eligible_symbol_count
eligible_observation_count
excluded_observation_count
join_policy
missing_value_policy
leakage_validation_result
dataset_checksum
created_at
code_version
```

Design rules:

- features for observation date `T` may use only information available at or
  before `T`;
- targets may use information after `T` only within the declared target horizon;
- feature calculation windows must not cross the target evaluation future;
- fiscal fundamentals require point-in-time availability dates when used for
  training;
- training snapshots must be immutable once a model is trained;
- rejected or incomplete rows must be counted and explainable.

## 9. Data Leakage Prevention

The platform must prevent:

- training from `LiveDataStore`;
- training from mutable provider refresh results;
- using future prices inside features;
- using revised fundamentals before their point-in-time availability;
- tuning model or feature decisions on frozen OOS results;
- reusing validation performance as final performance;
- silently changing feature or target formulas under the same version.

Required controls:

| Control | Purpose |
| --- | --- |
| Research Snapshot identity check | Prevent mutable or incorrect data source usage. |
| Semantic checksum check | Prevent research-meaning drift. |
| Feature lineage check | Confirm feature formula, snapshot, and code version. |
| Target lineage check | Confirm horizon, label rule, and evaluation cutoff. |
| Time-split validation | Confirm training, validation, and OOS periods do not overlap. |
| Frozen OOS lock | Prevent repeated optimization against final evaluation data. |

## 10. Model Registry Design

Phase 7A defines only the registry design. It does not train or register a real
model.

Minimum registry fields:

```text
model_id
model_version
training_period
validation_period
frozen_oos_period
training_dataset_id
training_dataset_checksum
feature_version
target_version
algorithm
hyperparameters
created_at
created_by
code_version
performance_metrics
oos_result
approval_status
approved_by
approved_at
rollback_model_version
notes
```

Model Registry purpose:

- every model can be traced back to its Research Snapshot, features, targets,
  training dataset, and code version;
- every reported metric can be linked to a fixed evaluation period;
- only approved versions can be used by future prediction or portfolio risk
  workflows;
- rollback can select a prior approved model without changing data history.

## 11. OOS Governance

Out-of-Sample Validation is required because investment AI can overfit to
historical patterns, feature choices, thresholds, and market regimes. Without a
frozen OOS period, reported performance can become an artifact of repeated
tuning rather than evidence of generalization.

Required period separation:

```text
Training period
  -> model fitting

Validation period
  -> feature/model/threshold selection

Frozen OOS period
  -> final evaluation only

Final evaluation
  -> locked report tied to model version
```

Governance rules:

- training and validation periods must not overlap;
- validation and frozen OOS periods must not overlap;
- frozen OOS results must not be used to select features, targets, thresholds,
  or hyperparameters;
- final OOS reports must reference model version, training dataset checksum,
  feature version, target version, Research Snapshot ID, and semantic checksum;
- a failed OOS result should block approval or require a new model version.

## 12. Portfolio Downside Risk Warning Design

Future portfolio risk architecture:

```text
Portfolio Position
  -> Risk Engine
  -> Risk Signals
  -> Warning Level
```

Inputs:

```text
portfolio_position_id
symbol
position_size
cost_basis
holding_period
approved_model_version
feature_artifact_version
latest_feature_values
non_model_risk_context
```

Risk signal groups:

| Group | Example signals |
| --- | --- |
| Technical Risk | trend weakening, MA breakdown, volatility increase |
| Fundamental Risk | EPS deterioration, ROE decline, margin compression, revenue slowdown |
| Market Risk | sector weakness, ETF adjustment, broad-market stress |

Warning levels:

```text
LOW
MEDIUM
HIGH
```

The risk warning system must not produce buy/sell recommendations. It should
explain downside-risk evidence and leave portfolio decisions outside the model
output contract.

## 13. Risk Warning Output Design

Example future output:

```text
symbol: 2330.TW
risk_level: MEDIUM
reasons:
  - MA60 breakdown
  - EPS revision negative
model_version: ltg_model_v1
feature_version: ltg_feature_set_v1
risk_generated_at: 2026-xx-xx
```

Output rules:

- state evidence, not advice;
- include model and feature lineage;
- separate model-driven signals from deterministic non-model signals;
- explain missing or stale data;
- preserve stable warning labels for dashboard and audit use.

## 14. AI Governance

Governance requirements:

| Area | Requirement |
| --- | --- |
| Model approval | Only explicitly approved model versions can be used in future production-facing risk workflows. |
| Version control | Features, targets, datasets, code, and models require immutable versions. |
| Reproducibility | A model must be reproducible from its dataset checksum, source snapshot, and code version. |
| Rollback | A prior approved model can be restored without mutating historical artifacts. |
| Performance monitoring | Future monitoring should compare live behavior against historical and OOS expectations. |
| Auditability | Every prediction or warning should reference model, feature, target, dataset, snapshot, and checksum lineage. |

Approval states:

```text
DRAFT
VALIDATED
OOS_PASSED
APPROVED
REJECTED
DEPRECATED
ROLLED_BACK
```

## 15. Relation With Current System

Current state:

```text
Database Separation
  -> Research Foundation
```

Future state:

```text
Long-Term Growth
  -> AI Research Platform
```

The future platform must not break:

- Live Scanner;
- Production V1;
- V1.1;
- ranking and ordering;
- technical formulas;
- PDF Export;
- Research Snapshot identity;
- Database Separation runtime routing.

Boundary relationship:

| Current component | Future Long-Term Growth relationship |
| --- | --- |
| `ResearchDataStore` | Approved source for future AI training evidence. |
| Corrected Research Snapshot v2 | Immutable source snapshot for derived features, targets, datasets, and OOS artifacts. |
| `LiveDataStore` | Current-market cache for scanner/dashboard, not training source. |
| Scanner | Remains current scan workflow; future AI must not change scanner semantics in this phase. |
| Scan Result Snapshot | Remains PDF Export input. |
| PDF Export | Remains DB-agnostic and independent of AI training architecture. |

## 16. Implementation Roadmap

| Phase | Purpose | Output |
| --- | --- | --- |
| Phase 7A | Architecture Design | This design document. |
| Phase 7B | Feature Engineering Framework | Versioned feature-definition framework and dry-run reproducibility checks. |
| Phase 7C | Target Generation | Fixed target-definition artifacts for 20, 60, and 252 trading-day horizons. |
| Phase 7D | Training Dataset | Point-in-time feature + target training snapshots with leakage validation. |
| Phase 7E | Baseline Models | Baseline model experiments with registry metadata. |
| Phase 7F | OOS Evaluation | Frozen OOS governance, final metrics, and approval gates. |
| Phase 7G | Portfolio Risk Warning | Downside risk warning engine and explanation contract. |

Each future phase should define its own hard scope, validation evidence, and
explicit prohibition list before implementation begins.

## 17. Future Test And Validation Strategy

Although Phase 7A writes no code, future phases should validate:

| Validation | Required evidence |
| --- | --- |
| Data lineage validation | Snapshot ID, version, materialization version, semantic checksum, and manifest match. |
| Feature reproducibility | Same snapshot + formula + code version produces same feature checksum. |
| Target reproducibility | Same target definition + snapshot produces same target checksum. |
| Training dataset reproducibility | Same feature and target artifacts produce same dataset checksum. |
| OOS isolation | Training, validation, and frozen OOS periods are non-overlapping and locked. |
| No future leakage | Feature windows and fundamental availability dates do not use future data. |
| Model reproducibility | Model registry can reconstruct training dataset, code version, metrics, and OOS result. |
| Risk warning audit | Every warning references model, feature, target, dataset, and snapshot lineage. |

Suggested future checks:

```text
lineage manifest validation
feature artifact checksum comparison
target artifact checksum comparison
training dataset checksum comparison
period overlap rejection tests
frozen OOS mutation rejection tests
model registry metadata completeness tests
portfolio warning no-buy-sell-language tests
```

## 18. Phase 7A Safety Result

Phase 7A creates only:

```text
docs/LONG_TERM_GROWTH_ARCHITECTURE_PHASE7A.md
```

No code, tests, runtime configuration, database files, scanner logic, PDF Export
logic, or production database schema are modified by this design document.

## 19. Open Design Decisions For Future Phases

The following are intentionally deferred:

- physical storage format for Feature Store artifacts;
- physical storage format for Target Store artifacts;
- exact feature formulas and implementation modules;
- fiscal fundamental point-in-time availability model;
- classification thresholds for `Positive`, `Neutral`, and `Negative`;
- baseline model algorithm choice;
- model approval owner and sign-off process;
- dashboard placement for future risk warning output;
- live monitoring cadence and alert-retention policy.

These decisions require separate authorization because they can affect research
semantics, data storage, UI behavior, or future model behavior.
