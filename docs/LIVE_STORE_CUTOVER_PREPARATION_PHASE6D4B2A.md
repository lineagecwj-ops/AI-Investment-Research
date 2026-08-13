# Live Store Cutover Preparation Phase 6D-4B-2A

## 1. Scope

This phase prepares the future Live Store runtime cutover only.

No runtime cutover was performed. The split-store flag remains off, the default
runtime path remains `data/stocks.db`, and scanner, Dashboard, PDF, Yahoo/API
fetch, migration, import, commit, and push are out of scope.

Current stores:

```text
legacy_db_path   = data/stocks.db
research_db_path = data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
live_db_path     = data/live/stocks_live.db
```

## 2. Flag Design

Future feature flag:

```text
use_physical_store_split = false | true
```

Flag off:

```text
active_db_mode      = legacy
active_live_db_path = data/stocks.db
```

Flag on:

```text
active_db_mode      = physical_split
active_live_db_path = data/live/stocks_live.db
```

The flag is represented by the config resolver only. It is not enabled by
default and is not wired into scanner, Dashboard, or PDF runtime entry points in
this phase.

## 3. Config Resolution

The prepared config contract includes:

- `legacy_db_path`
- `research_db_path`
- `live_db_path`
- `research_snapshot_id`
- `manifest_path`

`resolve_database_runtime_config(use_physical_store_split=False)` resolves the
current live runtime path to the legacy DB.

`resolve_database_runtime_config(use_physical_store_split=True)` resolves the
future live runtime path to the physical Live Store DB while keeping the
Research Store path unchanged.

## 4. Scanner Preparation

Future scanner cutover flow:

```text
Scanner
  -> LiveDataStore(db_path=live_db_path)
  -> data/live/stocks_live.db
```

Rollback flow:

```text
Scanner
  -> LiveDataStore(db_path=legacy_db_path)
  -> data/stocks.db
```

This phase does not execute scanner workflows and does not change scanner
ranking, ordering, technical formulas, MATCH/NO_MATCH semantics, V1, or V1.1.

## 5. Dashboard Preparation

Future Dashboard split:

```text
Current Market Panel
  -> Live Store

Research Evidence
  -> Research Store
```

No UI or Dashboard runtime path was changed in this phase.

## 6. PDF Preparation

PDF Export remains snapshot-based:

```text
Scan Result Snapshot
  -> PDF Export
```

PDF Export must not depend directly on `data/stocks.db`,
`data/live/stocks_live.db`, Research Store DB, provider refresh, or scanner
execution.

## 7. Rollback

Rollback trigger examples:

- scanner failure;
- missing live data;
- live DB schema mismatch;
- performance issue;
- unexpected write to `data/stocks.db`;
- unexpected write to Research Store;
- Dashboard current panel failure;
- PDF export regression.

Rollback action:

```text
use_physical_store_split = false
active_live_db_path = legacy_db_path
```

Rollback must not restore, overwrite, or delete DB rows automatically.

## 8. Validation Checklist

Before cutover:

- legacy behavior captured;
- `data/stocks.db` SHA, row count, symbol count, and integrity captured;
- Research Store path and manifest captured;
- Live Store path and schema captured;
- config resolver tests pass with flag off and flag on.

During cutover:

- live DB active only when flag is explicitly enabled;
- Research Store remains unchanged;
- writes target only `data/live/stocks_live.db`;
- no silent fallback from missing live DB to Research Store.

After cutover:

- scanner works with injected/resolved LiveDataStore;
- V1 identity unchanged;
- V1.1 unchanged;
- Dashboard current panels work;
- Research Evidence panels work;
- PDF works from scan result snapshots;
- DB isolation checks pass.

## 9. Observability

Future diagnostics should record:

- `active_db_mode`;
- `active_live_db_path`;
- `active_research_snapshot_id`;
- `active_manifest_path`;
- manifest version/status;
- Research Store checksum;
- Live Store existence/schema status;
- last refresh time;
- latest fetch-state date;
- split-store flag state.

Normal user-facing pages should not show noisy implementation details unless a
diagnostic view is explicitly requested.

## 10. Phase Status

Phase status:

```text
PASS
```

Safe next step:

```text
Phase 6D-4B-2B Cutover may proceed only after explicit authorization.
```
