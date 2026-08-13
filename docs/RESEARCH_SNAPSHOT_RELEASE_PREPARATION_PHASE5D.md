# Research Snapshot Release Preparation Phase 5D

## 1. Candidate A Identity

Candidate A is the Composite Canonical Baseline validated in Phase 5B and
reviewed for release readiness in Phase 5C.

Current preparation status:

```text
RELEASE_PREPARATION_COMPLETE
RELEASE_READY_CANDIDATE_PENDING_REPRODUCTION_GATES
not RELEASED
```

Candidate A source:

```text
base backup:
data/backups/stocks_before_adjusted_close_recovery_20260810T054845Z.db
sha256 = f70943ecbf132f0d1bd192e9d2811b31d3976b6c35bb8764cbabfe2124514470

recovery source:
data/backups/stocks_before_phase_6b_bulk_20260809T150444Z.db
sha256 = 1626dbd604927f2f00b1c7e5b6e1de621c7bf0008c05012c5654b77d0302c0be
```

Logical reconstruction:

```text
base backup
  + Phase 6B recovery semantics
  + five-symbol adjusted_close recovery
  + validation checks
```

Candidate A is not a single backup file and is not the current live DB.

## 2. Future Snapshot ID

Future snapshot ID design:

```text
snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
snapshot_version = v1
snapshot_role = research_validation_candidate
```

Properties:

- deterministic;
- human-readable;
- versionable;
- tied to Candidate A and its 2018 to 2025 research validation role;
- not tied to one physical DB purpose.

If Candidate A is corrected before release, the corrected candidate must receive
a new version and lineage link.

## 3. Release Metadata

Prepared release metadata contract:

```text
metadata:
  snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
  snapshot_version = v1
  snapshot_role = research_validation_candidate
  status = RELEASE_READY_CANDIDATE_PENDING_REPRODUCTION_GATES
  created_at = release-time UTC timestamp, not generated in Phase 5D
  created_by_process = future release process, not generated in Phase 5D

source:
  source_components = base backup + recovery source
  source_checksums = f70943... and 1626...
  reconstruction_method = base backup + Phase 6B recovery semantics + five-symbol adjusted_close recovery

database:
  database_checksum = future released artifact checksum, not generated in Phase 5D
  row_count = 473481
  symbol_count = 222
  duplicate_count = 0
  integrity = ok

universe:
  universe_id = candidate_a_price_universe_222_v1
  universe_version = candidate_a_composite_price_universe_2026_08_07_v1

price:
  price_basis_version = price_basis_candidate_a_adjusted_close_recovery_v1
  analysis_close_policy = adjusted_close if available else close
  price_data_start = 1980-12-12
  price_data_end = 2026-08-07
  research_window_start = 2018-01-01
  research_window_end = 2025-12-31

provider:
  provider_name = Yahoo Finance via existing historical price pipeline, inferred from project source history
  provider_data_vintage = composite pre-current-live-restatement vintage with Phase 6B five-symbol recovery
  loader_version = repository baseline 766571828b730faf8ee5ede8f22e37b9177598bf, historical price pipeline semantics
  ingestion_process_version = phase_6b_adjusted_close_recovery_semantics_v1

datasets:
  dataset_scope = base price snapshot scope

checksums:
  artifact_checksum = future manifest/report checksum, not generated in Phase 5D
  semantic_checksum = future semantic checksum, not generated in Phase 5D

lineage:
  parent_snapshot_id = none for first release candidate
  derived_artifacts = Phase 7, Phase 3, Phase 4, and downstream artifacts after reproduction gates

notes:
  release limitation statement required
```

## 4. Provider Vintage Decision

Candidate A must not remain `MISSING_FOR_RELEASE`. The release-preparation
decision is to use an explicit limited provider-vintage statement rather than
pretending exact provider-side vintage is recoverable.

Prepared provider block:

```text
provider_name = Yahoo Finance via existing project historical price pipeline
provider_data_vintage = composite Candidate A vintage:
  - base backup captured before adjusted-close recovery on 2026-08-10T05:48:45Z
  - recovery source captured before Phase 6B bulk work on 2026-08-09T15:04:44Z
  - five-symbol adjusted_close recovery semantics applied from recovery source
loader_version = repository baseline 766571828b730faf8ee5ede8f22e37b9177598bf
ingestion_process_version = phase_6b_adjusted_close_recovery_semantics_v1
```

Release limitation statement:

```text
Candidate A provider-side Yahoo release identity is not exactly recoverable.
Candidate A is released, if approved, as a reconstructed research baseline with
documented source backups, recovery semantics, source checksums, and reproduction
evidence. It must not be treated as a generic Yahoo latest vintage.
```

This statement prevents Candidate A from being confused with the current live DB
or a future provider-restatement-aware Candidate C.

## 5. Price Basis Decision

Prepared price basis:

```text
price_basis_version = price_basis_candidate_a_adjusted_close_recovery_v1
open_basis = stored historical_prices.open from Candidate A logical reconstruction
high_basis = stored historical_prices.high from Candidate A logical reconstruction
low_basis = stored historical_prices.low from Candidate A logical reconstruction
close_basis = stored historical_prices.close from Candidate A logical reconstruction
adjusted_close_basis = stored historical_prices.adjusted_close after five-symbol recovery semantics
analysis_close_policy = adjusted_close if available else close
```

This fixes snapshot semantics only. It does not change existing technical
formula behavior.

## 6. Universe Binding

Candidate A has two related but separate universe concepts that must not be
mixed.

Candidate A price universe:

```text
universe_id = candidate_a_price_universe_222_v1
universe_version = candidate_a_composite_price_universe_2026_08_07_v1
scope = 222 symbols present in Candidate A historical_prices
```

Frozen TWSE 218 research universe:

```text
universe_id = frozen_twse_research_universe_2026_08_09
universe_version = 2026-08-current-etf-constituent-v1
scope = 218 TWSE common-stock symbols, excluding 0050.TW and TPEx symbols
```

Release rule:

- Candidate A base snapshot binds its price universe explicitly.
- Phase 7 and other research artifacts may bind the Frozen TWSE 218 universe as
  a derived research universe.
- The 222-symbol price universe and the 218-symbol Frozen TWSE research universe
  must not be described as the same universe.
- Live universe refresh or editable user universes must not mutate either
  identity.

## 7. Dataset Scope

Candidate A base snapshot scope:

| Dataset | Scope decision |
|---|---|
| `historical_prices` | included |
| Candidate A price universe metadata | included as release metadata |
| Frozen TWSE 218 universe metadata | linked by derived Phase 7/research artifact, not the base price universe |
| listing dates | linked by derived Phase 7/research artifact when used |
| `historical_financials` | excluded from base snapshot semantics |
| `stocks` | excluded from base snapshot semantics |
| `historical_price_fetch_state` | excluded from research semantics; live/cache metadata only |
| features | excluded |
| targets | excluded |
| outcomes | excluded from base snapshot; derived artifacts only |

## 8. Manifest Structure

Future manifest structure:

```text
manifest:
  metadata
  source
  reconstruction
  database
  universe
  price
  provider
  datasets
  checksums
  lineage
  release_limitations
  reproduction_gates
  approval
```

The manifest must include artifact checksums for:

- the manifest itself;
- Candidate A validation report;
- release readiness report;
- Phase 7 reproduction report;
- Phase 3 reproduction report;
- Phase 4 reproduction report;
- any downstream backtest, replay, walk-forward, OOS, or AI artifact that cites
  this snapshot.

No manifest artifact is created in Phase 5D.

## 9. Semantic Checksum Design

Candidate A semantic checksum should normalize and include:

```text
research keys:
  symbol
  trading_date

price fields:
  open
  high
  low
  close
  adjusted_close
  volume
  dividends
  stock_splits
  currency

metadata:
  candidate_a_price_universe_222_v1
  price_basis_candidate_a_adjusted_close_recovery_v1
  price_data_start
  price_data_end
  research_window_start
  research_window_end
  provider_data_vintage
  reconstruction_method
```

Semantic checksum is not the same as SQLite byte SHA. SQLite byte SHA proves a
physical artifact; semantic checksum proves the normalized research meaning.

No semantic checksum artifact is generated in Phase 5D.

## 10. Artifact Checksum Design

Future release artifacts must each have artifact checksums:

```text
manifest
validation report
release readiness report
Phase 7 reproduction report
Phase 3 reproduction report
Phase 4 reproduction report
approval record
```

Downstream artifacts must add their own checksums when created:

```text
backtest report
replay report
walk-forward report
OOS report
feature dataset
target dataset
training dataset
model artifact
```

No artifact checksum is generated in Phase 5D.

## 11. Reproduction Release Gates

Candidate A release requires the following gates before `RELEASED`:

```text
Gate 1: Phase 7 reproduction
Gate 2: Phase 3 reproduction
Gate 3: Phase 4 reproduction
Gate 4: Backtest / Replay / OOS lineage validation
```

Gate 4 is required before Candidate A can be used for those downstream evidence
workflows. It does not need to block release of a research-validation-only
snapshot if the release approval explicitly scopes Candidate A to Phase 7 / Phase
3 / Phase 4 validation.

No reproduction gate is executed in Phase 5D.

## 12. Phase 7 Gate

Phase 7 reproduction must compare:

```text
threshold
n
HIT
MISS
HHR
year breakdown
symbol breadth
artifact checksum
semantic checksum
```

Phase 7 must cite:

```text
snapshot_id
snapshot_version
candidate_a_price_universe_222_v1
frozen_twse_research_universe_2026_08_09
2026-08-current-etf-constituent-v1
```

## 13. Phase 3 Gate

Phase 3 reproduction must compare:

```text
Formal V1 identity
Priority A identity
Priority B identity
Watch identity
classification counts
artifact checksum
semantic checksum
```

Phase 3 must preserve Production V1 and V1.1 semantics. Candidate A release
preparation does not alter classification, ranking, or recommendation logic.

## 14. Phase 4 Gate

Phase 4 reproduction must compare:

```text
Dashboard candidate groups
Formal order
projection consistency
artifact checksum
semantic checksum
```

Dashboard evidence must distinguish the released Research Snapshot from live
scanner output.

## 15. Backtest, Replay, Walk-Forward, and OOS Gate

All downstream outputs must preserve:

```text
snapshot_id
snapshot_version
snapshot checksum
artifact lineage
definition version
run config
OOS isolation policy
```

Cross-snapshot joins are not allowed unless explicitly documented as a special
study.

## 16. Release Checklist

Release checklist:

```text
[x] Candidate A identity defined
[x] Future snapshot ID designed
[x] source components identified
[x] source checksums validated
[x] reconstruction method documented
[x] provider vintage limitation statement defined
[x] price basis version defined
[x] universe binding separated between Candidate A price universe and Frozen TWSE 218
[x] dataset scope defined
[ ] formal manifest generated
[ ] semantic checksum generated
[ ] artifact checksums generated
[ ] Phase 7 reproduced
[ ] Phase 3 reproduced
[ ] Phase 4 reproduced
[ ] release approval completed
```

Unchecked items are intentionally not completed in Phase 5D.

## 17. Release Status Model

Allowed release statuses:

```text
VALIDATED_CANDIDATE
RELEASE_READY_CANDIDATE
RELEASED
DEPRECATED
REJECTED
```

Candidate A after Phase 5D:

```text
RELEASE_READY_CANDIDATE_PENDING_REPRODUCTION_GATES
```

This is a preparation status, not a release status. It means release metadata
decisions are prepared, while reproduction gates, formal checksums, manifest,
and approval remain incomplete.

## 18. Current Live DB Policy

Current live DB:

```text
sha256 = 69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7
```

Policy:

```text
NOT Research Snapshot
NOT automatically promoted
LiveDataStore material only unless future release gates approve it as a separate candidate
```

The current live DB is not Candidate A and must not inherit Candidate A release
lineage.

## 19. PDF Export Relation

PDF Export remains:

```text
Scan Result Snapshot
  -> PDF
```

Future PDF metadata may include:

```text
research_snapshot_id
research_snapshot_version
research_snapshot_checksum
```

PDF Export must not directly depend on ResearchDataStore or LiveDataStore, and
must not read SQLite during export.

## 20. Stop Gate

Phase 5D ends at review.

Do not proceed to:

- release Candidate A;
- create a manifest artifact;
- generate checksums;
- create a Research DB;
- create a Live DB;
- migrate or copy data;
- write to SQLite;
- run scanner workflows;
- start Long-Term Growth.
