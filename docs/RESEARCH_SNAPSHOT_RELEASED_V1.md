# Research Snapshot Released V1

## 1. Snapshot Identity

Released Research Snapshot:

```text
snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
snapshot_version = v1
snapshot_role = research_validation_reference
status = RELEASED
manifest = docs/research_snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json
```

This release creates metadata and a release artifact only. It does not create a
Research DB, create a Live DB, move data, migrate data, write to SQLite, fetch
Yahoo data, execute scanner workflows, change Dashboard behavior, change PDF
Export behavior, or start Long-Term Growth work.

## 2. Release Decision

Phase 5E-2 approved Candidate A for release:

```text
Decision = RELEASE
Final status = RELEASED
```

Phase 6A materializes that decision as a manifest artifact. The release status
is metadata status, not a physical database type.

## 3. Source Lineage

Candidate A is a logical reconstruction from two source components:

```text
base backup:
data/backups/stocks_before_adjusted_close_recovery_20260810T054845Z.db
sha256 = f70943ecbf132f0d1bd192e9d2811b31d3976b6c35bb8764cbabfe2124514470

recovery source:
data/backups/stocks_before_phase_6b_bulk_20260809T150444Z.db
sha256 = 1626dbd604927f2f00b1c7e5b6e1de621c7bf0008c05012c5654b77d0302c0be
```

Reconstruction method:

```text
base backup
  + Phase 6B recovery semantics
  + five-symbol adjusted_close recovery
  + validation checks
```

Candidate A is not the current live DB and is not a single newly created SQLite
file in Phase 6A.

## 4. Validation Evidence

Phase 5E-1 reproduction artifact:

```text
/tmp/phase5e1_candidate_a_reproduction_validation.json
sha256 = fd2ab85001ccbe25d856634a49db14488ff06fa70516cf35087c225a129a2064
```

Validation gates:

| Gate | Result | Differences |
|---|---:|---:|
| Phase 7 reproduction | PASS | 0 |
| Phase 3 reproduction | PASS | 0 |
| Phase 4 reproduction | PASS | 0 |

Phase 3 reproduced semantic checksum:

```text
79f641199e31166b6c2e13782766fa0b404058b06bb99fdd4a91e7c37be41736
```

## 5. Checksums

Database checksum references:

```text
base backup sha256 = f70943ecbf132f0d1bd192e9d2811b31d3976b6c35bb8764cbabfe2124514470
recovery source sha256 = 1626dbd604927f2f00b1c7e5b6e1de621c7bf0008c05012c5654b77d0302c0be
```

Semantic checksum:

```text
a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

The database SHA values prove source component byte identity. The semantic
checksum proves normalized research meaning. These must not be mixed.

## 6. Dataset Scope

Included:

- `historical_prices`;
- Candidate A price universe metadata;
- Frozen TWSE 218 research universe metadata reference.

Excluded:

- `stocks`;
- `historical_financials`;
- `historical_price_fetch_state`;
- features;
- targets;
- outcomes;
- scanner outputs;
- PDF exports;
- AI model artifacts.

Coverage:

```text
logical_key_count = 473481
symbol_count = 222
price_data_start = 1980-12-12
price_data_end = 2026-08-07
research_window_start = 2018-01-01
research_window_end = 2025-12-31
```

## 7. Limitations

Provider limitation:

```text
Yahoo provider-side release identity is not fully reconstructable.
```

Universe limitation:

```text
Frozen TWSE 218 is a 2026 current ETF constituent-derived research universe,
not a 2018 to 2025 point-in-time universe.
```

Research limitation:

```text
Every future backtest, replay, OOS, and AI artifact must carry its own snapshot
reference, checksum, lineage, and validation evidence.
```

## 8. Usage Rules

This Research Snapshot may be used as an explicit released reference for:

- Phase 7;
- Phase 3;
- Phase 4;
- Backtest;
- Replay;
- OOS;
- AI future datasets.

Downstream artifacts must cite:

```text
research_snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
research_snapshot_version = v1
semantic_checksum = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

## 9. Forbidden Usage

Forbidden:

- live refresh;
- Yahoo overwrite;
- silent mutation;
- implicit promotion of `data/stocks.db`;
- treating current live DB as this Research Snapshot;
- direct PDF Export database reads;
- changing scanner qualification, ranking, recommendations, persistence, or AI
  semantics without a separate authorized phase.

PDF Export relation:

```text
Scan Result Snapshot -> PDF
```

Future PDF Export may reference `research_snapshot_id`, but PDF Export should
not directly read the Research Snapshot DB in this phase.
