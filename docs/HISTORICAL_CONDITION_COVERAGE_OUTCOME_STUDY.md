# Historical Condition Coverage Outcome Study

Phase 1 research-only study for canonical `technical_example_v1` condition coverage.

## Research Question

Compare daily historical outcomes for exactly `5/5`, `4/5`, and `3/5` condition coverage, including missing-condition and missing-pair splits.

## Dataset / Universe

- Date window: `2018-01-01` through `2025-12-31`
- Universe: `frozen_twse_research_universe_2026_08_09`
- Frozen symbol count: `218`
- FULL_WINDOW_ELIGIBLE: `190`
- PARTIAL_WINDOW_VALID: `28`
- DATA_QUALITY_BLOCKED: `0`

Eligibility uses official listing date plus 60 trading-bar warm-up. Not-yet-listed symbols are not treated as zero-observation failures.

Outcome semantics reuse the attached canonical historical outcome `raw_high_breakout_60d_within_20d_v1`; this report does not create a second HIT/MISS definition.

## Overall

| Coverage | n | HIT | MISS | HHR | Sample |
| --- | --- | --- | --- | --- | --- |
| 5/5 | 1821 | 1567 | 254 | 86.05% | ADEQUATE |
| 4/5 | 33912 | 22506 | 11406 | 66.37% | ADEQUATE |
| 3/5 | 114716 | 62050 | 52666 | 54.09% | ADEQUATE |

- 4/5 minus 5/5 HHR delta: `-19.69 pp`
- 3/5 minus 5/5 HHR delta: `-31.96 pp`
- 5/5 control baseline reconciled: `True`

## 4/5 Missing Condition

| Missing condition | n | HIT | MISS | HHR | Share | Sample |
| --- | --- | --- | --- | --- | --- | --- |
| analysis_close_vs_sma_20 | 19 | 12 | 7 | 63.16% | 0.06% | SMALL_SAMPLE |
| sma_20_vs_sma_60 | 307 | 214 | 93 | 69.71% | 0.91% | ADEQUATE |
| volume_ratio_20 | 2691 | 2032 | 659 | 75.51% | 7.94% | ADEQUATE |
| rsi_14 | 2853 | 2771 | 82 | 97.13% | 8.41% | ADEQUATE |
| distance_to_prior_60d_high | 28042 | 17477 | 10565 | 62.32% | 82.69% | ADEQUATE |

## 4/5 Missing Volume Subgroups

| Subgroup | n | HIT | MISS | HHR | Sample |
| --- | --- | --- | --- | --- | --- |
| MISSING_volume_ratio_20__volume_lt_1_10 | 2440 | 1831 | 609 | 75.04% | ADEQUATE |
| MISSING_volume_ratio_20__volume_1_10_to_lt_1_20 | 251 | 201 | 50 | 80.08% | ADEQUATE |

V1.1 incremental identity consistency: `True`.

## 3/5 Missing Pairs

| Missing pair | n | HIT | MISS | HHR | Share | Sample |
| --- | --- | --- | --- | --- | --- | --- |
| MISSING_volume_ratio_20+distance_to_prior_60d_high | 79507 | 43062 | 36445 | 54.16% | 69.31% | ADEQUATE |
| MISSING_sma_20_vs_sma_60+distance_to_prior_60d_high | 18572 | 5572 | 13000 | 30.00% | 16.19% | ADEQUATE |
| MISSING_rsi_14+distance_to_prior_60d_high | 12163 | 10690 | 1473 | 87.89% | 10.60% | ADEQUATE |
| MISSING_analysis_close_vs_sma_20+distance_to_prior_60d_high | 2337 | 981 | 1356 | 41.98% | 2.04% | ADEQUATE |
| MISSING_volume_ratio_20+rsi_14 | 1405 | 1303 | 102 | 92.74% | 1.22% | ADEQUATE |
| MISSING_sma_20_vs_sma_60+volume_ratio_20 | 283 | 127 | 156 | 44.88% | 0.25% | ADEQUATE |
| MISSING_sma_20_vs_sma_60+rsi_14 | 244 | 225 | 19 | 92.21% | 0.21% | ADEQUATE |
| MISSING_analysis_close_vs_sma_20+volume_ratio_20 | 157 | 74 | 83 | 47.13% | 0.14% | ADEQUATE |
| MISSING_analysis_close_vs_sma_20+rsi_14 | 48 | 16 | 32 | 33.33% | 0.04% | ADEQUATE |

## Year Robustness

| Year | 5/5 n/HHR | 4/5 n/HHR | 3/5 n/HHR |
| --- | --- | --- | --- |
| 2018 | 20 / 90.00% | 2941 / 57.70% | 11736 / 45.28% |
| 2019 | 54 / 64.81% | 4259 / 66.94% | 16948 / 59.26% |
| 2020 | 84 / 82.14% | 4158 / 64.84% | 15157 / 56.15% |
| 2021 | 72 / 86.11% | 4340 / 66.18% | 15998 / 56.43% |
| 2022 | 81 / 81.48% | 3005 / 57.37% | 11142 / 45.02% |
| 2023 | 241 / 88.38% | 5218 / 70.56% | 17084 / 60.61% |
| 2024 | 373 / 86.33% | 4473 / 67.34% | 14009 / 53.11% |
| 2025 | 896 / 87.28% | 5518 / 71.98% | 12642 / 50.18% |

## Subperiod Robustness

| Period | 5/5 n/HHR | 4/5 n/HHR | 3/5 n/HHR |
| --- | --- | --- | --- |
| 2018-2020 | 158 / 77.22% | 11358 / 63.78% | 43841 / 54.44% |
| 2021-2023 | 394 / 86.55% | 12563 / 65.89% | 44224 / 55.17% |
| 2024 | 373 / 86.33% | 4473 / 67.34% | 14009 / 53.11% |
| 2025 | 896 / 87.28% | 5518 / 71.98% | 12642 / 50.18% |

## Concentration

| Coverage | Symbols | Median obs/symbol | Top1 | Top5 | Top10 | 2025 | 2024+2025 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5/5 | 155 | 7.00 | 3.29% | 14.72% | 25.10% | 49.20% | 69.69% |
| 4/5 | 217 | 158.00 | 0.94% | 3.97% | 7.59% | 16.27% | 29.46% |
| 3/5 | 217 | 566.00 | 0.69% | 3.34% | 6.51% | 11.02% | 23.23% |

## Evidence Classification

- 4/5 overall: `SUPPORTED`
- 3/5 overall: `SUPPORTED`

These classifications describe research evidence only. They are not production promotion, ranking, score, probability, confidence, alert, or recommendation.

## Safety Boundary

- Production V1 remains unchanged and authoritative.
- No Dashboard behavior was modified.
- No database write was performed.
- No network fetch was performed.
- No ranking, score, probability, confidence, recommendation, alert, or scanner promotion was created.

## Survivorship / Look-back Warning

Frozen universe is derived from 2026 current ETF constituents, not 2018-2025 point-in-time constituents; survivorship and constituent look-back bias remain.

Checksum: `b58f00ebf9cac16c1ce5bed3720b3eb7036ff456bb2d28862ffccd66c8e02632`
