import sys
import unittest
from datetime import date
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from features.calculators import PriceVolumePoint
from risk_oos import EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY
from risk_oos import EXCLUSION_INVALID_PRICE
from risk_oos import EXCLUSION_MISSING_AS_OF_CLOSE
from risk_oos import HISTORICAL_RISK_FEATURE_SET_V1
from risk_oos import HistoricalRiskFeatureMaterializationContext
from risk_oos import HistoricalRiskFeatureMaterializationError
from risk_oos import HistoricalRiskFeatureMaterializer
from risk_oos import HistoricalRiskFeatureStatus


class HistoricalRiskFeatureMaterializationTestCase(unittest.TestCase):

    def context(self, **overrides):
        values = {
            "symbol": "2330.TW",
            "evaluation_date": date(2026, 3, 31),
            "source_snapshot_id": "frozen_price_snapshot_v1",
            "source_snapshot_checksum": "snapshot_checksum_001",
            "feature_set_id": "technical_risk_v1_required_features",
            "calculation_id": "historical_risk_feature_calc_001",
        }
        values.update(overrides)
        return HistoricalRiskFeatureMaterializationContext(**values)

    def price_series(self, count=80, start=date(2026, 1, 11), symbol="2330.TW"):
        return tuple(
            PriceVolumePoint(
                symbol=symbol,
                trading_date=start + timedelta(days=index),
                close=float(index + 1),
                volume=float((index + 1) * 100),
            )
            for index in range(count)
        )

    def materialize(self, points=None, **context_overrides):
        active_points = self.price_series() if points is None else points
        return HistoricalRiskFeatureMaterializer(active_points).materialize(self.context(**context_overrides))

    def test_valid_observation_preserves_required_numeric_values(self):
        result = self.materialize()

        self.assertEqual(result.status, HistoricalRiskFeatureStatus.INCLUDED)
        observation = result.observation
        self.assertEqual(observation.symbol, "2330.TW")
        self.assertEqual(observation.evaluation_date, date(2026, 3, 31))
        self.assertEqual(observation.feature_ids, HISTORICAL_RISK_FEATURE_SET_V1)
        self.assertEqual(observation.as_of_close, 80.0)
        self.assertEqual(observation.sma20, 70.5)
        self.assertEqual(observation.sma60, 50.5)
        self.assertAlmostEqual(observation.rsi14, 100.0)

    def test_exact_feature_set_and_volume_ratio_excluded(self):
        context = self.context(requested_features=tuple(reversed(HISTORICAL_RISK_FEATURE_SET_V1)))

        self.assertEqual(context.requested_features, HISTORICAL_RISK_FEATURE_SET_V1)
        with self.assertRaisesRegex(HistoricalRiskFeatureMaterializationError, "exactly match"):
            self.context(requested_features=(*HISTORICAL_RISK_FEATURE_SET_V1, "TECH_VOLUME_RATIO_V1"))

    def test_as_of_close_requires_exact_evaluation_date(self):
        points = tuple(point for point in self.price_series() if point.trading_date != date(2026, 3, 31))

        result = self.materialize(points)

        self.assertEqual(result.status, HistoricalRiskFeatureStatus.EXCLUDED)
        self.assertEqual(result.exclusion.reason, EXCLUSION_MISSING_AS_OF_CLOSE)

    def test_future_bars_ignored(self):
        base = self.price_series()
        future = tuple(
            PriceVolumePoint("2330.TW", date(2026, 4, 1) + timedelta(days=index), 10000.0 + index, 1.0)
            for index in range(30)
        )

        first = self.materialize(base).observation
        second = self.materialize((*base, *future)).observation

        self.assertEqual(first.as_of_close, second.as_of_close)
        self.assertEqual(first.sma20, second.sma20)
        self.assertEqual(first.sma60, second.sma60)
        self.assertEqual(first.rsi14, second.rsi14)
        self.assertEqual(first.observation_id, second.observation_id)
        self.assertEqual(first.observation_checksum, second.observation_checksum)

    def test_symbol_isolation(self):
        other_symbol = self.price_series(symbol="9999.TW")
        result = self.materialize((*other_symbol, *self.price_series()))

        self.assertEqual(result.observation.symbol, "2330.TW")
        self.assertEqual(result.observation.as_of_close, 80.0)

    def test_insufficient_sma20_history(self):
        result = self.materialize(self.price_series(count=19), evaluation_date=date(2026, 1, 29))

        self.assertEqual(result.status, HistoricalRiskFeatureStatus.EXCLUDED)
        self.assertEqual(result.exclusion.reason, EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY)
        self.assertEqual(result.exclusion.feature_id, "TECH_SMA20_V1")

    def test_insufficient_sma60_history(self):
        result = self.materialize(self.price_series(count=59), evaluation_date=date(2026, 3, 10))

        self.assertEqual(result.status, HistoricalRiskFeatureStatus.EXCLUDED)
        self.assertEqual(result.exclusion.reason, EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY)
        self.assertEqual(result.exclusion.feature_id, "TECH_SMA60_V1")

    def test_insufficient_rsi_history(self):
        points = self.price_series(count=14)
        result = self.materialize(points, evaluation_date=date(2026, 1, 24))

        self.assertEqual(result.status, HistoricalRiskFeatureStatus.EXCLUDED)
        self.assertEqual(result.exclusion.reason, EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY)
        self.assertEqual(result.exclusion.feature_id, "TECH_RSI14_V1")

    def test_invalid_close_rejected(self):
        points = tuple(
            PriceVolumePoint(point.symbol, point.trading_date, 0.0 if point.trading_date == date(2026, 3, 31) else point.close, point.volume)
            for point in self.price_series()
        )

        result = self.materialize(points)

        self.assertEqual(result.status, HistoricalRiskFeatureStatus.EXCLUDED)
        self.assertEqual(result.exclusion.reason, EXCLUSION_INVALID_PRICE)

    def test_bool_close_rejected(self):
        points = tuple(
            PriceVolumePoint(point.symbol, point.trading_date, True if point.trading_date == date(2026, 3, 31) else point.close, point.volume)
            for point in self.price_series()
        )

        result = self.materialize(points)

        self.assertEqual(result.exclusion.reason, EXCLUSION_INVALID_PRICE)

    def test_deterministic_observation_id_and_output(self):
        first = self.materialize()
        second = self.materialize(tuple(reversed(self.price_series())))

        self.assertEqual(first, second)
        self.assertEqual(first.observation.observation_id, second.observation.observation_id)
        self.assertEqual(first.observation.observation_checksum, second.observation.observation_checksum)

    def test_source_lineage_preserved(self):
        observation = self.materialize().observation

        self.assertEqual(observation.source_snapshot_id, "frozen_price_snapshot_v1")
        self.assertEqual(observation.source_snapshot_checksum, "snapshot_checksum_001")
        self.assertEqual(observation.calculation_id, "historical_risk_feature_calc_001")
        self.assertEqual(observation.feature_versions["TECH_AS_OF_CLOSE_V1"], "v1")
        self.assertEqual(observation.formula_versions["TECH_SMA20_V1"], "SMA20_v1")

    def test_no_fake_portfolio_position_or_split_identity(self):
        observation = self.materialize().observation
        identity_text = observation.observation_id

        self.assertFalse(hasattr(observation, "portfolio_id"))
        self.assertFalse(hasattr(observation, "position_id"))
        self.assertFalse(hasattr(observation, "split_id"))
        self.assertNotIn("development", identity_text)
        self.assertNotIn("validation", identity_text)
        self.assertNotIn("holdout", identity_text)

    def test_no_db_yfinance_or_runtime_lookup_boundary(self):
        source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "risk_oos").glob("*.py"))
        )

        forbidden = (
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "pdf_export",
            "open(",
            "read_text",
            "write_text",
            "TechnicalRiskSignalProducer",
            "RiskSeverity",
        )
        for term in forbidden:
            self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
