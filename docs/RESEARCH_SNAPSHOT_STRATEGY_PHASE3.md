# Research Snapshot Strategy Phase 3

## 1. Problem Statement

The project currently has one SQLite file, `data/stocks.db`, serving both
reproducible research and live mutable cache workflows. Recent audits showed
that live refresh can change `adjusted_close`, which is a research-relevant
field because technical analysis uses `adjusted_close if available else close`.

This phase defines a strategy and specification for Research Snapshots. It does
not create a database, copy data, run migrations, or decide whether the current
DB SHA should become canonical.

## 2. Phase Lineage

This document belongs to the Database Architecture Separation series:

| Phase | Document | Purpose |
|---|---|---|
| Phase 1 | `docs/DATABASE_ARCHITECTURE_SEPARATION_PHASE1.md` | Inventory and design. |
| Phase 2 | `docs/DATABASE_ACCESS_BOUNDARY_PHASE2.md` | Data access boundary design. |
| Phase 3 | `docs/RESEARCH_SNAPSHOT_STRATEGY_PHASE3.md` | Research Snapshot strategy and specification. |

Phase 3 extends Phase 2 without changing its boundary decision:

```text
ResearchDataStore: snapshot-addressed, read-only, deterministic
LiveDataStore: mutable cache, refresh-capable, never canonical by default
PDF Export: snapshot consumer, no DB access
```

## 3. Snapshot Definition

A Research Snapshot is a named, versioned, immutable reference to a complete set
of research inputs. It is addressed by explicit metadata rather than inferred
from a mutable database filename.

Each snapshot answers:

| Question | Required answer |
|---|---|
| What data version? | Source database checksum, row counts, price coverage, universe, provider vintage, price basis, and semantic checksum. |
| What role? | Validation, backtest, OOS, AI training, or production reference role. |
| When created? | UTC `created_at` and process metadata. |
| Which datasets are included? | Explicit dataset scope entries. |
| Which research uses it? | Artifact links and dependent dataset IDs. |
| Is it immutable? | Released snapshots are immutable; corrections require a new snapshot version. |

## 4. Metadata Contract

Design-only metadata fields:

```text
snapshot_id
snapshot_version
snapshot_role
status
created_at
created_by_process
source_database_path
source_database_sha256
database_checksum
artifact_checksum
semantic_checksum
row_count
symbol_count
duplicate_count
source_database_integrity
universe_id
universe_version
price_data_start
price_data_end
research_window_start
research_window_end
provider_name
provider_data_vintage
loader_version
ingestion_process_version
price_basis_version
dataset_scope
parent_snapshot_id
deprecated_by_snapshot_id
purpose
notes
```

Recommended status values:

```text
CANDIDATE
VALIDATED
RELEASED
DEPRECATED
REJECTED
```

`snapshot_role` is a logical role, not a requirement to create one physical DB
per role. Valid initial roles:

```text
RESEARCH_VALIDATION
BACKTEST
AI_TRAINING
OOS_VALIDATION
PRODUCTION_REFERENCE
```

## 5. Physical vs Logical Snapshot Model

One physical Research Snapshot can support multiple logical research roles when
the underlying price data, universe, provider vintage, price basis, and research
window are compatible.

Example:

```text
research_snapshot_frozen_twse218_2018_2026_v1
  -> Research Validation artifacts
  -> Backtest artifacts
  -> AI Training feature and target artifacts
  -> OOS artifacts
  -> Production Reference artifacts
```

The preferred model is:

```text
Released physical Research Snapshot
  + logical snapshot_role
  + versioned derived artifacts
```

Avoid duplicating identical DB files just because a snapshot is used by more
than one research role. Derived artifacts must carry their own version and
checksum.

## 6. Naming Convention

Snapshot IDs should be deterministic and readable:

```text
research_snapshot_<scope>_<price_coverage>_v<version>
```

Examples:

```text
research_snapshot_frozen_twse218_2018_2026_v1
research_snapshot_current_reference_twse218_2018_2026_v1
research_snapshot_ltg_candidate_twse218_2018_2026_v1
```

Dataset IDs should include the snapshot ID or reference it directly:

```text
feature_dataset_<feature_definition_version>_<snapshot_id>
target_dataset_<target_definition_id>_<snapshot_id>
training_dataset_<feature_artifact_id>_<target_artifact_id>
```

## 7. Date Range Semantics

Snapshot metadata must separate price coverage from research observation
windows.

Price coverage:

```text
price_data_start
price_data_end
```

This is the actual trading-date range physically available inside the snapshot.

Research observation window:

```text
research_window_start
research_window_end
```

This is the period in which research observations may be created.

Example for future Long-Term Growth work:

```text
price_data_start = 2018-01-01
price_data_end = 2026-12-31
research_window_start = 2018-01-01
research_window_end = 2025-12-31
```

The 2026 forward bars can be used to complete forward target evaluation, but
they do not automatically become 2026 training observations.

## 8. Target Evaluation Window Semantics

Base Research Snapshot metadata stores price coverage and the allowed research
observation window. Target-specific metadata belongs to derived target artifacts.

Target artifacts should record:

```text
research_snapshot_id
target_definition_id
observation_window_start
observation_window_end
forward_horizon
evaluation_cutoff
target_semantic_checksum
```

This avoids forcing every target definition into the base price snapshot.

## 9. Price Basis Metadata

Each snapshot must record the price semantics used when the snapshot was
generated.

Required price basis fields:

```text
price_basis_version
open_basis
high_basis
low_basis
close_basis
adjusted_close_basis
analysis_close_policy
```

Initial analysis close policy:

```text
analysis_close = adjusted_close if available else close
```

This document records the current semantics; it does not change existing
calculation formulas.

## 10. Provider and Data Vintage Metadata

Snapshot metadata must distinguish provider vintages such as old Yahoo
historical data and a later Yahoo adjusted-close restatement.

Required provider fields:

```text
provider_name
provider_data_vintage
loader_version
ingestion_process_version
```

If the provider does not expose an official version,
`provider_data_vintage` may be a documented fetch batch timestamp, release
identity, or ingestion batch ID. `fetched_at` alone is not sufficient as the
only research identity because it does not fully describe provider-side
restatement semantics.

## 11. Adjustment Vintage Policy

A released snapshot must not mix incompatible `adjusted_close` vintages.

Forbidden state:

```text
old-vintage existing rows
  + partially refreshed existing rows
  + same snapshot_id
```

If a provider restates `adjusted_close`, the accepted path is:

```text
new candidate snapshot
  -> new provider_data_vintage
  -> new checksum
  -> adjustment-vintage consistency audit
  -> validation
  -> new release version
```

Candidate snapshot release must validate adjustment-vintage consistency before
the snapshot can become `RELEASED`.

## 12. CASE-C Protection Rule

LiveDataStore refresh must never silently become a Research Snapshot, even if
the refreshed DB has:

```text
new rows
integrity ok
duplicates 0
same or improved coverage
```

Release gates must explicitly check:

```text
existing-key research-field changes
adjusted_close restatement
provider vintage
price-basis compatibility
semantic checksum
```

If existing canonical `adjusted_close` values changed, the data must become a
new candidate snapshot. It must not be silently promoted under an existing
snapshot ID.

## 13. Dataset and Table Scope

A snapshot manifest must explicitly declare which datasets and tables are inside
the snapshot. Snapshot meaning must not be inferred from the DB filename alone.

Initial dataset scope structure:

```text
dataset_name
schema_version
row_count
symbol_count optional
date_start optional
date_end optional
semantic_checksum optional
included
notes
```

Expected initial datasets:

| Dataset | Required declaration |
|---|---|
| `historical_prices` | Included for price snapshots. |
| `research_universe_metadata` | Included for frozen research universe identity. |
| `listing_dates` | Included when used by research filters or target eligibility. |
| `historical_financials` | Explicitly included or excluded. |
| `features` | Explicitly included only for feature artifact snapshots. |
| `targets` | Explicitly included only for target artifact snapshots. |
| `outcomes` | Explicitly included only for outcome/backtest artifacts. |

## 14. Snapshot Manifest Design

Future snapshots should use a JSON manifest. This phase defines the design only
and does not create a manifest file.

Conceptual filename:

```text
research_snapshot_manifest.json
```

Conceptual structure:

```text
metadata
database_fingerprint
dataset_scopes
universe_identity
price_basis
provider_vintage
date_ranges
checksums
release_status
lineage
validation_evidence
```

The manifest is the contract consumed by ResearchDataStore and downstream
research artifacts.

## 15. Checksum Policy

Every released snapshot should carry three checksum layers:

| Checksum | Purpose |
|---|---|
| Database SHA-256 | Byte-level identity of the physical SQLite artifact. |
| Artifact checksum | File integrity for JSON, Markdown, dataset, model, or report artifacts. |
| Semantic checksum | Normalized research meaning independent of harmless formatting or storage layout. |

SQLite byte SHA changes do not always prove research content changed, because
page layout or metadata can change. Conversely, a research-field semantic
change is significant even if row count, symbol count, duplicates, and integrity
remain unchanged.

Checksum records should also include row count, symbol count, duplicate count,
integrity check, date ranges, universe ID, provider vintage, and price basis
version.

## 16. Immutability Rules

Released snapshots cannot be:

- overwritten;
- silently updated;
- refreshed from Yahoo;
- modified in place after `adjusted_close` restatement;
- reused under the same ID after any research-relevant data correction.

Allowed actions:

- create a new candidate snapshot;
- validate it;
- release it as a new version;
- mark an older snapshot as deprecated while preserving its metadata and artifacts.

Snapshots are not rolled back by editing them. If a released snapshot has a
problem:

1. Mark the snapshot `DEPRECATED` or `REJECTED`.
2. Record the reason and evidence.
3. Create a corrected candidate snapshot.
4. Validate and release a new version.
5. Leave old artifacts linked to the old snapshot for auditability.

## 17. Release Gate

Design-only release process:

```text
1. Candidate source selected
2. Source provenance recorded
3. Database integrity validation
4. Dataset/table scope validation
5. Row/symbol reconciliation
6. Universe validation
7. Price basis validation
8. Provider/vintage validation
9. Existing-key research-field diff audit, if this is a new version
10. Adjustment-vintage consistency audit
11. Research-window coverage validation
12. Database SHA recorded
13. Semantic checksum recorded
14. Manifest generated
15. Approval recorded
16. RELEASED
```

Any failed gate prevents release.

Required release metadata:

- creator or process identity;
- creation timestamp;
- validation commands or review evidence;
- source DB SHA;
- row count, symbol count, duplicate count, and integrity result;
- dataset/table scope;
- universe version;
- price basis version;
- provider data vintage;
- known limitations;
- release decision status.

## 18. Canonical Snapshot Selection Procedure

The current DB SHA
`69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7` and the old
composite canonical context remain an explicit decision point.

This phase does not decide which source becomes canonical.

```text
CURRENT_CANONICAL_DECISION = OPEN
```

Future canonical snapshot selection should consider:

- reproducibility;
- provider consistency;
- adjustment vintage consistency;
- coverage;
- existing-key research-field changes;
- current scanner relevance;
- compatibility with existing research artifacts;
- ability to pass the release gate.

## 19. Path and Configuration Contract

Future DB paths should be centralized and explicit:

```text
research_db_path
live_db_path
research_snapshot_id
research_manifest_path
```

Rules:

- research writers must not use `live_db_path`;
- live cache writers must not use a released `research_db_path`;
- research jobs must fail closed when a required snapshot ID or manifest is
  missing;
- runtime scanner paths must not write candidate or released Research Snapshots.

This phase only defines the contract. It does not implement configuration.

## 20. Read-Only Enforcement

ResearchDataStore normal runtime access should enforce:

```text
SQLite URI mode=ro
PRAGMA query_only=ON
required research_snapshot_id
required manifest checksum verification
```

Normal research reads must not open writable SQLite connections. Creating a new
Candidate Snapshot must use a separate release/build process, not the runtime
scanner.

## 21. Live Writer Isolation

LiveDataStore owns mutable cache writes:

```text
Yahoo refresh
save_historical_prices
historical_price_fetch_state updates
current profile cache writes
```

These write paths must point only to LiveDataStore. They must reject released
research paths. A live refresh can create source material for a future candidate
snapshot only through a separate release process.

## 22. Database Separation Relation

ResearchDataStore:

- stores or serves released Research Snapshots;
- opens read-only for normal research usage;
- requires snapshot ID for canonical research jobs;
- verifies manifest metadata and checksums;
- exposes checksum, provider vintage, price basis, and semantic metadata.

LiveDataStore:

- owns mutable cache and provider refresh state;
- may refresh prices and fundamentals;
- does not become canonical unless a separate snapshot release process promotes
  data into ResearchDataStore.

Research and Live must not share mutable canonical state.

## 23. AI Pipeline Relation

Long-Term Growth AI should depend on Research Snapshot lineage:

```text
Research Snapshot
  -> Feature Artifact
  -> Target Artifact
  -> Training Dataset
  -> Model Version
  -> OOS Result
```

Each downstream object must reference the upstream snapshot and checksum.

## 24. Feature, Target, and Training Lineage

Feature artifacts must include:

```text
research_snapshot_id
feature_definition_version
observation_window_start
observation_window_end
feature_semantic_checksum
feature_generation_config
```

Target artifacts must include:

```text
research_snapshot_id
target_definition_id
observation_window_start
observation_window_end
forward_horizon
evaluation_cutoff
price_basis_version
target_semantic_checksum
window_completeness_rule
```

Training datasets must include:

```text
feature_artifact_id
target_artifact_id
research_snapshot_id
training_dataset_checksum
leakage_boundary_statement
```

Feature and target artifacts should normally come from the same
`research_snapshot_id`. Any cross-snapshot join requires an explicit
compatibility declaration and documented reason. Silent cross-snapshot joins are
not allowed for canonical AI training.

## 25. Model Lineage

Future model artifacts should record:

```text
model_id
model_version
research_snapshot_id
feature_version
target_definition_id
training_window
validation_window
OOS_window
implementation_version
training_artifact_checksum
random_seed
```

`random_seed` is required when the model implementation uses randomness.

## 26. OOS Policy

OOS data must remain isolated until model selection is complete.

Forbidden:

```text
use OOS results for repeated tuning
  -> keep calling the same data "OOS"
```

If OOS results influence model or feature selection, the next evaluation round
must define a new OOS window or explicitly reclassify the used holdout data.

## 27. Migration Acceptance Test Design

Future migration acceptance tests should verify:

- Research DB immutable;
- Live write does not change Research DB SHA;
- Live Yahoo refresh does not change Research semantic checksum;
- Phase 7 reproduction from ResearchDataStore;
- Phase 3 reproduction from ResearchDataStore;
- backtest, replay, walk-forward, and OOS read ResearchDataStore for evidence
  runs;
- current scanner reads LiveDataStore;
- Frozen TWSE identity is maintained;
- PDF export remains DB-agnostic.

No migration tests are implemented in this phase.

## 28. PDF Export Relation

PDF Export should remain independent of database storage.

```text
Scan Result Snapshot
  -> coverage / candidate projection snapshot
  -> PDF export service
```

Future PDF metadata may include:

```text
scan_snapshot_id
research_evidence_snapshot_id
source_context
generated_at
```

But the PDF export service should continue to consume scan result snapshots and
should not read SQLite, run scanner, fetch prices, or rebuild technical
indicators.

## 29. Dashboard Relation

Dashboard panels should distinguish:

| Dashboard area | Future data source |
|---|---|
| Current market panel | LiveDataStore and in-session scan snapshot. |
| Research evidence panel | Released Research Snapshot via ResearchDataStore. |
| PDF export | Current scan snapshot, optionally annotated with snapshot IDs. |

The UI can still show research evidence beside live scan results, but
provenance labels and fingerprints must prevent users from confusing mutable
live cache with released research evidence.

## 30. Frozen TWSE Ownership

Frozen TWSE 218 belongs to versioned research universe metadata.

Live scanner workflows may reference:

```text
universe_id
universe_version
```

But mutable live data must not redefine or rebuild the frozen universe identity.

## 31. Current DB Transition Consideration

The current DB SHA
`69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7` and the old
canonical context remain an explicit decision point.

This phase does not decide which source becomes canonical. It defines the rule
that any future canonical research usage must cite an explicit snapshot ID,
source checksum, provider vintage, price basis version, dataset scope, and
semantic checksum.

## Phase 3 Decision

Recommended governance:

```text
Research evidence must be snapshot-addressed.
Released snapshots are immutable.
Live adjusted_close restatements require a new snapshot version before they affect research.
Long-Term Growth AI must start from a released Research Snapshot.
CURRENT_CANONICAL_DECISION = OPEN.
```
