import logging
import sqlite3
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from database_config import DEFAULT_DATABASE_PATH_CONFIG
from database_config import PROJECT_ROOT
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import Stock


DEFAULT_DB_PATH = DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path
CACHE_TTL = timedelta(hours=24)
HISTORICAL_CACHE_TTL = timedelta(days=7)
HISTORICAL_PRICE_CACHE_TTL = timedelta(hours=12)
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
    "period_year": "INTEGER",
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
    period_year INTEGER,
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

HISTORICAL_PRICE_COLUMNS = {
    "symbol": "TEXT NOT NULL",
    "trading_date": "TEXT NOT NULL",
    "open": "REAL",
    "high": "REAL NOT NULL",
    "low": "REAL NOT NULL",
    "close": "REAL NOT NULL",
    "adjusted_close": "REAL",
    "volume": "INTEGER",
    "dividends": "REAL",
    "stock_splits": "REAL",
    "currency": "TEXT",
    "fetched_at": "TEXT NOT NULL",
}

CREATE_HISTORICAL_PRICES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS historical_prices (
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    open REAL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    adjusted_close REAL,
    volume INTEGER,
    dividends REAL,
    stock_splits REAL,
    currency TEXT,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY(symbol, trading_date)
)
"""

HISTORICAL_PRICE_FETCH_STATE_COLUMNS = {
    "symbol": "TEXT PRIMARY KEY",
    "full_history_fetched": "INTEGER NOT NULL DEFAULT 0",
    "earliest_date": "TEXT",
    "latest_date": "TEXT",
    "fetched_at": "TEXT NOT NULL",
}

CREATE_HISTORICAL_PRICE_FETCH_STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS historical_price_fetch_state (
    symbol TEXT PRIMARY KEY,
    full_history_fetched INTEGER NOT NULL DEFAULT 0,
    earliest_date TEXT,
    latest_date TEXT,
    fetched_at TEXT NOT NULL
)
"""

RESEARCH_UNIVERSE_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "name": "TEXT NOT NULL",
    "description": "TEXT",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}

RESEARCH_UNIVERSE_SYMBOL_COLUMNS = {
    "universe_id": "TEXT NOT NULL",
    "position": "INTEGER NOT NULL",
    "symbol": "TEXT NOT NULL",
}

CREATE_RESEARCH_UNIVERSES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS research_universes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_RESEARCH_UNIVERSE_SYMBOLS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS research_universe_symbols (
    universe_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    PRIMARY KEY(universe_id, symbol),
    FOREIGN KEY(universe_id) REFERENCES research_universes(id)
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
        connection.execute(CREATE_HISTORICAL_PRICES_TABLE_SQL)
        connection.execute(CREATE_HISTORICAL_PRICE_FETCH_STATE_TABLE_SQL)
        connection.execute(CREATE_RESEARCH_UNIVERSES_TABLE_SQL)
        connection.execute(CREATE_RESEARCH_UNIVERSE_SYMBOLS_TABLE_SQL)
        schema_changed = migrate_stocks_table(connection)
        migrate_historical_financials_table(connection)
        migrate_historical_prices_table(connection)
        migrate_historical_price_fetch_state_table(connection)
        migrate_research_universes_table(connection)
        migrate_research_universe_symbols_table(connection)
        if schema_changed:
            invalidate_stock_cache_after_schema_migration(connection)
        connection.commit()
    finally:
        connection.close()


def initialize_live_cache_tables(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_STOCKS_TABLE_SQL)
    connection.execute(CREATE_HISTORICAL_FINANCIALS_TABLE_SQL)
    connection.execute(CREATE_HISTORICAL_PRICES_TABLE_SQL)
    connection.execute(CREATE_HISTORICAL_PRICE_FETCH_STATE_TABLE_SQL)
    schema_changed = migrate_stocks_table(connection)
    migrate_historical_financials_table(connection)
    migrate_historical_prices_table(connection)
    migrate_historical_price_fetch_state_table(connection)
    if schema_changed:
        invalidate_stock_cache_after_schema_migration(connection)


def initialize_live_cache_database(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        initialize_live_cache_tables(connection)
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

    connection.execute(
        """
        UPDATE historical_financials
        SET period_year = CAST(substr(period_end, 1, 4) AS INTEGER)
        WHERE period_year IS NULL
          AND period_end IS NOT NULL
          AND length(period_end) >= 4
        """
    )


def migrate_historical_prices_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(historical_prices)").fetchall()
    }

    for column, column_type in HISTORICAL_PRICE_COLUMNS.items():
        if column in existing_columns:
            continue
        connection.execute(f"ALTER TABLE historical_prices ADD COLUMN {column} {column_type}")


def migrate_historical_price_fetch_state_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(historical_price_fetch_state)"
        ).fetchall()
    }

    for column, column_type in HISTORICAL_PRICE_FETCH_STATE_COLUMNS.items():
        if column in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE historical_price_fetch_state ADD COLUMN {column} {column_type}"
        )


def migrate_research_universes_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(research_universes)").fetchall()
    }

    for column, column_type in RESEARCH_UNIVERSE_COLUMNS.items():
        if column in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE research_universes ADD COLUMN {column} {column_type}"
        )


def migrate_research_universe_symbols_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(research_universe_symbols)"
        ).fetchall()
    }

    for column, column_type in RESEARCH_UNIVERSE_SYMBOL_COLUMNS.items():
        if column in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE research_universe_symbols ADD COLUMN {column} {column_type}"
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
        initialize_live_cache_tables(connection)
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
    initialize_live_cache_database(db_path)

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
        initialize_live_cache_tables(connection)

        for period in series.periods or []:
            connection.execute(
                """
                INSERT INTO historical_financials (
                    symbol,
                    period_end,
                    period_year,
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
                    period_year = excluded.period_year,
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
    initialize_live_cache_database(db_path)

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
        period.period_year,
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
        period_year=row["period_year"],
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


def save_historical_prices(
    series: HistoricalPriceSeries,
    db_path: Path | str = DEFAULT_DB_PATH,
    fetched_at: datetime | None = None,
    full_history_fetched: bool = False,
) -> None:
    if not series.symbol:
        raise ValueError("Historical price series symbol is required before saving.")

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime_to_cache_value(fetched_at or series.fetched_at or utc_now())

    connection = sqlite3.connect(path)
    try:
        initialize_historical_price_tables(connection)
        for bar in series.bars:
            connection.execute(
                """
                INSERT INTO historical_prices (
                    symbol,
                    trading_date,
                    open,
                    high,
                    low,
                    close,
                    adjusted_close,
                    volume,
                    dividends,
                    stock_splits,
                    currency,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trading_date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    adjusted_close = excluded.adjusted_close,
                    volume = excluded.volume,
                    dividends = excluded.dividends,
                    stock_splits = excluded.stock_splits,
                    currency = excluded.currency,
                    fetched_at = excluded.fetched_at
                """,
                historical_price_bar_to_row_values(bar, series.currency, timestamp),
            )
        if series.bars:
            upsert_historical_price_fetch_state(
                connection,
                symbol=series.symbol,
                earliest_date=series.bars[0].trading_date,
                latest_date=series.bars[-1].trading_date,
                fetched_at=timestamp,
                full_history_fetched=full_history_fetched,
            )
        connection.commit()
    finally:
        connection.close()


def initialize_historical_price_tables(connection: sqlite3.Connection) -> None:
    initialize_live_cache_tables(connection)


def upsert_historical_price_fetch_state(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    earliest_date: date,
    latest_date: date,
    fetched_at: str,
    full_history_fetched: bool,
) -> None:
    existing = connection.execute(
        """
        SELECT earliest_date, latest_date, full_history_fetched
        FROM historical_price_fetch_state
        WHERE symbol = ?
        """,
        (symbol,),
    ).fetchone()
    if existing is not None:
        existing_earliest = parse_cache_date(existing[0])
        existing_latest = parse_cache_date(existing[1])
        earliest_date = min(
            value for value in [existing_earliest, earliest_date] if value is not None
        )
        latest_date = max(
            value for value in [existing_latest, latest_date] if value is not None
        )
        full_history_fetched = bool(full_history_fetched or existing[2])

    connection.execute(
        """
        INSERT INTO historical_price_fetch_state (
            symbol,
            full_history_fetched,
            earliest_date,
            latest_date,
            fetched_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            full_history_fetched = excluded.full_history_fetched,
            earliest_date = excluded.earliest_date,
            latest_date = excluded.latest_date,
            fetched_at = excluded.fetched_at
        """,
        (
            symbol,
            1 if full_history_fetched else 0,
            earliest_date.isoformat(),
            latest_date.isoformat(),
            fetched_at,
        ),
    )


def get_cached_historical_prices(
    symbol: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    *,
    start: date | None = None,
    end: date | None = None,
    now: datetime | None = None,
    ttl: timedelta = HISTORICAL_PRICE_CACHE_TTL,
    include_expired: bool = False,
    require_full_history: bool = False,
) -> HistoricalPriceSeries | None:
    initialize_live_cache_database(db_path)

    if not historical_price_cache_covers_range(
        symbol,
        db_path=db_path,
        start=start,
        end=end,
        require_full_history=require_full_history,
    ):
        return None

    connection = sqlite3.connect(Path(db_path))
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                {", ".join(HISTORICAL_PRICE_COLUMNS)}
            FROM historical_prices
            WHERE symbol = ?
              AND (? IS NULL OR trading_date >= ?)
              AND (? IS NULL OR trading_date <= ?)
            ORDER BY trading_date ASC
            """,
            (
                symbol,
                start.isoformat() if start else None,
                start.isoformat() if start else None,
                end.isoformat() if end else None,
                end.isoformat() if end else None,
            ),
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
    fetched_at = min(fetched_at_values) if fetched_at_values else utc_now()
    is_stale = is_cache_expired(fetched_at, now=now, ttl=ttl)
    if is_stale and not include_expired:
        return None

    currency = next((row["currency"] for row in rows if row["currency"]), None)
    return HistoricalPriceSeries(
        symbol=symbol,
        currency=currency,
        bars=tuple(historical_price_bar_from_row(row) for row in rows),
        fetched_at=fetched_at,
        is_stale=is_stale,
    )


def historical_price_cache_covers_range(
    symbol: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    *,
    start: date | None = None,
    end: date | None = None,
    require_full_history: bool = False,
) -> bool:
    state = get_historical_price_fetch_state(symbol, db_path=db_path)
    if state is None:
        return False

    earliest = state["earliest_date"]
    latest = state["latest_date"]
    if earliest is None or latest is None:
        return False
    if require_full_history and not state["full_history_fetched"]:
        return False
    if start is not None and earliest > start:
        return False
    if end is not None and latest < end:
        return False
    return True


def get_historical_price_fetch_state(
    symbol: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict | None:
    initialize_live_cache_database(db_path)

    connection = sqlite3.connect(Path(db_path))
    try:
        row = connection.execute(
            """
            SELECT full_history_fetched, earliest_date, latest_date, fetched_at
            FROM historical_price_fetch_state
            WHERE symbol = ?
            """,
            (symbol,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return {
        "full_history_fetched": bool(row[0]),
        "earliest_date": parse_cache_date(row[1]),
        "latest_date": parse_cache_date(row[2]),
        "fetched_at": parse_cache_datetime(row[3]),
    }


def get_latest_historical_price_date(
    symbol: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> date | None:
    initialize_live_cache_database(db_path)

    connection = sqlite3.connect(Path(db_path))
    try:
        row = connection.execute(
            """
            SELECT MAX(trading_date)
            FROM historical_prices
            WHERE symbol = ?
            """,
            (symbol,),
        ).fetchone()
    finally:
        connection.close()

    return parse_cache_date(row[0]) if row and row[0] else None


def historical_price_bar_to_row_values(
    bar: HistoricalPriceBar,
    currency: str | None,
    fetched_at: str,
) -> tuple:
    return (
        bar.symbol,
        bar.trading_date.isoformat(),
        bar.open,
        bar.high,
        bar.low,
        bar.close,
        bar.adjusted_close,
        bar.volume,
        bar.dividends,
        bar.stock_splits,
        currency,
        fetched_at,
    )


def historical_price_bar_from_row(row: sqlite3.Row) -> HistoricalPriceBar:
    return HistoricalPriceBar(
        symbol=row["symbol"],
        trading_date=datetime.fromisoformat(row["trading_date"]).date(),
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        adjusted_close=row["adjusted_close"],
        volume=row["volume"],
        dividends=row["dividends"],
        stock_splits=row["stock_splits"],
    )


def parse_cache_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).date()


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
