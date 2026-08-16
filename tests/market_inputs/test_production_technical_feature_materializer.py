import math
from unittest import mock
import sys
import unittest
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from features import FeatureCalculationContext
from features import FeatureCalculationOutput
from features.calculators import PriceVolumePoint
from features.calculators import RSI14Calculator
from features.calculators import SMA20Calculator
from features.calculators import SMA60Calculator
from market_inputs import ProductionTechnicalFeatureMaterializer
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalFeatureMaterializationError
from market_inputs import YAHOO_FINANCE_PROVIDER_ID_V1
from market_inputs import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1
from market_inputs.production_technical_feature_materializer import REQUIRED_TECHNICAL_FEATURE_OBSERVATIONS_V1
from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_ID


class FakeNonFiniteRSI14Calculator:
    feature_id = TECH_RSI14_FEATURE_ID

    def __init__(self, price_points):
        self.price_points = price_points

    def calculate(self, context):
        return FeatureCalculationOutput(
            feature_id=TECH_RSI14_FEATURE_ID,
            feature_version="v1",
            values=(
                {
                    "symbol": self.price_points[-1].symbol,
                    "date": context.as_of_date,
                    "feature_id": TECH_RSI14_FEATURE_ID,
                    "feature_version": "v1",
                    "feature_value": math.inf,
                },
            ),
            metadata={"validation_status": "PASS"},
        )

    def validate(self, output):
        return True


class ProductionTechnicalFeatureMaterializerTestCase(unittest.TestCase):

    def observation(self, market_session_date, technical_close):
        return TechnicalCloseObservation(
            market_session_date=market_session_date,
            technical_close=technical_close,
        )

    def series(self, *, closes=None, start=date(2026, 1, 1), valuation_date=None, fetched_at=None, **overrides):
        closes = closes if closes is not None else tuple(float(index + 1) for index in range(60))
        observations = tuple(
            self.observation(start + timedelta(days=index), close)
            for index, close in enumerate(closes)
        )
        values = {
            "symbol": "2330.TW",
            "provider": YAHOO_FINANCE_PROVIDER_ID_V1,
            "provider_symbol": "2330.TW",
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "valuation_date": valuation_date or observations[-1].market_session_date,
            "observations": observations,
            "fetched_at": fetched_at or datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
            "producer_version": YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1,
        }
        values.update(overrides)
        return TechnicalCloseObservationSeries(**values)

    def materializer(self):
        return ProductionTechnicalFeatureMaterializer()

    def test_materializes_exact_technical_risk_v1_feature_bundle(self):
        series = self.series(closes=tuple(float(100 + index) for index in range(60)))
        bundle = self.materializer().materialize(series)

        self.assertEqual(bundle.symbol, series.symbol)
        self.assertEqual(bundle.valuation_date, series.valuation_date)
        self.assertEqual(bundle.market_revision_id, series.market_revision_id)
        self.assertEqual(bundle.features[TECH_AS_OF_CLOSE_FEATURE_ID], 159.0)
        self.assertEqual(tuple(bundle.features), tuple(sorted(bundle.features)))
        self.assertEqual(
            set(bundle.features),
            {TECH_AS_OF_CLOSE_FEATURE_ID, TECH_SMA20_FEATURE_ID, TECH_SMA60_FEATURE_ID, TECH_RSI14_FEATURE_ID},
        )
        self.assertTrue(bundle.effective_observation_checksum.startswith("technical_effective_observations_"))
        self.assertTrue(bundle.feature_bundle_checksum.startswith("technical_feature_bundle_"))

    def test_existing_calculators_are_source_of_truth_for_sma_and_rsi(self):
        series = self.series(closes=tuple(float(100 + index) for index in range(80)))
        bundle = self.materializer().materialize(series)
        effective_closes = tuple(float(120 + index) for index in range(60))
        price_points = tuple(
            PriceVolumePoint(
                symbol=series.symbol,
                trading_date=series.observations[index + 20].market_session_date,
                close=effective_closes[index],
            )
            for index in range(60)
        )
        calculation_context = FeatureCalculationContext(
            snapshot_id=series.market_revision_id,
            snapshot_version=bundle.effective_observation_checksum,
            universe_id="production_technical_feature_bundle_v1",
            as_of_date=series.valuation_date,
            calculation_id=f"technical_feature_materializer_{series.market_revision_id}",
            data_source=series.producer_version,
            lineage={"market_revision_id": series.market_revision_id},
        )
        expected_sma20 = SMA20Calculator(price_points).calculate(calculation_context).values[0]["feature_value"]
        expected_sma60 = SMA60Calculator(price_points).calculate(calculation_context).values[0]["feature_value"]
        expected_rsi14 = RSI14Calculator(price_points).calculate(calculation_context).values[0]["feature_value"]

        self.assertEqual(bundle.features[TECH_SMA20_FEATURE_ID], expected_sma20)
        self.assertEqual(bundle.features[TECH_SMA60_FEATURE_ID], expected_sma60)
        self.assertEqual(bundle.features[TECH_RSI14_FEATURE_ID], expected_rsi14)

    def test_rsi_edge_cases_match_existing_calculator_semantics(self):
        flat = self.materializer().materialize(self.series(closes=(10.0,) * 60))
        gains = self.materializer().materialize(self.series(closes=tuple(float(index + 1) for index in range(60))))
        losses = self.materializer().materialize(self.series(closes=tuple(float(60 - index) for index in range(60))))

        self.assertEqual(flat.features[TECH_RSI14_FEATURE_ID], 50.0)
        self.assertEqual(gains.features[TECH_RSI14_FEATURE_ID], 100.0)
        self.assertEqual(losses.features[TECH_RSI14_FEATURE_ID], 0.0)

    def test_requires_full_trailing_sixty_observations_and_valuation_date_at_window_end(self):
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "insufficient"):
            self.materializer().materialize(self.series(closes=tuple(float(index + 1) for index in range(59))))

    def test_older_observation_outside_effective_window_does_not_change_feature_bundle(self):
        base_closes = tuple(float(index + 1) for index in range(65))
        changed_old_close = (999.0,) + base_closes[1:]

        base = self.materializer().materialize(self.series(closes=base_closes))
        changed = self.materializer().materialize(self.series(closes=changed_old_close))

        self.assertNotEqual(base.market_revision_id, changed.market_revision_id)
        self.assertEqual(base.effective_observation_checksum, changed.effective_observation_checksum)
        self.assertEqual(base.feature_bundle_checksum, changed.feature_bundle_checksum)

    def test_relevant_trailing_close_changes_effective_and_bundle_checksums(self):
        base_closes = tuple(float(index + 1) for index in range(65))
        changed_recent_close = base_closes[:-1] + (999.0,)

        base = self.materializer().materialize(self.series(closes=base_closes))
        changed = self.materializer().materialize(self.series(closes=changed_recent_close))

        self.assertNotEqual(base.effective_observation_checksum, changed.effective_observation_checksum)
        self.assertNotEqual(base.feature_bundle_checksum, changed.feature_bundle_checksum)

    def test_fetched_at_and_source_order_do_not_change_bundle_checksum(self):
        first_series = self.series(closes=tuple(float(index + 1) for index in range(60)))
        second_series = self.series(
            closes=tuple(float(index + 1) for index in range(60)),
            fetched_at=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc),
            observations=tuple(reversed(first_series.observations)),
        )

        first = self.materializer().materialize(first_series)
        second = self.materializer().materialize(second_series)

        self.assertEqual(first.effective_observation_checksum, second.effective_observation_checksum)
        self.assertEqual(first.feature_bundle_checksum, second.feature_bundle_checksum)

    def test_valuation_date_changes_effective_and_bundle_checksums(self):
        closes = tuple(float(index + 1) for index in range(61))
        first = self.materializer().materialize(self.series(closes=closes[:-1]))
        second = self.materializer().materialize(self.series(closes=closes))

        self.assertNotEqual(first.effective_observation_checksum, second.effective_observation_checksum)
        self.assertNotEqual(first.feature_bundle_checksum, second.feature_bundle_checksum)

    def test_calculator_non_finite_result_fails_closed(self):
        with mock.patch(
            "market_inputs.production_technical_feature_materializer.RSI14Calculator",
            FakeNonFiniteRSI14Calculator,
        ):
            with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "finite"):
                self.materializer().materialize(self.series())

    def test_invalid_materializer_version_and_input_type_fail_closed(self):
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "Unsupported"):
            ProductionTechnicalFeatureMaterializer(feature_materializer_version="OTHER_VERSION")
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "TechnicalCloseObservationSeries"):
            self.materializer().materialize(object())

    def test_boundary_no_runtime_io_policy_or_feature_set_contract(self):
        source = (SRC_PATH / "market_inputs" / "production_technical_feature_materializer.py").read_text()
        bundle_source = (SRC_PATH / "market_inputs" / "technical_feature_bundle.py").read_text()
        combined = source + "\n" + bundle_source

        forbidden = (
            "yfinance",
            "sqlite3",
            "open(",
            "write_text",
            "read_text",
            "ProductionMarketInputConfig",
            "RiskEvaluationInput",
            "RiskSignalProductionInput",
            "TechnicalFeatureSet",
            "technical_feature_set_checksum",
            "PortfolioRiskGenerationService",
            "datetime.now",
            "datetime.utcnow",
            "time.time",
        )
        for term in forbidden:
            self.assertNotIn(term, combined)
        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())

    def test_window_size_constant_is_sixty(self):
        self.assertEqual(REQUIRED_TECHNICAL_FEATURE_OBSERVATIONS_V1, 60)


if __name__ == "__main__":
    unittest.main()
