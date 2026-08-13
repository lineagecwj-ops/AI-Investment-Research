import sys
import unittest
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from targets import FutureReturn20DRegressionGenerator
from targets import FutureReturn60DClassificationGenerator
from targets import FutureReturn60DRegressionGenerator
from targets import MaximumAdverseExcursion20DRegressionGenerator
from targets import MaximumAdverseExcursion60DRegressionGenerator
from targets import TARGET_ARTIFACT_SCHEMA_VERSION
from targets import TARGET_CHECKSUM_CONTRACT_VERSION
from targets import TargetArtifact
from targets import TargetArtifactGenerationError
from targets import TargetArtifactGenerator
from targets import TargetCalculationContext
from targets import TargetChecksumGenerator
from targets import TargetDefinition
from targets import TargetGenerationOutput
from targets import TargetPricePoint
from targets import TargetRegistry
from targets import TargetRegistryError
from targets import TargetWindowLineage


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

    def prices_from_values(self, values, start=date(2026, 1, 1), symbol="2330.TW"):
        return tuple(
            TargetPricePoint(symbol, start + timedelta(days=index), value)
            for index, value in enumerate(values)
        )

    def test_target_definition_creation(self):
        definition = FutureReturn20DRegressionGenerator(()).get_definition()

        self.assertEqual(definition.target_id, "TARGET_RETURN_20D_REG_V1")
        self.assertEqual(definition.target_type, "Regression")
        self.assertEqual(definition.version, "v1")
        self.assertEqual(definition.calculation_window, 20)
        self.assertTrue(definition.formula_version)
        self.assertTrue(definition.requires_window_lineage)

    def test_mae_target_definitions(self):
        definition_20d = MaximumAdverseExcursion20DRegressionGenerator(()).get_definition()
        definition_60d = MaximumAdverseExcursion60DRegressionGenerator(()).get_definition()

        self.assertEqual(definition_20d.target_id, "TARGET_MAE_20D_REG_V1")
        self.assertEqual(definition_20d.target_type, "Regression")
        self.assertEqual(definition_20d.version, "v1")
        self.assertEqual(definition_20d.calculation_window, 20)
        self.assertEqual(definition_20d.formula_version, "mae_20d_close_v1")
        self.assertTrue(definition_20d.requires_window_lineage)
        self.assertIn("close-based maximum adverse excursion", definition_20d.description)
        self.assertEqual(definition_60d.target_id, "TARGET_MAE_60D_REG_V1")
        self.assertEqual(definition_60d.target_type, "Regression")
        self.assertEqual(definition_60d.version, "v1")
        self.assertEqual(definition_60d.calculation_window, 60)
        self.assertEqual(definition_60d.formula_version, "mae_60d_close_v1")
        self.assertTrue(definition_60d.requires_window_lineage)

    def test_target_registry_registration(self):
        registry = TargetRegistry()
        generators = [
            MaximumAdverseExcursion20DRegressionGenerator(self.prices()),
            MaximumAdverseExcursion60DRegressionGenerator(self.prices()),
            FutureReturn20DRegressionGenerator(self.prices()),
            FutureReturn60DRegressionGenerator(self.prices()),
            FutureReturn60DClassificationGenerator(self.prices()),
        ]

        registry.register_many(generators)

        self.assertEqual(
            registry.list_targets(),
            (
                "TARGET_MAE_20D_REG_V1:v1",
                "TARGET_MAE_60D_REG_V1:v1",
                "TARGET_RETURN_20D_REG_V1:v1",
                "TARGET_RETURN_60D_CLASS_V1:v1",
                "TARGET_RETURN_60D_REG_V1:v1",
            ),
        )
        self.assertIs(registry.get_generator("TARGET_MAE_20D_REG_V1", "v1"), generators[0])

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
        self.assertEqual(output.window_lineage.target_start_date, date(2026, 1, 2))
        self.assertEqual(output.window_lineage.target_end_date, date(2026, 1, 21))
        self.assertEqual(output.window_lineage.observations_used, 20)
        self.assertEqual(output.artifact.window_lineage, output.window_lineage)

    def test_60d_return_calculation(self):
        generator = FutureReturn60DRegressionGenerator(self.prices())

        output = generator.calculate(self.context(window=60))

        self.assertTrue(generator.validate(output))
        self.assertEqual(output.target_id, "TARGET_RETURN_60D_REG_V1")
        self.assertEqual(output.target_value, 0.6)
        self.assertEqual(output.window_lineage.target_start_date, date(2026, 1, 2))
        self.assertEqual(output.window_lineage.target_end_date, date(2026, 3, 2))
        self.assertEqual(output.window_lineage.observations_used, 60)

    def test_20d_mae_calculation_uses_worst_future_close(self):
        prices = self.prices_from_values(
            (100.0, 98.0, 95.0, 82.0, 101.0, *([105.0] * 16))
        )
        generator = MaximumAdverseExcursion20DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=20))

        self.assertTrue(generator.validate(output))
        self.assertEqual(output.target_id, "TARGET_MAE_20D_REG_V1")
        self.assertAlmostEqual(output.target_value, -0.18)
        self.assertEqual(output.metadata["worst_future_price"], 82.0)
        self.assertEqual(output.metadata["window_observations"], 20)
        self.assertEqual(output.window_lineage.target_start_date, date(2026, 1, 2))
        self.assertEqual(output.window_lineage.target_end_date, date(2026, 1, 21))
        self.assertEqual(output.window_lineage.observations_used, 20)
        self.assertEqual(output.artifact.window_lineage, output.window_lineage)

    def test_60d_mae_calculation(self):
        prices = self.prices_from_values((100.0, *([101.0] * 20), 70.0, *([102.0] * 39)))
        generator = MaximumAdverseExcursion60DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=60))

        self.assertTrue(generator.validate(output))
        self.assertEqual(output.target_id, "TARGET_MAE_60D_REG_V1")
        self.assertAlmostEqual(output.target_value, -0.3)
        self.assertEqual(output.metadata["worst_future_price"], 70.0)
        self.assertEqual(output.window_lineage.observations_used, 60)
        self.assertEqual(output.window_lineage.target_end_date, date(2026, 3, 2))

    def test_60d_mae_favorable_only_path_is_zero(self):
        prices = self.prices_from_values((100.0, *([103.0] * 60)))
        generator = MaximumAdverseExcursion60DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=60))

        self.assertEqual(output.target_value, 0.0)
        self.assertAlmostEqual(output.metadata["raw_min_return"], 0.03)

    def test_mae_reference_day_excluded(self):
        prices = self.prices_from_values((50.0, *([100.0] * 20)))
        generator = MaximumAdverseExcursion20DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=20))

        self.assertEqual(output.target_value, 0.0)
        self.assertAlmostEqual(output.metadata["raw_min_return"], 1.0)
        self.assertEqual(output.metadata["future_window_start"], "2026-01-02")
        self.assertEqual(output.window_lineage.target_start_date, date(2026, 1, 2))

    def test_mae_all_future_closes_above_reference_is_zero(self):
        prices = self.prices_from_values((100.0, *([101.0] * 20)))
        output = MaximumAdverseExcursion20DRegressionGenerator(prices).calculate(self.context(window=20))

        self.assertEqual(output.target_value, 0.0)
        self.assertAlmostEqual(output.metadata["raw_min_return"], 0.01)

    def test_mae_equal_reference_close_is_zero_unless_below_reference_exists(self):
        equal_only = MaximumAdverseExcursion20DRegressionGenerator(
            self.prices_from_values((100.0, 100.0, *([101.0] * 19)))
        ).calculate(self.context(window=20))
        downside = MaximumAdverseExcursion20DRegressionGenerator(
            self.prices_from_values((100.0, 100.0, *([101.0] * 5), 94.0, *([102.0] * 13)))
        ).calculate(self.context(window=20))

        self.assertEqual(equal_only.target_value, 0.0)
        self.assertAlmostEqual(downside.target_value, -0.06)
        self.assertAlmostEqual(downside.metadata["raw_min_return"], -0.06)

    def test_60d_classification(self):
        positive = FutureReturn60DClassificationGenerator(self.prices(start_price=100.0, step=1.0))
        neutral = FutureReturn60DClassificationGenerator(self.prices(start_price=100.0, step=0.0))
        negative = FutureReturn60DClassificationGenerator(self.prices(start_price=100.0, step=-0.2))

        self.assertEqual(positive.calculate(self.context(window=60)).target_value, "Positive")
        self.assertEqual(neutral.calculate(self.context(window=60)).target_value, "Neutral")
        self.assertEqual(negative.calculate(self.context(window=60)).target_value, "Negative")
        self.assertEqual(positive.calculate(self.context(window=60)).window_lineage.observations_used, 60)

    def test_missing_future_window_rejection(self):
        generator = FutureReturn20DRegressionGenerator(self.prices(count=20))

        output = generator.calculate(self.context(window=20))

        self.assertFalse(generator.validate(output))
        self.assertIsNone(output.target_value)
        self.assertIsNone(output.window_lineage)
        self.assertIsNone(output.artifact)
        self.assertEqual(output.metadata["validation_status"], "INSUFFICIENT_FUTURE_DATA")

    def test_mae_insufficient_future_windows(self):
        output_20d = MaximumAdverseExcursion20DRegressionGenerator(self.prices(count=20)).calculate(self.context(window=20))
        output_60d = MaximumAdverseExcursion60DRegressionGenerator(self.prices(count=60)).calculate(self.context(window=60))

        self.assertEqual(output_20d.metadata["validation_status"], "INSUFFICIENT_FUTURE_DATA")
        self.assertEqual(output_60d.metadata["validation_status"], "INSUFFICIENT_FUTURE_DATA")
        self.assertIsNone(output_20d.artifact)
        self.assertIsNone(output_60d.artifact)

    def test_invalid_price_rejection(self):
        prices = (
            TargetPricePoint("2330.TW", date(2026, 1, 1), 0.0),
            *self.prices(count=21, start=date(2026, 1, 2)),
        )
        generator = FutureReturn20DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=20))

        self.assertFalse(generator.validate(output))
        self.assertIsNone(output.artifact)
        self.assertIsNone(output.window_lineage)
        self.assertEqual(output.metadata["validation_status"], "INVALID_PRICE")

    def test_mae_invalid_reference_and_future_close_rejection(self):
        invalid_reference = MaximumAdverseExcursion20DRegressionGenerator(
            self.prices_from_values((0.0, *([100.0] * 20)))
        ).calculate(self.context(window=20))
        invalid_future = MaximumAdverseExcursion20DRegressionGenerator(
            self.prices_from_values((100.0, *([101.0] * 5), -1.0, *([102.0] * 14)))
        ).calculate(self.context(window=20))
        non_numeric_future = MaximumAdverseExcursion20DRegressionGenerator(
            self.prices_from_values((100.0, *([101.0] * 5), "bad", *([102.0] * 14)))
        ).calculate(self.context(window=20))

        self.assertEqual(invalid_reference.metadata["validation_status"], "INVALID_PRICE")
        self.assertEqual(invalid_future.metadata["validation_status"], "INVALID_PRICE")
        self.assertEqual(non_numeric_future.metadata["validation_status"], "INVALID_PRICE")

    def test_mae_missing_future_close_is_insufficient_data(self):
        prices = self.prices_from_values((100.0, *([101.0] * 5), None, *([102.0] * 14)))
        generator = MaximumAdverseExcursion20DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=20))

        self.assertEqual(output.metadata["validation_status"], "INSUFFICIENT_FUTURE_DATA")
        self.assertEqual(output.metadata["reason"], "missing future close")

    def test_mae_duplicate_dates_fail_closed(self):
        prices = (
            TargetPricePoint("2330.TW", date(2026, 1, 1), 100.0),
            TargetPricePoint("2330.TW", date(2026, 1, 2), 98.0),
            TargetPricePoint("2330.TW", date(2026, 1, 2), 97.0),
            *self.prices(count=19, start=date(2026, 1, 3), start_price=100.0),
        )
        generator = MaximumAdverseExcursion20DRegressionGenerator(prices)

        output = generator.calculate(self.context(window=20))

        self.assertEqual(output.metadata["validation_status"], "INSUFFICIENT_FUTURE_DATA")
        self.assertEqual(output.metadata["reason"], "duplicate trading_date")

    def test_mae_non_monotonic_input_is_deterministically_ordered(self):
        ordered_prices = self.prices_from_values((100.0, 98.0, 95.0, *([110.0] * 18)))
        non_monotonic_prices = tuple(reversed(ordered_prices))
        context = self.context(window=20)

        ordered = MaximumAdverseExcursion20DRegressionGenerator(ordered_prices).calculate(context)
        non_monotonic = MaximumAdverseExcursion20DRegressionGenerator(non_monotonic_prices).calculate(context)

        self.assertEqual(ordered.target_value, non_monotonic.target_value)
        self.assertEqual(ordered.metadata["worst_future_date"], non_monotonic.metadata["worst_future_date"])
        self.assertEqual(ordered.window_lineage, non_monotonic.window_lineage)

    def test_mae_symbol_isolation(self):
        target_symbol_prices = self.prices_from_values((100.0, *([99.0] * 20)), symbol="2330.TW")
        other_symbol_prices = self.prices_from_values((100.0, *([1.0] * 20)), symbol="9999.TW")
        generator = MaximumAdverseExcursion20DRegressionGenerator((*other_symbol_prices, *target_symbol_prices))

        output = generator.calculate(self.context(window=20, symbol="2330.TW"))

        self.assertAlmostEqual(output.target_value, -0.01)
        self.assertEqual(output.symbol, "2330.TW")

    def test_window_lineage_uses_actual_trading_observation_dates_not_calendar_days(self):
        prices = (
            TargetPricePoint("2330.TW", date(2026, 1, 2), 100.0),
            TargetPricePoint("2330.TW", date(2026, 1, 5), 101.0),
            TargetPricePoint("2330.TW", date(2026, 1, 8), 102.0),
            TargetPricePoint("2330.TW", date(2026, 1, 15), 103.0),
        )
        context = self.context(window=3, reference_date=date(2026, 1, 2))
        output = FutureReturn20DRegressionGenerator(prices).calculate(context)

        self.assertEqual(output.metadata["validation_status"], "INSUFFICIENT_FUTURE_DATA")
        self.assertIsNone(output.window_lineage)

        class ThreeObservationReturnGenerator(FutureReturn20DRegressionGenerator):
            calculation_window = 3

        output = ThreeObservationReturnGenerator(prices).calculate(context)

        self.assertEqual(output.window_lineage.target_start_date, date(2026, 1, 5))
        self.assertEqual(output.window_lineage.target_end_date, date(2026, 1, 15))
        self.assertEqual(output.window_lineage.observations_used, 3)

    def test_checksum_deterministic(self):
        generator = FutureReturn20DRegressionGenerator(self.prices())
        context = self.context(window=20)
        output = generator.calculate(context)
        checksum = TargetChecksumGenerator()

        self.assertEqual(checksum.generate(output, context), checksum.generate(output, context))

    def test_checksum_v2_protects_window_lineage_and_calculation_id(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices()).calculate(context)
        checksum = TargetChecksumGenerator()
        baseline = checksum.generate(output, context)

        changed_start = TargetWindowLineage(
            target_start_date=date(2026, 1, 3),
            target_end_date=output.window_lineage.target_end_date,
            observations_used=output.window_lineage.observations_used,
        )
        changed_end = TargetWindowLineage(
            target_start_date=output.window_lineage.target_start_date,
            target_end_date=date(2026, 1, 22),
            observations_used=output.window_lineage.observations_used,
        )
        changed_observations = TargetWindowLineage(
            target_start_date=output.window_lineage.target_start_date,
            target_end_date=output.window_lineage.target_end_date,
            observations_used=19,
        )
        changed_context = replace(context, calculation_id="different_calc")

        self.assertNotEqual(baseline, checksum.generate(self.output_with_lineage(output, changed_start), context))
        self.assertNotEqual(baseline, checksum.generate(self.output_with_lineage(output, changed_end), context))
        self.assertNotEqual(baseline, checksum.generate(self.output_with_lineage(output, changed_observations), context))
        self.assertNotEqual(baseline, checksum.generate(output, changed_context))

    def test_mae_checksum_deterministic(self):
        generator = MaximumAdverseExcursion20DRegressionGenerator(self.prices_from_values((100.0, 98.0, *([105.0] * 19))))
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
        self.assertEqual(artifact.window_lineage, output.window_lineage)
        self.assertEqual(artifact.schema_version, TARGET_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(artifact.checksum_contract_version, TARGET_CHECKSUM_CONTRACT_VERSION)

    def test_mae_artifact_generation_and_validator_compatibility(self):
        context = self.context(window=20)
        output = MaximumAdverseExcursion20DRegressionGenerator(
            self.prices_from_values((100.0, 98.0, *([105.0] * 19)))
        ).calculate(context)

        artifact = TargetArtifactGenerator().generate(output, context)

        self.assertEqual(artifact.target_id, "TARGET_MAE_20D_REG_V1")
        self.assertEqual(artifact.target_version, "v1")
        self.assertEqual(artifact.symbol, "2330.TW")
        self.assertEqual(artifact.reference_date, date(2026, 1, 1))
        self.assertAlmostEqual(artifact.target_value, -0.02)
        self.assertEqual(artifact.validation_status, "PASS")
        self.assertTrue(artifact.checksum)
        self.assertEqual(artifact.window_lineage, output.window_lineage)
        self.assertEqual(artifact.window_lineage.target_start_date, date(2026, 1, 2))
        self.assertEqual(artifact.window_lineage.target_end_date, date(2026, 1, 21))

    def test_mae_artifact_generation_uses_zero_floor_semantics(self):
        context = self.context(window=20)
        output = MaximumAdverseExcursion20DRegressionGenerator(
            self.prices_from_values((100.0, *([103.0] * 20)))
        ).calculate(context)

        artifact = TargetArtifactGenerator().generate(output, context)

        self.assertEqual(artifact.target_id, "TARGET_MAE_20D_REG_V1")
        self.assertEqual(artifact.target_value, 0.0)
        self.assertEqual(artifact.validation_status, "PASS")

    def test_invalid_target_blocks_artifact(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices(count=20)).calculate(context)

        with self.assertRaisesRegex(TargetArtifactGenerationError, "validation failed"):
            TargetArtifactGenerator().generate(output, context)

    def test_requires_window_lineage_blocks_valid_artifact_without_lineage(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices()).calculate(context)
        output_without_lineage = replace(
            output,
            window_lineage=None,
            artifact=replace(output.artifact, window_lineage=None),
        )

        with self.assertRaisesRegex(TargetArtifactGenerationError, "window lineage"):
            TargetArtifactGenerator().generate(output_without_lineage, context)

    def test_definition_requires_window_lineage_blocks_output_echo_false_without_lineage(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices()).calculate(context)
        mismatched_output = replace(
            output,
            requires_window_lineage=False,
            window_lineage=None,
            artifact=replace(output.artifact, window_lineage=None),
        )

        with self.assertRaisesRegex(TargetArtifactGenerationError, "requirement echo mismatch"):
            TargetArtifactGenerator().generate(mismatched_output, context)

    def test_definition_requires_window_lineage_blocks_output_echo_false_with_lineage(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices()).calculate(context)
        mismatched_output = replace(output, requires_window_lineage=False)

        with self.assertRaisesRegex(TargetArtifactGenerationError, "requirement echo mismatch"):
            TargetArtifactGenerator().generate(mismatched_output, context)

    def test_non_window_definition_blocks_output_echo_true(self):
        context = self.context(window=1)
        definition = TargetDefinition(
            target_id="TARGET_POINT_IN_TIME_V1",
            target_name="Point-in-Time Target",
            target_type="Regression",
            version="v1",
            calculation_window=1,
            formula_version="point_in_time_v1",
            description="Synthetic point-in-time target for contract validation.",
            requires_window_lineage=False,
        )
        output = TargetGenerationOutput(
            target_id=definition.target_id,
            target_version=definition.version,
            symbol="2330.TW",
            reference_date=context.reference_date,
            target_value=0.1,
            metadata={"validation_status": "PASS"},
            requires_window_lineage=True,
            definition=definition,
        )

        with self.assertRaisesRegex(TargetArtifactGenerationError, "requirement echo mismatch"):
            TargetArtifactGenerator().generate(output, context)

    def test_non_window_definition_allows_no_window_lineage(self):
        context = self.context(window=1)
        definition = TargetDefinition(
            target_id="TARGET_POINT_IN_TIME_V1",
            target_name="Point-in-Time Target",
            target_type="Regression",
            version="v1",
            calculation_window=1,
            formula_version="point_in_time_v1",
            description="Synthetic point-in-time target for contract validation.",
            requires_window_lineage=False,
        )
        output = TargetGenerationOutput(
            target_id=definition.target_id,
            target_version=definition.version,
            symbol="2330.TW",
            reference_date=context.reference_date,
            target_value=0.1,
            metadata={"validation_status": "PASS"},
            requires_window_lineage=False,
            definition=definition,
        )

        artifact = TargetArtifactGenerator().generate(output, context)

        self.assertIsNone(artifact.window_lineage)
        self.assertEqual(artifact.checksum_contract_version, TARGET_CHECKSUM_CONTRACT_VERSION)

    def test_artifact_generation_requires_definition(self):
        context = self.context(window=1)
        output = TargetGenerationOutput(
            target_id="TARGET_POINT_IN_TIME_V1",
            target_version="v1",
            symbol="2330.TW",
            reference_date=context.reference_date,
            target_value=0.1,
            metadata={"validation_status": "PASS"},
            requires_window_lineage=False,
        )

        with self.assertRaisesRegex(TargetArtifactGenerationError, "definition is required"):
            TargetArtifactGenerator().generate(output, context)

    def test_artifact_path_fallback_uses_same_window_lineage_contract(self):
        context = self.context(window=20)
        output = FutureReturn20DRegressionGenerator(self.prices()).calculate(context)
        output_without_source_artifact = replace(output, artifact=None)

        artifact = TargetArtifactGenerator().generate(output_without_source_artifact, context)

        self.assertEqual(artifact.window_lineage, output.window_lineage)
        self.assertEqual(artifact.schema_version, TARGET_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(artifact.checksum_contract_version, TARGET_CHECKSUM_CONTRACT_VERSION)
        self.assertEqual(artifact.checksum, TargetChecksumGenerator().generate(output_without_source_artifact, context))

    def test_feature_join_compatibility_metadata(self):
        context = self.context(window=60)
        output = FutureReturn60DRegressionGenerator(self.prices()).calculate(context)

        self.assertEqual(output.symbol, "2330.TW")
        self.assertEqual(output.reference_date, date(2026, 1, 1))
        self.assertEqual(output.metadata["snapshot_id"], context.snapshot_id)
        self.assertEqual(output.metadata["calculation_id"], context.calculation_id)

    def test_metadata_and_first_class_window_lineage_are_consistent(self):
        output = MaximumAdverseExcursion20DRegressionGenerator(self.prices()).calculate(self.context(window=20))

        self.assertEqual(output.metadata["future_window_start"], output.window_lineage.target_start_date.isoformat())
        self.assertEqual(output.metadata["future_window_end"], output.window_lineage.target_end_date.isoformat())
        self.assertEqual(output.metadata["window_observations"], output.window_lineage.observations_used)

    def test_target_window_lineage_validation(self):
        with self.assertRaisesRegex(ValueError, "observations_used"):
            TargetWindowLineage(date(2026, 1, 2), date(2026, 1, 21), 0)
        with self.assertRaisesRegex(ValueError, "after"):
            TargetWindowLineage(date(2026, 1, 21), date(2026, 1, 2), 20)

    def test_legacy_keyword_target_artifact_construction_remains_compatible(self):
        artifact = TargetArtifact(
            target_id="TARGET_RETURN_60D_REG_V1",
            target_version="v1",
            symbol="2330.TW",
            reference_date=date(2026, 1, 1),
            target_value=0.12,
            calculation_id="target_calc",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            checksum="target_checksum",
            validation_status="PASS",
        )

        self.assertIsNone(artifact.window_lineage)
        self.assertEqual(artifact.schema_version, TARGET_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(artifact.checksum_contract_version, TARGET_CHECKSUM_CONTRACT_VERSION)

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

    def output_with_lineage(self, output, lineage):
        return replace(
            output,
            window_lineage=lineage,
            artifact=replace(output.artifact, window_lineage=lineage) if output.artifact is not None else None,
        )


if __name__ == "__main__":
    unittest.main()
