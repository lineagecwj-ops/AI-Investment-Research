# Formal Live Store Creation Phase 6D-4B-2B-1

## 1. Purpose

Phase 6D-4B-2B-1 creates the formal physical Live Store database without runtime cutover.

Allowed and performed:

- Created `data/live/`.
- Created `data/live/stocks_live.db`.
- Initialized a fresh live-only schema.
- Validated `LiveDataStore` can write isolated test data to the new live DB.

Not performed:

- No copy from `data/stocks.db`.
- No data import.
- No migration.
- No Yahoo/API/network fetch.
- No real refresh.
- No scanner cutover.
- No Dashboard cutover.
- No PDF modification.
- No runtime config switch.
- No commit or push.

## 2. Created Path

Formal Live Store:

```text
data/live/stocks_live.db
```

Initial creation checksum before validation write:

```text
8402c28156ffba2056a655b92e8f6ea7677c79287fe85e93d0c8c524e9ca58e3
```

Checksum after isolated write validation:

```text
2a01fb1213eb2e0d71f2eb55f552af8615a472eb192388a5e2fc09531972cb00
```

The checksum changed only because Phase 6D-4B-2B-1 performed the required isolated write/update/fetch-state validation against the Live Store.

## 3. Schema

Live Store tables:

- `historical_prices`
- `historical_price_fetch_state`
- `stocks`
- `historical_financials`

Excluded tables:

- `snapshot_metadata`
- `research_universes`
- `research_universe_symbols`
- Research Snapshot artifacts
- Research manifests
- Phase artifacts

Initial state before validation write:

| Table | Rows |
| --- | ---: |
| `historical_prices` | `0` |
| `historical_price_fetch_state` | `0` |
| `stocks` | `0` |
| `historical_financials` | `0` |

State after isolated validation write:

| Table | Rows |
| --- | ---: |
| `historical_prices` | `1` |
| `historical_price_fetch_state` | `1` |
| `stocks` | `0` |
| `historical_financials` | `0` |

Validation symbol:

```text
LIVE_VALIDATION.TW
```

This is isolated validation data, not provider data and not research evidence.

## 4. No Cutover Rule

Runtime defaults are not switched in this phase.

Current runtime state remains:

```text
legacy_db_path = data/stocks.db
live_db_path exists but is not active runtime default
use_physical_store_split = OFF / not enabled
```

Scanner, Dashboard, and PDF runtime behavior were not changed.

## 5. Validation

Production DB protection:

| Check | Before | After |
| --- | --- | --- |
| `data/stocks.db` SHA | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` | `def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa` |
| `historical_prices` rows | `1185744` | `1185744` |
| symbols | `222` | `222` |
| integrity | `ok` | `ok` |

Live DB validation:

- `LiveDataStore(db_path=data/live/stocks_live.db)` can write.
- Insert validation succeeded.
- Update validation succeeded.
- `historical_price_fetch_state` write succeeded.
- Live DB contains no forbidden research tables.
- Integrity is `ok`.

Research protection:

- `ResearchDataStore` cannot write the Live DB.
- `ResearchDataStore` cannot write the released Research Store snapshot.
- Research Store was preserved.

Validation artifacts:

```text
/tmp/formal_live_store_creation_phase6d4b2b1_validation.json
/tmp/formal_live_store_creation_phase6d4b2b1_write_validation.json
```

## 6. Rollback

Rollback is config-based, not restore-based.

Because no runtime cutover occurred:

- Existing app/scanner/dashboard behavior still uses legacy configuration.
- `data/stocks.db` remains unchanged.
- `data/live/stocks_live.db` can be retained for inspection or recreated in a future authorized phase.
- Do not delete or replace `data/stocks.db`.
- Do not modify Research Store during rollback.

If this Live Store candidate is rejected, the next authorized phase should either recreate `data/live/stocks_live.db` from a fresh schema or document why the candidate is retained.

## 7. Phase Status

Phase 6D-4B-2B-1 status:

```text
PASS
```

Safe next step:

```text
Phase 6D-4B-2B-2 may proceed if it explicitly keeps runtime cutover disabled or authorizes the next validation/cutover step.
```
