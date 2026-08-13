import sqlite3
import sys
import tempfile
import unittest
import json
from datetime import UTC
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import initialize_database
from database import save_historical_prices
from database_config import DEFAULT_RESEARCH_DB_SHA256
from database_config import DEFAULT_RESEARCH_MATERIALIZATION_VERSION
from database_config import DEFAULT_RESEARCH_SEMANTIC_CHECKSUM
from database_config import DEFAULT_DATABASE_PATH_CONFIG
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from research_data_store import DEFAULT_RESEARCH_SNAPSHOT_ID
from research_data_store import ResearchDataStore
from research_data_store import ResearchDataStoreError
from expanded_volume_threshold_validation_service import load_historical_price_series_read_only
from scanner_condition_coverage_outcome_research_service import database_safety_audit


class ResearchDataStoreTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        initialize_database(self.db_path)
        now = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
        series = HistoricalPriceSeries(
            symbol="1111.TW",
            currency="TWD",
            bars=(
                HistoricalPriceBar(
                    symbol="1111.TW",
                    trading_date=now.date(),
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
            fetched_at=now,
        )
        save_historical_prices(series, db_path=self.db_path, fetched_at=now, full_history_fetched=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_initialization_resolves_released_research_store(self):
        store = ResearchDataStore()

        self.assertEqual(store.resolved_research_snapshot_id, DEFAULT_RESEARCH_SNAPSHOT_ID)
        self.assertEqual(store.resolved_research_snapshot_version, "v1")
        self.assertEqual(store.resolved_materialization_version, "v2")
        self.assertEqual(store.resolved_db_path, DEFAULT_DATABASE_PATH_CONFIG.research_db_path.resolve())
        self.assertEqual(store.resolved_manifest_path, DEFAULT_DATABASE_PATH_CONFIG.manifest_path.resolve())
        self.assertTrue(store.resolved_db_path.name.endswith("_materialization_v2.db"))
        self.assertTrue(store.resolved_manifest_path.name.endswith("_materialization_v2_manifest.json"))
        self.assertNotEqual(store.resolved_db_path, DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path.resolve())
        self.assertNotEqual(store.resolved_db_path, DEFAULT_DATABASE_PATH_CONFIG.live_db_path.resolve())

    def test_default_runtime_identity_verifies_corrected_materialization(self):
        store = ResearchDataStore()

        identity = store.verify_runtime_identity()

        self.assertEqual(identity["active_db_mode"], "physical_split")
        self.assertTrue(identity["active_research_db_path"].endswith("_materialization_v2.db"))
        self.assertEqual(identity["active_research_snapshot_id"], DEFAULT_RESEARCH_SNAPSHOT_ID)
        self.assertEqual(identity["active_research_snapshot_version"], "v1")
        self.assertEqual(identity["active_research_materialization_version"], DEFAULT_RESEARCH_MATERIALIZATION_VERSION)
        self.assertEqual(identity["active_research_semantic_checksum"], DEFAULT_RESEARCH_SEMANTIC_CHECKSUM)
        self.assertEqual(identity["active_research_db_sha"], DEFAULT_RESEARCH_DB_SHA256)

    def test_read_only_connection_enforces_query_only(self):
        store = ResearchDataStore(db_path=self.db_path)
        connection = store.connect_read_only()
        try:
            query_only = connection.execute("PRAGMA query_only").fetchone()[0]
            self.assertEqual(query_only, 1)
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE should_not_write (id INTEGER)")
        finally:
            connection.close()

    def test_research_data_store_rejects_formal_live_store_path(self):
        store = ResearchDataStore(db_path=DEFAULT_DATABASE_PATH_CONFIG.live_db_path)

        with self.assertRaisesRegex(ResearchDataStoreError, "Live Store"):
            store.connect_read_only()

    def test_research_data_store_rejects_legacy_store_path(self):
        store = ResearchDataStore(db_path=DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path)

        with self.assertRaisesRegex(ResearchDataStoreError, "Legacy Store"):
            store.connect_read_only()

    def test_load_historical_price_series_reads_through_store(self):
        store = ResearchDataStore(db_path=self.db_path)

        series = store.load_historical_price_series("1111.TW")

        self.assertEqual(series.symbol, "1111.TW")
        self.assertEqual(len(series.bars), 1)
        self.assertEqual(series.bars[0].trading_date.isoformat(), "2026-08-01")
        self.assertEqual(series.bars[0].adjusted_close, 10.4)

    def test_materialized_twse_common_stock_symbols_reads_through_store(self):
        store = ResearchDataStore(db_path=self.db_path)

        self.assertEqual(store.materialized_twse_common_stock_symbols(), ("1111.TW",))

    def test_research_services_can_resolve_through_store(self):
        store = ResearchDataStore(db_path=self.db_path)

        series = load_historical_price_series_read_only(
            "1111.TW",
            db_path=self.db_path,
            research_store=store,
        )
        audit = database_safety_audit(self.db_path, research_store=store)

        self.assertEqual(series.symbol, "1111.TW")
        self.assertEqual(audit.row_count, 1)
        self.assertEqual(audit.symbol_count, 1)
        self.assertEqual(audit.integrity_check, "ok")

    def test_missing_manifest_reference_fails_deterministically(self):
        store = ResearchDataStore(db_path=self.db_path, manifest_path=Path(self.temp_dir.name) / "missing.json")

        with self.assertRaises(ResearchDataStoreError):
            store.verify_manifest_reference()

    def test_faulty_physical_store_fails_active_runtime_verification(self):
        faulty_path = DEFAULT_DATABASE_PATH_CONFIG.research_db_path.with_name(
            "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db"
        )
        store = ResearchDataStore(db_path=faulty_path)

        with self.assertRaisesRegex(ResearchDataStoreError, "metadata materialization_version mismatch"):
            store.verify_runtime_identity(verify_db_sha=False)

    def test_bad_manifest_checksum_fails_closed(self):
        manifest = json.loads(DEFAULT_DATABASE_PATH_CONFIG.manifest_path.read_text(encoding="utf-8"))
        manifest["semantic_checksum"]["recomputed"] = "bad"
        manifest_path = Path(self.temp_dir.name) / "bad_manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        store = ResearchDataStore(
            db_path=DEFAULT_DATABASE_PATH_CONFIG.research_db_path,
            manifest_path=manifest_path,
        )

        with self.assertRaisesRegex(ResearchDataStoreError, "semantic checksum mismatch"):
            store.verify_runtime_identity(verify_db_sha=False)

    def test_bad_db_sha_fails_closed(self):
        store = ResearchDataStore(
            db_path=DEFAULT_DATABASE_PATH_CONFIG.research_db_path,
            expected_db_sha256="bad",
        )

        with self.assertRaisesRegex(ResearchDataStoreError, "DB SHA mismatch"):
            store.verify_runtime_identity(verify_db_sha=False)


if __name__ == "__main__":
    unittest.main()
