# Live Store Runtime Cutover Phase 6D-4B-2B

## 1. Scope

Phase 6D-4B-2B performs the physical path runtime cutover without real provider
warm-up.

Authorized change:

```text
Live runtime resolution:
  from data/stocks.db
  to   data/live/stocks_live.db
```

Out of scope:

- Yahoo/yfinance/provider network fetch;
- real cache warm-up;
- bulk population of `stocks_live.db`;
- copying or importing `data/stocks.db`;
- Research Snapshot mutation;
- Production V1/V1.1 semantic changes;
- technical formula, ranking, or ordering changes;
- PDF Export behavior changes;
- Long-Term Growth work;
- commit or push.

## 2. Before Architecture

```text
Current/live runtime
  -> LiveDataStore(default)
  -> data/stocks.db

Research readers
  -> mixed legacy-compatible defaults
```

`data/stocks.db` remains the rollback store only after this phase.

## 3. After Architecture

```text
Current/live runtime
  -> LiveDataStore()
  -> data/live/stocks_live.db

Research evidence
  -> ResearchDataStore()
  -> data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
  -> docs/research_snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json

Rollback compatibility
  -> use_physical_store_split = false
  -> data/stocks.db
```

## 4. Feature Flag And Defaults

Runtime default:

```text
use_physical_store_split = true
active_db_mode = physical_split
active_live_db_path = data/live/stocks_live.db
```

Explicit rollback/off resolution:

```text
use_physical_store_split = false
active_db_mode = legacy
active_live_db_path = data/stocks.db
```

Research path resolution is independent of the live flag and remains bound to
the released Research Store snapshot.

## 5. Formal Live Store

Formal Live Store path:

```text
data/live/stocks_live.db
```

Expected contents at this phase:

- live schema only;
- synthetic validation row may remain from the formal creation phase;
- no migrated legacy historical data;
- no provider warm-up rows;
- no research tables.

This phase validates `CUTOVER_PATH_READY`. It does not claim
`LIVE_CACHE_WARMED`.

## 6. Research Store

Released Research Store path:

```text
data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
```

Released manifest path:

```text
docs/research_snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json
```

Semantic checksum:

```text
a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

`ResearchDataStore()` uses read-only SQLite connections with `query_only=ON`
and rejects the mutable Live Store path.

## 7. Scanner, Dashboard, And PDF

Scanner preparation:

```text
SwingScannerService()
  -> LiveDataStore()
  -> data/live/stocks_live.db
```

App current scan builder injects `LiveDataStore()` into scanner and historical
price loading. Real current scans are not executed in this phase.

Dashboard target split:

```text
Current Market Panel -> Live Store
Research Evidence    -> Research Store
```

PDF Export remains DB-agnostic:

```text
Scan Result Snapshot -> PDF
```

## 8. Rollback

Rollback uses config resolution only:

```text
use_physical_store_split = false
active_live_db_path = data/stocks.db
```

Rollback must not restore, copy, merge, delete, or mutate any DB.

## 9. Validation Evidence

Targeted validation covered:

- split OFF resolves legacy live path;
- split ON resolves formal live path;
- split ON resolves released research path;
- LiveDataStore rejects Research Store;
- ResearchDataStore rejects Live Store;
- scanner receives formal LiveDataStore under split mode;
- app current scan builder uses formal LiveDataStore;
- Research Evidence helper uses ResearchDataStore;
- Production V1 and V1.1 source definitions remain unchanged;
- PDF Export service remains DB-agnostic;
- rollback flag returns legacy path;
- production DB fingerprint remains unchanged;
- no network/provider call is required for validation.

## 10. Remaining Gap

```text
PHYSICAL_PATH_CUTOVER_PASS = YES
LIVE_CACHE_WARMED = NO
```

The next authorized phase should perform controlled Live Cache warm-up with
explicit provider/network permission or fully mocked warm-up validation.
