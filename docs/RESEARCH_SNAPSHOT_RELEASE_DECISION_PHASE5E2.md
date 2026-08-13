# Research Snapshot Release Decision Phase 5E-2

## 1. Candidate Identity

Candidate A:

```text
snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
snapshot_version = v1
snapshot_role = research_validation_candidate
decision_status = RELEASED_DECISION_ONLY
materialized_status = NOT_CREATED_IN_THIS_PHASE
```

This is a release decision review. It does not create a Released Snapshot file,
Research DB, Live DB, manifest file, migration, or database write.

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

## 2. Criteria Checklist

| Criterion | Decision | Evidence |
|---|---|---|
| Source provenance | PASS | Source components and checksums are documented. |
| Reconstruction method | PASS | Candidate A is defined as logical reconstruction, not a single backup file. |
| Row/symbol reconciliation | PASS | `473481` keys and `222` symbols. |
| Integrity | PASS | Candidate source integrity `ok`, duplicates `0`. |
| Adjusted-close semantics | PASS | Five-symbol recovery validated; other research fields unchanged. |
| Price basis version | PASS | `price_basis_candidate_a_adjusted_close_recovery_v1`. |
| Provider vintage | PASS_WITH_LIMITATION | Provider-side Yahoo release identity is not exactly recoverable. |
| Universe binding | PASS | Candidate A price universe is separated from Frozen TWSE 218 research universe. |
| Dataset scope | PASS | Base snapshot scope is `historical_prices`; derived artifacts are separate. |
| Date semantics | PASS | Price data range and research window are separated. |
| Semantic checksum | PASS | `a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91`. |
| Artifact checksum | PASS_WITH_LIMITATION | Phase 5E-1 validation artifact checksum exists in `/tmp`; no formal manifest file is created in this phase. |
| Phase 7 reproduction | PASS | Exact match. |
| Phase 3 reproduction | PASS | Counts, identities, and semantic checksum match. |
| Phase 4 reproduction | PASS | Projection groups and ordering match Phase 3 evidence. |
| Backtest lineage readiness | PASS_WITH_LIMITATION | Ready as source; downstream artifact lineage still required when run. |
| Replay lineage readiness | PASS_WITH_LIMITATION | Ready as source; downstream artifact lineage still required when run. |
| OOS lineage readiness | PASS_WITH_LIMITATION | Ready as source; OOS split and tuning policy required when run. |
| AI lineage readiness | PASS_WITH_LIMITATION | Future AI anchor only; no feature, target, or model artifact exists. |

## 3. Metadata Readiness

Prepared metadata is sufficient for release decision:

```text
snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
snapshot_version = v1
snapshot_role = research_validation_candidate
status = RELEASED_DECISION_ONLY
source_components = base backup + recovery source
source_checksums = f70943... + 1626...
row_count = 473481
symbol_count = 222
duplicate_count = 0
integrity = ok
price_data_start = 1980-12-12
price_data_end = 2026-08-07
research_window_start = 2018-01-01
research_window_end = 2025-12-31
price_basis_version = price_basis_candidate_a_adjusted_close_recovery_v1
analysis_close_policy = adjusted_close if available else close
semantic_checksum = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

Formal manifest fields such as `created_at`, `created_by_process`, and manifest
artifact checksum must be generated only in a later phase that is allowed to
create release artifacts.

## 4. Provider Vintage Decision

Decision:

```text
PASS_WITH_LIMITATION
```

Accepted limitation:

```text
Candidate A provider-side Yahoo release identity is not exactly recoverable.
Candidate A is accepted as a reconstructed research baseline with documented
source backups, recovery semantics, source checksums, semantic checksum, and
reproduction evidence. It must not be treated as Yahoo latest vintage.
```

Future improvement:

- Candidate C should become a provider-restatement-aware successor snapshot
  with explicit provider vintage metadata.

## 5. Price Basis Decision

Decision:

```text
PASS
```

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

This does not change technical formulas.

## 6. Universe Decision

Decision:

```text
PASS
```

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

The two universes are linked but not identical.

## 7. Reproduction Summary

Phase 5E-1 validation artifact:

```text
/tmp/phase5e1_candidate_a_reproduction_validation.json
artifact_sha256 = fd2ab85001ccbe25d856634a49db14488ff06fa70516cf35087c225a129a2064
```

Candidate semantic checksum:

```text
a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

Phase 7:

```text
decision = PASS
differences = none
```

Phase 3:

```text
decision = PASS
differences = none
semantic_checksum = 79f641199e31166b6c2e13782766fa0b404058b06bb99fdd4a91e7c37be41736
```

Phase 4:

```text
decision = PASS
differences = none
```

## 8. Current Live DB Policy

Current live DB:

```text
sha256 = 69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7
```

Policy:

```text
LiveDataStore candidate
NOT Research Snapshot
NOT automatically promoted
```

The current live DB is not Candidate A and does not inherit Candidate A release
lineage.

## 9. Accepted Limitations

Candidate A is released by decision with these limitations:

- provider-side Yahoo release identity is reconstructed, not exact;
- Frozen TWSE 218 is a 2026 current ETF constituent-derived research universe,
  not a 2018 to 2025 point-in-time universe;
- Candidate A price universe has `222` symbols, while Frozen TWSE 218 research
  universe has `218` symbols;
- Candidate A can anchor Phase 7, Phase 3, and Phase 4 evidence;
- downstream backtest, replay, walk-forward, OOS, and AI artifacts still need
  their own snapshot ID, checksums, lineage, and validation.

These limitations must be visible in future manifests and reports.

## 10. Release Decision

Decision:

```text
RELEASE
```

Final decision status:

```text
RELEASED
```

Implementation status:

```text
NO_RELEASED_SNAPSHOT_FILE_CREATED
NO_MANIFEST_FILE_CREATED
NO_RESEARCH_DB_CREATED
NO_DB_WRITE
```

Interpretation:

Candidate A is approved as the first Released Research Snapshot decision record,
under the accepted limitations above. Physical release artifacts are not created
in this phase because the phase explicitly prohibits creating a Released
Snapshot or manifest file.

## 11. Future Version Policy

Any next snapshot version must:

- use a new `snapshot_id` or new `snapshot_version`;
- generate a new checksum;
- run a new validation;
- preserve Candidate A `v1` lineage;
- never overwrite Candidate A `v1`.

Candidate C should be treated as a future corrected or provider-restatement-aware
successor snapshot, not an in-place replacement.

## 12. Stop Gate

Phase 5E-2 ends at review.

Do not proceed to:

- create a Released Snapshot file;
- create a manifest file;
- create a Research DB;
- create a Live DB;
- migrate or copy data;
- write to SQLite;
- run scanner workflows;
- start Long-Term Growth.
