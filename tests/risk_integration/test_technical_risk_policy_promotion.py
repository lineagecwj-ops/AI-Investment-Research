import inspect
import sys
import unittest
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk import RiskSeverity
from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1
from risk_evaluation import ProductionTechnicalRiskPredicateId
from risk_evaluation import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation import ProductionTechnicalRiskThresholdOperator
from risk_integration import TechnicalRiskPolicyPromotionError
from risk_integration import promote_research_freeze_to_production_policy
from risk_oos import TechnicalRiskCandidateRule
from risk_oos import TechnicalRiskCandidateSeverity
from risk_oos import TechnicalRiskPolicyFreezeReasonCode
from risk_oos import TechnicalRiskPolicyFreezeStatus
from risk_oos import TechnicalRiskPredicateId
from risk_oos import TechnicalRiskReasonCode
from risk_oos import technical_risk_candidate_a_spec
from risk_oos import technical_risk_candidate_b_spec
from tests.risk_oos.test_research_policy_freeze_contracts import TechnicalRiskPolicyFreezeContractTestCase


class TechnicalRiskPolicyPromotionTestCase(unittest.TestCase):

    def setUp(self):
        self.helper = TechnicalRiskPolicyFreezeContractTestCase(methodName="runTest")
        self.helper.setUp()

    def bundle(self, candidate=None, threshold_set=None):
        dataset, selection, _, _, confirmation = self.helper.bundle()
        candidate = technical_risk_candidate_a_spec() if candidate is None else candidate
        threshold_set = self.helper.helper.threshold_a() if threshold_set is None else threshold_set
        freeze = self.helper.freeze(selection=selection, confirmation=confirmation, candidate=candidate, threshold_set=threshold_set)
        return freeze, candidate, threshold_set

    def promote(self, freeze=None, candidate=None, threshold_set=None, **overrides):
        if freeze is None or candidate is None or threshold_set is None:
            freeze, candidate, threshold_set = self.bundle()
        return promote_research_freeze_to_production_policy(
            research_freeze=freeze,
            candidate=candidate,
            threshold_set=threshold_set,
            **overrides,
        )

    def tamper(self, artifact, **overrides):
        for field_name, value in overrides.items():
            object.__setattr__(artifact, field_name, value)
        return artifact

    def test_valid_frozen_research_freeze_promotes_to_policy(self):
        freeze, candidate, threshold_set = self.bundle()
        policy = self.promote(freeze, candidate, threshold_set)

        self.assertEqual(policy.policy_version, PRODUCTION_TECHNICAL_RISK_POLICY_V1)
        self.assertEqual(policy.technical_policy_version, freeze.technical_policy_version)
        self.assertEqual(policy.source_research_freeze_id, freeze.freeze_id)
        self.assertEqual(policy.source_research_freeze_checksum, freeze.freeze_checksum)
        self.assertEqual(policy.candidate_id, candidate.policy_candidate_id)
        self.assertEqual(policy.threshold_set_id, threshold_set.threshold_set_id)

    def test_non_frozen_or_missing_reason_rejected(self):
        freeze, candidate, threshold_set = self.bundle()
        self.tamper(freeze, freeze_status="NOT_FROZEN")

        with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "FROZEN"):
            self.promote(freeze, candidate, threshold_set)

        freeze, candidate, threshold_set = self.bundle()
        self.tamper(freeze, structured_freeze_reason_codes=())
        with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "RESEARCH_POLICY_FROZEN"):
            self.promote(freeze, candidate, threshold_set)

    def test_candidate_identity_mismatch_rejected(self):
        freeze, candidate, threshold_set = self.bundle()
        cases = (
            replace(candidate, policy_candidate_id="DIFFERENT", candidate_structural_checksum=None),
            replace(candidate, candidate_version="v2", candidate_structural_checksum=None),
            self.tamper(replace(candidate), candidate_structural_checksum="different_checksum"),
        )
        for changed_candidate in cases:
            with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "candidate"):
                self.promote(freeze, changed_candidate, threshold_set)

    def test_threshold_identity_mismatch_rejected(self):
        freeze, candidate, threshold_set = self.bundle()
        cases = (
            replace(threshold_set, threshold_set_id="different", threshold_set_checksum=None),
            replace(threshold_set, threshold_set_version="v2", threshold_set_checksum=None),
            self.tamper(replace(threshold_set), threshold_set_checksum="different_checksum"),
        )
        for changed_threshold in cases:
            with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "threshold"):
                self.promote(freeze, candidate, changed_threshold)

    def test_rule_semantics_are_exactly_copied(self):
        freeze, candidate, threshold_set = self.bundle()
        policy = self.promote(freeze, candidate, threshold_set)

        self.assertEqual(len(policy.rules), len(candidate.rules))
        for production_rule, research_rule in zip(policy.rules, candidate.rules, strict=True):
            self.assertEqual(production_rule.rule_id, research_rule.rule_id)
            self.assertEqual(production_rule.rule_priority, research_rule.rule_priority)
            self.assertEqual(production_rule.severity.value, research_rule.severity.value)
            self.assertEqual(
                tuple(predicate.value for predicate in production_rule.required_predicates),
                tuple(predicate.value for predicate in research_rule.required_predicates),
            )
            self.assertEqual(
                tuple(predicate.value for predicate in production_rule.optional_confirmation_predicates),
                tuple(predicate.value for predicate in research_rule.optional_confirmation_predicates),
            )
            self.assertEqual(
                tuple(reason.value for reason in production_rule.reason_codes),
                tuple(reason.value for reason in research_rule.reason_codes),
            )

    def test_threshold_decimal_values_are_exactly_copied(self):
        freeze, candidate, threshold_set = self.bundle()
        policy = self.promote(freeze, candidate, threshold_set)

        production_by_id = policy.threshold_dimensions_by_id
        for research_dimension in threshold_set.dimensions:
            production_dimension = production_by_id[ProductionTechnicalRiskThresholdDimensionId(research_dimension.dimension_id.value)]
            self.assertEqual(production_dimension.operator, ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL)
            self.assertEqual(production_dimension.canonical_decimal_string, research_dimension.canonical_value)

    def test_severity_mapping_and_never_critical(self):
        freeze, candidate, threshold_set = self.bundle()
        policy = self.promote(freeze, candidate, threshold_set)

        severities = {rule.severity for rule in policy.rules}
        self.assertIn(RiskSeverity.MEDIUM, severities)
        self.assertIn(RiskSeverity.HIGH, severities)
        self.assertNotIn(RiskSeverity.CRITICAL, severities)

        critical_rule = TechnicalRiskCandidateRule(
            "CRITICAL_RULE",
            TechnicalRiskCandidateSeverity.HIGH,
            (TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,),
            (),
            1,
            (TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,),
        )
        self.tamper(critical_rule, severity=RiskSeverity.CRITICAL)
        critical_candidate = replace(candidate)
        self.tamper(critical_candidate, rules=(critical_rule,), candidate_structural_checksum=freeze.candidate_structural_checksum)
        with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "CRITICAL"):
            self.promote(freeze, critical_candidate, threshold_set)

    def test_unknown_predicate_operator_and_reason_fail_closed(self):
        freeze, candidate, threshold_set = self.bundle()
        bad_rule = replace(candidate.rules[0])
        self.tamper(bad_rule, required_predicates=("UNKNOWN",))
        bad_candidate = replace(candidate)
        self.tamper(bad_candidate, rules=(bad_rule,), candidate_structural_checksum=freeze.candidate_structural_checksum)
        with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "predicate"):
            self.promote(freeze, bad_candidate, threshold_set)

        bad_reason_rule = replace(candidate.rules[0])
        self.tamper(bad_reason_rule, reason_codes=("UNKNOWN",))
        bad_reason_candidate = replace(candidate)
        self.tamper(bad_reason_candidate, rules=(bad_reason_rule,), candidate_structural_checksum=freeze.candidate_structural_checksum)
        with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "reason"):
            self.promote(freeze, bad_reason_candidate, threshold_set)

        bad_dimension = replace(threshold_set.dimensions[0])
        self.tamper(bad_dimension, operator="GREATER_THAN")
        bad_threshold = replace(threshold_set)
        self.tamper(
            bad_threshold,
            dimensions=(bad_dimension, *threshold_set.dimensions[1:]),
            threshold_set_checksum=freeze.threshold_set_checksum,
        )
        with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "operator"):
            self.promote(freeze, candidate, bad_threshold)

    def test_same_promotion_same_policy_id_and_checksum(self):
        freeze, candidate, threshold_set = self.bundle()
        first = self.promote(freeze, candidate, threshold_set)
        second = self.promote(freeze, candidate, threshold_set)

        self.assertEqual(first.policy_id, second.policy_id)
        self.assertEqual(first.policy_checksum, second.policy_checksum)

    def test_source_objects_not_mutated(self):
        freeze, candidate, threshold_set = self.bundle()
        before = (
            freeze.freeze_checksum,
            candidate.candidate_structural_checksum,
            threshold_set.threshold_set_checksum,
        )

        self.promote(freeze, candidate, threshold_set)

        self.assertEqual(
            before,
            (
                freeze.freeze_checksum,
                candidate.candidate_structural_checksum,
                threshold_set.threshold_set_checksum,
            ),
        )

    def test_alternate_candidate_not_substituted(self):
        freeze, _, threshold_set = self.bundle()

        with self.assertRaisesRegex(TechnicalRiskPolicyPromotionError, "candidate"):
            self.promote(freeze, technical_risk_candidate_b_spec(), threshold_set)

    def test_no_search_evaluator_producer_or_activation_api(self):
        import risk_integration
        import risk_integration.technical_risk_policy_promotion as promotion

        source = inspect.getsource(promotion)
        forbidden = (
            "candidate_list",
            "threshold_list",
            "find_best",
            "select_best",
            "search(",
            "rank(",
            "optimize",
            "TechnicalRiskEvaluator",
            "TechnicalRiskEvaluationResult",
            "TechnicalRiskSignalProducer",
            "RiskSignal(",
            "ProducedRiskSignal(",
            "active =",
            "latest",
            "default_policy",
            "deploy",
        )
        for token in forbidden:
            self.assertNotIn(token, source)
        self.assertIn("promote_research_freeze_to_production_policy", risk_integration.__all__)


if __name__ == "__main__":
    unittest.main()
