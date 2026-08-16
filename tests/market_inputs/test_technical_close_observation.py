import math
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import MarketInputValidationError
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSION_V1
from market_inputs import TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1
from market_inputs import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1


class TechnicalCloseObservationContractTestCase(unittest.TestCase):

    def observation(self, market_session_date=date(2026, 8, 14), technical_close=100.25):
        return TechnicalCloseObservation(
            market_session_date=market_session_date,
            technical_close=technical_close,
        )

    def series(self, *, observations=None, fetched_at=None, **overrides):
        values = {
            "symbol": "2330.TW",
            "provider": "Yahoo Finance",
            "provider_symbol": "2330.TW",
            "timezone": "Asia/Taipei",
            "close_basis": TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            "valuation_date": date(2026, 8, 14),
            "observations": observations
            if observations is not None
            else (
                self.observation(date(2026, 8, 12), 98.0),
                self.observation(date(2026, 8, 14), 100.25),
            ),
            "fetched_at": fetched_at or datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
        }
        values.update(overrides)
        return TechnicalCloseObservationSeries(**values)

    def test_valid_single_and_multiple_observations(self):
        single = self.series(observations=(self.observation(),))
        multiple = self.series()

        self.assertEqual(single.market_revision_id[:16], "market_revision_")
        self.assertEqual(multiple.schema_version, TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1)
        self.assertEqual(multiple.producer_version, TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSION_V1)
        self.assertEqual(multiple.close_basis.value, "TECHNICAL_CLOSE_ADJUSTED_FIRST_V1")

    def test_contracts_are_frozen(self):
        series = self.series()

        with self.assertRaises(FrozenInstanceError):
            series.symbol = "changed"

    def test_observations_are_canonical_sorted_by_market_session_date(self):
        series = self.series(
            observations=(
                self.observation(date(2026, 8, 14), 100.25),
                self.observation(date(2026, 8, 12), 98.0),
            )
        )

        self.assertEqual(
            tuple(observation.market_session_date for observation in series.observations),
            (date(2026, 8, 12), date(2026, 8, 14)),
        )

    def test_duplicate_market_session_date_rejected(self):
        with self.assertRaisesRegex(MarketInputValidationError, "duplicate"):
            self.series(
                observations=(
                    self.observation(date(2026, 8, 14), 100.25),
                    self.observation(date(2026, 8, 14), 101.25),
                )
            )

    def test_valuation_date_must_exist_without_fallback(self):
        with self.assertRaisesRegex(MarketInputValidationError, "valuation_date"):
            self.series(
                valuation_date=date(2026, 8, 15),
                observations=(self.observation(date(2026, 8, 14), 100.25),),
            )

    def test_positive_close_only(self):
        for value in (0.0, -1.0):
            with self.subTest(value=value):
                with self.assertRaisesRegex(MarketInputValidationError, "positive"):
                    self.observation(technical_close=value)

    def test_bool_nan_and_infinity_rejected(self):
        for value in (True, math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(MarketInputValidationError):
                    self.observation(technical_close=value)

    def test_datetime_as_market_session_date_rejected(self):
        with self.assertRaisesRegex(MarketInputValidationError, "date"):
            self.observation(market_session_date=datetime(2026, 8, 14, tzinfo=timezone.utc))

    def test_fetched_at_must_be_timezone_aware(self):
        with self.assertRaisesRegex(MarketInputValidationError, "timezone-aware"):
            self.series(fetched_at=datetime(2026, 8, 16, 9, 0))

    def test_same_semantic_series_same_revision(self):
        first = self.series()
        second = self.series(
            observations=tuple(reversed(first.observations)),
            fetched_at=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(first.market_revision_id, second.market_revision_id)

    def test_revision_changes_for_semantic_source_changes(self):
        base = self.series()
        cases = (
            self.series(observations=(self.observation(date(2026, 8, 12), 98.0), self.observation(date(2026, 8, 14), 101.25))),
            self.series(provider="TWSE"),
            self.series(provider_symbol="2330"),
            self.series(timezone="UTC"),
            self.series(close_basis="TECHNICAL_CLOSE_ADJUSTED_FIRST_V1", producer_version="TECHNICAL_CLOSE_OBSERVATION_PRODUCER_V1"),
        )

        self.assertNotEqual(base.market_revision_id, cases[0].market_revision_id)
        self.assertNotEqual(base.market_revision_id, cases[1].market_revision_id)
        self.assertNotEqual(base.market_revision_id, cases[2].market_revision_id)
        self.assertNotEqual(base.market_revision_id, cases[3].market_revision_id)
        self.assertEqual(base.market_revision_id, cases[4].market_revision_id)

    def test_yahoo_source_producer_version_is_valid_and_changes_revision(self):
        generic = self.series()
        yahoo = self.series(producer_version=YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1)

        self.assertEqual(yahoo.producer_version, YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1)
        self.assertNotEqual(generic.market_revision_id, yahoo.market_revision_id)

    def test_unknown_producer_version_rejected(self):
        with self.assertRaisesRegex(MarketInputValidationError, "producer_version"):
            self.series(producer_version="UNKNOWN_PRODUCER_V1")

    def test_close_basis_changes_revision(self):
        with self.assertRaisesRegex(MarketInputValidationError, "close_basis"):
            self.series(close_basis="RAW_CLOSE_V1")

    def test_market_revision_mismatch_rejected(self):
        with self.assertRaisesRegex(MarketInputValidationError, "market_revision_id"):
            self.series(market_revision_id="market_revision_wrong")

    def test_float_canonicalization_values_are_stable(self):
        values = (0.1, 100.25, 5e-324, 1.7976931348623157e308, 0.30000000000000004)

        for value in values:
            with self.subTest(value=value):
                first = self.series(observations=(self.observation(technical_close=value),))
                second = self.series(observations=(self.observation(technical_close=float.fromhex(value.hex())),))
                self.assertEqual(first.market_revision_id, second.market_revision_id)

    def test_no_network_feature_or_persistence_boundary(self):
        source = (SRC_PATH / "market_inputs" / "technical_close_observation.py").read_text()

        forbidden = (
            "requests",
            "urllib",
            "TWSE",
            "TPEx",
            "historical_price_service",
            "LiveDataStore",
            "ResearchDataStore",
            "SMA20",
            "SMA60",
            "RSI14",
            "RiskEvaluationInput",
            "generation_key",
            "calculation_id",
            "sqlite3",
            "risk_persistence",
            "open(",
            "write_text",
        )
        for term in forbidden:
            self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
