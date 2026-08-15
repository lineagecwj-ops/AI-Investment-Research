import io
import sqlite3
import subprocess
import sys
import tempfile
import unittest
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

from risk_persistence.production_cli import main
from risk_persistence.sqlite_schema import APPLICATION_ID
from risk_persistence.sqlite_schema import CREATE_PORTFOLIO_RISK_GENERATION_RUNS_TABLE_SQL
from risk_persistence.sqlite_schema import CREATE_RISK_ARTIFACTS_TABLE_SQL
from risk_persistence.sqlite_schema import CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL
from risk_persistence.sqlite_schema import CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL
from risk_persistence.sqlite_schema import SCHEMA_VERSION
from risk_persistence.sqlite_schema import SCHEMA_VERSION_V2


class ProductionCliTestCase(unittest.TestCase):

    def setUp(self):
        self._assert_real_production_paths_absent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "AI-Investment-Research"
        self.project_root.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()
        self._assert_real_production_paths_absent()

    def db_path(self):
        return self.project_root / "data" / "production" / "risk_artifacts.db"

    def create_schema(self, version):
        path = self.db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
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

    def run_main(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = main(argv, stdout=stdout, stderr=stderr)
        return exit_code, stdout.getvalue().strip(), stderr.getvalue().strip()

    def _assert_real_production_paths_absent(self):
        for path in REAL_PRODUCTION_PATHS:
            self.assertFalse(path.exists(), f"real production DB path unexpectedly exists: {path}")

    def test_help_exits_zero_and_has_no_filesystem_side_effects(self):
        result = subprocess.run(
            [sys.executable, "-m", "risk_persistence.production_cli", "--help"],
            cwd=PROJECT_ROOT,
            env={"PYTHONPATH": str(SRC_PATH)},
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("verify", result.stdout)
        self.assertFalse((self.project_root / "data").exists())
        self._assert_real_production_paths_absent()

    def test_verify_missing_returns_exit_one_without_creating_directory(self):
        exit_code, stdout, stderr = self.run_main(["verify", "--project-root", str(self.project_root)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "MISSING schema=none db=data/production/risk_artifacts.db")
        self.assertEqual(stderr, "")
        self.assertFalse((self.project_root / "data" / "production").exists())

    def test_verify_ready_returns_exit_zero(self):
        self.create_schema(SCHEMA_VERSION)

        exit_code, stdout, stderr = self.run_main(["verify", "--project-root", str(self.project_root)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            stdout,
            "READY schema=v3 db=data/production/risk_artifacts.db quick_check=ok "
            "warning=backup_directory_missing",
        )
        self.assertEqual(stderr, "")

    def test_verify_v2_returns_migration_required_exit_one(self):
        self.create_schema(SCHEMA_VERSION_V2)

        exit_code, stdout, stderr = self.run_main(["verify", "--project-root", str(self.project_root)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "MIGRATION_REQUIRED schema=v2 db=data/production/risk_artifacts.db")
        self.assertEqual(stderr, "")

    def test_verify_wrong_application_returns_invalid_exit_one(self):
        self.create_schema(SCHEMA_VERSION)
        connection = sqlite3.connect(self.db_path())
        try:
            connection.execute("PRAGMA application_id=123")
            connection.commit()
        finally:
            connection.close()

        exit_code, stdout, stderr = self.run_main(["verify", "--project-root", str(self.project_root)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "INVALID schema=v3 db=data/production/risk_artifacts.db")
        self.assertEqual(stderr, "")

    def test_verify_unhealthy_returns_exit_one(self):
        self.create_schema(SCHEMA_VERSION)

        with patch("risk_persistence.sqlite_production_health._run_quick_check", return_value="failed"):
            exit_code, stdout, stderr = self.run_main(["verify", "--project-root", str(self.project_root)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "UNHEALTHY schema=v3 db=data/production/risk_artifacts.db quick_check=failed")
        self.assertEqual(stderr, "")

    def test_bad_project_root_returns_exit_two_without_traceback(self):
        missing_root = self.project_root / "missing"

        exit_code, stdout, stderr = self.run_main(["verify", "--project-root", str(missing_root)])

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("CONFIG_ERROR", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_usage_error_returns_exit_two(self):
        exit_code, _stdout, _stderr = self.run_main(["verify"])

        self.assertEqual(exit_code, 2)

    def test_cli_source_boundary_no_write_commands_or_extra_framework(self):
        source = (SRC_PATH / "risk_persistence" / "production_cli.py").read_text()
        forbidden = (
            "click",
            "typer",
            "bootstrap",
            "migrate",
            "repair",
            "force",
            "schedule",
            "dashboard",
            "PortfolioRiskGenerationService",
            "SQLiteRiskPersistenceBootstrapper",
            "CREATE TABLE",
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, source)
        self.assertIn("argparse", source)


if __name__ == "__main__":
    unittest.main()
