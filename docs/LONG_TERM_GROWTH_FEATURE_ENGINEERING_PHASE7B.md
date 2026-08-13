# Long-Term Growth Feature Engineering Framework Phase 7B

Phase 7B is feature engineering framework design review only.

This document does not implement a Feature Store, Feature Database, Training
Dataset, AI model, market-data fetch, scanner change, PDF Export change,
Database Separation change, database schema change, migration, commit, or push.

## 1. Scope

Allowed in this phase:

- architecture documentation;
- feature engineering framework design;
- read-only repository inspection;
- `/tmp` design artifacts if needed;
- `git diff --check`.

Out of scope:

- Python code changes;
- test changes;
- `app.py` changes;
- `requirements.txt` changes;
- database file changes;
- Research Snapshot changes;
- Live Store changes;
- Yahoo, yfinance, provider, or network fetch;
- scanner, Production V1, V1.1, ranking, ordering, technical formula, or PDF
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

Current data architecture:

```text
ResearchDataStore
  -> Corrected Research Snapshot v2

LiveDataStore
  -> data/live/stocks_live.db

Scanner
  -> LiveDataStore
  -> Scan Result Snapshot
  -> PDF Export
```

Feature Engineering must sit between the immutable Research Snapshot and future
AI datasets. It must not train from `LiveDataStore`, modify current scanner
logic, or write back to the Research Snapshot.

## 3. Feature Engineering Overview

Future Feature Engineering Pipeline:

```text
Research Snapshot
  -> Raw Data Layer
  -> Feature Calculation Layer
  -> Feature Dataset
  -> Feature Validation
  -> Future Training Dataset
```

Layer responsibilities:

| Layer | Responsibility |
| --- | --- |
| Research Snapshot | Immutable historical evidence, addressed by snapshot ID, version, materialization version, semantic checksum, and manifest lineage. |
| Raw Data Layer | Read-only extraction view over approved snapshot datasets, with no mutation and no provider refresh. |
| Feature Calculation Layer | Deterministic formula execution using declared input fields, windows, and as-of rules. |
| Feature Dataset | Versioned feature output artifact linked to source snapshot, formula versions, calculation metadata, and checksum. |
| Feature Validation | Completeness, accuracy, stability, leakage, and outlier validation before future training use. |
| Future Training Dataset | Later phase join of validated features with fixed target artifacts. |

Feature Engineering is the bridge between Research Snapshot evidence and future
AI research. It converts snapshot data into reproducible, versioned, validated
feature artifacts without changing the original evidence source.

## 4. Feature Category Framework

The framework should group features by research role and validation need. A
feature may belong to one primary category and optional secondary tags.

| Category | Purpose | Example features |
| --- | --- | --- |
| Technical Features | Price, trend, momentum, volume, and volatility behavior derived from historical prices. | `RSI14`, `SMA20`, `SMA60`, `MACD`, `Volume_Ratio`, `Price_Momentum`, `Volatility` |
| Fundamental Features | Business performance and financial quality features derived from financial statement evidence. | `EPS_Growth`, `Revenue_Growth`, `ROE`, `Gross_Margin`, `Operating_Margin`, `Cash_Flow` |
| Valuation Features | Market valuation and shareholder-yield context. | `PE_Ratio`, `PB_Ratio`, `Dividend_Yield` |
| Market / Macro Features | Broad market, index, sector, or volatility regime context. | `Index_Trend`, `Sector_Trend`, `Market_Volatility` |
| Portfolio Risk Features | Position-level and portfolio-level downside risk context. | `Drawdown`, `Position_Risk`, `Correlation` |

Category rules:

- category assignment is metadata, not model behavior;
- the same raw field can feed multiple categories through separate feature
  definitions;
- feature categories do not change Production V1 or V1.1 formulas;
- model-specific feature subsets are selected later from approved feature
  versions.

## 5. Feature Dictionary Design

The Feature Dictionary defines what a feature means before any calculation is
accepted. It is design metadata, not a database in this phase.

Minimum dictionary fields:

```text
feature_id
feature_name
category
description
formula
formula_version
input_fields
source_dataset
calculation_frequency
effective_date_rule
available_date_rule
created_at
owner
status
notes
```

Example:

```text
feature_id: TECH_RSI14_V1
feature_name: RSI14
category: Technical
description: 14-trading-day relative strength index calculated from analysis close.
formula: RSI over 14 trading days
formula_version: v1
input_fields:
  - historical_prices.symbol
  - historical_prices.trading_date
  - historical_prices.adjusted_close
  - historical_prices.close
source_dataset: Research Snapshot historical_prices
calculation_frequency: daily
effective_date_rule: trading_date
available_date_rule: same trading date after bar close
created_at: 2026-xx-xx
owner: future feature owner
status: DRAFT
```

Dictionary status values:

```text
DRAFT
VALIDATED
APPROVED
DEPRECATED
REJECTED
```

## 6. Feature Contract Design

Each feature must have a contract before it can become an approved feature
version.

Minimum contract fields:

```text
feature_id
feature_version
input_contract
output_contract
datatype
missing_value_policy
calculation_window
as_of_rule
source_snapshot_requirement
validation_requirement
lineage_requirement
```

Contract requirements:

| Contract area | Required definition |
| --- | --- |
| Input | Required source dataset, columns, date fields, symbol fields, and minimum history. |
| Output | Output column name, row grain, symbol grain, date grain, and allowed values. |
| Datatype | `float`, `int`, `category`, `boolean`, or explicit nullable variant. |
| Missing Value Policy | Whether missing values are excluded, imputed, carried forward, or emitted as null with reason. |
| Calculation Window | Example: 20 trading days, 60 trading days, 252 trading days, trailing fiscal periods. |
| As-of Rule | Which effective date and available date control look-ahead prevention. |

Example contract:

```text
feature_id: TECH_SMA60_V1
input:
  dataset: historical_prices
  fields: symbol, trading_date, adjusted_close, close
  minimum_history: 60 trading days
output:
  field: sma60
  grain: symbol + trading_date
datatype: float
missing_value_policy: null until minimum_history is available
calculation_window: 60 trading days
as_of_rule: use only prices with trading_date <= observation_date
```

## 7. Feature Lineage Design

Every generated feature artifact must trace back to:

```text
source_snapshot_id
source_snapshot_version
source_materialization_version
source_semantic_checksum
source_dataset
formula_version
code_version
calculation_date
generated_artifact_id
generated_artifact_checksum
```

Example:

```text
feature_id: TECH_RSI14_V1
source_snapshot_id: research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
source_snapshot_version: v1
source_materialization_version: v2
source_semantic_checksum: a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
source_dataset: historical_prices
formula_version: technical_indicator.py v1
code_version: future commit SHA
calculation_date: 2026-xx-xx
generated_artifact_id: feature_artifact_technical_daily_v1_snapshot_v1
generated_artifact_checksum: future checksum
```

Lineage rules:

- lineage must be recorded for each artifact, not only each feature definition;
- lineage must fail closed when the source snapshot, semantic checksum, formula
  version, code version, or artifact checksum does not match;
- lineage records should be immutable once referenced by a future training
  dataset.

## 8. Feature Versioning Policy

Feature versions are immutable. A feature output cannot be overwritten under an
existing version when research meaning changes.

New feature version required when:

| Change | Version action |
| --- | --- |
| Formula changes | Create new feature version. |
| Input fields change research meaning | Create new feature version. |
| Calculation window changes | Create new feature version. |
| Missing value policy changes | Create new feature version. |
| As-of or available-date rule changes | Create new feature version. |
| Output datatype or label mapping changes | Create new feature version. |
| Bug fix changes historical output | Create corrected version and deprecate old version; do not overwrite. |

Example:

```text
TECH_RSI14_V1
  -> formula changed
  -> TECH_RSI14_V2
```

Old feature versions remain available for reproduction of prior model and
training dataset results.

## 9. Feature Reproducibility

Reproducibility rule:

```text
same Research Snapshot
+ same Feature Version
+ same Code Version
+ same Calculation Metadata
= same Feature Output
```

Required reproducibility metadata:

```text
feature_artifact_id
feature_artifact_checksum
source_snapshot_id
source_semantic_checksum
feature_version
formula_version
code_version
calculation_started_at
calculation_completed_at
row_count
symbol_count
null_count
validation_result
```

Feature checksum purpose:

- detect silent output drift;
- support AI training reproducibility;
- allow model registry lineage to reference exact feature artifacts;
- separate formula identity from generated artifact identity.

## 10. Feature Quality Validation Framework

Future validation should run before a feature artifact can be approved for
training dataset generation.

| Validation area | Purpose | Example evidence |
| --- | --- | --- |
| Completeness | Confirm expected rows and non-null coverage. | Row count, symbol count, missing rate by feature and date. |
| Accuracy | Confirm formula implementation matches definition. | Golden sample, hand-check sample, boundary-case checks. |
| Stability | Confirm deterministic output across reruns. | Same checksum for same snapshot/version/code. |
| Leakage Detection | Confirm no future information enters features. | As-of validation, window boundary checks, available-date checks. |
| Outlier Detection | Identify abnormal feature values. | Distribution stats, percentile thresholds, extreme-value report. |

Validation statuses:

```text
PASS
PASS_WITH_WARNINGS
FAIL
BLOCKED
```

Validation failure should block future training dataset use unless a later
authorized phase defines an explicit exception policy.

## 11. Data Leakage Prevention

Feature calculation must not use future data.

Incorrect:

```text
2020 prediction uses 2021 EPS
```

Correct:

```text
2020 prediction uses only data available on or before the feature available date.
```

For an observation date:

```text
observation_date = 2020-01-01
allowed_feature_inputs = records with available_date <= 2020-01-01
```

Leakage prevention rules:

- price features may use only prices with `trading_date <= observation_date`;
- trailing windows must end at the observation date or an earlier allowed date;
- fundamental features must use financial statement values only after their
  available date, not merely the fiscal period end date;
- market and sector context must be as-of aligned to the same observation date;
- feature validation must reject rows where `available_date > observation_date`;
- feature artifacts must record the rule used to derive `available_date`.

## 12. As-Of Feature Framework

Each feature needs three dates:

| Date | Meaning |
| --- | --- |
| `effective_date` | Date the underlying business or market event applies to. |
| `available_date` | Earliest date the feature value is allowed to be known by the model. |
| `calculation_date` | Date the artifact was generated by the feature calculation process. |

Examples:

| Feature type | Effective date | Available date | Calculation date |
| --- | --- | --- | --- |
| Daily price feature | Trading date | Trading date after bar close | Artifact generation date |
| Financial statement feature | Fiscal period end | Statement release or verified availability date | Artifact generation date |
| Sector trend feature | Index trading date | Index trading date after bar close | Artifact generation date |

As-of rule:

```text
For prediction or training observation date T:
use feature value only when available_date <= T.
```

This prevents look-ahead bias and preserves point-in-time training semantics.

## 13. Technical Feature Framework

Technical features are derived from price and volume data in the Research
Snapshot. Phase 7B does not modify current Production V1 formulas.

Technical feature groups:

| Group | Example features | Design note |
| --- | --- | --- |
| Price features | close return, moving average, price gap | Use declared analysis close policy. |
| Trend features | MA relationship, trend strength | Define exact window and relationship rule. |
| Momentum features | RSI14, MACD, price momentum | Preserve formula version and warm-up requirement. |
| Volume features | volume ratio, volume breakout | Define comparison baseline window. |
| Volatility features | ATR, standard deviation | Define price field basis and window. |

Technical contract requirements:

- input price basis must be explicit;
- warm-up rows must be null or excluded with reason;
- split/adjustment assumptions must inherit from the source snapshot metadata;
- formula outputs must be reproducible from the same snapshot and code version.

## 14. Fundamental Feature Framework

Fundamental features are derived from company financial evidence.

Feature groups:

| Group | Example features |
| --- | --- |
| Earnings | EPS, EPS growth, EPS revision direction |
| Revenue | revenue, revenue growth, revenue acceleration |
| Profitability | ROE, gross margin, operating margin |
| Cash Flow | operating cash flow, free cash flow, cash-flow quality |

Fundamental feature rules:

- every financial value needs an `available_date`;
- fiscal period end date alone is insufficient for AI training;
- restatement or revision policy must be recorded;
- missing filings must be represented explicitly;
- cross-company comparisons must use consistent fiscal frequency and currency
  semantics when applicable.

Future AI use must be able to distinguish:

```text
fiscal_period_end
statement_available_date
feature_calculation_date
```

## 15. Valuation Feature Framework

Valuation features combine market price context with fundamental values.

Examples:

| Feature | Design inputs |
| --- | --- |
| `PE_Ratio` | as-of price, trailing or forward EPS definition, EPS available date |
| `PB_Ratio` | as-of price, book value definition, statement available date |
| `Dividend_Yield` | as-of price, dividend amount, dividend availability date |

Valuation rules:

- numerator and denominator must both be as-of valid;
- denominator source and revision policy must be explicit;
- zero or negative denominator handling must be defined by feature contract;
- valuation features must not silently blend live prices with research snapshot
  fundamentals for training artifacts.

## 16. Market And Macro Feature Framework

Market and macro features provide context beyond a single stock.

Examples:

| Feature | Design note |
| --- | --- |
| `Index_Trend` | Index-level trend as-of the observation date. |
| `Sector_Trend` | Sector group trend with explicit membership version. |
| `Market_Volatility` | Broad-market volatility window and calculation basis. |

Rules:

- index and sector datasets must have their own lineage;
- sector membership must be versioned when it affects calculations;
- macro or market data must not be fetched in this phase;
- future market feature artifacts must record source snapshot or source artifact
  identity.

## 17. Feature Store Future Design

Phase 7B designs the future Feature Store concept only. It does not create a DB.

Possible future `feature_table` fields:

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
artifact_id
artifact_checksum
validation_status
```

Possible future `feature_definition` fields:

```text
feature_id
feature_name
category
formula_version
input_contract
output_contract
missing_value_policy
as_of_rule
owner
approval_status
created_at
deprecated_at
```

Storage design remains deferred. Future phases should decide whether feature
artifacts are stored as SQLite, Parquet, CSV, JSON manifests, or another format.

## 18. Feature Calculation Pipeline

Future flow:

```text
Research Snapshot
  -> Feature Calculator
  -> Feature Validation
  -> Feature Dataset
```

Feature Calculator rules:

- read from Research Snapshot through approved read-only access;
- never write back to Research Snapshot;
- never mutate `data/live/stocks_live.db`;
- never fetch Yahoo, yfinance, or provider data during calculation;
- generate a separate feature artifact with checksum and metadata;
- fail closed when snapshot identity or semantic checksum does not match;
- emit validation evidence before feature dataset approval.

Feature Dataset output should be a derived artifact, not a replacement for the
Research Snapshot.

## 19. AI Model Compatibility

The Feature Framework should support different future model families without
changing feature definitions.

| Model type | Feature framework support |
| --- | --- |
| Classification Model | Uses selected feature subset to classify fixed target labels such as `Positive`, `Neutral`, `Negative`. |
| Regression Model | Uses selected feature subset to estimate numeric target values such as `future_return_percent`. |
| Ranking Model | Uses selected feature subset to rank research candidates in future AI research, separate from current scanner ranking. |
| Risk Model | Uses selected feature subset to estimate downside or deterioration risk. |

Compatibility rules:

- model feature subsets reference approved feature versions;
- model training records exact feature artifact IDs;
- ranking models must not modify current scanner ranking or ordering;
- model compatibility does not imply any model is trained in Phase 7B.

## 20. Portfolio Risk Feature Design

Portfolio risk features extend Phase 7A's downside warning design.

Risk feature groups:

| Group | Example feature | Meaning |
| --- | --- | --- |
| Technical Risk | `trend_weakening_score` | Price trend is losing strength. |
| Technical Risk | `ma_breakdown_flag` | Price falls below a declared moving average threshold. |
| Fundamental Risk | `eps_deterioration_flag` | EPS trend worsens after as-of availability is respected. |
| Fundamental Risk | `roe_decline_score` | ROE trend weakens versus prior comparable periods. |
| Market Risk | `sector_weakness_score` | Sector trend is weaker than broad market. |
| Portfolio Risk | `position_concentration_ratio` | Position weight is high relative to portfolio value. |
| Portfolio Risk | `correlation_cluster_score` | Multiple holdings share correlated downside exposure. |

Risk feature rules:

- risk features explain evidence, not buy/sell recommendations;
- portfolio-level features require portfolio position lineage and calculation
  date;
- risk labels should remain stable across UI and audit output;
- missing data should lower confidence or emit explicit warning metadata rather
  than fabricating values.

## 21. Feature Governance

Feature Governance prevents silent feature changes.

Minimum governance fields:

```text
owner
reviewer
approval_status
feature_version
validation_status
created_at
approved_at
deprecated_at
deprecation_reason
replacement_feature_id
```

Governance rules:

- no silent feature formula change;
- no silent missing-value-policy change;
- no silent as-of-rule change;
- deprecated features remain readable for reproduction;
- approved features require passing validation evidence;
- future training datasets may use only approved or explicitly research-labeled
  feature versions.

## 22. Current System Compatibility

The Feature Framework must not break:

- `ResearchDataStore`;
- `LiveDataStore`;
- Scanner;
- Production V1;
- V1.1;
- technical formulas;
- ranking and ordering;
- PDF Export.

Future relationship:

```text
Research Snapshot
  -> Feature Layer
  -> AI Research

Live Scanner
  -> LiveDataStore
  -> Scan Result Snapshot
  -> PDF Export
```

Compatibility principles:

- Feature Engineering uses Research Snapshot evidence for future AI research;
- Live Scanner remains independent;
- PDF Export continues to consume Scan Result Snapshot;
- `LiveDataStore` remains current-market cache, not an AI training source;
- Research Snapshot remains immutable and is never rewritten by feature
  calculation.

## 23. Implementation Roadmap

| Phase | Purpose | Output |
| --- | --- | --- |
| Phase 7B | Feature Framework Design | This design review document. |
| Phase 7C | Feature Calculation Engine | Future feature calculator interfaces and dry-run artifact generation. |
| Phase 7D | Feature Validation Framework | Future validation rules, reports, and failure gates. |
| Phase 7E | Target Dataset Generation | Future fixed target artifacts and feature-target join policy. |
| Phase 7F | Baseline Model | Future baseline model experiments and registry metadata. |
| Phase 7G | OOS Evaluation | Future frozen OOS evaluation and approval gates. |
| Phase 7H | Portfolio Risk Engine | Future downside risk feature use and warning output contract. |

Each future phase should restate its own hard prohibitions before implementation
starts.

## 24. Future Validation Strategy

Although Phase 7B writes no code, future Feature Engineering implementation
should validate:

| Validation | Required evidence |
| --- | --- |
| Snapshot identity | Source snapshot ID, version, materialization version, and semantic checksum match. |
| Feature dictionary completeness | Every feature has category, formula, inputs, source dataset, frequency, and date rules. |
| Feature contract completeness | Input, output, datatype, missing policy, and window are defined. |
| Feature lineage completeness | Snapshot, formula, code, calculation date, artifact ID, and checksum are recorded. |
| Versioning discipline | Formula or policy changes create new versions, not overwritten artifacts. |
| Reproducibility | Same inputs reproduce same feature checksum. |
| Leakage prevention | `available_date <= observation_date` for training-eligible rows. |
| Feature quality | Completeness, accuracy, stability, leakage, and outlier checks pass. |

Suggested future commands or checks are intentionally deferred until a code
implementation phase is authorized.

## 25. Phase 7B Safety Result

Phase 7B creates only:

```text
docs/LONG_TERM_GROWTH_FEATURE_ENGINEERING_PHASE7B.md
```

No Python code, tests, runtime configuration, database files, scanner logic,
technical formulas, ranking, ordering, PDF Export logic, Research Snapshot, Live
Store, or database schema are modified by this design document.

## 26. Deferred Decisions

Deferred to later authorized phases:

- physical Feature Store storage format;
- exact feature calculator module boundaries;
- exact technical formula implementations for AI features;
- financial statement `available_date` source of truth;
- sector and market dataset source and versioning;
- feature artifact retention policy;
- model-specific feature subset selection;
- portfolio position input schema;
- UI placement for future risk warnings.

These decisions can affect research semantics, storage, or future AI behavior,
so Phase 7B records the framework without implementing them.
