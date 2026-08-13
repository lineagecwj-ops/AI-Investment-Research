import hashlib
import json
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

from database import initialize_database
from database_config import DatabasePathConfig
from live_data_store import LiveDataStore
from live_data_store import LiveDataStoreError
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from research_data_store import DEFAULT_RESEARCH_SNAPSHOT_ID
from research_data_store import ResearchDataStore


MANIFEST_PATH = (
    PROJECT_ROOT
    / "docs"
    / "research_snapshots"
    / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json"
)
ACTIVE_RESEARCH_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "snapshots"
    / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_v2.db"
)
PRODUCTION_DB_PATH = PROJECT_ROOT / "data" / "stocks.db"
EXPECTED_SEMANTIC_CHECKSUM = "a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91"


def _production_db_fingerprint():
    digest = hashlib.sha256(PRODUCTION_DB_PATH.read_bytes()).hexdigest()
    connection = sqlite3.connect(PRODUCTION_DB_PATH.as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0]
        symbols = connection.execute("SELECT COUNT(DISTINCT symbol) FROM historical_prices").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return digest, rows, symbols, integrity


def _create_research_dry_run_store(db_path: Path):
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE snapshot_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE historical_prices (
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
        )
        connection.executemany(
            "INSERT INTO snapshot_metadata (key, value) VALUES (?, ?)",
            (
                ("snapshot_id", DEFAULT_RESEARCH_SNAPSHOT_ID),
                ("manifest_path", str(MANIFEST_PATH)),
                ("dataset_scope", "phase_6d2_dry_run_minimal_research_price_data"),
            ),
        )
        connection.execute(
            """
            INSERT INTO historical_prices (
                symbol, trading_date, open, high, low, close, adjusted_close,
                volume, dividends, stock_splits, currency, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "1111.TW",
                "2025-12-31",
                10.0,
                11.0,
                9.0,
                10.5,
                10.4,
                1000,
                0.0,
                0.0,
                "TWD",
                "2026-08-11T18:05:13+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()


class PhysicalStoreDryRunTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir="/tmp")
        self.root = Path(self.temp_dir.name)
        self.research_path = self.root / "research_store_dry_run" / "research_snapshot.db"
        self.live_path = self.root / "live_store_dry_run" / "stocks_live.db"
        self.research_path.parent.mkdir(parents=True)
        self.live_path.parent.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_research_store_temp_creation_and_read_only_access(self):
        _create_research_dry_run_store(self.research_path)
        store = ResearchDataStore(db_path=self.research_path, manifest_path=MANIFEST_PATH)

        manifest = store.verify_manifest_reference()
        connection = store.connect_read_only()
        try:
            query_only = connection.execute("PRAGMA query_only").fetchone()[0]
            metadata_snapshot_id = connection.execute(
                "SELECT value FROM snapshot_metadata WHERE key = 'snapshot_id'"
            ).fetchone()[0]
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE should_not_write (id INTEGER)")
        finally:
            connection.close()

        series = store.load_historical_price_series("1111.TW")
        self.assertEqual(query_only, 1)
        self.assertEqual(metadata_snapshot_id, DEFAULT_RESEARCH_SNAPSHOT_ID)
        self.assertEqual(manifest["identity"]["snapshot_id"], DEFAULT_RESEARCH_SNAPSHOT_ID)
        self.assertEqual(manifest["validation"]["semantic_checksum"], EXPECTED_SEMANTIC_CHECKSUM)
        self.assertEqual(series.symbol, "1111.TW")
        self.assertEqual(series.bars[0].trading_date, date(2025, 12, 31))

    def test_live_store_temp_creation_and_write_isolation(self):
        initialize_database(self.live_path)
        store = LiveDataStore(db_path=self.live_path)
        now = datetime(2026, 8, 12, tzinfo=UTC)
        series = HistoricalPriceSeries(
            symbol="2222.TW",
            currency="TWD",
            bars=(
                HistoricalPriceBar(
                    symbol="2222.TW",
                    trading_date=now.date(),
                    open=20.0,
                    high=21.0,
                    low=19.0,
                    close=20.5,
                    adjusted_close=20.5,
                    volume=2000,
                    dividends=0.0,
                    stock_splits=0.0,
                ),
            ),
            fetched_at=now,
        )

        store.save_historical_prices(series, fetched_at=now, full_history_fetched=True)
        cached = store.get_cached_historical_prices("2222.TW", require_full_history=True, now=now)
        state = store.get_historical_price_fetch_state("2222.TW")

        self.assertEqual(cached.symbol, "2222.TW")
        self.assertEqual(state["latest_date"], now.date())
        self.assertFalse(str(self.live_path).startswith(str(PROJECT_ROOT / "data")))

    def test_boundary_and_config_dry_run(self):
        config = DatabasePathConfig.default(project_root=self.root)

        self.assertEqual(config.research_db_path, self.root / "data" / "research" / "snapshots" / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_v2.db")
        self.assertEqual(config.live_db_path, self.root / "data" / "live" / "stocks_live.db")
        with self.assertRaises(LiveDataStoreError):
            LiveDataStore(db_path=ACTIVE_RESEARCH_DB_PATH).connect_writable()

    def test_no_production_db_mutation(self):
        before = _production_db_fingerprint()

        _create_research_dry_run_store(self.research_path)
        initialize_database(self.live_path)

        after = _production_db_fingerprint()
        self.assertEqual(after, before)

    def test_manifest_dataset_scope_excludes_live_tables(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertIn("historical_prices", manifest["datasets"]["included_datasets"])
        self.assertIn("historical_price_fetch_state", manifest["datasets"]["excluded_datasets"])
        self.assertIn("stocks", manifest["datasets"]["excluded_datasets"])
        self.assertIn("historical_financials", manifest["datasets"]["excluded_datasets"])


if __name__ == "__main__":
    unittest.main()
