import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_persistence import RiskPersistenceConfigurationError
from risk_persistence import RiskPersistenceEnvironment
from risk_persistence import RiskPersistenceProductionConfig


class RiskPersistenceProductionConfigTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "AI-Investment-Research"
        self.project_root.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_from_project_root_derives_canonical_paths(self):
        config = RiskPersistenceProductionConfig.from_project_root(self.project_root)

        self.assertEqual(config.project_root, self.project_root.resolve())
        self.assertEqual(config.environment, RiskPersistenceEnvironment.PRODUCTION)
        self.assertEqual(
            config.db_path,
            self.project_root.resolve() / "data" / "production" / "risk_artifacts.db",
        )
        self.assertEqual(
            config.backup_directory,
            self.project_root.resolve() / "data" / "production" / "backups",
        )
        self.assertEqual(config.busy_timeout_ms, 5000)

    def test_config_is_frozen(self):
        config = RiskPersistenceProductionConfig.from_project_root(self.project_root)

        with self.assertRaises(FrozenInstanceError):
            config.busy_timeout_ms = 10

    def test_config_creation_has_no_filesystem_side_effect(self):
        RiskPersistenceProductionConfig.from_project_root(self.project_root)

        self.assertFalse((self.project_root / "data").exists())
        self.assertFalse((self.project_root / "data" / "production").exists())
        self.assertFalse((self.project_root / "data" / "production" / "risk_artifacts.db").exists())

    def test_project_root_file_rejected(self):
        file_root = Path(self.temp_dir.name) / "not_a_project"
        file_root.write_text("not a directory")

        with self.assertRaises(RiskPersistenceConfigurationError):
            RiskPersistenceProductionConfig.from_project_root(file_root)

    def test_missing_project_root_rejected(self):
        with self.assertRaises(RiskPersistenceConfigurationError):
            RiskPersistenceProductionConfig.from_project_root(Path(self.temp_dir.name) / "missing")

    def test_empty_project_root_rejected(self):
        with self.assertRaises(RiskPersistenceConfigurationError):
            RiskPersistenceProductionConfig.from_project_root("")

    def test_busy_timeout_bool_rejected(self):
        with self.assertRaises(RiskPersistenceConfigurationError):
            RiskPersistenceProductionConfig.from_project_root(self.project_root, busy_timeout_ms=True)

    def test_busy_timeout_zero_negative_and_non_int_rejected(self):
        for value in (0, -1, "5000"):
            with self.subTest(value=value):
                with self.assertRaises(RiskPersistenceConfigurationError):
                    RiskPersistenceProductionConfig.from_project_root(self.project_root, busy_timeout_ms=value)

    def test_direct_constructor_rejects_arbitrary_db_path(self):
        root = self.project_root.resolve()

        with self.assertRaises(RiskPersistenceConfigurationError):
            RiskPersistenceProductionConfig(
                project_root=root,
                environment=RiskPersistenceEnvironment.PRODUCTION,
                db_path=root / "data" / "production" / "other.db",
                backup_directory=root / "data" / "production" / "backups",
            )

    def test_direct_constructor_rejects_arbitrary_backup_path(self):
        root = self.project_root.resolve()

        with self.assertRaises(RiskPersistenceConfigurationError):
            RiskPersistenceProductionConfig(
                project_root=root,
                environment=RiskPersistenceEnvironment.PRODUCTION,
                db_path=root / "data" / "production" / "risk_artifacts.db",
                backup_directory=root / "data" / "backups",
            )

    def test_environment_must_be_production(self):
        root = self.project_root.resolve()

        with self.assertRaises(RiskPersistenceConfigurationError):
            RiskPersistenceProductionConfig(
                project_root=root,
                environment="DEVELOPMENT",
                db_path=root / "data" / "production" / "risk_artifacts.db",
                backup_directory=root / "data" / "production" / "backups",
            )


if __name__ == "__main__":
    unittest.main()
