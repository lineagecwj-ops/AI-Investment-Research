# Physical Store Dry Run Phase 6D-2

## 1. Dry Run Scope

Phase 6D-2 rehearses the physical separation process without formal migration.

Allowed actions performed:

- Created temporary dry-run stores under `/tmp`.
- Created a temporary validation artifact under `/tmp`.
- Added dry-run tests.
- Added this documentation file.

Actions not performed:

- No `data/research/` creation.
- No `data/live/` creation.
- No `data/stocks.db` modification.
- No formal migration.
- No path cutover.
- No scanner execution.
- No dashboard or PDF change.
- No Production V1 or V1.1 change.
- No Long-Term Growth implementation.
- No commit or push.
- No network fetch.

Production DB baseline:

- Path: `data/stocks.db`
- SHA: `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa`
- `historical_prices` rows: `1185744`
- symbols: `222`
- integrity: `ok`

## 2. Research Materialization

Dry-run path:

```text
/tmp/research_store_dry_run/
  research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.dry_run.db
```

The dry-run research DB contains:

- `snapshot_metadata`
- `historical_prices`
- a manifest reference to Released Research Snapshot v1
- minimal sample research price data for validation

Snapshot identity:

- Expected snapshot ID: `research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1`
- Manifest status: `RELEASED`
- Dry-run metadata snapshot ID: `research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1`

Dataset scope:

- This is a minimal dry-run sample.
- It is not the full canonical materialized research snapshot.
- It proves physical-store mechanics and reader boundary behavior, not full Phase 7/3/4 reproduction.

Semantic checksum:

- Expected semantic checksum: `a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91`
- Dry-run checksum source: Phase 6A manifest `validation.semantic_checksum`
- Result: `MATCH`

Important limitation:

- The dry-run DB does not recompute the canonical semantic checksum from full materialized research rows.
- It verifies that the dry-run store can bind to the released manifest and preserve the canonical snapshot identity.

## 3. ResearchDataStore Validation

Validation result: `PASS`.

Confirmed:

- `ResearchDataStore` can read the temp research store.
- `verify_manifest_reference()` accepts the Released Research Snapshot v1 manifest.
- `connect_read_only()` sets `PRAGMA query_only=ON`.
- Write attempt through the read-only connection fails.
- `load_historical_price_series()` reads dry-run `historical_prices`.

Phase 7/3/4 readiness:

- Supported by boundary and manifest reference.
- Not fully reproduced in Phase 6D-2, by instruction.
- Full reproduction remains an implementation/acceptance-phase requirement.

## 4. Live Initialization

Dry-run path:

```text
/tmp/live_store_dry_run/
  stocks_live.dry_run.db
```

Validation result: `PASS`.

Confirmed:

- `LiveDataStore` can connect to a temp live DB.
- `LiveDataStore` can write temp `historical_prices`.
- `historical_price_fetch_state` is updated in the temp live DB.
- The write target is `/tmp/live_store_dry_run/stocks_live.dry_run.db`.
- `data/stocks.db` remains unchanged.

## 5. Initialization Option Analysis

### Option A: Current live DB seed

Use current `data/stocks.db` as the seed source for future `data/live/stocks_live.db`.

Advantages:

- Preserves cache warmth.
- Minimizes initial live refresh volume.
- Keeps current dashboard/current-market behavior closest to today's local state.

Risks:

- Imports the current live DB state, including rows added during prior validation pollution.
- Requires explicit provenance labeling as mutable live cache, not research truth.
- Needs a baseline audit before acceptance.

### Option B: Fresh live cache

Create `stocks_live.db` as a fresh mutable live cache.

Advantages:

- Cleanest physical boundary.
- Avoids carrying mixed legacy/research history into live cache.
- Makes live provenance easier to reason about.

Risks:

- Initial cache is cold.
- More provider refresh is needed after cutover.
- Requires mocked or controlled refresh tests before relying on provider availability.

Recommendation:

- Prefer Option B for clean separation.
- Use Option A only if the current DB seed is explicitly accepted as mutable live cache and not research evidence.

## 6. Boundary Validation

Research boundary:

- Research temp store is read through `ResearchDataStore`.
- Research write attempt is blocked by read-only/query-only connection.

Live boundary:

- Live temp store writes only to `/tmp`.
- `LiveDataStore` rejects the configured released research store path.

Production DB protection:

- Before and after production DB fingerprints are identical.
- No production DB write occurred.

## 7. Config Dry Run

Future config shape was validated in temp environment:

- `research_db_path`
- `live_db_path`
- `research_snapshot_id`
- `manifest_path`

No config cutover was performed.

No runtime default was changed.

## 8. Rollback Dry Run

Rollback model:

- Dry-run stores live under `/tmp`.
- Removing `/tmp/research_store_dry_run/` and `/tmp/live_store_dry_run/` fully removes dry-run state.
- Production config remains unchanged.
- `data/stocks.db` remains untouched.

Rollback result: `PASS`.

## 9. Tests

Added:

- `tests/test_physical_store_dry_run.py`

Coverage:

- Research store temp creation.
- Live store temp creation.
- Research read-only behavior.
- Live write isolation.
- No production DB mutation.
- Manifest dataset scope excludes live-only tables.

Executed:

- `python -m unittest tests.test_physical_store_dry_run`

Result:

- `5 tests OK`

## 10. Findings

Dry-run result: `PASS_WITH_GAPS`.

Confirmed:

- Physical split mechanics work in `/tmp`.
- Research and live boundaries can operate against separate temporary SQLite stores.
- Released Research Snapshot v1 manifest identity is usable as the research anchor.
- Live writes can be isolated to a temp live DB.
- Production DB remains unchanged.

Gaps:

- The dry-run research store is not a full canonical materialized snapshot.
- Phase 7/3/4 were not fully reproduced, per dry-run scope.
- Formal materialization, checksum recomputation, and config cutover remain future Phase 6D tasks.

Safe next step:

- Proceed to Phase 6D-3 only if the next phase explicitly authorizes deeper materialization planning or implementation.
