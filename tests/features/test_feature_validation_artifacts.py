import sys
import unittest
from datetime import date
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from features import ArtifactGenerationError
from features import FeatureArtifactGenerator
from features import FeatureCalculationContext
from features import FeatureCalculationOutput
from features import FeatureChecksumGenerator
from features import FeatureValidator
from features import LeakageValidationError
from features import RangeValidationError
from features import SchemaError
from features.calculators import PriceVolumePoint
from features.calculators import RSI14Calculator
from features.calculators import SMA20Calculator
from features.calculators import SMA60Calculator
from features.calculators import VolumeRatioCalculator


class FeatureValidationArtifactTestCase(unittest.TestCase):

    def context(self, as_of_date=date(2026, 3, 31)):
        return FeatureCalculationContext(
            snapshot_id="research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
            snapshot_version="v1",
            universe_id="frozen_twse_218",
            as_of_date=as_of_date,
            calculation_id="calc_phase7d3_validation",
        )

    def output(self, feature_id="TECH_SMA20_V1", value=10.5, feature_date=date(2026, 1, 20), symbol="2330.TW"):
        return FeatureCalculationOutput(
            feature_id=feature_id,
            feature_version="v1",
            values=(
                {
                    "feature_id": feature_id,
                    "feature_version": "v1",
                    "symbol": symbol,
                    "date": feature_date,
                    "value": value,
                    "feature_value": value,
                },
            ),
            metadata={"validation_status": "PASS"},
        )

    def price_series(self, count=80, start=date(2026, 1, 1), symbol="2330.TW"):
        return tuple(
            PriceVolumePoint(
                symbol=symbol,
                trading_date=start + timedelta(days=index),
                close=float(index + 1),
                volume=float((index + 1) * 100),
            )
            for index in range(count)
        )

    def test_schema_validation_pass(self):
        validator = FeatureValidator()

        validator.validate_schema(self.output())

    def test_schema_validation_fail(self):
        validator = FeatureValidator()
        output = FeatureCalculationOutput(
            feature_id="TECH_SMA20_V1",
            feature_version="v1",
            values=({"feature_id": "TECH_SMA20_V1", "symbol": "2330.TW"},),
        )

        with self.assertRaisesRegex(SchemaError, "missing required fields"):
            validator.validate_schema(output)

    def test_rsi_range_validation(self):
        validator = FeatureValidator()

        validator.validate_range(self.output(feature_id="TECH_RSI14_V1", value=100.0))

        with self.assertRaisesRegex(RangeValidationError, "RSI14 value out of range"):
            validator.validate_range(self.output(feature_id="TECH_RSI14_V1", value=120.0))

    def test_negative_volume_ratio_rejection(self):
        validator = FeatureValidator()

        with self.assertRaisesRegex(RangeValidationError, "non-negative"):
            validator.validate_range(self.output(feature_id="TECH_VOLUME_RATIO_V1", value=-0.1))

    def test_completeness_calculation(self):
        validator = FeatureValidator()
        output = FeatureCalculationOutput(
            feature_id="TECH_SMA20_V1",
            feature_version="v1",
            values=(
                {
                    "feature_id": "TECH_SMA20_V1",
                    "feature_version": "v1",
                    "symbol": "2330.TW",
                    "date": date(2026, 1, 20),
                    "value": 10.5,
                },
                {
                    "feature_id": "TECH_SMA20_V1",
                    "feature_version": "v1",
                    "symbol": "2454.TW",
                    "date": date(2026, 1, 20),
                    "value": 20.5,
                },
            ),
        )

        result = validator.validate_completeness(("2330.TW", "2454.TW", "2317.TW"), output)

        self.assertEqual(result.expected_count, 3)
        self.assertEqual(result.actual_count, 2)
        self.assertAlmostEqual(result.coverage_ratio, 2 / 3)
        self.assertEqual(result.missing_symbols, ("2317.TW",))

    def test_future_date_leakage_detection(self):
        validator = FeatureValidator()

        with self.assertRaisesRegex(LeakageValidationError, "after as_of_date"):
            validator.validate_leakage(self.output(feature_date=date(2026, 4, 1)), self.context())

    def test_checksum_deterministic(self):
        generator = FeatureChecksumGenerator()
        context = self.context()
        output = self.output()

        first = generator.generate(output, context)
        second = generator.generate(output, context)

        self.assertEqual(first, second)

    def test_different_input_different_checksum(self):
        generator = FeatureChecksumGenerator()
        context = self.context()

        first = generator.generate(self.output(value=10.5), context)
        second = generator.generate(self.output(value=10.6), context)

        self.assertNotEqual(first, second)

    def test_artifact_generation_success(self):
        artifact = FeatureArtifactGenerator().generate(
            self.output(),
            self.context(),
            expected_symbols=("2330.TW",),
        )

        self.assertEqual(artifact.feature_id, "TECH_SMA20_V1")
        self.assertEqual(artifact.feature_version, "v1")
        self.assertEqual(artifact.snapshot_id, self.context().snapshot_id)
        self.assertEqual(artifact.calculation_id, self.context().calculation_id)
        self.assertEqual(artifact.validation_status, "PASS")
        self.assertTrue(artifact.checksum)

    def test_invalid_validation_prevents_artifact(self):
        with self.assertRaisesRegex(ArtifactGenerationError, "validation failed"):
            FeatureArtifactGenerator().generate(
                self.output(feature_id="TECH_RSI14_V1", value=120.0),
                self.context(),
            )

    def test_artifact_metadata_correctness(self):
        context = self.context(as_of_date=date(2026, 1, 20))
        artifact = FeatureArtifactGenerator().generate(self.output(feature_date=date(2026, 1, 20)), context)

        self.assertEqual(artifact.created_at.isoformat(), "2026-01-20T00:00:00+00:00")
        self.assertEqual(artifact.validation_status, "PASS")
        self.assertIsNotNone(artifact.checksum)

    def test_technical_calculators_integrate_with_validation_checksum_artifact_flow(self):
        context = self.context()
        calculators = [
            SMA20Calculator(self.price_series()),
            SMA60Calculator(self.price_series()),
            RSI14Calculator(self.price_series()),
            VolumeRatioCalculator(self.price_series(count=80)),
        ]
        generator = FeatureArtifactGenerator()

        artifacts = tuple(generator.generate(calculator.calculate(context), context) for calculator in calculators)

        self.assertEqual(
            tuple(artifact.feature_id for artifact in artifacts),
            ("TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1", "TECH_VOLUME_RATIO_V1"),
        )
        self.assertTrue(all(artifact.validation_status == "PASS" for artifact in artifacts))
        self.assertTrue(all(artifact.checksum for artifact in artifacts))

    def test_validation_modules_do_not_import_existing_runtime_boundaries(self):
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
