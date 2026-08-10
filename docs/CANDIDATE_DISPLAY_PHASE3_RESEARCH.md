# Candidate Display Phase 3 Research

Purpose: define a research-only candidate display classification from the frozen Historical Condition Coverage Phase 1 and Phase 2 robustness outputs.

This document does not change Production V1, V1.1, the scanner, Dashboard UI, technical formulas, historical outcomes, backtest, Historical Replay, Walk-Forward, OOS, database schema/content, or AI/OpenAI logic.

## Locked Evidence

- Production definition: `technical_example_v1`
- Phase 1 checksum: `b58f00ebf9cac16c1ce5bed3720b3eb7036ff456bb2d28862ffccd66c8e02632`
- Phase 2 semantic checksum: `71c69eda6b743b195a531c67c9517b84b8a7b0fb19aa5263e97fec8ab891c704`
- Evidence classification for the display design: `DISPLAY_DESIGN_SUPPORTED`

## Classification Design

`FORMAL_V1` is the only official Production V1 class. It requires coverage `5/5`, sets `formal_v1_qualified = true`, and its identity set must exactly equal Production Scanner V1 hits.

`RESEARCH_PRIORITY_A` is a research display group for coverage exactly `4/5` where the only missing condition is `rsi_14`. Evidence metadata may cite Phase 1 daily group HHR `97.13%` and Phase 2 robustness values: reduced `98.03%`, first-event `97.55%`, full-window `97.04%`, partial-window `97.78%`.

`RESEARCH_PRIORITY_B` is a research display group for coverage exactly `4/5` where the only missing condition is `volume_ratio_20`. Evidence metadata may cite daily group HHR `75.51%`, reduced `78.02%`, and first-event `76.92%`.

`RESEARCH_WATCH` is a conservative research watch group for coverage exactly `4/5` where the only missing condition is `distance_to_prior_60d_high`. Evidence metadata may cite daily group HHR `62.32%`, reduced `58.09%`, and first-event `61.80%`. It must not be described as having the same historical strength as Priority A or Priority B.

`EXPLORATORY` covers other `4/5` signatures, including missing `sma_20_vs_sma_60` or `analysis_close_vs_sma_20`, plus all `3/5` cases. This phase does not promote any `3/5` pair even if a Phase 1 pair had high historical group HHR, because Phase 2 did not select `3/5` robustness groups.

`BELOW_DISPLAY_SCOPE` covers coverage `0/5`, `1/5`, and `2/5`. These rows are kept for count reconciliation and are not part of the Phase 3 candidate projection groups.

## V1.1 Badge Semantics

For `RESEARCH_PRIORITY_B` only, a factual `V1_1_EXPERIMENTAL_MATCH` badge may be true when the canonical V1.1 experimental evaluator passes on the same scan-time snapshot. The classification remains `RESEARCH_PRIORITY_B`; it is not promoted to `FORMAL_V1`.

If `volume_ratio_20 < 1.10`, the factual label is below the V1.1 volume interval. This is only information, not a low/high score.

## Why This Is Not Ranking

The fixed display section order is:

1. `FORMAL_V1`
2. `RESEARCH_PRIORITY_A`
3. `RESEARCH_PRIORITY_B`
4. `RESEARCH_WATCH`
5. `EXPLORATORY`

This is display grouping order, not stock ranking. Within each group, symbols are listed numeric ascending or by an existing stable order. The Phase 3 result model contains no score, rank, probability, confidence, recommendation, expected return, buy, or sell field.

Historical group HHR is explanatory metadata only. It must be labeled as historical group HHR and must not be shown as individual stock probability, stock win rate, or predicted HHR.

## Live Local Projection

Method:

- Read local `data/stocks.db` through SQLite `mode=ro`.
- Use the frozen materialized TWSE common-stock universe of `218` symbols.
- Reuse scanner current signal details through the existing condition coverage service.
- No Yahoo, yfinance, web API, ETF refetch, listing-date refetch, DB write, Dashboard integration, or scanner change.

Count reconciliation:

| Group | Count |
| --- | ---: |
| Evaluated symbols | 218 |
| `FORMAL_V1` | 13 |
| `RESEARCH_PRIORITY_A` | 8 |
| `RESEARCH_PRIORITY_B` | 12 |
| `RESEARCH_WATCH` | 12 |
| Other `4/5` exploratory | 5 |
| `3/5` exploratory | 49 |
| Below display scope | 119 |
| Reconciled | true |

`FORMAL_V1` symbols:

`1714.TW`, `2301.TW`, `2308.TW`, `2395.TW`, `2415.TW`, `2882.TW`, `2891.TW`, `2892.TW`, `3036.TW`, `3167.TW`, `4904.TW`, `6213.TW`, `6789.TW`

`RESEARCH_PRIORITY_A` symbols:

`2345.TW`, `2347.TW`, `2383.TW`, `2880.TW`, `2883.TW`, `2890.TW`, `7750.TW`, `7769.TW`

`RESEARCH_PRIORITY_B` symbols:

`2002.TW`, `2243.TW`, `2313.TW`, `2360.TW`, `2368.TW`, `2449.TW`, `2884.TW`, `3023.TW`, `3189.TW`, `3533.TW`, `3653.TW`, `6442.TW`

Priority B V1.1 factual badge:

`2368.TW`, `2884.TW`

`RESEARCH_WATCH` symbols:

`1342.TW`, `1402.TW`, `1708.TW`, `2409.TW`, `2455.TW`, `2851.TW`, `2855.TW`, `3550.TW`, `5871.TW`, `8033.TW`, `8046.TW`, `8996.TW`

Other `4/5` exploratory symbols:

`2412.TW`, `2542.TW`, `2838.TW`, `2886.TW`, `5880.TW`

## Limitations

Priority A/B/Watch are post-hoc display categories selected from historical research. They are not prospectively validated ranking, prediction, recommendation, buy/sell guidance, formal V1 upgrade, or V1.1 promotion.

The frozen universe is derived from 2026 current ETF constituents, not a 2018 to 2025 historical point-in-time universe. Survivorship bias and constituent look-back bias remain.

Phase 3 can only answer whether this candidate display grouping is suitable for a next-stage UI experiment. It cannot answer which stock should be bought, which stock is most likely to rise, or whether Production V1 should be formally upgraded.

## Artifacts

- Deterministic JSON artifact: `docs/research_outputs/candidate_display_phase3_research.json`
- Phase 3 semantic checksum: `79f641199e31166b6c2e13782766fa0b404058b06bb99fdd4a91e7c37be41736`

Database safety audit before and after live projection:

- Rows: `473481`
- Symbols: `222`
- Duplicates: `0`
- Integrity: `ok`
- SHA-256: `aa90f60d00e96c31630c9edede7af7a4b0ceedbb15a5fbbaf30042174920ae06`
