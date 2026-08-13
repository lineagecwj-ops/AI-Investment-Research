# Research Snapshot Release Readiness Phase 5C

## 1. Candidate Status

Candidate A is the Composite Canonical Baseline validated in Phase 5B.

Current status:

```text
VALIDATED_CANDIDATE
not RELEASED
```

Release readiness result:

```text
BLOCKED_FOR_RELEASE
```

This phase is a release readiness review only. It does not create a Released
Research Snapshot, create a Research DB, create a Live DB, move data, run
migration, write to SQLite, fetch Yahoo data, execute scanner workflows, or
start Long-Term Growth.

## 2. Release Criteria

Candidate A can become `RELEASED` only after these criteria are complete:

- required metadata is present;
- formal manifest can be generated;
- source provenance is documented;
- adjusted-close recovery semantics are release-ready;
- provider vintage is documented;
- price basis is formalized;
- universe identity is bound to a versioned research universe;
- dataset scope is explicit;
- database, artifact, and semantic checksums are generated;
- Phase 7 reproduction artifact is available;
- Phase 3 reproduction artifact is available;
- Phase 4 evidence reproduction artifact is available;
- release approval is recorded.

Candidate A currently passes candidate validation, but does not yet satisfy the
release criteria.

## 3. Metadata Readiness

| Field | Status | Notes |
|---|---|---|
| `snapshot_id` | MISSING_BEFORE_RELEASE | Must be assigned by release process. |
| `snapshot_version` | MISSING_BEFORE_RELEASE | Must be assigned by release process. |
| `snapshot_role` | READY | Planned as logical role, not physical DB type. |
| `status` | READY | Current status is `VALIDATED_CANDIDATE`; future release would set `RELEASED`. |
| `created_at` | MISSING_BEFORE_RELEASE | Release timestamp not generated. |
| `created_by_process` | MISSING_BEFORE_RELEASE | Release process identity not recorded. |
| `source_database_path` | READY | Source backup paths are known. |
| `source_database_sha256` | READY | Source checksums were validated in Phase 5B. |
| `database_checksum` | MISSING_BEFORE_RELEASE | Formal candidate/released artifact checksum not generated. |
| `artifact_checksum` | MISSING_BEFORE_RELEASE | No release manifest or reproduction artifacts yet. |
| `semantic_checksum` | MISSING_BEFORE_RELEASE | Design exists, artifact not generated. |
| `row_count` | READY | Candidate logical keys: `473481`. |
| `symbol_count` | READY | Candidate symbols: `222`. |
| `universe_id` | MISSING_BEFORE_RELEASE | Needs formal released research universe identity. |
| `universe_version` | MISSING_BEFORE_RELEASE | Needs Frozen TWSE lineage or accepted scope linkage. |
| `price_data_start` | READY | `1980-12-12`. |
| `price_data_end` | READY | `2026-08-07`. |
| `research_window_start` | READY | `2018-01-01`. |
| `research_window_end` | READY | `2025-12-31`. |
| `price_basis_version` | MISSING_BEFORE_RELEASE | Currently inferred from existing pipeline. |
| `analysis_close_policy` | READY_WITH_GAP | Known as `adjusted_close if available else close`, but needs formal metadata. |
| `provider_name` | MISSING_BEFORE_RELEASE | Not formally recorded. |
| `provider_data_vintage` | MISSING_BEFORE_RELEASE | Required to distinguish old vs restated Yahoo vintage. |
| `loader_version` | MISSING_BEFORE_RELEASE | Not formally recorded. |
| `ingestion_process_version` | MISSING_BEFORE_RELEASE | Not formally recorded. |
| `dataset_scope` | READY_WITH_GAP | Scope is designed, but release manifest not generated. |
| `parent_snapshot_id` | NOT_APPLICABLE | First released snapshot candidate can have no parent. |
| deprecated linkage | NOT_APPLICABLE | No prior released snapshot is being deprecated in this phase. |
| `notes` | READY_WITH_GAP | Release limitations still need approval wording. |

## 4. Manifest Readiness

Manifest readiness:

```text
NOT_READY
```

The manifest design exists in Phase 5A and validation evidence exists in Phase
5B, but a formal release manifest has not been generated.

Manifest gaps:

- formal `snapshot_id`;
- formal `snapshot_version`;
- release timestamp and process identity;
- source lineage block;
- dataset scope block;
- provider vintage block;
- price basis block;
- database checksum;
- artifact checksum;
- semantic checksum;
- approval status.

## 5. Provenance Readiness

Provenance readiness:

```text
PASS_WITH_GAPS
```

Known provenance:

```text
base backup:
data/backups/stocks_before_adjusted_close_recovery_20260810T054845Z.db
sha256 = f70943ecbf132f0d1bd192e9d2811b31d3976b6c35bb8764cbabfe2124514470

recovery source:
data/backups/stocks_before_phase_6b_bulk_20260809T150444Z.db
sha256 = 1626dbd604927f2f00b1c7e5b6e1de621c7bf0008c05012c5654b77d0302c0be
```

Known reconstruction method:

```text
base backup
  + Phase 6B recovery semantics
  + five-symbol adjusted_close recovery
  + validation checks
```

Gap:

- reconstruction limitation statement must be approved before release;
- provider vintage for each source component is not yet formal.

## 6. Adjusted-Close Readiness

Adjusted-close recovery validation from Phase 5B:

```text
PASS for Candidate A recovery semantics
```

Evidence:

- five-symbol recovery scope validated for `0050.TW`, `2330.TW`, `2337.TW`,
  `2404.TW`, and `2454.TW`;
- differences between base and recovery are only in `adjusted_close`;
- non-adjusted research-field differences are `0`;
- recovery-source symbols outside the five-symbol scope have no differences;
- current live DB has `197642` existing-key `adjusted_close` differences versus
  logical Candidate A and must not be auto-promoted.

Release readiness:

```text
BLOCKED
```

Reason:

- provider vintage is still missing;
- release metadata cannot yet distinguish old Yahoo vintage from later Yahoo
  restatement vintage.

## 7. Price Basis Readiness

Price basis readiness:

```text
BLOCKED
```

Known:

```text
analysis_close = adjusted_close if available else close
```

Gap:

- `price_basis_version` is not formalized;
- OHLC semantics are not formally versioned;
- `adjusted_close` semantics are inferred from existing pipeline rather than
  release metadata.

## 8. Provider Vintage Readiness

Provider vintage readiness:

```text
BLOCKED
```

Missing required metadata:

```text
provider_name
provider_data_vintage
loader_version
ingestion_process_version
```

Current evidence is not sufficient to distinguish old Yahoo vintage from new
Yahoo restatement vintage at release standard.

## 9. Universe Readiness

Universe readiness:

```text
BLOCKED
```

Observed source universe tables exist:

```text
research_universes
research_universe_symbols
```

Observed records in source include:

- `0050`;
- `現在持有股`, with `5` symbols.

Release gap:

- Frozen TWSE 218 / research universe lineage must be bound to formal
  `universe_id` and `universe_version`;
- release manifest must prove the snapshot will not be changed by live universe
  refresh or editable user universes.

## 10. Dataset Scope Readiness

Dataset scope readiness:

```text
READY_WITH_GAPS
```

Release scope should be:

| Dataset | Release scope |
|---|---|
| `historical_prices` | included |
| universe metadata | included only after formal universe linkage |
| listing dates | included or linked by manifest if used for Phase 7 eligibility |
| `historical_financials` | excluded unless explicitly added to release scope |
| features | excluded |
| targets | excluded |
| outcomes | excluded as base snapshot data; derived artifacts must link separately |

Gap:

- formal manifest scope is not generated yet.

## 11. Checksum Readiness

Checksum readiness:

```text
BLOCKED
```

Known:

- source database SHA values are validated;
- current live DB SHA is validated;
- semantic checksum design exists.

Missing before release:

- formal released snapshot database checksum;
- formal manifest artifact checksum;
- formal semantic checksum artifact.

Important distinction:

```text
SQLite byte SHA != semantic identity
```

Both byte-level and semantic checksums must be present before release.

## 12. Date Semantics Readiness

Date semantics readiness:

```text
READY
```

Candidate A separates price coverage and research observation window:

```text
price_data_start = 1980-12-12
price_data_end = 2026-08-07
research_window_start = 2018-01-01
research_window_end = 2025-12-31
```

Future target evaluation windows should remain in target artifacts, not in the
base snapshot.

## 13. Research Validation Gates

### Phase 7 Gate

Status:

```text
REQUIRED_BEFORE_RELEASE
```

Candidate A release requires Phase 7 reproduction comparing:

```text
n
HIT
MISS
HHR
year breakdown
symbol breadth
semantic checksum
```

### Phase 3 Gate

Status:

```text
REQUIRED_BEFORE_RELEASE
```

Candidate A release requires Phase 3 reproduction comparing:

```text
Formal identity
Priority groups
Watch
classification counts
artifact checksum
```

### Phase 4 Gate

Status:

```text
REQUIRED_BEFORE_RELEASE
```

Candidate A release requires Phase 4 evidence reproduction confirming:

```text
dashboard evidence
Formal ordering
candidate grouping
```

## 14. Backtest, Replay, Walk-Forward, and OOS Gate

Status:

```text
NON_BLOCKER_FOR_INITIAL_RELEASE
REQUIRED_FOR_DOWNSTREAM_EVIDENCE_RUNS
```

After release, backtest, replay, walk-forward, and OOS artifacts must preserve:

```text
snapshot_id
checksum lineage
definition version
run config
OOS isolation rules
```

These gates are not required to release the first research validation snapshot,
but they are required before using Candidate A for those downstream evidence
workflows.

## 15. AI Readiness

AI readiness:

```text
NOT_READY_FOR_AI_TRAINING
```

Candidate A can become a research anchor after release, but Long-Term Growth AI
still needs:

- feature dataset;
- target dataset;
- training dataset checksum;
- model lineage;
- OOS split;
- provider vintage metadata;
- price basis metadata.

No feature dataset, target dataset, or model exists in this phase.

## 16. Blocker Classification

### Blockers

- provider vintage missing;
- price basis metadata not formalized;
- formal release manifest missing;
- formal semantic checksum artifact missing;
- artifact checksums missing;
- universe ID/version not formally bound to Frozen TWSE 218 / research lineage;
- Phase 7 reproduction artifact missing;
- Phase 3 reproduction artifact missing;
- Phase 4 evidence reproduction artifact missing;
- release approval process not completed.

### Non-Blockers

- Candidate A source checksum validation passed;
- Candidate A reconstruction validation passed;
- five-symbol adjusted-close recovery semantics passed;
- date semantics are ready;
- current live DB was proven not auto-promoted.

### Future Improvements

- create Candidate C as a provider-restatement-aware successor snapshot;
- add backtest/replay/walk-forward/OOS artifact lineage after release;
- add AI feature/target/model lineage only after a released snapshot exists.

## 17. Release Path

Future path after blockers are resolved:

```text
BLOCKED_FOR_RELEASE
  -> fill provider vintage metadata
  -> formalize price_basis_version
  -> bind universe_id and universe_version
  -> run Phase 7 reproduction
  -> run Phase 3 reproduction
  -> run Phase 4 evidence reproduction
  -> generate manifest
  -> generate database, artifact, and semantic checksums
  -> approval
  -> RELEASED
```

This phase does not perform any release step.

## 18. Release Decision

Candidate A Release Readiness:

```text
BLOCKED_FOR_RELEASE
```

Candidate A remains:

```text
VALIDATED_CANDIDATE
```

It is not a Released Research Snapshot.

## 19. Stop Gate

Phase 5C ends at review.

Do not proceed to:

- release Candidate A;
- create a Released Snapshot;
- create a Research DB;
- create a Live DB;
- migrate or copy data;
- write to SQLite;
- run scanner workflows;
- start Long-Term Growth.
