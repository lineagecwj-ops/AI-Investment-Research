import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import get_cached_stock
from database import get_cached_historical_financials
from database import get_cached_historical_prices
from database import get_historical_price_fetch_state
from database import get_latest_historical_price_date
from database import HISTORICAL_CACHE_TTL
from database import HISTORICAL_PRICE_CACHE_TTL
from database import initialize_database
from database import SCHEMA_MIGRATION_EXPIRED_CACHE_TIMESTAMP
from database import save_historical_financials
from database import save_historical_prices
from database import save_stock
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import Stock


class DatabaseTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    def tearDown(self):
        self.temp_dir.cleanup()

    def sample_stock(self, symbol="NVDA", price=200.75):
        return Stock(
            symbol=symbol,
            company_name="NVIDIA Corporation",
            current_price=price,
            currency="USD",
            market_cap=4879000000000,
            trailing_pe=57.68,
            forward_pe=44.3,
            trailing_eps=3.48,
            return_on_equity=0.25,
            company_summary="NVIDIA builds accelerated computing platforms.",
            gross_margin=0.741,
            operating_margin=0.656,
            net_margin=0.63,
            revenue_growth=0.852,
            earnings_growth=2.145,
            total_cash=53171998720,
            total_debt=12814000128,
            debt_to_equity=6.555,
            operating_cash_flow=125648003072,
            free_cash_flow=46335873024,
            price_to_book=24.876,
            fifty_two_week_high=236.54,
            fifty_two_week_low=164.07,
            fifty_day_average=206.17,
            two_hundred_day_average=193.11,
            sector="Technology",
            industry="Semiconductors",
        )

    def test_initialize_database_creates_stocks_table(self):
        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "stocks"),
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(table)

    def test_initialize_database_creates_historical_financials_table(self):
        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "historical_financials"),
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(table)

    def test_initialize_database_creates_historical_prices_table(self):
        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "historical_prices"),
            ).fetchone()
            state_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "historical_price_fetch_state"),
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(table)
        self.assertIsNotNone(state_table)

    def test_initialize_database_creates_research_universe_tables(self):
        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            universe_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "research_universes"),
            ).fetchone()
            symbol_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "research_universe_symbols"),
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(universe_table)
        self.assertIsNotNone(symbol_table)

    def test_save_and_read_stock_from_fresh_cache(self):
        save_stock(self.sample_stock(), self.db_path, fetched_at=self.now)

        stock = get_cached_stock("NVDA", self.db_path, now=self.now + timedelta(hours=1))

        self.assertIsNotNone(stock)
        self.assertEqual(stock.symbol, "NVDA")
        self.assertEqual(stock.company_name, "NVIDIA Corporation")
        self.assertEqual(stock.current_price, 200.75)
        self.assertEqual(stock.currency, "USD")
        self.assertEqual(stock.gross_margin, 0.741)
        self.assertEqual(stock.free_cash_flow, 46335873024)
        self.assertEqual(stock.fifty_two_week_high, 236.54)

    def test_expired_cache_returns_none(self):
        save_stock(self.sample_stock(), self.db_path, fetched_at=self.now)

        stock = get_cached_stock("NVDA", self.db_path, now=self.now + timedelta(hours=25))

        self.assertIsNone(stock)

    def test_update_existing_symbol_replaces_cached_values(self):
        save_stock(self.sample_stock(price=200.75), self.db_path, fetched_at=self.now)
        save_stock(self.sample_stock(price=210.5), self.db_path, fetched_at=self.now)

        stock = get_cached_stock("NVDA", self.db_path, now=self.now)

        self.assertEqual(stock.current_price, 210.5)

    def test_initialize_database_adds_new_columns_to_existing_table(self):
        self.create_old_stocks_table()

        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(stocks)").fetchall()
            }
        finally:
            connection.close()

        self.assertIn("gross_margin", columns)
        self.assertIn("free_cash_flow", columns)
        self.assertIn("fifty_two_week_high", columns)

    def test_old_schema_migration_expires_existing_cache_row(self):
        self.create_old_stocks_table()
        self.insert_old_cache_row(fetched_at=self.now.isoformat())

        stock = get_cached_stock("NVDA", self.db_path, now=self.now)

        self.assertIsNone(stock)

        connection = sqlite3.connect(self.db_path)
        try:
            row = connection.execute(
                "SELECT fetched_at FROM stocks WHERE symbol = ?",
                ("NVDA",),
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(row[0], SCHEMA_MIGRATION_EXPIRED_CACHE_TIMESTAMP)

    def test_initialize_database_does_not_invalidate_when_schema_is_current(self):
        save_stock(self.sample_stock(), self.db_path, fetched_at=self.now)

        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            row = connection.execute(
                "SELECT fetched_at FROM stocks WHERE symbol = ?",
                ("NVDA",),
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(row[0], self.now.isoformat())

    def test_repeated_migration_is_safe(self):
        self.create_old_stocks_table()
        self.insert_old_cache_row(fetched_at=self.now.isoformat())

        initialize_database(self.db_path)
        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(stocks)").fetchall()
            }
            row = connection.execute(
                "SELECT fetched_at FROM stocks WHERE symbol = ?",
                ("NVDA",),
            ).fetchone()
        finally:
            connection.close()

        self.assertIn("gross_margin", columns)
        self.assertEqual(row[0], SCHEMA_MIGRATION_EXPIRED_CACHE_TIMESTAMP)

    def test_save_and_read_historical_financials_from_fresh_cache(self):
        series = self.sample_historical_series()
        save_historical_financials(series, self.db_path, fetched_at=self.now)

        cached = get_cached_historical_financials(
            "NVDA",
            self.db_path,
            now=self.now + timedelta(days=1),
        )

        self.assertIsNotNone(cached)
        self.assertFalse(cached.is_stale)
        self.assertEqual(cached.currency, "USD")
        self.assertEqual([period.period_year for period in cached.periods], [2024, 2025])
        self.assertEqual(cached.periods[-1].revenue, 1200.0)
        self.assertEqual(cached.periods[-1].free_cash_flow, 220.0)

    def test_historical_financial_cache_uses_independent_seven_day_ttl(self):
        save_historical_financials(
            self.sample_historical_series(),
            self.db_path,
            fetched_at=self.now,
        )

        fresh_after_stock_ttl = get_cached_historical_financials(
            "NVDA",
            self.db_path,
            now=self.now + timedelta(days=6, hours=23),
        )
        expired = get_cached_historical_financials(
            "NVDA",
            self.db_path,
            now=self.now + HISTORICAL_CACHE_TTL,
        )

        self.assertIsNotNone(fresh_after_stock_ttl)
        self.assertIsNone(expired)

    def test_expired_historical_cache_can_be_returned_as_stale(self):
        save_historical_financials(
            self.sample_historical_series(),
            self.db_path,
            fetched_at=self.now,
        )

        stale = get_cached_historical_financials(
            "NVDA",
            self.db_path,
            now=self.now + timedelta(days=8),
            include_expired=True,
        )

        self.assertIsNotNone(stale)
        self.assertTrue(stale.is_stale)

    def test_historical_upsert_updates_same_symbol_and_period(self):
        save_historical_financials(
            self.sample_historical_series(revenue_2025=1200.0),
            self.db_path,
            fetched_at=self.now,
        )
        save_historical_financials(
            self.sample_historical_series(revenue_2025=1300.0),
            self.db_path,
            fetched_at=self.now,
        )

        cached = get_cached_historical_financials("NVDA", self.db_path, now=self.now)

        self.assertEqual(len(cached.periods), 2)
        self.assertEqual(cached.periods[-1].revenue, 1300.0)

    def test_historical_upsert_does_not_delete_omitted_old_period(self):
        save_historical_financials(
            self.sample_historical_series(revenue_2025=1200.0),
            self.db_path,
            fetched_at=self.now - timedelta(days=30),
        )
        save_historical_financials(
            HistoricalFinancialSeries(
                symbol="NVDA",
                currency="USD",
                periods=[
                    HistoricalFinancialPeriod(
                        symbol="NVDA",
                        period_end=datetime(2025, 1, 31, tzinfo=UTC).date(),
                        period_year=2025,
                        currency="USD",
                        revenue=1300.0,
                    )
                ],
            ),
            self.db_path,
            fetched_at=self.now,
        )

        cached = get_cached_historical_financials("NVDA", self.db_path, now=self.now)

        self.assertEqual([period.period_year for period in cached.periods], [2024, 2025])
        self.assertEqual(cached.periods[-1].revenue, 1300.0)

    def test_old_historical_table_migration_adds_period_year(self):
        self.create_old_historical_financials_table()

        initialize_database(self.db_path)

        cached = get_cached_historical_financials("NVDA", self.db_path, now=self.now)

        self.assertIsNotNone(cached)
        self.assertEqual(cached.periods[0].period_end.isoformat(), "2026-01-31")
        self.assertEqual(cached.periods[0].period_year, 2026)

    def test_stock_cache_unaffected_by_historical_table(self):
        save_stock(self.sample_stock(), self.db_path, fetched_at=self.now)
        save_historical_financials(
            self.sample_historical_series(),
            self.db_path,
            fetched_at=self.now - timedelta(days=8),
        )

        stock = get_cached_stock(
            "NVDA",
            self.db_path,
            now=self.now + timedelta(hours=1),
        )

        self.assertIsNotNone(stock)
        self.assertEqual(stock.current_price, 200.75)

    def test_save_and_read_historical_prices_from_fresh_cache(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )

        cached = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            now=self.now + timedelta(hours=1),
            require_full_history=True,
        )

        self.assertIsNotNone(cached)
        self.assertFalse(cached.is_stale)
        self.assertEqual(cached.currency, "USD")
        self.assertEqual([bar.trading_date.isoformat() for bar in cached.bars], ["2025-01-02", "2025-01-03"])
        self.assertEqual(cached.bars[-1].adjusted_close, 125.0)
        self.assertEqual(cached.bars[-1].volume, 1100)

    def test_historical_price_range_read_filters_at_database_boundary(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )

        cached = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            start=date(2025, 1, 3),
            end=date(2025, 1, 3),
            now=self.now,
        )

        self.assertEqual(len(cached.bars), 1)
        self.assertEqual(cached.bars[0].trading_date, date(2025, 1, 3))

    def test_historical_price_cache_uses_independent_twelve_hour_ttl(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )

        fresh = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            now=self.now + HISTORICAL_PRICE_CACHE_TTL - timedelta(seconds=1),
            require_full_history=True,
        )
        expired = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            now=self.now + HISTORICAL_PRICE_CACHE_TTL,
            require_full_history=True,
        )

        self.assertIsNotNone(fresh)
        self.assertIsNone(expired)

    def test_expired_historical_price_cache_can_be_returned_as_stale(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )

        stale = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            now=self.now + timedelta(hours=13),
            include_expired=True,
            require_full_history=True,
        )

        self.assertIsNotNone(stale)
        self.assertTrue(stale.is_stale)

    def test_historical_price_upsert_updates_same_symbol_and_date(self):
        save_historical_prices(
            self.sample_price_series(close_2025_01_03=125.0),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )
        save_historical_prices(
            self.sample_price_series(close_2025_01_03=130.0),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )

        cached = get_cached_historical_prices("NVDA", self.db_path, now=self.now)

        self.assertEqual(len(cached.bars), 2)
        self.assertEqual(cached.bars[-1].close, 130.0)

    def test_historical_price_upsert_does_not_delete_omitted_old_bar(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now - timedelta(hours=1),
            full_history_fetched=True,
        )
        save_historical_prices(
            HistoricalPriceSeries(
                symbol="NVDA",
                currency="USD",
                bars=(
                    HistoricalPriceBar(
                        symbol="NVDA",
                        trading_date=date(2025, 1, 3),
                        open=126.0,
                        high=132.0,
                        low=125.0,
                        close=130.0,
                        adjusted_close=130.0,
                        volume=1200,
                    ),
                ),
                fetched_at=self.now,
            ),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=False,
        )

        cached = get_cached_historical_prices("NVDA", self.db_path, now=self.now)

        self.assertEqual([bar.trading_date for bar in cached.bars], [date(2025, 1, 2), date(2025, 1, 3)])
        self.assertEqual(cached.bars[-1].close, 130.0)

    def test_partial_historical_price_refresh_does_not_make_older_coverage_fresh(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now - timedelta(hours=13),
            full_history_fetched=True,
        )
        save_historical_prices(
            HistoricalPriceSeries(
                symbol="NVDA",
                currency="USD",
                bars=(
                    HistoricalPriceBar(
                        symbol="NVDA",
                        trading_date=date(2025, 1, 3),
                        open=126.0,
                        high=132.0,
                        low=125.0,
                        close=130.0,
                        adjusted_close=130.0,
                        volume=1200,
                    ),
                ),
                fetched_at=self.now,
            ),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=False,
        )

        full_history_cache = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            now=self.now,
            require_full_history=True,
        )
        refreshed_day_cache = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            start=date(2025, 1, 3),
            end=date(2025, 1, 3),
            now=self.now,
        )

        self.assertIsNone(full_history_cache)
        self.assertIsNotNone(refreshed_day_cache)
        self.assertEqual(refreshed_day_cache.bars[0].close, 130.0)

    def test_historical_price_coverage_requires_explicit_start(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=False,
        )

        covered = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            start=date(2025, 1, 2),
            now=self.now,
        )
        not_covered = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            start=date(2024, 12, 31),
            now=self.now,
        )

        self.assertIsNotNone(covered)
        self.assertIsNone(not_covered)

    def test_historical_price_full_history_requires_fetch_state(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=False,
        )

        full_history_cache = get_cached_historical_prices(
            "NVDA",
            self.db_path,
            now=self.now,
            require_full_history=True,
        )

        self.assertIsNone(full_history_cache)

    def test_historical_price_fetch_state_and_latest_date_are_persisted(self):
        save_historical_prices(
            self.sample_price_series(),
            self.db_path,
            fetched_at=self.now,
            full_history_fetched=True,
        )

        state = get_historical_price_fetch_state("NVDA", self.db_path)
        latest = get_latest_historical_price_date("NVDA", self.db_path)

        self.assertTrue(state["full_history_fetched"])
        self.assertEqual(state["earliest_date"], date(2025, 1, 2))
        self.assertEqual(state["latest_date"], date(2025, 1, 3))
        self.assertEqual(latest, date(2025, 1, 3))

    def test_old_historical_price_table_migration_adds_missing_columns(self):
        self.create_old_historical_prices_table()

        initialize_database(self.db_path)

        connection = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(historical_prices)").fetchall()
            }
        finally:
            connection.close()

        self.assertIn("adjusted_close", columns)
        self.assertIn("stock_splits", columns)
        self.assertIn("currency", columns)

    def insert_old_cache_row(self, fetched_at: str) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
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
                """,
                (
                    "NVDA",
                    "NVIDIA Corporation",
                    200.75,
                    "USD",
                    4879000000000,
                    57.68,
                    44.3,
                    3.48,
                    0.25,
                    "Technology",
                    "Semiconductors",
                    fetched_at,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def create_old_stocks_table(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE stocks (
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
            )
            connection.commit()
        finally:
            connection.close()

    def create_old_historical_financials_table(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE historical_financials (
                    symbol TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    fiscal_year INTEGER,
                    currency TEXT,
                    revenue REAL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY(symbol, period_end)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO historical_financials (
                    symbol,
                    period_end,
                    fiscal_year,
                    currency,
                    revenue,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "NVDA",
                    "2026-01-31",
                    2026,
                    "USD",
                    100.0,
                    self.now.isoformat(),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def create_old_historical_prices_table(self):
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE historical_prices (
                    symbol TEXT NOT NULL,
                    trading_date TEXT NOT NULL,
                    open REAL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY(symbol, trading_date)
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def sample_historical_series(self, revenue_2025=1200.0):
        return HistoricalFinancialSeries(
            symbol="NVDA",
            currency="USD",
            periods=[
                HistoricalFinancialPeriod(
                    symbol="NVDA",
                    period_end=datetime(2024, 1, 31, tzinfo=UTC).date(),
                    period_year=2024,
                    currency="USD",
                    revenue=1000.0,
                    net_income=180.0,
                    free_cash_flow=150.0,
                    total_debt=450.0,
                ),
                HistoricalFinancialPeriod(
                    symbol="NVDA",
                    period_end=datetime(2025, 1, 31, tzinfo=UTC).date(),
                    period_year=2025,
                    currency="USD",
                    revenue=revenue_2025,
                    net_income=240.0,
                    free_cash_flow=220.0,
                    total_debt=500.0,
                ),
            ],
        )

    def sample_price_series(self, close_2025_01_03=125.0):
        return HistoricalPriceSeries(
            symbol="NVDA",
            currency="USD",
            bars=(
                HistoricalPriceBar(
                    symbol="NVDA",
                    trading_date=date(2025, 1, 2),
                    open=100.0,
                    high=110.0,
                    low=95.0,
                    close=105.0,
                    adjusted_close=104.5,
                    volume=1000,
                    dividends=0.0,
                    stock_splits=0.0,
                ),
                HistoricalPriceBar(
                    symbol="NVDA",
                    trading_date=date(2025, 1, 3),
                    open=120.0,
                    high=130.0,
                    low=115.0,
                    close=close_2025_01_03,
                    adjusted_close=close_2025_01_03,
                    volume=1100,
                    dividends=0.0,
                    stock_splits=0.0,
                ),
            ),
            fetched_at=self.now,
        )


if __name__ == "__main__":
    unittest.main()
