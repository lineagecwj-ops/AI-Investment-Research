import logging
import sqlite3
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from models import Stock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "stocks.db"
CACHE_TTL = timedelta(hours=24)


CREATE_STOCKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    company_name TEXT,
    current_price REAL,
    currency TEXT,
    market_cap INTEGER,
    trailing_pe REAL,
    forward_pe REAL,
    trailing_eps REAL,
    return_on_equity REAL,
    sector TEXT,
    industry TEXT,
    fetched_at TEXT NOT NULL
)
"""


def utc_now() -> datetime:
    return datetime.now(UTC)


def initialize_database(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.execute(CREATE_STOCKS_TABLE_SQL)
        connection.commit()
    finally:
        connection.close()


def save_stock(
    stock: Stock,
    db_path: Path | str = DEFAULT_DB_PATH,
    fetched_at: datetime | None = None,
) -> None:
    if not stock.symbol:
        raise ValueError("Stock symbol is required before saving to cache.")

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime_to_cache_value(fetched_at or utc_now())

    connection = sqlite3.connect(path)
    try:
        connection.execute(CREATE_STOCKS_TABLE_SQL)
        connection.execute(
            """
            INSERT INTO stocks (
                symbol,
                company_name,
                current_price,
                currency,
                market_cap,
                trailing_pe,
                forward_pe,
                trailing_eps,
                return_on_equity,
                sector,
                industry,
                fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                company_name = excluded.company_name,
                current_price = excluded.current_price,
                currency = excluded.currency,
                market_cap = excluded.market_cap,
                trailing_pe = excluded.trailing_pe,
                forward_pe = excluded.forward_pe,
                trailing_eps = excluded.trailing_eps,
                return_on_equity = excluded.return_on_equity,
                sector = excluded.sector,
                industry = excluded.industry,
                fetched_at = excluded.fetched_at
            """,
            (
                stock.symbol,
                stock.company_name,
                stock.current_price,
                stock.currency,
                stock.market_cap,
                stock.trailing_pe,
                stock.forward_pe,
                stock.trailing_eps,
                stock.return_on_equity,
                stock.sector,
                stock.industry,
                timestamp,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def get_cached_stock(
    symbol: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    now: datetime | None = None,
    ttl: timedelta = CACHE_TTL,
) -> Stock | None:
    initialize_database(db_path)

    connection = sqlite3.connect(Path(db_path))
    try:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT
                symbol,
                company_name,
                current_price,
                currency,
                market_cap,
                trailing_pe,
                forward_pe,
                trailing_eps,
                return_on_equity,
                sector,
                industry,
                fetched_at
            FROM stocks
            WHERE symbol = ?
            """,
            (symbol,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    fetched_at = parse_cache_datetime(row["fetched_at"])
    if is_cache_expired(fetched_at, now=now, ttl=ttl):
        return None

    return stock_from_row(row)


def stock_from_row(row: sqlite3.Row) -> Stock:
    return Stock(
        symbol=row["symbol"],
        company_name=row["company_name"],
        current_price=row["current_price"],
        currency=row["currency"],
        market_cap=row["market_cap"],
        trailing_pe=row["trailing_pe"],
        forward_pe=row["forward_pe"],
        trailing_eps=row["trailing_eps"],
        return_on_equity=row["return_on_equity"],
        sector=row["sector"],
        industry=row["industry"],
    )


def datetime_to_cache_value(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat()


def parse_cache_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def is_cache_expired(
    fetched_at: datetime,
    now: datetime | None = None,
    ttl: timedelta = CACHE_TTL,
) -> bool:
    current_time = now or utc_now()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)

    return current_time.astimezone(UTC) - fetched_at.astimezone(UTC) >= ttl


def log_cache_warning(message: str, error: Exception) -> None:
    logging.warning("%s: %s", message, error)
