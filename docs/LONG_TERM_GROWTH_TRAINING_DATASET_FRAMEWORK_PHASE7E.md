# Long-Term Growth Training Dataset Framework Phase 7E

Phase 7E is Training Dataset Framework design review only.

This document does not create a Training Dataset, Training Database, Feature
Database, Dataset Database, model pipeline, AI model, market-data fetch, scanner
change, PDF Export change, Database Separation change, database schema change,
migration, commit, or push.

## 1. Scope

Allowed in this phase:

- architecture documentation;
- dataset framework design;
- read-only repository inspection;
- `git status`;
- `git diff --check`.

Out of scope:

- Python code changes;
- test changes;
- `app.py` changes;
- `requirements.txt` changes;
- `data/` changes;
- Research Snapshot changes;
- ResearchDataStore or LiveDataStore changes;
- Scanner, Production V1, V1.1, technical formula, ranking, ordering, or PDF
  Export changes;
- Yahoo, yfinance, provider, or network fetch;
- Training DB, Feature DB, Dataset DB, migration, or schema change.

## 2. Current Project State

Current HEAD for this design review:

```text
677fc52c6de0373f47fe26cfdbb24257742bf25d
```

Current status:

| Area | Status |
| --- | --- |
| Database Architecture Separation | `COMPLETE_AND_PUSHED` |
| Regression Fix | `COMPLETE_AND_PUSHED` |
| PDF Export | `COMPLETE_AND_PUSHED` |
| Long-Term Growth Phase 7A | `PASS` |
| Long-Term Growth Phase 7B | `PASS` |
| Long-Term Growth Phase 7C | `PASS` |
| Long-Term Growth Phase 7D-1 | `PASS` |
| Long-Term Growth Phase 7D-2 | `PASS` |
| Long-Term Growth Phase 7D-3 | `PASS` |

Current Feature Pipeline:

```text
Research Snapshot
  -> Feature Calculator
  -> Feature Validation
  -> Checksum
  -> Feature Artifact
```

Phase 7E designs the next conceptual layer: how approved Feature Artifacts and
fixed Target Definitions will later combine into reproducible Training Dataset
artifacts.

## 3. Training Dataset Architecture Overview

Future AI pipeline position:

```text
Research Snapshot
  -> Feature Artifact
  -> Target Definition
  -> Training Dataset
  -> Model Training
```

A Training Dataset is the point-in-time join of:

```text
Feature Artifact + Target Artifact + observation policy + universe policy
```

Layer responsibilities:

| Layer | Responsibility |
| --- | --- |
| Research Snapshot | Immutable evidence source with snapshot identity and semantic checksum. |
| Feature Artifact | Versioned feature values known as of each feature date. |
| Target Definition | Fixed future outcome rule and horizon. |
| Training Dataset | Reproducible row set joining feature values to target labels or numeric outcomes. |
| Model Training | Future phase that consumes an approved dataset; not performed in Phase 7E. |

## 4. Feature / Target Separation Design

Feature and Target must remain separate.

Feature:

```text
Information knowable at or before feature_as_of_date.
```

Target:

```text
Future realized outcome after feature_as_of_date, evaluated by a fixed target rule.
```

Example:

```text
feature_date: 2025-01-01
feature_values: technical, fundamental, valuation, market context available on 2025-01-01
target: future 60 trading day return
```

Prohibited:

- feature values that include future prices;
- feature values that include future financial statements;
- feature values that use future universe membership;
- target thresholds changed after model training without a new target version;
- mixing validation or OOS outcomes into feature selection under the same
  dataset version.

## 5. Training Dataset Model Design

Conceptual Training Dataset metadata:

```text
dataset_id
dataset_version
snapshot_id
snapshot_version
snapshot_semantic_checksum
feature_set_version
feature_artifact_ids
target_version
target_artifact_id
universe_id
universe_version
observation_start
observation_end
created_at
created_by_pipeline
checksum
validation_status
notes
```

Purpose:

- every dataset is traceable;
- every dataset can be reproduced;
- every model can cite the exact dataset it was trained on;
- dataset changes are explicit and versioned.

## 6. Dataset Lineage Design

Every Training Dataset must answer:

| Question | Required lineage |
| --- | --- |
| Which Research Snapshot? | `snapshot_id`, `snapshot_version`, materialization version, semantic checksum. |
| Which Features? | feature IDs, feature versions, feature artifact IDs, feature checksums. |
| Which Target Definition? | target ID, target version, horizon, label or regression rule. |
| Which Universe? | universe snapshot, effective dates, symbol membership version. |
| When calculated? | dataset `created_at`, pipeline version, code version. |
| Which rows? | observation date range, symbol count, row count, exclusion count. |

Lineage must be immutable once a model references the dataset.

## 7. Dataset Versioning Policy

Training Dataset versions are immutable.

New dataset version required when:

| Change | Required action |
| --- | --- |
| Feature version changes | Create new dataset version. |
| Target version changes | Create new dataset version. |
| Universe changes | Create new dataset version. |
| Research Snapshot changes | Create new dataset version. |
| Observation window changes | Create new dataset version. |
| Missing-value policy changes | Create new dataset version. |
| Leakage validation rule changes | Create new dataset version. |
| Bug fix changes row content | Create corrected dataset version; do not overwrite. |

Example:

```text
TrainingDataset_v1
  -> feature set changed
  -> TrainingDataset_v2
```

Forbidden:

```text
overwrite existing dataset
silent row mutation
silent target rule mutation
silent universe mutation
```

## 8. Target Definition Framework

Target Layer horizons:

| Horizon | Trading days | Purpose |
| --- | ---: | --- |
| Short-term target | 20 | short tactical outcome research |
| Medium target | 60 | medium trend outcome research |
| Long-term target | 252 | long-term growth outcome research |

Supported target modes:

| Mode | Output |
| --- | --- |
| Classification | fixed class label such as `Positive`, `Neutral`, `Negative` |
| Regression | numeric value such as `future_return_percent` |

Target metadata:

```text
target_id
target_version
target_mode
horizon_trading_days
evaluation_window
calculation_formula
thresholds
created_at
code_version
checksum
```

## 9. Classification Target Design

Example classes:

```text
Positive
Neutral
Negative
```

Required classification fields:

```text
target_id
target_version
threshold_positive
threshold_negative
calculation_date
evaluation_window_start
evaluation_window_end
horizon_trading_days
label_policy
```

Classification rules:

- thresholds are fixed by target version;
- class definitions cannot change under the same version;
- incomplete future windows must be explicit, not silently treated as
  `Negative`;
- class labels are research outcomes, not trading recommendations.

## 10. Regression Target Design

Example regression target:

```text
future_return_percent
```

Required regression fields:

```text
target_id
target_version
start_date
end_date
horizon_trading_days
calculation_formula
return_basis
version
```

Regression rules:

- formula must be fixed by target version;
- start and end date semantics must be explicit;
- missing future prices must produce an incomplete or excluded target status;
- target values may use future realized outcomes only inside the declared target
  evaluation window.

## 11. As-Of Dataset Design

Every training row must know:

```text
symbol
feature_as_of_date
target_evaluation_start
target_evaluation_end
feature_artifact_id
target_artifact_id
dataset_id
```

As-of rule:

```text
feature_available_date <= feature_as_of_date
target_evaluation_start > feature_as_of_date
```

Training rows must distinguish:

- feature date;
- feature available date;
- target start date;
- target end date;
- dataset creation date.

This separation prevents look-ahead bias and makes leakage validation possible.

## 12. Data Leakage Prevention

Dataset leakage validation must prohibit:

- future feature values;
- future financial statement values;
- future universe membership;
- target outcomes leaking into features;
- validation or OOS periods influencing training-period feature selection;
- mutable Live Store data entering Training Dataset artifacts.

Required controls:

| Control | Purpose |
| --- | --- |
| Feature as-of check | Ensure feature values were available at the row observation date. |
| Target horizon check | Ensure target values are evaluated only after the feature date. |
| Universe point-in-time check | Ensure symbol eligibility uses the correct historical universe. |
| Snapshot checksum check | Ensure feature and target artifacts derive from the expected Research Snapshot. |
| Split isolation check | Ensure training, validation, and frozen OOS periods do not contaminate each other. |

Leakage detection must fail deterministically and must not silently drop rows
without counts and reasons.

## 13. Dataset Validation Framework

Future dataset validation should include:

| Validation | Purpose |
| --- | --- |
| Feature completeness | Confirm expected feature columns and non-null policy. |
| Target completeness | Confirm targets exist or have explicit incomplete status. |
| Duplicate detection | Confirm no duplicate `symbol + feature_as_of_date + target_version` rows. |
| Missing value analysis | Count missing features and targets by symbol, date, and feature. |
| Leakage detection | Confirm as-of and target horizon constraints. |
| Checksum validation | Confirm deterministic dataset identity and row content. |

Validation output:

```text
validation_status
row_count
symbol_count
feature_missing_count
target_missing_count
duplicate_count
leakage_violation_count
checksum
validation_messages
```

## 14. Dataset Checksum Design

Dataset checksum input:

```text
dataset_id
dataset_version
feature_version
target_version
snapshot_id
snapshot_semantic_checksum
symbol_universe
date_range
row_content
missing_value_policy
split_policy
```

Checksum rule:

```text
same Research Snapshot
+ same Feature Version
+ same Target Version
+ same Universe Version
+ same row content
= same Training Dataset checksum
```

Checksum purpose:

- detect silent row drift;
- support model reproducibility;
- connect model registry entries to exact dataset artifacts;
- make corrections visible through new dataset versions.

## 15. Training / Validation / OOS Split Design

Dataset split design:

```text
Training period
  -> model fitting

Validation period
  -> model and feature selection

Frozen OOS period
  -> final evaluation only
```

Example:

| Split | Period |
| --- | --- |
| Training | 2015-2021 |
| Validation | 2022 |
| Frozen OOS | 2023-2025 |

Split rules:

- split periods must not overlap;
- validation results must not be used as final OOS evidence;
- OOS results must not be used to tune features, targets, thresholds, or
  hyperparameters;
- every row must carry its split assignment and split policy version.

## 16. Point-In-Time Universe Design

Point-in-time universe handling prevents using today's stock pool to evaluate
past dates.

Required universe metadata:

```text
universe_id
universe_version
effective_date
symbol_membership
membership_source
membership_checksum
created_at
```

Universe rules:

- each training row must use the universe valid for its feature date;
- delisted or not-yet-listed symbols must not be silently included;
- universe changes require a new dataset version;
- symbol exclusions must be counted and explained.

## 17. Dataset Artifact Design

Training Dataset Artifact metadata:

```text
dataset_id
dataset_version
feature_lineage
target_lineage
snapshot_lineage
universe_lineage
row_count
symbol_count
date_range
split_policy
checksum
validation_status
created_at
created_by_pipeline
notes
```

Artifact rules:

- artifact metadata is separate from physical row storage;
- invalid validation status blocks model training use;
- artifacts must not overwrite prior versions;
- artifacts must not mutate Feature Artifacts or Research Snapshots.

## 18. Portfolio Risk Dataset Design

Future Portfolio Risk Dataset concept:

```text
Position Features
  + Risk Features
  + Market Features
  + Outcome
  -> Portfolio Risk Dataset
```

Possible row fields:

```text
portfolio_id
symbol
position_weight
feature_as_of_date
technical_risk_features
fundamental_risk_features
market_risk_features
portfolio_context
outcome
```

This phase does not create a Portfolio Risk Dataset. It only records how future
risk datasets should inherit the same lineage, as-of, checksum, and leakage
controls.

## 19. Model Compatibility Design

Different model families may require different dataset artifacts.

| Model type | Dataset requirement |
| --- | --- |
| Classification Model | Uses classification target labels and approved feature subsets. |
| Regression Model | Uses numeric target values and numeric feature matrices. |
| Ranking Model | Uses pairwise or listwise research labels in a future AI research context; it must not alter current scanner ranking. |
| Risk Model | Uses downside outcome definitions and risk feature groups. |

Compatibility rules:

- model training must reference exact dataset ID and checksum;
- different model purposes can use different dataset versions;
- no model should train from mutable Live Store data;
- dataset semantics must not imply buy/sell advice.

## 20. Reproducibility Design

Reproducibility rule:

```text
same Research Snapshot
+ same Feature Version
+ same Target Version
+ same Universe Version
+ same Builder Version
= same Training Dataset checksum
```

Required evidence:

- source snapshot identity;
- feature artifact checksums;
- target artifact checksum;
- universe membership checksum;
- dataset builder version;
- dataset validation result;
- final dataset checksum.

## 21. Error Handling Design

Required deterministic errors:

| Error | Handling |
| --- | --- |
| Feature missing | Block affected rows or dataset; report feature ID, symbol, date, and count. |
| Target missing | Mark incomplete or block according to target policy; report count. |
| Checksum mismatch | Block artifact approval and require investigation. |
| Leakage detected | Fail validation; do not approve dataset. |
| Universe mismatch | Block dataset generation and report expected vs actual universe identity. |
| Duplicate rows | Fail validation unless explicit deduplication policy is approved. |

Forbidden:

```text
silent ignore
silent row overwrite
silent fallback to LiveDataStore
silent target relabeling
silent universe substitution
```

## 22. Implementation Roadmap

| Phase | Purpose | Output |
| --- | --- | --- |
| Phase 7E | Training Dataset Framework Design | This design document. |
| Phase 7F | Target Generation Framework | Future target definitions and target artifact metadata. |
| Phase 7G | Dataset Builder Implementation | Future point-in-time feature-target join and dataset artifact generation. |
| Phase 7H | Baseline AI Model | Future baseline model experiment using approved dataset artifacts. |
| Phase 7I | OOS Evaluation | Future frozen OOS evaluation and model approval gate. |
| Phase 7J | Portfolio Risk Engine | Future portfolio risk dataset and warning engine. |

Each future phase must restate its own hard rules before implementation begins.

## 23. Current System Compatibility

Future Training Dataset source:

```text
Research Snapshot
  -> Feature Artifact
  -> Target Artifact
  -> Training Dataset Artifact
```

Unaffected production path:

```text
LiveDataStore
  -> Scanner
  -> Scan Result Snapshot
  -> PDF Export
```

Compatibility principles:

- Research Platform and Production Scanner remain isolated;
- Training Dataset generation must not modify `ResearchDataStore` semantics;
- Training Dataset generation must not read or mutate `LiveDataStore`;
- Scanner, Production V1, V1.1, ranking, ordering, and PDF Export remain
  unchanged;
- PDF Export remains DB-agnostic and consumes Scan Result Snapshot only.

## 24. Phase 7E Safety Result

Phase 7E creates only:

```text
docs/LONG_TERM_GROWTH_TRAINING_DATASET_FRAMEWORK_PHASE7E.md
```

No code, tests, runtime configuration, database files, schema, Research
Snapshot, Feature DB, Training DB, Dataset DB, scanner logic, PDF Export logic,
Production V1, V1.1, ranking, ordering, or technical formulas are modified by
this design document.

## 25. Deferred Decisions

Deferred to later authorized phases:

- physical target artifact storage format;
- dataset builder implementation;
- real dataset row schema;
- training / validation / OOS date boundaries;
- exact classification thresholds;
- regression return basis;
- point-in-time universe source of truth;
- dataset missing-value policy;
- baseline model algorithm;
- portfolio risk outcome definition.

These decisions can affect code, storage, model behavior, or research
semantics, so Phase 7E records the framework without implementing them.
