import hashlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from formal_live_store_creation_service import FORBIDDEN_LIVE_TABLES
from formal_live_store_creation_service import LIVE_TABLES
from formal_live_store_creation_service import FormalLiveStoreCreationError
from formal_live_store_creation_service import create_fresh_live_store
from formal_live_store_creation_service import validate_live_store_schema
from database_config import DEFAULT_DATABASE_PATH_CONFIG
from live_data_store import LiveDataStore
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from research_data_store import ResearchDataStore
from research_data_store import ResearchDataStoreError


PRODUCTION_DB_PATH = PROJECT_ROOT / "data" / "stocks.db"


def _production_fingerprint():
    digest = hashlib.sha256(PRODUCTION_DB_PATH.read_bytes()).hexdigest()
    connection = sqlite3.connect(PRODUCTION_DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0]
        symbols = connection.execute("SELECT COUNT(DISTINCT symbol) FROM historical_prices").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return digest, rows, symbols, integrity


class FormalLiveStoreCreationServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.live_path = Path(self.temp_dir.name) / "live" / "stocks_live.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_live_db_creation_uses_empty_live_only_schema(self):
        result = create_fresh_live_store(self.live_path)

        self.assertTrue(self.live_path.exists())
        self.assertEqual(set(result.tables), set(LIVE_TABLES))
        self.assertEqual(result.forbidden_tables_present, tuple())
        self.assertEqual(result.historical_prices_rows, 0)
        self.assertEqual(result.fetch_state_rows, 0)
        self.assertEqual(result.stocks_rows, 0)
        self.assertEqual(result.historical_financials_rows, 0)
        self.assertEqual(result.integrity_check, "ok")

    def test_existing_live_db_is_not_overwritten_by_default(self):
        create_fresh_live_store(self.live_path)

        with self.assertRaises(FormalLiveStoreCreationError):
            create_fresh_live_store(self.live_path)

    def test_live_data_store_write_and_fetch_state_are_isolated(self):
        create_fresh_live_store(self.live_path)
        store = LiveDataStore(db_path=self.live_path)
        before = _production_fingerprint()
        now = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
        first = self.price_series(close=50.5, adjusted_close=50.5, fetched_at=now)
        second = self.price_series(close=51.5, adjusted_close=51.5, fetched_at=now)

        store.save_historical_prices(first, fetched_at=now, full_history_fetched=True)
        store.save_historical_prices(second, fetched_at=now, full_history_fetched=True)
        cached = store.get_cached_historical_prices("LIVE_VALIDATION.TW", require_full_history=True)
        state = store.get_historical_price_fetch_state("LIVE_VALIDATION.TW")

        after = _production_fingerprint()
        self.assertEqual(after, before)
        self.assertEqual(cached.bars[0].close, 51.5)
        self.assertEqual(state["latest_date"], date(2026, 8, 12))
        validation = validate_live_store_schema(self.live_path)
        self.assertEqual(validation.historical_prices_rows, 1)
        self.assertEqual(validation.fetch_state_rows, 1)

    def test_research_data_store_rejects_live_db_and_cannot_write_research_snapshot(self):
        create_fresh_live_store(self.live_path)
        with self.assertRaisesRegex(ResearchDataStoreError, "Live Store"):
            ResearchDataStore(db_path=DEFAULT_DATABASE_PATH_CONFIG.live_db_path).connect_read_only()

        faulty_research_path = PROJECT_ROOT / "data" / "research" / "snapshots" / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db"
        store = ResearchDataStore(db_path=faulty_research_path)
        connection = store.connect_read_only()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE should_not_write (id INTEGER)")
        finally:
            connection.close()

    def test_production_db_unchanged_by_live_creation_and_validation(self):
        before = _production_fingerprint()

        create_fresh_live_store(self.live_path)
        validate_live_store_schema(self.live_path)

        after = _production_fingerprint()
        self.assertEqual(after, before)

    def test_forbidden_research_tables_are_not_created(self):
        create_fresh_live_store(self.live_path)
        connection = sqlite3.connect(self.live_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            connection.close()

        for table in FORBIDDEN_LIVE_TABLES:
            self.assertNotIn(table, tables)

    def price_series(self, *, close, adjusted_close, fetched_at):
        return HistoricalPriceSeries(
            symbol="LIVE_VALIDATION.TW",
            currency="TWD",
            bars=(
                HistoricalPriceBar(
                    symbol="LIVE_VALIDATION.TW",
                    trading_date=date(2026, 8, 12),
                    open=50.0,
                    high=52.0,
                    low=49.0,
                    close=close,
                    adjusted_close=adjusted_close,
                    volume=5000,
                    dividends=0.0,
                    stock_splits=0.0,
                ),
            ),
            fetched_at=fetched_at,
        )


if __name__ == "__main__":
    unittest.main()
