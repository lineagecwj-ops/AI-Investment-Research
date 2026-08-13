# Research Snapshot Candidate Validation Phase 5B

## 1. Candidate A Source

Candidate A is the Composite Canonical Baseline proposed as the first Research
Snapshot Candidate.

Status in this phase:

```text
VALIDATED_CANDIDATE
not RELEASED
```

Candidate A source components:

```text
Component 1:
data/backups/stocks_before_adjusted_close_recovery_20260810T054845Z.db

Component 2:
data/backups/stocks_before_phase_6b_bulk_20260809T150444Z.db
```

Candidate A is a logical reconstruction:

```text
base backup
  + Phase 6B recovery semantics
  + five-symbol adjusted_close recovery
  + validation checks
```

It must not be treated as a single backup file.

## 2. Source Checksum Validation

All source checks were read-only.

| Source | SHA-256 | Rows | Symbols | Duplicates | Integrity | Price coverage |
|---|---|---:|---:|---:|---|---|
| Base backup | `f70943ecbf132f0d1bd192e9d2811b31d3976b6c35bb8764cbabfe2124514470` | `473481` | `222` | `0` | `ok` | `1980-12-12` to `2026-08-07` |
| Recovery source | `1626dbd604927f2f00b1c7e5b6e1de621c7bf0008c05012c5654b77d0302c0be` | `91780` | `28` | `0` | `ok` | `1980-12-12` to `2026-08-07` |
| Current live DB | `69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7` | `1185308` | `222` | `0` | `ok` | `1980-12-12` to `2026-08-10` |

Source checksum validation result:

```text
PASS
```

## 3. Reconstruction Validation

Candidate A logical key space:

```text
keys = 473481
symbols = 222
duplicates = 0
```

The recovery source is used for the five-symbol adjusted-close recovery
semantics only. It does not redefine the entire candidate.

Five-symbol row counts:

| Symbol | Base rows | Recovery rows | Current rows |
|---|---:|---:|---:|
| `0050.TW` | `4305` | `4305` | `4306` |
| `2330.TW` | `6613` | `6613` | `6613` |
| `2337.TW` | `6613` | `6613` | `6613` |
| `2404.TW` | `6613` | `6613` | `6613` |
| `2454.TW` | `6209` | `6209` | `6209` |

Reconstruction validation result:

```text
PASS
```

## 4. Adjusted-Close Validation

Base vs recovery differences for the five-symbol recovery scope:

| Symbol | Overlap rows | `adjusted_close` differences | Other research-field differences |
|---|---:|---:|---:|
| `0050.TW` | `4305` | `2922` | `0` |
| `2330.TW` | `6613` | `5219` | `0` |
| `2337.TW` | `6613` | `3688` | `0` |
| `2404.TW` | `6613` | `4302` | `0` |
| `2454.TW` | `6209` | `4339` | `0` |

Base vs recovery total overlap:

```text
overlap rows = 91780
adjusted_close differences = 20470
other research-field differences = 0
```

Recovery-source symbols outside the five-symbol scope:

```text
other adjusted_close differences = 0
other non-adjusted research-field differences = 0
```

Current live DB comparison:

```text
base keys = 473481
current keys = 1185308
common keys = 473481
current-only keys = 711827
base-only keys = 0
logical Candidate A existing-key adjusted_close differences vs current = 197642
logical Candidate A existing-key non-adjusted research-field differences vs current = 0
```

Adjusted-close validation result:

```text
PASS for Candidate A recovery semantics
PASS that current live DB must not be auto-promoted
```

Release caution:

```text
provider vintage still needs formal release metadata
```

## 5. Price Basis

Candidate A price basis status:

```text
INFERRED_FROM_EXISTING_PIPELINE
```

Required release metadata:

```text
price_basis_version
analysis_close_policy
adjusted_close semantics
```

Known analysis-close policy from the current research pipeline:

```text
analysis_close = adjusted_close if available else close
```

This is sufficient for candidate validation, but not sufficient for release
without formal metadata.

## 6. Provider Vintage

Provider vintage status:

```text
MISSING_FOR_RELEASE
```

Candidate A can remain a validated candidate, but release still requires:

```text
provider_name
provider_data_vintage
loader_version
ingestion_process_version
reconstruction limitation statement
```

This is a release gap, not a candidate-validation failure.

## 7. Dataset Scope

Observed source tables:

```text
historical_prices
historical_financials
historical_price_fetch_state
research_universe_symbols
research_universes
stocks
```

Candidate A dataset-scope recommendation:

| Dataset | Candidate scope status |
|---|---|
| `historical_prices` | included |
| `research_universe_metadata` | included through `research_universes` and `research_universe_symbols` |
| `listing_dates` | included as related research input only if linked by artifact manifest |
| `historical_financials` | present in source DB, but explicitly excluded from base price-snapshot semantics unless release manifest includes it |
| `features` | excluded |
| `targets` | excluded |
| `outcomes` | excluded unless generated as derived artifacts |

Dataset scope validation result:

```text
PASS_WITH_RELEASE_SCOPE_GAPS
```

## 8. Research Window

Candidate A price coverage:

```text
price_data_start = 1980-12-12
price_data_end = 2026-08-07
```

Candidate A research observation window readiness:

```text
research_window_start = 2018-01-01
research_window_end = 2025-12-31
rows in window = 415250
symbols in window = 222
```

The price coverage and research observation window must remain separate. Bars
after `2025-12-31` may support forward outcome evaluation, but they do not
automatically become training or research observations.

Research window validation result:

```text
PASS
```

## 9. Phase Readiness

### Phase 7

Candidate A is ready for Phase 7 reproduction validation.

Future comparison fields:

```text
counts
HIT
MISS
HHR
artifact checksum
semantic checksum
```

No Phase 7 rerun was executed in this phase.

### Phase 3

Candidate A is ready for Candidate Display Research reproduction validation.

Future comparison fields:

```text
classification counts
formal identities
priority groups
semantic checksum
```

No Phase 3 rerun was executed in this phase.

### Phase 4

Candidate A is ready for Experimental Candidate View evidence validation.

Future comparison fields:

```text
Formal
Priority A
Priority B
Watch
artifact consistency
```

No Phase 4 rerun was executed in this phase.

## 10. Backtest, Replay, Walk-Forward, and OOS Readiness

Candidate A can serve as a future read-only input for:

```text
Backtest
Replay
Walk-Forward
OOS
```

Prerequisites:

- fixed `research_snapshot_id`;
- fixed checksum lineage;
- manifest-based dataset scope;
- no silent LiveDataStore dependency;
- OOS window and tuning rules documented before use.

Readiness result:

```text
READY_FOR_FUTURE_REPRODUCTION_VALIDATION
```

No backtest, replay, walk-forward, or OOS run was executed in this phase.

## 11. AI Readiness

Candidate A is suitable as a future reproducibility anchor, but not yet as a
released Long-Term Growth AI training base.

AI release prerequisites:

```text
feature dataset lineage
target dataset lineage
training dataset checksum
model lineage
OOS split definition
provider vintage metadata
price basis metadata
```

AI readiness result:

```text
NOT_READY_FOR_AI_TRAINING
READY_AS_VALIDATED_RESEARCH_CANDIDATE_INPUT
```

No AI model was trained in this phase.

## 12. Semantic Checksum Design

Candidate A semantic checksum should include normalized research-relevant
contents:

```text
historical_prices key set
symbol
trading_date
open
high
low
close
adjusted_close
volume
dividends
stock_splits
currency
universe_id
universe_version
price_data_start
price_data_end
research_window_start
research_window_end
analysis_close_policy
reconstruction_method
```

The semantic checksum should exclude storage-layout-only differences such as
SQLite page layout. A formal semantic checksum artifact was not created in this
phase.

## 13. Release Gaps

Candidate A gaps before `RELEASED`:

- formal manifest generation;
- formal semantic checksum artifact;
- provider vintage metadata;
- price basis metadata;
- reconstruction limitation statement;
- Phase 7 reproduction artifact;
- Phase 3 reproduction artifact;
- Phase 4 evidence reproduction artifact;
- backtest/replay/walk-forward/OOS lineage acceptance;
- release approval process.

These gaps prevent release now, but they do not invalidate Candidate A as a
validated candidate.

## 14. Validation Result

Candidate A validation result:

```text
PASS_WITH_GAPS
```

Interpretation:

- Candidate A source checks match expected values.
- Candidate A logical reconstruction preserves `473481` keys and `222` symbols.
- Five-symbol adjusted-close recovery semantics are validated in read-only
  comparison.
- Other research fields are unchanged in the recovery comparison.
- Current live DB has `711827` additional keys and `197642` existing-key
  adjusted-close differences versus logical Candidate A, so it is not
  automatically promoted.
- Release still requires manifest, provider vintage, price basis, semantic
  checksum artifact, reproduction artifacts, and approval.

## 15. Stop Gate

Phase 5B ends at review.

Do not proceed to:

- release Candidate A;
- create a Research DB;
- create a Released Snapshot;
- migrate or copy data;
- write to SQLite;
- run scanner workflows;
- start Long-Term Growth.
