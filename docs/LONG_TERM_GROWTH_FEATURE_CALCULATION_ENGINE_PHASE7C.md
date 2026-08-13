# Long-Term Growth Feature Calculation Engine Phase 7C

Phase 7C is Feature Calculation Engine design review only.

This document does not implement a Feature Calculator, Feature Store, Feature
Database, Target DB, Training DB, Feature Dataset, AI model, market-data fetch,
scanner change, PDF Export change, Database Separation change, database schema
change, migration, commit, or push.

## 1. Scope

Allowed in this phase:

- architecture documentation;
- Feature Calculation Engine design;
- read-only repository inspection;
- design artifact creation if needed;
- `git status`;
- `git diff --check`.

Out of scope:

- Python code changes;
- test changes;
- `app.py` changes;
- `requirements.txt` changes;
- `data/` changes;
- Research Snapshot changes;
- Live Store changes;
- Feature Store DB creation;
- Target DB creation;
- Training DB creation;
- Yahoo, yfinance, provider, or network fetch;
- Scanner, Production V1, V1.1, technical formula, ranking, ordering, or PDF
  Export changes.

## 2. Current Project State

Current HEAD for this design review:

```text
677fc52c6de0373f47fe26cfdbb24257742bf25d
```

Current architecture status:

| Area | Status |
| --- | --- |
| Database Architecture Separation | `COMPLETE_AND_PUSHED` |
| Regression Fix | `COMPLETE_AND_PUSHED` |
| PDF Export | `COMPLETE_AND_PUSHED` |
| Long-Term Growth Phase 7A | `PASS` |
| Long-Term Growth Phase 7B | `PASS` |

Current architecture:

```text
ResearchDataStore
  -> Corrected Research Snapshot v2

LiveDataStore
  -> data/live/stocks_live.db

Scanner
  -> Scan Result Snapshot
  -> PDF Export
```

The future Feature Calculation Engine must read from immutable Research
Snapshot evidence and produce separate derived feature artifacts. It must not
write back to the Research Snapshot and must not affect the live scanner path.

## 3. Feature Engineering Pipeline Position

Future architecture position:

```text
Research Snapshot
  -> Feature Calculation Engine
  -> Feature Validation Layer
  -> Feature Dataset
  -> Future Training Dataset
```

Responsibilities:

| Layer | Responsibility |
| --- | --- |
| Research Snapshot | Immutable historical evidence with snapshot ID, version, materialization version, semantic checksum, and lineage. |
| Feature Calculation Engine | Resolves feature definitions and calculator versions, executes deterministic calculations, and emits output metadata. |
| Feature Validation Layer | Checks schema, completeness, ranges, stability, and leakage before feature artifact approval. |
| Feature Dataset | Future derived artifact containing feature values and lineage; not created in Phase 7C. |
| Future Training Dataset | Later phase point-in-time join of feature artifacts and target artifacts. |

Feature Engine principle:

```text
Research Snapshot remains immutable.
Feature calculation creates derived artifacts outside the snapshot.
```

## 4. Feature Calculator Architecture

The future framework should expose a `FeatureCalculator` concept. Each
calculator owns one feature family or tightly related group of features.

Conceptual calculator responsibilities:

```text
input definition
calculation logic
output schema
validation hooks
lineage metadata
version metadata
dependency declaration
```

Conceptual calculator shape:

```text
FeatureCalculator
  -> feature_id
  -> feature_version
  -> input_contract
  -> output_contract
  -> dependencies
  -> calculate(context, input_data)
  -> validate(output)
  -> metadata()
```

Example:

```text
calculator_class: RSI14Calculator
feature_id: TECH_RSI14_V1
input: historical_prices.close
output: feature_value
version: RSI14_v1
validation:
  - schema valid
  - value range 0 to 100
  - no future rows beyond as_of_date
```

Phase 7C does not create this class in code. It only defines the future
architecture contract.

## 5. Feature Registry Design

The Feature Registry is the future source of approved feature definitions and
calculator mappings. It is design metadata in this phase, not a database.

Minimum registry fields:

```text
feature_id
feature_name
category
calculator_class
version
dependencies
input_fields
output_fields
formula_version
status
owner
created_at
deprecated_at
notes
```

Example:

```text
feature_id: TECH_RSI14_V1
feature_name: RSI14
category: Technical
calculator_class: RSI14Calculator
version: v1
dependencies:
  - historical_prices.close
input_fields:
  - symbol
  - trading_date
  - close
output_fields:
  - symbol
  - date
  - feature_id
  - feature_value
formula_version: RSI14_v1
status: ACTIVE
```

Suggested status values:

```text
DRAFT
ACTIVE
DEPRECATED
REJECTED
BLOCKED
```

Registry rules:

- feature IDs are immutable once used by an artifact;
- formula or dependency changes create a new feature version;
- deprecated features remain readable for reproducibility;
- registry resolution must fail closed when a requested feature is unknown,
  blocked, or version-mismatched.

## 6. Calculator Contract Design

Each future calculator must define input, output, metadata, and validation
contracts before implementation.

Input contract:

```text
source_dataset
required_fields
symbol_field
date_field
date_range
minimum_history
as_of_date
available_date_rule
missing_input_policy
```

Example input:

```text
source_dataset: historical_prices
required_fields:
  - symbol
  - trading_date
  - close
date_range: trailing 14 trading days or longer
as_of_date: calculation context as_of_date
```

Output contract:

```text
feature_id
symbol
date
feature_value
feature_version
calculation_id
value_datatype
null_reason
```

Metadata contract:

```text
snapshot_id
snapshot_version
source_semantic_checksum
feature_version
calculation_version
calculator_class
code_version
calculation_id
created_at
```

Validation contract:

```text
schema_validation
range_validation
completeness_validation
stability_validation
leakage_validation
```

## 7. Execution Context Design

Feature Calculation Context ensures that every calculation is reproducible and
auditable.

Minimum context fields:

```text
snapshot_id
snapshot_version
source_materialization_version
source_semantic_checksum
universe_id
as_of_date
feature_version
calculation_id
calculation_version
requested_feature_ids
code_version
created_at
```

Purpose:

- lock the Research Snapshot identity;
- lock requested feature versions;
- lock the as-of date;
- provide a stable calculation ID;
- connect feature output to future validation and artifact metadata;
- prevent accidental mixing of live data and research evidence.

Example:

```text
calculation_id: calc_2026xxxx_ltg_features_v1
snapshot_id: research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
snapshot_version: v1
source_materialization_version: v2
source_semantic_checksum: a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
universe_id: frozen_twse_218
as_of_date: 2025-12-31
feature_version: feature_set_v1
```

## 8. As-Of Date Control

Every feature calculation must know its `as_of_date`.

Rule:

```text
calculator input rows must satisfy input_available_date <= as_of_date
```

For daily price features:

```text
historical_prices.trading_date <= as_of_date
```

For financial statement features:

```text
financial_statement.available_date <= as_of_date
```

Forbidden:

- reading future prices after `as_of_date`;
- using financial values before their public or verified available date;
- using revised fundamentals without a recorded point-in-time revision policy;
- using a mutable live refresh as a feature source;
- broadening the calculation window to complete missing future data.

The engine should treat an as-of violation as a hard validation failure, not a
warning.

## 9. Dependency Management

The Feature Dependency Graph records what each feature needs before execution.

Example graph:

```text
RSI14
  -> historical_prices.close

EPS_Growth
  -> financial_statements.eps
  -> financial_statements.available_date

ROE
  -> financial_statements.net_income
  -> financial_statements.equity
  -> financial_statements.available_date

PE_Ratio
  -> historical_prices.close
  -> financial_statements.eps
  -> financial_statements.available_date
```

Dependency metadata:

```text
feature_id
dependency_dataset
dependency_field
dependency_version
required
as_of_rule
missing_policy
```

Dependency graph purpose:

- identify source datasets and fields before execution;
- determine calculation ordering for derived features;
- reuse shared inputs when multiple features depend on the same data;
- validate that all required dependencies are available in the Research
  Snapshot or approved derived artifacts;
- prevent hidden dependencies on `LiveDataStore`.

## 10. Feature Calculation Flow

Future flow:

```text
Request Feature Calculation
  -> Load Research Snapshot
  -> Resolve Feature Registry
  -> Resolve Calculator Version
  -> Resolve Dependency Graph
  -> Build Execution Context
  -> Execute Calculator
  -> Validate Output
  -> Generate Feature Artifact
  -> Store Metadata
```

Phase 7C does not generate an actual artifact or store metadata. The flow only
defines the future contract.

Flow rules:

- load Research Snapshot through read-only research access;
- verify snapshot identity and semantic checksum before any calculation;
- reject unknown or inactive feature versions;
- execute calculators only against as-of-valid input;
- validate output before artifact approval;
- produce a checksum over feature output and metadata;
- never mutate the Research Snapshot, Live Store, scanner inputs, or PDF Export
  outputs.

## 11. Feature Output Design

Conceptual feature output fields:

```text
symbol
date
feature_id
feature_value
feature_version
snapshot_id
snapshot_version
source_semantic_checksum
calculation_id
available_date
value_datatype
null_reason
validation_status
```

Output grain:

```text
symbol + date + feature_id + feature_version + calculation_id
```

Output rules:

- output is a derived feature result, not a database schema change in this
  phase;
- values must reference exact source snapshot identity;
- missing values must carry an explicit `null_reason`;
- feature values must not include buy/sell advice or scanner ranking semantics.

## 12. Feature Validation Pipeline

Validation layer:

| Validation | Purpose | Example |
| --- | --- | --- |
| Schema Validation | Confirm expected columns and datatypes. | `symbol`, `date`, `feature_id`, `feature_value` exist. |
| Completeness Validation | Confirm missing ratio and row coverage. | Missing rate below feature-specific threshold. |
| Range Validation | Confirm expected domain. | `RSI14` is between 0 and 100. |
| Stability Validation | Confirm same execution inputs produce same result. | Repeated run has same checksum. |
| Leakage Validation | Confirm no future data was used. | All input available dates are `<= as_of_date`. |

Validation result fields:

```text
validation_status
schema_status
completeness_status
range_status
stability_status
leakage_status
validation_messages
validated_at
```

Validation statuses:

```text
PASS
PASS_WITH_WARNINGS
FAIL
BLOCKED
```

Leakage failures should always be `FAIL` or `BLOCKED`, never a non-blocking
warning.

## 13. Feature Checksum Design

Feature Artifact checksum should cover both feature values and identity
metadata.

Checksum inputs:

```text
feature_values
symbol_set
date_range
feature_id
feature_version
snapshot_id
snapshot_version
source_semantic_checksum
calculation_id
calculator_version
output_schema_version
```

Checksum rule:

```text
same snapshot
+ same feature version
+ same calculator version
+ same symbol set
+ same date range
+ same as_of rules
= same checksum
```

Checksum purpose:

- detect silent output drift;
- prove reproducibility for future AI training;
- link model registry entries to exact feature artifacts;
- separate formula version from generated result identity.

## 14. Feature Version Policy

Versioning rules:

| Change | Action |
| --- | --- |
| Formula change | New feature version, such as `RSI14_v1 -> RSI14_v2`. |
| Input dependency change | New feature version. |
| Output schema change | New feature version or output schema version. |
| Missing value policy change | New feature version. |
| As-of rule change | New feature version. |
| Bug fix that changes historical output | New corrected version; do not overwrite. |
| Performance-only refactor with identical checksum | Same feature version may be retained, but code version changes. |

Forbidden:

```text
silent overwrite
silent formula mutation
silent dependency mutation
silent leakage-rule mutation
```

Old versions must remain reproducible for prior feature artifacts, training
datasets, model registry entries, and OOS reports.

## 15. Technical Feature Calculator Design

Phase 7C designs future calculators only. It does not modify current Production
V1 formulas.

| Calculator | Input | Output | Dependency | Validation |
| --- | --- | --- | --- | --- |
| `RSI14Calculator` | historical prices, close basis, 14-day window | `RSI14` value | `historical_prices.close` | range 0 to 100, warm-up nulls, as-of check |
| `MovingAverageCalculator` | historical prices, close basis, window | moving average value | `historical_prices.close` | minimum history, numeric output, as-of check |
| `MomentumCalculator` | historical prices, start/end window | momentum or return value | `historical_prices.close` | date ordering, finite value, as-of check |
| `VolumeRatioCalculator` | volume and baseline window | volume ratio | `historical_prices.volume` | non-negative values, baseline non-zero policy |
| `VolatilityCalculator` | price series and window | standard deviation, ATR-like value | price fields | non-negative value, enough observations |

Technical calculator rules:

- declare analysis price basis;
- declare warm-up behavior;
- preserve formula version;
- reject future rows beyond `as_of_date`;
- do not alter scanner, Production V1, V1.1, ranking, ordering, or current
  technical formula semantics.

## 16. Fundamental Feature Calculator Design

Future fundamental calculators:

| Calculator | Input | Output | As-of requirement |
| --- | --- | --- | --- |
| `EPSGrowthCalculator` | EPS by fiscal period | EPS growth | statement `available_date <= as_of_date` |
| `ROECalculator` | net income and equity | ROE | statement `available_date <= as_of_date` |
| `RevenueGrowthCalculator` | revenue by fiscal period | revenue growth | statement `available_date <= as_of_date` |
| `MarginCalculator` | revenue, gross profit, operating income | margin values | statement `available_date <= as_of_date` |

Fundamental calculator rules:

- financial statement `available_date` is mandatory;
- fiscal period end date is not enough for training eligibility;
- restatement or revision policy must be recorded;
- missing financial periods must be explicit;
- future values must not be backfilled into earlier as-of dates.

## 17. Valuation Feature Calculator Design

Future valuation calculators:

| Calculator | Input | Output | Leakage control |
| --- | --- | --- | --- |
| `PECalculator` | as-of price and EPS | PE ratio | EPS must be available as of calculation date. |
| `PBCalculator` | as-of price and book value | PB ratio | book value must be available as of calculation date. |
| `DividendYieldCalculator` | as-of price and dividend data | dividend yield | dividend data must be available as of calculation date. |

Valuation rules:

- numerator and denominator must both be point-in-time valid;
- zero, negative, or missing denominators need explicit missing or invalid
  policies;
- calculator output must record whether the denominator is trailing, annualized,
  or otherwise defined;
- no unpublished or future information can be used.

## 18. Portfolio Risk Feature Calculator Design

Future Risk Feature Engine:

| Calculator | Input | Output | Validation |
| --- | --- | --- | --- |
| `DrawdownCalculator` | position price history or feature price series | drawdown value | non-positive drawdown convention or explicit sign convention |
| `VolatilityRiskCalculator` | trailing volatility feature | volatility risk score | non-negative range and window validation |
| `ConcentrationRiskCalculator` | portfolio position weights | concentration score | position weights sum and missing position checks |
| `TrendWeakeningCalculator` | trend and moving average features | trend weakening signal | dependency freshness and as-of validation |

Risk feature rules:

- risk calculators explain downside evidence, not buy/sell advice;
- portfolio inputs require their own lineage and calculation date;
- missing portfolio or market data must be explicit;
- risk outputs should preserve stable labels for future warning workflows.

## 19. Feature Artifact Design

Future Feature Calculation Result Artifact should contain:

```text
feature_set_identity
snapshot_lineage
calculation_metadata
feature_output_schema
feature_values_reference
feature_checksum
validation_result
dependency_graph
error_summary
created_at
code_version
```

Artifact identity fields:

```text
artifact_id
artifact_version
feature_set_id
feature_versions
snapshot_id
snapshot_version
source_semantic_checksum
calculation_id
checksum
```

Purpose:

- allow future AI training to trace feature values back to exact Research
  Snapshot evidence;
- make repeated calculations comparable;
- allow rejected or failed artifacts to be audited without silently disappearing;
- keep derived feature results separate from immutable Research Snapshot data.

Phase 7C does not create this artifact.

## 20. Error Handling Design

Feature Engine errors must be explicit and auditable.

| Error | Handling |
| --- | --- |
| Missing data | Emit explicit missing reason; fail if required dependency is absent. |
| Invalid input | Block calculation for affected feature or artifact. |
| Formula error | Fail calculation, record calculator and feature version. |
| Checksum mismatch | Block artifact approval and require investigation. |
| Snapshot mismatch | Fail closed; do not fallback to Live Store or Legacy DB. |
| Leakage violation | Fail validation; do not approve feature artifact. |
| Unknown feature ID | Reject request before execution. |

Forbidden behavior:

```text
silent ignore
silent fallback
silent overwrite
silent partial success without counts
silent use of live data
```

Every failure should include:

```text
calculation_id
feature_id
feature_version
error_code
error_message
affected_symbols
affected_dates
created_at
```

## 21. Performance Considerations

Future implementation may consider:

| Consideration | Design note |
| --- | --- |
| Incremental calculation | Recalculate only affected symbols/dates when lineage allows. |
| Cache | Cache derived intermediate values by snapshot and checksum, not by mutable live state. |
| Parallel calculation | Parallelize independent calculators after dependency graph resolution. |
| Dependency reuse | Share input loads across calculators that depend on the same fields. |
| Chunking | Process large symbol/date ranges in deterministic chunks. |

Performance rules:

- performance optimization must not change feature outputs;
- cache hits must be validated by snapshot, feature version, and checksum;
- parallel execution must preserve deterministic ordering for checksums;
- no performance shortcut may bypass as-of or leakage validation.

Phase 7C does not implement these optimizations.

## 22. Test Strategy Design

Future tests should include:

| Test | Purpose |
| --- | --- |
| Feature calculator unit test | Verify calculator formula contract and boundary cases. |
| Registry resolution test | Verify feature ID, class, version, and status resolution. |
| Calculator contract test | Verify required input, output schema, datatype, and missing policy. |
| Lineage test | Verify snapshot, formula, code, and calculation metadata are recorded. |
| Checksum reproducibility test | Verify same inputs produce same checksum. |
| Leakage test | Verify future rows are rejected. |
| As-of date test | Verify `available_date <= as_of_date` enforcement. |
| Integration test | Verify request through validation and artifact metadata without DB mutation. |
| Current-system compatibility test | Verify scanner, PDF Export, and Live Store routes are not invoked by feature calculation. |

Test evidence should include commands, counts, failure messages, and artifact
metadata checks in later implementation phases.

## 23. Current System Compatibility

Future Feature Engine connection:

```text
ResearchDataStore
  -> Research Snapshot
  -> Feature Engine
  -> AI Platform
```

Unaffected current path:

```text
LiveDataStore
  -> Scanner
  -> Scan Result Snapshot
  -> PDF Export
```

Compatibility rules:

- Feature Engine reads research evidence through `ResearchDataStore`;
- Feature Engine does not read current scanner payloads;
- Feature Engine does not mutate `LiveDataStore`;
- Feature Engine does not change scanner logic, ranking, ordering, V1, or V1.1;
- PDF Export remains DB-agnostic and continues to consume Scan Result Snapshot;
- Research Snapshot remains immutable.

## 24. Implementation Roadmap

| Phase | Purpose | Output |
| --- | --- | --- |
| Phase 7C | Feature Calculation Engine Design | This design review document. |
| Phase 7D | Feature Calculator Framework Implementation | Future calculator interfaces, registry loading, and context objects. |
| Phase 7E | Feature Artifact Generation | Future derived feature artifact creation and metadata output. |
| Phase 7F | Target Dataset Generation | Future target artifact and feature-target join policy. |
| Phase 7G | Baseline AI Model | Future baseline model experiment and registry entry. |
| Phase 7H | OOS Evaluation | Future frozen OOS validation and approval gate. |
| Phase 7I | Portfolio Risk Engine | Future portfolio downside risk feature engine and warning outputs. |

Each future phase should restate its own hard prohibitions and validation
evidence before implementation begins.

## 25. Phase 7C Safety Result

Phase 7C creates only:

```text
docs/LONG_TERM_GROWTH_FEATURE_CALCULATION_ENGINE_PHASE7C.md
```

No Python code, tests, `app.py`, `requirements.txt`, `data/`, runtime
configuration, database schema, Research Snapshot, Live Store, scanner logic,
technical formulas, ranking, ordering, or PDF Export behavior are modified by
this design document.

## 26. Deferred Decisions

Deferred to later authorized phases:

- exact `FeatureCalculator` Python interface;
- physical Feature Registry storage;
- feature artifact storage format;
- exact calculator module boundaries;
- implementation of checksum serialization;
- real feature output schema migration or storage;
- financial statement available-date source of truth;
- portfolio position input schema;
- test fixtures and golden samples;
- performance implementation strategy.

These decisions can affect code, storage, or research semantics, so Phase 7C
records the architecture without implementing them.
