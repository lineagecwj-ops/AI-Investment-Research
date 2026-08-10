# V1.1 Experimental Shadow Scanner

## Purpose

The Phase 1 shadow scanner adds an in-memory comparison between Production V1
and V1.1 Experimental for the current scanner snapshot.

Production V1 remains authoritative. The official scanner result, ranking,
candidate count, alerts, backtest, Replay, Walk-Forward, OOS, and Dashboard
production defaults remain V1-only.

## Architecture

The production scanner already stores scan-time current signal details in
`SwingScannerResult.current_signal_details`. Each item includes the latest
`TechnicalIndicatorSnapshot` used by the Production V1 scanner.

The shadow scanner service consumes that existing result:

```text
Cached/local price data
        -> technical indicators built once by SwingScannerService
        -> Production V1 scanner result
        -> current_signal_details
        -> V1/V1.1 shadow comparison
```

The shadow path does not fetch prices, build technical indicators, run
backtests, write the database, or mutate Streamlit session state.

## Definitions

Production V1:

```text
technical_example_v1
volume_ratio_20 >= 1.20
```

V1.1 Experimental:

```text
technical_example_v1_1_experimental
volume_ratio_20 >= 1.10
```

Both definitions are imported from the canonical signal definition module. The
shadow scanner does not introduce a third threshold definition.

## Same Technical Snapshot

V1 and V1.1 are evaluated against the same `TechnicalIndicatorSnapshot`. The
shadow service calls the canonical `evaluate_signal_conditions()` evaluator for
each definition and does not recalculate:

- SMA
- RSI
- volume ratio
- distance to prior high

## Classification Semantics

`SHARED_PASS`
: Production V1 passes and V1.1 passes.

`V1_1_ONLY`
: Production V1 fails and V1.1 passes. This must mean the other four
conditions pass and:

```text
1.10 <= volume_ratio_20 < 1.20
```

`NEITHER`
: Production V1 fails and V1.1 fails.

`INVARIANT_VIOLATION`
: Production V1 passes but V1.1 fails. This should not occur because V1.1 is
less strict only on volume. The batch summary treats this as a blocking semantic
error.

## Set Invariant

For the same scanner batch:

```text
V1 hits subset V1.1 hits
```

This is enforced at symbol identity level, not by count alone.

## Production Safety

The shadow scanner does not affect:

- production scanner return type
- production hit identities
- production ordering
- ranking policy
- scanner default definition
- alerts
- recommendations
- Dashboard production default

No fields such as winner, rank, score, probability, confidence,
recommendation, or buy/sell action are added to the shadow result model.

## No Persistence

Phase 1 keeps all shadow scanner results in memory. It does not add tables,
migrations, daily persistence, future outcome tracking, or any V1.1-only
performance storage.

## Rollback / Removal

The shadow scanner is isolated in:

```text
src/v1_1_shadow_scanner_service.py
tests/test_v1_1_shadow_scanner_service.py
docs/V1_1_EXPERIMENTAL_SHADOW_SCANNER.md
```

Removing those files restores the repository to the pre-shadow-scanner
production scanner behavior because no production scanner contract is changed.
