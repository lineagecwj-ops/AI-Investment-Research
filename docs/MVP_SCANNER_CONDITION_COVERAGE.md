# MVP Scanner Condition Coverage

This Phase 1 view turns the current scanner condition diagnostics into a factual display for the latest scanner run.

Production V1 is unchanged:

- Signal definition: `technical_example_v1`
- Formal volume threshold: `volume_ratio_20 >= 1.20`
- Formal scanner pass: all 5 of 5 V1 conditions pass

Condition Coverage is not a score. The labels `5/5`, `4/5`, `3/5`, `2/5`, `1/5`, and `0/5` are plain counts of canonical V1 conditions that matched during the scanner run. They are not converted into percentages, weights, probabilities, confidence, or recommendation language.

Display classifications:

- `5/5`: formal V1 match
- `4/5`: near match, display-only
- `3/5`: exploratory observation, display-only
- `0/5` to `2/5`: below display threshold, hidden by default

The coverage service reuses `SwingScannerResult.current_signal_details` and the scan-time `SignalMatch.evaluated_conditions`. It does not rebuild technical indicators, change scanner qualification semantics, change technical formulas, run backtests, run replay, run OOS validation, write SQLite, or call AI/OpenAI logic.

Missing-condition signatures are deterministic factual labels built from canonical condition identifiers, for example:

- `MISSING_volume_ratio_20`
- `MISSING_volume_ratio_20+rsi_14`
- `NONE`

These signatures are grouping labels only. They do not imply that missing one condition is better, worse, stronger, weaker, or more predictive than missing another.

The V1.1 badge is factual and experimental. A `4/5` symbol can show `V1.1 實驗版符合` only when the only missing Production V1 condition is volume and the existing V1.1 experimental definition evaluates to `MATCH` on the same scan-time snapshot. The badge does not change Production V1 coverage, so the symbol remains `4/5` under Production V1.

Future research can compare historical outcomes for `5/5`, `4/5`, and `3/5`, and can study historical differences among `4/5` missing-condition groups. That outcome research is not part of this Phase 1 view.
