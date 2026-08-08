# Universe Management

## Purpose

Sprint 07 Batch B adds saved research universes: user-defined symbol collections for Swing Research scanning.

A Universe is a research symbol collection. It is not a recommendation list, buy list, AI-selected pool, high-hit-rate pool, prediction, or investment advice.

## Universe vs Watchlist

Watchlist remains a single personal observation list persisted in `data/watchlist.json`.

Universe is a separate named collection model persisted in SQLite. Multiple Universes can exist at the same time, each with its own stable id, name, optional description, symbol order, and timestamps.

The two concepts are intentionally separate:

- Watchlist: one personal list.
- Universe: many named research collections.

Swing Research can read either source, but it does not copy Watchlist symbols into Universe storage.

## Named Collections

Each saved Universe has:

- `id`: stable persisted id created once.
- `name`: required, trimmed, non-empty, max 100 characters.
- `description`: optional, max 500 characters.
- `symbols`: normalized tuple of symbols.
- `created_at`: timezone-aware UTC timestamp.
- `updated_at`: timezone-aware UTC timestamp.

Universe names are case-insensitive unique. Duplicate names raise a domain error instead of silently renaming.

## Symbol Normalization

Universe symbols use the shared `normalize_stock_symbol()` helper.

Examples:

- `2330` -> `2330.TW`
- `2330.TW` -> `2330.TW`
- `6488.TWO` -> `6488.TWO`
- `NVDA` -> `NVDA`

Duplicate normalized symbols collapse before persistence.

## Symbol Order

Symbols preserve deterministic first-seen order. This matches the user-edited multiline input and also allows reordering by editing the symbol text.

## Multi-Market Support

A single Universe can mix Taiwan listed, Taiwan OTC, and US symbols, such as:

```text
2330.TW
6488.TWO
NVDA
AAPL
```

Universe storage does not infer market, currency, industry, or internal security ids.

## Persistence

Universe data is stored in SQLite:

```text
research_universes
research_universe_symbols
```

`initialize_database()` creates these tables additively and can be called repeatedly. No database deletion or reset is required.

Symbol membership is normalized into `research_universe_symbols` with `position` for order preservation and `PRIMARY KEY(universe_id, symbol)` for uniqueness.

Delete explicitly removes membership rows and then removes the Universe row, so it does not depend on SQLite foreign key cascade being enabled.

## Create / Edit / Delete

Create, edit, and delete operations are handled by `src/universe_service.py`.

The service API includes:

- `create_universe()`
- `get_universe()`
- `list_universes()`
- `update_universe()`
- `delete_universe()`
- `add_symbols()`
- `remove_symbols()`
- `replace_symbols()`

Multi-table writes run in transactions.

## Empty Universe

Empty Universes are allowed. This supports creating a named research pool first and adding symbols later.

Swing Research does not run the scanner for an empty Universe. It shows a zero-symbol message instead.

## No Network During CRUD

Universe create, edit, delete, and list operations are local database operations only. They do not call Yahoo Finance, OpenAI, or any external service.

Symbol existence is not validated during CRUD. Provider failures are handled later by the scanner when the user explicitly runs a scan.

## Swing Research Source

Swing Research supports explicit symbol source selection:

- Manual Input
- Watchlist
- Saved Universe

Manual Input remains available and does not require creating a Universe.

Saved Universe selection shows the Universe name, symbol count, updated timestamp, and symbol preview. Selecting a Universe does not run the scanner.

## Scan-Time Snapshot

When a scan runs, Swing Research stores the actual normalized symbols used for that scan in session state source metadata.

This means an existing result still represents the symbols scanned at that time even if the Universe or Watchlist changes later.

## Fingerprint / Content Change

The Swing Research fingerprint includes:

- source mode
- resolved normalized symbols
- signal id
- outcome id
- overlap policy
- cooldown
- date range
- preferred resolved sample minimum

The fingerprint is based on content, not only a Universe id. If Universe membership changes after a scan, the current configuration differs from the stored result and the UI asks the user to scan again.

## Edit After Scan

If a user scans Universe A with two symbols and later edits Universe A to three symbols, the old scan result still displays the two-symbol scan-time snapshot. It does not mutate into a three-symbol result.

## Delete After Scan

Deleting a Universe removes only Universe metadata and membership rows. It does not delete historical prices, Watchlist, AI data, scanner outputs, or session scan results.

Existing session results can still render because they store source name and symbol snapshot.

## No All-Market Crawler

This Batch does not add all-market Taiwan scanning, US market scanning, S&P 500 crawling, built-in index universes, automatic sector grouping, AI Universe generation, alerts, or scheduled scanning.

## Future Work

Future batches can add CSV import/export, built-in index universes, market-wide providers, industry groups, scheduled scanning, or copy/duplicate Universe actions.
