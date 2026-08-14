import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError
from dataclasses import replace
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk import RiskSeverity
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_VERSION
from risk_evaluation import TECH_RISK_REASON_MAPPING_V1
from risk_evaluation import TECH_RISK_REQUIRED_FEATURE_IDS_V1
from risk_evaluation import TECH_RISK_SEVERITY_MAPPING_V1
from risk_evaluation import TECH_RSI14_FEATURE_ID
from risk_evaluation import TECH_RSI14_FEATURE_VERSION
from risk_evaluation import TECH_SMA20_FEATURE_ID
from risk_evaluation import TECH_SMA20_FEATURE_VERSION
from risk_evaluation import TECH_SMA60_FEATURE_ID
from risk_evaluation import TECH_SMA60_FEATURE_VERSION
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskReasonCode
from risk_evaluation import ProductionTechnicalRiskRule
from risk_evaluation import ProductionTechnicalRiskThresholdDimension
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator
from risk_evaluation import RiskEvaluationPolicyError


class ProductionTechnicalRiskPolicyContractTestCase(unittest.TestCase):

    def rule(self, **overrides):
        values = {
            "rule_id": "PROD_TECH_MEDIUM_RULE",
            "rule_priority": 20,
            "severity": RiskSeverity.MEDIUM,
            "required_predicates": (ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,),
            "optional_confirmation_predicates": (ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,),
            "reason_codes": (ProductionTechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,),
        }
        values.update(overrides)
        return ProductionTechnicalRiskRule(**values)

    def dimension(self, dimension_id, value):
        return ProductionTechnicalRiskThresholdDimension(
            dimension_id=dimension_id,
            operator=ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            canonical_value=value,
        )

    def dimensions(self, close_vs_sma20=Decimal("-0.025")):
        return (
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, close_vs_sma20),
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, Decimal("-0.05")),
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, Decimal("-0.02")),
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, Decimal("40")),
        )

    def policy(self, **overrides):
        values = {
            "policy_id": None,
            "policy_version": PRODUCTION_TECHNICAL_RISK_POLICY_V1,
            "policy_checksum": None,
            "technical_policy_version": "TECH_RISK_POLICY_V1_RESEARCH_FREEZE",
            "source_research_freeze_id": "technical_risk_policy_freeze_001",
            "source_research_freeze_checksum": "freeze_checksum_001",
            "candidate_id": "TECH_POLICY_CANDIDATE_A",
            "candidate_version": "v1",
            "candidate_structural_checksum": "candidate_checksum_001",
            "rules": (
                self.rule(
                    rule_id="PROD_TECH_HIGH_RULE",
                    rule_priority=10,
                    severity=RiskSeverity.HIGH,
                    required_predicates=(
                        ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                        ProductionTechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    ),
                    optional_confirmation_predicates=(),
                    reason_codes=(ProductionTechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,),
                ),
                self.rule(),
            ),
            "threshold_set_id": "threshold_set_001",
            "threshold_set_version": "v1",
            "threshold_set_checksum": "threshold_checksum_001",
            "threshold_dimensions": self.dimensions(),
            "required_feature_ids": TECH_RISK_REQUIRED_FEATURE_IDS_V1,
            "derived_evidence_version": "TECH_RISK_DERIVED_EVIDENCE_V1",
            "numeric_context_version": "TECH_RISK_DECIMAL_CONTEXT_V1",
            "severity_mapping_version": TECH_RISK_SEVERITY_MAPPING_V1,
            "reason_mapping_version": TECH_RISK_REASON_MAPPING_V1,
        }
        values.update(overrides)
        return ProductionTechnicalRiskPolicy(**values)

    def test_production_feature_vocabulary_constants(self):
        self.assertEqual(TECH_AS_OF_CLOSE_FEATURE_ID, "TECH_AS_OF_CLOSE_V1")
        self.assertEqual(TECH_AS_OF_CLOSE_FEATURE_VERSION, "v1")
        self.assertEqual(TECH_SMA20_FEATURE_ID, "TECH_SMA20_V1")
        self.assertEqual(TECH_SMA20_FEATURE_VERSION, "v1")
        self.assertEqual(TECH_SMA60_FEATURE_ID, "TECH_SMA60_V1")
        self.assertEqual(TECH_SMA60_FEATURE_VERSION, "v1")
        self.assertEqual(TECH_RSI14_FEATURE_ID, "TECH_RSI14_V1")
        self.assertEqual(TECH_RSI14_FEATURE_VERSION, "v1")
        self.assertEqual(
            TECH_RISK_REQUIRED_FEATURE_IDS_V1,
            ("TECH_AS_OF_CLOSE_V1", "TECH_RSI14_V1", "TECH_SMA20_V1", "TECH_SMA60_V1"),
        )

    def test_valid_immutable_policy_and_deterministic_identity(self):
        first = self.policy()
        second = self.policy()

        self.assertEqual(first.policy_id, second.policy_id)
        self.assertEqual(first.policy_checksum, second.policy_checksum)
        self.assertTrue(first.policy_id.startswith("production_technical_risk_policy_"))
        with self.assertRaises(FrozenInstanceError):
            first.technical_policy_version = "changed"

    def test_semantic_ordering_does_not_change_identity(self):
        first = self.policy()
        reversed_semantic = self.policy(
            rules=tuple(reversed(first.rules)),
            threshold_dimensions=tuple(reversed(first.threshold_dimensions)),
            required_feature_ids=tuple(reversed(first.required_feature_ids)),
        )

        self.assertEqual(first.policy_id, reversed_semantic.policy_id)
        self.assertEqual(first.policy_checksum, reversed_semantic.policy_checksum)

    def test_exact_required_feature_set_enforced(self):
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "required feature"):
            self.policy(required_feature_ids=("TECH_AS_OF_CLOSE_V1", "TECH_SMA20_V1", "TECH_SMA60_V1"))
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "required feature"):
            self.policy(required_feature_ids=(*TECH_RISK_REQUIRED_FEATURE_IDS_V1, "TECH_VOLUME_RATIO_V1"))

    def test_low_medium_high_rules_allowed_but_critical_rejected(self):
        for severity in (RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH):
            rule = self.rule(severity=severity)
            self.assertEqual(rule.severity, severity)
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "CRITICAL"):
            self.rule(severity=RiskSeverity.CRITICAL)
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "CRITICAL"):
            self.policy(rules=(self.rule(severity=RiskSeverity.CRITICAL),))

    def test_unknown_predicate_operator_and_reason_rejected(self):
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "predicate"):
            self.rule(required_predicates=("UNKNOWN_PREDICATE",))
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "operator"):
            ProductionTechnicalRiskThresholdDimension(
                ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
                "GREATER_THAN",
                Decimal("-0.1"),
            )
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "reason"):
            self.rule(reason_codes=("UNKNOWN_REASON",))

    def test_threshold_decimal_preserved_and_float_rejected(self):
        dimension = self.dimension(
            ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
            Decimal("-0.0250"),
        )

        self.assertEqual(dimension.canonical_value, Decimal("-0.025"))
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "Decimal"):
            self.dimension(ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, -0.025)

    def test_checksum_changes_for_semantic_changes(self):
        base = self.policy()

        changed_threshold = self.policy(threshold_dimensions=self.dimensions(close_vs_sma20=Decimal("-0.03")))
        changed_rule = self.policy(rules=(replace(base.rules[0], rule_priority=11), base.rules[1]))
        changed_version = self.policy(technical_policy_version="TECH_RISK_POLICY_V1B")
        changed_freeze = self.policy(source_research_freeze_checksum="freeze_checksum_002")
        self.assertNotEqual(base.policy_checksum, changed_threshold.policy_checksum)
        self.assertNotEqual(base.policy_checksum, changed_rule.policy_checksum)
        self.assertNotEqual(base.policy_checksum, changed_version.policy_checksum)
        self.assertNotEqual(base.policy_checksum, changed_freeze.policy_checksum)
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "severity mapping"):
            self.policy(severity_mapping_version="TECH_RISK_SEVERITY_MAPPING_V2")
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "reason mapping"):
            self.policy(reason_mapping_version="TECH_RISK_REASON_MAPPING_V2")

    def test_id_and_checksum_mismatch_rejected(self):
        policy = self.policy()

        with self.assertRaisesRegex(RiskEvaluationPolicyError, "policy_id"):
            self.policy(policy_id="wrong")
        with self.assertRaisesRegex(RiskEvaluationPolicyError, "policy_checksum"):
            self.policy(policy_checksum="wrong")
        self.assertIsNotNone(policy.policy_checksum)

    def test_no_auto_activation_or_evaluator_surface(self):
        import risk_evaluation
        import risk_evaluation.technical_policy as technical_policy

        source = inspect.getsource(technical_policy)
        forbidden_tokens = (
            "TechnicalRiskEvaluator",
            "TechnicalRiskEvaluationResult",
            "TechnicalRiskSignalProducer",
            "active =",
            "latest",
            "default_policy",
            "auto_register",
            "RiskSignal(",
            "ProducedRiskSignal(",
            "risk_oos",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)
        self.assertNotIn("TechnicalRiskEvaluator", risk_evaluation.__all__)
        self.assertNotIn("TechnicalRiskSignalProducer", risk_evaluation.__all__)


if __name__ == "__main__":
    unittest.main()
