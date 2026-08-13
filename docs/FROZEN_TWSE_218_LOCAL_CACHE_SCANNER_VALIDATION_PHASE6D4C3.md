# Frozen TWSE 218 Local-Cache Scanner Validation Phase 6D-4C-3

## 1. Scope

Phase 6D-4C-3 validated that the current scanner can run against the warmed
formal Live Store without provider access.

Execution mode:

```text
local-cache-only
network/provider calls = forbidden
price source = data/live/stocks_live.db
```

No Yahoo fetch, yfinance fetch, provider network fetch, ETF universe refetch,
listing-date refetch, cache refresh, DB write, Dashboard interaction, PDF
generation, Long-Term Growth work, commit, or push was performed.

## 2. Runtime Context

```text
active_db_mode     = physical_split
live_db_path       = data/live/stocks_live.db
research_snapshot  = research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1
scanner_as_of_date = 2026-08-12
```

## 3. Universe

Canonical Frozen TWSE 218 was loaded through the existing universe loader and
released Research Store.

```text
universe_id      = frozen_twse_research_universe_2026_08_09
universe_version = 2026-08-current-etf-constituent-v1
symbols          = 218
unique_symbols   = 218
fingerprint      = db73096e24026e0d9b3388e15a29abeed10b87214d2fab795bd274858447dbb9
```

`LIVE_VALIDATION.TW` is not part of the universe and was not scanned.

## 4. Store Fingerprints

Before and after scanner validation:

```text
Legacy DB SHA   = def21e8d78d3027299c264ca9c997765ae54772f02a25f886880ab21d6cec4aa
Research DB SHA = 6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073
Live DB SHA     = e9c04141fd247876f61fc7e982c688aaf8c802b646a30442aa0fd54f71789e26
```

All three stayed unchanged.

Final DB state:

```text
Legacy rows/symbols/duplicates/integrity   = 1185744 / 222 / 0 / ok
Research rows/symbols/duplicates/integrity = 473481 / 222 / 0 / ok
Live rows/symbols/duplicates/integrity     = 1160362 / 219 / 0 / ok
Live fetch-state rows                      = 219
```

Research semantic checksum:

```text
a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91
```

## 5. Scanner Result

Scanner validation result:

```text
requested_symbols = 218
loaded_symbols    = 218
evaluated_symbols = 218
load_errors       = 0
not_evaluable     = 0
```

Production V1 result:

```text
Formal V1 hit count = 3
Formal V1 identities/order = 6446.TW, 4763.TW, 8464.TW
```

The scanner used Production V1 and the existing ranking/order semantics. No
Production V1, V1.1, technical formula, ranking, or ordering logic was changed.

## 6. Candidate Display Projection

Current local-cache classification:

```text
Formal V1 = 3
Priority A = 2
Priority B = 17
Watch = 7
Other 4/5 = 0
3/5 = 67
Below = 122
sum = 218
reconciled = true
```

Dashboard projection validation:

```text
coverage_view_built = true
experimental_projection_built = true
projection_reconciled = true
```

No Streamlit user interaction was performed.

## 7. Baseline Comparability

Accepted Phase 3 baseline:

```text
Formal V1 = 13
Priority A = 8
Priority B = 12
Watch = 12
Other 4/5 = 5
3/5 = 49
Below = 119
```

Comparison result:

```text
NOT_DIRECTLY_COMPARABLE_AS_OF_DIFFERENCE
```

Reason:

```text
Current Live Store scanner as-of date is 2026-08-12. The accepted Phase 3
baseline is a fixed historical artifact, not the same current-date input.
```

The current result is therefore reported as a live-cache scanner validation
result, not as a regression against the fixed Phase 3 artifact.

## 8. 2368 / 2884 Checks

`2368.TW`:

```text
Production V1 status = NO_MATCH
classification = EXPLORATORY
coverage = 3/5
missing = sma_20_vs_sma_60, distance_to_prior_60d_high
V1.1 badge = N/A
V1.1 status = NO_MATCH
as_of_date = 2026-08-12
```

`2884.TW`:

```text
Production V1 status = NO_MATCH
classification = BELOW_DISPLAY_SCOPE
coverage = 2/5
missing = analysis_close_vs_sma_20, volume_ratio_20, distance_to_prior_60d_high
V1.1 badge = N/A
V1.1 status = NO_MATCH
as_of_date = 2026-08-12
```

## 9. Safety Audit

Network/provider audit:

```text
provider_calls = 0
unauthorized_fetch = false
legacy_fallback = false
research_price_fallback = false
```

DB write audit:

```text
db_write_detected = false
```

PDF boundary:

```text
PDF generation performed = false
PDF service DB/provider source check = DB-agnostic
```

## 10. Regression

Targeted regressions were run with the production DB test guard enabled:

```text
tests.test_swing_scanner_service
tests.test_live_data_store
tests.test_research_data_store
tests.test_database_config
tests.test_frozen_twse_research_universe_service
tests.test_candidate_display_research_service
tests.test_dashboard
tests.test_swing_scanner_pdf_export_service
```

Result:

```text
Ran 145 tests
OK
```

Compile check:

```text
python -m compileall app.py src tests
PASS
```

Full suite:

```text
FULL_SUITE_DEFERRED_FOR_SAFETY
```

Reason: after runtime cutover, full-suite execution cannot yet be proven to
avoid all formal Live Store writes.

## 11. Artifact

Validation artifact:

```text
/tmp/frozen_twse_218_local_cache_scanner_validation_phase6d4c3.json
```

## 12. Phase Status

```text
PASS_WITH_GAPS
```

The runtime scanner validation itself passed. The gap is baseline
non-comparability due to as-of date/input difference.
