# Database Architecture Separation Phase 1

## 1. Current Architecture

`data/stocks.db` is currently a single SQLite file used for both research baselines and live mutable cache data.

Read-only inventory on 2026-08-11:

| Item | Value |
|---|---:|
| Size | 170,819,584 bytes |
| SHA-256 | `69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7` |
| `historical_prices` rows | 1,185,308 |
| `historical_prices` symbols | 222 |
| Duplicate `(symbol, trading_date)` keys | 0 |
| Integrity check | `ok` |
| Journal mode | `delete` |
| Page size | 4,096 |
| Page count | 41,704 |
| Views | none |
| Triggers | none |

Existing tables:

| Table | Rows | Primary ownership today | Current role |
|---|---:|---|---|
| `historical_prices` | 1,185,308 | Shared / Need Separation | Daily OHLCV, adjusted close, actions, currency, and fetched timestamp. Used by both historical research and live scanner cache refresh. |
| `historical_price_fetch_state` | 222 | Live Only | Mutable coverage and freshness state for price cache fetches. |
| `stocks` | 7 | Live Only | Mutable company profile, current quote, valuation, margins, growth, and Yahoo-derived metadata cache. |
| `historical_financials` | 17 | Shared / Need Separation | Historical fundamentals cache; can support research, but current fetch and cache semantics are mutable. |
| `research_universes` | 2 | Shared / Need Separation | User-managed saved universes. These are research inputs, but currently live-editable in the same DB. |
| `research_universe_symbols` | 5 | Shared / Need Separation | Ordered saved-universe membership. |

The only explicit foreign key is `research_universe_symbols.universe_id -> research_universes.id`. SQLite `foreign_keys` was off in the inspected file.

## 2. Current Conflict

The central conflict is that `historical_prices` acts as both:

- a frozen research baseline for Phase 7, Phase 3 Candidate Display, Phase 4 experimental views, condition coverage research, backtest, replay, walk-forward, and OOS validation; and
- a live Yahoo-backed cache used by current scanner paths and ad hoc dashboard workflows.

Fields most prone to drift:

| Field | Drift risk |
|---|---|
| `adjusted_close` | High. Provider restatements can change technical analysis close because project semantics use `adjusted_close if available else close`. |
| `fetched_at` | High. Mutable cache metadata changes even when price values are unchanged. |
| `historical_price_fetch_state.latest_date` | High. Live refresh extends cache coverage and changes freshness interpretation. |
| `historical_price_fetch_state.full_history_fetched` | Medium. Full-history state controls whether cache satisfies loader requirements. |
| `open`, `high`, `low`, `close`, `volume`, `dividends`, `stock_splits`, `currency` | Medium. Provider corrections are possible and research-relevant. |

The current `get_historical_prices()` path can fetch from Yahoo and then call `save_historical_prices()`, which performs an upsert into `historical_prices` and updates `historical_price_fetch_state`. In contrast, research services already have read-only loaders using SQLite URI `mode=ro` and, in some cases, `PRAGMA query_only=ON`.

## 3. Research DB Proposal

Future target path:

```text
data/research/stocks_research.db
```

Purpose: immutable or controlled-update research store.

Recommended contents:

| Data family | Notes |
|---|---|
| Frozen historical OHLCV | Versioned `historical_prices` equivalent used by research jobs. |
| Historical price metadata | Snapshot checksum, source, generation time, row count, symbol count, date range, and provenance. |
| Universe snapshots | Frozen TWSE 218, listing dates, source artifacts, membership lineage, and version IDs. |
| Signal snapshots | Point-in-time feature inputs for backtest, replay, OOS, and future AI datasets. |
| Outcome snapshots | Validated historical outcomes and semantic checksums. |
| Feature datasets | Point-in-time feature tables; every feature must be derivable from data available at or before observation date. |
| Target labels | Future outcome labels such as Long-Term Growth targets; stored separately from features. |
| Research artifacts registry | Links to JSON outputs, semantic checksum, source DB SHA, code version, and config fingerprints. |

Rules:

- Direct live refresh must not write to the research DB.
- Any research DB change must be versioned, checksummed, documented, and reproducible.
- Each research result must state the exact DB snapshot, row count, symbol count, integrity result, and semantic checksum.
- Historical feature and target materialization should be idempotent and create a new snapshot/version rather than mutating an accepted one.

## 4. Live DB Proposal

Future target path:

```text
data/live/stocks_live.db
```

Purpose: mutable runtime cache for scanner and dashboard operations.

Recommended contents:

| Data family | Notes |
|---|---|
| Latest and historical price cache | May be refreshed from Yahoo or another provider. |
| Fetch state | Coverage, freshness, provider timestamp, errors, retry state. |
| Company profile cache | Current quote, market cap, valuation, sector, industry, summary, and runtime fundamentals cache. |
| Runtime scan metadata | Optional scanner session metadata, request source, generated time, and cache freshness. |
| Current universe source cache | Live scanner symbol source references, not accepted research snapshots. |

Rules:

- Live DB may refresh, upsert, and extend cache rows.
- Live DB must not be used as an implicit research baseline.
- Live scanner outputs should preserve a snapshot of inputs used for display and PDF export.
- If live data is promoted to research, promotion must happen through an explicit research snapshot process, not by sharing mutable tables.

## 5. Table Ownership Matrix

| Table | Purpose | Current usage | Research dependency | Live dependency | Recommended future owner |
|---|---|---|---|---|---|
| `historical_prices` | Daily price bars and adjusted close | Research baselines and live cache | Critical | Critical | Split into research frozen prices and live cache prices |
| `historical_price_fetch_state` | Cache coverage and full-history state | Loader freshness and coverage | Audit-only at most | Critical | Live DB |
| `stocks` | Current stock profile cache | Dashboard/company research cache | Low for reproducible historical research | High | Live DB |
| `historical_financials` | Historical fundamentals | Fundamental dashboard/research cache | Potentially critical for future AI | Medium | Split or snapshot into Research DB; mutable source remains Live DB |
| `research_universes` | Saved named universes | User-managed symbol sets | Medium | Medium | Split: accepted universe snapshots in Research DB; user editable universes in Live DB or separate user DB |
| `research_universe_symbols` | Ordered universe membership | User-managed membership | Medium | Medium | Same as `research_universes` |

## 6. Data Ownership Rules

| Data class | Mutability | Future owner |
|---|---|---|
| Accepted research historical prices | Immutable / Frozen | Research DB |
| Accepted adjusted close | Immutable / Frozen per snapshot | Research DB |
| Universe metadata and listing dates | Semi-static; versioned when accepted | Research DB |
| User editable saved universes | Mutable | Live DB or user DB |
| Technical snapshots for research | Immutable once materialized | Research DB |
| Current technical snapshots | Mutable session data | Live DB or in-memory session |
| Research artifacts | Immutable once accepted | Files plus Research DB registry |
| Live cache state | Mutable | Live DB |
| Scan results | Mutable runtime snapshots unless explicitly promoted | Live DB or session state |
| AI training features and labels | Immutable per dataset version | Research DB |

## 7. Reproducibility Rules

Research DB requirements:

- Every accepted DB snapshot has a stable ID, file SHA-256, row counts, symbol counts, duplicate count, integrity result, and date range.
- Every research output records the exact snapshot ID and code/config fingerprint.
- Accepted snapshots are append-only at the metadata level; replacing a snapshot requires a new version and a decision record.
- Provider restatements are not silently absorbed. They become either a new research DB snapshot or stay isolated in the live cache.
- `adjusted_close` changes are research-relevant and must trigger reproducibility review.

Live scanner requirements:

- Live scanner may refresh prices and update fetch state.
- Live scanner must never mutate accepted research baselines.
- Current scan UI and PDF export should use scanner result snapshots, not direct DB queries.
- Any live-to-research promotion must be explicit and audited.

## 8. AI Future Impact

Long-Term Growth AI should depend on the Research DB, not the Live DB.

Required future research-store assets:

- observation universe snapshot;
- point-in-time feature snapshot;
- target definition metadata;
- target label snapshot;
- train / validation / holdout split metadata;
- OOS validation dataset;
- semantic checksum for features and targets;
- leakage boundary contract showing features use only information available at or before observation date.

Feature datasets and target labels should be independently versioned. Target construction may use future data, but feature materialization must not.

## 9. Migration Considerations

This phase does not decide how or when to migrate. Future planning should answer:

- which existing DB snapshot is canonical for Phase 7 / Phase 3 / Phase 4;
- whether current Yahoo-restated `adjusted_close` is accepted as a new canonical baseline;
- how to preserve the composite canonical baseline if current DB is not adopted;
- whether user-managed universes should live in a separate user DB;
- how application config chooses research DB versus live DB;
- how tests enforce that research code uses read-only connections and live code does not touch research DB.

Potential future stages:

1. Decision record for canonical research snapshot.
2. Read-only adapter design for research price loading.
3. Config-level DB path separation.
4. Tests that prevent live refresh code from opening research DB in write mode.
5. Optional migration or snapshot build after approval.

## 10. Rollback Considerations

Rollback should be a decision process, not an implicit `restore`.

Recommended rollback principles:

- Keep current live cache and research snapshot decisions separate.
- Never rollback `data/stocks.db` without first preserving evidence of current state.
- If a research snapshot is rejected, mark it rejected in documentation and keep the audit trail.
- If a new research snapshot is adopted, rerun affected baselines and store the new semantic checksums.
- PDF Export work should remain independent because it consumes scan snapshots and should not write or read DB directly.

## Phase 1 Decision

Recommended future architecture:

```text
SEPARATE_RESEARCH_AND_LIVE_PRICE_STORES = YES
```

This directly addresses the root conflict: one mutable SQLite file currently serves both reproducible research and live provider cache needs.
