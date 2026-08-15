import hashlib
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
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

from risk_persistence import RiskPersistenceHealthResult
from risk_persistence import RiskPersistenceHealthStatus
from risk_persistence import RiskPersistenceProductionConfig
from risk_persistence import RiskPersistenceProductionError
from risk_persistence import SQLiteRiskPersistenceHealthChecker
from risk_persistence.sqlite_schema import APPLICATION_ID
from risk_persistence.sqlite_schema import CREATE_PORTFOLIO_RISK_GENERATION_RUNS_TABLE_SQL
from risk_persistence.sqlite_schema import CREATE_RISK_ARTIFACTS_TABLE_SQL
from risk_persistence.sqlite_schema import CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL
from risk_persistence.sqlite_schema import CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL
from risk_persistence.sqlite_schema import SCHEMA_VERSION
from risk_persistence.sqlite_schema import SCHEMA_VERSION_V1
from risk_persistence.sqlite_schema import SCHEMA_VERSION_V2


class SQLiteRiskPersistenceHealthCheckerTestCase(unittest.TestCase):

    def setUp(self):
        self._assert_real_production_paths_absent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "AI-Investment-Research"
        self.project_root.mkdir()
        self.config = RiskPersistenceProductionConfig.from_project_root(self.project_root)

    def tearDown(self):
        self.temp_dir.cleanup()
        self._assert_real_production_paths_absent()

    def health_checker(self):
        return SQLiteRiskPersistenceHealthChecker(self.config)

    def connection(self):
        return sqlite3.connect(self.config.db_path)

    def create_schema(self, version):
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(CREATE_RISK_ARTIFACTS_TABLE_SQL)
            if version >= SCHEMA_VERSION_V2:
                connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL)
                connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL)
            if version >= SCHEMA_VERSION:
                connection.execute(CREATE_PORTFOLIO_RISK_GENERATION_RUNS_TABLE_SQL)
            connection.execute(f"PRAGMA user_version={version}")
            connection.commit()
        finally:
            connection.close()

    def schema_identity(self):
        connection = self.connection()
        try:
            return (
                connection.execute("PRAGMA application_id").fetchone()[0],
                connection.execute("PRAGMA user_version").fetchone()[0],
            )
        finally:
            connection.close()

    def user_tables(self):
        connection = self.connection()
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

    def file_sha256(self):
        digest = hashlib.sha256()
        with self.config.db_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def assert_no_mutation(self, before):
        self.assertEqual(self.file_sha256(), before["hash"])
        self.assertEqual(self.config.db_path.stat().st_mtime_ns, before["mtime_ns"])
        self.assertEqual(self.schema_identity(), before["identity"])
        self.assertEqual(self.user_tables(), before["tables"])

    def snapshot_db(self):
        return {
            "hash": self.file_sha256(),
            "mtime_ns": self.config.db_path.stat().st_mtime_ns,
            "identity": self.schema_identity(),
            "tables": self.user_tables(),
        }

    def _assert_real_production_paths_absent(self):
        for path in REAL_PRODUCTION_PATHS:
            self.assertFalse(path.exists(), f"real production DB path unexpectedly exists: {path}")

    def test_health_result_is_frozen(self):
        result = RiskPersistenceHealthResult(
            status=RiskPersistenceHealthStatus.MISSING,
            schema_version=None,
            db_path_alias="data/production/risk_artifacts.db",
            quick_check_result=None,
            checks=("path",),
        )

        with self.assertRaises(FrozenInstanceError):
            result.status = RiskPersistenceHealthStatus.READY

    def test_constructor_requires_production_config(self):
        with self.assertRaises(RiskPersistenceProductionError):
            SQLiteRiskPersistenceHealthChecker(self.config.db_path)

    def test_missing_parent_returns_missing_without_creating_directory(self):
        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.MISSING)
        self.assertIsNone(result.schema_version)
        self.assertEqual(result.db_path_alias, "data/production/risk_artifacts.db")
        self.assertFalse((self.project_root / "data" / "production").exists())

    def test_missing_db_returns_missing_without_creating_db(self):
        self.config.db_path.parent.mkdir(parents=True)

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.MISSING)
        self.assertFalse(self.config.db_path.exists())

    def test_empty_db_file_returns_missing_without_initializing(self):
        self.config.db_path.parent.mkdir(parents=True)
        self.config.db_path.touch()
        before_hash = self.file_sha256()
        before_mtime = self.config.db_path.stat().st_mtime_ns

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.MISSING)
        self.assertEqual(result.schema_version, 0)
        self.assertEqual(self.config.db_path.stat().st_size, 0)
        self.assertEqual(self.file_sha256(), before_hash)
        self.assertEqual(self.config.db_path.stat().st_mtime_ns, before_mtime)

    def test_valid_v1_returns_migration_required_without_migration(self):
        self.create_schema(SCHEMA_VERSION_V1)
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.MIGRATION_REQUIRED)
        self.assertEqual(result.schema_version, SCHEMA_VERSION_V1)
        self.assert_no_mutation(before)

    def test_valid_v2_returns_migration_required_without_migration(self):
        self.create_schema(SCHEMA_VERSION_V2)
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.MIGRATION_REQUIRED)
        self.assertEqual(result.schema_version, SCHEMA_VERSION_V2)
        self.assertNotIn("portfolio_risk_generation_runs", self.user_tables())
        self.assert_no_mutation(before)

    def test_valid_current_v3_returns_ready_without_mutation(self):
        self.create_schema(SCHEMA_VERSION)
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.READY)
        self.assertEqual(result.schema_version, SCHEMA_VERSION)
        self.assertEqual(result.quick_check_result, "ok")
        self.assertEqual(result.checks, ("path", "schema", "quick_check"))
        self.assertEqual(result.warnings, ("backup_directory_missing",))
        self.assert_no_mutation(before)

    def test_backup_directory_missing_is_warning_not_unready(self):
        self.create_schema(SCHEMA_VERSION)

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.READY)
        self.assertIn("backup_directory_missing", result.warnings)

    def test_wrong_application_id_returns_invalid_without_repair(self):
        self.create_schema(SCHEMA_VERSION_V1)
        connection = self.connection()
        try:
            connection.execute("PRAGMA application_id=123")
            connection.commit()
        finally:
            connection.close()
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.INVALID)
        self.assertEqual(result.schema_version, SCHEMA_VERSION_V1)
        self.assert_no_mutation(before)

    def test_future_schema_returns_invalid_without_downgrade(self):
        self.create_schema(SCHEMA_VERSION)
        connection = self.connection()
        try:
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
            connection.commit()
        finally:
            connection.close()
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.INVALID)
        self.assertEqual(result.schema_version, SCHEMA_VERSION + 1)
        self.assert_no_mutation(before)

    def test_malformed_v1_returns_invalid_without_repair(self):
        self.create_schema(SCHEMA_VERSION_V1)
        connection = self.connection()
        try:
            connection.execute("CREATE TABLE extra_table (id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.INVALID)
        self.assertEqual(result.schema_version, SCHEMA_VERSION_V1)
        self.assert_no_mutation(before)

    def test_malformed_v2_returns_invalid_without_repair(self):
        self.create_schema(SCHEMA_VERSION_V2)
        connection = self.connection()
        try:
            connection.execute("DROP INDEX idx_technical_risk_artifact_position_latest")
            connection.commit()
        finally:
            connection.close()
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.INVALID)
        self.assertEqual(result.schema_version, SCHEMA_VERSION_V2)
        self.assert_no_mutation(before)

    def test_malformed_v3_returns_invalid_without_repair(self):
        self.create_schema(SCHEMA_VERSION)
        connection = self.connection()
        try:
            connection.execute("CREATE TABLE extra_table (id TEXT PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()
        before = self.snapshot_db()

        result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.INVALID)
        self.assertEqual(result.schema_version, SCHEMA_VERSION)
        self.assert_no_mutation(before)

    def test_quick_check_failure_returns_unhealthy(self):
        self.create_schema(SCHEMA_VERSION)
        before = self.snapshot_db()

        with patch("risk_persistence.sqlite_production_health._run_quick_check", return_value="failed"):
            result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.UNHEALTHY)
        self.assertEqual(result.schema_version, SCHEMA_VERSION)
        self.assertEqual(result.quick_check_result, "failed")
        self.assert_no_mutation(before)

    def test_readonly_sqlite_error_returns_unhealthy(self):
        self.create_schema(SCHEMA_VERSION)
        before = self.snapshot_db()

        with patch("risk_persistence.sqlite_production_health.inspect_schema_state", side_effect=sqlite3.OperationalError):
            result = self.health_checker().check()

        self.assertEqual(result.status, RiskPersistenceHealthStatus.UNHEALTHY)
        self.assert_no_mutation(before)

    def test_source_boundary_no_write_or_runtime_implementation(self):
        source = (SRC_PATH / "risk_persistence" / "sqlite_production_health.py").read_text()
        forbidden = (
            "PortfolioRiskGenerationService",
            "CapturingRiskEvaluator",
            "SQLiteTechnicalPortfolioRiskPersistenceCoordinator",
            "portfolio_generation",
            "dashboard",
            "scheduler",
            "alert",
            "TechnicalRiskEvidenceSnapshot",
            "CREATE TABLE",
            "ALTER TABLE",
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
            "PRAGMA user_version",
            "PRAGMA journal_mode",
            "VACUUM",
            "initialize_or_verify_schema",
            "SQLiteRiskPersistenceBootstrapper",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, source)
        self.assertIn("mode=ro", source)
        self.assertIn("query_only=ON", source)
        self.assertIn("PRAGMA quick_check", source)

    def test_public_exports_include_health_contracts_only(self):
        import risk_persistence

        self.assertIn("SQLiteRiskPersistenceHealthChecker", risk_persistence.__all__)
        self.assertIn("RiskPersistenceHealthResult", risk_persistence.__all__)
        self.assertIn("RiskPersistenceHealthStatus", risk_persistence.__all__)
        self.assertNotIn("RiskPersistenceHealthError", risk_persistence.__all__)
        self.assertNotIn("_run_quick_check", risk_persistence.__all__)


if __name__ == "__main__":
    unittest.main()
