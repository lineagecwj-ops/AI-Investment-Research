# Long-Term Growth Target Generation Framework Phase 7F

Phase 7F is Target Generation Framework design review only.

This document does not create a Target DB, Training DB, Feature DB, Training
Dataset, model pipeline, AI model, market-data fetch, scanner change, PDF
Export change, Database Separation change, database schema change, migration,
commit, or push.

## 1. Scope

Allowed in this phase:

- architecture documentation;
- target generation framework design;
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
- Target DB, Training DB, Feature DB, migration, or schema change.

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
| Long-Term Growth Phase 7E | `PASS` |

Current AI pipeline:

```text
Research Snapshot
  -> Feature Calculator
  -> Feature Validation
  -> Feature Artifact
  -> Training Dataset Framework
```

Phase 7F defines how future realized outcomes become versioned Target Artifacts
that can later join with Feature Artifacts.

## 3. Target Generation Position

Target Generation position:

```text
Feature Artifact
  + Future Market Outcome
  -> Target Generator
  -> Target Artifact
  -> Training Dataset
```

Feature:

```text
Information known at or before reference date T0.
```

Target:

```text
Realized outcome after T0, calculated by a fixed target definition.
```

The two must remain completely separated. Feature generation must not know the
future target result, and target generation must not mutate feature artifacts.

## 4. Target Definition Framework

Target Definition metadata:

```text
target_id
target_name
target_type
version
calculation_window
formula
formula_version
threshold_version
created_at
owner
status
notes
```

Example:

```text
target_id: TARGET_RETURN_60D_V1
target_name: 60D Future Return
target_type: Regression
version: v1
calculation_window: 60 trading days
formula: (price_T60 - price_T0) / price_T0
formula_version: future_return_v1
```

Design rules:

- target definitions are immutable once approved;
- formula, window, threshold, or output semantics changes require a new target
  version;
- target labels are research outcomes, not buy/sell recommendations.

## 5. Forward Return Target Design

Forward return target:

```text
reference_date: T0
future_date: T + horizon
target = (price_future - price_T0) / price_T0
```

Supported horizons:

| Horizon | Trading days | Example target ID |
| --- | ---: | --- |
| Short-term | 20 | `TARGET_RETURN_20D_REG_V1` |
| Medium | 60 | `TARGET_RETURN_60D_REG_V1` |
| Long-term | 252 | `TARGET_RETURN_252D_REG_V1` |

Required design choices:

- price basis;
- reference price policy;
- future price policy;
- missing future-price handling;
- incomplete horizon handling;
- trading-calendar rule.

## 6. Classification Target Design

Classification target example for 60D future return:

```text
Positive: return > positive_threshold
Neutral: negative_threshold <= return <= positive_threshold
Negative: return < negative_threshold
```

Required metadata:

```text
target_id
target_version
threshold_version
positive_threshold
negative_threshold
calculation_window
formula_version
label_set
```

Classification rules:

- thresholds are fixed by `threshold_version`;
- threshold changes create a new target version;
- incomplete future windows must be explicit;
- class labels must not be used as trading advice.

## 7. Regression Target Design

Regression target example:

```text
target_id: TARGET_RETURN_60D_REG_V1
output: future_return_percentage
```

Required fields:

```text
start_date
end_date
horizon_trading_days
calculation_formula
formula_version
return_basis
target_value
```

Regression rules:

- formula is fixed by target version;
- start and end dates must be explicit;
- missing price data must produce deterministic incomplete or invalid status;
- return values should remain numeric until presentation.

## 8. Target Calculation Context

TargetCalculationContext design:

```text
snapshot_id
snapshot_version
source_semantic_checksum
symbol
reference_date
evaluation_window
target_version
universe_id
universe_version
calculation_id
created_at
```

Purpose:

- bind target generation to a Research Snapshot;
- bind the symbol and reference date;
- bind the future evaluation window;
- bind target definition and version;
- make every target reproducible.

Example:

```text
snapshot_id: research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
symbol: 2330.TW
reference_date: 2025-01-01
evaluation_window: 60 trading days
target_version: TARGET_RETURN_60D_REG_V1
```

## 9. As-Of And Future Window Control

Time rule:

```text
Feature inputs <= T0
Target outcome > T0 and <= T0 + horizon
```

Target generation may use realized future outcomes only to create labels or
regression values after the feature reference date. It must not write that
future outcome back into feature artifacts.

Forbidden:

- target calculation mutating features;
- feature selection using target values from validation or frozen OOS periods;
- target labels visible to feature calculators;
- future target information used before the reference date.

## 10. Target Lineage Design

Target lineage must record:

```text
source_price_data
source_snapshot_id
source_snapshot_version
source_semantic_checksum
symbol
reference_date
future_window_start
future_window_end
horizon_trading_days
formula_version
target_version
calculation_timestamp
calculation_id
```

Lineage purpose:

- reproduce target values;
- audit missing or incomplete outcomes;
- prove that target artifacts derive from the correct Research Snapshot;
- connect future Training Dataset rows to target evidence.

## 11. Target Artifact Design

Target Artifact metadata:

```text
target_id
target_version
symbol
reference_date
target_value
target_label
calculation_metadata
checksum
validation_status
created_at
```

Artifact rules:

- artifact metadata is separate from physical storage;
- target artifacts must not overwrite prior versions;
- invalid validation status blocks training dataset use;
- target artifacts must not modify Research Snapshot or Feature Artifacts.

## 12. Target Validation Framework

Validation areas:

| Validation | Purpose |
| --- | --- |
| Future window availability | Confirm enough future bars exist for the target horizon. |
| Missing outcome detection | Identify symbols or dates with unavailable target values. |
| Duplicate target detection | Reject duplicate `symbol + reference_date + target_version`. |
| Formula validation | Confirm target formula and price basis match target definition. |
| Leakage validation | Confirm target values do not contaminate features or earlier periods. |

Validation output:

```text
validation_status
target_count
missing_outcome_count
duplicate_count
incomplete_window_count
leakage_violation_count
validation_messages
```

## 13. Leakage Prevention

Incorrect:

```text
2022 prediction uses 2023 return label as a feature.
```

Correct:

```text
2022 feature values
+ realized outcome after 2022 reference date
= 2022 target label or target value
```

Leakage controls:

- target generation runs after feature artifact identity is fixed;
- target values are never written to feature artifacts;
- target labels are hidden from feature validation and feature selection inside
  frozen OOS;
- target artifacts record reference date and future evaluation window;
- dataset builder later joins features and targets only through point-in-time
  rules.

## 14. Multi-Horizon Target Design

Multi-horizon target families:

| Family | Horizon | Use |
| --- | ---: | --- |
| Short-term | 20D | short tactical classification or regression |
| Medium | 60D | intermediate outcome study |
| Long-term | 252D | long-term growth model training |

Design rules:

- each horizon has its own target version;
- different models may select different horizons;
- cross-horizon comparison requires distinct artifact identities;
- incomplete long-horizon outcomes must be explicit rather than inferred.

## 15. Target Version Policy

Target versions are immutable.

New target version required when:

| Change | Required action |
| --- | --- |
| Threshold changes | Create new target version. |
| Formula changes | Create new target version. |
| Window changes | Create new target version. |
| Price basis changes | Create new target version. |
| Label set changes | Create new target version. |
| Missing outcome policy changes | Create new target version. |

Example:

```text
RETURN_60D_V1
  -> threshold changed
  -> RETURN_60D_V2
```

Forbidden:

```text
overwrite target version
silent threshold mutation
silent formula mutation
silent horizon mutation
```

## 16. Universe Consistency

Target calculation must bind to Universe Snapshot metadata:

```text
universe_id
universe_version
universe_effective_date
symbol_membership_checksum
```

Purpose:

- avoid using today's stock pool for historical target generation;
- ensure delisted, newly listed, or excluded symbols are handled explicitly;
- make target artifacts compatible with point-in-time dataset rows.

Universe mismatch must fail deterministically and must not silently substitute a
different universe.

## 17. Target Checksum Design

Target checksum input:

```text
target_id
target_version
symbol_set
reference_date_range
future_window
target_values
target_labels
snapshot_id
source_semantic_checksum
universe_id
universe_version
```

Checksum rule:

```text
same target identity
+ same symbol set
+ same reference dates
+ same future window
+ same target values
= same checksum
```

Checksum purpose:

- detect silent label drift;
- reproduce future Training Dataset rows;
- connect model registry entries to exact target artifacts;
- make corrections visible through new target versions.

## 18. Target + Feature Join Design

Future Training Dataset row:

```text
symbol
date
features
target
feature_artifact_id
target_artifact_id
dataset_id
```

Join rules:

- feature date must equal target reference date or follow an explicit join
  policy;
- feature artifact must be generated before target outcome is attached;
- target artifact must share the same Research Snapshot and universe lineage;
- this phase does not build a dataset or join real rows.

## 19. Portfolio Risk Target Design

Future risk target examples:

| Risk target | Meaning |
| --- | --- |
| Future Drawdown | Maximum decline after reference date within a fixed window. |
| Maximum Loss | Worst realized return over the evaluation horizon. |
| Risk Event | Binary or categorical downside event occurrence. |

Risk target rules:

- risk outcome definition must be versioned;
- risk target does not imply buy/sell advice;
- portfolio risk targets must record position context separately from market
  outcome context;
- this phase does not create risk targets.

## 20. OOS Compatibility

Target Generation must support:

```text
Training
Validation
Frozen OOS
```

OOS compatibility rules:

- target calculation can label frozen OOS rows for final evaluation;
- OOS target results must not be used to tune thresholds, features, or model
  hyperparameters;
- target artifact lineage must record split membership or split policy;
- target generation must not expose OOS future outcomes to training decisions.

## 21. Error Handling Design

Deterministic errors:

| Error | Handling |
| --- | --- |
| Insufficient future data | Mark incomplete or block according to target policy; report count. |
| Missing price | Block affected target rows or emit invalid status with reason. |
| Universe mismatch | Fail generation and report expected vs actual universe identity. |
| Checksum mismatch | Block artifact approval and require investigation. |
| Formula error | Fail target generation with formula version and target ID. |
| Duplicate target | Reject duplicate `symbol + reference_date + target_version`. |

Forbidden:

```text
silent ignore
silent target overwrite
silent fallback to LiveDataStore
silent universe substitution
silent threshold mutation
```

## 22. Implementation Roadmap

| Phase | Purpose | Output |
| --- | --- | --- |
| Phase 7F | Target Generation Framework | This design document. |
| Phase 7G | Target Generator Implementation | Future target definitions, context, validation, checksum, and artifact metadata. |
| Phase 7H | Training Dataset Builder | Future feature-target row join and dataset artifact generation. |
| Phase 7I | Baseline AI Model | Future baseline model experiment. |
| Phase 7J | OOS Evaluation | Future frozen OOS evaluation and model approval gate. |
| Phase 7K | Portfolio Risk Engine | Future portfolio downside risk target and warning engine. |

Each implementation phase must restate hard rules before code changes begin.

## 23. Current System Compatibility

Future Target Generator source:

```text
Research Snapshot
  -> Feature Artifact
  -> Target Generator
  -> Target Artifact
```

Unaffected production path:

```text
LiveDataStore
  -> Scanner
  -> Scan Result Snapshot
  -> PDF Export
```

Compatibility principles:

- Production Scanner remains independent;
- Target Generator must not mutate `ResearchDataStore` or `LiveDataStore`;
- Target Generator must not modify scanner, Production V1, V1.1, ranking,
  ordering, technical formulas, or PDF Export;
- PDF Export remains DB-agnostic and consumes Scan Result Snapshot only.

## 24. Phase 7F Safety Result

Phase 7F creates only:

```text
docs/LONG_TERM_GROWTH_TARGET_GENERATION_FRAMEWORK_PHASE7F.md
```

No code, tests, runtime configuration, database files, schema, Research
Snapshot, Target DB, Training DB, Feature DB, scanner logic, PDF Export logic,
Production V1, V1.1, ranking, ordering, or technical formulas are modified by
this design document.

## 25. Deferred Decisions

Deferred to later authorized phases:

- target generator Python interfaces;
- physical target artifact storage;
- exact target row schema;
- real price basis implementation;
- exact classification thresholds;
- incomplete future window policy;
- universe source of truth;
- target validation implementation;
- dataset builder join implementation;
- OOS split enforcement implementation.

These decisions can affect code, storage, model behavior, or research
semantics, so Phase 7F records the framework without implementing them.
