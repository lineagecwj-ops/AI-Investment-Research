import hashlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
REAL_PRODUCTION_PATHS = (
    PROJECT_ROOT / "data" / "production" / "risk_artifacts.db",
    PROJECT_ROOT / "data" / "production" / "risk_artifacts.db-wal",
    PROJECT_ROOT / "data" / "production" / "risk_artifacts.db-shm",
)

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_persistence.sqlite_schema as schema_module
from risk_persistence import RiskArtifactPersistenceError
from risk_persistence import RiskPersistenceBackupError
from risk_persistence import RiskPersistenceBootstrapStatus
from risk_persistence import RiskPersistenceProductionConfig
from risk_persistence import RiskPersistenceProductionError
from risk_persistence import SQLiteRiskArtifactRepository
from risk_persistence import SQLiteRiskPersistenceBootstrapper
from risk_persistence.sqlite_schema import APPLICATION_ID
from risk_persistence.sqlite_schema import CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL
from risk_persistence.sqlite_schema import CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL
from risk_persistence.sqlite_schema import CREATE_RISK_ARTIFACTS_TABLE_SQL
from risk_persistence.sqlite_schema import SCHEMA_VERSION
from risk_persistence.sqlite_schema import SCHEMA_VERSION_V1
from risk_persistence.sqlite_schema import SCHEMA_VERSION_V2
from risk_persistence.sqlite_schema import SQLiteRiskArtifactSchemaState
from risk_persistence.sqlite_schema import inspect_schema_state


class SQLiteRiskPersistenceBootstrapperTestCase(unittest.TestCase):

    def setUp(self):
        self._assert_real_production_paths_absent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "AI-Investment-Research"
        self.project_root.mkdir()
        self.config = RiskPersistenceProductionConfig.from_project_root(self.project_root)
        self.clock = lambda: datetime(2026, 8, 16, 1, 30, 45, 123456, tzinfo=UTC)

    def tearDown(self):
        self.temp_dir.cleanup()
        self._assert_real_production_paths_absent()

    def bootstrapper(self, *, clock=None):
        return SQLiteRiskPersistenceBootstrapper(self.config, clock=clock or self.clock)

    def connection(self, path=None):
        return sqlite3.connect(path or self.config.db_path)

    def schema_identity(self, path=None):
        connection = self.connection(path)
        try:
            return (
                connection.execute("PRAGMA application_id").fetchone()[0],
                connection.execute("PRAGMA user_version").fetchone()[0],
            )
        finally:
            connection.close()

    def user_tables(self, path=None):
        connection = self.connection(path)
        try:
            return tuple(
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                    """
                ).fetchall()
            )
        finally:
            connection.close()

    def create_v1_db(self):
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(CREATE_RISK_ARTIFACTS_TABLE_SQL)
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION_V1}")
            connection.commit()
        finally:
            connection.close()

    def create_v2_db(self):
        self.create_v1_db()
        connection = self.connection()
        try:
            schema_module._migrate_v1_to_v2(connection)
        finally:
            connection.close()

    def create_v2_db_without_wal(self):
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(CREATE_RISK_ARTIFACTS_TABLE_SQL)
            connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL)
            connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL)
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION_V2}")
            connection.commit()
        finally:
            connection.close()

    def backup_path(self, source_version):
        return (
            self.config.backup_directory
            / f"risk_artifacts.schema-v{source_version}.20260816T013045.123456Z.db"
        )

    def assert_backup_schema(self, source_version):
        path = self.backup_path(source_version)
        self.assertTrue(path.exists())
        self.assertEqual(self.schema_identity(path), (APPLICATION_ID, source_version))
        connection = self.connection(path)
        try:
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0], "ok")
        finally:
            connection.close()

    def _assert_real_production_paths_absent(self):
        for path in REAL_PRODUCTION_PATHS:
            self.assertFalse(path.exists(), f"real production DB path unexpectedly exists: {path}")

    def file_sha256(self):
        digest = hashlib.sha256()
        with self.config.db_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def test_missing_fresh_db_initializes_v3_and_creates_parent_directories(self):
        result = self.bootstrapper().bootstrap()

        self.assertEqual(result.status, RiskPersistenceBootstrapStatus.CREATED)
        self.assertIsNone(result.schema_before)
        self.assertEqual(result.schema_after, SCHEMA_VERSION)
        self.assertIsNone(result.backup_identifier)
        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))
        self.assertTrue(self.config.db_path.exists())
        self.assertTrue(self.config.backup_directory.is_dir())

    def test_empty_file_initializes_v3(self):
        self.config.db_path.parent.mkdir(parents=True)
        self.config.db_path.touch()

        result = self.bootstrapper().bootstrap()

        self.assertEqual(result.status, RiskPersistenceBootstrapStatus.CREATED)
        self.assertEqual(result.schema_before, 0)
        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))

    def test_current_v3_returns_already_ready_without_backup(self):
        self.bootstrapper().bootstrap()

        result = self.bootstrapper().bootstrap()

        self.assertEqual(result.status, RiskPersistenceBootstrapStatus.ALREADY_READY)
        self.assertEqual(result.schema_before, SCHEMA_VERSION)
        self.assertEqual(result.schema_after, SCHEMA_VERSION)
        self.assertIsNone(result.backup_identifier)
        self.assertEqual(tuple(self.config.backup_directory.iterdir()), tuple())

    def test_valid_v2_backs_up_then_migrates_to_v3(self):
        self.create_v2_db()

        result = self.bootstrapper().bootstrap()

        self.assertEqual(result.status, RiskPersistenceBootstrapStatus.MIGRATED)
        self.assertEqual(result.schema_before, SCHEMA_VERSION_V2)
        self.assertEqual(result.schema_after, SCHEMA_VERSION)
        self.assertEqual(result.backup_identifier, self.backup_path(SCHEMA_VERSION_V2).name)
        self.assert_backup_schema(SCHEMA_VERSION_V2)
        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))

    def test_schema_inspection_valid_v2_is_read_only_by_hash_mtime_and_user_version(self):
        self.create_v2_db_without_wal()
        hash_before = self.file_sha256()
        mtime_ns_before = self.config.db_path.stat().st_mtime_ns
        identity_before = self.schema_identity()
        tables_before = self.user_tables()

        connection = sqlite3.connect(self.config.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            inspection = inspect_schema_state(connection)
        finally:
            connection.close()

        hash_after = self.file_sha256()
        mtime_ns_after = self.config.db_path.stat().st_mtime_ns
        identity_after = self.schema_identity()
        tables_after = self.user_tables()

        self.assertEqual(inspection.state, SQLiteRiskArtifactSchemaState.V2)
        self.assertEqual(identity_before, (APPLICATION_ID, SCHEMA_VERSION_V2))
        self.assertEqual(identity_after, (APPLICATION_ID, SCHEMA_VERSION_V2))
        self.assertEqual(hash_after, hash_before)
        self.assertEqual(mtime_ns_after, mtime_ns_before)
        self.assertEqual(tables_after, tables_before)

    def test_valid_v1_backs_up_then_migrates_through_v3(self):
        self.create_v1_db()

        result = self.bootstrapper().bootstrap()

        self.assertEqual(result.status, RiskPersistenceBootstrapStatus.MIGRATED)
        self.assertEqual(result.schema_before, SCHEMA_VERSION_V1)
        self.assertEqual(result.backup_identifier, self.backup_path(SCHEMA_VERSION_V1).name)
        self.assert_backup_schema(SCHEMA_VERSION_V1)
        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))

    def test_backup_collision_fails_closed_and_does_not_migrate(self):
        self.create_v2_db()
        self.config.backup_directory.mkdir(parents=True)
        self.backup_path(SCHEMA_VERSION_V2).write_text("existing backup")

        with self.assertRaises(RiskPersistenceBackupError):
            self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V2))

    def test_backup_api_failure_blocks_migration(self):
        self.create_v2_db()

        with patch(
            "risk_persistence.sqlite_production_bootstrap._sqlite_backup",
            side_effect=RiskPersistenceBackupError("forced backup failure"),
        ):
            with self.assertRaises(RiskPersistenceBackupError):
                self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V2))
        self.assertFalse(self.backup_path(SCHEMA_VERSION_V2).exists())

    def test_backup_verify_failure_blocks_migration_and_removes_temp_backup(self):
        self.create_v2_db()

        with patch(
            "risk_persistence.sqlite_production_bootstrap._verify_backup",
            side_effect=RiskPersistenceBackupError("forced verify failure"),
        ):
            with self.assertRaises(RiskPersistenceBackupError):
                self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V2))
        self.assertEqual(tuple(self.config.backup_directory.iterdir()), tuple())

    def test_migration_failure_preserves_verified_backup(self):
        self.create_v2_db()

        with patch(
            "risk_persistence.sqlite_production_bootstrap.initialize_or_verify_schema",
            side_effect=RiskArtifactPersistenceError("forced migration failure"),
        ):
            with self.assertRaises(RiskPersistenceProductionError):
                self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V2))
        self.assert_backup_schema(SCHEMA_VERSION_V2)

    def test_wrong_application_id_fails_closed_without_backup(self):
        self.create_v1_db()
        connection = self.connection()
        try:
            connection.execute("PRAGMA application_id=123")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskPersistenceProductionError):
            self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (123, SCHEMA_VERSION_V1))
        self.assertEqual(tuple(self.config.backup_directory.iterdir()), tuple())

    def test_future_schema_fails_closed_without_downgrade(self):
        self.create_v1_db()
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskPersistenceProductionError):
            self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION + 1))
        self.assertEqual(tuple(self.config.backup_directory.iterdir()), tuple())

    def test_malformed_v1_fails_closed_without_repair(self):
        self.create_v1_db()
        connection = self.connection()
        try:
            connection.execute("CREATE TABLE extra_table (id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskPersistenceProductionError):
            self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V1))
        self.assertIn("extra_table", self.user_tables())

    def test_malformed_v2_fails_closed_without_backup_or_repair(self):
        self.create_v2_db()
        connection = self.connection()
        try:
            connection.execute("DROP INDEX idx_technical_risk_artifact_position_latest")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskPersistenceProductionError):
            self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V2))
        self.assertEqual(tuple(self.config.backup_directory.iterdir()), tuple())

    def test_malformed_current_v3_fails_closed_without_repair(self):
        self.bootstrapper().bootstrap()
        connection = self.connection()
        try:
            connection.execute("CREATE TABLE extra_table (id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(RiskPersistenceProductionError):
            self.bootstrapper().bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION))
        self.assertIn("extra_table", self.user_tables())

    def test_directory_db_path_fails_closed(self):
        self.config.db_path.parent.mkdir(parents=True)
        self.config.db_path.mkdir()

        with self.assertRaises(RiskPersistenceProductionError):
            self.bootstrapper().bootstrap()

    def test_backup_directory_file_fails_closed(self):
        self.config.db_path.parent.mkdir(parents=True)
        self.config.backup_directory.write_text("not a directory")

        with self.assertRaises(RiskPersistenceProductionError):
            self.bootstrapper().bootstrap()

    def test_naive_backup_clock_rejected_before_migration(self):
        self.create_v2_db()

        with self.assertRaises(RiskPersistenceBackupError):
            self.bootstrapper(clock=lambda: datetime(2026, 8, 16, 1, 30)).bootstrap()

        self.assertEqual(self.schema_identity(), (APPLICATION_ID, SCHEMA_VERSION_V2))

    def test_generic_repository_parent_missing_still_fails_closed(self):
        with self.assertRaises(RiskArtifactPersistenceError):
            SQLiteRiskArtifactRepository(Path(self.temp_dir.name) / "missing" / "risk_artifacts.db")

    def test_public_exports_include_p1a_contracts_only(self):
        import risk_persistence

        expected = {
            "RiskPersistenceProductionConfig",
            "RiskPersistenceEnvironment",
            "SQLiteRiskPersistenceBootstrapper",
            "RiskPersistenceBootstrapResult",
            "RiskPersistenceBootstrapStatus",
            "RiskPersistenceProductionError",
            "RiskPersistenceConfigurationError",
            "RiskPersistenceBackupError",
        }
        self.assertTrue(expected.issubset(set(risk_persistence.__all__)))
        self.assertNotIn("inspect_schema_state", risk_persistence.__all__)
        self.assertNotIn("_create_verified_backup", risk_persistence.__all__)

    def test_source_boundary_no_runtime_or_health_implementation(self):
        source = (
            (SRC_PATH / "risk_persistence" / "production_config.py").read_text()
            + "\n"
            + (SRC_PATH / "risk_persistence" / "sqlite_production_bootstrap.py").read_text()
        )
        forbidden = (
            "PortfolioRiskGenerationService",
            "CapturingRiskEvaluator",
            "SQLiteTechnicalPortfolioRiskPersistenceCoordinator",
            "portfolio_generation",
            "dashboard",
            "scheduler",
            "alert",
            "policy activation",
            "TechnicalRiskEvidenceSnapshot",
            "SQLiteRiskPersistenceHealthChecker",
            "integrity_check",
            "shutil.copy",
            "data/stocks.db",
            "data/live",
            "data/research",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, source)
        self.assertIn("data\" / \"production\" / \"risk_artifacts.db", source)

    def test_real_repo_production_db_is_not_touched(self):
        self.bootstrapper().bootstrap()

        self._assert_real_production_paths_absent()
        self.assertTrue(self.config.db_path.exists())
        self.assertNotEqual(self.config.db_path, PROJECT_ROOT / "data" / "production" / "risk_artifacts.db")


if __name__ == "__main__":
    unittest.main()
