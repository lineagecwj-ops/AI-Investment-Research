# Canonical Research Snapshot Selection Review Phase 4A

## 1. Background

This review evaluates candidate strategies for the first future Released
Research Snapshot. It is analysis and documentation only.

This phase does not:

- select and release a canonical snapshot;
- create a Research DB;
- create a Live DB;
- copy data;
- run migration;
- write to SQLite;
- fetch Yahoo or network data;
- execute scanner workflows;
- modify Dashboard, PDF Export, Production V1, V1.1, or Long-Term Growth code.

The current canonical decision remains open until a future release gate approves
one candidate with manifest, checksum, provider vintage, price basis, and
reproducibility evidence.

## 2. Candidate A: Composite Canonical Baseline

Definition:

```text
Candidate A = Composite canonical baseline
source = f70943 backup + Phase 6B recovery semantics + logical reconstruction
keys = 473481
symbols = 222
```

Known supporting context:

- existing Phase 7 / V1 expanded TWSE validation cites a canonical research DB
  with `473481` rows, `222` symbols, duplicates `0`, and integrity `ok`;
- this baseline is aligned with existing research semantics and Phase 7
  evidence;
- it is older and has more limited coverage than the current live DB.

Assessment:

```text
Suitable as first released Research Snapshot: CONDITIONAL
```

Conditions:

- create an explicit snapshot manifest;
- document reconstruction lineage;
- record provider vintage and price basis as far as recoverable;
- verify semantic checksum;
- confirm Phase 7 and Phase 3 reproducibility;
- label coverage limitations clearly.

Strengths:

- strongest existing reproducibility link;
- best compatibility with current research evidence;
- lower risk of silent adjusted-close drift;
- lower migration risk for first ResearchDataStore cutover.

Weaknesses:

- older coverage;
- may lack complete provider-vintage metadata;
- may be less suitable for future AI training without a corrected successor
  snapshot.

## 3. Candidate B: Current Live Database

Definition:

```text
Candidate B = Current live database
source = data/stocks.db
sha256 = 69694f98e8694da509b5dc0b6a99fe55b64dacbace8475f66aa92c29192f85c7
rows = 1185308
symbols = 222
```

Known concerns:

- row count increased compared with the composite baseline;
- `adjusted_close` rewrites are known research-relevant changes;
- current live DB is a mutable cache source;
- provider vintage and price basis are not yet formalized as released snapshot
  metadata.

Assessment:

```text
Suitable as first released Research Snapshot: NO, not directly
```

Candidate B could become a candidate only after:

- provider-vintage validation;
- price-basis validation;
- adjusted-close consistency audit;
- existing-key research-field diff audit;
- semantic checksum creation;
- Phase 7 rerun and comparison;
- Phase 3 / Phase 4 evidence rerun and comparison;
- backtest, replay, walk-forward, and OOS reproducibility checks;
- release manifest approval.

Strengths:

- widest current historical coverage;
- likely useful as a future live-derived candidate source;
- closer to current scanner cache state.

Weaknesses:

- not reproducible enough as-is;
- adjusted-close restatement risk is already known;
- direct acceptance would violate the no silent baseline mutation rule;
- AI training from this source would inherit unclear provider-vintage and target
  reproducibility risk.

## 4. Candidate C: New Corrected Research Snapshot

Definition:

```text
Candidate C = Future corrected Research Snapshot
source = selected input after release process
requires = manifest + provider vintage validation + price basis validation
           + research-window validation + semantic checksum
```

Assessment:

```text
Suitable as first released Research Snapshot: YES as target strategy, not yet executable in this phase
```

Strengths:

- best long-term architecture;
- can fully satisfy Phase 3A snapshot specification;
- handles adjusted-close vintage explicitly;
- strongest basis for AI feature/target/model lineage.

Weaknesses:

- requires future build/release process;
- requires canonical source decision;
- requires validation work before any migration or AI use;
- cannot be claimed as released until the acceptance gates pass.

## 5. Evaluation Matrix

| Criterion | Candidate A: Composite baseline | Candidate B: Current live DB | Candidate C: Corrected snapshot |
|---|---|---|---|
| Research reproducibility | Strong, pending manifest formalization. | Weak unless fully revalidated. | Strong after release gate. |
| Phase 7 compatibility | Strongest existing alignment. | Requires rerun and comparison. | Strong after rerun and release. |
| Phase 3 compatibility | Likely strongest with existing artifacts, pending verification. | Requires rerun due adjusted-close changes. | Strong after artifact regeneration. |
| Phase 4 compatibility | Good as conservative initial freeze. | Risky as direct release. | Best strategic fit. |
| Backtest reproducibility | Conditional; needs formal baseline artifact. | Requires full rerun. | Strong after release. |
| Replay reproducibility | Conditional; needs formal baseline artifact. | Requires full rerun. | Strong after release. |
| Walk-Forward reproducibility | Conditional; needs formal baseline artifact. | Requires full rerun. | Strong after release. |
| OOS reproducibility | Conditional; needs formal baseline artifact and split metadata. | Requires full rerun and OOS discipline. | Strong after release. |
| `adjusted_close` consistency | Better aligned with prior evidence, but metadata must be reconstructed. | Known risk due rewrites. | Explicitly validated. |
| Provider vintage clarity | Partial. | Insufficient. | Required by design. |
| Price basis clarity | Partial. | Insufficient. | Required by design. |
| Historical coverage | Lower. | Highest current coverage. | Depends on selected source and window. |
| Migration complexity | Lowest for first research freeze. | High due revalidation. | Medium/high but cleanest long term. |
| AI training suitability | Limited; may serve as initial evidence snapshot, not ideal AI base. | Not suitable until corrected and released. | Best after release. |
| Future maintenance risk | Medium. | High if accepted directly. | Lowest after tooling exists. |

## 6. Adjusted-Close Considerations

Research Snapshot selection must confirm:

```text
adjusted_close source
provider vintage
loader version
ingestion batch
price basis
semantic checksum
```

Current information is not sufficient to directly accept Candidate B as a
Released Research Snapshot. The known adjusted-close rewrites mean Candidate B
must be treated as mutable live data until it passes the full release gate.

Any accepted adjusted-close rewrite must produce a new candidate snapshot, not
overwrite or silently redefine an existing research baseline.

## 7. Phase Impacts

### Phase 7

Candidate A:

- likely best starting point;
- must attach manifest, checksum, and reconstruction lineage;
- should verify existing Phase 7 outputs remain reproducible.

Candidate B:

- requires Phase 7 rerun;
- must compare observation counts, hit/miss counts, HHR, and semantic checksum;
- cannot inherit Candidate A evidence.

Candidate C:

- requires full Phase 7 run after snapshot release;
- becomes preferred once provider vintage, price basis, and semantic checksum are
  formalized.

### Phase 3 / Phase 4 Research Evidence

Candidate A:

- likely preserves existing candidate display semantics better;
- needs artifact checksum verification.

Candidate B:

- requires candidate display and experimental candidate view reruns;
- Dashboard evidence must label it as a new research baseline, not a continuation
  of Candidate A.

Candidate C:

- cleanest future path;
- all candidate-display evidence should cite the released snapshot ID and
  artifact checksums.

## 8. AI Training Impact

Candidate A:

- useful as a conservative research-evidence baseline;
- weaker for Long-Term Growth AI if coverage or provider metadata are incomplete;
- feature and target reproducibility would require extra manifest reconstruction.

Candidate B:

- not suitable for AI training directly;
- unclear provider vintage and adjusted-close rewrites would undermine feature,
  target, and model lineage;
- must not be used before release validation.

Candidate C:

- best AI strategy;
- supports feature reproducibility, target reproducibility, training lineage,
  model lineage, and OOS traceability;
- requires released snapshot, feature artifact, target artifact, split metadata,
  and checksums before Long-Term Growth work starts.

## 9. Migration Impacts

Candidate A:

- easiest first migration freeze;
- safest for preserving existing research behavior;
- may need a later corrected successor snapshot for broader coverage and AI.

Candidate B:

- hardest to accept safely;
- risks turning live restatement into research baseline;
- only migration-safe after complete revalidation and release manifest approval.

Candidate C:

- most aligned with Phase 4 migration plan;
- requires more preparation but produces the cleanest long-term state;
- should be the strategic target even if Candidate A is used as the first
  conservative released snapshot.

## 10. Recommendation

Recommended:

```text
Option A first, then Option C
```

Reasoning:

1. Candidate A is the safest first Released Research Snapshot candidate because
   it aligns with existing Phase 7 and research evidence.
2. Candidate B should remain LiveDataStore material until adjusted-close,
   provider-vintage, price-basis, and semantic checks pass.
3. Candidate C is the correct long-term strategy for future corrected snapshots
   and Long-Term Growth AI, but it requires future release tooling and
   validation before it can exist.

Operational interpretation:

- First released research snapshot candidate: Candidate A, conditional on
  manifest and reproducibility validation.
- Future corrected canonical candidate: Candidate C.
- Current live DB: not directly accepted as research canonical.

## 11. Rejected Strategies

Rejected:

```text
Directly promote Candidate B
```

Reason:

- known adjusted-close rewrites;
- insufficient provider-vintage clarity;
- insufficient price-basis clarity;
- no semantic checksum;
- would risk silent research baseline mutation.

Rejected:

```text
Skip Candidate A and wait indefinitely for Candidate C
```

Reason:

- delays ResearchDataStore separation;
- leaves existing research evidence without a formal released snapshot anchor;
- does not help immediate migration planning.

Rejected:

```text
Treat A, B, and C as interchangeable baselines
```

Reason:

- violates snapshot identity and lineage;
- would break feature/target/model reproducibility;
- hides adjusted-close vintage differences.

## 12. Open Decisions

Open human decisions before any release:

- whether to accept the old composite research baseline as the first released
  snapshot candidate;
- how much provider-vintage metadata can be reconstructed for Candidate A;
- whether Candidate A limitations are acceptable for first migration freeze;
- whether to run a full corrected Candidate C build later;
- whether current live DB should be revalidated as a future Candidate C source;
- which Phase 7 / Phase 3 / backtest / replay / walk-forward / OOS artifacts are
  required as release evidence;
- what naming convention to use for the first released snapshot ID;
- who approves the release gate.

## 13. Review Decision

This phase recommends strategy only.

```text
DO NOT RELEASE SNAPSHOT IN PHASE 4A.
DO NOT MIGRATE IN PHASE 4A.
DO NOT START LONG-TERM GROWTH IN PHASE 4A.
```

The safe next step is Phase 4A review. If accepted, a later phase can design or
execute a release-gate workflow for Candidate A and a corrected Candidate C
strategy.
