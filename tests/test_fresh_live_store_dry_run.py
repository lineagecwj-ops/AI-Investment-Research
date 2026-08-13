import hashlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import initialize_database
from database_config import DatabasePathConfig
from database_config import DEFAULT_DATABASE_PATH_CONFIG
from historical_price_service import get_historical_prices
from live_data_store import LiveDataStore
from live_data_store import LiveDataStoreError
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from research_data_store import DEFAULT_RESEARCH_SNAPSHOT_ID
from research_data_store import ResearchDataStore
from swing_scanner_service import SwingScannerService
from swing_scanner_service import live_data_store_price_loader


PRODUCTION_DB_PATH = PROJECT_ROOT / "data" / "stocks.db"


def _production_fingerprint():
    digest = hashlib.sha256(PRODUCTION_DB_PATH.read_bytes()).hexdigest()
    connection = sqlite3.connect(PRODUCTION_DB_PATH.as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0]
        symbols = connection.execute("SELECT COUNT(DISTINCT symbol) FROM historical_prices").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return digest, rows, symbols, integrity


def _mock_price_series(symbol="3333.TW"):
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    return HistoricalPriceSeries(
        symbol=symbol,
        currency="TWD",
        bars=(
            HistoricalPriceBar(
                symbol=symbol,
                trading_date=date(2026, 8, 12),
                open=30.0,
                high=31.0,
                low=29.0,
                close=30.5,
                adjusted_close=30.5,
                volume=3000,
                dividends=0.0,
                stock_splits=0.0,
            ),
        ),
        fetched_at=now,
    )


class FreshLiveStoreDryRunTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir="/tmp")
        self.root = Path(self.temp_dir.name)
        self.live_dir = self.root / "live_store_dry_run_phase6d4b1"
        self.live_path = self.live_dir / "stocks_live.dry_run.db"
        self.live_dir.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_temp_live_creation_uses_live_schema_without_snapshot_metadata(self):
        initialize_database(self.live_path)
        connection = sqlite3.connect(self.live_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            connection.close()

        self.assertIn("historical_prices", tables)
        self.assertIn("historical_price_fetch_state", tables)
        self.assertIn("stocks", tables)
        self.assertIn("historical_financials", tables)
        self.assertNotIn("snapshot_metadata", tables)
        self.assertNotIn("research_snapshot_manifest", tables)
        self.assertFalse(str(self.live_path).startswith(str(PROJECT_ROOT / "data")))

    def test_live_data_store_write_and_fetch_state_are_isolated_to_temp_db(self):
        initialize_database(self.live_path)
        store = LiveDataStore(db_path=self.live_path)
        before = _production_fingerprint()
        series = _mock_price_series("3333.TW")

        store.save_historical_prices(series, fetched_at=series.fetched_at, full_history_fetched=True)
        cached = store.get_cached_historical_prices("3333.TW", require_full_history=True, now=series.fetched_at)
        state = store.get_historical_price_fetch_state("3333.TW")

        after = _production_fingerprint()
        self.assertEqual(after, before)
        self.assertEqual(cached.symbol, "3333.TW")
        self.assertEqual(state["latest_date"], date(2026, 8, 12))

    def test_mock_provider_refresh_writes_only_temp_live_db(self):
        initialize_database(self.live_path)
        store = LiveDataStore(db_path=self.live_path)
        before = _production_fingerprint()
        series = _mock_price_series("4444.TW")

        with patch("historical_price_service.fetch_historical_prices_from_yahoo", return_value=series):
            loaded = get_historical_prices("4444.TW", force_refresh=True, live_store=store)

        after = _production_fingerprint()
        self.assertEqual(after, before)
        self.assertEqual(loaded.symbol, "4444.TW")
        self.assertEqual(store.get_historical_price_fetch_state("4444.TW")["latest_date"], date(2026, 8, 12))

    def test_scanner_compatibility_uses_injected_temp_live_store(self):
        initialize_database(self.live_path)
        store = LiveDataStore(db_path=self.live_path)
        series = _mock_price_series("5555.TW")
        store.save_historical_prices(series, fetched_at=series.fetched_at, full_history_fetched=True)

        service = SwingScannerService(
            live_data_store=store,
            price_loader=live_data_store_price_loader(store),
        )
        loaded = service.price_loader("5555.TW")

        self.assertIs(service.live_data_store, store)
        self.assertEqual(loaded.symbol, "5555.TW")

    def test_research_live_boundary_and_config_dry_run(self):
        initialize_database(self.live_path)
        config = DatabasePathConfig(
            project_root=self.root,
            legacy_db_path=self.root / "data" / "stocks.db",
            research_db_path=DEFAULT_DATABASE_PATH_CONFIG.research_db_path,
            live_db_path=self.live_path,
        )

        with self.assertRaises(LiveDataStoreError):
            LiveDataStore(db_path=config.research_db_path).connect_writable()

        research_store = ResearchDataStore(db_path=self.live_path)
        connection = research_store.connect_read_only()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE should_not_write (id INTEGER)")
        finally:
            connection.close()

        self.assertEqual(config.live_db_path, self.live_path)
        self.assertEqual(DEFAULT_RESEARCH_SNAPSHOT_ID, "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1")


if __name__ == "__main__":
    unittest.main()
