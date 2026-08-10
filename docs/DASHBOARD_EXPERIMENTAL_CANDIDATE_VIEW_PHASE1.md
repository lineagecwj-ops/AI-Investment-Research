# Dashboard Experimental Candidate View Phase 1

## Purpose

Phase 4 Phase 1 adds an Experimental Candidate View to the current swing research Dashboard. The view is display-only and helps inspect the existing Candidate Display Research Phase 3 classification projection during the current scanner session.

Production V1 remains authoritative. The Dashboard must continue to show Formal V1 as the primary section before any experimental display.

## Data Source

The view reuses the existing scanner result and condition coverage summary. It then consumes the canonical Phase 3 classification service from `candidate_display_research_service`.

The Dashboard does not rewrite classification rules in `app.py`, recompute technical indicators, fetch Yahoo data, write SQLite, or persist display history.

## Display Semantics

Formal V1:

- `正式 V1 命中`
- Coverage `5/5`
- Production V1 status `正式命中`
- No Experimental or Research-only badge

Research Priority A:

- `研究優先觀察 A`
- Coverage `4/5`
- Only missing RSI
- Marked as `實驗研究分類`

Research Priority B:

- `研究優先觀察 B`
- Coverage `4/5`
- Only missing volume
- Marked as `實驗研究分類`
- May show `V1.1 實驗版符合`
- Production V1 remains `不符合`

Research Watch:

- `研究觀察`
- Coverage `4/5`
- Only missing distance to prior high
- Marked as `實驗研究分類`

Exploratory:

- `探索觀察`
- Other `4/5` rows and `3/5` rows
- `3/5` rows are collapsed by default in the UI

Below Display Scope:

- `0-2/5`
- Count only by default
- No full default list

## Safety Boundaries

This phase creates no ranking, score, confidence, individual probability, expected return, recommendation, top picks, buy/sell wording, alerts, watchlist automation, or persisted candidate history.

Historical group HHR can only be explanatory group metadata. Phase 1 keeps the UI simple and does not show HHR in per-symbol rows.

## Error Isolation

If the experimental projection cannot load, the Dashboard shows `實驗候選觀察暫時無法載入` while keeping the Formal V1 Production section available.

## Rollback

Rollback is limited to removing the experimental projection adapter, the experimental render subsection, related tests, and this document. No database rollback is required because Phase 1 performs no schema change, no DB write, and no persistence.
