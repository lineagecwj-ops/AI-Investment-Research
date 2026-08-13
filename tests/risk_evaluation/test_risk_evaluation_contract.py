import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk import RiskCategory
from risk import RiskSeverity
from risk import RiskSignal
from risk_evaluation import MissingDataPolicy
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import RiskEvaluationPolicy
from risk_evaluation import RiskEvaluationPolicyError
from risk_evaluation import RiskEvaluationPolicyRegistry
from risk_evaluation import RiskFeatureInput
from risk_evaluation import RiskFeatureInputError
from risk_evaluation import RiskSignalProducer
from risk_evaluation import RiskSignalProducerError
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import RiskSignalProductionInputError
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_VERSION
from risk_evaluation import validate_producer_created_at


class FakeProtocolProducer:
    category = RiskCategory.TECHNICAL
    producer_version = "technical_contract_v1"

    def produce(self, input, policy, created_at):
        validate_producer_created_at(created_at)
        policy.validate_required_features(input)
        signal = RiskSignal(
            risk_id="TECH_CONTRACT_ONLY_V1",
            symbol=input.symbol,
            category=self.category,
            severity=RiskSeverity.LOW,
            trigger_reason="contract-only fake signal",
            created_at=created_at,
        )
        return (
            ProducedRiskSignal(
                signal=signal,
                policy_id=policy.policy_id,
                policy_version=policy.version,
                producer_version=self.producer_version,
                source_feature_ids=input.feature_ids,
                source_checksums=input.source_checksums,
                calculation_id=input.calculation_id,
            ),
        )


class RiskEvaluationContractTestCase(unittest.TestCase):

    def feature(
        self,
        feature_id="TECH_SMA20_V1",
        value=Decimal("70.5"),
        *,
        feature_version="v1",
        portfolio_id="portfolio_synthetic_001",
        position_id="position_001",
        symbol="2330.TW",
        calculation_id="risk_calc_contract_001",
        source_artifact_id="feature_artifact_sma20",
        source_checksum="checksum_sma20",
        feature_date=date(2026, 3, 31),
    ):
        return RiskFeatureInput(
            feature_id=feature_id,
            feature_version=feature_version,
            portfolio_id=portfolio_id,
            position_id=position_id,
            symbol=symbol,
            as_of_date=date(2026, 3, 31),
            feature_date=feature_date,
            value=value,
            source_artifact_id=source_artifact_id,
            source_checksum=source_checksum,
            calculation_id=calculation_id,
        )

    def as_of_close(self, value=Decimal("100.25"), **overrides):
        params = {
            "feature_id": TECH_AS_OF_CLOSE_FEATURE_ID,
            "value": value,
            "feature_version": TECH_AS_OF_CLOSE_FEATURE_VERSION,
            "source_artifact_id": "feature_artifact_as_of_close",
            "source_checksum": "checksum_as_of_close",
            "feature_date": date(2026, 3, 31),
        }
        params.update(overrides)
        return self.feature(**params)

    def production_input(self, *, features=None, **overrides):
        active_features = features if features is not None else (
            self.feature("TECH_VOLUME_RATIO_V1", 2.0, source_artifact_id="feature_artifact_volume", source_checksum="checksum_volume"),
            self.feature("TECH_SMA20_V1", Decimal("70.5"), source_artifact_id="feature_artifact_sma20", source_checksum="checksum_sma20"),
        )
        params = {
            "portfolio_id": "portfolio_synthetic_001",
            "position_id": "position_001",
            "symbol": "2330.TW",
            "as_of_date": date(2026, 3, 31),
            "valuation_date": date(2026, 3, 30),
            "feature_version": "feature_set_v1",
            "feature_values": active_features,
            "model_version": None,
            "model_metadata": {"model_role": "not_used_in_contract_sprint"},
            "exposure_metadata": {"shares": Decimal("10")},
            "source_artifact_ids": tuple(feature.source_artifact_id for feature in active_features),
            "source_checksums": tuple(feature.source_checksum for feature in active_features),
            "calculation_id": "risk_calc_contract_001",
        }
        params.update(overrides)
        return RiskSignalProductionInput(**params)

    def policy(self, **overrides):
        params = {
            "policy_id": "risk_eval_policy_contract",
            "version": "v1",
            "enabled_categories": (RiskCategory.TECHNICAL,),
            "required_feature_ids": ("TECH_SMA20_V1", "TECH_VOLUME_RATIO_V1"),
            "category_producer_versions": {RiskCategory.TECHNICAL: "technical_contract_v1"},
            "severity_rules": {
                "TECH_CONTRACT_ONLY_V1": "contract representation only; no production threshold defined",
            },
            "missing_data_policy": MissingDataPolicy.FAIL_EVALUATION,
            "calculation_metadata": {"scope": "contract_only"},
        }
        params.update(overrides)
        return RiskEvaluationPolicy(**params)

    def test_risk_feature_input_creation_and_immutability(self):
        feature = self.feature()

        self.assertEqual(feature.feature_id, "TECH_SMA20_V1")
        self.assertEqual(feature.symbol, "2330.TW")
        self.assertEqual(feature.feature_date, date(2026, 3, 31))
        self.assertEqual(feature.source_checksum, "checksum_sma20")
        with self.assertRaises(FrozenInstanceError):
            feature.value = Decimal("1.0")

    def test_decimal_and_numeric_value_preservation(self):
        decimal_feature = self.feature(value=Decimal("70.500"))
        float_feature = self.feature("TECH_RSI14_V1", 82.3529411764706, source_artifact_id="feature_artifact_rsi", source_checksum="checksum_rsi")

        self.assertEqual(decimal_feature.value, Decimal("70.500"))
        self.assertEqual(float_feature.value, 82.3529411764706)
        with self.assertRaisesRegex(RiskFeatureInputError, "numeric"):
            self.feature(value=True)

    def test_feature_date_cannot_exceed_as_of_date(self):
        with self.assertRaisesRegex(RiskFeatureInputError, "feature_date"):
            self.feature(feature_date=date(2026, 4, 1))

    def test_valid_tech_as_of_close_v1(self):
        close = self.as_of_close()

        self.assertEqual(close.feature_id, TECH_AS_OF_CLOSE_FEATURE_ID)
        self.assertEqual(close.feature_version, "v1")
        self.assertEqual(close.feature_date, close.as_of_date)
        self.assertEqual(close.value, Decimal("100.25"))
        self.assertEqual(close.source_artifact_id, "feature_artifact_as_of_close")
        self.assertEqual(close.source_checksum, "checksum_as_of_close")

    def test_as_of_close_feature_date_must_equal_as_of_date(self):
        with self.assertRaisesRegex(RiskFeatureInputError, "feature_date must equal as_of_date"):
            self.as_of_close(feature_date=date(2026, 3, 30))
        with self.assertRaisesRegex(RiskFeatureInputError, "feature_date"):
            self.as_of_close(feature_date=date(2026, 4, 1))

    def test_as_of_close_numeric_types_and_positive_value(self):
        decimal_close = self.as_of_close(Decimal("100.25"))
        int_close = self.as_of_close(100)
        float_close = self.as_of_close(100.25)

        self.assertEqual(decimal_close.value, Decimal("100.25"))
        self.assertEqual(int_close.value, 100)
        self.assertEqual(float_close.value, 100.25)
        with self.assertRaisesRegex(RiskFeatureInputError, "numeric"):
            self.as_of_close(True)
        with self.assertRaisesRegex(RiskFeatureInputError, "positive"):
            self.as_of_close(0)
        with self.assertRaisesRegex(RiskFeatureInputError, "positive"):
            self.as_of_close(Decimal("-1.0"))

    def test_as_of_close_lineage_and_version_validation(self):
        close = self.as_of_close()

        self.assertEqual(close.calculation_id, "risk_calc_contract_001")
        with self.assertRaisesRegex(RiskFeatureInputError, "source_artifact_id"):
            self.as_of_close(source_artifact_id="")
        with self.assertRaisesRegex(RiskFeatureInputError, "source_checksum"):
            self.as_of_close(source_checksum="")
        with self.assertRaisesRegex(RiskFeatureInputError, "calculation_id"):
            self.as_of_close(calculation_id="")
        with self.assertRaisesRegex(RiskFeatureInputError, "feature_version"):
            self.as_of_close(feature_version="v2")

    def test_as_of_close_production_input_compatibility_and_ordering(self):
        features = (
            self.feature("TECH_RSI14_V1", 82.35, source_artifact_id="artifact_rsi", source_checksum="checksum_rsi"),
            self.as_of_close(),
            self.feature("TECH_SMA60_V1", 50.5, source_artifact_id="artifact_sma60", source_checksum="checksum_sma60"),
            self.feature("TECH_SMA20_V1", 70.5, source_artifact_id="artifact_sma20", source_checksum="checksum_sma20"),
        )
        production_input = self.production_input(features=features)

        self.assertEqual(
            production_input.feature_ids,
            ("TECH_AS_OF_CLOSE_V1", "TECH_RSI14_V1", "TECH_SMA20_V1", "TECH_SMA60_V1"),
        )
        self.assertIn("checksum_as_of_close", production_input.source_checksums)

    def test_as_of_close_deterministic_equality(self):
        self.assertEqual(self.as_of_close(), self.as_of_close())

    def test_non_close_features_are_not_subject_to_as_of_close_rules(self):
        older_sma = self.feature("TECH_SMA20_V1", feature_date=date(2026, 3, 30))
        zero_volume_ratio = self.feature("TECH_VOLUME_RATIO_V1", value=0)

        self.assertEqual(older_sma.feature_date, date(2026, 3, 30))
        self.assertEqual(zero_volume_ratio.value, 0)

    def test_signal_production_input_creation_and_deterministic_feature_ordering(self):
        production_input = self.production_input()

        self.assertEqual(
            production_input.feature_ids,
            ("TECH_SMA20_V1", "TECH_VOLUME_RATIO_V1"),
        )
        self.assertEqual(production_input.source_checksums, ("checksum_sma20", "checksum_volume"))
        self.assertEqual(production_input.exposure_metadata["shares"], Decimal("10"))

    def test_duplicate_feature_identity_rejected(self):
        first = self.feature("TECH_SMA20_V1", source_artifact_id="a", source_checksum="ca")
        duplicate = self.feature("TECH_SMA20_V1", source_artifact_id="b", source_checksum="cb")

        with self.assertRaisesRegex(RiskSignalProductionInputError, "duplicate feature"):
            self.production_input(features=(first, duplicate))

    def test_portfolio_position_symbol_and_calculation_mismatch_rejected(self):
        with self.assertRaisesRegex(RiskSignalProductionInputError, "portfolio_id mismatch"):
            self.production_input(features=(self.feature(portfolio_id="other_portfolio"),))
        with self.assertRaisesRegex(RiskSignalProductionInputError, "position_id mismatch"):
            self.production_input(features=(self.feature(position_id="other_position"),))
        with self.assertRaisesRegex(RiskSignalProductionInputError, "symbol mismatch"):
            self.production_input(features=(self.feature(symbol="2454.TW"),))
        with self.assertRaisesRegex(RiskSignalProductionInputError, "calculation_id mismatch"):
            self.production_input(features=(self.feature(calculation_id="other_calc"),))

    def test_missing_lineage_rejected(self):
        with self.assertRaisesRegex(RiskFeatureInputError, "source_checksum"):
            self.feature(source_checksum="")
        feature = self.feature(source_artifact_id="feature_artifact_sma20", source_checksum="checksum_sma20")
        with self.assertRaisesRegex(RiskSignalProductionInputError, "source_checksum"):
            self.production_input(features=(feature,), source_checksums=("other_checksum",))

    def test_risk_evaluation_policy_creation_and_exact_identity(self):
        policy = self.policy()

        self.assertEqual(policy.identity, ("risk_eval_policy_contract", "v1"))
        self.assertEqual(policy.enabled_categories, (RiskCategory.TECHNICAL,))
        self.assertEqual(policy.missing_data_policy, MissingDataPolicy.FAIL_EVALUATION)
        self.assertEqual(policy.category_producer_versions[RiskCategory.TECHNICAL], "technical_contract_v1")

    def test_policy_unknown_category_and_missing_producer_fail_closed(self):
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "Unknown risk category"):
            self.policy(enabled_categories=("unknown",))
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "Missing producer version"):
            self.policy(category_producer_versions={})

    def test_policy_registry_exact_version_fail_closed(self):
        policy = self.policy()
        registry = RiskEvaluationPolicyRegistry((policy,))

        self.assertIs(registry.resolve("risk_eval_policy_contract", "v1"), policy)
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "Unknown risk evaluation policy version"):
            registry.resolve("risk_eval_policy_contract", "v2")
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "policy_id"):
            registry.resolve("", "v1")

    def test_missing_required_feature_rejected_with_fail_evaluation_policy(self):
        policy = self.policy(required_feature_ids=("TECH_SMA20_V1", "TECH_RSI14_V1"))
        production_input = self.production_input(features=(self.feature("TECH_SMA20_V1"),))

        with self.assertRaisesRegex(RiskEvaluationPolicyError, "Required feature missing"):
            policy.validate_required_features(production_input)

    def test_timezone_aware_created_at_contract(self):
        validate_producer_created_at(datetime(2026, 8, 13, 12, 0, tzinfo=UTC))

        with self.assertRaisesRegex(RiskSignalProducerError, "timezone-aware"):
            validate_producer_created_at(datetime(2026, 8, 13, 12, 0))

    def test_producer_protocol_and_produced_signal_lineage_wrapper(self):
        producer: RiskSignalProducer = FakeProtocolProducer()
        production_input = self.production_input()
        policy = self.policy()
        created_at = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

        produced = producer.produce(production_input, policy, created_at)

        self.assertEqual(len(produced), 1)
        self.assertEqual(produced[0].signal.created_at, created_at)
        self.assertEqual(produced[0].policy_version, "v1")
        self.assertEqual(produced[0].producer_version, "technical_contract_v1")
        self.assertEqual(produced[0].source_feature_ids, production_input.feature_ids)
        self.assertFalse(hasattr(produced[0].signal, "policy_version"))
        self.assertFalse(hasattr(produced[0].signal, "producer_version"))

    def test_deterministic_equality(self):
        first = self.production_input()
        second = self.production_input()
        first_policy = self.policy()
        second_policy = self.policy()

        self.assertEqual(first, second)
        self.assertEqual(first_policy, second_policy)

    def test_existing_technical_feature_value_compatibility(self):
        features = (
            self.feature("TECH_SMA20_V1", 70.5, source_artifact_id="artifact_sma20", source_checksum="checksum_sma20"),
            self.feature("TECH_SMA60_V1", 50.5, source_artifact_id="artifact_sma60", source_checksum="checksum_sma60"),
            self.feature("TECH_RSI14_V1", 82.3529411764706, source_artifact_id="artifact_rsi", source_checksum="checksum_rsi"),
            self.feature("TECH_VOLUME_RATIO_V1", 2.0, source_artifact_id="artifact_volume", source_checksum="checksum_volume"),
        )
        production_input = self.production_input(features=features)

        self.assertEqual(
            production_input.feature_ids,
            ("TECH_RSI14_V1", "TECH_SMA20_V1", "TECH_SMA60_V1", "TECH_VOLUME_RATIO_V1"),
        )

    def test_architecture_boundary_scan(self):
        source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "risk_evaluation").glob("*.py"))
        )

        forbidden_terms = (
            "sqlite3",
            "LiveDataStore",
            "live_data_store",
            "ResearchDataStore",
            "research_data_store",
            "yfinance",
            "scanner",
            "pdf_export",
            "RiskMonitoringEngine",
            "RiskArtifactGenerator(",
            "FeatureArtifactGenerator(",
            "FeatureCalculator(",
            "FeatureRegistry(",
            "app.py",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
