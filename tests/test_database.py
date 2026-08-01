import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import get_cached_stock
from database import initialize_database
from database import save_stock
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

    def test_save_and_read_stock_from_fresh_cache(self):
        save_stock(self.sample_stock(), self.db_path, fetched_at=self.now)

        stock = get_cached_stock("NVDA", self.db_path, now=self.now + timedelta(hours=1))

        self.assertIsNotNone(stock)
        self.assertEqual(stock.symbol, "NVDA")
        self.assertEqual(stock.company_name, "NVIDIA Corporation")
        self.assertEqual(stock.current_price, 200.75)
        self.assertEqual(stock.currency, "USD")

    def test_expired_cache_returns_none(self):
        save_stock(self.sample_stock(), self.db_path, fetched_at=self.now)

        stock = get_cached_stock("NVDA", self.db_path, now=self.now + timedelta(hours=25))

        self.assertIsNone(stock)

    def test_update_existing_symbol_replaces_cached_values(self):
        save_stock(self.sample_stock(price=200.75), self.db_path, fetched_at=self.now)
        save_stock(self.sample_stock(price=210.5), self.db_path, fetched_at=self.now)

        stock = get_cached_stock("NVDA", self.db_path, now=self.now)

        self.assertEqual(stock.current_price, 210.5)


if __name__ == "__main__":
    unittest.main()
