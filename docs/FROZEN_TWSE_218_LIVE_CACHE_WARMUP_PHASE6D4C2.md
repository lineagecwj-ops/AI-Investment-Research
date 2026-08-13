# Frozen TWSE 218 Live Cache Warm-up Phase 6D-4C-2

## 1. Scope

Phase 6D-4C-2 warmed the formal Live Store for the canonical Frozen TWSE 218
scanner universe.

Authorized network scope:

```text
canonical Frozen TWSE 218 symbols only
```

Mutable write target:

```text
data/live/stocks_live.db
```

No ETF universe refetch, listing-date refetch, TPEx fetch, US stock fetch,
saved-universe fetch, manual-symbol fetch, financial-data bulk fetch, Research
Store enrichment, production scanner workflow, Dashboard scan, PDF generation,
Long-Term Growth work, commit, or push was performed.

## 2. Universe Identity

The universe was loaded through the existing canonical Frozen TWSE research
universe loader backed by the released Research Store.

```text
universe_id      = frozen_twse_research_universe_2026_08_09
universe_version = 2026-08-current-etf-constituent-v1
symbols          = 218
unique_symbols   = 218
TPEx symbols     = 0
non-Taiwan       = 0
0050.TW          = excluded
fingerprint      = db73096e24026e0d9b3388e15a29abeed10b87214d2fab795bd274858447dbb9
```

The Phase 6D-4C-1 smoke symbols were all present in the 218-symbol universe:

```text
2330.TW
2454.TW
2368.TW
2884.TW
```

`LIVE_VALIDATION.TW` is not part of the Frozen TWSE 218 universe.

## 3. Before Fingerprints

Legacy DB:

```text
sha256     = def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa
rows       = 1185744
symbols    = 222
duplicates = 0
integrity  = ok
```

Research DB:

```text
sha256            = 6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073
rows              = 473481
symbols           = 222
duplicates        = 0
integrity         = ok
semantic_checksum = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

Live DB:

```text
sha256                       = 1b1710780517da96d4671f8fc13f8869379718af70f282f1310aa814469699a8
historical_prices_rows       = 25521
historical_price_fetch_state = 5
symbols                      = 5
duplicates                   = 0
integrity                    = ok
```

## 4. Batch Strategy

Existing warm symbols were not refetched:

```text
already_warm = 2330.TW, 2368.TW, 2454.TW, 2884.TW
already_warm_count = 4
```

Remaining symbols were warmed in deterministic ascending order.

```text
batch_size  = 20
batch_count = 11
remaining   = 214
```

Per-batch summary:

| Batch | Attempted | Success | Failed | Rows Delta |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 20 | 20 | 0 | 126236 |
| 2 | 20 | 20 | 0 | 114496 |
| 3 | 20 | 20 | 0 | 134145 |
| 4 | 20 | 20 | 0 | 130348 |
| 5 | 20 | 20 | 0 | 120556 |
| 6 | 20 | 20 | 0 | 116918 |
| 7 | 20 | 20 | 0 | 111327 |
| 8 | 20 | 20 | 0 | 82432 |
| 9 | 20 | 20 | 0 | 89097 |
| 10 | 20 | 20 | 0 | 40360 |
| 11 | 14 | 14 | 0 | 68926 |

Checkpoint artifact:

```text
/tmp/frozen_twse_218_live_warmup_phase6d4c2_checkpoint.json
```

## 5. Network Audit

Provider:

```text
Yahoo Finance through existing historical_price_service / yfinance path
```

Request policy:

```text
canonical full-history request: start=None, end=None, force_refresh=True
```

Provider guard:

```text
actual_provider_request_count = 214
unique_provider_request_count = 214
unauthorized_provider_symbols = 0
```

All actual provider requested symbols were a subset of canonical Frozen TWSE
218.

## 6. Coverage Reconciliation

Final Frozen TWSE 218 coverage:

```text
WARM_READY = 218
FAILED     = 0
MISSING    = 0
UNEXPECTED = 0
```

Counts:

```text
already_warm_count = 4
newly_warmed_count = 214
failed_count       = 0
missing_count      = 0
```

## 7. Scanner Technical Readiness

Local/cache-only readiness validation was performed without production scanner
workflow execution.

```text
TECHNICAL_READY   = 218
INSUFFICIENT_DATA = 0
LOAD_ERROR        = 0
```

This validation only checked cache loading and Production V1 required technical
feature availability. It did not run ranking, recommendation, PDF export, or a
Dashboard scan.

## 8. After Fingerprints

Legacy DB:

```text
sha256     = def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa
rows       = 1185744
symbols    = 222
duplicates = 0
integrity  = ok
```

Research DB:

```text
sha256            = 6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073
rows              = 473481
symbols           = 222
duplicates        = 0
integrity         = ok
semantic_checksum = a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

Live DB:

```text
sha256                       = e9c04141fd247876f61fc7e982c688aaf8c802b646a30442aa0fd54f71789e26
historical_prices_rows       = 1160362
historical_price_fetch_state = 219
symbols                      = 219
duplicates                   = 0
integrity                    = ok
min_trading_date             = 1993-01-05
max_trading_date             = 2026-08-12
```

Live DB has 219 symbols because it contains the 218 real Frozen TWSE symbols
plus the retained `LIVE_VALIDATION.TW` provenance row.

## 9. Synthetic Symbol

`LIVE_VALIDATION.TW` remains present:

```text
historical_prices rows = 1
```

It was not fetched, not part of the warm-up universe, and not part of the
scanner universe.

## 10. Regression

Targeted regressions were run with production DB test guard enabled:

```text
tests.test_live_data_store
tests.test_research_data_store
tests.test_database_config
tests.test_swing_scanner_service
tests.test_frozen_twse_research_universe_service
tests.test_technical_indicator_service
```

Result:

```text
Ran 115 tests
OK
```

Compile check:

```text
python -m compileall app.py src tests
PASS
```

Full suite was not run in this phase because it is not required and was deferred
until a later final validation phase.

## 11. Phase Status

```text
PASS
```

Safe next step:

```text
local-cache-only Frozen TWSE 218 scanner validation
```
