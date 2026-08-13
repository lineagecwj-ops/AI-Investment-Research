import sys
import unittest
from datetime import date
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from targets import FutureReturn20DRegressionGenerator
from targets import FutureReturn60DClassificationGenerator
from targets import FutureReturn60DRegressionGenerator
from targets import TargetArtifactGenerationError
from targets import TargetArtifactGenerator
from targets import TargetCalculationContext
from targets import TargetChecksumGenerator
from targets import TargetPricePoint
from targets import TargetRegistry
from targets import TargetRegistryError


class TargetFrameworkTestCase(unittest.TestCase):

    def context(self, window=20, reference_date=date(2026, 1, 1), symbol="2330.TW"):
        return TargetCalculationContext(
            snapshot_id="research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
            symbol=symbol,
            reference_date=reference_date,
            evaluation_window=window,
            target_version="v1",
            calculation_id="calc_phase7g_target",
        )

    def prices(self, count=80, start=date(2026, 1, 1), symbol="2330.TW", start_price=100.0, step=1.0):
        return tuple(
            TargetPricePoint(
                symbol=symbol,
                trading_date=start + timedelta(days=index),
                price=start_price + index * step,
            )
            for index in range(count)
        )

    def test_target_definition_creation(self):
        definition = FutureReturn20DRegressionGenerator(()).get_definition()

        self.assertEqual(definition.target_id, "TARGET_RETURN_20D_REG_V1")
        self.assertEqual(definition.target_type, "Regression")
        self.assertEqual(definition.version, "v1")
        self.assertEqual(definition.calculation_window, 20)
        self.assertTrue(definition.formula_version)

    def test_target_registry_registration(self):
        registry = TargetRegistry()
        generators = [
            FutureReturn20DRegressionGenerator(self.prices()),
            FutureReturn60DRegressionGenerator(self.prices()),
            FutureReturn60DClassificationGenerator(self.prices()),
        ]

        registry.register_many(generators)

        self.assertEqual(
            registry.list_targets(),
            (
                "TARGET_RETURN_20D_REG_V1:v1",
                "TARGET_RETURN_60D_CLASS_V1:v1",
                "TARGET_RETURN_60D_REG_V1:v1",
            ),
        )
        self.assertIs(registry.get_generator("TARGET_RETURN_20D_REG_V1", "v1"), generators[0])

    def test_duplicate_registration_rejected(self):
        registry = TargetRegistry()
        registry.register(FutureReturn20DRegressionGenerator(self.prices()))

        with self.assertRaisesRegex(TargetRegistryError, "already registered"):
            registry.register(FutureReturn20DRegressionGenerator(self.prices()))

    def test_20d_return_calculation(self):
        generator = FutureReturn20DRegressionGenerator(self.prices())

        output = generator.calculate(self.context(window=20))

        self.assertTrue(generator.validate(output))
        self.assertEqual(output.target_id, "TARGET_RETURN_20D_REG_V1")
        self.assertEqual(output.target_value, 0.2)
        self.assertEqual(output.artifact.validation_status, "PASS")

    def test_60d_return_calculation(self):
        generator = FutureReturn60DRegressionGenerator(self.prices())

        output = generator.calculate(self.context(window=60))

        self.assertTrue(generator.validate(output))
        self.assertEqual(output.target_id, "TARGET_RETURN_60D_REG_V1")
        self.assertEqual(output.target_value, 0.6)

    def test_60d_classification(self):
        positive = FutureReturn60DClassificationGenerator(self.prices(start_price=100.0, step=1.0))
        neutral = FutureReturn60DClassificationGenerator(self.prices(start_price=100.0, step=0.0))
        negative = FutureReturn60DClassificationGenerator(self.prices(start_price=100.0, step=-0.2))

        self.assertEqual(positive.calculate(self.context(window=60)).target_value, "Positive")
        self.assertEqual(neutral.calculate(self.context(window=60)).target_value, "Neutral")
        self.assertEqual(negative.calculate(self.context(window=60)).target_value, "Negative")

    def test_missing_future_window_rejection(self):
        generator = FutureReturn20DRegressionGenerator(self.prices(count=20))

        output = generator.calculate(self.context(window=20))

        self.assertFalse(generator.validate(output))
        self.assertIsNone(output.target_value)
        self.assertEqual(output.metadata["validation_status"], "INSUFFICIENT_FUTURE_DATA")

    def test_invalid_price_rejection(self):
        prices = (
            TargetPricePoint("2330.TW", date(2026, 1, 1), 0.0),
            *self.prices(count=21, start=date(2026, 1, 2)),
        )
        generator = FutureReturn20DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=20))

        self.assertFalse(generator.validate(output))
        self.assertEqual(output.metadata["validation_status"], "INVALID_PRICE")

    def test_checksum_deterministic(self):
        generator = FutureReturn20DRegressionGenerator(self.prices())
        context = self.context(window=20)
        output = generator.calculate(context)
        checksum = TargetChecksumGenerator()

        self.assertEqual(checksum.generate(output, context), checksum.generate(output, context))

    def test_different_target_input_produces_different_checksum(self):
        context = self.context(window=20)
        first = FutureReturn20DRegressionGenerator(self.prices(step=1.0)).calculate(context)
        second = FutureReturn20DRegressionGenerator(self.prices(step=2.0)).calculate(context)
        checksum = TargetChecksumGenerator()

        self.assertNotEqual(checksum.generate(first, context), checksum.generate(second, context))

    def test_artifact_generation(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices()).calculate(context)

        artifact = TargetArtifactGenerator().generate(output, context)

        self.assertEqual(artifact.target_id, "TARGET_RETURN_20D_REG_V1")
        self.assertEqual(artifact.target_version, "v1")
        self.assertEqual(artifact.symbol, "2330.TW")
        self.assertEqual(artifact.reference_date.isoformat(), "2026-01-01")
        self.assertEqual(artifact.validation_status, "PASS")
        self.assertTrue(artifact.checksum)

    def test_invalid_target_blocks_artifact(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices(count=20)).calculate(context)

        with self.assertRaisesRegex(TargetArtifactGenerationError, "validation failed"):
            TargetArtifactGenerator().generate(output, context)

    def test_feature_join_compatibility_metadata(self):
        context = self.context(window=60)
        output = FutureReturn60DRegressionGenerator(self.prices()).calculate(context)

        self.assertEqual(output.symbol, "2330.TW")
        self.assertEqual(output.reference_date, date(2026, 1, 1))
        self.assertEqual(output.metadata["snapshot_id"], context.snapshot_id)
        self.assertEqual(output.metadata["calculation_id"], context.calculation_id)

    def test_target_modules_do_not_import_existing_runtime_boundaries(self):
        target_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "targets").glob("*.py"))
        )

        forbidden_imports = (
            "live_data_store",
            "swing_scanner_service",
            "swing_scanner_pdf_export_service",
            "yfinance",
            "sqlite3",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, target_source)


if __name__ == "__main__":
    unittest.main()
