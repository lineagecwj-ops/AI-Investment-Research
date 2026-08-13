# Fresh Live Store Dry Run Phase 6D-4B-1

## 1. Option B Design

Phase 6D-4B-1 validates the recommended Option B Fresh Live Cache strategy as a dry run only.

Actions allowed and performed:

- Created a temporary live database under `/tmp`.
- Used mock provider data only.
- Wrote temporary live cache rows.
- Validated `LiveDataStore` against the temporary DB.
- Validated scanner compatibility through injected `LiveDataStore`.
- Added dry-run tests and this document.

Actions not performed:

- No `data/live/` creation.
- No `data/live/stocks_live.db` creation.
- No `data/stocks.db` modification.
- No Yahoo fetch.
- No external API or network fetch.
- No real cache refresh.
- No production scanner workflow.
- No dashboard switch.
- No PDF change.
- No path cutover.
- No migration.
- No commit or push.

## 2. Temp Store

Dry-run path:

```text
/tmp/live_store_dry_run_phase6d4b1/stocks_live.dry_run.db
```

Temp live schema was initialized with the current live database schema contract.

Required live tables validated:

- `historical_prices`
- `historical_price_fetch_state`
- `stocks`
- `historical_financials`

Legacy mutable universe tables are also present in the current live schema:

- `research_universes`
- `research_universe_symbols`

Research snapshot metadata is not present:

- no `snapshot_metadata`
- no research manifest table
- no Phase artifacts

## 3. Validation

Production DB before and after:

| Check | Before | After |
| --- | --- | --- |
| `data/stocks.db` SHA | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` |
| `historical_prices` rows | `1185744` | `1185744` |
| symbols | `222` | `222` |
| integrity | `ok` | `ok` |

Temp live write validation:

- Mock provider returned one price series for `6666.TW`.
- `get_historical_prices(..., live_store=temp_store, force_refresh=True)` wrote to the temp DB.
- Temp `historical_prices` rows: `1`.
- Temp `historical_price_fetch_state` rows: `1`.
- Fetch state `latest_date`: `2026-08-12`.
- Production DB remained unchanged.

Validation artifact:

```text
/tmp/fresh_live_store_dry_run_phase6d4b1_validation.json
```

## 4. Scanner Compatibility

Scanner compatibility was validated through dependency injection:

```text
SwingScannerService(live_data_store=temp_store, price_loader=live_data_store_price_loader(temp_store))
```

Result:

- The scanner service accepted the injected temp `LiveDataStore`.
- The injected price loader read `6666.TW` from the temp live DB.
- No production scanner workflow was executed.
- Production V1 and V1.1 definitions were not modified.

## 5. Research / Live Boundary

Boundary validation:

- `LiveDataStore` cannot target the configured Research Store path.
- `ResearchDataStore` opens the temp live DB read-only and blocks write attempts.
- Temp live DB writes stay under `/tmp/live_store_dry_run_phase6d4b1/`.
- Research Store under `data/research/` was preserved and not modified.

Config dry run:

- `live_db_path` was set to `/tmp/live_store_dry_run_phase6d4b1/stocks_live.dry_run.db`.
- `research_db_path` remained the Research Store Candidate path.
- `research_snapshot_id` remained `research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1`.
- No production runtime config was switched.

## 6. Risks

Fresh Live Cache risks:

- Cold start: the live DB begins without production cache warmth.
- First real refresh may be slow unless staged warm-up is implemented.
- Provider availability remains a future operational concern.
- Current UI paths must handle missing or partial live cache coverage.

Mitigations:

- Use a controlled warm-up phase before cutover.
- Mock providers in tests.
- Keep legacy `data/stocks.db` fallback until live cutover acceptance passes.
- Add no-network and no-production-write safety tests to the future implementation phase.

## 7. Next Cutover Requirements

Before creating a formal `data/live/stocks_live.db`, a future phase must explicitly authorize:

- `data/live/` creation.
- live schema initialization.
- live DB warm-up strategy.
- provider refresh policy.
- production runtime config switch.
- scanner current path validation against the formal live DB.
- dashboard current panel validation against the formal live DB.
- rollback feature flag or config switch.

Phase 6D-4B-1 result:

```text
PASS_WITH_GAPS
```

The fresh live cache approach is viable, but real provider refresh and cold-start warm-up remain future authorized work.
