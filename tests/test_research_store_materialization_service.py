import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
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
from research_data_store import ResearchDataStore
from research_store_materialization_service import EXPECTED_SEMANTIC_CHECKSUM
from research_store_materialization_service import SNAPSHOT_ID
from research_store_materialization_service import _build_research_database
from research_store_materialization_service import materialize_research_store_candidate
from research_store_materialization_service import validate_research_store_candidate


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


class ResearchStoreMaterializationServiceTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.result = materialize_research_store_candidate(
            output_root=Path(cls.temp_dir.name) / "research",
            materialized_at=datetime(2026, 8, 12, tzinfo=UTC),
        )

    @classmethod
    def tearDownClass(cls):
        cls.result.db_path.chmod(0o644)
        cls.temp_dir.cleanup()

    def test_materializes_full_research_store_candidate(self):
        self.assertTrue(self.result.db_path.exists())
        self.assertTrue(self.result.manifest_path.exists())
        self.assertEqual(self.result.row_count, 473481)
        self.assertEqual(self.result.symbol_count, 222)
        self.assertEqual(self.result.duplicate_count, 0)
        self.assertEqual(self.result.integrity_check, "ok")
        self.assertEqual(self.result.min_trading_date, "1980-12-12")
        self.assertEqual(self.result.max_trading_date, "2026-08-07")
        self.assertEqual(self.result.excluded_tables_present, tuple())

    def test_manifest_validation_records_released_snapshot_identity(self):
        payload = json.loads(self.result.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["identity"]["snapshot_id"], SNAPSHOT_ID)
        self.assertEqual(payload["identity"]["status"], "RELEASED")
        self.assertEqual(payload["identity"]["materialized_status"], "RESEARCH_STORE_CANDIDATE")
        self.assertEqual(payload["semantic_checksum"]["expected"], EXPECTED_SEMANTIC_CHECKSUM)
        self.assertEqual(payload["semantic_checksum"]["materialized"], EXPECTED_SEMANTIC_CHECKSUM)
        self.assertEqual(payload["semantic_checksum"]["result"], "MATCH")
        self.assertIn("historical_prices", payload["datasets"]["included"])
        self.assertIn("historical_price_fetch_state", payload["datasets"]["excluded"])

    def test_research_data_store_reads_candidate_with_query_only(self):
        store = ResearchDataStore(db_path=self.result.db_path, manifest_path=self.result.manifest_path)
        manifest = store.verify_manifest_reference()
        connection = store.connect_read_only()
        try:
            query_only = connection.execute("PRAGMA query_only").fetchone()[0]
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE should_not_write (id INTEGER)")
        finally:
            connection.close()

        symbols = store.materialized_twse_common_stock_symbols()
        self.assertEqual(manifest["identity"]["snapshot_id"], SNAPSHOT_ID)
        self.assertEqual(query_only, 1)
        self.assertEqual(len(symbols), 218)

    def test_live_research_boundary_and_excluded_tables(self):
        with self.assertRaises(LiveDataStoreError):
            LiveDataStore(db_path=DEFAULT_DATABASE_PATH_CONFIG.research_db_path).connect_writable()
        corrected_candidate_path = DEFAULT_DATABASE_PATH_CONFIG.research_db_path.with_name(
            f"{SNAPSHOT_ID}_materialization_v2.db"
        )
        with self.assertRaises(LiveDataStoreError):
            LiveDataStore(db_path=corrected_candidate_path).connect_writable()

        validation = validate_research_store_candidate(self.result.db_path)
        self.assertEqual(validation["excluded_tables_present"], tuple())

    def test_production_db_untouched_by_temp_materialization_validation(self):
        before = _production_fingerprint()

        validate_research_store_candidate(self.result.db_path)

        after = _production_fingerprint()
        self.assertEqual(after, before)

    def test_adjusted_close_recovery_is_correlated_by_symbol_and_trading_date(self):
        root = Path(self.temp_dir.name) / "adjusted_close_regression"
        root.mkdir(parents=True, exist_ok=True)
        base_path = root / "base.db"
        recovery_path = root / "recovery.db"
        output_path = root / "candidate.db"
        source_manifest_path = root / "source_manifest.json"
        rows = (
            ("2330.TW", "2026-08-06", 10.0, 11.0, 9.0, 10.5, 10.5, 100),
            ("2330.TW", "2026-08-07", 20.0, 22.0, 19.0, 21.0, 21.0, 200),
            ("2337.TW", "2026-08-06", 30.0, 33.0, 29.0, 32.0, 32.0, 300),
            ("2337.TW", "2026-08-07", 40.0, 44.0, 39.0, 43.0, 43.0, 400),
        )
        recovery_adjusted = {
            ("2330.TW", "2026-08-06"): 100.1,
            ("2330.TW", "2026-08-07"): 100.2,
            ("2337.TW", "2026-08-06"): 200.1,
            ("2337.TW", "2026-08-07"): 200.2,
        }
        self._create_recovery_regression_db(base_path, rows, {})
        self._create_recovery_regression_db(recovery_path, rows, recovery_adjusted)
        source_manifest_path.write_text("{}", encoding="utf-8")

        _build_research_database(
            db_path=output_path,
            source_manifest_path=source_manifest_path,
            base_backup_path=base_path,
            recovery_source_path=recovery_path,
            materialized_at=datetime(2026, 8, 13, tzinfo=UTC),
            semantic_checksum=EXPECTED_SEMANTIC_CHECKSUM,
            materialization_version="regression",
        )

        connection = sqlite3.connect(output_path)
        try:
            materialized = {
                (row[0], row[1]): row
                for row in connection.execute(
                    """
                    SELECT symbol, trading_date, open, high, low, close, adjusted_close, volume
                    FROM historical_prices
                    ORDER BY symbol, trading_date
                    """
                ).fetchall()
            }
        finally:
            connection.close()

        for row in rows:
            key = (row[0], row[1])
            materialized_row = materialized[key]
            self.assertEqual(materialized_row[2], row[2])
            self.assertEqual(materialized_row[3], row[3])
            self.assertEqual(materialized_row[4], row[4])
            self.assertEqual(materialized_row[5], row[5])
            self.assertEqual(materialized_row[6], recovery_adjusted[key])
            self.assertEqual(materialized_row[7], row[7])

    def _create_recovery_regression_db(self, db_path, rows, adjusted_by_key):
        connection = sqlite3.connect(db_path)
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
            connection.execute(
                """
                CREATE TABLE research_universes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE research_universe_symbols (
                    universe_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    PRIMARY KEY(universe_id, symbol)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO research_universes (id, name, description, created_at, updated_at)
                VALUES ('u', 'u', NULL, '2026-08-13T00:00:00+00:00', '2026-08-13T00:00:00+00:00')
                """
            )
            for position, symbol in enumerate(("2330.TW", "2337.TW"), start=1):
                connection.execute(
                    "INSERT INTO research_universe_symbols (universe_id, position, symbol) VALUES ('u', ?, ?)",
                    (position, symbol),
                )
            for row in rows:
                adjusted_close = adjusted_by_key.get((row[0], row[1]), row[6])
                connection.execute(
                    """
                    INSERT INTO historical_prices (
                        symbol, trading_date, open, high, low, close, adjusted_close,
                        volume, dividends, stock_splits, currency, fetched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'TWD', '2026-08-13T00:00:00+00:00')
                    """,
                    (*row[:6], adjusted_close, row[7]),
                )
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
