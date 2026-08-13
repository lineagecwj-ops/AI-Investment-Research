from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from database import CREATE_HISTORICAL_FINANCIALS_TABLE_SQL
from database import CREATE_HISTORICAL_PRICES_TABLE_SQL
from database import CREATE_HISTORICAL_PRICE_FETCH_STATE_TABLE_SQL
from database import CREATE_STOCKS_TABLE_SQL
from database_config import DEFAULT_DATABASE_PATH_CONFIG


LIVE_TABLES = (
    "historical_prices",
    "historical_price_fetch_state",
    "stocks",
    "historical_financials",
)
FORBIDDEN_LIVE_TABLES = (
    "snapshot_metadata",
    "research_universes",
    "research_universe_symbols",
)


class FormalLiveStoreCreationError(Exception):
    """Raised when a fresh live store cannot be created safely."""


@dataclass(frozen=True)
class FormalLiveStoreCreationResult:
    db_path: Path
    database_checksum: str
    tables: tuple[str, ...]
    forbidden_tables_present: tuple[str, ...]
    historical_prices_rows: int
    fetch_state_rows: int
    stocks_rows: int
    historical_financials_rows: int
    integrity_check: str


def create_fresh_live_store(
    db_path: Path | str | None = None,
    *,
    overwrite: bool = False,
) -> FormalLiveStoreCreationResult:
    path = Path(db_path) if db_path is not None else DEFAULT_DATABASE_PATH_CONFIG.live_db_path
    if path.exists() and not overwrite:
        raise FormalLiveStoreCreationError(f"Live store already exists: {path}")
    if path.exists() and overwrite:
        path.unlink()

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(CREATE_STOCKS_TABLE_SQL)
        connection.execute(CREATE_HISTORICAL_FINANCIALS_TABLE_SQL)
        connection.execute(CREATE_HISTORICAL_PRICES_TABLE_SQL)
        connection.execute(CREATE_HISTORICAL_PRICE_FETCH_STATE_TABLE_SQL)
        connection.commit()
    finally:
        connection.close()

    result = validate_live_store_schema(path)
    if set(result.tables) != set(LIVE_TABLES):
        raise FormalLiveStoreCreationError("Fresh live store schema does not match expected live-only tables.")
    if result.forbidden_tables_present:
        raise FormalLiveStoreCreationError("Fresh live store contains forbidden research tables.")
    if any(
        count != 0
        for count in (
            result.historical_prices_rows,
            result.fetch_state_rows,
            result.stocks_rows,
            result.historical_financials_rows,
        )
    ):
        raise FormalLiveStoreCreationError("Fresh live store must start with empty cache tables.")
    return result


def validate_live_store_schema(db_path: Path | str) -> FormalLiveStoreCreationResult:
    path = Path(db_path)
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = tuple(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        )
        forbidden = tuple(table for table in FORBIDDEN_LIVE_TABLES if table in tables)
        historical_prices_rows = _count_rows(connection, "historical_prices")
        fetch_state_rows = _count_rows(connection, "historical_price_fetch_state")
        stocks_rows = _count_rows(connection, "stocks")
        historical_financials_rows = _count_rows(connection, "historical_financials")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()

    return FormalLiveStoreCreationResult(
        db_path=path,
        database_checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        tables=tables,
        forbidden_tables_present=forbidden,
        historical_prices_rows=historical_prices_rows,
        fetch_state_rows=fetch_state_rows,
        stocks_rows=stocks_rows,
        historical_financials_rows=historical_financials_rows,
        integrity_check=integrity,
    )


def _count_rows(connection: sqlite3.Connection, table: str) -> int:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if not exists:
        return -1
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
