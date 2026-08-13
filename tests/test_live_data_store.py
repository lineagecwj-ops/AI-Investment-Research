import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import UTC
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database_config import DEFAULT_DATABASE_PATH_CONFIG
from live_data_store import LiveDataStore
from live_data_store import LiveDataStoreError
from live_data_store import PRODUCTION_DB_TEST_ALLOW_ENV
from live_data_store import PRODUCTION_DB_TEST_GUARD_ENV
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import Stock
from research_data_store import ResearchDataStore


class LiveDataStoreTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.now = datetime.now(UTC)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_initialization_uses_formal_live_store_path(self):
        store = LiveDataStore()

        self.assertEqual(store.resolved_db_path, DEFAULT_DATABASE_PATH_CONFIG.live_db_path.resolve())
        self.assertTrue(store.mutable)

    def test_explicit_legacy_path_remains_available_for_rollback(self):
        store = LiveDataStore(db_path=DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path)

        self.assertEqual(store.resolved_db_path, DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path.resolve())

    def test_connect_writable_resolves_configured_path(self):
        store = LiveDataStore(db_path=self.db_path)
        connection = store.connect_writable()
        try:
            connection.execute("CREATE TABLE live_store_write_check (id INTEGER)")
            connection.commit()
        finally:
            connection.close()

        self.assertTrue(self.db_path.exists())

    def test_production_db_path_is_blocked_in_tests(self):
        store = LiveDataStore(db_path=DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path)

        with patch.dict(
            "os.environ",
            {PRODUCTION_DB_TEST_GUARD_ENV: "1", PRODUCTION_DB_TEST_ALLOW_ENV: ""},
            clear=False,
        ):
            with self.assertRaisesRegex(LiveDataStoreError, "production data/stocks.db"):
                store.connect_writable()

    def test_live_store_test_guard_allows_temp_db_path(self):
        store = LiveDataStore(db_path=self.db_path)

        with patch.dict("os.environ", {PRODUCTION_DB_TEST_GUARD_ENV: "1"}, clear=False):
            connection = store.connect_writable()
            connection.close()

        self.assertTrue(self.db_path.exists())

    def test_historical_price_save_updates_fetch_state_through_live_store(self):
        store = LiveDataStore(db_path=self.db_path)
        series = HistoricalPriceSeries(
            symbol="1111.TW",
            currency="TWD",
            bars=(
                HistoricalPriceBar(
                    symbol="1111.TW",
                    trading_date=self.now.date(),
                    open=10.0,
                    high=11.0,
                    low=9.0,
                    close=10.5,
                    adjusted_close=10.4,
                    volume=1000,
                    dividends=0.0,
                    stock_splits=0.0,
                ),
            ),
            fetched_at=self.now,
        )

        store.save_historical_prices(series, fetched_at=self.now, full_history_fetched=True)
        state = store.get_historical_price_fetch_state("1111.TW")
        cached = store.get_cached_historical_prices("1111.TW", require_full_history=True)

        self.assertIsNotNone(state)
        self.assertTrue(state["full_history_fetched"])
        self.assertEqual(cached.symbol, "1111.TW")
        self.assertEqual(cached.bars[0].adjusted_close, 10.4)

    def test_stock_save_and_read_use_live_store(self):
        store = LiveDataStore(db_path=self.db_path)
        stock = Stock(
            symbol="NVDA",
            company_name="NVIDIA Corporation",
            current_price=200.0,
            currency="USD",
        )

        store.save_stock(stock, fetched_at=self.now)
        cached = store.get_cached_stock("NVDA")

        self.assertIsNotNone(cached)
        self.assertEqual(cached.current_price, 200.0)

    def test_live_store_rejects_research_snapshot_path(self):
        store = LiveDataStore(db_path=DEFAULT_DATABASE_PATH_CONFIG.research_db_path)

        with self.assertRaises(LiveDataStoreError):
            store.connect_writable()

    def test_research_data_store_cannot_write(self):
        live_store = LiveDataStore(db_path=self.db_path)
        live_store.initialize()
        research_store = ResearchDataStore(db_path=self.db_path)
        connection = research_store.connect_read_only()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE should_not_write (id INTEGER)")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
