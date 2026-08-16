import math
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from market_inputs import PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1
from market_inputs import TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1
from market_inputs import TECHNICAL_RISK_V1_FEATURE_IDS
from market_inputs import TechnicalFeatureBundle
from market_inputs import TechnicalFeatureMaterializationError
from market_inputs.technical_feature_bundle import effective_observation_checksum
from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_ID


class TechnicalFeatureBundleContractTestCase(unittest.TestCase):

    def features(self, **overrides):
        values = {
            TECH_AS_OF_CLOSE_FEATURE_ID: 100.25,
            TECH_SMA20_FEATURE_ID: 98.5,
            TECH_SMA60_FEATURE_ID: 95.75,
            TECH_RSI14_FEATURE_ID: 55.0,
        }
        values.update(overrides)
        return values

    def effective_checksum(self):
        return effective_observation_checksum(
            symbol="2330.TW",
            valuation_date=date(2026, 8, 14),
            observations=(
                {
                    "market_session_date": date(2026, 8, 13).isoformat(),
                    "technical_close": (99.5).hex(),
                },
                {
                    "market_session_date": date(2026, 8, 14).isoformat(),
                    "technical_close": (100.25).hex(),
                },
            ),
        )

    def bundle(self, **overrides):
        values = {
            "schema_version": TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1,
            "feature_materializer_version": PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1,
            "symbol": "2330.TW",
            "valuation_date": date(2026, 8, 14),
            "market_revision_id": "market_revision_" + "a" * 64,
            "effective_observation_checksum": self.effective_checksum(),
            "features": self.features(),
        }
        values.update(overrides)
        return TechnicalFeatureBundle(**values)

    def test_valid_bundle_is_frozen_and_features_are_immutable(self):
        bundle = self.bundle()

        self.assertEqual(bundle.schema_version, TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1)
        self.assertTrue(bundle.feature_bundle_checksum.startswith("technical_feature_bundle_"))
        self.assertEqual(tuple(bundle.features), tuple(sorted(TECHNICAL_RISK_V1_FEATURE_IDS)))
        with self.assertRaises(FrozenInstanceError):
            bundle.symbol = "changed"
        with self.assertRaises(TypeError):
            bundle.features[TECH_AS_OF_CLOSE_FEATURE_ID] = 1.0

    def test_exact_technical_risk_v1_feature_set_required(self):
        missing = self.features()
        missing.pop(TECH_RSI14_FEATURE_ID)
        extra = self.features(EXTRA_FEATURE_V1=1.0)

        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "exact"):
            self.bundle(features=missing)
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "exact"):
            self.bundle(features=extra)
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "feature ids"):
            self.bundle(features={1: 100.25, **self.features()})

    def test_feature_values_must_be_finite_numeric_and_bool_is_rejected(self):
        invalid_values = (True, math.nan, math.inf, -math.inf, "100.25")

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(TechnicalFeatureMaterializationError):
                    self.bundle(features=self.features(**{TECH_AS_OF_CLOSE_FEATURE_ID: value}))

    def test_identity_fields_validate_without_market_revision_in_bundle_checksum(self):
        base = self.bundle()
        changed_revision = self.bundle(market_revision_id="market_revision_" + "b" * 64)

        self.assertEqual(base.feature_bundle_checksum, changed_revision.feature_bundle_checksum)
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "schema_version"):
            self.bundle(schema_version="2")
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "materializer"):
            self.bundle(feature_materializer_version="OTHER_VERSION")
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "symbol"):
            self.bundle(symbol="")
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "date"):
            self.bundle(valuation_date="2026-08-14")
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "market_revision"):
            self.bundle(market_revision_id="bad")
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "effective_observation_checksum"):
            self.bundle(effective_observation_checksum="bad")

    def test_feature_bundle_checksum_is_deterministic_and_order_independent(self):
        first = self.bundle()
        second = self.bundle(features=dict(reversed(tuple(self.features().items()))))

        self.assertEqual(first.feature_bundle_checksum, second.feature_bundle_checksum)
        self.assertEqual(first.features, second.features)

    def test_feature_bundle_checksum_changes_for_semantic_mutations(self):
        base = self.bundle()
        changed_symbol = self.bundle(symbol="2317.TW")
        changed_date = self.bundle(valuation_date=date(2026, 8, 13))
        changed_effective = self.bundle(
            effective_observation_checksum=effective_observation_checksum(
                symbol="2330.TW",
                valuation_date=date(2026, 8, 14),
                observations=(
                    {
                        "market_session_date": date(2026, 8, 14).isoformat(),
                        "technical_close": (101.25).hex(),
                    },
                ),
            )
        )
        changed_feature = self.bundle(features=self.features(**{TECH_RSI14_FEATURE_ID: 56.0}))

        self.assertNotEqual(base.feature_bundle_checksum, changed_symbol.feature_bundle_checksum)
        self.assertNotEqual(base.feature_bundle_checksum, changed_date.feature_bundle_checksum)
        self.assertNotEqual(base.feature_bundle_checksum, changed_effective.feature_bundle_checksum)
        self.assertNotEqual(base.feature_bundle_checksum, changed_feature.feature_bundle_checksum)

    def test_supplied_feature_bundle_checksum_must_match(self):
        bundle = self.bundle()
        same = self.bundle(feature_bundle_checksum=bundle.feature_bundle_checksum)

        self.assertEqual(bundle.feature_bundle_checksum, same.feature_bundle_checksum)
        with self.assertRaisesRegex(TechnicalFeatureMaterializationError, "mismatch"):
            self.bundle(feature_bundle_checksum="technical_feature_bundle_" + "0" * 64)


if __name__ == "__main__":
    unittest.main()
