# Corrected Research Store Runtime Cutover Phase 6E-E

Phase 6E-E cuts the runtime ResearchDataStore target from the known faulty
physical materialization to the corrected materialization v2. The logical
Research Snapshot remains unchanged.

## Identity

- Logical snapshot ID:
  `research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1`
- Logical snapshot version: `v1`
- Active physical materialization version: `v2`
- Canonical semantic checksum:
  `a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91`

## Runtime Paths

- Active Research Store:
  `data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_v2.db`
- Active Research materialization manifest:
  `data/research/manifests/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_v2_manifest.json`
- Live Store:
  `data/live/stocks_live.db`
- Legacy rollback/audit DB:
  `data/stocks.db`

## Faulty Store Policy

The faulty physical Research Store remains preserved for provenance evidence:

`data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db`

It must not be selected as the active runtime ResearchDataStore target. Runtime
verification rejects it because it is not materialization version `v2`.

## Runtime Guards

ResearchDataStore verifies:

- logical snapshot ID;
- logical snapshot version `v1`;
- materialization version `v2`;
- canonical semantic checksum;
- manifest materialized and recomputed semantic checksums;
- corrected DB SHA;
- DB metadata identity;
- read-only SQLite access with `mode=ro` and `PRAGMA query_only=ON`.

If verification fails, research workflows must fail closed. Rollback must not
silently fallback to the faulty Research Store, Live Store, or Legacy DB.

## Fingerprints

| Store | SHA-256 |
| --- | --- |
| Legacy | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` |
| Live | `e9c04141fd247876f61fc7e982c688aaf8c802b646a30442aa0fd54f71789e26` |
| Faulty Research | `6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073` |
| Corrected Research | `3417b34a11660e672d75c5879d0d8f9e177c574b603b540274bad7acb2215de0` |

## Validation Evidence

Phase 6E-C established corrected materialization reproduction:

- Phase 3 checksum:
  `79f641199e31166b6c2e13782766fa0b404058b06bb99fdd4a91e7c37be41736`
- Phase 3 counts:
  Formal V1 `13`, Priority A `8`, Priority B `12`, Watch `12`,
  Other 4/5 `5`, 3/5 `49`, Below `119`
- Phase 7:
  - `1.00`: `2377 / 1991 / 386 / 83.76%`
  - `1.10`: `2072 / 1768 / 304 / 85.33%`
  - `1.20`: `1821 / 1567 / 254 / 86.05%`

Phase 6E-E revalidates those paths through default runtime ResearchDataStore
resolution after cutover.

## Scope

This cutover does not change Production V1, V1.1, technical formulas, ranking,
ordering, Phase 3 semantics, Phase 7 outcome semantics, Live Store data, Legacy
DB, PDF Export implementation, or Long-Term Growth work.
