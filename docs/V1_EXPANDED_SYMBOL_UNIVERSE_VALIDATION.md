# V1 Expanded Symbol Universe Validation

## Research Purpose

V1 Condition Contribution Research Batch 4 answers one narrow question:

When the symbol universe is expanded using a deterministic local Taiwan universe, do `volume_ratio_20 >= 1.00` and `volume_ratio_20 >= 1.10` still show similar historical evidence relative to the formal V1 `1.20` threshold?

This is external breadth validation and robustness research. It is not threshold optimization, V1.1 implementation, scanner logic, ranking, future probability, recommendation, or AI analysis.

## Selection-Bias Prevention

Universe selection was frozen before threshold results were calculated.

Selection used only local SQLite coverage metadata from `data/stocks.db`:

- candidate source: symbols already present in `historical_prices`
- deterministic Taiwan filter: symbols ending in `.TW` or `.TWO`
- coverage rule: enough pre-window, in-window, and post-window price bars
- data quality rule: no duplicate dates and no unusable OHLCV rows

Selection did not use Historical Hit Rate, HIT / MISS results, candidate threshold results, scanner output, V1 match frequency, backtest result, profitability, ranking, or score.

## Universe Freeze

Frozen config:

- research start: `2018-01-01`
- research end: `2025-12-31`
- warm-up: `60` trading bars
- outcome horizon: `20` trading bars
- thresholds: `1.00`, `1.10`, `1.20`
- baseline: `1.20`
- source: `data/stocks.db` via SQLite `mode=ro`

Local DB limitation: `historical_prices` had only `8` distinct symbols. Only `6` were Taiwan symbols, so this Batch expands the old five to six symbols but does not reach the target `15` to `30` symbols. No network backfill was used.

## Coverage Audit

| Symbol | Earliest | Latest | Window Rows | Warm-up Bars | Post-window Bars | Included | Reason |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `0050.TW` | 2009-01-02 | 2026-08-07 | 1,944 | 2,217 | 144 | Yes |  |
| `2330.TW` | 2000-01-04 | 2026-08-07 | 1,943 | 4,526 | 144 | Yes |  |
| `2337.TW` | 2000-01-04 | 2026-08-07 | 1,943 | 4,526 | 144 | Yes |  |
| `2404.TW` | 2000-01-04 | 2026-08-07 | 1,943 | 4,526 | 144 | Yes | zero sample retained |
| `2454.TW` | 2001-07-23 | 2026-08-07 | 1,943 | 4,122 | 144 | Yes |  |
| `6488.TWO` | 2014-10-30 | 2026-08-07 | 1,942 | 776 | 144 | Yes |  |
| `AAPL` | 1980-12-12 | 2026-08-07 | 2,011 | 9,344 | 150 | No | `EXCLUDED_NOT_TAIWAN_UNIVERSE` |
| `NVDA` | 1999-01-22 | 2026-08-07 | 2,011 | 4,767 | 150 | No | `EXCLUDED_NOT_TAIWAN_UNIVERSE` |

All original five symbols were retained. No symbol was excluded because of Historical Hit Rate or threshold result.

## Expanded Aggregate

| Threshold | n | HIT | MISS | INCOMPLETE | NOT_EVALUABLE | Resolved | HHR | Delta vs 1.20 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 | 124 | 114 | 10 | 0 | 0 | 124 | 91.94% | +1.94 pp |
| 1.10 | 104 | 95 | 9 | 0 | 0 | 104 | 91.35% | +1.35 pp |
| 1.20 | 80 | 72 | 8 | 0 | 0 | 80 | 90.00% | +0.00 pp |

## Per-Symbol Results

| Symbol | Threshold | n | HIT | MISS | Resolved | HHR | Delta vs 1.20 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `0050.TW` | 1.00 | 34 | 32 | 2 | 34 | 94.12% | -1.53 pp |
| `0050.TW` | 1.10 | 30 | 28 | 2 | 30 | 93.33% | -2.32 pp |
| `0050.TW` | 1.20 | 23 | 22 | 1 | 23 | 95.65% | +0.00 pp |
| `2330.TW` | 1.00 | 55 | 53 | 2 | 55 | 96.36% | +0.07 pp |
| `2330.TW` | 1.10 | 41 | 40 | 1 | 41 | 97.56% | +1.26 pp |
| `2330.TW` | 1.20 | 27 | 26 | 1 | 27 | 96.30% | +0.00 pp |
| `2337.TW` | 1.00 | 17 | 12 | 5 | 17 | 70.59% | +1.84 pp |
| `2337.TW` | 1.10 | 17 | 12 | 5 | 17 | 70.59% | +1.84 pp |
| `2337.TW` | 1.20 | 16 | 11 | 5 | 16 | 68.75% | +0.00 pp |
| `2404.TW` | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A |
| `2404.TW` | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A |
| `2404.TW` | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A |
| `2454.TW` | 1.00 | 8 | 8 | 0 | 8 | 100.00% | +0.00 pp |
| `2454.TW` | 1.10 | 8 | 8 | 0 | 8 | 100.00% | +0.00 pp |
| `2454.TW` | 1.20 | 7 | 7 | 0 | 7 | 100.00% | +0.00 pp |
| `6488.TWO` | 1.00 | 10 | 9 | 1 | 10 | 90.00% | +4.29 pp |
| `6488.TWO` | 1.10 | 8 | 7 | 1 | 8 | 87.50% | +1.79 pp |
| `6488.TWO` | 1.20 | 7 | 6 | 1 | 7 | 85.71% | +0.00 pp |

## Symbol-Breadth Summary

| Candidate | Baseline Symbols Resolved | Positive Delta | Negative Delta | Same Delta | Unavailable |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 vs 1.20 | 5 | 3 | 1 | 1 | 1 |
| 1.10 vs 1.20 | 5 | 3 | 1 | 1 | 1 |

This is a count summary only. It is not a score and does not select a winner.

## Per-Year Results

| Year | Threshold | n | HIT | MISS | Resolved | HHR | Delta vs 1.20 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2018 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2018 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2019 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2019 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2019 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2020 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2020 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2020 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2021 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2021 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2021 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2022 | 1.00 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2022 | 1.10 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2022 | 1.20 | 0 | 0 | 0 | 0 | N/A | N/A |
| 2023 | 1.00 | 7 | 6 | 1 | 7 | 85.71% | +5.71 pp |
| 2023 | 1.10 | 6 | 5 | 1 | 6 | 83.33% | +3.33 pp |
| 2023 | 1.20 | 5 | 4 | 1 | 5 | 80.00% | +0.00 pp |
| 2024 | 1.00 | 28 | 27 | 1 | 28 | 96.43% | +1.43 pp |
| 2024 | 1.10 | 24 | 23 | 1 | 24 | 95.83% | +0.83 pp |
| 2024 | 1.20 | 20 | 19 | 1 | 20 | 95.00% | +0.00 pp |
| 2025 | 1.00 | 89 | 81 | 8 | 89 | 91.01% | +1.92 pp |
| 2025 | 1.10 | 74 | 67 | 7 | 74 | 90.54% | +1.45 pp |
| 2025 | 1.20 | 55 | 49 | 6 | 55 | 89.09% | +0.00 pp |

Effective years with resolved samples:

- `1.00`: `3 / 8`
- `1.10`: `3 / 8`
- `1.20`: `3 / 8`

Expanded universe did not create resolved samples for `2018` through `2022`.

## Overlap-Reduced Results

Overlap-reduced selection uses explicit prepared trading-bar indexes from the prepared price series, not outcome-observation ordinal positions. Selected samples are at least `20` prepared trading bars apart for the same symbol.

| Threshold | Daily n | Reduced n | HIT | MISS | Resolved | HHR | Delta vs reduced 1.20 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 | 124 | 39 | 35 | 4 | 39 | 89.74% | +4.03 pp |
| 1.10 | 104 | 38 | 34 | 4 | 38 | 89.47% | +3.76 pp |
| 1.20 | 80 | 35 | 30 | 5 | 35 | 85.71% | +0.00 pp |

## Concentration Metrics

| Threshold | Latest Year | Latest-Year Share | Top-2 Symbol Share | Top-5 Symbol Share |
| ---: | ---: | ---: | ---: | ---: |
| 1.00 | 2025 | 71.77% | 71.77% | 100.00% |
| 1.10 | 2025 | 71.15% | 68.27% | 100.00% |
| 1.20 | 2025 | 68.75% | 62.50% | 100.00% |

Concentration remains high because the expanded universe has only six local Taiwan symbols and `2404.TW` has zero qualified samples.

## Old-Five Benchmark Comparison

Daily benchmark:

| Threshold | Expanded n | Old-Five n | n Difference | Expanded HHR | Old-Five HHR | HHR Difference |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 | 124 | 114 | +10 | 91.94% | 92.11% | -0.17 pp |
| 1.10 | 104 | 96 | +8 | 91.35% | 91.67% | -0.32 pp |
| 1.20 | 80 | 73 | +7 | 90.00% | 90.41% | -0.41 pp |

Overlap-reduced benchmark:

| Threshold | Expanded n | Old-Five n | n Difference | Expanded HHR | Old-Five HHR | HHR Difference |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 | 39 | 36 | +3 | 89.74% | 88.89% | +0.85 pp |
| 1.10 | 38 | 35 | +3 | 89.47% | 88.57% | +0.90 pp |
| 1.20 | 35 | 32 | +3 | 85.71% | 84.38% | +1.33 pp |

## Candidate Robustness Classification

| Threshold | Aggregate | Symbol Breadth | Year Coverage | Overlap-Reduced | Concentration |
| ---: | --- | --- | --- | --- | --- |
| 1.00 | SUPPORTED | SUPPORTED | MIXED | SUPPORTED | MIXED |
| 1.10 | SUPPORTED | SUPPORTED | MIXED | SUPPORTED | MIXED |

Interpretation: evidence is strengthened on aggregate and overlap-reduced views, while year coverage and concentration remain limited. This does not create a V1.1 decision.

## Live DB Safety

DB before and after live calculation matched:

- size: `7,327,744` bytes
- SHA-256: `dcd65c9f2e579164728eaadbbc7b6926f3d6513bcdcac2cb36154bc8961f9aa5`
- SQLite access mode: `mode=ro`

No DB initialization, migration, write, Yahoo refetch, network fallback, schema change, or persistence was performed.

## Protected Logic Audit

This Batch did not modify:

- `technical_example_v1`
- formal V1 `volume_ratio_20 >= 1.20`
- scanner
- technical formulas
- outcome semantics
- backtest
- Historical Replay
- Walk-Forward Replay
- Replay Analytics
- OOS
- database schema or content
- OpenAI / AI logic

## Limitations

- Local DB had only six Taiwan symbols, below the target `15` to `30`.
- `2404.TW` remains a zero-sample symbol, which is preserved as research information.
- Effective resolved years remain `2023` through `2025` only.
- Sample concentration remains high.
- This Batch stops at descriptive evidence and does not start V1.1, dashboard integration, RSI sensitivity, distance sensitivity, V2, or AI analysis.
