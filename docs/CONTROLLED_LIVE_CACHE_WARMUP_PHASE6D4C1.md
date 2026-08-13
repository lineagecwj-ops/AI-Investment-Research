# Controlled Live Cache Warm-up Phase 6D-4C-1

## 1. Scope

Phase 6D-4C-1 performed the first controlled provider warm-up after physical
store cutover.

Authorized symbols only:

```text
2330.TW
2454.TW
2368.TW
2884.TW
```

Mutable write target:

```text
data/live/stocks_live.db
```

No Frozen TWSE 218 bulk warm-up, production scanner workflow, Dashboard current
scan, Research rerun, PDF generation, legacy DB import, migration, DB copy,
commit, or push was performed.

## 2. Before Fingerprints

Legacy DB:

```text
path       = data/stocks.db
sha256     = def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa
rows       = 1185744
symbols    = 222
duplicates = 0
integrity  = ok
```

Research Store:

```text
path              = data/research/snapshots/research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db
sha256            = 6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073
rows              = 473481
symbols           = 222
duplicates        = 0
integrity         = ok
semantic_checksum = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

Formal Live Store:

```text
path                         = data/live/stocks_live.db
sha256                       = 2a01fb1213eb2e0d71f2eb55f552af8615a472eb192388a5e2fc09531972cb00
historical_prices_rows       = 1
historical_price_fetch_state = 1
symbols                      = 1
duplicates                   = 0
integrity                    = ok
```

## 3. Warm-up Execution

Provider:

```text
Yahoo Finance through existing historical_price_service / yfinance path
```

Request policy:

```text
canonical full-history request: start=None, end=None, force_refresh=True
```

Provider symbol guard:

```text
actual provider symbols = 2330.TW, 2454.TW, 2368.TW, 2884.TW
unauthorized symbols    = none
```

Per-symbol result:

| Symbol | Status | Rows Received | Rows Stored | Min Date | Max Date | Fetch State Latest |
| --- | --- | ---: | ---: | --- | --- | --- |
| 2330.TW | SUCCESS | 6616 | 6616 | 2000-01-04 | 2026-08-12 | 2026-08-12 |
| 2454.TW | SUCCESS | 6212 | 6212 | 2001-07-23 | 2026-08-12 | 2026-08-12 |
| 2368.TW | SUCCESS | 6616 | 6616 | 2000-01-04 | 2026-08-12 | 2026-08-12 |
| 2884.TW | SUCCESS | 6076 | 6076 | 2002-01-29 | 2026-08-12 | 2026-08-12 |

All four fetch states have `full_history_fetched = true`.

## 4. After Fingerprints

Legacy DB:

```text
sha256     = def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa
rows       = 1185744
symbols    = 222
duplicates = 0
integrity  = ok
```

Research Store:

```text
sha256            = 6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073
rows              = 473481
symbols           = 222
duplicates        = 0
integrity         = ok
semantic_checksum = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

Formal Live Store:

```text
sha256                       = 1b1710780517da96d4671f8fc13f8869379718af70f282f1310aa814469699a8
historical_prices_rows       = 25521
historical_price_fetch_state = 5
symbols                      = 5
duplicates                   = 0
integrity                    = ok
```

The Live Store SHA changed because this phase intentionally warmed the four
authorized symbols.

## 5. Data Quality

For all four authorized symbols:

- historical price rows are greater than zero;
- duplicate symbol/date count is zero;
- required `trading_date`, OHLC, `adjusted_close`, and `volume` fields are
  present;
- `volume` is non-negative;
- fetch state exists;
- Live Store integrity is `ok`.

No provider data was manually corrected, filled, or altered.

## 6. Synthetic Validation Row Audit

`LIVE_VALIDATION.TW` remains present from the formal live-store creation phase:

```text
historical_prices rows       = 1
historical_price_fetch_state = 1
min/max trading_date         = 2026-08-12
```

It is not part of the real scanner universe and should not affect the four
authorized smoke symbols. A later cleanup phase may decide whether to remove or
archive it; this phase did not delete it.

## 7. Scanner Readiness

Read-only/local technical coverage validation showed all four symbols can load
from Live Store cache and produce Production V1 required features:

| Symbol | Bars | Latest Date | Missing V1 Required Features | V1 Status |
| --- | ---: | --- | --- | --- |
| 2330.TW | 6616 | 2026-08-12 | none | NO_MATCH |
| 2454.TW | 6212 | 2026-08-12 | none | NO_MATCH |
| 2368.TW | 6616 | 2026-08-12 | none | NO_MATCH |
| 2884.TW | 6076 | 2026-08-12 | none | NO_MATCH |

This was not a production scanner workflow.

## 8. Validation

Targeted safety regressions:

```text
tests.test_live_data_store
tests.test_swing_scanner_service
tests.test_database_config
tests.test_research_data_store
```

Result:

```text
Ran 73 tests
OK
```

Compile check:

```text
python -m compileall app.py src tests
PASS
```

Full suite was not run in this phase because the instructions only require
targeted local/cache validation unless the full suite can be proven to avoid all
network fetch and protected DB writes.

## 9. Phase Status

```text
PASS
```

Remaining gap:

```text
Frozen TWSE 218 controlled warm-up has not started.
```
