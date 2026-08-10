# V1 Expanded TWSE Volume Threshold Validation

## OFFICIAL FINAL RESULT

Purpose: validate whether expanded historical evidence remains directionally consistent when the research universe is widened to the materialized Frozen TWSE common-stock set.

This is expanded-universe historical validation only. It is not threshold optimization, V1.1 implementation, scanner ranking, future probability, trading recommendation, dashboard integration, or AI analysis.

## Official Inputs

- DB canonical SHA-256: `aa90f60d00e96c31630c9edede7af7a4b0ceedbb15a5fbbaf30042174920ae06`
- DB rows: `473481`
- DB symbols: `222`
- DB duplicate symbol/date groups: `0`
- DB integrity: `ok`
- SQLite mode: `mode=ro`, `PRAGMA query_only=ON`
- Listing-date snapshot: `docs/research_inputs/twse_listing_dates_2026_08_09.json`
- Official source: TWSE OpenAPI `/v1/opendata/t187ap03_L`
- Source report date: `2026-08-09`
- Source report date raw: `1150809`
- Source checksum: `496cfa5a392102d23d5900ef1a382b0cbbb4bfb503ecd454428f48dd818d719f`
- Snapshot checksum: `cc4a531dd4f821376a0e9ed138c99fc5f526c0b79879ec65499667fc63f07528`
- Snapshot records: `218`
- Listing-date coverage: `218 / 218`
- Missing listing dates: `0`
- Duplicate listing dates: `0`
- Invalid listing dates: `0`

No live listing-date fetch was performed for this final run.

## Universe

- Frozen universe version: `2026-08-current-etf-constituent-v1`
- Frozen total: `224`
- TWSE common stocks: `218`
- TPEx stocks: `6`
- Unknown exchange: `0`
- Phase 7 official research universe: `218` TWSE common stocks only
- Materialized local DB rule: four-digit `.TW` symbols in `historical_prices`, excluding `0050.TW`

The `218` stocks are retained in the universe even when a symbol has no qualified observations for a threshold. This is a 2026 current ETF constituent-based Frozen Universe, not a 2018 to 2025 historical point-in-time universe.

## Eligibility Semantics

Historical daily observations are eligible only after all of the following are true:

- official listing date has started
- at least 60 trading bars of warm-up are available after listing
- technical indicators are evaluable
- observation date is within `2018-01-01` through `2025-12-31`
- existing DB rows support the 20 trading-bar outcome horizon

Observation eligibility and outcome resolvability are separate. `evaluate_historical_outcome()` remains the outcome evaluator. Historical Hit Rate is `HIT / (HIT + MISS)`; `INCOMPLETE` and `NOT_EVALUABLE` are excluded from the denominator. When `resolved = 0`, HHR is `None`.

`7769.TW` is retained as `PARTIAL_WINDOW_VALID` with `0` eligible observations. No synthetic history is created.

## Readiness

| Readiness | Count |
|---|---:|
| FULL_WINDOW_ELIGIBLE | 190 |
| PARTIAL_WINDOW_VALID | 28 |
| DATA_QUALITY_BLOCKED | 0 |

| Year | Eligible Symbols |
|---:|---:|
| 2018 | 191 |
| 2019 | 196 |
| 2020 | 196 |
| 2021 | 200 |
| 2022 | 206 |
| 2023 | 207 |
| 2024 | 214 |
| 2025 | 217 |

Target readiness checks:

- `3711.TW`: listing date `2018-04-30`, `PARTIAL_WINDOW_VALID`, eligible observations `1809`
- `6531.TW`: listing date `2016-05-31`, `FULL_WINDOW_ELIGIBLE`, eligible observations `1830`
- `7769.TW`: listing date `2025-11-27`, `PARTIAL_WINDOW_VALID`, eligible observations `0`

## Thresholds

Only these thresholds are tested:

- `volume_ratio_20 >= 1.00`
- `volume_ratio_20 >= 1.10`
- `volume_ratio_20 >= 1.20`

`1.20` remains the formal production V1 baseline. Candidate qualification still requires the other four V1 conditions to pass and changes only the volume threshold.

## Daily Aggregate

| Threshold | n | HIT | MISS | INCOMPLETE | NOT_EVALUABLE | Resolved | HHR |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 2377 | 1991 | 386 | 0 | 0 | 2377 | 83.76% |
| 1.10 | 2072 | 1768 | 304 | 0 | 0 | 2072 | 85.33% |
| 1.20 | 1821 | 1567 | 254 | 0 | 0 | 1821 | 86.05% |

Candidate deltas versus `1.20`:

| Candidate | Observation Delta | Observation Change Rate | HIT Delta | MISS Delta | HHR Delta |
|---:|---:|---:|---:|---:|---:|
| 1.00 | +556 | +30.53% | +424 | +132 | -2.29 pp |
| 1.10 | +251 | +13.78% | +201 | +50 | -0.72 pp |

Daily qualified identity-set nesting passed:

`1.20 qualified IDs subset 1.10 qualified IDs subset 1.00 qualified IDs`

Missing `1.20` IDs from `1.10`: `0`. Missing `1.10` IDs from `1.00`: `0`.

## Per-Symbol Breadth

All `218` symbols are retained in per-symbol summaries.

| Candidate | Baseline Resolved Symbols | Positive Delta | Negative Delta | Same | Unavailable | Added-Sample Symbols |
|---:|---:|---:|---:|---:|---:|---|
| 1.00 | 155 | 34 | 36 | 85 | 63 | `2324.TW`, `3026.TW`, `3481.TW`, `4904.TW`, `6505.TW` |
| 1.10 | 155 | 32 | 21 | 102 | 63 | `4904.TW`, `6505.TW` |

Per-symbol reconciliation:

| Threshold | Symbols | n Sum | HIT Sum | MISS Sum | Resolved Sum | Zero-Observation Symbols |
|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 218 | 2377 | 1991 | 386 | 2377 | 58 |
| 1.10 | 218 | 2072 | 1768 | 304 | 2072 | 61 |
| 1.20 | 218 | 1821 | 1567 | 254 | 1821 | 63 |

Resolved sample sizes are preserved in the result model. No rank, score, or recommendation is introduced.

## Year-by-Year

| Year | Eligible Symbols | 1.00 n/HIT/MISS/HHR | 1.10 n/HIT/MISS/HHR | 1.20 n/HIT/MISS/HHR | 1.00 Delta | 1.10 Delta |
|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 191 | 26 / 23 / 3 / 88.46% | 20 / 18 / 2 / 90.00% | 20 / 18 / 2 / 90.00% | -1.54 pp | +0.00 pp |
| 2019 | 196 | 70 / 50 / 20 / 71.43% | 61 / 42 / 19 / 68.85% | 54 / 35 / 19 / 64.81% | +6.61 pp | +4.04 pp |
| 2020 | 196 | 110 / 87 / 23 / 79.09% | 93 / 76 / 17 / 81.72% | 84 / 69 / 15 / 82.14% | -3.05 pp | -0.42 pp |
| 2021 | 200 | 97 / 76 / 21 / 78.35% | 80 / 68 / 12 / 85.00% | 72 / 62 / 10 / 86.11% | -7.76 pp | -1.11 pp |
| 2022 | 206 | 99 / 77 / 22 / 77.78% | 90 / 71 / 19 / 78.89% | 81 / 66 / 15 / 81.48% | -3.70 pp | -2.59 pp |
| 2023 | 207 | 310 / 271 / 39 / 87.42% | 274 / 241 / 33 / 87.96% | 241 / 213 / 28 / 88.38% | -0.96 pp | -0.43 pp |
| 2024 | 214 | 454 / 382 / 72 / 84.14% | 413 / 355 / 58 / 85.96% | 373 / 322 / 51 / 86.33% | -2.19 pp | -0.37 pp |
| 2025 | 217 | 1211 / 1025 / 186 / 84.64% | 1041 / 897 / 144 / 86.17% | 896 / 782 / 114 / 87.28% | -2.64 pp | -1.11 pp |

Year consistency:

| Candidate | Positive Years | Negative Years | Same Years | Unavailable Years | Years With Resolved Samples |
|---:|---:|---:|---:|---:|---:|
| 1.00 | 1 | 7 | 0 | 0 | 8 |
| 1.10 | 1 | 6 | 1 | 0 | 8 |
| 1.20 | n/a | n/a | n/a | n/a | 8 |

## Overlap-Reduced View

Overlap reduction uses explicit prepared trading-bar indexes with 20 trading-bar spacing inside each symbol. Different symbols are independent. Reduced IDs are subsets of daily qualified IDs per threshold.

| Threshold | Daily n | Reduced n | HIT | MISS | INCOMPLETE | NOT_EVALUABLE | Resolved | HHR | Delta vs Reduced 1.20 | Contributing Symbols |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 2377 | 841 | 728 | 113 | 0 | 0 | 841 | 86.56% | -1.11 pp | 160 |
| 1.10 | 2072 | 800 | 700 | 100 | 0 | 0 | 800 | 87.50% | -0.18 pp | 157 |
| 1.20 | 1821 | 771 | 676 | 95 | 0 | 0 | 771 | 87.68% | +0.00 pp | 155 |

Reduced invariants:

- spacing invariant: PASS
- reduced subset of daily IDs by threshold: PASS
- symbol-level de-overlap only: PASS

## Concentration

| Threshold | 2025 Share | Largest-Year Share | Top-1 Symbol | Top-2 Symbols | Top-5 Symbols | Top-10 Symbols |
|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 50.95% | 2025 / 50.95% | 4.38% | 7.40% | 15.36% | 26.21% |
| 1.10 | 50.24% | 2025 / 50.24% | 3.23% | 6.27% | 14.38% | 25.29% |
| 1.20 | 49.20% | 2025 / 49.20% | 3.29% | 6.53% | 14.72% | 25.10% |

Concentration remains a factual research output only. No numeric score is produced.

## FULL 190 Secondary View

| Threshold | Symbols | n | Resolved | HHR |
|---:|---:|---:|---:|---:|
| 1.00 | 190 | 2147 | 2147 | 83.56% |
| 1.10 | 190 | 1870 | 1870 | 85.19% |
| 1.20 | 190 | 1640 | 1640 | 85.73% |

## PARTIAL 28 View

| Threshold | Symbols | n | Resolved | HHR |
|---:|---:|---:|---:|---:|
| 1.00 | 28 | 230 | 230 | 85.65% |
| 1.10 | 28 | 202 | 202 | 86.63% |
| 1.20 | 28 | 181 | 181 | 88.95% |

`7769.TW` remains in the `PARTIAL_WINDOW_VALID` subset identity even though it contributes `0` observations.

## Old-Five Benchmark Comparison

Daily benchmark:

| Threshold | Official n | Old-Five n | Official HHR | Old-Five HHR | HHR Difference |
|---:|---:|---:|---:|---:|---:|
| 1.00 | 2377 | 114 | 83.76% | 92.11% | -8.35 pp |
| 1.10 | 2072 | 96 | 85.33% | 91.67% | -6.34 pp |
| 1.20 | 1821 | 73 | 86.05% | 90.41% | -4.36 pp |

Reduced benchmark:

| Threshold | Official Reduced n | Old-Five Reduced n | Official Reduced HHR | Old-Five Reduced HHR | HHR Difference |
|---:|---:|---:|---:|---:|---:|
| 1.00 | 841 | 36 | 86.56% | 88.89% | -2.33 pp |
| 1.10 | 800 | 35 | 87.50% | 88.57% | -1.07 pp |
| 1.20 | 771 | 32 | 87.68% | 84.38% | +3.30 pp |

These are factual comparisons only. They do not affect expanded calculations.

## NON_FINAL_FALLBACK_REFERENCE

Prior DB-first-date fallback result is retained only as a non-final diagnostic reference.

Daily official versus fallback:

| Threshold | Official n | Fallback n | n Delta | Official HHR | Fallback HHR | HHR Delta |
|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 2377 | 2486 | -109 | 83.76% | 83.75% | +0.01 pp |
| 1.10 | 2072 | 2171 | -99 | 85.33% | 85.31% | +0.02 pp |
| 1.20 | 1821 | 1912 | -91 | 86.05% | 86.14% | -0.09 pp |

Reduced official versus fallback:

| Threshold | Official n | Fallback n | n Delta | Official HHR | Fallback HHR | HHR Delta |
|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 841 | 880 | -39 | 86.56% | 86.36% | +0.20 pp |
| 1.10 | 800 | 836 | -36 | 87.50% | 87.32% | +0.18 pp |
| 1.20 | 771 | 807 | -36 | 87.68% | 87.48% | +0.20 pp |

Fallback is not a final listing-date source and must not be promoted to official evidence.

## Evidence Classifications

| Candidate | Aggregate | Symbol Breadth | Year Consistency | Year Coverage | Overlap-Reduced Persistence | Concentration | Full-vs-Partial Robustness |
|---:|---|---|---|---|---|---|---|
| 1.00 | WEAK | WEAK | MIXED | MIXED | WEAK | MIXED | MIXED |
| 1.10 | WEAK | SUPPORTED | MIXED | MIXED | WEAK | MIXED | MIXED |

Reasons:

- `1.00` aggregate HHR is `-2.29 pp` below `1.20`; symbol breadth has `34` positive versus `36` negative symbols; year consistency is `1` positive and `7` negative years; overlap-reduced HHR is `-1.11 pp` below reduced `1.20`; 2025 share is `50.95%`; partial subset HHR is higher than full subset but both remain below their own `1.20` subset baselines.
- `1.10` aggregate HHR is `-0.72 pp` below `1.20`; symbol breadth is broader with `32` positive versus `21` negative symbols and `102` same; year consistency is `1` positive, `6` negative, `1` same; overlap-reduced HHR is `-0.18 pp` below reduced `1.20`; 2025 share is `50.24%`; partial subset HHR is higher than full subset but both remain below their own `1.20` subset baselines.

Overall evidence relative to prior small-universe research evidence:

- `1.00`: `EVIDENCE_MIXED`
- `1.10`: `EVIDENCE_MIXED`

This is not a V1.1 decision.

## Bias And Scope Warnings

The 218-stock pool comes from 2026 current ETF constituents, not 2018 to 2025 point-in-time constituents. Results have survivorship bias and constituent look-back bias. Phase 7 supports expanded breadth historical validation only; it is not a bias-free historical strategy test.

No statistical significance claim is made. No p-value, confidence interval, bootstrap, hypothesis test, probability, ranking, score, or recommendation is introduced.

Production V1 remains unchanged: `volume_ratio_20 >= 1.20`. V1.1 implementation is not started. Dashboard integration is not started. No Yahoo fetch is performed. No DB write is performed.
