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


STOCK_COLUMNS = {
    "symbol": "TEXT PRIMARY KEY",
    "company_name": "TEXT",
    "current_price": "REAL",
    "currency": "TEXT",
    "market_cap": "INTEGER",
    "trailing_pe": "REAL",
    "forward_pe": "REAL",
    "trailing_eps": "REAL",
    "return_on_equity": "REAL",
    "company_summary": "TEXT",
    "gross_margin": "REAL",
    "operating_margin": "REAL",
    "net_margin": "REAL",
    "revenue_growth": "REAL",
    "earnings_growth": "REAL",
    "total_cash": "INTEGER",
    "total_debt": "INTEGER",
    "debt_to_equity": "REAL",
    "operating_cash_flow": "INTEGER",
    "free_cash_flow": "INTEGER",
    "price_to_book": "REAL",
    "fifty_two_week_high": "REAL",
    "fifty_two_week_low": "REAL",
    "fifty_day_average": "REAL",
    "two_hundred_day_average": "REAL",
    "sector": "TEXT",
    "industry": "TEXT",
    "fetched_at": "TEXT NOT NULL",
}

STOCK_FIELD_COLUMNS = [
    column for column in STOCK_COLUMNS if column != "fetched_at"
]


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
    company_summary TEXT,
    gross_margin REAL,
    operating_margin REAL,
    net_margin REAL,
    revenue_growth REAL,
    earnings_growth REAL,
    total_cash INTEGER,
    total_debt INTEGER,
    debt_to_equity REAL,
    operating_cash_flow INTEGER,
    free_cash_flow INTEGER,
    price_to_book REAL,
    fifty_two_week_high REAL,
    fifty_two_week_low REAL,
    fifty_day_average REAL,
    two_hundred_day_average REAL,
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
        migrate_stocks_table(connection)
        connection.commit()
    finally:
        connection.close()


def migrate_stocks_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(stocks)").fetchall()
    }

    for column, column_type in STOCK_COLUMNS.items():
        if column in existing_columns:
            continue
        connection.execute(f"ALTER TABLE stocks ADD COLUMN {column} {column_type}")


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
        migrate_stocks_table(connection)
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
                company_summary,
                gross_margin,
                operating_margin,
                net_margin,
                revenue_growth,
                earnings_growth,
                total_cash,
                total_debt,
                debt_to_equity,
                operating_cash_flow,
                free_cash_flow,
                price_to_book,
                fifty_two_week_high,
                fifty_two_week_low,
                fifty_day_average,
                two_hundred_day_average,
                sector,
                industry,
                fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                company_name = excluded.company_name,
                current_price = excluded.current_price,
                currency = excluded.currency,
                market_cap = excluded.market_cap,
                trailing_pe = excluded.trailing_pe,
                forward_pe = excluded.forward_pe,
                trailing_eps = excluded.trailing_eps,
                return_on_equity = excluded.return_on_equity,
                company_summary = excluded.company_summary,
                gross_margin = excluded.gross_margin,
                operating_margin = excluded.operating_margin,
                net_margin = excluded.net_margin,
                revenue_growth = excluded.revenue_growth,
                earnings_growth = excluded.earnings_growth,
                total_cash = excluded.total_cash,
                total_debt = excluded.total_debt,
                debt_to_equity = excluded.debt_to_equity,
                operating_cash_flow = excluded.operating_cash_flow,
                free_cash_flow = excluded.free_cash_flow,
                price_to_book = excluded.price_to_book,
                fifty_two_week_high = excluded.fifty_two_week_high,
                fifty_two_week_low = excluded.fifty_two_week_low,
                fifty_day_average = excluded.fifty_day_average,
                two_hundred_day_average = excluded.two_hundred_day_average,
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
                stock.company_summary,
                stock.gross_margin,
                stock.operating_margin,
                stock.net_margin,
                stock.revenue_growth,
                stock.earnings_growth,
                stock.total_cash,
                stock.total_debt,
                stock.debt_to_equity,
                stock.operating_cash_flow,
                stock.free_cash_flow,
                stock.price_to_book,
                stock.fifty_two_week_high,
                stock.fifty_two_week_low,
                stock.fifty_day_average,
                stock.two_hundred_day_average,
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
            f"""
            SELECT
                {", ".join(STOCK_COLUMNS)}
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
        company_summary=row["company_summary"],
        gross_margin=row["gross_margin"],
        operating_margin=row["operating_margin"],
        net_margin=row["net_margin"],
        revenue_growth=row["revenue_growth"],
        earnings_growth=row["earnings_growth"],
        total_cash=row["total_cash"],
        total_debt=row["total_debt"],
        debt_to_equity=row["debt_to_equity"],
        operating_cash_flow=row["operating_cash_flow"],
        free_cash_flow=row["free_cash_flow"],
        price_to_book=row["price_to_book"],
        fifty_two_week_high=row["fifty_two_week_high"],
        fifty_two_week_low=row["fifty_two_week_low"],
        fifty_day_average=row["fifty_day_average"],
        two_hundred_day_average=row["two_hundred_day_average"],
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
