# Live Store Initialization Decision Phase 6D-4A

## 1. Current Live State

Phase 6D-4A is analysis and planning only. It does not create `data/live/`, create `stocks_live.db`, copy `data/stocks.db`, run migrations, switch paths, execute scanners, fetch from Yahoo, modify dashboard/PDF behavior, commit, or push.

Current live database:

```text
path = data/stocks.db
sha256 = def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa
historical_prices_rows = 1185744
symbols = 222
integrity = ok
historical_price_coverage = 1980-12-12 to 2026-08-11
latest_fetched_at = 2026-08-12T00:40:48.174668+00:00
```

Current table inventory:

| Table | Rows | Live relevance |
| --- | ---: | --- |
| `historical_prices` | `1185744` | Live historical cache for scanner/current workflows. |
| `historical_price_fetch_state` | `222` | Live refresh state and cache coverage metadata. |
| `stocks` | `7` | Current stock profile/quote cache. |
| `historical_financials` | `17` | Current historical financial cache. |
| `research_universes` | `2` | Mutable saved/research universe records in legacy DB. |
| `research_universe_symbols` | `5` | Mutable universe membership/order in legacy DB. |

Research Store status:

- Research Store Candidate exists under `data/research/snapshots/`.
- Research Store Candidate status is `PASS`.
- `data/live/` is currently absent.

Important live provenance observation:

- Current live DB contains `437` `historical_prices` rows after the Research Snapshot v1 price end date `2026-08-07`.
- `218` symbols have fetch state `latest_date = 2026-08-11`.
- Most historical price rows currently have `fetched_at` on `2026-08-12`.
- Therefore `data/stocks.db` is a mutable live cache candidate, not a research snapshot and not a research-lineage artifact.

## 2. Option A: Current DB Seed

Option A initializes future `data/live/stocks_live.db` from current `data/stocks.db`.

Advantages:

- Fastest startup because historical price cache is already warm.
- Preserves current scanner/cache behavior with minimal first-run refresh burden.
- Preserves existing `historical_price_fetch_state`, which reduces immediate provider calls.
- Easier user experience during cutover because current market panels have local cache coverage.

Risks:

- Provenance is mixed: current `data/stocks.db` has legacy research history, live refresh history, and known prior test contamination.
- It includes live rows after the Research Snapshot v1 cutoff; these rows are useful for live cache but must never become research evidence.
- It may carry stale or polluted fetch-state assumptions into the new live DB.
- It can obscure whether future live behavior is working correctly or only using inherited cache warmth.
- Requires a strict label: mutable live cache seed, not released research data.

Coverage:

- Strong historical price coverage: `222` symbols and `1185744` rows.
- Good live freshness: latest trading date reaches `2026-08-11`.
- Includes current stock and financial caches, but only for small sample coverage (`stocks = 7`, `historical_financials = 17`).

Rollback:

- Easier runtime rollback because the seed resembles existing behavior.
- Harder provenance rollback because inherited rows and fetch state require audit if unexpected behavior appears.

## 3. Option B: Fresh Live Cache

Option B initializes future `data/live/stocks_live.db` as a fresh mutable live cache.

Advantages:

- Cleanest physical separation.
- Best provenance: all rows in the new live DB are created after live-store cutover under explicit live rules.
- Avoids carrying prior validation contamination forward.
- Easier to prove that live refresh, fetch state, and cache writes are working.
- Maintains a clean conceptual split: Research Store is frozen; Live Store is newly mutable.

Risks:

- Cold start: scanner/current panels may need many cache refreshes.
- Higher dependency on Yahoo/provider availability after cutover.
- First-run performance may be slower.
- Requires explicit staged warm-up or controlled initial refresh workflow.
- Requires user-facing handling for missing live cache during early cutover.

Coverage:

- Starts with no historical price coverage or minimal schema-only coverage, depending on implementation.
- Coverage becomes a property of live refresh execution after cutover.
- Requires refresh instrumentation to avoid silent partial coverage.

Rollback:

- Cleaner rollback. If fresh live initialization fails, discard the candidate live DB and keep legacy `data/stocks.db` as fallback.
- Easier to compare live writes because every row has post-cutover provenance.

## 4. Comparison

| Criterion | Option A: Current DB Seed | Option B: Fresh Live Cache |
| --- | --- | --- |
| Startup speed | Best | Slowest unless warmed |
| Cache coverage | Best immediately | Initially empty/minimal |
| Provenance clarity | Weak | Strong |
| Test contamination risk | Higher | Lower |
| Research lineage risk | Higher if mislabeled | Lower |
| LiveDataStore conceptual fit | Acceptable only as mutable seed | Best fit |
| Provider dependency at cutover | Lower | Higher |
| Validation clarity | Lower | Higher |
| Rollback simplicity | Runtime easy, provenance harder | Runtime easy and provenance cleaner |
| Maintenance | Needs seed audits | Needs warm-up strategy |

## 5. Live Data Requirements

Future Live Store must support:

- current prices and stock profile cache;
- historical price cache;
- `historical_price_fetch_state`;
- historical financial cache;
- runtime cache metadata needed by live services;
- mutable saved/user universe workflows if those remain DB-backed.

Future Live Store does not need:

- Research Snapshot DB artifacts;
- Research Snapshot manifests;
- Phase 7 artifacts;
- Phase 3 artifacts;
- Phase 4 artifacts;
- PDF exports;
- scanner result snapshots;
- AI / Long-Term Growth artifacts.

## 6. Future Live Table Ownership

| Table | Future Live Need | Notes |
| --- | --- | --- |
| `historical_prices` | Required | Mutable live cache used by scanner/current workflows. |
| `historical_price_fetch_state` | Required | Live only; drives cache freshness and full-history coverage. |
| `stocks` | Required | Current stock profile/quote cache. |
| `historical_financials` | Required | Current historical financial cache. |
| `research_universes` | Likely required if saved universes remain DB-backed | Treat as mutable user/live data, not released research metadata. |
| `research_universe_symbols` | Likely required if saved universes remain DB-backed | Preserve user ordering; do not confuse with released research universe metadata. |

## 7. Provenance Analysis

Option A provenance:

- Source is current `data/stocks.db`.
- The DB has live rows, legacy research source history, and prior validation write pollution.
- It is usable as a mutable live cache candidate only if explicitly labeled and audited.
- It must not inherit Research Snapshot v1 release status.

Option B provenance:

- Source is a fresh live schema and future explicit refresh operations.
- Every row can be traced to post-cutover live refresh or user action.
- It better matches the purpose of `LiveDataStore` as mutable current data.

Provenance conclusion:

- Option B is cleaner and safer for architecture.
- Option A is operationally faster but must be treated as a convenience seed, not canonical data.

## 8. Scanner Impact

SwingScannerService already depends on `LiveDataStore` through explicit boundary injection.

Option A:

- Scanner starts with warm historical cache.
- Less first-run latency.
- Risk: inherited stale/polluted rows can affect current scan inputs until refreshed.

Option B:

- Scanner may see cache misses initially.
- Requires controlled refresh or user-facing unavailable/stale handling.
- Better proof that scanner is reading the new live store after cutover.

Production V1 semantics:

- Neither option changes Production V1 formulas, thresholds, ranking, ordering, or scanner semantics.
- Differences are data availability/provenance differences only.

## 9. Dashboard Impact

Current Market Panel:

- Option A gives smoother transition because current cache already exists.
- Option B may require staged cache warm-up and clearer empty/stale-state UI behavior.

Research Evidence:

- Should continue to use Research Store / Research Snapshot.
- Must not depend on the live initialization option.

Dashboard conclusion:

- The dashboard impact is operational, not semantic.
- Future implementation should route current market panels to `LiveDataStore` and research evidence panels to `ResearchDataStore`.

## 10. PDF Impact

PDF Export should not depend on the Live Store seed choice.

The intended contract remains:

```text
Scan Result Snapshot -> PDF
```

PDF Export should not directly read `data/stocks.db`, `data/live/stocks_live.db`, or the Research Store.

## 11. Future Test Strategy

Live Store initialization tests should include:

- create temp live DB;
- verify schema creation;
- verify `LiveDataStore.connect_writable()`;
- verify stock cache write/read;
- verify historical price write/read;
- verify `historical_price_fetch_state` update;
- verify historical financial write/read;
- verify mocked refresh writes only to live DB;
- verify scanner can read through injected temp `LiveDataStore`;
- verify production `data/stocks.db` remains unchanged;
- verify Research Store cannot be targeted by LiveDataStore;
- verify no network fetch unless explicitly authorized and mocked in tests.

If Option A is later selected:

- add source-seed audit tests;
- record seed SHA, row counts, max date, fetch-state counts;
- label seed provenance as mutable live cache.

If Option B is later selected:

- add cold-cache behavior tests;
- add staged warm-up tests;
- verify missing-cache/stale-cache UX behavior without provider dependency.

## 12. Rollback Strategy

Option A rollback:

- Keep `data/stocks.db` as legacy fallback.
- If seeded live DB fails validation, turn off split-store feature flag.
- Discard candidate `stocks_live.db` or retain it only for forensic inspection.
- Re-audit seed provenance before retry.

Option B rollback:

- Keep `data/stocks.db` as legacy fallback.
- If fresh live DB is insufficient, disable split-store feature flag.
- Remove or archive the fresh live candidate.
- Retry with staged warm-up or reconsider Option A seed.

Shared rollback principles:

- Use config switch / feature flag, not DB restore alone.
- Do not delete legacy `data/stocks.db` during initial cutover.
- Do not modify Research Store during live rollback.

## 13. Recommendation

Recommended option: Option B, Fresh Live Cache.

Reasons:

1. It provides the cleanest provenance and best matches `LiveDataStore` as a mutable current-data boundary.
2. It avoids carrying known prior validation contamination and mixed research/live history into the new physical live store.
3. It makes future validation stronger because every live row and fetch state is created by explicit post-cutover live workflows.
4. It lowers the risk that current live cache rows are accidentally interpreted as research lineage.
5. It creates a simpler long-term mental model: Research Store is frozen; Live Store is rebuilt and refreshable.

Operational mitigation:

- Use a staged warm-up plan before cutover.
- Mock provider fetches in tests.
- Keep feature-flag rollback to legacy `data/stocks.db`.
- Consider an explicitly labeled Option A seed only if cold-cache startup is unacceptable.

## 14. Pending Decision

Phase 6D-4A does not execute the choice.

Decision state:

```text
recommended_strategy = Option B Fresh Live Cache
implementation_status = PENDING_APPROVAL
```

Phase 6D-4B should not create `data/live/` unless explicitly authorized.
