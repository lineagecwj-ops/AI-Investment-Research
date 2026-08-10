# V1.1 Experimental Shadow Definition

## Purpose

V1.1 exists as an isolated shadow research definition for comparing one narrow
technical-condition change against the formal V1 baseline.

It is not a production replacement, scanner default change, dashboard
integration, recommendation feature, tuned threshold, or preferred model.

## Signal Definitions

Formal production V1 remains:

```text
signal_definition_id = technical_example_v1
volume_ratio_20 >= 1.20
```

Experimental V1.1 is:

```text
signal_definition_id = technical_example_v1_1_experimental
label = V1.1 實驗版
volume_ratio_20 >= 1.10
```

The V1.1 definition is explicitly marked `EXPERIMENTAL`. It must not be
presented as a new formal V1, upgraded V1, better version, or recommended
version.

## Exact Difference

V1.1 changes exactly one condition:

```text
volume_ratio_20 >= 1.20
```

to:

```text
volume_ratio_20 >= 1.10
```

The other four technical conditions remain identical:

```text
analysis_close > sma_20
sma_20 > sma_60
rsi_14 between 50.0 and 70.0
distance_to_prior_60d_high >= -0.05
```

Required features remain identical.

## Set Semantics

Because V1.1 only lowers the volume threshold while keeping the other four
conditions unchanged:

```text
V1 qualified observations are a subset of V1.1 qualified observations.
```

Shared observations are observations that qualify under both V1 and V1.1.
They reuse the same technical snapshot and the same attached historical
outcome.

Incremental V1.1 observations are observations where:

```text
other four V1 conditions pass
and 1.10 <= volume_ratio_20 < 1.20
```

Shared V1 observations are not counted as incremental V1.1 observations.

## Production Boundary

Phase 1 does not change:

- scanner default
- dashboard default
- existing backtest default
- Historical Replay default
- Walk-Forward Replay default
- OOS default
- `app.py`
- database schema
- database content
- technical formulas
- outcome semantics
- scanner algorithm
- AI/OpenAI logic

Formal V1 remains authoritative for production-facing flows.

## No Recommendation Semantics

V1.1 does not create:

- buy recommendation
- sell recommendation
- best threshold
- preferred model
- rank
- score
- probability
- confidence

It is only a second research definition for controlled side-by-side
observation comparison.

## Rollback

The Phase 1 implementation is intentionally isolated:

- one experimental `SignalDefinition`
- one pure comparison service
- focused regression tests
- this documentation

Rollback/removal can delete the experimental definition, comparison service,
tests, and documentation without database migration or data rollback.
