# OOS Validation Dashboard

## Purpose

Sprint 08 Batch B adds a deterministic Streamlit visualization layer for the existing Out-of-Sample Validation foundation.

The dashboard compares `Development`, `Validation`, and `Holdout` results side by side so the user can inspect descriptive validation facts. It does not issue an automatic verdict, create a hidden score, or decide whether a research specification is good or bad.

This dashboard is the final validation visualization layer before the planned V1.0 release review.

## Development / Validation / Holdout

The dashboard uses the same three period roles as `out_of_sample_validation_service.py`:

- `Development`
- `Validation`
- `Holdout / Out-of-Sample`

Period boundaries are inclusive. The service rejects overlaps and requires Development before Validation, and Validation before Holdout.

Holdout is labeled separately because it does not participate in research specification creation or adjustment.

## Frozen Research Specification

Each validation run freezes the materially relevant research settings:

- Signal ID
- Outcome ID
- Replay Frequency
- Overlap Policy
- Cooldown Bars
- Historical Start
- Preferred Resolved Samples

The dashboard shows these settings in a `Frozen Research Specification` expander so the user can confirm that all three period roles used the same fixed rules.

## Research Fingerprint

The service generates a deterministic `Research Specification Fingerprint`.

The dashboard displays:

- `Research Specification Fingerprint`
- `Same Specification Across All Periods`

This is separate from the UI request fingerprint. The UI request fingerprint is only used to detect whether the currently displayed result came from a previous set of dashboard inputs.

## Historical Hit Rate

Historical Hit Rate remains:

```text
HIT / (HIT + MISS)
```

It is a descriptive historical event ratio. It is not future probability, prediction accuracy, confidence, likelihood, or investment advice.

## Resolved n

Resolved n is always displayed with Historical Hit Rate.

Resolved n is:

```text
HIT + MISS
```

If `Resolved n == 0`, Historical Hit Rate is displayed as `N/A`, not `0%`.

## Candidate Period Share

Candidate Period Share is:

```text
periods with at least one candidate / total replay periods
```

The dashboard displays the numerator, denominator, and percentage together, for example:

```text
5 / 60 = 8.33%
```

Candidate Period Share describes signal occurrence frequency. It is not signal quality and not future probability.

## Outcome Counts

The dashboard displays outcome counts side by side:

- `HIT`
- `MISS`
- `INCOMPLETE`
- `NOT_EVALUABLE`

These are `OutcomeDefinition` event results, not actual trading profit or loss.

## Candidate Stability

The dashboard reuses period-local Replay Analytics.

For each period, it can show:

- Symbol
- Candidate Occurrences
- Candidate Period Share
- First Appearance
- Last Appearance
- Longest Consecutive Periods
- Post-Replay HIT / MISS / INCOMPLETE / NOT_EVALUABLE
- Best / Median / Worst Research Priority

No cross-period stability score is created.

## Cross-Period Comparison

The comparison table shows:

- Replay Periods
- Periods With Candidates
- Candidate Period Share
- Unique Candidates
- Candidate Occurrences
- Resolved n
- Historical Hit Rate
- HIT / MISS / INCOMPLETE / NOT_EVALUABLE

Development, Validation, and Holdout are shown side by side.

## Percentage-Point Differences

For percentage metrics, raw differences are shown as percentage points.

Example:

```text
8.33% -> 42.11% = +33.78 percentage points
```

The MVP does not display relative change.

## Sample Size Context

When a period has fewer resolved samples than the configured preferred minimum, the dashboard shows the neutral warning:

```text
此期間已解析歷史樣本低於偏好門檻。
```

It does not call the result unreliable, invalid, or low confidence.

## Holdout / OOS Semantics

Holdout is presented as out-of-sample descriptive context.

Holdout results must not automatically modify:

- Signal definition
- Outcome definition
- Replay frequency
- Overlap policy
- Cooldown
- Minimum resolved samples
- Research ranking rules

Any future rule change belongs in a separate explicit research workflow.

## No Automatic Verdict

The dashboard must not display:

- Validation Passed
- Validation Failed
- Robust
- Not Robust
- Reliable
- Unreliable
- Production Ready

Only deterministic data-quality validation may produce direct errors, such as invalid period ordering.

## No Probability

Out-of-Sample Historical Hit Rate is not future probability, success probability, win rate, or prediction accuracy.

Candidate Period Share is not signal probability or market probability.

## No Strategy P&L

`HIT` and `MISS` describe the configured outcome event. They are not trade entries, exits, realized returns, or strategy profit and loss.

The dashboard does not model transaction costs, position sizing, stop loss, portfolio allocation, or expected return.

## No Optimization

The dashboard has no optimization controls.

It does not offer:

- Optimize
- Tune Signal
- Find Best Threshold
- Best Parameters
- Improve Hit Rate
- Apply Holdout Findings

## Session State

The dashboard stores only session-scoped OOS result state:

- `oos_validation_result`
- `oos_validation_fingerprint`
- `oos_validation_last_error`
- `oos_validation_source_context`

Source context preserves the source type, universe metadata when applicable, symbol count, and symbols snapshot.

## Rerun Safety

Changing an expander, table, selector, or chart does not rerun OOS validation.

The validation service runs only when the user presses:

```text
執行樣本外驗證
```

If the current input settings differ from the stored result fingerprint, the dashboard shows:

```text
目前結果來自上一組驗證設定。
```

It does not automatically rerun.

## V1.0 Role

Batch B gives the project an auditable validation visualization layer before the planned V1.0 release review.

It does not itself declare V1.0 production readiness.
