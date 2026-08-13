# Physical Store Separation Planning Phase 6D-1

## 1. Current State

Phase 6D-1 is planning only. It does not create a research database, create a live database, copy `data/stocks.db`, run migrations, switch paths, execute scanners, fetch from Yahoo, or change dashboard/PDF behavior.

Current baseline:

- Git baseline: `HEAD == origin/main == 766571828b730faf8ee5ede8f22e37b9177598bf`.
- Current combined database: `data/stocks.db`.
- Current production DB SHA: `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa`.
- Current `historical_prices` rows: `1185744`.
- Current symbol count in `historical_prices`: `222`.
- Current DB integrity: `ok`.
- Research boundary: `PASS`.
- Live boundary: `PASS`.
- Physical separation: `NOT STARTED`.

Future target:

```text
data/
  research/
    snapshots/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
    manifests/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json
  live/
    stocks_live.db
```

The path names above are a design target only. Phase 6D-1 does not create these files or directories.

## 2. Current Table Inventory

| Table | Rows | Purpose | Current Usage |
| --- | ---: | --- | --- |
| `historical_prices` | `1185744` | OHLCV, `adjusted_close`, currency, and fetched timestamp by `symbol` and `trading_date`. | Research validations, scanner price series, replay/OOS/walk-forward services, current app cache, and snapshot manifest lineage. |
| `historical_price_fetch_state` | `222` | Mutable full-history coverage and latest fetch state by symbol. | Live cache freshness, refresh decisions, and current Yahoo-backed price service behavior. |
| `stocks` | `7` | Current company/profile/valuation/cache metadata. | Current market panels, stock query/cache, comparison views, and profile context. |
| `historical_financials` | `17` | Financial statement history and ratios by symbol and period. | Historical financial views, AI/research context, and live Yahoo-backed financial cache. |
| `research_universes` | `2` | Saved user/research universe metadata. | Existing saved universe workflow and current logical universe storage. |
| `research_universe_symbols` | `5` | Symbols and order within saved research universes. | Existing saved universe membership and ordering. |

## 3. Table Ownership Matrix

| Table | Current Owner | Future Owner | Migration Action | Risk |
| --- | --- | --- | --- | --- |
| `historical_prices` | Combined legacy DB | Shared / Split | Materialize immutable research snapshot copy; keep live mutable copy or overlay for refresh. | Highest. Drift in `adjusted_close`, provider vintage, or row coverage can invalidate reproduced research semantics. |
| `historical_price_fetch_state` | Combined legacy DB | Live only | Exclude from research snapshots; initialize only in live DB from the selected live strategy. | Medium. Accidentally including it in research snapshots would import live freshness state into immutable research. |
| `stocks` | Combined legacy DB | Shared / Split | Keep mutable profile/cache fields in live; optionally snapshot minimal listing metadata needed for research identity. | Medium. Live valuation/profile fields are time-varying and should not become research evidence unless explicitly frozen. |
| `historical_financials` | Combined legacy DB | Shared / Split | Use live for mutable cache; only include frozen financial rows in research snapshots when a research artifact explicitly depends on them. | Medium. Financial restatements and provider updates can silently change research results if not frozen. |
| `research_universes` | Combined legacy DB | Split | Move user-editable saved universes to live; represent released research universes in manifests or immutable snapshot metadata. | Medium. User watchlists/saved universes and released research universes have different mutability. |
| `research_universe_symbols` | Combined legacy DB | Split | Same as `research_universes`; live for mutable user universes, research snapshot metadata for released/frozen universes. | Medium. Ordering and point-in-time identity must be preserved for research reproducibility. |

Ownership categories:

- Research only: released snapshot price data and immutable research universe metadata.
- Live only: fetch state, mutable caches, live stock profile data, user-editable saved universes.
- Shared / Split: `historical_prices`, `stocks`, `historical_financials`, and universe tables when both live and research semantics need the same shape but different mutability.
- Archive: legacy `data/stocks.db` after cutover validation, retained read-only for rollback and audit until deprecation criteria are met.

## 4. Historical Prices Strategy

### Option A: Research copy plus Live copy

Create a physical immutable research DB containing frozen `historical_prices`, and create a separate mutable live DB containing independently refreshable `historical_prices`.

- Consistency: Strong for research because the research copy is immutable.
- Complexity: Moderate. Requires copy/materialization and explicit lineage checks.
- Performance: Good. Both stores can index locally and avoid overlay merging.
- Maintenance: Clear operational model, but duplicate storage must be accepted.

### Option B: Immutable research snapshots plus live mutable overlay

Keep research snapshots immutable and store only live deltas/overlays separately.

- Consistency: Strong if overlay is never applied to research readers.
- Complexity: Higher. Every reader must know whether to compose base plus overlay.
- Performance: Mixed. Reads can become more complex for large universes.
- Maintenance: More moving parts and higher risk of accidental cross-read.

### Option C: Snapshot files plus live database

Represent research snapshots as file artifacts and keep one mutable live database.

- Consistency: Strong if snapshots are immutable and checksummed.
- Complexity: Moderate. Snapshot file lifecycle must be formalized.
- Performance: Good for research reads if snapshot files remain SQLite with local indexes.
- Maintenance: Good. Clear split between artifact files and live mutable DB.

Recommendation: use Option C with the operational shape of Option A. In practice, keep released research snapshots as immutable SQLite files under `data/research/snapshots/`, with manifests under `data/research/manifests/`, and maintain `data/live/stocks_live.db` as the only mutable live database. This avoids overlay complexity while preserving direct SQLite performance and checksum-based research reproducibility.

## 5. Adjusted Close Policy

Research store:

- `adjusted_close` is frozen at snapshot release time.
- Research readers must not refresh, recalculate, or backfill `adjusted_close`.
- Snapshot manifests must record price basis, provider vintage, row coverage, and semantic checksum.

Live store:

- `adjusted_close` remains refreshable through the live historical price pipeline.
- Live refresh can overwrite live cache rows according to live cache policy.
- Live writes must never target research snapshot paths.

Policy rule: live `adjusted_close` updates may create newer live truth, but they cannot mutate or silently supersede released research truth.

## 6. Fetch State Strategy

`historical_price_fetch_state` is live only.

- Research snapshots should not include fetch state.
- Research manifests may include source coverage and provider vintage, but not mutable freshness state.
- Live DB should own full-history freshness, latest fetch date, and cache refresh status.
- Any code path that needs fetch state must use `LiveDataStore`, not `ResearchDataStore`.

## 7. Stocks Table Strategy

`stocks` contains mutable company/profile/valuation fields such as price, market cap, ratios, sector/industry, summary, margins, cash/debt, and moving averages.

Live store:

- Owns current quote/profile/cache fields.
- Supports current market panel, stock search, comparison, and live AI context.
- May refresh from external providers.

Research store:

- Should include only stable listing identity fields when a released research artifact requires them.
- Candidate research fields: `symbol`, `company_name`, `currency`, `sector`, `industry`, and optional listing/universe metadata.
- Should exclude current price, market cap, valuation ratios, current averages, fetched freshness, and profile text unless a specific snapshot formally freezes them with provider vintage and checksums.

## 8. Financial Data Strategy

`historical_financials` is split by use case.

Live store:

- Owns mutable Yahoo-backed financial cache.
- Can refresh financial statements and restated values.
- Supports current financial panels and AI context.

Research store:

- Includes frozen financial rows only when a released research artifact depends on financial features.
- Snapshot policy must record provider vintage, fiscal period coverage, currency, restatement policy, and semantic checksum.
- Current Released Research Snapshot v1 excludes `historical_financials`, so Phase 6D initial research store should not add it to that snapshot.

## 9. Universe Strategy

Current `research_universes` and `research_universe_symbols` are mutable logical universe tables in the combined DB.

Future ownership:

- Live DB: user-editable saved universes, watchlists, and current UI universe selections.
- Research store/manifest: released research universe identity, ordered membership, source version, point-in-time limitations, and semantic checksum.

Frozen TWSE 218:

- Treat `frozen_twse_research_universe_2026_08_09` / `2026-08-current-etf-constituent-v1` as released research universe metadata.
- Preserve the limitation that it is a 2026 current ETF constituent-derived research universe, not a full Taiwan market universe and not a 2018-2025 point-in-time membership reconstruction.

Future point-in-time universes:

- Should be new immutable research snapshot metadata or separate universe snapshot artifacts.
- Must not be inferred from live saved-universe tables.

## 10. Physical Directory Design

Target design:

```text
data/
  research/
    snapshots/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
    manifests/
      research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json
  live/
    stocks_live.db
  stocks.db
```

`data/stocks.db` remains as legacy combined DB during transition. It should not be deleted or overwritten during cutover. It becomes a retained rollback/audit artifact after acceptance.

## 11. Migration Plan

### Step 0: Backup/current state

- Capture SHA, size, row counts, symbol count, duplicate count, schema, and integrity for `data/stocks.db`.
- Risk: missing baseline prevents rollback verification.
- Rollback: keep legacy path active; no config cutover yet.

### Step 1: Freeze research snapshot

- Select Released Research Snapshot v1 as the initial research source.
- Confirm manifest identity, semantic checksum, Phase 7/3/4 reproduction references, and limitations.
- Risk: accidentally using current live DB instead of released snapshot semantics.
- Rollback: do not proceed to materialization until manifest and checksum pass.

### Step 2: Create physical stores

- Future implementation creates `data/research/snapshots/` and `data/live/` under an explicit migration phase.
- Risk: path creation or DB creation in the wrong phase.
- Rollback: remove only newly created empty artifacts if no cutover occurred; retain legacy DB.

### Step 3: Materialize research store

- Materialize immutable research SQLite snapshot from Released Research Snapshot v1 semantics.
- Include only allowed datasets from the manifest.
- Risk: row-count or semantic checksum mismatch.
- Rollback: discard materialized candidate and keep legacy config.

### Step 4: Move live mutable paths

- Create or initialize `data/live/stocks_live.db` from selected live strategy.
- Risk: importing polluted or stale current DB state without explicit acceptance.
- Rollback: keep legacy live path until live validation passes.

### Step 5: Switch configuration

- Switch `research_db_path`, `live_db_path`, `research_snapshot_id`, and `manifest_path` through config/feature flags.
- Risk: mixed readers still use `data/stocks.db`.
- Rollback: config flag returns all active runtime paths to legacy.

### Step 6: Validate

- Run checksum, semantic reproduction, scanner, dashboard, PDF, live refresh, no-cross-write, and no-old-path tests.
- Risk: tests pass in isolation but app still has direct legacy references.
- Rollback: keep feature flag off and leave legacy DB active.

### Step 7: Deprecate legacy

- Mark `data/stocks.db` as legacy read-only audit artifact after all acceptance checks pass.
- Risk: premature removal breaks hidden dependencies.
- Rollback: retain file and config switch until no-old-path dependency is proven.

## 12. Canonical Research Snapshot Usage

Released Research Snapshot v1 is the initial research source:

- `snapshot_id`: `research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1`.
- `status`: `RELEASED`.
- `research_window`: `2018-01-01` to `2025-12-31`.
- `price_data_end`: `2026-08-07`.
- Included datasets: `historical_prices`, Candidate A price universe metadata, Frozen TWSE 218 research universe metadata reference.
- Excluded datasets: `stocks`, `historical_financials`, `historical_price_fetch_state`, features, targets, outcomes, scanner outputs, PDF exports, and AI model artifacts.

Do not modify the snapshot or manifest during physical separation planning.

## 13. Live Store Initial State

Two live initialization strategies should be evaluated in the implementation phase:

1. Current live DB seed:
   - Start `stocks_live.db` from current `data/stocks.db` live cache contents.
   - Pro: preserves cache warmth and current app behavior.
   - Con: imports existing pollution and mixed research/live history unless explicitly accepted.

2. Fresh live cache:
   - Start `stocks_live.db` empty or minimally initialized and let live cache rebuild through explicit live operations.
   - Pro: clean boundary and avoids carrying research-era artifacts.
   - Con: first refreshes are slower and require provider availability.

Recommendation: use current live DB seed only if accompanied by an explicit baseline audit and acceptance that current live state is mutable cache, not research truth. Otherwise use a fresh live cache for cleaner separation.

## 14. Config Cutover Design

Future config contract:

- `legacy_db_path`: `data/stocks.db`, retained for transition and rollback.
- `research_db_path`: immutable released research SQLite snapshot.
- `live_db_path`: mutable live SQLite database.
- `research_snapshot_id`: active released research snapshot identity.
- `manifest_path`: active research snapshot manifest.
- Feature flag: controls whether physical split is active.

Cutover rule:

- Research readers resolve only `research_db_path` and `manifest_path`.
- Live readers/writers resolve only `live_db_path`.
- Legacy path is read-only fallback until deprecation.
- No service should choose `data/stocks.db` implicitly after cutover.

## 15. Acceptance Criteria

Physical separation is acceptable only when all checks pass:

- Research checksum preserved.
- Research semantic checksum preserved.
- Phase 7 reproduced.
- Phase 3 reproduced.
- Phase 4 reproduced.
- Scanner current workflow works through live DB.
- Dashboard current market panels work through live DB.
- Dashboard research evidence panels work through research snapshot.
- PDF export remains snapshot-result-only and does not read DB directly.
- Live refresh works and writes only to live DB.
- Research DB is read-only and cannot be written by live paths.
- Live store cannot target research path.
- Research store cannot accidentally read live path.
- No direct old-path dependency remains in runtime services after cutover.
- Legacy `data/stocks.db` remains available for rollback until explicit deprecation.

## 16. Rollback Plan

Rollback should rely on config and feature flags, not only DB restore.

- Keep `data/stocks.db` unchanged and available during cutover.
- Keep `legacy_db_path` in `DatabasePathConfig`.
- Introduce a split-store feature flag before switching defaults.
- If validation fails, turn the flag off and route both research and live paths back to legacy behavior.
- Do not delete split-store candidate files until acceptance is final.
- Preserve created split-store artifacts for forensic comparison when rollback is triggered.

## 17. Test Strategy

Research DB tests:

- Open research DB with `mode=ro`.
- Assert `PRAGMA query_only=ON`.
- Verify manifest identity and snapshot ID.
- Verify row counts, symbol counts, duplicate count, integrity, checksum, and semantic checksum.
- Confirm forbidden live tables such as `historical_price_fetch_state` are absent unless explicitly allowed by snapshot spec.

Live DB tests:

- Initialize temp live DB only.
- Verify writes for stock cache, historical prices, financials, and fetch state.
- Verify refresh code writes to live DB, not legacy or research DB.
- Mock Yahoo/provider fetches in tests.

Boundary tests:

- `LiveDataStore` cannot target research snapshot paths.
- `ResearchDataStore` cannot write.
- Test environment blocks production `data/stocks.db` unless explicit integration permission is set.
- Current scanner requires injected live store or explicit live path.
- Research services cannot use `LiveDataStore`.
- PDF export cannot call scanner, price fetch, or SQLite.

## 18. Performance Review

Research snapshot loading:

- SQLite snapshot files are appropriate for current scale.
- Add indexes matching `symbol`, `trading_date`, and universe lookup before release materialization.
- Prefer short-lived read-only connections unless repeated batch reads justify a local read cache.

Live cache access:

- Current SQLite pattern is acceptable for single-user/local app workflows.
- Avoid connection pooling until concurrent write contention is observed.
- Use explicit transactions for bulk refreshes.

Cache layer:

- Research readers may use in-process memoization keyed by snapshot ID and symbol.
- Live readers should avoid stale in-process cache across refresh unless invalidation is explicit.

## 19. PDF and Dashboard Impact

PDF:

- Target remains `Scan Result Snapshot -> PDF`.
- PDF export should not depend on `ResearchDataStore`, `LiveDataStore`, `get_historical_prices`, or direct SQLite.
- Existing PDF boundary tests should remain part of acceptance.

Dashboard:

- Current Market Panel uses live store.
- Research Evidence uses research snapshot.
- The dashboard should not decide physical paths directly; it should call services with the correct store boundary.
- UI behavior should not change during physical cutover except for improved safety.

## 20. Phase 6D-1 Decision

Phase 6D-1 planning status: `PASS`.

Pre-commit blocker:

- Physical separation is still planning-only.
- Do not commit until a follow-up review confirms the planning document, DB proof, and preserved Phase 6C/PDF changes.
- Do not start Phase 6D physical implementation until an explicit implementation phase authorizes DB creation/materialization/cutover.
