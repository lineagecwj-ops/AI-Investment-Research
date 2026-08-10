# Historical Condition Coverage Phase 2 Robustness

Research-only robustness review for exactly three Phase 1 `4/5` missing-condition groups: `rsi_14`, `volume_ratio_20`, and `distance_to_prior_60d_high`.

## Scope

- Phase 1 input checksum: `b58f00ebf9cac16c1ce5bed3720b3eb7036ff456bb2d28862ffccd66c8e02632`
- Window: `2018-01-01` through `2025-12-31`
- Signal: `technical_example_v1`
- Outcome: `raw_high_breakout_60d_within_20d_v1`
- Universe: `frozen_twse_research_universe_2026_08_09` / `218` symbols

These groups were selected after Phase 1 observations. This is descriptive post-hoc research, not a confirmatory trial.

## Group Results

| Group | Daily | Reduced | First Event | FULL | PARTIAL | 2025 | Top1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rsi_14 | 2853 / 2771 / 82 / 97.13% | 1017 / 997 / 20 / 98.03% | 1674 / 1633 / 41 / 97.55% | 2538 / 2463 / 75 / 97.04% | 315 / 308 / 7 / 97.78% | 42.76% | 2.91% |
| volume_ratio_20 | 2691 / 2032 / 659 / 75.51% | 605 / 472 / 133 / 78.02% | 1278 / 983 / 295 / 76.92% | 2461 / 1858 / 603 / 75.50% | 230 / 174 / 56 / 75.65% | 57.67% | 8.81% |
| distance_to_prior_60d_high | 28042 / 17477 / 10565 / 62.32% | 7483 / 4347 / 3136 / 58.09% | 17766 / 10980 / 6786 / 61.80% | 26386 / 16397 / 9989 / 62.14% | 1656 / 1080 / 576 / 65.22% | 9.37% | 0.76% |

## RSI Audit

- Canonical condition: `rsi_14 BETWEEN 50.0 AND 70.0 inclusive`
- Fail semantics: missing RSI means finite rsi_14 is below 50.0 or above 70.0 under canonical V1 evaluation.
- Failed value distribution: count `2853`, min `49.26916916448447`, p10 `71.34188736636325`, p25 `73.34622566107319`, median `76.8674069190991`, p75 `81.46771021571712`, p90 `85.93365886633104`, max `96.11938687311498`
- Fail below: 2 / 1 / 1 / 50.00%
- Fail above: 2851 / 2770 / 81 / 97.16%

## Volume Audit

- `volume_lt_1_10` daily `2440 / 1831 / 609 / 75.04%`, reduced `574 / 446 / 128 / 77.70%`, first-event `1194 / 914 / 280 / 76.55%`
- `volume_1_10_to_lt_1_20` daily `251 / 201 / 50 / 80.08%`, reduced `180 / 146 / 34 / 81.11%`, first-event `241 / 195 / 46 / 80.91%`

## Distance Audit

- Canonical condition: `distance_to_prior_60d_high >= -0.05`
- Fail semantics: missing Distance means finite distance_to_prior_60d_high is below -0.05 under canonical V1 evaluation, i.e. farther below the prior 60-day high than allowed.
- Failed value distribution: count `28042`, min `-0.7171453552246094`, p10 `-0.3356303573964885`, p25 `-0.2631914702339099`, median `-0.1828900796395761`, p75 `-0.12185742119246687`, p90 `-0.08431219503032181`, max `-0.050000000000000044`

## Limitations

- No threshold tuning, grid search, ranking, score, probability, confidence, recommendation, alert, or scanner promotion was created.
- Production V1 remains unchanged and authoritative.
- Dashboard behavior was not changed.
- Phase 3 was not started.
- Frozen universe is derived from 2026 current ETF constituents, not 2018-2025 point-in-time constituents; survivorship and constituent look-back bias remain.

Semantic checksum: `71c69eda6b743b195a531c67c9517b84b8a7b0fb19aa5263e97fec8ab891c704`
