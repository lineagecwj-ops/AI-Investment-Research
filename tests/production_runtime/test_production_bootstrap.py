import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from production_runtime import ProductionBootstrapStatus
from production_runtime import ProductionEnvironmentBootstrapError
from production_runtime import ProductionEnvironmentBootstrapper
from production_runtime import ProductionEnvironmentComponentStatus
from production_runtime import ProductionEnvironmentInspector
from production_runtime import ProductionRuntimeConfig
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_persistence import RiskPersistenceHealthStatus


class ProductionBootstrapTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = ProductionRuntimeConfig.from_project_root(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def write_valid_portfolio(self):
        self.write_json(
            self.config.portfolio_source_path,
            {
                "schema_version": "1",
                "portfolio_id": "portfolio_001",
                "snapshot_id": "snapshot_001",
                "as_of_date": "2026-08-14",
                "valuation_date": "2026-08-14",
                "snapshot_created_at": "2026-08-16T09:00:00+00:00",
                "source_lineage": {"source_type": "local_json_portfolio_snapshot", "source_version": "1"},
                "positions": [
                    {
                        "position_id": "p1",
                        "symbol": "2330.TW",
                        "shares": "1.5",
                        "average_cost": "100",
                        "currency": "TWD",
                        "position_status": "ACTIVE",
                        "holding_type": "fractional_share",
                        "acquisition_date": "2026-01-01",
                    }
                ],
            },
        )

    def write_valid_mapping(self):
        self.write_json(
            self.config.symbol_mapping_path,
            {
                "schema_version": "1",
                "mapping_version": "provider_mapping_v1",
                "mappings": [
                    {
                        "domain_symbol": "2330.TW",
                        "provider": "YAHOO_FINANCE_V1",
                        "provider_symbol": "2330.TW",
                    }
                ],
            },
        )

    def write_valid_policy_pin(self):
        self.write_json(
            self.config.policy_pin_path,
            {
                "schema_version": "1",
                "policy_pin_version": "technical_risk_policy_pin_v1",
                "policy_version": PRODUCTION_TECHNICAL_RISK_POLICY_V1,
                "policy_source_key": "technical_risk_v1_research_freeze",
            },
        )

    def test_status_inspection_is_read_only_when_missing(self):
        status = ProductionEnvironmentInspector(self.config).inspect()

        self.assertEqual(status.production_root, ProductionEnvironmentComponentStatus.MISSING)
        self.assertEqual(status.portfolio_source, ProductionEnvironmentComponentStatus.MISSING)
        self.assertEqual(status.database, ProductionEnvironmentComponentStatus.MISSING)
        self.assertEqual(status.database_health, RiskPersistenceHealthStatus.MISSING)
        self.assertEqual(status.market_artifact_root, ProductionEnvironmentComponentStatus.MISSING)
        self.assertEqual(status.symbol_mapping, ProductionEnvironmentComponentStatus.MISSING)
        self.assertEqual(status.policy_pin, ProductionEnvironmentComponentStatus.MISSING)
        self.assertFalse(self.config.production_root.exists())

    def test_bootstrap_explicitly_creates_controlled_structure_and_sqlite(self):
        result = ProductionEnvironmentBootstrapper(self.config).bootstrap()

        self.assertEqual(result.status, ProductionBootstrapStatus.CREATED)
        self.assertTrue(self.config.production_root.is_dir())
        self.assertTrue(self.config.portfolio_root.is_dir())
        self.assertTrue(self.config.config_root.is_dir())
        self.assertTrue(self.config.market_artifact_root.is_dir())
        self.assertTrue(self.config.db_path.is_file())
        self.assertFalse(self.config.portfolio_source_path.exists())
        self.assertFalse(self.config.symbol_mapping_path.exists())
        self.assertFalse(self.config.policy_pin_path.exists())
        self.assertEqual(result.environment_status.portfolio_source, ProductionEnvironmentComponentStatus.MISSING)
        self.assertEqual(result.environment_status.symbol_mapping, ProductionEnvironmentComponentStatus.MISSING)
        self.assertEqual(result.environment_status.policy_pin, ProductionEnvironmentComponentStatus.MISSING)

    def test_repeat_bootstrap_is_safe(self):
        first = ProductionEnvironmentBootstrapper(self.config).bootstrap()
        second = ProductionEnvironmentBootstrapper(self.config).bootstrap()

        self.assertEqual(first.status, ProductionBootstrapStatus.CREATED)
        self.assertEqual(second.status, ProductionBootstrapStatus.ALREADY_READY)
        self.assertEqual(second.environment_status.database_health, RiskPersistenceHealthStatus.READY)

    def test_conflicting_production_path_fails_closed(self):
        self.config.production_root.parent.mkdir(parents=True)
        self.config.production_root.write_text("not a directory", encoding="utf-8")

        with self.assertRaisesRegex(ProductionEnvironmentBootstrapError, "conflicts"):
            ProductionEnvironmentBootstrapper(self.config).bootstrap()

    def test_status_ready_after_explicit_files_and_bootstrap(self):
        ProductionEnvironmentBootstrapper(self.config).bootstrap()
        self.write_valid_portfolio()
        self.write_valid_mapping()
        self.write_valid_policy_pin()

        status = ProductionEnvironmentInspector(self.config).inspect()

        self.assertTrue(status.ready_for_runtime)
        self.assertEqual(status.portfolio_source, ProductionEnvironmentComponentStatus.READY)
        self.assertEqual(status.database_health, RiskPersistenceHealthStatus.READY)
        self.assertEqual(status.symbol_mapping, ProductionEnvironmentComponentStatus.READY)
        self.assertEqual(status.policy_pin, ProductionEnvironmentComponentStatus.READY)

    def test_malformed_files_are_invalid_not_fabricated(self):
        ProductionEnvironmentBootstrapper(self.config).bootstrap()
        self.config.symbol_mapping_path.write_text("{bad json", encoding="utf-8")
        self.config.policy_pin_path.write_text("{bad json", encoding="utf-8")

        status = ProductionEnvironmentInspector(self.config).inspect()

        self.assertEqual(status.symbol_mapping, ProductionEnvironmentComponentStatus.INVALID)
        self.assertEqual(status.policy_pin, ProductionEnvironmentComponentStatus.INVALID)

    def test_real_production_path_untouched(self):
        ProductionEnvironmentBootstrapper(self.config).bootstrap()

        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())


if __name__ == "__main__":
    unittest.main()
