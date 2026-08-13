import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from database import DEFAULT_DB_PATH
from database_config import DEFAULT_DATABASE_PATH_CONFIG
from database_config import DEFAULT_RESEARCH_DB_SHA256
from database_config import DEFAULT_RESEARCH_MATERIALIZATION_VERSION
from database_config import DEFAULT_RESEARCH_SEMANTIC_CHECKSUM
from database_config import DEFAULT_USE_PHYSICAL_STORE_SPLIT
from database_config import DatabasePathConfig
from database_config import resolve_database_runtime_config


class DatabasePathConfigTestCase(unittest.TestCase):

    def test_default_legacy_path_matches_existing_stocks_db_path(self):
        self.assertEqual(DEFAULT_DATABASE_PATH_CONFIG.legacy_db_path, PROJECT_ROOT / "data" / "stocks.db")
        self.assertEqual(DEFAULT_DB_PATH, PROJECT_ROOT / "data" / "stocks.db")

    def test_runtime_physical_store_split_default_is_enabled(self):
        resolution = resolve_database_runtime_config()

        self.assertTrue(DEFAULT_USE_PHYSICAL_STORE_SPLIT)
        self.assertTrue(resolution.use_physical_store_split)
        self.assertEqual(resolution.active_db_mode, "physical_split")
        self.assertEqual(resolution.active_live_db_path, PROJECT_ROOT / "data" / "live" / "stocks_live.db")

    def test_default_config_exposes_research_live_and_legacy_paths(self):
        config = DatabasePathConfig.default(PROJECT_ROOT)

        self.assertEqual(config.legacy_db_path, PROJECT_ROOT / "data" / "stocks.db")
        self.assertEqual(
            config.research_db_path,
            PROJECT_ROOT
            / "data"
            / "research"
            / "snapshots"
            / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_v2.db",
        )
        self.assertEqual(config.live_db_path, PROJECT_ROOT / "data" / "live" / "stocks_live.db")
        self.assertEqual(
            config.research_snapshot_id,
            "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
        )
        self.assertEqual(config.research_snapshot_version, "v1")
        self.assertEqual(config.research_materialization_version, "v2")
        self.assertEqual(config.research_semantic_checksum, DEFAULT_RESEARCH_SEMANTIC_CHECKSUM)
        self.assertEqual(config.research_db_sha256, DEFAULT_RESEARCH_DB_SHA256)
        self.assertEqual(
            config.manifest_path,
            PROJECT_ROOT
            / "data"
            / "research"
            / "manifests"
            / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_materialization_v2_manifest.json",
        )

    def test_default_database_path_config_separates_materialized_research_and_live_paths(self):
        config = DatabasePathConfig.default(PROJECT_ROOT)

        self.assertTrue(config.research_db_path.exists())
        self.assertTrue(config.live_db_path.exists())
        self.assertNotEqual(config.research_db_path, config.live_db_path)
        self.assertNotEqual(config.legacy_db_path, config.live_db_path)

    def test_flag_off_resolution_keeps_legacy_live_runtime_path(self):
        config = DatabasePathConfig.default(PROJECT_ROOT)

        resolution = resolve_database_runtime_config(use_physical_store_split=False, path_config=config)

        self.assertFalse(resolution.use_physical_store_split)
        self.assertEqual(resolution.active_db_mode, "legacy")
        self.assertEqual(resolution.active_live_db_path, PROJECT_ROOT / "data" / "stocks.db")
        self.assertEqual(resolution.legacy_db_path, PROJECT_ROOT / "data" / "stocks.db")

    def test_flag_on_resolution_points_current_live_runtime_to_live_store(self):
        config = DatabasePathConfig.default(PROJECT_ROOT)

        resolution = resolve_database_runtime_config(use_physical_store_split=True, path_config=config)

        self.assertTrue(resolution.use_physical_store_split)
        self.assertEqual(resolution.active_db_mode, "physical_split")
        self.assertEqual(resolution.active_live_db_path, PROJECT_ROOT / "data" / "live" / "stocks_live.db")
        self.assertNotEqual(resolution.active_live_db_path, resolution.legacy_db_path)

    def test_rollback_switch_returns_to_legacy_without_changing_config_paths(self):
        config = DatabasePathConfig.default(PROJECT_ROOT)

        split_resolution = resolve_database_runtime_config(use_physical_store_split=True, path_config=config)
        rollback_resolution = resolve_database_runtime_config(use_physical_store_split=False, path_config=config)

        self.assertEqual(split_resolution.active_live_db_path, config.live_db_path)
        self.assertEqual(rollback_resolution.active_live_db_path, config.legacy_db_path)
        self.assertEqual(rollback_resolution.live_db_path, config.live_db_path)
        self.assertEqual(rollback_resolution.research_db_path, config.research_db_path)

    def test_research_path_is_unchanged_by_live_cutover_flag(self):
        config = DatabasePathConfig.default(PROJECT_ROOT)

        off_resolution = resolve_database_runtime_config(use_physical_store_split=False, path_config=config)
        on_resolution = resolve_database_runtime_config(use_physical_store_split=True, path_config=config)

        self.assertEqual(off_resolution.active_research_db_path, config.research_db_path)
        self.assertEqual(on_resolution.active_research_db_path, config.research_db_path)
        self.assertEqual(on_resolution.research_snapshot_id, config.research_snapshot_id)
        self.assertEqual(on_resolution.research_snapshot_version, "v1")
        self.assertEqual(on_resolution.research_materialization_version, DEFAULT_RESEARCH_MATERIALIZATION_VERSION)
        self.assertEqual(on_resolution.research_semantic_checksum, DEFAULT_RESEARCH_SEMANTIC_CHECKSUM)
        self.assertEqual(on_resolution.research_db_sha256, DEFAULT_RESEARCH_DB_SHA256)
        self.assertEqual(on_resolution.manifest_path, config.manifest_path)

    def test_live_path_is_isolated_from_legacy_and_research_paths(self):
        resolution = resolve_database_runtime_config(use_physical_store_split=True)

        self.assertNotEqual(resolution.live_db_path, resolution.legacy_db_path)
        self.assertNotEqual(resolution.live_db_path, resolution.research_db_path)
        self.assertNotEqual(resolution.legacy_db_path, resolution.research_db_path)


if __name__ == "__main__":
    unittest.main()
