# Database Migration Planning Phase 4

## 1. Migration Goals

This phase designs a future migration from the current single SQLite database:

```text
data/stocks.db
```

into separated data-access responsibilities:

```text
ResearchDataStore
LiveDataStore
```

This document is planning-only. It does not create a research DB, create a live
DB, copy data, run schema migration, write to SQLite, fetch Yahoo data, execute
scanner workflows, modify Dashboard behavior, modify PDF Export, or start
Long-Term Growth implementation.

## 2. Migration Principles

Migration principles, in priority order:

1. Research reproducibility first.
2. Live scanner availability second.
3. No silent research baseline mutation.
4. Every released snapshot is versioned.
5. Rollback must be possible through configuration and retained artifacts.

The future architecture must preserve Phase 2 and Phase 3 decisions:

```text
ResearchDataStore: snapshot-addressed, read-only, deterministic
LiveDataStore: mutable cache, refresh-capable, never canonical by default
PDF Export: snapshot consumer, no DB access
```

## 3. Migration Stages

### Phase A: Preparation

Purpose:

- centralize future configuration names;
- define manifest schema and validation commands;
- identify all direct `data/stocks.db` dependencies;
- prepare tests that prove old behavior before migration.

Input:

- current `data/stocks.db`;
- Phase 1 inventory;
- Phase 2 access boundary;
- Phase 3 Research Snapshot specification.

Output:

- migration checklist;
- config contract;
- acceptance test list;
- baseline research and live-output fingerprints.

Risk:

- missed code path still hard-codes the old database.

Rollback:

- no runtime migration has occurred; continue using current `data/stocks.db`.

### Phase B: Research Snapshot Freeze

Purpose:

- select a candidate canonical research source;
- create a released Research Snapshot only after provenance, checksum, provider
  vintage, price basis, universe, dataset scope, and semantic checksum checks.

Input:

- candidate source DB;
- candidate snapshot manifest;
- canonical selection review.

Output:

- released Research Snapshot;
- immutable manifest;
- research artifact fingerprints.

Risk:

- adjusted-close vintage mismatch or current/old canonical disagreement.

Rollback:

- do not release the candidate;
- keep `CURRENT_CANONICAL_DECISION = OPEN`;
- continue research with explicitly labeled prior artifacts only.

### Phase C: Create Separated Stores

Purpose:

- introduce separate physical or configured paths for ResearchDataStore and
  LiveDataStore.

Input:

- released Research Snapshot;
- current live cache source;
- config values.

Output:

- research store path;
- live store path;
- manifest path;
- unchanged released research checksum.

Risk:

- accidental copy of mutable fetch state into research semantics;
- accidental live writer access to research path.

Rollback:

- switch config back to the old single-db path;
- keep research snapshot immutable and unused by writers.

### Phase D: Redirect Research Readers

Purpose:

- move evidence-producing research modules to ResearchDataStore.

Input:

- released Research Snapshot;
- manifest;
- read-only ResearchDataStore interface.

Output:

- research readers require `research_snapshot_id`;
- reproducible Phase 7, Phase 3, backtest, replay, walk-forward, and OOS
  artifacts.

Risk:

- research module still depends on live cache or Yahoo fetch path.

Rollback:

- feature flag research modules back to old read-only path;
- keep new ResearchDataStore artifacts labeled experimental until accepted.

### Phase E: Redirect Live Writers

Purpose:

- move mutable price/profile/fetch-state writes to LiveDataStore.

Input:

- live DB path;
- live writer interfaces;
- scanner live workflow.

Output:

- Yahoo refresh writes only to LiveDataStore;
- `save_historical_prices` and fetch-state updates reject released research
  paths.

Risk:

- current scanner outage;
- live writes accidentally point at a released snapshot.

Rollback:

- switch live scanner config back to old cache path;
- keep released research checksum unchanged.

### Phase F: Validation

Purpose:

- compare old architecture and new architecture outputs.

Input:

- old baseline fingerprints;
- new research and live outputs;
- acceptance checklist.

Output:

- pass/fail report;
- checksum comparison;
- artifact comparison;
- scanner availability evidence.

Risk:

- output mismatch without clear provenance.

Rollback:

- fail the migration gate;
- keep old path active;
- preserve mismatch artifacts for diagnosis.

### Phase G: Cleanup / Deprecation

Purpose:

- deprecate direct single-db usage only after all acceptance criteria pass.

Input:

- accepted migration report;
- rollback path;
- production readiness decision.

Output:

- direct `data/stocks.db` usage removed or guarded;
- old path retained behind a rollback feature flag during a defined transition
  window.

Risk:

- premature cleanup removes rollback ability.

Rollback:

- re-enable the retained old path and feature flag;
- do not modify released Research Snapshots.

## 4. Canonical Snapshot Decision Process

The canonical research snapshot decision remains open. This phase does not
choose between the current DB SHA and any old composite canonical context.

Future decision criteria:

- reproducibility;
- adjusted-close consistency;
- provider vintage;
- price basis version;
- price coverage;
- research-window coverage;
- universe identity;
- existing research compatibility;
- semantic checksum;
- Phase 7 reproducibility;
- Phase 3 reproducibility;
- backtest reproducibility.

Required decision artifacts:

- candidate manifest;
- checksum report;
- adjusted-close consistency report;
- provider-vintage statement;
- dataset/table scope;
- review decision with accepted limitations.

## 5. Research Store Migration Plan

ResearchDataStore future source:

- released Research Snapshot;
- immutable manifest;
- database checksum;
- semantic checksum;
- universe metadata;
- listing-date metadata when required;
- versioned research artifacts.

Research modules migration order:

1. Read-only research reports and diagnostics.
2. Phase 7 / condition coverage research.
3. Phase 3 candidate display research.
4. Backtest.
5. Replay.
6. Walk-forward.
7. OOS.
8. Future AI pipeline.

Research migration rules:

- require `research_snapshot_id`;
- open SQLite with `mode=ro`;
- apply `PRAGMA query_only=ON`;
- verify manifest checksum before evidence runs;
- reject live cache paths for canonical research jobs;
- never call Yahoo fetch or live refresh code.

## 6. Live Store Migration Plan

LiveDataStore future source:

- current prices;
- mutable historical price cache;
- current company/profile cache;
- `historical_price_fetch_state`;
- fetch retry/failure/runtime metadata.

Live writer migration targets:

- `historical_price_service`;
- `save_historical_prices`;
- fetch-state updates;
- current stock/profile cache writers;
- current scanner data loading.

Live migration rules:

- live writers may update only LiveDataStore;
- live refresh does not change released research checksum;
- live refresh does not change released research semantic checksum;
- live data may become candidate snapshot input only through the release gate.

## 7. Module Migration Matrix

| Module | Current data source | Future data source | Migration phase | Risk | Validation |
|---|---|---|---|---|---|
| `src/database.py` | Shared `data/stocks.db` helpers | Boundary layer split into ResearchDataStore and LiveDataStore helpers | A, C | Hidden shared writer remains | Direct old-path dependency scan and boundary tests. |
| `src/historical_price_service.py` | Mutable cache, Yahoo fetch, save helpers | LiveDataStore | E | Writes research path by mistake | Live refresh changes only live checksum. |
| `src/stock_service.py` | Stock profile cache in current DB | LiveDataStore | E | Current market panel loses profile data | Current profile cache read/write test. |
| `SwingScannerService` | Default live price loader | LiveDataStore | E, F | Scanner availability regression | Current scanner smoke and output fingerprint comparison. |
| Condition Coverage | Read-only current DB loaders | ResearchDataStore | D, F | Research uses live-adjusted values | Phase 7 reproduction and manifest verification. |
| Phase 3 services | Read-only projection and safety audit | ResearchDataStore | D, F | Candidate display evidence drift | Phase 3 artifact checksum comparison. |
| Phase 4 Dashboard | Mixed orchestration | LiveDataStore for current panel; ResearchDataStore for research evidence panel | D, E, F | Provenance confusion | UI/source labels and fingerprints verified. |
| Backtest | Supplied series or default cache paths | ResearchDataStore for evidence runs | D, F | Mixed live/research series | Backtest deterministic output comparison. |
| Replay | Default mutable loader unless injected | ResearchDataStore for evidence runs; LiveDataStore only for ad hoc live paths | D, F | Hidden old default remains | Replay rejects missing snapshot for evidence mode. |
| Walk-Forward | Default mutable loader unless injected | ResearchDataStore for evidence runs | D, F | Cross-window data drift | Walk-forward deterministic output comparison. |
| OOS | Default mutable loader unless injected | ResearchDataStore for evidence runs | D, F | OOS tuning contamination | OOS split and artifact lineage validation. |
| PDF Export | No DB access | Scan Result Snapshot only | F | Accidental DB dependency added | PDF export dependency test stays DB-agnostic. |
| Universe services | Frozen reads and mutable CRUD mixed | Frozen research universe in ResearchDataStore; editable user/live universes outside released snapshot | C, D, E | Live mutates frozen identity | Frozen TWSE universe checksum unchanged. |
| AI future modules | Not implemented | ResearchDataStore, feature artifacts, target artifacts, model lineage | D, F, future phase | Training from mutable live cache | AI jobs require released snapshot and artifact lineage. |
| `app.py` | Mixed orchestration and some direct DB reads | Explicit LiveDataStore and ResearchDataStore routing | D, E, F | UI calls wrong store | Current panel and research panel provenance tests. |

## 8. Connection Management Design

Future config:

```text
research_db_path
live_db_path
research_snapshot_id
manifest_path
```

Design rules:

- no evidence-producing research path should rely on hard-coded
  `data/stocks.db`;
- research jobs fail closed if `research_snapshot_id` or `manifest_path` is
  missing;
- live jobs fail closed if pointed at a released research path;
- app-level orchestration must choose the boundary explicitly.

## 9. Read / Write Boundary

Research:

```text
READ ONLY
snapshot-addressed
manifest-verified
no Yahoo fetch
no fetch-state updates
```

Live:

```text
READ / WRITE
refresh-capable
runtime-cache-owned
not canonical by default
```

Forbidden:

- Live writer opening ResearchDataStore in writable mode;
- Research module depending on live cache for canonical artifacts;
- hidden cross-write between released snapshot and live cache;
- silent promotion of live data into research baseline.

## 10. Adjusted-Close Migration Rule

Migration validation must check:

- `adjusted_close` consistency;
- price basis version;
- provider vintage;
- existing-key research-field changes;
- semantic checksum.

Any `adjusted_close` rewrite requires:

```text
new candidate snapshot
  -> provider/vintage audit
  -> semantic checksum
  -> release gate
  -> new released snapshot version
```

It must not overwrite a released snapshot.

## 11. `historical_prices` Table Strategy

### Option A: Research Copy + Live Copy

Advantages:

- strongest isolation;
- simple read/write boundary;
- easiest checksum and rollback story.

Risks:

- duplicated storage;
- requires explicit copy/release process;
- potential confusion if paths are mislabeled.

### Option B: Shared Immutable Layer + Live Overlay

Advantages:

- less duplication;
- live cache can store only deltas or refreshed rows.

Risks:

- more complex query semantics;
- higher chance of accidental hybrid adjusted-close vintage;
- harder artifact reproducibility.

### Option C: Snapshot Files + Live Database

Advantages:

- clear immutable snapshot artifact;
- live DB remains optimized for scanner/cache use;
- snapshots can be archived and checksummed independently.

Risks:

- requires manifest discipline;
- requires explicit artifact storage policy;
- snapshot release tooling must be reliable.

Recommendation:

Use Option C as the default target: immutable snapshot files plus a mutable live
database. It gives ResearchDataStore a stable artifact boundary while preserving
LiveDataStore availability. Option A is acceptable for early migration if it
reduces implementation risk. Avoid Option B unless there is a strong storage or
performance reason and stronger tests exist.

## 12. Fetch State Separation

`historical_price_fetch_state` belongs entirely to LiveDataStore.

ResearchDataStore must not depend on:

- `full_history_fetched`;
- live `earliest_date` / `latest_date` fetch state;
- retry/failure state;
- live `fetched_at` freshness state.

Research coverage is proven by snapshot manifest fields and dataset checksums,
not by mutable fetch state.

## 13. Universe Separation

Frozen TWSE 218 belongs to versioned research universe metadata.

Rules:

- released research artifacts cite `universe_id` and `universe_version`;
- live scanner may reference a frozen universe ID/version;
- live refresh must not rebuild or mutate frozen universe identity;
- editable user/live universes must not silently replace a released frozen
  universe.

## 14. PDF Export Migration Impact

PDF Export should remain:

```text
Scan Result Snapshot
  -> PDF
```

It should not directly depend on ResearchDataStore or LiveDataStore.

Allowed future metadata:

```text
scan_snapshot_id
research_evidence_snapshot_id
source_fingerprint
generated_at
```

Migration acceptance should prove PDF export still does not open SQLite, run
scanner workflows, fetch prices, or rebuild technical indicators.

## 15. Dashboard Migration Impact

Dashboard source ownership:

| Dashboard area | Future source |
|---|---|
| Current panel | LiveDataStore |
| Research evidence panel | Research Snapshot via ResearchDataStore |
| PDF export action | Current scan result snapshot |

The same page may show live and research evidence together, but the UI must
keep provenance visible through labels, snapshot IDs, provider vintage, and
fingerprints.

## 16. AI Pipeline Migration Impact

Long-Term Growth AI must depend on ResearchDataStore.

Future lineage:

```text
Research Snapshot
  -> Feature Artifact
  -> Target Artifact
  -> Training Dataset
  -> Model Version
  -> OOS Result
```

AI migration prerequisites:

- released Research Snapshot;
- feature definition version;
- target definition ID;
- training/validation/OOS window definition;
- artifact checksums;
- leakage boundary statement.

## 17. Acceptance Criteria

Formal migration acceptance checklist:

- Research snapshot checksum unchanged after live refresh.
- Research semantic checksum unchanged after live refresh.
- Phase 7 reproducible from ResearchDataStore.
- Phase 3 reproducible from ResearchDataStore.
- Backtest reproducible from ResearchDataStore.
- Replay reproducible from ResearchDataStore for evidence mode.
- Walk-forward reproducible from ResearchDataStore for evidence mode.
- OOS reproducible from ResearchDataStore for evidence mode.
- Live scanner still works from LiveDataStore.
- Frozen TWSE identity unchanged.
- PDF export works from Scan Result Snapshot and stays DB-agnostic.
- Dashboard current panel uses LiveDataStore.
- Dashboard research evidence panel uses ResearchDataStore.
- No DB cross-write.
- No hidden dependency on old `data/stocks.db` path for accepted research jobs.
- Rollback config can return live scanner to the prior path without changing
  released research artifacts.

## 18. Validation Strategy

Before migration:

- record current DB SHA;
- record row, symbol, duplicate, and integrity counts;
- record Phase 7 artifact fingerprints;
- record Phase 3 artifact fingerprints;
- record backtest/replay/walk-forward/OOS baseline outputs where applicable;
- record current scanner smoke output;
- record PDF export smoke output.

After migration:

- verify Research DB SHA unchanged after live operations;
- verify Research semantic checksum unchanged;
- compare research outputs to accepted baselines;
- compare row and symbol counts within each declared snapshot scope;
- verify live scanner availability;
- verify Dashboard provenance labels;
- verify PDF export remains DB-agnostic;
- scan for hidden `data/stocks.db` dependencies in evidence-producing paths.

Comparison dimensions:

```text
results
counts
checksums
artifacts
scanner output
provenance labels
```

## 19. Rollback Plan

Rollback triggers:

- research checksum changes unexpectedly;
- live writer touches research path;
- Phase 7 or Phase 3 reproduction fails;
- backtest/replay/walk-forward/OOS evidence outputs drift without accepted
  reason;
- current scanner cannot run from LiveDataStore;
- Dashboard provenance becomes ambiguous;
- PDF export gains DB dependency;
- performance regression blocks normal use.

Rollback actions:

- switch config back to old single-db path for live scanner;
- disable new ResearchDataStore routing behind feature flag;
- keep released Research Snapshots immutable;
- preserve failed migration artifacts for diagnosis;
- do not manually restore DB as the only rollback mechanism.

Rollback validation:

- old live scanner path works;
- released Research Snapshot checksum unchanged;
- no staged or partial migration code remains active;
- user-facing workflows return to the prior accepted behavior.

## 20. Cutover Strategy

Big bang migration:

- faster end-state;
- higher outage and hidden dependency risk;
- harder rollback if multiple readers/writers fail together.

Gradual migration:

- migrate research readers first;
- validate evidence reproducibility;
- migrate live writers second;
- keep rollback flags until acceptance is complete.

Recommendation:

Use gradual migration. Research reproducibility should be stabilized before live
writer cutover. Live scanner availability remains protected by retaining the old
path behind a feature flag until acceptance passes.

## 21. Migration Risks

| Risk | Impact | Mitigation |
|---|---|---|
| `adjusted_close` drift | Research evidence silently changes. | Provider vintage, price basis, semantic checksum, and new snapshot version gate. |
| Path misconfiguration | Live writer may touch research path or research may read live cache. | Explicit config, fail-closed validation, boundary tests. |
| Research/live cross-write | Released snapshot loses immutability. | `mode=ro`, `PRAGMA query_only=ON`, writer path rejection. |
| Missing artifact linkage | Research output cannot be reproduced. | Require snapshot ID, manifest path, artifact checksum, semantic checksum. |
| Snapshot mismatch | Feature, target, or model uses incompatible inputs. | Same-snapshot rule and explicit compatibility declaration. |
| Performance issue | Dashboard or scanner becomes slow. | Gradual cutover, live path rollback, targeted performance smoke tests. |
| Hidden old-path dependency | Migration appears successful but evidence still reads old DB. | Dependency scan and accepted research jobs reject missing snapshot IDs. |
| Frozen universe mutation | Research universe identity changes under same label. | Versioned universe metadata and checksum validation. |

## 22. Stop Gate

Phase 4 ends at migration planning review.

Do not proceed to:

- migration implementation;
- database creation;
- data copy;
- schema migration;
- scanner execution;
- Dashboard modification;
- PDF Export modification;
- Long-Term Growth implementation.
