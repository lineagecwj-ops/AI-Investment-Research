import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from features import FeatureArtifact
from features import FeatureCalculationContext
from features import FeatureCalculationOutput
from features import FeatureDefinition
from features import FeatureRegistry
from features import FeatureRegistryError


class StubCalculator:
    def __init__(self, definition):
        self._definition = definition

    def get_definition(self):
        return self._definition

    def calculate(self, context):
        return FeatureCalculationOutput(
            feature_id=self._definition.feature_id,
            feature_version=self._definition.version,
            values=(),
            metadata={"calculation_id": context.calculation_id},
        )

    def validate(self, output):
        return output.feature_id == self._definition.feature_id


class FeatureFrameworkTestCase(unittest.TestCase):

    def definition(self):
        return FeatureDefinition(
            feature_id="TECH_RSI14_V1",
            feature_name="RSI14",
            category="Technical",
            version="v1",
            description="Skeleton RSI14 feature definition.",
            formula_version="RSI14_v1",
            dependencies=("historical_prices.close",),
            input_fields=("symbol", "trading_date", "close"),
        )

    def test_feature_definition_creation(self):
        definition = self.definition()

        self.assertEqual(definition.feature_id, "TECH_RSI14_V1")
        self.assertEqual(definition.version, "v1")
        self.assertEqual(definition.dependencies, ("historical_prices.close",))
        self.assertEqual(definition.input_fields, ("symbol", "trading_date", "close"))

    def test_feature_registry_register_and_get_calculator(self):
        calculator = StubCalculator(self.definition())
        registry = FeatureRegistry()

        registry.register(calculator)

        self.assertIs(registry.get_calculator("TECH_RSI14_V1", "v1"), calculator)
        self.assertEqual(registry.list_features(), ("TECH_RSI14_V1:v1",))

    def test_duplicate_registration_rejected(self):
        registry = FeatureRegistry()
        registry.register(StubCalculator(self.definition()))

        with self.assertRaisesRegex(FeatureRegistryError, "already registered"):
            registry.register(StubCalculator(self.definition()))

    def test_feature_calculation_context_creation(self):
        context = FeatureCalculationContext(
            snapshot_id="research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
            snapshot_version="v1",
            universe_id="frozen_twse_218",
            as_of_date=date(2025, 12, 31),
            calculation_id="calc_phase7d1_skeleton",
            data_source="future ResearchDataStore integration placeholder",
            lineage={"source_materialization_version": "v2"},
        )

        self.assertEqual(context.snapshot_version, "v1")
        self.assertEqual(context.as_of_date.isoformat(), "2025-12-31")
        self.assertEqual(context.lineage["source_materialization_version"], "v2")

    def test_feature_artifact_metadata_creation(self):
        created_at = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

        artifact = FeatureArtifact(
            feature_id="TECH_RSI14_V1",
            feature_version="v1",
            snapshot_id="research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
            calculation_id="calc_phase7d1_skeleton",
            created_at=created_at,
            checksum=None,
            validation_status="PENDING",
        )

        self.assertEqual(artifact.feature_id, "TECH_RSI14_V1")
        self.assertIsNone(artifact.checksum)
        self.assertEqual(artifact.validation_status, "PENDING")

    def test_no_existing_system_impact_import_boundaries(self):
        feature_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "features").glob("*.py"))
        )

        forbidden_imports = (
            "live_data_store",
            "swing_scanner_service",
            "swing_scanner_pdf_export_service",
            "yfinance",
            "sqlite3",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, feature_source)


if __name__ == "__main__":
    unittest.main()
