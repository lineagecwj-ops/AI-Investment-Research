# Database Access Boundary Phase 2

## 1. Current DB Usage Map

Current hard-coded default:

```text
src/database.py: DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "stocks.db"
```

Observed access categories:

| Location | Access pattern | Current purpose | Boundary classification |
|---|---|---|---|
| `src/database.py` | `sqlite3.connect(Path(db_path))`, schema creation, migrations, inserts, updates, cache reads | Base persistence and cache helpers | MIXED |
| `src/historical_price_service.py` | `get_historical_prices()` reads cache, may fetch Yahoo, then `save_historical_prices()` | Live price loader used by scanner, replay, OOS, and dashboards | MUTABLE_LIVE_CACHE |
| `src/stock_service.py` | Uses stock cache helpers | Company profile and current stock data | MUTABLE_LIVE_CACHE |
| `src/historical_financial_service.py` | Uses historical financial cache helpers | Fundamental history cache | MIXED |
| `src/universe_service.py` | Creates, reads, updates, deletes saved universes | User-managed research universes | MIXED |
| `src/expanded_volume_threshold_validation_service.py` | SQLite URI `mode=ro` read-only loader and coverage audit | Research validation inputs | READ_ONLY_RESEARCH |
| `src/scanner_condition_coverage_outcome_research_service.py` | `mode=ro`, `PRAGMA query_only=ON`, DB safety audit | Condition coverage outcome research | READ_ONLY_RESEARCH |
| `src/scanner_condition_coverage_phase2_robustness_service.py` | Uses research DB safety audit and read-only inputs | Phase 2 robustness research | READ_ONLY_RESEARCH |
| `src/candidate_display_research_service.py` | Uses read-only loader and DB safety audits around live projection | Phase 3 candidate display research | READ_ONLY_RESEARCH |
| `src/etf_constituent_universe_service.py` | `mode=ro`, `PRAGMA query_only=ON` coverage audit; DB file audit | Frozen ETF/TWSE universe coverage | READ_ONLY_RESEARCH |
| `src/frozen_twse_research_universe_service.py` | Loads Frozen TWSE symbols from default DB through helper stack | Frozen universe source | READ_ONLY_RESEARCH |
| `app.py` | Calls `get_historical_prices()` in live workflows; also has explicit `mode=ro` historical diagnostics query | Dashboard orchestration | MIXED |
| `src/swing_scanner_service.py` | Default price loader is `get_historical_prices` | Current scanner and current signal details | MUTABLE_LIVE_CACHE |
| `src/historical_replay_service.py` | Default price loader is `get_historical_prices` | Replay when not supplied with cached series | MIXED |
| `src/walk_forward_replay_service.py` | Default price loader is `get_historical_prices` | Walk-forward replay input loading | MIXED |
| `src/out_of_sample_validation_service.py` | Default price loader is `get_historical_prices` | OOS price loading | MIXED |
| `src/twse_backfill_pilot_service.py` | Backup creation, read-only verification, and explicit pilot writes | Backfill tooling | MUTABLE_LIVE_CACHE / migration-tooling risk |
| `src/swing_scanner_pdf_export_service.py` | No DB access | Snapshot-to-PDF export | NO_DB_ACCESS |

## 2. Module Ownership Matrix

| Module / area | Current DB access | Purpose | Future owner |
|---|---|---|---|
| `SwingScannerService` | Indirect mutable loader by default | Current scanner | Live |
| Price loader / `historical_price_service` | Mutable cache read/fetch/write | Live price cache | Live |
| `database.py` | All table creation, migration, cache reads/writes | Shared persistence implementation | Shared boundary layer to be split |
| Historical outcome services | Mostly in-memory inputs; rely on price series supplied by callers | Outcome evaluation | Research when running baselines; Shared pure logic otherwise |
| Condition Coverage research | Read-only DB audits and loaders | Historical research evidence | Research |
| Phase 3 candidate display | Read-only research projection and safety audit | Research display evidence | Research |
| Phase 4 dashboard | Displays current and research panels together | UI orchestration | Shared UI with separated inputs |
| Backtest | Pure service once price/technical series supplied | Historical aggregation | Research |
| Replay | Default mutable loader unless supplied cached series | Point-in-time replay | Research for historical studies; Live only for ad hoc current cache loading |
| Walk-Forward | Default mutable loader unless supplied cached series | Multi-period replay | Research |
| OOS | Default mutable loader unless injected otherwise | OOS validation | Research |
| AI / research modules | Currently not a DB owner; future datasets need stable inputs | AI reports and future ML datasets | Research |
| PDF Export | No DB access | Export existing scan snapshot | Shared / No DB |
| Universe modules | Frozen universe reads and mutable saved universe CRUD both exist | Symbol source management | Split Research snapshots vs Live/user editable universes |

Research modules list:

- `expanded_volume_threshold_validation_service`
- `scanner_condition_coverage_outcome_research_service`
- `scanner_condition_coverage_phase2_robustness_service`
- `candidate_display_research_service`
- `etf_constituent_universe_service`
- `frozen_twse_research_universe_service`
- backtest service when supplied research inputs
- replay / walk-forward / OOS when supplied research store inputs

Live modules list:

- `historical_price_service`
- `stock_service`
- current scanner path in `swing_scanner_service`
- company and current-market dashboard paths
- mutable cache portions of `database.py`

Shared modules list:

- `database.py` until split
- `app.py`
- `universe_service`
- replay / walk-forward / OOS service entrypoints when they keep default mutable loaders
- `historical_financial_service`

## 3. ResearchDataStore Design

Future interface responsibilities:

```python
class ResearchDataStore:
    def load_frozen_price_series(self, symbol: str, snapshot_id: str): ...
    def load_universe_snapshot(self, universe_id: str): ...
    def load_listing_dates(self, universe_id: str): ...
    def load_signal_snapshot(self, signal_snapshot_id: str): ...
    def load_outcome_dataset(self, outcome_dataset_id: str): ...
    def load_feature_dataset(self, feature_dataset_id: str): ...
    def load_target_dataset(self, target_dataset_id: str): ...
    def audit_snapshot(self, snapshot_id: str): ...
```

Rules:

- Opens research data read-only by default.
- Requires snapshot IDs for accepted research inputs.
- Returns immutable domain objects or tuples.
- Exposes checksum, row count, symbol count, date range, and semantic metadata.
- Does not fetch Yahoo, update cache state, initialize schemas, or migrate tables during research reads.

## 4. LiveDataStore Design

Future interface responsibilities:

```python
class LiveDataStore:
    def get_cached_price_series(self, symbol: str, start=None, end=None): ...
    def refresh_price_series(self, symbol: str, start=None, end=None): ...
    def save_price_series(self, series, *, full_history_fetched: bool): ...
    def get_fetch_state(self, symbol: str): ...
    def get_cached_stock_profile(self, symbol: str): ...
    def save_stock_profile(self, stock): ...
```

Rules:

- May update live cache and fetch state.
- Owns `fetched_at`, retry/failure metadata, current quote cache, and provider freshness state.
- Must not open the ResearchDataStore in writable mode.
- Must not silently promote refreshed rows into accepted research snapshots.

## 5. Table Ownership Proposal

| Table | Current owner | Future owner | Need split? | Need snapshot? | Need mutable? |
|---|---|---|---|---|---|
| `historical_prices` | Shared | Research frozen prices plus Live cache prices | Yes | Yes | Live copy yes; research copy no |
| `historical_price_fetch_state` | Shared/live cache | LiveDataStore | Yes | No, except audit metadata | Yes |
| `stocks` | Live cache | LiveDataStore | No | No | Yes |
| `historical_financials` | Shared cache | Research snapshots plus live/provider cache | Yes | Yes for research and AI | Live source yes |
| `research_universes` | Shared/user-managed | Research snapshots plus editable user/live store | Yes | Yes for accepted universes | Editable copy yes |
| `research_universe_symbols` | Shared/user-managed | Research snapshots plus editable user/live store | Yes | Yes for accepted membership | Editable copy yes |

## 6. Price Data Boundary

`historical_prices` should be divided conceptually:

Research-owned fields:

- `symbol`
- `trading_date`
- `open`
- `high`
- `low`
- `close`
- `adjusted_close`
- `volume`
- `dividends`
- `stock_splits`
- `currency`

Live-owned metadata:

- `fetched_at`
- fetch coverage state in `historical_price_fetch_state`
- provider retry/failure status in future live metadata

The table does not need to be changed in this phase. The boundary is semantic: price values in an accepted research snapshot must be frozen, while live metadata may continue to change in the live store.

## 7. Adjusted Close Policy

Future rule:

- Research store freezes `adjusted_close` by snapshot version.
- Live store may refresh and receive provider restatements.
- Any `adjusted_close` restatement that should affect research must create a new research snapshot version.
- Existing accepted research snapshots must not be silently overwritten.
- Research reports must cite the exact adjusted-close snapshot version used.

## 8. Scanner Flow

Future current scanner flow:

```text
User request
  -> LiveDataStore
  -> price series / current cache
  -> technical indicators
  -> Production V1
  -> Dashboard current scan result
  -> optional PDF export from scan result snapshot
```

Future research flow:

```text
Research snapshot
  -> ResearchDataStore
  -> deterministic historical price series
  -> technical features
  -> backtest / outcome / replay / OOS
  -> research artifact with checksum
```

## 9. Dashboard Flow

The dashboard should separate two panels conceptually:

| Panel | Source | Mutability |
|---|---|---|
| Live panel | LiveDataStore and in-session scanner snapshots | Mutable |
| Research evidence panel | ResearchDataStore snapshots and artifacts | Immutable per snapshot |

The UI can still present both together, but source labels and fingerprints should distinguish live data from accepted research evidence.

## 10. PDF Export Boundary

PDF Export should remain DB-agnostic:

```text
Scan Result Snapshot
  -> coverage / candidate projection snapshot
  -> PDF export service
```

The PDF export service should not scan, fetch, rebuild technical indicators, or open SQLite. A ResearchDataStore / LiveDataStore split should not change PDF export architecture.

## 11. AI Pipeline Requirement

Long-Term Growth AI and any future model dataset should depend only on ResearchDataStore snapshots.

Required versioned inputs:

- universe snapshot;
- feature snapshot;
- target label snapshot;
- training dataset version;
- validation and OOS dataset versions;
- code/config fingerprint;
- checksum for every dataset artifact;
- leakage contract proving features use only data available at or before observation date.

## 12. Configuration Design

Future DB paths should be centralized instead of scattered through default constants:

```text
research_db_path
live_db_path
user_db_path optional
research_snapshot_id
```

Configuration should make the caller choose the boundary explicitly. Research jobs should fail closed if they receive only a live DB path.

## 13. Test Strategy

Research access tests:

- opens SQLite with URI `mode=ro`;
- applies `PRAGMA query_only=ON`;
- requires snapshot metadata and checksum;
- produces deterministic output from the same snapshot;
- does not import or call Yahoo fetch paths.

Live access tests:

- allows cache refresh and fetch state updates in test DBs;
- preserves provider failure behavior;
- records `fetched_at` and coverage state;
- never writes to a research DB path.

Boundary tests:

- LiveDataStore cannot mutate ResearchDataStore;
- ResearchDataStore cannot depend on `historical_price_service.get_historical_prices`;
- research workflows reject missing snapshot IDs;
- PDF export does not call DB, scanner, fetch, or technical builder.

## 14. Migration Design

Design-only future sequence:

1. Freeze the current accepted research snapshot decision.
2. Create separated store paths.
3. Move mutable live cache responsibilities to the live store.
4. Redirect research modules to ResearchDataStore.
5. Redirect live scanner modules to LiveDataStore.
6. Validate Phase 7, Phase 3, Phase 4, backtest, replay, walk-forward, and OOS reproducibility.
7. Only after validation, consider deprecating direct `data/stocks.db` access.

No migration is executed in this phase.

## 15. Rollback Design

Rollback should use configuration rather than file restore as the first line:

- retain old DB path support behind a feature flag during transition;
- keep both old and new paths readable during validation;
- allow switching scanner back to the old live DB path if LiveDataStore rollout fails;
- keep research snapshots immutable so research rollback is a snapshot selection change;
- record the exact DB path and snapshot ID in every artifact.

## Phase 2 Boundary Decision

Recommended future boundary:

```text
ResearchDataStore: snapshot-addressed, read-only, deterministic
LiveDataStore: mutable cache, refresh-capable, never canonical by default
PDF Export: snapshot consumer, no DB access
```
