import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1
from market_inputs import TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1
from market_inputs import TECHNICAL_FEATURE_SET_SCHEMA_VERSION_V1
from market_inputs import MarketInputValidationError
from market_inputs import ProductionTechnicalFeatureMaterializer
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseObservation
from market_inputs import TechnicalCloseObservationSeries
from market_inputs import TechnicalFeatureBundle
from market_inputs import TechnicalFeatureSet
from market_inputs import YAHOO_FINANCE_PROVIDER_ID_V1
from market_inputs import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1
from market_inputs.technical_feature_bundle import effective_observation_checksum
from market_inputs.technical_feature_set import _technical_feature_set_checksum
from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_ID


class TechnicalFeatureSetContractTestCase(unittest.TestCase):

    def features(self, **overrides):
        values = {
            TECH_AS_OF_CLOSE_FEATURE_ID: 100.25,
            TECH_SMA20_FEATURE_ID: 98.5,
            TECH_SMA60_FEATURE_ID: 95.75,
            TECH_RSI14_FEATURE_ID: 55.0,
        }
        values.update(overrides)
        return values

    def effective_checksum(self, symbol="2330.TW", valuation_date=date(2026, 8, 14), close=100.25):
        return effective_observation_checksum(
            symbol=symbol,
            valuation_date=valuation_date,
            observations=(
                {
                    "market_session_date": valuation_date.isoformat(),
                    "technical_close": close.hex(),
                },
            ),
        )

    def bundle(self, symbol="2330.TW", valuation_date=date(2026, 8, 14), market_revision_char="a", **overrides):
        values = {
            "schema_version": TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1,
            "feature_materializer_version": PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1,
            "symbol": symbol,
            "valuation_date": valuation_date,
            "market_revision_id": "market_revision_" + market_revision_char * 64,
            "effective_observation_checksum": self.effective_checksum(symbol=symbol, valuation_date=valuation_date),
            "features": self.features(**{TECH_AS_OF_CLOSE_FEATURE_ID: 100.25}),
        }
        values.update(overrides)
        return TechnicalFeatureBundle(**values)

    def observation(self, market_session_date, technical_close):
        return TechnicalCloseObservation(
            market_session_date=market_session_date,
            technical_close=technical_close,
        )

    def series(self, symbol, closes, start=date(2026, 1, 1)):
        observations = tuple(
            self.observation(start + timedelta(days=index), close)
            for index, close in enumerate(closes)
        )
        return TechnicalCloseObservationSeries(
            symbol=symbol,
            provider=YAHOO_FINANCE_PROVIDER_ID_V1,
            provider_symbol=symbol,
            timezone="Asia/Taipei",
            close_basis=TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE,
            valuation_date=observations[-1].market_session_date,
            observations=observations,
            fetched_at=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
            producer_version=YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1,
        )

    def test_valid_one_bundle_feature_set_is_frozen(self):
        feature_set = TechnicalFeatureSet(bundles=(self.bundle(),))

        self.assertEqual(feature_set.schema_version, TECHNICAL_FEATURE_SET_SCHEMA_VERSION_V1)
        self.assertEqual(feature_set.feature_materializer_version, PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1)
        self.assertEqual(feature_set.valuation_date, date(2026, 8, 14))
        self.assertEqual(feature_set.symbols, ("2330.TW",))
        self.assertTrue(feature_set.technical_feature_set_checksum.startswith("technical_feature_set_"))
        with self.assertRaises(FrozenInstanceError):
            feature_set.schema_version = "2"

    def test_valid_multiple_bundles_store_canonical_symbol_order(self):
        tsmc = self.bundle(symbol="2330.TW", market_revision_char="a")
        nvidia = self.bundle(symbol="NVDA", market_revision_char="b")
        feature_set = TechnicalFeatureSet(bundles=(nvidia, tsmc))

        self.assertEqual(feature_set.symbols, ("2330.TW", "NVDA"))
        self.assertEqual(tuple(bundle.symbol for bundle in feature_set.bundles), ("2330.TW", "NVDA"))

    def test_empty_and_wrong_bundle_type_rejected(self):
        with self.assertRaisesRegex(MarketInputValidationError, "empty"):
            TechnicalFeatureSet(bundles=())
        with self.assertRaisesRegex(MarketInputValidationError, "tuple"):
            TechnicalFeatureSet(bundles=[self.bundle()])
        with self.assertRaisesRegex(MarketInputValidationError, "TechnicalFeatureBundle"):
            TechnicalFeatureSet(bundles=(object(),))

    def test_input_order_does_not_change_checksum(self):
        tsmc = self.bundle(symbol="2330.TW", market_revision_char="a")
        nvidia = self.bundle(symbol="NVDA", market_revision_char="b")

        first = TechnicalFeatureSet(bundles=(tsmc, nvidia))
        second = TechnicalFeatureSet(bundles=(nvidia, tsmc))

        self.assertEqual(first.bundles, second.bundles)
        self.assertEqual(first.technical_feature_set_checksum, second.technical_feature_set_checksum)

    def test_mixed_valuation_date_materializer_version_and_bundle_schema_rejected(self):
        tsmc = self.bundle(symbol="2330.TW", market_revision_char="a")
        different_date = self.bundle(
            symbol="NVDA",
            valuation_date=date(2026, 8, 15),
            market_revision_char="b",
            effective_observation_checksum=self.effective_checksum(symbol="NVDA", valuation_date=date(2026, 8, 15)),
        )
        different_version = self.bundle(symbol="NVDA", market_revision_char="b")
        object.__setattr__(different_version, "feature_materializer_version", "PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V2")
        different_schema = self.bundle(symbol="NVDA", market_revision_char="b")
        object.__setattr__(different_schema, "schema_version", "2")

        with self.assertRaisesRegex(MarketInputValidationError, "valuation_date"):
            TechnicalFeatureSet(bundles=(tsmc, different_date))
        with self.assertRaisesRegex(MarketInputValidationError, "feature_materializer_version"):
            TechnicalFeatureSet(bundles=(tsmc, different_version))
        with self.assertRaisesRegex(MarketInputValidationError, "schema_version"):
            TechnicalFeatureSet(bundles=(tsmc, different_schema))

    def test_caller_supplied_metadata_must_match_derived_values(self):
        bundle = self.bundle()
        feature_set = TechnicalFeatureSet(bundles=(bundle,))

        same = TechnicalFeatureSet(
            bundles=(bundle,),
            technical_feature_set_checksum=feature_set.technical_feature_set_checksum,
            feature_materializer_version=feature_set.feature_materializer_version,
            valuation_date=feature_set.valuation_date,
        )

        self.assertEqual(feature_set.technical_feature_set_checksum, same.technical_feature_set_checksum)
        with self.assertRaisesRegex(MarketInputValidationError, "feature_materializer_version"):
            TechnicalFeatureSet(bundles=(bundle,), feature_materializer_version="OTHER_VERSION")
        with self.assertRaisesRegex(MarketInputValidationError, "valuation_date"):
            TechnicalFeatureSet(bundles=(bundle,), valuation_date=date(2026, 8, 15))
        with self.assertRaisesRegex(MarketInputValidationError, "technical_feature_set_checksum"):
            TechnicalFeatureSet(bundles=(bundle,), technical_feature_set_checksum="technical_feature_set_" + "0" * 64)
        with self.assertRaisesRegex(MarketInputValidationError, "schema_version"):
            TechnicalFeatureSet(bundles=(bundle,), schema_version="2")

    def test_duplicate_symbol_rejected_without_dedupe_or_provenance_selection(self):
        original = self.bundle(symbol="2330.TW", market_revision_char="a")
        same_semantic_different_provenance = self.bundle(symbol="2330.TW", market_revision_char="b")
        different_semantic = self.bundle(
            symbol="2330.TW",
            market_revision_char="c",
            features=self.features(**{TECH_RSI14_FEATURE_ID: 56.0}),
        )

        with self.assertRaisesRegex(MarketInputValidationError, "Duplicate"):
            TechnicalFeatureSet(bundles=(original, original))
        with self.assertRaisesRegex(MarketInputValidationError, "Duplicate"):
            TechnicalFeatureSet(bundles=(original, same_semantic_different_provenance))
        with self.assertRaisesRegex(MarketInputValidationError, "Duplicate"):
            TechnicalFeatureSet(bundles=(original, different_semantic))

    def test_provenance_only_market_revision_change_does_not_change_set_checksum(self):
        tsmc_provenance_a = self.bundle(symbol="2330.TW", market_revision_char="a")
        tsmc_provenance_b = self.bundle(symbol="2330.TW", market_revision_char="b")
        nvidia = self.bundle(symbol="NVDA", market_revision_char="c")

        first = TechnicalFeatureSet(bundles=(tsmc_provenance_a, nvidia))
        second = TechnicalFeatureSet(bundles=(tsmc_provenance_b, nvidia))

        self.assertNotEqual(tsmc_provenance_a.market_revision_id, tsmc_provenance_b.market_revision_id)
        self.assertEqual(tsmc_provenance_a.feature_bundle_checksum, tsmc_provenance_b.feature_bundle_checksum)
        self.assertEqual(first.technical_feature_set_checksum, second.technical_feature_set_checksum)

    def test_bundle_semantic_change_and_valuation_date_change_affect_set_checksum(self):
        base = TechnicalFeatureSet(
            bundles=(
                self.bundle(symbol="2330.TW", market_revision_char="a"),
                self.bundle(symbol="NVDA", market_revision_char="b"),
            )
        )
        changed_feature = TechnicalFeatureSet(
            bundles=(
                self.bundle(symbol="2330.TW", market_revision_char="a"),
                self.bundle(
                    symbol="NVDA",
                    market_revision_char="c",
                    features=self.features(**{TECH_RSI14_FEATURE_ID: 60.0}),
                ),
            )
        )
        changed_date = TechnicalFeatureSet(
            bundles=(
                self.bundle(
                    symbol="2330.TW",
                    valuation_date=date(2026, 8, 15),
                    market_revision_char="d",
                    effective_observation_checksum=self.effective_checksum(symbol="2330.TW", valuation_date=date(2026, 8, 15)),
                ),
            )
        )
        base_single = TechnicalFeatureSet(bundles=(self.bundle(symbol="2330.TW", market_revision_char="a"),))

        self.assertNotEqual(base.technical_feature_set_checksum, changed_feature.technical_feature_set_checksum)
        self.assertNotEqual(base_single.technical_feature_set_checksum, changed_date.technical_feature_set_checksum)

    def test_materializer_version_participates_in_checksum_material(self):
        bundle = self.bundle()
        base = _technical_feature_set_checksum(
            schema_version=TECHNICAL_FEATURE_SET_SCHEMA_VERSION_V1,
            feature_materializer_version=PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1,
            valuation_date=bundle.valuation_date,
            bundles=(bundle,),
        )
        changed = _technical_feature_set_checksum(
            schema_version=TECHNICAL_FEATURE_SET_SCHEMA_VERSION_V1,
            feature_materializer_version="PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V2",
            valuation_date=bundle.valuation_date,
            bundles=(bundle,),
        )

        self.assertNotEqual(base, changed)

    def test_p2b3a_materializer_integration_constructs_feature_set(self):
        materializer = ProductionTechnicalFeatureMaterializer()
        tsmc = materializer.materialize(self.series("2330.TW", tuple(float(100 + index) for index in range(60))))
        nvidia = materializer.materialize(self.series("NVDA", tuple(float(200 + index) for index in range(60))))

        first = TechnicalFeatureSet(bundles=(nvidia, tsmc))
        second = TechnicalFeatureSet(bundles=(tsmc, nvidia))

        self.assertEqual(first.symbols, ("2330.TW", "NVDA"))
        self.assertEqual(first.technical_feature_set_checksum, second.technical_feature_set_checksum)

    def test_dependency_and_identity_boundary_scan(self):
        source = (SRC_PATH / "market_inputs" / "technical_feature_set.py").read_text()

        forbidden = (
            "PortfolioSnapshot",
            "PortfolioPositionState",
            "PositionStatus",
            "portfolio_state",
            "portfolio_generation",
            "risk_evaluation",
            "risk_persistence",
            "risk_oos",
            "SMA20Calculator",
            "SMA60Calculator",
            "RSI14Calculator",
            "yfinance",
            "pandas",
            "sqlite3",
            "open(",
            "read_text",
            "write_text",
            "portfolio_id",
            "snapshot_id",
            "position_id",
            "shares",
            "average_cost",
            "fetched_at",
            "provider",
            "Fresh",
            "Replay",
            "market_revision_id",
            "effective_observation_checksum",
        )
        for term in forbidden:
            self.assertNotIn(term, source)
        self.assertFalse((PROJECT_ROOT / "data" / "production").exists())


if __name__ == "__main__":
    unittest.main()
