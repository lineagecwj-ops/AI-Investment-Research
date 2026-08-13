# Research Store Materialization Phase 6D-3

## 1. Materialization Scope

Phase 6D-3 materializes Released Research Snapshot v1 as a Research Store Candidate.

Allowed and performed:

- Created `data/research/`.
- Created `data/research/snapshots/`.
- Created `data/research/manifests/`.
- Created a Research Store Candidate SQLite DB.
- Created a Research Store Candidate materialization manifest.
- Added materialization service and validation tests.

Not performed:

- No `data/stocks.db` modification.
- No `data/live/` creation.
- No Live cutover.
- No scanner path switch.
- No dashboard switch.
- No PDF modification.
- No Production V1 or V1.1 modification.
- No Yahoo or external network fetch.
- No Long-Term Growth implementation.
- No commit or push.

## 2. Source Snapshot

Released source snapshot:

```text
snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
snapshot_version = v1
status = RELEASED
semantic_checksum = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

Source manifest:

```text
docs/research_snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json
```

Source components:

| Source | Role | SHA-256 |
| --- | --- | --- |
| `data/backups/stocks_before_adjusted_close_recovery_20260810T054845Z.db` | base backup | `f70943ecbf132f0d1bd192e9d2811b31d3976b6c35bb8764cbabfe2124514470` |
| `data/backups/stocks_before_phase_6b_bulk_20260809T150444Z.db` | recovery source | `1626dbd604927f2f00b1c7e5b6e1de621c7bf0008c05012c5654b77d0302c0be` |

Reconstruction semantics:

- Start from the base backup key space.
- Apply five-symbol `adjusted_close` recovery from the recovery source.
- Preserve all non-`adjusted_close` research fields from the base key space.
- Do not promote current live DB rows.

Five-symbol recovery scope:

```text
0050.TW
2330.TW
2337.TW
2404.TW
2454.TW
```

## 3. Store Structure

Research Store Candidate DB:

```text
data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
```

Research Store Candidate materialization manifest:

```text
data/research/manifests/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_manifest.json
```

Candidate DB tables:

- `historical_prices`
- `research_universes`
- `research_universe_symbols`
- `snapshot_metadata`

Excluded live/runtime tables:

- `historical_price_fetch_state`
- `stocks`
- `historical_financials`

The candidate DB file is marked read-only on disk after materialization.

## 4. Validation

Materialized DB validation:

| Check | Result |
| --- | ---: |
| `historical_prices` rows | `473481` |
| symbols | `222` |
| duplicates | `0` |
| integrity | `ok` |
| price data start | `1980-12-12` |
| price data end | `2026-08-07` |
| research universe rows | `2` |
| research universe symbol rows | `5` |
| excluded live tables present | `0` |

ResearchDataStore validation:

- `verify_manifest_reference()` passes against the materialization manifest.
- `connect_read_only()` opens the candidate with SQLite `mode=ro`.
- `PRAGMA query_only=ON`.
- Write attempt fails.
- `materialized_twse_common_stock_symbols()` returns `218` symbols.

Live separation validation:

- `LiveDataStore` rejects the configured released research store path.
- No `data/live/` directory was created.
- No live runtime path was switched.

Production DB validation:

| Check | Before | After |
| --- | --- | --- |
| `data/stocks.db` SHA | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` |
| `historical_prices` rows | `1185744` | `1185744` |
| symbols | `222` | `222` |
| integrity | `ok` | `ok` |

## 5. Checksum

Research Store Candidate database checksum:

```text
6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073
```

Semantic checksum:

```text
expected     = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
materialized = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
result       = MATCH
```

The semantic checksum validates the released research meaning recorded in the Phase 6A manifest. The database checksum validates this materialized candidate file's byte identity.

## 6. Read-Only Rules

Research Store Candidate rules:

- Open through `ResearchDataStore`.
- Use SQLite `mode=ro`.
- Enforce `PRAGMA query_only=ON`.
- Reject write attempts.
- Keep live refresh, Yahoo overwrite, runtime cache state, and mutable user data out of the candidate.

The candidate file is also chmod read-only after materialization.

## 7. Boundary Rules

Research boundary:

- `ResearchDataStore` may read the candidate and verify the manifest.
- Research services may use the candidate only through explicit research-store configuration.
- Research store must not contain live fetch state or mutable runtime cache tables.

Live boundary:

- `LiveDataStore` must not target the released research store path.
- Live writes remain out of scope in Phase 6D-3.
- `data/live/` must not exist after this phase.

PDF boundary:

- PDF Export remains `Scan Result Snapshot -> PDF`.
- PDF Export was not modified and must not directly read the Research Store Candidate.

Dashboard boundary:

- No dashboard switch was performed.
- Future research panels may use `ResearchDataStore`.
- Current market panels must remain live-store scoped in a later authorized phase.

## 8. Phase 7/3/4 Readiness

Readiness status:

- Phase 7: supported.
- Phase 3: supported.
- Phase 4: supported.

Phase 6D-3 did not fully rerun Phase 7, Phase 3, or Phase 4. The candidate now provides a physical research-store input for later reproduction acceptance.

## 9. Remaining Cutover Gaps

Remaining before Phase 6D completion:

- No runtime config cutover has occurred.
- `ResearchDataStore` default path still preserves current non-cutover behavior.
- `data/live/stocks_live.db` has not been created.
- Live store physical initialization remains future work.
- Scanner, dashboard, and PDF paths were not switched.
- Full Phase 7/3/4 reproduction against the physical candidate remains a future acceptance gate.
- Commit and push remain blocked until an explicit review/commit phase authorizes them.

Phase 6D-3 status:

```text
PASS
```
