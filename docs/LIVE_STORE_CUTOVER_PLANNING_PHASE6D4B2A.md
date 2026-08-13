# Live Store Cutover Planning Phase 6D-4B-2A

## 1. Objective

Phase 6D-4B-2A designs the future Live Store cutover plan only.

This phase does not create `data/live/`, create `stocks_live.db`, copy production DB, run migrations, switch paths, execute scanner workflows, fetch from Yahoo, change Dashboard/PDF behavior, commit, or push.

Cutover objective:

```text
Before:
  data/stocks.db

After:
  data/live/stocks_live.db

Managed by:
  LiveDataStore
```

Current decision:

```text
Live initialization strategy = Option B Fresh Live Cache
implementation_status = planning only
```

## 2. Target Architecture

Future physical store layout:

```text
data/
  research/
    snapshots/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
    manifests/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_manifest.json
  live/
    stocks_live.db
  stocks.db
```

Live Store target contents:

- `historical_prices`
- `historical_price_fetch_state`
- `stocks`
- `historical_financials`
- runtime metadata required for live cache operations
- mutable user/saved universe tables if those workflows remain DB-backed

Live Store must exclude:

- Research Snapshot rows or metadata;
- Research Store manifests;
- Phase 7 artifacts;
- Phase 3 artifacts;
- Phase 4 artifacts;
- PDF outputs;
- scanner result snapshots;
- AI / Long-Term Growth artifacts.

Research Store remains immutable and read-only. Live Store is mutable current cache.

## 3. Initialization

Recommended future implementation path:

1. Keep the split-store feature flag disabled.
2. Capture production `data/stocks.db` baseline fingerprint.
3. Create `data/live/` and an empty `stocks_live.db` only in the authorized implementation phase.
4. Initialize the live schema with the current live schema contract.
5. Insert live-store metadata recording:
   - live store creation timestamp;
   - initialization strategy `fresh_live_cache`;
   - schema version;
   - repository baseline;
   - no source seed DB.
6. Keep `data/stocks.db` unchanged as legacy fallback.
7. Do not copy production DB rows into the fresh live DB.

Fresh cache rationale:

- It gives the cleanest provenance.
- It avoids inheriting known prior validation contamination from `data/stocks.db`.
- It makes every live row attributable to post-cutover live operations.

## 4. Warm-Up

Cold-start behavior:

- The initial live DB may have schema but no cache rows.
- Current market panels must handle missing cache clearly.
- Scanner current workflow must either:
  - perform explicit controlled refresh through `LiveDataStore`, or
  - fail gracefully with an actionable stale/missing data message.

Warm-up priorities:

1. Minimal smoke symbols:
   - a small fixed set of local symbols used by tests and app smoke validation.
2. Current scanner source universe:
   - `研究股票池（Frozen TWSE 218）` only if explicitly authorized for warm-up.
3. Stock/profile cache:
   - current price and company metadata for UI panels.
4. Historical financial cache:
   - only for dashboard panels that need financial statements.
5. Fetch state:
   - updated only by successful live refresh writes.

Warm-up rules:

- No Yahoo/network calls in tests.
- Provider calls must be mocked until an explicit live refresh phase authorizes real provider access.
- Warm-up must write only to `data/live/stocks_live.db`.
- Warm-up must not write to Research Store or `data/stocks.db`.

## 5. Scanner Cutover

Before cutover:

```text
Scanner
  -> LiveDataStore(default legacy path)
  -> data/stocks.db
```

After cutover:

```text
Scanner
  -> LiveDataStore(live_db_path)
  -> data/live/stocks_live.db
```

Required scanner cutover steps:

1. Add config/feature-flag path resolution for `live_db_path`.
2. Ensure app current scan builder passes explicit `LiveDataStore(db_path=live_db_path)`.
3. Keep `SwingScannerService` injected-store behavior unchanged.
4. Run scanner regression with mocked temp live data first.
5. Run live-store smoke scan only after the future live DB is initialized.

Production V1 safety:

- Do not modify `TECHNICAL_EXAMPLE_SIGNAL_V1`.
- Do not modify V1.1.
- Do not change technical formulas.
- Do not change ranking, ordering, MATCH/NO_MATCH semantics, probabilities, or recommendations.
- Cutover affects storage location only.

## 6. App Cutover

Future app behavior:

- Current Market Panel resolves data through `LiveDataStore(live_db_path)`.
- Swing current scan path resolves prices through `LiveDataStore(live_db_path)`.
- Research Evidence panels resolve data through `ResearchDataStore(research_db_path, manifest_path)`.
- PDF Export remains independent of physical DB location.

App cutover requirements:

- Add explicit config object or resolver for live/research paths.
- Make active paths observable in diagnostics.
- Fail closed if live path is missing while split-store flag is enabled.
- Keep legacy fallback available only when the feature flag is disabled.

## 7. Config

Recommended feature/config contract:

```text
use_physical_store_split = false | true
live_db_path = data/live/stocks_live.db
research_db_path = data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
research_snapshot_id = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
manifest_path = data/research/manifests/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_manifest.json
legacy_db_path = data/stocks.db
```

Cutover stages:

1. Flag off: all production behavior remains legacy.
2. Flag on in tests: services use temp live/research paths.
3. Flag on in local dry run: app services use candidate physical paths, no real provider calls.
4. Flag on for production local app: only after validation checklist passes.

Config safety:

- If `use_physical_store_split=true` and `live_db_path` is missing, abort current/live workflows.
- If `research_db_path` checksum does not match expected Research Store Candidate, abort research workflows.
- Never silently fall back from a missing live DB to Research Store.

## 8. Rollback

Rollback should rely on config/feature flags, not DB restore.

Rollback plan:

1. Disable `use_physical_store_split`.
2. Route live workflows back to legacy `data/stocks.db`.
3. Leave `data/live/stocks_live.db` intact for forensic inspection.
4. Keep Research Store unchanged.
5. Capture failure reason and DB fingerprints.
6. Re-enable split only after fixing and revalidating.

Rollback triggers:

- Live DB initialization failure.
- Warm-up failure.
- Scanner regression.
- Unexpected write to `data/stocks.db`.
- Unexpected write to Research Store.
- Research checksum mismatch.
- Dashboard current panels cannot load required live data.

## 9. Validation

Required post-cutover validation checklist:

- Scanner works against `data/live/stocks_live.db`.
- Production V1 identity unchanged.
- V1.1 unchanged.
- Dashboard current market panels work against Live Store.
- Research Evidence panels work against Research Store.
- PDF export works from scan result snapshots and does not read DB directly.
- Research Store checksum unchanged.
- Phase 7/3/4 reproduction readiness unchanged.
- Live refresh writes only to Live DB.
- Research readers cannot write.
- Live writers cannot target Research Store.
- No direct old-path dependency remains in current live runtime paths.
- `data/stocks.db` remains unchanged during split-store validation.

Pre-cutover validation:

- Run temp live dry-run tests.
- Run Research Store read-only tests.
- Run no-production-write tests.
- Run scanner dependency injection tests with temp live store.
- Run app source-level path resolution tests.

Post-cutover validation:

- Run full unit test suite.
- Run focused scanner/dashboard/PDF/research tests.
- Compare `data/stocks.db` before/after SHA.
- Compare Research Store before/after SHA.
- Verify Live Store row/fetch-state deltas only in `data/live/stocks_live.db`.

## 10. Failure Handling

### Live DB initialization failure

Response:

- Stop cutover.
- Keep feature flag disabled.
- Do not retry against `data/stocks.db`.
- Record schema error and temp/live DB path.

### Cache warm-up failure

Response:

- Keep live DB candidate for inspection.
- Do not switch scanner/dashboard to split mode.
- Report failed symbols, provider/mock status, and partial row counts.

### Scanner regression

Response:

- Disable split flag.
- Confirm V1/V1.1 definitions unchanged.
- Compare injected temp live results with legacy fixture expectations.

### Unexpected DB write

Response:

- Stop immediately.
- Capture before/after SHA, rows, symbols, integrity for affected DB.
- Do not restore automatically.
- Report root cause and write call graph.

### Rollback trigger

Response:

- Disable flag.
- Preserve all candidate stores.
- Use legacy path until a new authorized phase fixes the issue.

## 11. Observability

Cutover should expose:

- active live DB path;
- active research DB path;
- active research snapshot ID;
- active manifest path;
- manifest version/status;
- Research Store checksum;
- Live Store existence and schema version;
- last live refresh time;
- latest `historical_price_fetch_state.latest_date`;
- split-store feature flag state;
- fallback mode state.

Observability should be available in diagnostics/logging, not as noisy user-facing text on normal pages.

## 12. PDF Boundary

PDF remains independent of Live Store location.

Expected contract:

```text
Scan Result Snapshot
  -> PDF Export
```

PDF Export must not directly depend on:

- `data/stocks.db`;
- `data/live/stocks_live.db`;
- Research Store DB;
- provider refresh;
- scanner execution.

## 13. Phase 6D-4B-2A Decision

Phase 6D-4B-2A status:

```text
PASS
```

Safe next step:

```text
Phase 6D-4B-2B may proceed if it remains planning/dry-run or explicitly authorizes formal live DB creation.
```

Still pending:

- formal `data/live/` creation;
- formal `stocks_live.db` creation;
- live warm-up implementation;
- config feature flag implementation;
- scanner/dashboard cutover implementation;
- rollback switch implementation.
