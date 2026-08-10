# V1.1 Volume Threshold Time Robustness

## Scope

This Batch 2 research validation evaluates only:

- active V1.1 research candidate: `volume_ratio_20 >= 1.10`
- formal production V1 baseline: `volume_ratio_20 >= 1.20`

`1.00` was dropped from the active V1.1 candidate set in the prior decision review and is not re-researched here. No new threshold such as `1.05`, `1.08`, `1.12`, or `1.15` is introduced.

This is read-only research validation. It does not modify production V1, SignalDefinition, scanner logic, technical formulas, outcome semantics, backtest, Historical Replay, Walk-Forward, OOS, Dashboard, database, or AI/OpenAI logic.

## Inputs

- DB canonical SHA-256: `aa90f60d00e96c31630c9edede7af7a4b0ceedbb15a5fbbaf30042174920ae06`
- SQLite access: `mode=ro`, `PRAGMA query_only=ON`
- Official listing-date snapshot: `docs/research_inputs/twse_listing_dates_2026_08_09.json`
- Snapshot checksum: `cc4a531dd4f821376a0e9ed138c99fc5f526c0b79879ec65499667fc63f07528`
- Snapshot records: `218`
- Listing-date coverage: `218 / 218`
- Frozen TWSE symbols: `218`
- Readiness: FULL `190`, PARTIAL `28`, BLOCKED `0`

Year eligibility remains:

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

## Phase 7 Baseline Reproduction

| Threshold | n | HIT | MISS | INCOMPLETE | NOT_EVALUABLE | Resolved | HHR | Delta vs 1.20 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.10 | 2072 | 1768 | 304 | 0 | 0 | 2072 | 85.33% | -0.72 pp |
| 1.20 | 1821 | 1567 | 254 | 0 | 0 | 1821 | 86.05% | +0.00 pp |

Reproduction passed. No `1.00` active analysis was run.

## Fixed Sub-Periods

The periods were fixed before this run:

- `PERIOD_A`: `2018-01-01` to `2020-12-31`
- `PERIOD_B`: `2021-01-01` to `2023-12-31`
- `PERIOD_C`: `2024-01-01` to `2024-12-31`
- `PERIOD_D`: `2025-01-01` to `2025-12-31`

Period grouping uses `observation.trading_date`, not outcome hit date, future high date, or fetch date.

## Daily Sub-Period Results

| Period | Eligible Symbols | Threshold | n | HIT | MISS | Resolved | HHR |
|---|---:|---:|---:|---:|---:|---:|---:|
| PERIOD_A | 196 | 1.10 | 174 | 136 | 38 | 174 | 78.16% |
| PERIOD_A | 196 | 1.20 | 158 | 122 | 36 | 158 | 77.22% |
| PERIOD_B | 207 | 1.10 | 444 | 380 | 64 | 444 | 85.59% |
| PERIOD_B | 207 | 1.20 | 394 | 341 | 53 | 394 | 86.55% |
| PERIOD_C | 214 | 1.10 | 413 | 355 | 58 | 413 | 85.96% |
| PERIOD_C | 214 | 1.20 | 373 | 322 | 51 | 373 | 86.33% |
| PERIOD_D | 217 | 1.10 | 1041 | 897 | 144 | 1041 | 86.17% |
| PERIOD_D | 217 | 1.20 | 896 | 782 | 114 | 896 | 87.28% |

1.10 versus 1.20:

| Period | Observation Delta | Observation Change Rate | HIT Delta | MISS Delta | HHR Delta | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| PERIOD_A | +16 | +10.13% | +14 | +2 | +0.95 pp | SUPPORTED |
| PERIOD_B | +50 | +12.69% | +39 | +11 | -0.96 pp | SUPPORTED |
| PERIOD_C | +40 | +10.72% | +33 | +7 | -0.37 pp | MIXED |
| PERIOD_D | +145 | +16.18% | +115 | +30 | -1.11 pp | MIXED |

Sub-period reconciliation:

| Threshold | n Sum | HIT Sum | MISS Sum |
|---:|---:|---:|---:|
| 1.10 | 2072 | 1768 | 304 |
| 1.20 | 1821 | 1567 | 254 |

The sub-period sums exactly reconcile to the Phase 7 full-window totals.

## Period Symbol Breadth

| Period | Baseline Resolved Symbols | Positive | Negative | Same | Unavailable | Candidate Added Symbols |
|---|---:|---:|---:|---:|---:|---|
| PERIOD_A | 16 | 3 | 1 | 12 | 202 | none |
| PERIOD_B | 58 | 7 | 6 | 45 | 160 | none |
| PERIOD_C | 83 | 3 | 4 | 76 | 135 | none |
| PERIOD_D | 147 | 17 | 14 | 116 | 71 | `4904.TW`, `6505.TW` |

This breadth view is sample-size aware: PERIOD_A has very few baseline resolved symbols, while PERIOD_D dominates the available breadth.

## Period Concentration

| Period | Threshold | n | Largest Symbol | Largest Symbol n | Top-1 | Top-2 | Top-5 | Top-10 |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| PERIOD_A | 1.10 | 174 | `2305.TW` | 26 | 14.94% | 26.44% | 58.05% | 94.25% |
| PERIOD_A | 1.20 | 158 | `2305.TW` | 26 | 16.46% | 28.48% | 58.23% | 93.67% |
| PERIOD_B | 1.10 | 444 | `2466.TW` | 34 | 7.66% | 15.09% | 31.98% | 51.58% |
| PERIOD_B | 1.20 | 394 | `8033.TW` | 30 | 7.61% | 14.21% | 30.71% | 50.00% |
| PERIOD_C | 1.10 | 413 | `2406.TW` | 28 | 6.78% | 12.11% | 23.73% | 38.50% |
| PERIOD_C | 1.20 | 373 | `2406.TW` | 24 | 6.43% | 11.53% | 23.86% | 39.41% |
| PERIOD_D | 1.10 | 1041 | `2834.TW` | 35 | 3.36% | 6.05% | 12.68% | 21.71% |
| PERIOD_D | 1.20 | 896 | `2834.TW` | 27 | 3.01% | 5.58% | 12.28% | 20.65% |

Earlier periods have higher symbol concentration because samples are much smaller. PERIOD_D has lower symbol concentration but dominates total observations.

## Excluding 2025 View

This is not period tuning. It is the pre-declared full result minus `PERIOD_D` concentration sensitivity view.

| Window | Threshold | n | HIT | MISS | Resolved | HHR |
|---|---:|---:|---:|---:|---:|---:|
| 2018-2024 | 1.10 | 1031 | 871 | 160 | 1031 | 84.48% |
| 2018-2024 | 1.20 | 925 | 785 | 140 | 925 | 84.86% |

1.10 versus 1.20 without 2025:

- observation delta: `+106`
- observation change rate: `+11.46%`
- HIT delta: `+86`
- MISS delta: `+20`
- HHR delta: `-0.38 pp`

The sample-expansion property persists without 2025, and the HHR gap narrows relative to the full-window daily gap.

## First-Qualification Event Definition

For each symbol and each threshold independently, observations are sorted by trading date. An event is created only when qualification state changes from `NOT_QUALIFIED` to `QUALIFIED`.

`QUALIFIED` means:

- the other four V1 conditions pass
- `volume_ratio_20 >= threshold`

Continuous qualified days inside the same episode create only one event. A new event can occur only after qualification returns to `NOT_QUALIFIED` and later becomes `QUALIFIED` again.

Event outcome reuses the attached historical outcome on the event start observation. No new outcome calculation is introduced.

## First-Qualification Event Results

| Threshold | Daily Qualified n | Events | HIT | MISS | INCOMPLETE | NOT_EVALUABLE | Resolved | Event HHR | Contributing Symbols |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.10 | 2072 | 1458 | 1259 | 199 | 0 | 0 | 1458 | 86.35% | 157 |
| 1.20 | 1821 | 1327 | 1150 | 177 | 0 | 0 | 1327 | 86.66% | 155 |

1.10 versus 1.20 event view:

- event-count delta: `+131`
- event-count change rate: `+9.87%`
- HIT delta: `+109`
- MISS delta: `+22`
- event HHR delta: `-0.31 pp`

Descriptive classification: `approximately comparable`. The candidate remains below 1.20, but not materially below in this event-level view.

## Event Sub-Period Results

| Period | Threshold | Events | HIT | MISS | Resolved | Event HHR |
|---|---:|---:|---:|---:|---:|---:|
| PERIOD_A | 1.10 | 127 | 105 | 22 | 127 | 82.68% |
| PERIOD_A | 1.20 | 119 | 96 | 23 | 119 | 80.67% |
| PERIOD_B | 1.10 | 317 | 273 | 44 | 317 | 86.12% |
| PERIOD_B | 1.20 | 293 | 254 | 39 | 293 | 86.69% |
| PERIOD_C | 1.10 | 291 | 249 | 42 | 291 | 85.57% |
| PERIOD_C | 1.20 | 272 | 233 | 39 | 272 | 85.66% |
| PERIOD_D | 1.10 | 723 | 632 | 91 | 723 | 87.41% |
| PERIOD_D | 1.20 | 643 | 567 | 76 | 643 | 88.18% |

1.10 event HHR deltas versus 1.20:

- PERIOD_A: `+2.00 pp`
- PERIOD_B: `-0.57 pp`
- PERIOD_C: `-0.09 pp`
- PERIOD_D: `-0.77 pp`

## Event Concentration

| Threshold | Events | 2025 Share | Largest-Year Share | Top-1 Symbol | Top-2 | Top-5 | Top-10 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.10 | 1458 | 49.59% | 2025 / 49.59% | 3.02% | 5.90% | 13.65% | 24.35% |
| 1.20 | 1327 | 48.46% | 2025 / 48.46% | 3.09% | 6.10% | 13.94% | 24.27% |

Compared with Phase 7 daily concentration, event-level symbol concentration is slightly lower, but 2025 time concentration remains high.

## Event Episode Audit

Deterministic audit symbols were selected from 1.10 event counts, not performance:

- many-event symbol: highest event count, tie by symbol
- few-event symbol: lowest non-zero event count, tie by symbol
- zero-event symbol: zero event count, tie by symbol

Audit results:

- `2406.TW`: `44` qualified segments from `1943` eligible observation dates. Example: `2019-07-31` to `2019-08-01` is one continuous qualified segment of 2 days, producing one event.
- `1303.TW`: `1` qualified segment from `1943` eligible observation dates. The only qualified segment is `2025-11-28` for 1 day.
- `1101.TW`: `0` qualified segments from `1943` eligible observation dates. The full sequence remains not qualified.

This verifies that continuous qualified days create only the first event and do not duplicate events.

## Existing 20-Bar Reduced Benchmark

The existing Phase 7 20-bar reduced view is retained and not replaced:

| Threshold | Reduced n | HHR |
|---:|---:|---:|
| 1.10 | 800 | 87.50% |
| 1.20 | 771 | 87.68% |

There are now three distinct views:

- Daily
- 20-bar reduced
- First-qualification event

Event identities are not required to nest across thresholds because threshold state transitions can occur on different dates.

## Combined Interpretation

Time robustness for `1.10`: `MIXED`.

Reason: 1.10 preserves sample expansion in all fixed periods and in the 2018-2024 exclusion-of-2025 view, but PERIOD_D remains large and lower than 1.20 by `-1.11 pp` in daily HHR.

Event robustness for `1.10`: `SUPPORTED`.

Reason: first-qualification events reduce repeated daily observations and keep 1.10 approximately comparable to 1.20: `+9.87%` events with event HHR only `-0.31 pp` below 1.20. Event sub-period deltas are closer than daily deltas, but 2025 event share remains high at `49.59%`.

Overall evidence relative to the prior Phase 7 Decision Review: `EVIDENCE_STRENGTHENED`.

The result is not an implementation approval. Formal V1 remains `volume_ratio_20 >= 1.20`.

## Bias And Scope Limitations

The 218-stock pool comes from 2026 current ETF constituents, not 2018 to 2025 point-in-time constituents. Results retain survivorship bias, constituent look-back bias, current ETF constituent universe bias, time concentration, and daily/event overlap limitations.

No future probability, strategy win rate, rank, score, recommendation, p-value, or confidence interval is introduced.

## Gate

Batch 2 final gate: `READY_FOR_V1_1_DECISION_REVIEW`.

Do not start V1.1 implementation from this document alone.
