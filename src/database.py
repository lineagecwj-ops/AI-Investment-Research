import logging
import sqlite3
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from models import Stock
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "stocks.db"
CACHE_TTL = timedelta(hours=24)
HISTORICAL_CACHE_TTL = timedelta(days=7)
SCHEMA_MIGRATION_EXPIRED_CACHE_TIMESTAMP = "1970-01-01T00:00:00+00:00"


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

HISTORICAL_FINANCIAL_COLUMNS = {
    "symbol": "TEXT NOT NULL",
    "period_end": "TEXT NOT NULL",
    "fiscal_year": "INTEGER",
    "currency": "TEXT",
    "revenue": "REAL",
    "gross_profit": "REAL",
    "operating_income": "REAL",
    "net_income": "REAL",
    "eps": "REAL",
    "gross_margin": "REAL",
    "operating_margin": "REAL",
    "net_margin": "REAL",
    "operating_cash_flow": "REAL",
    "capital_expenditure": "REAL",
    "free_cash_flow": "REAL",
    "total_assets": "REAL",
    "total_debt": "REAL",
    "total_equity": "REAL",
    "cash_and_cash_equivalents": "REAL",
    "fetched_at": "TEXT NOT NULL",
}

CREATE_HISTORICAL_FINANCIALS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS historical_financials (
    symbol TEXT NOT NULL,
    period_end TEXT NOT NULL,
    fiscal_year INTEGER,
    currency TEXT,
    revenue REAL,
    gross_profit REAL,
    operating_income REAL,
    net_income REAL,
    eps REAL,
    gross_margin REAL,
    operating_margin REAL,
    net_margin REAL,
    operating_cash_flow REAL,
    capital_expenditure REAL,
    free_cash_flow REAL,
    total_assets REAL,
    total_debt REAL,
    total_equity REAL,
    cash_and_cash_equivalents REAL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY(symbol, period_end)
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
        connection.execute(CREATE_HISTORICAL_FINANCIALS_TABLE_SQL)
        schema_changed = migrate_stocks_table(connection)
        migrate_historical_financials_table(connection)
        if schema_changed:
            invalidate_stock_cache_after_schema_migration(connection)
        connection.commit()
    finally:
        connection.close()


def migrate_stocks_table(connection: sqlite3.Connection) -> bool:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(stocks)").fetchall()
    }
    schema_changed = False

    for column, column_type in STOCK_COLUMNS.items():
        if column in existing_columns:
            continue
        connection.execute(f"ALTER TABLE stocks ADD COLUMN {column} {column_type}")
        schema_changed = True

    return schema_changed


def migrate_historical_financials_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(historical_financials)").fetchall()
    }

    for column, column_type in HISTORICAL_FINANCIAL_COLUMNS.items():
        if column in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE historical_financials ADD COLUMN {column} {column_type}"
        )


def invalidate_stock_cache_after_schema_migration(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        "UPDATE stocks SET fetched_at = ?",
        (SCHEMA_MIGRATION_EXPIRED_CACHE_TIMESTAMP,),
    )


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
        connection.execute(CREATE_HISTORICAL_FINANCIALS_TABLE_SQL)
        schema_changed = migrate_stocks_table(connection)
        migrate_historical_financials_table(connection)
        if schema_changed:
            invalidate_stock_cache_after_schema_migration(connection)
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


def save_historical_financials(
    series: HistoricalFinancialSeries,
    db_path: Path | str = DEFAULT_DB_PATH,
    fetched_at: datetime | None = None,
) -> None:
    if not series.symbol:
        raise ValueError("Historical financial series symbol is required before saving.")

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime_to_cache_value(fetched_at or utc_now())

    connection = sqlite3.connect(path)
    try:
        connection.execute(CREATE_STOCKS_TABLE_SQL)
        connection.execute(CREATE_HISTORICAL_FINANCIALS_TABLE_SQL)
        schema_changed = migrate_stocks_table(connection)
        migrate_historical_financials_table(connection)
        if schema_changed:
            invalidate_stock_cache_after_schema_migration(connection)

        for period in series.periods or []:
            connection.execute(
                """
                INSERT INTO historical_financials (
                    symbol,
                    period_end,
                    fiscal_year,
                    currency,
                    revenue,
                    gross_profit,
                    operating_income,
                    net_income,
                    eps,
                    gross_margin,
                    operating_margin,
                    net_margin,
                    operating_cash_flow,
                    capital_expenditure,
                    free_cash_flow,
                    total_assets,
                    total_debt,
                    total_equity,
                    cash_and_cash_equivalents,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, period_end) DO UPDATE SET
                    fiscal_year = excluded.fiscal_year,
                    currency = excluded.currency,
                    revenue = excluded.revenue,
                    gross_profit = excluded.gross_profit,
                    operating_income = excluded.operating_income,
                    net_income = excluded.net_income,
                    eps = excluded.eps,
                    gross_margin = excluded.gross_margin,
                    operating_margin = excluded.operating_margin,
                    net_margin = excluded.net_margin,
                    operating_cash_flow = excluded.operating_cash_flow,
                    capital_expenditure = excluded.capital_expenditure,
                    free_cash_flow = excluded.free_cash_flow,
                    total_assets = excluded.total_assets,
                    total_debt = excluded.total_debt,
                    total_equity = excluded.total_equity,
                    cash_and_cash_equivalents = excluded.cash_and_cash_equivalents,
                    fetched_at = excluded.fetched_at
                """,
                historical_period_to_row_values(period, timestamp),
            )
        connection.commit()
    finally:
        connection.close()


def get_cached_historical_financials(
    symbol: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    now: datetime | None = None,
    ttl: timedelta = HISTORICAL_CACHE_TTL,
    include_expired: bool = False,
) -> HistoricalFinancialSeries | None:
    initialize_database(db_path)

    connection = sqlite3.connect(Path(db_path))
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                {", ".join(HISTORICAL_FINANCIAL_COLUMNS)}
            FROM historical_financials
            WHERE symbol = ?
            ORDER BY period_end ASC
            """,
            (symbol,),
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return None

    fetched_at_values = [
        parse_cache_datetime(row["fetched_at"])
        for row in rows
        if row["fetched_at"]
    ]
    fetched_at = max(fetched_at_values) if fetched_at_values else None
    is_stale = bool(
        fetched_at
        and is_cache_expired(fetched_at, now=now, ttl=ttl)
    )
    if is_stale and not include_expired:
        return None

    currency = next((row["currency"] for row in rows if row["currency"]), None)
    return HistoricalFinancialSeries(
        symbol=symbol,
        currency=currency,
        periods=[historical_period_from_row(row) for row in rows],
        fetched_at=fetched_at,
        is_stale=is_stale,
    )


def historical_period_to_row_values(
    period: HistoricalFinancialPeriod,
    fetched_at: str,
) -> tuple:
    return (
        period.symbol,
        period.period_end.isoformat(),
        period.fiscal_year,
        period.currency,
        period.revenue,
        period.gross_profit,
        period.operating_income,
        period.net_income,
        period.eps,
        period.gross_margin,
        period.operating_margin,
        period.net_margin,
        period.operating_cash_flow,
        period.capital_expenditure,
        period.free_cash_flow,
        period.total_assets,
        period.total_debt,
        period.total_equity,
        period.cash_and_cash_equivalents,
        fetched_at,
    )


def historical_period_from_row(row: sqlite3.Row) -> HistoricalFinancialPeriod:
    return HistoricalFinancialPeriod(
        symbol=row["symbol"],
        period_end=datetime.fromisoformat(row["period_end"]).date(),
        fiscal_year=row["fiscal_year"],
        currency=row["currency"],
        revenue=row["revenue"],
        gross_profit=row["gross_profit"],
        operating_income=row["operating_income"],
        net_income=row["net_income"],
        eps=row["eps"],
        gross_margin=row["gross_margin"],
        operating_margin=row["operating_margin"],
        net_margin=row["net_margin"],
        operating_cash_flow=row["operating_cash_flow"],
        capital_expenditure=row["capital_expenditure"],
        free_cash_flow=row["free_cash_flow"],
        total_assets=row["total_assets"],
        total_debt=row["total_debt"],
        total_equity=row["total_equity"],
        cash_and_cash_equivalents=row["cash_and_cash_equivalents"],
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
