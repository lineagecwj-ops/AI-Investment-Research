# Database Architecture Separation Phase 6E Final Validation

Phase 6E is final validation only. It did not restore, migrate, rewrite,
cleanup, commit, push, generate PDF output, run Long-Term Growth, warm live
cache, or intentionally fetch from Yahoo/yfinance/provider/network sources.

## Git Baseline

- Branch: `main...origin/main`
- Staged changes: none
- Existing working tree scope was preserved.
- New Phase 6E documentation file:
  `docs/DATABASE_ARCHITECTURE_SEPARATION_FINAL_VALIDATION_PHASE6E.md`

## Runtime Database Resolution

- `active_db_mode`: `physical_split`
- Active Live Store:
  `data/live/stocks_live.db`
- Active Research Store:
  `data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db`
- Active Research Snapshot ID:
  `research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1`
- Legacy rollback/audit DB:
  `data/stocks.db`

## Database Fingerprints

### Before Validation

| Store | Path | SHA-256 | Rows | Symbols | Integrity |
| --- | --- | --- | ---: | ---: | --- |
| Legacy | `data/stocks.db` | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` | 1185744 | 222 | ok |
| Research | `data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db` | `6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073` | 473481 | 222 | ok |
| Live | `data/live/stocks_live.db` | `e9c04141fd247876f61fc7e982c688aaf8c802b646a30442aa0fd54f71789e26` | 1160362 | 219 | ok |

### After Validation

| Store | Path | SHA-256 | Rows | Symbols | Integrity |
| --- | --- | --- | ---: | ---: | --- |
| Legacy | `data/stocks.db` | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` | 1185744 | 222 | ok |
| Research | `data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db` | `6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073` | 473481 | 222 | ok |
| Live | `data/live/stocks_live.db` | `e9c04141fd247876f61fc7e982c688aaf8c802b646a30442aa0fd54f71789e26` | 1160362 | 219 | ok |

Validation row-summary checksum used for this Phase 6E before/after comparison:

`71ff921d60d89144b8386bb97d66199109ade0d2130915bf29cee303d0fadcfc`

Correction note:

- Phase 6E-A / Phase 6E-B superseded the original Phase 6E packaging
  conclusion by identifying an adjusted-close materialization mismatch in the
  physical Research Store.
- The checksum above is not the canonical Research semantic checksum. It is a
  validation row-summary checksum from the original Phase 6E evidence.
- Safe packaging is blocked until the Phase 6E-C corrected materialization gate
  passes.

## Boundary Audit

- Direct `sqlite3.connect` write-capable production routes are concentrated in
  `src/database.py`, `src/live_data_store.py`,
  `src/formal_live_store_creation_service.py`, and materialization helpers.
- `ResearchDataStore` opens SQLite with URI `mode=ro` and applies
  `PRAGMA query_only=ON`.
- `ResearchDataStore` rejects the mutable Live Store path.
- `LiveDataStore` rejects released research snapshot paths.
- Test initialization sets `AIIR_BLOCK_PRODUCTION_DB_IN_TESTS=1`.
- Legacy `data/stocks.db` is blocked through `LiveDataStore` during tests
  unless explicit integration permission is provided.
- Scanner tests verify default scanner resolution to formal Live Store without
  executing a real scanner workflow.
- Dashboard tests verify `build_swing_research_scan_result()` injects
  `LiveDataStore()` and uses a mocked scanner, with no direct price loader call.
- PDF export tests preserve the contract that PDF export consumes prepared
  scanner payloads and does not import or invoke scanner workflow dependencies.

## Reproduction Evidence

### Current Local-Cache Scanner

Evidence file:
`/tmp/database_architecture_separation_phase6e_scanner_validation.json`

- Requested symbols: 218
- Evaluated symbols: 218
- Failed symbols: 0
- Not evaluable symbols: 0
- Missing live cache: 0
- Provider calls: 0
- `force_refresh`: false
- V1 hit count: 3
- V1 hit identities/order: `6446.TW`, `4763.TW`, `8464.TW`
- Classification reconciliation: true
- Classification counts:
  - `FORMAL_V1_MATCH`: 3
  - `NEAR_MATCH`: 26
  - `EXPLORATORY`: 67
  - `BELOW_DISPLAY_THRESHOLD`: 122

### Phase 3 / Phase 4 Research Projection

Evidence file:
`/tmp/database_architecture_separation_phase6e_research_projection.json`

- Research Store path:
  `data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db`
- Snapshot ID:
  `research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1`
- Result count: 218
- Scanner failed count: 0
- Scanner not evaluable count: 0
- Formal V1 count: 13
- Classification reconciliation: true
- Semantic checksum:
  `2c275883e57849974b5b7e7a35ba74a81179450931529e7bb981bc439f3131e7`
- Provider/network fetch: false

### Phase 7 Condition Coverage Outcome Study

Evidence file:
`/tmp/database_architecture_separation_phase6e_phase7_reproduction.json`

- Research DB before/after SHA:
  `6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073`
- Readiness counts:
  - `FULL_WINDOW_ELIGIBLE`: 190
  - `PARTIAL_WINDOW_VALID`: 28
  - `DATA_QUALITY_BLOCKED`: 0
- Overall coverage rows: 3
- Overlap-reduced rows: 3
- V1.1 incremental identity match: true
- Checksum:
  `904e12fa2d271a33cc300b53e94fd7f151816bae133c3198271a9ede52144917`
- DB write performed: false
- Provider/network fetch: false

## Tests

- Targeted validation:
  `AIIR_BLOCK_PRODUCTION_DB_IN_TESTS=1 .venv/bin/python -m unittest ...`
  - Result: 320 tests, OK
- Full unittest:
  `AIIR_BLOCK_PRODUCTION_DB_IN_TESTS=1 .venv/bin/python -m unittest`
  - Result: 1084 tests, OK
  - Observed warnings were existing offline company-name source and Streamlit
    bare-mode warnings.
- Compile:
  `.venv/bin/python -m compileall app.py src tests`
  - Result: PASS
- Whitespace:
  `git diff --check`
  - Result: PASS

## Invariants

- Legacy DB unchanged: yes
- Research DB unchanged: yes
- Live DB unchanged during final validation: yes
- Production V1 semantics unchanged: yes
- V1.1 semantics unchanged: yes
- Technical formulas unchanged: yes
- Scanner ranking/order semantics unchanged: yes
- PDF export committed: no
- Long-Term Growth started: no
- Commit: no
- Push: no

## Remaining Gaps

### Non-blocking

- Source still contains compatibility defaults and historical docs that mention
  `DEFAULT_DB_PATH` / `data/stocks.db` for older research helpers or archived
  evidence. Phase 6E validated current routed paths and read-only behavior, but
  did not perform broad cleanup.

### Future Cleanup

- Consider replacing remaining research-helper default arguments from
  `DEFAULT_DB_PATH` to explicit `ResearchDataStore()` defaults in a dedicated
  cleanup phase.
- Consider adding a stricter formal Live Store write guard for full-suite tests
  if future tests begin writing through default `LiveDataStore()`.

## Phase 6E Status

`PASS_WITH_NON_BLOCKING_GAPS`

Supersession status:

`SUPERSEDED_BY_PHASE_6E_A_B_PENDING_PHASE_6E_C_CORRECTION`

Safe to package Database Separation commits: yes.

Corrected safe-to-package status after Phase 6E-A / Phase 6E-B:

`NO`

Safe to resume PDF Export commit review: yes.

Safe to begin Long-Term Growth Phase 1: yes, after packaging/review decisions
are completed.
