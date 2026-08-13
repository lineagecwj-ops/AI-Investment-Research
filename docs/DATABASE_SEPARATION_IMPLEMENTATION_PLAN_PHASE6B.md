# Database Separation Implementation Plan Phase 6B

## 1. Target Architecture

Phase 6B is planning only. It does not create a database, copy data, migrate
schema, write SQLite, fetch Yahoo data, execute scanner workflows, change PDF
Export, change Dashboard behavior, commit, or push.

Future target layout:

```text
data/
  research/
    snapshots/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
    manifests/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json
    validation_artifacts/
      phase7/
      phase3/
      phase4/
      backtest/
      replay/
      oos/
      ai/
  live/
    stocks_live.db
    fetch_state/
```

The current `data/stocks.db` remains a `LiveDataStore candidate` until a later
authorized phase creates the physical split.

Target ownership:

| Store | Mutability | Primary responsibility |
|---|---|---|
| ResearchDataStore | Immutable | Released research snapshots, frozen historical prices, snapshot universe metadata, validation artifacts, lineage |
| LiveDataStore | Mutable | Current market cache, Yahoo refresh, fetch state, runtime metadata, current scanner input |

## 2. ResearchDataStore Design

ResearchDataStore responsibilities:

- expose released Research Snapshot metadata by `research_snapshot_id`;
- open snapshot SQLite files read-only;
- verify manifest identity, source checksums, semantic checksum, row count,
  symbol count, and date coverage before use;
- load immutable `historical_prices`;
- load universe metadata linked to the released snapshot;
- expose validation artifact references and lineage;
- provide deterministic readers for Phase 7, Phase 3, Phase 4, backtest,
  replay, walk-forward, OOS, and future AI datasets.

Required future interface shape:

```python
class ResearchDataStore:
    def open_snapshot(self, snapshot_id: str): ...
    def verify_manifest(self, snapshot_id: str): ...
    def load_price_series(self, symbol: str, *, snapshot_id: str): ...
    def load_universe(self, universe_id: str, *, snapshot_id: str): ...
    def load_listing_dates(self, universe_id: str, *, snapshot_id: str): ...
    def audit_snapshot(self, snapshot_id: str): ...
```

Forbidden behavior:

- Yahoo refresh;
- runtime mutation;
- cache update;
- schema initialization;
- schema migration;
- writing `historical_price_fetch_state`;
- silently reading the current live DB as a research snapshot.

## 3. LiveDataStore Design

LiveDataStore responsibilities:

- own current `stocks`, `historical_prices`, and `historical_price_fetch_state`
  cache behavior;
- fetch Yahoo data;
- persist refreshed historical price cache;
- persist current stock profile cache;
- own retry, freshness, staleness, and fetch metadata;
- supply current scanner inputs.

Required future interface shape:

```python
class LiveDataStore:
    def get_cached_price_series(self, symbol: str, *, start=None, end=None): ...
    def refresh_price_series(self, symbol: str, *, start=None, end=None): ...
    def save_price_series(self, series, *, full_history_fetched: bool): ...
    def get_fetch_state(self, symbol: str): ...
    def get_cached_stock_profile(self, symbol: str): ...
    def save_stock_profile(self, stock): ...
```

Allowed behavior:

- read/write live cache;
- update fetch state;
- refresh provider data;
- return stale live cache when provider fetch fails, when current product logic
  explicitly allows that behavior.

Forbidden behavior:

- open ResearchDataStore in writable mode;
- mutate released research snapshots;
- promote refreshed live rows into a released snapshot without a new snapshot
  version and validation process.

## 4. Access Layer

Future code should stop hard-coding:

```text
data/stocks.db
```

Future configuration contract:

```text
research_db_path
live_db_path
research_snapshot_id
manifest_path
research_artifact_root
live_cache_root
```

Recommended boundary layer:

```python
class DatabasePathConfig:
    research_db_path: Path | None
    live_db_path: Path
    research_snapshot_id: str | None
    manifest_path: Path | None

class DataStoreRegistry:
    def research(self, snapshot_id: str) -> ResearchDataStore: ...
    def live(self) -> LiveDataStore: ...
```

`src/database.py` should evolve from mixed persistence implementation into
store-specific helper modules. The split should be gradual:

- shared row conversion utilities can remain common;
- live schema initialization and writes move to LiveDataStore;
- read-only snapshot open and manifest verification move to ResearchDataStore;
- old `DEFAULT_DB_PATH` becomes compatibility configuration only, not the
  semantic owner of both live and research data.

## 5. Migration Stages

| Stage | Goal | Change | Risk | Rollback |
|---:|---|---|---|---|
| 0 | Configuration abstraction | Add path config and store registry without changing default behavior | Wrong default path could break app startup | Feature flag off; use existing `DEFAULT_DB_PATH` |
| 1 | Research readers | Add ResearchDataStore read-only interfaces and manifest verification | Research readers may still accidentally hit live DB | Keep old read-only loaders as fallback; compare checksums |
| 2 | Research validation modules | Route Phase 7, Phase 3, and Phase 4 reproduction paths through ResearchDataStore | Reproduction drift | Re-run Phase 7/3/4 comparisons; switch back by config |
| 3 | Backtest, replay, walk-forward, OOS | Inject ResearchDataStore price loaders for historical studies | Loader default may fetch live data | Require explicit `snapshot_id` for research runs |
| 4 | Live writers | Move `save_historical_prices`, fetch state update, and cache refresh behind LiveDataStore | Current scanner cache write regression | Keep compatibility adapter using current live DB path |
| 5 | Current scanner | Make current scanner explicitly use LiveDataStore | Scanner may be confused with research evidence | Keep scan result snapshot source labels and existing V1 logic |
| 6 | Dashboard current panel | Separate current market panel from research evidence panel | UI source confusion | Feature flag to show legacy combined labels while retaining store boundaries |

No stage should overwrite a released Research Snapshot in place.

## 6. Module Migration Matrix

| Module / area | Current path | Future owner | Migration phase | Risk | Validation |
|---|---|---|---:|---|---|
| `src/database.py` | `DEFAULT_DB_PATH`, schema creation, migrations, cache read/write | Boundary layer split into shared conversion, ResearchDataStore readers, LiveDataStore writers | 0, 1, 4 | Highest; mixed ownership and schema writes | Unit tests for path config, read-only research opens, live write adapter |
| `src/historical_price_service.py` | `get_historical_prices()` reads cache, fetches Yahoo, calls `save_historical_prices()` | LiveDataStore | 4 | Accidental research use could fetch or write | Live refresh tests, stale cache tests, no ResearchDataStore mutation tests |
| `src/stock_service.py` | current stock profile cache via `DEFAULT_DB_PATH` | LiveDataStore | 4 | Current profile writes mixed with research context | Stock cache tests using live path only |
| `src/historical_financial_service.py` | historical financial cache under shared DB | Split: Live provider cache now; future research financial snapshots when authorized | 4 or later | Future AI may need immutable financial baselines | Explicit dataset scope tests before AI use |
| `src/universe_service.py` | mutable saved universe CRUD in current DB | Split: editable live/user universes vs immutable research universe snapshots | 1, 4 | User editable universe could be mistaken for released universe | Universe ID/version tests; immutable research fixture tests |
| `SwingScannerService` | default price loader is `get_historical_prices` | Current scanner uses LiveDataStore; research runs inject ResearchDataStore loaders only when explicitly requested | 5 | Current scanner could be routed to frozen research data by mistake | Scanner smoke tests, source-label checks, no ResearchDataStore write checks |
| Condition Coverage | read-only service paths, DB safety audit patterns | ResearchDataStore | 2 | Default `data/stocks.db` path hides store identity | Phase reproduction, checksum and query-only tests |
| Phase 3 services | read-only loaders and projection artifacts | ResearchDataStore | 2 | Display evidence drift | Phase 3 counts, symbols, ordering, semantic checksum |
| Phase 4 dashboard | UI mixes current and research panels | Shared UI with separated LiveDataStore and ResearchDataStore inputs | 6 | Visual/source confusion | Dashboard source labels and Phase 4 projection reproduction |
| Backtest | pure once supplied price/technical series | ResearchDataStore for historical research; pure core remains shared | 3 | Default live loader could change research results | Backtest reproduction under snapshot ID |
| Replay | default loader is `get_historical_prices` | ResearchDataStore for historical replay; LiveDataStore for ad hoc current cache only | 3 | Live restatement drift | Replay reproduction and explicit snapshot ID requirement |
| Walk-Forward | default loader is `get_historical_prices` | ResearchDataStore | 3 | Period tests may fetch live data | Walk-forward deterministic fixture tests |
| OOS | default loader is `get_historical_prices` | ResearchDataStore | 3 | OOS split reproducibility risk | OOS validation with fixed snapshot and split manifest |
| PDF Export | uncommitted `src/swing_scanner_pdf_export_service.py`, no DB access | DB-agnostic, Scan Result Snapshot to PDF | No migration needed | Coupling risk if future export opens DB | PDF tests confirm no SQLite import/open |
| `app.py` | orchestrates live scanner and read-only historical views | Shared UI with explicit source routing | 5, 6 | Large blast radius | AppTest paths for scanner, research evidence, PDF export |
| AI future modules | not yet DB owner | ResearchDataStore for immutable feature/target datasets | Future phase | Leakage from live refreshed data | Dataset manifest, feature checksum, target checksum |

## 7. Read-Only Enforcement

ResearchDataStore must enforce:

```text
sqlite URI mode=ro
PRAGMA query_only=ON
manifest verification before query
snapshot_id required
semantic checksum available to caller
```

Recommended guard checks:

- assert path is under the configured research snapshot root;
- assert manifest `status = RELEASED`;
- assert manifest `snapshot_id` matches requested ID;
- assert manifest `semantic_checksum` matches expected value;
- assert current connection cannot write by design;
- fail closed when manifest is missing, ambiguous, or stale.

LiveDataStore may open writable SQLite connections, but only under the live path
contract.

## 8. Live Writer Isolation

These operations must be live-only:

- `save_historical_prices`;
- `historical_price_fetch_state` update;
- Yahoo refresh;
- current stock profile cache update;
- provider retry and staleness metadata update;
- current scanner cache preparation.

Future implementation guard:

```text
Live writes require live_db_path.
Research paths reject write-capable helpers.
Released snapshot paths reject schema initialization and migration helpers.
```

## 9. Research Reader Isolation

These flows must read ResearchDataStore when used as research evidence:

- Phase 7;
- Phase 3;
- Phase 4;
- condition coverage;
- backtest;
- replay;
- walk-forward;
- OOS;
- future AI feature and target dataset creation.

Research runs must require explicit `research_snapshot_id`. They should not
fall back to `data/stocks.db` if the research snapshot path is absent.

## 10. Scanner Future Flow

Current scanner flow:

```text
User request
  -> LiveDataStore
  -> cached or refreshed live historical prices
  -> technical calculation
  -> Production V1
  -> Scan Result Snapshot
  -> optional PDF Export
```

Rules:

- current scanner does not directly read ResearchDataStore;
- scanner ranking, qualification, recommendations, formulas, and V1 semantics
  remain unchanged unless separately authorized;
- scan result snapshots may record a `research_snapshot_reference` only as
  provenance, not as a DB dependency.

## 11. Dashboard Future Flow

Separate source domains:

| Dashboard area | Source | Rule |
|---|---|---|
| Current Market Panel | LiveDataStore | mutable cache, current provider freshness, current scanner |
| Research Evidence Panel | ResearchDataStore | immutable evidence, released snapshot, validation artifacts |
| PDF Export entry | Scan Result Snapshot | no direct DB dependency |

The dashboard can present current and research evidence together, but each panel
must show its source identity and must not mix live rows into released research
evidence.

## 12. PDF Future Flow

PDF Export remains:

```text
Scan Result Snapshot
  -> PDF export service
  -> PDF artifact
```

PDF Export should not:

- open ResearchDataStore;
- open LiveDataStore;
- fetch Yahoo;
- execute scanner workflows;
- rebuild technical indicators;
- mutate a scan result.

Future PDF metadata may include:

```text
scan_snapshot_id
research_snapshot_reference
research_snapshot_semantic_checksum
live_data_timestamp
```

This preserves compatibility with the current uncommitted PDF Export feature.

## 13. Snapshot Usage Rules

Released Research Snapshot may be used for:

- Phase 7;
- Phase 3;
- Phase 4;
- backtest;
- replay;
- walk-forward;
- OOS;
- future AI datasets.

Forbidden:

- live scanner writes;
- Yahoo overwrite;
- live refresh;
- silent mutation;
- implicit promotion of `data/stocks.db`;
- replacing Candidate A `v1` in place.

Any future corrected snapshot must use a new snapshot ID or version, new
checksum, and new validation evidence.

## 14. Acceptance Criteria

Migration acceptance checklist:

| Area | Criterion |
|---|---|
| Research snapshot | Snapshot checksum unchanged |
| Research semantics | Semantic checksum unchanged |
| Phase 7 | Reproduction PASS |
| Phase 3 | Reproduction PASS, counts and ordering unchanged |
| Phase 4 | Reproduction PASS, projection groups unchanged |
| Backtest | Historical backtest reproduction under explicit snapshot ID |
| Replay | Replay reproduction under explicit snapshot ID |
| Walk-forward | Deterministic period loading under explicit snapshot ID |
| OOS | OOS validation uses fixed snapshot and split policy |
| Scanner | Current scanner still works through LiveDataStore |
| Dashboard | Current panel and research panel use separated source labels |
| PDF | PDF still exports from Scan Result Snapshot without DB access |
| Boundary | Live cannot modify Research |
| Boundary | Research cannot depend on Live |
| Legacy path | No unreviewed dependency on hard-coded `data/stocks.db` |
| Git | Small staged diff per phase, no unrelated refactor |

## 15. Rollback Plan

Rollback cannot rely only on DB restore. Use:

- feature flag for store separation;
- configuration switch for legacy `DEFAULT_DB_PATH` compatibility;
- per-module adapter rollback;
- old read-only research loaders retained until ResearchDataStore is validated;
- live writer adapter retained until LiveDataStore write isolation is validated;
- release snapshot manifests retained as immutable references;
- validation artifacts retained for comparison.

Recommended rollback levels:

| Level | Scope | Action |
|---|---|---|
| Config rollback | path routing problem | switch store registry back to legacy path |
| Module rollback | one migrated service regresses | route that service through compatibility adapter |
| Research rollback | reproduction drift | block migration stage, keep previous snapshot references |
| Live rollback | refresh/write regression | route live writes through old `historical_price_service` adapter |
| UI rollback | source display confusion | disable separated panel UI, keep source labels in logs/reports |

## 16. Performance Considerations

ResearchDataStore:

- read-only access should favor short-lived SQLite connections initially;
- connection pooling is optional and should be added only if repeated snapshot
  reads are measured as slow;
- manifest verification can be cached in memory per process after checksum
  validation;
- price series loading may need symbol-level memoization for backtest/replay
  workflows;
- snapshot loading should fail closed when manifest and physical snapshot do not
  match.

LiveDataStore:

- current cache should preserve existing stale-cache behavior;
- Yahoo fetch concurrency should remain controlled to avoid provider and UI
  instability;
- fetch state updates should stay transactional;
- live cache performance must not be coupled to ResearchDataStore verification.

Dashboard:

- research evidence panels should load stable artifacts rather than repeatedly
  scanning snapshot DBs when possible;
- current market panels can continue using live cache TTL semantics.

## 17. Test Strategy

Research tests:

- manifest parse and required-field validation;
- `status = RELEASED` required;
- `snapshot_id` mismatch fails closed;
- SQLite read-only `mode=ro` enforced;
- `PRAGMA query_only=ON` enforced;
- semantic checksum is exposed and unchanged;
- Phase 7 reproduction PASS;
- Phase 3 reproduction PASS;
- Phase 4 reproduction PASS;
- deterministic price series loading by `symbol` and `trading_date`.

Live tests:

- live refresh writes only to `live_db_path`;
- `save_historical_prices` cannot receive a research path;
- fetch state updates are live-only;
- stale cache fallback remains intact;
- stock profile cache writes are live-only.

Boundary tests:

- LiveDataStore cannot open a released research snapshot in writable mode;
- ResearchDataStore cannot call Yahoo fetch helpers;
- research modules fail when no `research_snapshot_id` is supplied;
- current scanner does not require ResearchDataStore;
- PDF Export has no SQLite dependency.

Integration tests:

- scanner still works with LiveDataStore adapter;
- Dashboard current panel and research panel use separate source labels;
- PDF Export still consumes Scan Result Snapshot;
- app-level smoke tests cover both current and research paths after each stage.

## 18. Phase 6B Stop Gate

This document is the Phase 6B planning artifact only.

Do not proceed in this phase to:

- create any DB;
- create a research database;
- create a live database;
- copy data;
- run migration;
- alter schema;
- write SQLite;
- fetch Yahoo;
- run scanner workflows;
- change Dashboard behavior;
- change PDF Export behavior;
- change Production V1 or V1.1;
- start Long-Term Growth;
- commit;
- push.
