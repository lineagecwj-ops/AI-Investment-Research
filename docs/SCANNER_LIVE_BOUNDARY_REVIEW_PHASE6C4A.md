# Scanner Live Boundary Review Phase 6C-4A

## 1. Current Scanner Flow

Phase 6C-4A is an audit and documentation phase only. It does not modify
scanner code, Production V1, V1.1, technical formulas, Dashboard, PDF Export,
database files, migration logic, commits, or pushes.

Current Swing Scanner runtime flow:

```text
User request
  -> app.py build_swing_research_scan_result()
  -> recording_price_loader()
  -> historical_price_service.get_historical_prices()
  -> LiveDataStore
  -> cached or refreshed live historical prices
  -> SwingScannerService.scan()
  -> build_technical_indicator_series()
  -> evaluate_signal_conditions(..., TECHNICAL_EXAMPLE_SIGNAL_V1)
  -> run_historical_backtest()
  -> rank_swing_candidates()
  -> SwingScannerResult
  -> Dashboard current scan panel
  -> optional PDF export from Scan Result Snapshot
```

`SwingScannerService` itself is dependency-injected. Its default price loader is
`get_historical_prices`, but tests and research projections can provide another
loader explicitly.

## 2. Data Dependencies

| File | Function / entry | Data dependency | Current classification |
|---|---|---|---|
| `src/swing_scanner_service.py` | `SwingScannerService.scan()` | injected `price_loader`, `technical_builder`, `backtest_runner` | Scanner orchestration; no direct DB access |
| `src/swing_scanner_service.py` | `_scan_symbol()` | price series from loader, technical series, Production V1 signal definition | Scanner orchestration; no direct DB access |
| `src/swing_scanner_service.py` | `scan_swing_opportunities()` | default `SwingScannerService()` | Current scanner convenience entry |
| `app.py` | `build_swing_research_scan_result()` | `get_historical_prices()` through `recording_price_loader()` | Current live scanner flow |
| `src/historical_price_service.py` | `get_historical_prices()` | `LiveDataStore` cache read/write and Yahoo fallback | LiveDataStore boundary |
| `src/live_data_store.py` | `get_cached_historical_prices()` / `save_historical_prices()` | legacy live path for now | LiveDataStore boundary |
| `src/research_data_store.py` | `load_historical_price_series()` | read-only snapshot reader | ResearchDataStore boundary, not scanner runtime |
| `src/historical_replay_service.py` | `HistoricalReplayService` | default `get_historical_prices()` unless injected | Historical workflow; future explicit source split needed |
| `src/walk_forward_replay_service.py` | `WalkForwardReplayService` | default `get_historical_prices()` unless injected | Historical workflow; future explicit source split needed |
| `src/out_of_sample_validation_service.py` | `OutOfSampleValidationService` | default `get_historical_prices()` unless injected | Historical workflow; future explicit source split needed |
| `src/swing_scanner_pdf_export_service.py` | `export_swing_scanner_pdf()` | `SwingScannerResult` and coverage view | No DB access |

## 3. Live / Research Classification

Current scanner:

```text
LiveDataStore
```

Reason:

- scanner uses scan-time market cache data;
- cache miss / stale cache path can call Yahoo through `get_historical_prices`;
- cache writes now enter through `LiveDataStore`;
- scan result represents a current scan snapshot, not a released research
  snapshot.

Research evidence:

```text
ResearchDataStore
```

Reason:

- Phase 7, Phase 3, Phase 4, condition coverage, and frozen research evidence
  require deterministic released snapshot lineage;
- ResearchDataStore opens SQLite through `mode=ro` and `PRAGMA query_only=ON`;
- ResearchDataStore is not used by the current scanner runtime.

## 4. Price Data Access Classification

| Access path | Direct DB access? | Store boundary | Notes |
|---|---:|---|---|
| `SwingScannerService.scan()` | No | Injected loader | No `sqlite3.connect`, no manifest read |
| `scan_swing_opportunities()` | No | Defaults to `get_historical_prices()` | Indirect live path |
| `app.py build_swing_research_scan_result()` | No direct DB access | Calls `get_historical_prices()` | Records price series for scan snapshot |
| `historical_price_service.get_historical_prices()` | No direct writer after 6C-3 | LiveDataStore | May fetch Yahoo if cache misses or `force_refresh=True` |
| `LiveDataStore.save_historical_prices()` | Yes, via database primitive | LiveDataStore | Mutable cache boundary |
| `ResearchDataStore.load_historical_price_series()` | Yes, read-only only | ResearchDataStore | Not a scanner runtime dependency |
| `app.py load_historical_price_series_from_cache_read_only()` | Yes, read-only direct legacy path | Historical case / cache preview gap | Not current scanner runtime |

Scanner price access does not currently depend on ResearchDataStore or released
snapshot manifests.

## 5. Technical Pipeline Dependency

`SwingScannerService._scan_symbol()` uses:

- scan-time `HistoricalPriceSeries`;
- `build_technical_indicator_series(price_series)`;
- latest technical snapshot;
- `evaluate_signal_conditions(latest_snapshot, config.signal_definition)`;
- `run_historical_backtest(price_series, technical_series, config.to_backtest_config())`.

No dependency was found on:

- Research Snapshot manifest;
- Phase 7 artifact;
- Phase 3 artifact;
- Phase 4 artifact;
- `ResearchDataStore`;
- direct SQLite access inside `SwingScannerService`.

## 6. Cache Refresh Path

When current scanner lacks usable cached data:

```text
SwingScannerService
  -> price_loader
  -> historical_price_service.get_historical_prices()
  -> LiveDataStore.get_cached_historical_prices()
  -> Yahoo fetch if needed
  -> LiveDataStore.save_historical_prices()
```

This is live behavior. It must remain outside ResearchDataStore and must not
mutate released research snapshots.

## 7. Production Safety

Production V1 safety findings:

- `TECHNICAL_EXAMPLE_SIGNAL_V1` remains the scanner signal definition in app
  current scan flow.
- `SwingScannerService` qualification logic was not modified in this phase.
- Ranking remains `rank_swing_candidates()` using the existing rank key.
- Technical formulas remain owned by `technical_indicator_service`.
- Backtest behavior remains owned by `backtest_service`.

This review did not change Production V1 semantics.

## 8. V1.1 Safety

V1.1 shadow logic is separate from current scanner runtime:

- `v1_1_shadow_scanner_service.py` uses explicit V1/V1.1 comparison logic;
- `app.py` keeps the V1.1 dashboard as an experimental comparison;
- scanner runtime does not switch Production V1 to V1.1.

No V1.1 runtime dependency change was made in this phase.

## 9. Dashboard Flow

Current dashboard flow should remain separated:

| Panel | Future store | Rule |
|---|---|---|
| Current Market Panel / current scanner | LiveDataStore | Mutable, current cache, Yahoo fallback allowed by live policy |
| Research Evidence Panel | ResearchDataStore | Immutable, released snapshot lineage |
| Historical replay / walk-forward / OOS | Explicit source required in future | Currently defaults to live loader unless injected |

This phase does not change Dashboard behavior.

## 10. PDF Flow

PDF Export remains:

```text
Scan Result Snapshot
  -> coverage view
  -> export_swing_scanner_pdf()
  -> PDF bytes
```

`src/swing_scanner_pdf_export_service.py` consumes scanner result objects and
coverage view objects. It should not open ResearchDataStore, LiveDataStore, or
SQLite directly.

## 11. Research / Live Mixing Findings

Findings:

- Current scanner runtime has no `ResearchDataStore` import.
- Current scanner runtime has no Research Snapshot manifest dependency.
- `SwingScannerService` has no `sqlite3.connect`.
- Current scanner cache read/write path is live through
  `historical_price_service.get_historical_prices()` and `LiveDataStore`.
- Phase 3 research projection intentionally injects a read-only research loader
  into `SwingScannerService`; that is a research workflow, not current scanner
  runtime.

Risk area:

- Historical replay, walk-forward replay, and OOS services still default to
  `get_historical_prices()` when no explicit price series or loader is injected.
  Future phases should force explicit live vs research source selection for
  these historical workflows.

## 12. Migration Gaps

Current distance to the desired LiveDataStore scanner boundary:

| Gap | Current state | Risk | Future resolution |
|---|---|---|---|
| Scanner constructor default | `price_loader=get_historical_prices` | Live source is implicit | Phase 6C-4B can inject or wrap a named LiveDataStore loader |
| App recording loader | calls `get_historical_prices()` without explicit LiveDataStore | Boundary exists but not visible in scanner call site | Pass a LiveDataStore-backed loader explicitly |
| Historical replay / walk-forward / OOS defaults | default live loader unless injected | Research workflows may accidentally use mutable live cache | Require explicit source mode or ResearchDataStore loader for research modes |
| Historical case read-only helper in `app.py` | direct `sqlite3.connect(...mode=ro)` | Legacy direct read remains outside store abstraction | Migrate to explicit ResearchDataStore or LiveDataStore read policy in later phase |
| Source labels | current scan result does not expose store identity | Audit trail can be unclear | Add non-invasive source metadata in scan snapshot, not in scanner ranking logic |

## 13. Future Phase 6C-4B Plan

Recommended Phase 6C-4B scope:

1. Add a small LiveDataStore-backed price loader factory for current scanner.
2. Wire `app.py build_swing_research_scan_result()` to pass that loader
   explicitly.
3. Preserve `SwingScannerService` ranking, qualification, formulas, backtest,
   and result contract.
4. Add scanner regression tests proving matched/no-match ordering is unchanged.
5. Add a test proving current scanner path does not import or instantiate
   ResearchDataStore.
6. Add a test proving PDF Export still receives only Scan Result Snapshot data.
7. Keep historical replay / OOS source-selection changes separate unless
   explicitly authorized.

Do not include in Phase 6C-4B unless separately authorized:

- Research DB creation;
- live DB creation;
- DB migration;
- Yahoo behavior changes;
- Production V1 / V1.1 semantic changes;
- PDF Export behavior changes.

## 14. Test Impact Plan

Future validation should include:

- scanner regression tests for `MATCH`, `NO_MATCH`, `NOT_EVALUABLE`, and
  failure behavior;
- Production V1 identity test for `TECHNICAL_EXAMPLE_SIGNAL_V1`;
- rank ordering unchanged test;
- technical snapshot unchanged test using fixed input price series;
- LiveDataStore loader invocation test;
- ResearchDataStore non-dependency test for current scanner;
- PDF Export no-SQLite test;
- Dashboard current scan source-label test if metadata is added.

## 15. DB Safety

Production DB reference:

```text
data/stocks.db
sha256 = 69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7
rows = 1185308
symbols = 222
duplicates = 0
integrity = ok
```

Phase 6C-4A performed read-only inspection and documentation only.

## 16. Stop Gate

Stop at Phase 6C-4A Review Gate.

Do not proceed in this phase to:

- modify scanner code;
- modify Production V1;
- modify V1.1;
- modify technical formulas;
- modify Dashboard;
- modify PDF Export;
- create a live DB;
- run migration;
- write SQLite;
- fetch Yahoo;
- execute scanner workflows;
- commit;
- push.
