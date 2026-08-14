import sys
import unittest
from dataclasses import replace
from datetime import date
from decimal import ROUND_DOWN
from decimal import ROUND_UP
from decimal import Decimal
from decimal import getcontext
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import ALLOWED_CANDIDATE_SEVERITIES_V1
from risk_oos import HISTORICAL_RISK_FEATURE_SET_V1
from risk_oos import REQUIRED_THRESHOLD_DIMENSIONS_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos import TECHNICAL_RISK_V1_FEATURE_SET_ID
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import TechnicalRiskCandidateFamily
from risk_oos import TechnicalRiskCandidateRule
from risk_oos import TechnicalRiskCandidateSeverity
from risk_oos import TechnicalRiskPredicateId
from risk_oos import TechnicalRiskReasonCode
from risk_oos import TechnicalRiskRuleCandidateError
from risk_oos import TechnicalRiskRuleCandidateSpec
from risk_oos import TechnicalRiskThresholdDimension
from risk_oos import TechnicalRiskThresholdDimensionId
from risk_oos import TechnicalRiskThresholdOperator
from risk_oos import TechnicalRiskThresholdSet
from risk_oos import derive_technical_risk_evidence
from risk_oos import evaluate_technical_risk_predicates
from risk_oos import technical_risk_candidate_a_spec
from risk_oos import technical_risk_candidate_b_spec
from risk_oos import technical_risk_candidate_c_spec
from risk_oos import technical_risk_candidate_d_spec


class TechnicalRiskRuleCandidateContractTestCase(unittest.TestCase):

    def row(self, **overrides):
        values = {
            "row_id": "row_001",
            "observation_id": "obs_001",
            "symbol": "2330.TW",
            "evaluation_date": date(2026, 5, 1),
            "as_of_close": 95.0,
            "sma20": 100.0,
            "sma60": 110.0,
            "rsi14": 35.0,
            "feature_observation_checksum": "obs_checksum_001",
            "mae20_value": -0.05,
            "mae20_target_checksum": "mae20_checksum_001",
            "mae20_calculation_id": "mae20_calc_001",
            "mae20_target_start_date": date(2026, 5, 2),
            "mae20_target_end_date": date(2026, 5, 29),
            "mae60_value": -0.10,
            "mae60_target_checksum": "mae60_checksum_001",
            "mae60_calculation_id": "mae60_calc_001",
            "mae60_target_start_date": date(2026, 5, 2),
            "mae60_target_end_date": date(2026, 7, 30),
            "split_id": "development_2026_h1",
            "split_role": "DEVELOPMENT",
            "dataset_spec_id": "technical_risk_oos_dataset_v1",
            "dataset_spec_version": "v1",
        }
        values.update(overrides)
        return AlignedTechnicalRiskOOSRow(**values)

    def threshold_dimension(self, dimension_id, value, operator=TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL):
        return TechnicalRiskThresholdDimension(dimension_id, operator, value)

    def threshold_set(self, dimensions=None, **overrides):
        values = {
            "threshold_set_id": "threshold_set_dev_001",
            "threshold_set_version": "v1",
            "numeric_representation_version": TECH_RISK_NUMERIC_REPRESENTATION_V1,
            "dimensions": (
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.0250"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.0500"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.0200"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40.0"),
            )
            if dimensions is None
            else dimensions,
            "compatible_candidate_families": tuple(TechnicalRiskCandidateFamily),
        }
        values.update(overrides)
        return TechnicalRiskThresholdSet(**values)

    def test_same_raw_row_same_derived_evidence(self):
        first = derive_technical_risk_evidence(self.row())
        second = derive_technical_risk_evidence(self.row())

        self.assertEqual(first, second)
        self.assertEqual(first.derived_evidence_version, TECH_RISK_DERIVED_EVIDENCE_V1)
        self.assertEqual(first.close_vs_sma20, Decimal("-0.05"))
        self.assertEqual(first.close_vs_sma60, Decimal("-0.1363636363636363636363636363636364"))
        self.assertEqual(first.relative_sma_spread, Decimal("-0.09090909090909090909090909090909091"))

    def test_derived_evidence_uses_fixed_decimal_context(self):
        self.assertEqual(TECH_RISK_DECIMAL_CONTEXT_V1, "TECH_RISK_DECIMAL_CONTEXT_V1")
        self.assertEqual(TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1, 34)
        self.assertEqual(TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1, "ROUND_HALF_EVEN")
        baseline = derive_technical_risk_evidence(self.row())
        context = getcontext()
        original_precision = context.prec
        original_rounding = context.rounding
        try:
            context.prec = 12
            context.rounding = ROUND_DOWN
            low_precision = derive_technical_risk_evidence(self.row())
            context.prec = 50
            context.rounding = ROUND_UP
            high_precision = derive_technical_risk_evidence(self.row())
        finally:
            context.prec = original_precision
            context.rounding = original_rounding

        self.assertEqual(baseline, low_precision)
        self.assertEqual(baseline, high_precision)

    def test_input_float_representation_canonicalization_deterministic(self):
        float_row = self.row(sma20=100.0, sma60=110.0)
        decimal_like_row = self.row(sma20=100, sma60=110)

        self.assertEqual(derive_technical_risk_evidence(float_row), derive_technical_risk_evidence(decimal_like_row))

    def test_sma20_non_positive_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "sma20"):
            derive_technical_risk_evidence(self.row(sma20=0.0))

    def test_sma60_non_positive_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "sma60"):
            derive_technical_risk_evidence(self.row(sma60=-1.0))

    def test_same_threshold_semantics_same_checksum(self):
        first = self.threshold_set()
        second = self.threshold_set(
            dimensions=tuple(
                reversed(
                    (
                        self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.025"),
                        self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.05"),
                        self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.02"),
                        self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
                    )
                )
            )
        )

        self.assertEqual(first.threshold_set_checksum, second.threshold_set_checksum)

    def test_threshold_value_change_changes_checksum(self):
        first = self.threshold_set()
        second = self.threshold_set(
            dimensions=(
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.030"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.050"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.020"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
            )
        )

        self.assertNotEqual(first.threshold_set_checksum, second.threshold_set_checksum)

    def test_operator_change_rejected(self):
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "operator"):
            TechnicalRiskThresholdDimension(
                TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
                "GREATER_THAN",
                "-0.025",
            )

    def test_dimension_missing_fails(self):
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "exact"):
            self.threshold_set(
                dimensions=(
                    self.threshold_dimension(REQUIRED_THRESHOLD_DIMENSIONS_V1[0], "-0.025"),
                    self.threshold_dimension(REQUIRED_THRESHOLD_DIMENSIONS_V1[1], "-0.050"),
                )
            )

    def test_duplicate_dimension_fails(self):
        duplicate = (
            self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.025"),
            self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.030"),
            self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.050"),
            self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
        )

        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "Duplicate"):
            self.threshold_set(dimensions=duplicate)

    def test_same_candidate_structure_same_checksum(self):
        self.assertEqual(
            technical_risk_candidate_a_spec().candidate_structural_checksum,
            technical_risk_candidate_a_spec().candidate_structural_checksum,
        )

    def test_rule_changed_changes_candidate_checksum(self):
        candidate = technical_risk_candidate_a_spec()
        changed_rule = replace(candidate.rules[1], rule_priority=21)
        changed = replace(candidate, rules=(candidate.rules[0], changed_rule), candidate_structural_checksum=None)

        self.assertNotEqual(candidate.candidate_structural_checksum, changed.candidate_structural_checksum)

    def test_threshold_set_changed_does_not_change_candidate_structural_checksum(self):
        candidate = technical_risk_candidate_b_spec()
        first_thresholds = self.threshold_set()
        second_thresholds = self.threshold_set(
            dimensions=(
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.030"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.060"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.025"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "35"),
            )
        )

        self.assertNotEqual(first_thresholds.threshold_set_checksum, second_thresholds.threshold_set_checksum)
        self.assertEqual(candidate.candidate_structural_checksum, technical_risk_candidate_b_spec().candidate_structural_checksum)

    def test_critical_candidate_rule_rejected(self):
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "severity"):
            TechnicalRiskCandidateRule(
                "BAD_CRITICAL",
                "CRITICAL",
                (TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,),
                (),
                1,
                (TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,),
            )

    def test_volume_ratio_feature_rejected_from_v1_candidate(self):
        candidate = technical_risk_candidate_a_spec()
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "exact feature set"):
            replace(
                candidate,
                required_feature_ids=(*HISTORICAL_RISK_FEATURE_SET_V1, "TECH_VOLUME_RATIO_V1"),
                candidate_structural_checksum=None,
            )

    def test_candidate_a_structural_validation(self):
        candidate = technical_risk_candidate_a_spec()
        high = candidate.rules[0]

        self.assertEqual(candidate.policy_candidate_id, "TECH_POLICY_CANDIDATE_A")
        self.assertEqual(candidate.candidate_family, TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC)
        self.assertEqual(high.severity, TechnicalRiskCandidateSeverity.HIGH)
        self.assertIn(TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS, high.required_predicates)

    def test_candidate_b_structural_validation(self):
        candidate = technical_risk_candidate_b_spec()
        medium = candidate.rules[1]

        self.assertEqual(candidate.policy_candidate_id, "TECH_POLICY_CANDIDATE_B")
        self.assertEqual(candidate.candidate_family, TechnicalRiskCandidateFamily.STRUCTURE_FIRST)
        self.assertEqual(medium.required_predicates, (TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,))

    def test_candidate_c_short_term_weakness_cannot_create_high_alone(self):
        candidate = technical_risk_candidate_c_spec()
        high_rules = tuple(rule for rule in candidate.rules if rule.severity == TechnicalRiskCandidateSeverity.HIGH)

        self.assertTrue(high_rules)
        for rule in high_rules:
            self.assertNotEqual(rule.required_predicates, (TechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,))
            self.assertIn(TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS, rule.required_predicates)
            self.assertIn(TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS, rule.required_predicates)

    def test_candidate_d_high_requires_all_approved_predicates(self):
        candidate = technical_risk_candidate_d_spec()
        high = tuple(rule for rule in candidate.rules if rule.severity == TechnicalRiskCandidateSeverity.HIGH)[0]

        self.assertEqual(
            set(high.required_predicates),
            {
                TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
            },
        )

    def test_no_weighted_score_contract(self):
        candidate = technical_risk_candidate_d_spec()

        self.assertFalse(hasattr(candidate, "weighted_score"))
        self.assertFalse(hasattr(candidate, "probability"))
        self.assertFalse(any(hasattr(rule, "score") for rule in candidate.rules))

    def test_no_threshold_search_contract(self):
        threshold_set = self.threshold_set()

        self.assertFalse(hasattr(threshold_set, "search_grid"))
        self.assertFalse(hasattr(threshold_set, "optimizer"))
        self.assertFalse(hasattr(threshold_set, "selected_by_holdout"))

    def test_predicate_evaluation_is_boolean_only(self):
        evidence = derive_technical_risk_evidence(self.row())
        states = evaluate_technical_risk_predicates(evidence, self.row().rsi14, self.threshold_set())

        self.assertEqual(len(states), 4)
        self.assertTrue(all(isinstance(state.is_triggered, bool) for state in states))
        self.assertEqual(tuple(state.predicate_id for state in states), tuple(TechnicalRiskPredicateId))

    def test_bool_threshold_value_rejected(self):
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "Boolean"):
            self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, True)

    def test_non_finite_threshold_value_rejected(self):
        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "finite"):
            self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "NaN")

    def test_duplicate_rule_priority_rejected(self):
        first = TechnicalRiskCandidateRule(
            "R1",
            TechnicalRiskCandidateSeverity.MEDIUM,
            (TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,),
            (),
            10,
            (TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,),
        )
        second = TechnicalRiskCandidateRule(
            "R2",
            TechnicalRiskCandidateSeverity.HIGH,
            (
                TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
            ),
            (),
            10,
            (TechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,),
        )

        with self.assertRaisesRegex(TechnicalRiskRuleCandidateError, "Duplicate rule priority"):
            TechnicalRiskRuleCandidateSpec(
                policy_candidate_id="BAD",
                candidate_version="v1",
                candidate_family=TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC,
                rule_hierarchy_id="bad_hierarchy",
                required_feature_ids=HISTORICAL_RISK_FEATURE_SET_V1,
                derived_evidence_version=TECH_RISK_DERIVED_EVIDENCE_V1,
                allowed_predicate_ids=tuple(TechnicalRiskPredicateId),
                allowed_severities=ALLOWED_CANDIDATE_SEVERITIES_V1,
                trigger_vocabulary_version="TECH_RISK_TRIGGER_VOCABULARY_V1",
                evidence_vocabulary_version="TECH_RISK_EVIDENCE_VOCABULARY_V1",
                rules=(first, second),
            )

    def test_no_db_market_producer_or_metrics_boundary(self):
        source = (SRC_PATH / "risk_oos" / "rule_candidates.py").read_text()
        forbidden = (
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "pdf",
            "open(",
            "TargetGenerator",
            "TargetGenerationOutput",
            "RiskSeverity",
            "RiskSignal",
            "TechnicalRiskSignalProducer",
            "aggregate metric",
            "monotonicity",
            "Holdout evaluation",
        )
        for term in forbidden:
            self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
