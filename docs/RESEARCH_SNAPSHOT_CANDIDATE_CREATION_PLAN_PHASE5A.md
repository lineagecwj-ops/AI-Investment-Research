# Research Snapshot Candidate Creation Plan Phase 5A

## 1. Candidate A Definition

Candidate A is the proposed first Research Snapshot Candidate for the composite
canonical baseline.

Definition:

```text
candidate_name = Candidate A Composite Canonical Baseline
source = f70943 backup + Phase 6B recovery semantics + logical reconstruction
keys = 473481
symbols = 222
status = CANDIDATE
```

Candidate A is not `RELEASED`. It cannot be used as the canonical Research
Snapshot until the future validation and approval gates pass.

Candidate A is also not equivalent to the `f70943` backup file alone. It is a
logical reconstruction that combines the backup, recovery semantics, and
validation evidence.

## 2. Reconstruction Method

Candidate A must document its reconstruction method before it can become a
formal candidate.

Required reconstruction description:

```text
base backup
  + Phase 6B recovery semantics
  + five-symbol recovery semantics
  + validation checks
  + manifest metadata
  -> Research Snapshot Candidate
```

The reconstruction record must make clear:

- which source components were used;
- which recovery semantics were applied;
- which five-symbol Phase 6B corrections were expected;
- which rows or keys are included in the logical baseline;
- which checksum and semantic checksum were produced;
- which limitations remain unresolved.

This avoids future confusion between a physical backup artifact and the logical
Research Snapshot Candidate.

## 3. Snapshot Role

Candidate A should use a logical `snapshot_role`, not a physical database type.

Recommended initial role:

```text
snapshot_role = research_validation_candidate
```

The role means Candidate A is intended to anchor reproducible research
validation first. The same physical snapshot may later support backtest, replay,
OOS, production reference, or AI lineage only if derived artifacts cite their
own definitions and checksums.

## 4. Candidate Manifest Design

This phase designs the manifest only. It does not create an actual manifest
artifact.

Candidate A manifest should include:

```text
metadata:
  snapshot_id
  snapshot_version
  snapshot_role
  status
  created_at
  created_by_process

source:
  source_components
  source_database_checksums
  reconstruction_method
  recovery_semantics_version

universe:
  universe_id
  universe_version
  symbol_count

price:
  price_data_start
  price_data_end
  research_window_start
  research_window_end
  price_basis_version
  analysis_close_policy

provider:
  provider_name
  provider_data_vintage
  loader_version
  ingestion_process_version

datasets:
  dataset_scope

checksums:
  database_checksum
  artifact_checksum
  semantic_checksum

lineage:
  parent_snapshot_id
  derived_artifacts

notes:
  known_limitations
  validation_evidence
  approval_status
```

Conceptual `dataset_scope` entries:

```text
historical_prices
research_universe_metadata
listing_dates
historical_financials explicitly included or excluded
features explicitly excluded for base candidate
targets explicitly excluded for base candidate
outcomes explicitly excluded unless generated as derived artifacts
```

## 5. Validation Checklist

Candidate A validation checklist:

| Check | Required evidence |
|---|---|
| Source availability | Source components can be located and identified. |
| Source checksum verification | Backup and reconstruction inputs have recorded checksums. |
| Symbol count | Expected `222` symbols verified. |
| Row/key count | Expected `473481` keys verified. |
| Duplicate check | Duplicate symbol/date groups are `0`. |
| Integrity check | SQLite integrity or equivalent source integrity is `ok`. |
| Universe validation | Universe ID, version, and membership are recorded. |
| Price basis validation | OHLC and `adjusted_close` semantics are documented. |
| Adjusted-close vintage validation | No mixed or partial adjusted-close vintage is accepted. |
| Research window validation | Observation window and price coverage are separated. |
| Artifact checksum | Manifest and derived artifacts have file checksums. |
| Semantic checksum | Research-relevant logical content checksum is produced. |

Every validation result must be recorded in the future manifest or release
evidence.

## 6. Adjusted-Close Validation Plan

Candidate A validation must specifically confirm:

- five-symbol Phase 6B recovery semantics were applied;
- no mixed `adjusted_close` vintage is present inside the candidate;
- no partial rewrite is treated as the same baseline;
- provider vintage is documented as far as recoverable;
- `analysis_close_policy` is recorded.

If adjusted-close vintage consistency cannot be proven, Candidate A may still be
kept as a documented candidate, but it must not be promoted to `RELEASED`
without an explicit limitation decision and approval.

## 7. Phase 7 Reproduction Plan

Future Phase 7 validation flow:

```text
Candidate Snapshot
  -> Phase 7 threshold validation
  -> reproduction comparison
```

Comparison fields:

```text
n
HIT
MISS
HHR
year summaries
symbol summaries
artifact checksum
semantic checksum
```

Acceptance rule:

- reproduced Phase 7 output must match the accepted baseline exactly or produce
  a documented, approved delta.

This phase does not run Phase 7.

## 8. Phase 3 Reproduction Plan

Future Phase 3 validation flow:

```text
Candidate Snapshot
  -> Candidate Display Research
  -> reproduction comparison
```

Validation fields:

```text
classification counts
formal identity
priority group identity
symbol identity
candidate display semantic checksum
artifact checksum
```

Acceptance rule:

- Candidate Display Research must reproduce the accepted classification and
  symbol identities, or any delta must be explained and approved.

This phase does not run Phase 3 research.

## 9. Phase 4 Reproduction Plan

Future Phase 4 validation flow:

```text
Candidate Snapshot
  -> Experimental Candidate View evidence
  -> reproduction comparison
```

Validation fields:

```text
Formal identity
Priority A identity
Priority B identity
Watch identity
Other groups
artifact consistency
semantic checksum
```

Acceptance rule:

- Experimental Candidate View evidence must remain reproducible under the same
  snapshot ID and checksum lineage.

This phase does not run Phase 4 evidence.

## 10. Backtest, Replay, Walk-Forward, and OOS Plan

Future validation flow:

```text
Candidate Snapshot
  -> Backtest
  -> Replay
  -> Walk-Forward
  -> OOS
```

Each derived artifact must record:

```text
research_snapshot_id
snapshot_version
database_checksum
semantic_checksum
artifact_checksum
definition_version
run_config
```

Acceptance rule:

- evidence runs must use the same `research_snapshot_id`;
- no evidence run may silently use LiveDataStore;
- any cross-snapshot comparison must be explicitly labeled as such.

This phase does not run backtest, replay, walk-forward, or OOS.

## 11. AI Future Compatibility

Candidate A can support future AI lineage only as a research baseline after it
passes release criteria. It should not start Long-Term Growth implementation in
this phase.

Future AI lineage:

```text
Candidate Snapshot
  -> Feature Dataset
  -> Target Dataset
  -> Training Dataset
  -> Model
```

Each layer must preserve:

```text
research_snapshot_id
definition_version
semantic_checksum
artifact_checksum
lineage metadata
```

Candidate A may be useful as an initial reproducibility anchor. Candidate C is
expected to be the stronger long-term AI input if it is built with provider
restatement awareness and full snapshot metadata.

## 12. Release Criteria

Candidate A can move from `CANDIDATE` to `RELEASED` only when all conditions
pass:

- manifest complete;
- all validation checks pass;
- checksums generated and recorded;
- Phase 7 reproducibility verified;
- Phase 3 reproducibility verified;
- Phase 4 evidence reproducibility verified;
- backtest, replay, walk-forward, and OOS lineage plan accepted;
- adjusted-close vintage limitations resolved or explicitly approved;
- derived artifact lineage recorded;
- release approval completed.

Release is a future action. This phase does not perform release.

## 13. Failure Handling

If Candidate A validation fails:

```text
do not modify Candidate A in place
  -> mark REJECTED or keep as failed CANDIDATE
  -> record failure reason
  -> create corrected candidate version later
```

Failure examples:

- source checksum mismatch;
- symbol or row/key count mismatch;
- duplicate groups present;
- integrity check failure;
- adjusted-close vintage inconsistency;
- Phase 7 reproduction mismatch;
- Phase 3 or Phase 4 semantic mismatch;
- missing manifest fields.

The corrected version must have a new candidate ID and lineage link.

## 14. Candidate A and Candidate C Relationship

Candidate A and Candidate C are not replacements for each other.

Candidate A:

- fastest path to a first reproducible Research Snapshot Candidate;
- best aligned with existing research evidence;
- may have older coverage and reconstructed provider metadata limitations.

Candidate C:

- future corrected provider-restatement-aware snapshot;
- better long-term fit for Long-Term Growth AI;
- requires full release-gate workflow before use.

Relationship rule:

```text
Candidate A can become first released research baseline.
Candidate C can become a later corrected or expanded released snapshot.
Neither silently overwrites the other.
```

## 15. Current Live DB Status

Current live DB:

```text
sha256 = 69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7
```

Status:

```text
NOT automatically promoted
```

The current live DB may become future candidate source material only through the
same manifest, provider-vintage, price-basis, adjusted-close, semantic checksum,
and reproduction gates.

## 16. Stop Gate

Phase 5A ends at review.

Do not proceed to:

- creating a snapshot file;
- creating a manifest artifact;
- copying or migrating data;
- writing to SQLite;
- running scanner workflows;
- releasing Candidate A;
- starting Long-Term Growth.
