import sys
import unittest
from datetime import date
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from features import FeatureCalculationContext
from features import FeatureRegistry
from features.calculators import PriceVolumePoint
from features.calculators import RSI14Calculator
from features.calculators import SMA20Calculator
from features.calculators import SMA60Calculator
from features.calculators import VolumeRatioCalculator


class TechnicalCalculatorTestCase(unittest.TestCase):

    def context(self, as_of_date=date(2026, 3, 31)):
        return FeatureCalculationContext(
            snapshot_id="research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1",
            snapshot_version="v1",
            universe_id="frozen_twse_218",
            as_of_date=as_of_date,
            calculation_id="calc_phase7d2_technical",
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

    def test_sma20_calculation(self):
        calculator = SMA20Calculator(self.price_series())

        output = calculator.calculate(self.context())

        self.assertTrue(calculator.validate(output))
        self.assertEqual(output.feature_id, "TECH_SMA20_V1")
        self.assertEqual(output.values[0]["symbol"], "2330.TW")
        self.assertEqual(output.values[0]["feature_value"], 70.5)
        self.assertEqual(output.artifact.validation_status, "PASS")

    def test_sma60_calculation(self):
        calculator = SMA60Calculator(self.price_series())

        output = calculator.calculate(self.context())

        self.assertTrue(calculator.validate(output))
        self.assertEqual(output.feature_id, "TECH_SMA60_V1")
        self.assertEqual(output.values[0]["feature_value"], 50.5)

    def test_rsi14_calculation(self):
        closes = [44, 45, 44, 46, 47, 48, 47, 49, 50, 51, 52, 51, 53, 54, 55]
        series = tuple(
            PriceVolumePoint(
                symbol="2330.TW",
                trading_date=date(2026, 1, 1) + timedelta(days=index),
                close=float(close),
                volume=1000.0,
            )
            for index, close in enumerate(closes)
        )
        calculator = RSI14Calculator(series)

        output = calculator.calculate(self.context(as_of_date=date(2026, 1, 15)))

        self.assertTrue(calculator.validate(output))
        self.assertEqual(output.feature_id, "TECH_RSI14_V1")
        self.assertAlmostEqual(output.values[0]["feature_value"], 82.3529411764706)

    def test_volume_ratio_calculation(self):
        series = self.price_series(count=21, start=date(2026, 1, 1))
        calculator = VolumeRatioCalculator(series)

        output = calculator.calculate(self.context(as_of_date=date(2026, 1, 21)))

        self.assertTrue(calculator.validate(output))
        self.assertEqual(output.feature_id, "TECH_VOLUME_RATIO_V1")
        self.assertEqual(output.values[0]["feature_value"], 2.0)

    def test_feature_definition_correct(self):
        definitions = [
            SMA20Calculator(()).get_definition(),
            SMA60Calculator(()).get_definition(),
            RSI14Calculator(()).get_definition(),
            VolumeRatioCalculator(()).get_definition(),
        ]

        self.assertEqual(
            [definition.feature_id for definition in definitions],
            ["TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_RSI14_V1", "TECH_VOLUME_RATIO_V1"],
        )
        for definition in definitions:
            self.assertEqual(definition.category, "Technical")
            self.assertEqual(definition.version, "v1")
            self.assertTrue(definition.formula_version)
            self.assertTrue(definition.dependencies)

    def test_registry_registration(self):
        registry = FeatureRegistry()
        calculators = [
            SMA20Calculator(self.price_series()),
            SMA60Calculator(self.price_series()),
            RSI14Calculator(self.price_series()),
            VolumeRatioCalculator(self.price_series(count=21)),
        ]

        registry.register_many(calculators)

        self.assertEqual(
            registry.list_features(),
            (
                "TECH_RSI14_V1:v1",
                "TECH_SMA20_V1:v1",
                "TECH_SMA60_V1:v1",
                "TECH_VOLUME_RATIO_V1:v1",
            ),
        )

    def test_validation_behavior_rejects_invalid_output(self):
        calculator = RSI14Calculator(())

        output = calculator.calculate(self.context())

        self.assertFalse(calculator.validate(output))
        self.assertEqual(output.metadata["validation_status"], "INSUFFICIENT_HISTORY")

    def test_insufficient_history(self):
        calculator = SMA20Calculator(self.price_series(count=19))

        output = calculator.calculate(self.context(as_of_date=date(2026, 1, 19)))

        self.assertFalse(calculator.validate(output))
        self.assertEqual(output.values, ())
        self.assertEqual(output.metadata["validation_status"], "INSUFFICIENT_HISTORY")

    def test_zero_volume_handling(self):
        series = tuple(
            PriceVolumePoint(
                symbol="2330.TW",
                trading_date=date(2026, 1, 1) + timedelta(days=index),
                close=10.0,
                volume=0.0,
            )
            for index in range(21)
        )
        calculator = VolumeRatioCalculator(series)

        output = calculator.calculate(self.context(as_of_date=date(2026, 1, 21)))

        self.assertFalse(calculator.validate(output))
        self.assertEqual(output.values, ())
        self.assertEqual(output.metadata["validation_status"], "INVALID_INPUT")
        self.assertEqual(output.metadata["reason"], "zero baseline volume")

    def test_deterministic_output_for_same_input_and_context(self):
        calculator = SMA20Calculator(self.price_series())
        context = self.context()

        first = calculator.calculate(context)
        second = calculator.calculate(context)

        self.assertEqual(first, second)

    def test_as_of_date_excludes_future_rows(self):
        calculator = SMA20Calculator(self.price_series(count=30, start=date(2026, 1, 1)))

        output = calculator.calculate(self.context(as_of_date=date(2026, 1, 20)))

        self.assertTrue(calculator.validate(output))
        self.assertEqual(output.values[0]["date"].isoformat(), "2026-01-20")
        self.assertEqual(output.values[0]["feature_value"], 10.5)

    def test_calculators_do_not_import_existing_runtime_boundaries(self):
        calculator_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "features" / "calculators").glob("*.py"))
        )

        forbidden_imports = (
            "live_data_store",
            "swing_scanner_service",
            "swing_scanner_pdf_export_service",
            "yfinance",
            "sqlite3",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, calculator_source)


if __name__ == "__main__":
    unittest.main()
