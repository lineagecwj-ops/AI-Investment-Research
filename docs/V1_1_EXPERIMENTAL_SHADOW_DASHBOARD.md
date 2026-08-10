# V1.1 Experimental Shadow Dashboard

## Purpose

The Phase 2 dashboard adds a read-only side-by-side comparison for formal V1
and V1.1 Experimental.

It does not replace Production V1, change scanner defaults, add alerts,
create recommendations, or modify any database content.

## Side-by-Side Semantics

The dashboard presents:

- Production V1: `technical_example_v1`
- V1.1 Experimental: `technical_example_v1_1_experimental`

Production V1 remains the default and authoritative production-facing
definition.

V1.1 remains experimental / shadow only.

## Definition Difference

The only technical-condition difference is:

```text
Production V1: volume_ratio_20 >= 1.20
V1.1 Experimental: volume_ratio_20 >= 1.10
```

The other four conditions are unchanged:

- Price > SMA20
- SMA20 > SMA60
- RSI condition
- Distance to prior high condition

## Shared And Incremental Observations

Shared observations qualify under both V1 and V1.1.

V1.1 incremental observations qualify only under V1.1 because:

```text
other four V1 conditions pass
and 1.10 <= volume_ratio_20 < 1.20
```

The dashboard table for V1.1-only observations is read-only and contains only
factual fields such as symbol, trading date, volume ratio, outcome status, and
signal definition id.

## Research Evidence

The dashboard displays accepted Phase 7 evidence:

| Evidence | V1 n | V1 HHR | V1.1 n | V1.1 HHR |
|---|---:|---:|---:|---:|
| Daily | 1821 | 86.05% | 2072 | 85.33% |
| 20-bar reduced | 771 | 87.68% | 800 | 87.50% |
| First-event | 1327 | 86.66% | 1458 | 86.35% |

The wording remains factual: V1.1 increases observations / events, but current
evidence does not show Historical Hit Rate above formal V1.

## Limitations

The dashboard keeps these limitations visible:

- survivorship bias
- constituent look-back bias
- current constituent universe limitation
- daily observation overlap
- 2025 time concentration
- V1.1 Experimental is not a production recommendation

## No Production Switch

The dashboard does not provide:

- Use V1.1
- Set V1.1 as default
- Apply to scanner
- Enable V1.1 alerts
- threshold sliders
- threshold tuning controls

## No DB Change

The dashboard uses read-only local historical price inputs and existing
services. It does not add tables, alter schema, write `stocks.db`, run Yahoo
fetches, or backfill prices.
