# MVP Scanner Frozen TWSE Universe Integration

## Purpose

Phase 1 adds one scanner input source for Swing Research current-market scanning:

`研究股票池（Frozen TWSE 218）`

The source loads the currently locked Frozen TWSE research universe and passes those symbols into the existing `SwingScannerService` current-market path.

## Frozen TWSE 218 Definition

- Canonical source service: `src/frozen_twse_research_universe_service.py`
- Underlying materialized source: `data/stocks.db` historical price symbols read in SQLite `mode=ro`
- Universe version: `2026-08-current-etf-constituent-v1`
- Universe ID: `frozen_twse_research_universe_2026_08_09`
- Frozen Taiwan total: `224`
- Current MVP source: `218` TWSE common-stock symbols
- TPEx excluded in this phase: `6`
- Symbol format: scanner-ready `####.TW`
- Ordering: deterministic ascending symbol order

This is not the full Taiwan market. It is a 2026 current ETF constituent-derived universe, not a historical point-in-time universe.

## UI Behavior

- The dropdown keeps existing sources: manual input, watchlist, and saved universe.
- Current-market mode adds `研究股票池（Frozen TWSE 218）`.
- Selecting the Frozen source hides the manual textarea.
- The screen shows the source label, `218` symbol count, Production V1 signal label, universe version, and universe ID before execution.
- Selecting the source does not automatically scan.
- The user must still press `執行波段掃描`.

## Scanner Behavior

- The existing `SwingScannerService` remains the scanner entry point.
- The default signal remains Production V1: `technical_example_v1`.
- The existing current-market price path is unchanged: local cache first, with Yahoo Finance fallback and SQLite cache update if cache is missing or stale.
- This integration does not change technical formulas, scanner qualification semantics, Condition Coverage, Phase 3 candidate classification, Phase 4 Experimental Candidate View, V1.1, ranking, recommendations, probabilities, historical outcomes, backtest, replay, walk-forward, OOS, AI logic, or DB schema/content.

## Safety And Error Handling

The loader validates:

- count equals `218`
- symbols are unique
- all symbols are four-digit `.TW`
- no `.TWO`
- no non-Taiwan symbols
- no ETF source code `0050.TW`
- deterministic ascending order

If validation fails, the UI shows `研究股票池目前無法載入。` and does not fall back to manual input, watchlist, saved universe, Yahoo universe, or any rebuilt universe.

## No Persistence

Loading this source does not:

- write to SQLite
- fetch Yahoo Finance
- mutate the watchlist
- create or update a saved universe
- persist a new symbol list

## Rollback Path

Remove the Frozen source from the current-market `source_options` in `app.py`, and remove the source constant from `src/universe_dashboard.py`. Existing manual, watchlist, and saved-universe paths are independent and remain usable.
