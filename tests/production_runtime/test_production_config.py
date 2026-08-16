import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import TechnicalMarketDataProvider
from production_runtime import ProductionPolicyPinError
from production_runtime import ProductionRuntimeConfig
from production_runtime import ProviderSymbolMappingError
from production_runtime import load_production_policy_pin
from production_runtime import load_provider_symbol_mapping
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1


class ProductionRuntimeConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, relative_path, payload):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def valid_mapping_payload(self):
        return {
            "schema_version": "1",
            "mapping_version": "provider_mapping_v1",
            "mappings": [
                {
                    "domain_symbol": "2330.TW",
                    "provider": "YAHOO_FINANCE_V1",
                    "provider_symbol": "2330.TW",
                },
                {
                    "domain_symbol": "NVDA",
                    "provider": "YAHOO_FINANCE_V1",
                    "provider_symbol": "NVDA",
                },
            ],
        }

    def valid_policy_pin_payload(self):
        return {
            "schema_version": "1",
            "policy_pin_version": "technical_risk_policy_pin_v1",
            "policy_version": PRODUCTION_TECHNICAL_RISK_POLICY_V1,
            "policy_source_key": "technical_risk_v1_research_freeze",
        }

    def test_config_construction_derives_paths_without_creating_files(self):
        config = ProductionRuntimeConfig.from_project_root(self.root)

        self.assertEqual(config.production_root, self.root / "data" / "production")
        self.assertEqual(config.portfolio_source_path, self.root / "data" / "production" / "portfolio" / "portfolio.json")
        self.assertEqual(config.db_path, self.root / "data" / "production" / "risk_artifacts.db")
        self.assertEqual(config.market_artifact_root, self.root / "data" / "production" / "market_inputs")
        self.assertEqual(config.symbol_mapping_path, self.root / "data" / "production" / "config" / "provider_symbol_mapping.json")
        self.assertEqual(config.policy_pin_path, self.root / "data" / "production" / "config" / "policy_pin.json")
        self.assertFalse((self.root / "data" / "production").exists())

    def test_symbol_mapping_loads_explicit_versioned_mapping(self):
        path = self.write_json("mapping.json", self.valid_mapping_payload())

        mapping = load_provider_symbol_mapping(path)

        self.assertEqual(mapping.schema_version, "1")
        self.assertEqual(mapping.mapping_version, "provider_mapping_v1")
        self.assertEqual(
            dict(mapping.provider_symbols_for(("2330.TW", "NVDA"))),
            {"2330.TW": "2330.TW", "NVDA": "NVDA"},
        )

    def test_missing_symbol_mapping_fails_closed(self):
        path = self.write_json("mapping.json", self.valid_mapping_payload())
        mapping = load_provider_symbol_mapping(path)

        with self.assertRaisesRegex(ProviderSymbolMappingError, "missing"):
            mapping.provider_symbols_for(("2454.TW",))

    def test_duplicate_symbol_mapping_fails_closed(self):
        payload = self.valid_mapping_payload()
        payload["mappings"].append(
            {
                "domain_symbol": "2330.TW",
                "provider": "YAHOO_FINANCE_V1",
                "provider_symbol": "2330.TW",
            }
        )
        path = self.write_json("mapping.json", payload)

        with self.assertRaisesRegex(ProviderSymbolMappingError, "duplicate"):
            load_provider_symbol_mapping(path)

    def test_symbol_mapping_does_not_normalize_or_guess_suffix(self):
        path = self.write_json("mapping.json", self.valid_mapping_payload())
        mapping = load_provider_symbol_mapping(path)

        with self.assertRaisesRegex(ProviderSymbolMappingError, "missing"):
            mapping.provider_symbols_for(("2330",), provider=TechnicalMarketDataProvider.YAHOO_FINANCE_V1)

    def test_invalid_provider_symbol_mapping_fails_closed(self):
        payload = self.valid_mapping_payload()
        payload["mappings"][0]["provider_symbol"] = " \n"
        path = self.write_json("mapping.json", payload)

        with self.assertRaisesRegex(ProviderSymbolMappingError, "provider_symbol"):
            load_provider_symbol_mapping(path)

    def test_policy_pin_requires_exact_production_policy_version(self):
        path = self.write_json("policy_pin.json", self.valid_policy_pin_payload())

        pin = load_production_policy_pin(path)

        self.assertEqual(pin.schema_version, "1")
        self.assertEqual(pin.policy_version, PRODUCTION_TECHNICAL_RISK_POLICY_V1)
        self.assertEqual(pin.policy_source_key, "technical_risk_v1_research_freeze")

    def test_policy_pin_rejects_latest_or_unsupported_policy(self):
        payload = self.valid_policy_pin_payload()
        payload["policy_version"] = "LATEST"
        path = self.write_json("policy_pin.json", payload)

        with self.assertRaisesRegex(ProductionPolicyPinError, "unsupported"):
            load_production_policy_pin(path)


if __name__ == "__main__":
    unittest.main()
