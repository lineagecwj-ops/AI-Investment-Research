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

from risk_oos import TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1
from risk_oos import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos import TECH_RISK_LOW_REASON_V1
from risk_oos import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import TechnicalRiskCandidateEvaluationError
from risk_oos import TechnicalRiskCandidateEvaluationInput
from risk_oos import TechnicalRiskCandidateEvaluator
from risk_oos import TechnicalRiskCandidateSeverity
from risk_oos import TechnicalRiskMonotonicityStatus
from risk_oos import TechnicalRiskOOSDatasetResult
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskPredicateId
from risk_oos import TechnicalRiskReasonCode
from risk_oos import TechnicalRiskThresholdDimension
from risk_oos import TechnicalRiskThresholdDimensionId
from risk_oos import TechnicalRiskThresholdOperator
from risk_oos import TechnicalRiskThresholdSet
from risk_oos import technical_risk_candidate_a_spec
from risk_oos import technical_risk_candidate_b_spec
from risk_oos import technical_risk_candidate_c_spec
from risk_oos import technical_risk_candidate_d_spec


class TechnicalRiskCandidateEvaluatorTestCase(unittest.TestCase):

    def row(self, row_id="row_001", split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT, **overrides):
        values = {
            "row_id": row_id,
            "observation_id": f"obs_{row_id}",
            "symbol": "2330.TW",
            "evaluation_date": date(2026, 5, 1),
            "as_of_close": 80.0,
            "sma20": 90.0,
            "sma60": 100.0,
            "rsi14": 35.0,
            "feature_observation_checksum": f"obs_checksum_{row_id}",
            "mae20_value": -0.08,
            "mae20_target_checksum": f"mae20_checksum_{row_id}",
            "mae20_calculation_id": f"mae20_calc_{row_id}",
            "mae20_target_start_date": date(2026, 5, 2),
            "mae20_target_end_date": date(2026, 5, 29),
            "mae60_value": -0.12,
            "mae60_target_checksum": f"mae60_checksum_{row_id}",
            "mae60_calculation_id": f"mae60_calc_{row_id}",
            "mae60_target_start_date": date(2026, 5, 2),
            "mae60_target_end_date": date(2026, 7, 30),
            "split_id": f"{split_role.value.lower()}_split",
            "split_role": split_role,
            "dataset_spec_id": "technical_risk_oos_dataset_v1",
            "dataset_spec_version": "v1",
        }
        values.update(overrides)
        return AlignedTechnicalRiskOOSRow(**values)

    def dataset(self, rows):
        return TechnicalRiskOOSDatasetResult(
            included_rows=tuple(rows),
            excluded_records=(),
            dataset_id="technical_risk_oos_dataset_test",
            dataset_checksum="dataset_checksum_test",
            summary_counts={"included_rows": len(rows)},
        )

    def threshold_dimension(self, dimension_id, value):
        return TechnicalRiskThresholdDimension(
            dimension_id=dimension_id,
            operator=TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            canonical_value=value,
        )

    def threshold_set(self, **overrides):
        values = {
            "threshold_set_id": "threshold_set_001",
            "threshold_set_version": "v1",
            "numeric_representation_version": TECH_RISK_NUMERIC_REPRESENTATION_V1,
            "dimensions": (
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
            ),
            "compatible_candidate_families": tuple(type(technical_risk_candidate_a_spec().candidate_family)),
        }
        values.update(overrides)
        return TechnicalRiskThresholdSet(**values)

    def evaluation_input(self, dataset, candidate, threshold_set, roles=(TechnicalRiskOOSSplitRole.DEVELOPMENT,), **overrides):
        values = {
            "evaluation_input_version": TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1,
            "dataset_id": dataset.dataset_id,
            "dataset_checksum": dataset.dataset_checksum,
            "candidate_id": candidate.policy_candidate_id,
            "candidate_version": candidate.candidate_version,
            "candidate_structural_checksum": candidate.candidate_structural_checksum,
            "threshold_set_id": threshold_set.threshold_set_id,
            "threshold_set_version": threshold_set.threshold_set_version,
            "threshold_set_checksum": threshold_set.threshold_set_checksum,
            "derived_evidence_version": TECH_RISK_DERIVED_EVIDENCE_V1,
            "evaluator_version": TECH_RISK_CANDIDATE_EVALUATOR_V1,
            "metric_version": TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            "quantile_version": TECH_RISK_QUANTILE_NEAREST_RANK_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
            "allowed_split_roles": roles,
        }
        values.update(overrides)
        return TechnicalRiskCandidateEvaluationInput(**values)

    def evaluate(self, rows, candidate=None, threshold_set=None, roles=(TechnicalRiskOOSSplitRole.DEVELOPMENT,)):
        candidate = technical_risk_candidate_a_spec() if candidate is None else candidate
        threshold_set = self.threshold_set() if threshold_set is None else threshold_set
        dataset = self.dataset(rows)
        return TechnicalRiskCandidateEvaluator().evaluate(
            dataset,
            candidate,
            threshold_set,
            self.evaluation_input(dataset, candidate, threshold_set, roles=roles),
        )

    def metric(self, result, split_role, severity):
        matches = tuple(
            metric for metric in result.aggregate_metrics
            if metric.split_role == split_role and metric.severity == severity
        )
        self.assertEqual(len(matches), 1)
        return matches[0]

    def monotonicity(self, result, split_role, horizon):
        matches = tuple(
            item for item in result.monotonicity_results
            if item.split_role == split_role and item.horizon == horizon
        )
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_candidate_a_valid_row_evaluation(self):
        result = self.evaluate((self.row(),), candidate=technical_risk_candidate_a_spec())
        row = result.row_evaluations[0]

        self.assertEqual(row.severity, TechnicalRiskCandidateSeverity.HIGH)
        self.assertEqual(row.matched_rule_id, "A_HIGH_MULTI_EVIDENCE")
        self.assertIn(TechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION.value, row.reason_codes)

    def test_candidate_b_valid_row_evaluation(self):
        result = self.evaluate((self.row(),), candidate=technical_risk_candidate_b_spec())

        self.assertEqual(result.row_evaluations[0].severity, TechnicalRiskCandidateSeverity.HIGH)
        self.assertEqual(result.row_evaluations[0].matched_rule_id, "B_HIGH_STRUCTURE_WITH_CONFIRMATION")

    def test_candidate_c_short_only_is_medium_and_never_high(self):
        row = self.row(as_of_close=95.0, sma20=100.0, sma60=90.0, rsi14=50.0)
        result = self.evaluate((row,), candidate=technical_risk_candidate_c_spec())
        evaluation = result.row_evaluations[0]

        self.assertEqual(evaluation.severity, TechnicalRiskCandidateSeverity.MEDIUM)
        self.assertNotEqual(evaluation.severity, TechnicalRiskCandidateSeverity.HIGH)
        self.assertEqual(evaluation.matched_rule_id, "C_MEDIUM_SHORT_PRICE_EARLY_WARNING")

    def test_candidate_d_all_three_confirmations_is_high(self):
        result = self.evaluate((self.row(),), candidate=technical_risk_candidate_d_spec())

        self.assertEqual(result.row_evaluations[0].severity, TechnicalRiskCandidateSeverity.HIGH)
        self.assertEqual(result.row_evaluations[0].matched_rule_id, "D_HIGH_STRICT_MULTI_EVIDENCE")

    def test_unmatched_rules_are_low_with_neutral_reason(self):
        row = self.row(as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0)
        result = self.evaluate((row,), candidate=technical_risk_candidate_a_spec())
        evaluation = result.row_evaluations[0]

        self.assertEqual(evaluation.severity, TechnicalRiskCandidateSeverity.LOW)
        self.assertIsNone(evaluation.matched_rule_id)
        self.assertEqual(evaluation.reason_codes, (TECH_RISK_LOW_REASON_V1,))

    def test_high_precedence_over_medium_and_matched_rule_deterministic(self):
        first = self.evaluate((self.row(),), candidate=technical_risk_candidate_a_spec()).row_evaluations[0]
        second = self.evaluate((self.row(),), candidate=technical_risk_candidate_a_spec()).row_evaluations[0]

        self.assertEqual(first.severity, TechnicalRiskCandidateSeverity.HIGH)
        self.assertEqual(first.matched_rule_id, "A_HIGH_MULTI_EVIDENCE")
        self.assertEqual(first.matched_rule_id, second.matched_rule_id)

    def test_optional_confirmation_does_not_affect_match_but_adds_reason(self):
        row = self.row(as_of_close=80.0, sma20=120.0, sma60=100.0, rsi14=35.0)
        result = self.evaluate((row,), candidate=technical_risk_candidate_a_spec())
        evaluation = result.row_evaluations[0]

        self.assertEqual(evaluation.severity, TechnicalRiskCandidateSeverity.MEDIUM)
        self.assertEqual(evaluation.matched_rule_id, "A_MEDIUM_MEDIUM_PRICE_WEAKNESS")
        self.assertIn(TechnicalRiskReasonCode.MOMENTUM_WEAKNESS_CONFIRMATION.value, evaluation.reason_codes)

    def test_mae_never_affects_predicate_or_severity(self):
        first = self.evaluate((self.row(mae20_value=0.0, mae60_value=0.0),)).row_evaluations[0]
        second = self.evaluate((self.row(mae20_value=-0.90, mae60_value=-0.95),)).row_evaluations[0]

        self.assertEqual(first.severity, second.severity)
        self.assertEqual(first.predicate_states, second.predicate_states)

    def test_threshold_change_can_change_predicate_and_severity(self):
        strict = self.threshold_set(
            dimensions=(
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.20"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.30"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.20"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "20"),
            )
        )

        loose_result = self.evaluate((self.row(),), threshold_set=self.threshold_set())
        strict_result = self.evaluate((self.row(),), threshold_set=strict)

        self.assertEqual(loose_result.row_evaluations[0].severity, TechnicalRiskCandidateSeverity.HIGH)
        self.assertEqual(strict_result.row_evaluations[0].severity, TechnicalRiskCandidateSeverity.LOW)

    def test_threshold_set_and_dataset_are_not_mutated(self):
        threshold_set = self.threshold_set()
        dataset = self.dataset((self.row(),))
        threshold_before = repr(threshold_set)
        dataset_before = repr(dataset)
        candidate = technical_risk_candidate_a_spec()

        TechnicalRiskCandidateEvaluator().evaluate(
            dataset,
            candidate,
            threshold_set,
            self.evaluation_input(dataset, candidate, threshold_set),
        )

        self.assertEqual(repr(threshold_set), threshold_before)
        self.assertEqual(repr(dataset), dataset_before)

    def test_mean_median_and_quantiles_are_decimal_and_deterministic(self):
        rows = (
            self.row("low1", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("0"), mae60_value=Decimal("0")),
            self.row("low2", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.02"), mae60_value=Decimal("-0.03")),
            self.row("low3", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.04"), mae60_value=Decimal("-0.06")),
            self.row("low4", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.08"), mae60_value=Decimal("-0.09")),
        )
        result = self.evaluate(rows)
        metric = self.metric(result, TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.LOW)

        self.assertEqual(metric.mae20_mean, Decimal("-0.035"))
        self.assertEqual(metric.mae20_median, Decimal("-0.03"))
        self.assertEqual(metric.mae20_p25, Decimal("-0.08"))
        self.assertEqual(metric.mae20_p75, Decimal("-0.02"))
        self.assertIsInstance(metric.mae20_mean, Decimal)

    def test_median_odd_and_nearest_rank_n_1_2_3_4(self):
        rows = (
            self.row("low1", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.01")),
            self.row("low2", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.02")),
            self.row("low3", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.03")),
        )
        metric = self.metric(self.evaluate(rows), TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.LOW)
        self.assertEqual(metric.mae20_median, Decimal("-0.02"))
        self.assertEqual(metric.mae20_p25, Decimal("-0.03"))
        self.assertEqual(metric.mae20_p75, Decimal("-0.01"))

        one = self.metric(self.evaluate((rows[0],)), TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.LOW)
        two = self.metric(self.evaluate(rows[:2]), TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.LOW)
        four = self.metric(self.evaluate((*rows, self.row("low4", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.04")))), TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.LOW)
        self.assertEqual((one.mae20_p25, one.mae20_p75), (Decimal("-0.01"), Decimal("-0.01")))
        self.assertEqual((two.mae20_p25, two.mae20_p75), (Decimal("-0.02"), Decimal("-0.01")))
        self.assertEqual((four.mae20_p25, four.mae20_p75), (Decimal("-0.04"), Decimal("-0.02")))

    def test_quantile_version_enforced(self):
        dataset = self.dataset((self.row(),))
        candidate = technical_risk_candidate_a_spec()
        threshold_set = self.threshold_set()

        with self.assertRaisesRegex(TechnicalRiskCandidateEvaluationError, "quantile_version"):
            self.evaluation_input(dataset, candidate, threshold_set, quantile_version="OTHER")

    def test_empty_bucket_semantics_and_coverage_completion(self):
        result = self.evaluate((self.row(),), candidate=technical_risk_candidate_d_spec())
        low = self.metric(result, TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.LOW)
        medium = self.metric(result, TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.MEDIUM)
        high = self.metric(result, TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.HIGH)

        self.assertEqual(low.sample_count, 0)
        self.assertEqual(low.coverage_ratio, Decimal("0"))
        self.assertIsNone(low.mae20_mean)
        self.assertEqual(high.coverage_ratio, Decimal("1"))
        self.assertEqual(low.coverage_ratio + medium.coverage_ratio + high.coverage_ratio, Decimal("1"))

    def test_coverage_denominator_is_split_included_rows(self):
        rows = (
            self.row("dev_high", split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT),
            self.row("dev_low", split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT, as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0),
            self.row("val_high", split_role=TechnicalRiskOOSSplitRole.VALIDATION, evaluation_date=date(2026, 8, 1)),
        )
        result = self.evaluate(rows, roles=(TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskOOSSplitRole.VALIDATION))

        self.assertEqual(self.metric(result, TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskCandidateSeverity.HIGH).coverage_ratio, Decimal("0.5"))
        self.assertEqual(self.metric(result, TechnicalRiskOOSSplitRole.VALIDATION, TechnicalRiskCandidateSeverity.HIGH).coverage_ratio, Decimal("1"))

    def test_mae20_and_mae60_monotonic_pass_warning_empty_and_equality(self):
        pass_rows = (
            self.row("low", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("0"), mae60_value=Decimal("0")),
            self.row("medium", as_of_close=80.0, sma20=90.0, sma60=120.0, rsi14=50.0, mae20_value=Decimal("-0.03"), mae60_value=Decimal("-0.04")),
            self.row("high", mae20_value=Decimal("-0.08"), mae60_value=Decimal("-0.10")),
        )
        pass_result = self.evaluate(pass_rows)
        self.assertEqual(self.monotonicity(pass_result, TechnicalRiskOOSSplitRole.DEVELOPMENT, 20).status, TechnicalRiskMonotonicityStatus.PASS)
        self.assertEqual(self.monotonicity(pass_result, TechnicalRiskOOSSplitRole.DEVELOPMENT, 60).status, TechnicalRiskMonotonicityStatus.PASS)

        warning_rows = (
            self.row("low", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.10")),
            self.row("medium", as_of_close=80.0, sma20=90.0, sma60=120.0, rsi14=50.0, mae20_value=Decimal("-0.03")),
            self.row("high", mae20_value=Decimal("-0.08")),
        )
        warning_result = self.evaluate(warning_rows)
        self.assertEqual(self.monotonicity(warning_result, TechnicalRiskOOSSplitRole.DEVELOPMENT, 20).status, TechnicalRiskMonotonicityStatus.WARNING)

        empty_result = self.evaluate((self.row(),), candidate=technical_risk_candidate_d_spec())
        self.assertEqual(self.monotonicity(empty_result, TechnicalRiskOOSSplitRole.DEVELOPMENT, 20).status, TechnicalRiskMonotonicityStatus.NOT_EVALUABLE)

        equality_rows = (
            self.row("low", as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0, mae20_value=Decimal("-0.05")),
            self.row("medium", as_of_close=80.0, sma20=90.0, sma60=120.0, rsi14=50.0, mae20_value=Decimal("-0.05")),
            self.row("high", mae20_value=Decimal("-0.05")),
        )
        equality_result = self.evaluate(equality_rows)
        self.assertEqual(self.monotonicity(equality_result, TechnicalRiskOOSSplitRole.DEVELOPMENT, 20).status, TechnicalRiskMonotonicityStatus.PASS)

    def test_multi_split_metrics_remain_separated_with_no_combined_aggregate(self):
        rows = (
            self.row("dev_high", split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT),
            self.row("val_low", split_role=TechnicalRiskOOSSplitRole.VALIDATION, evaluation_date=date(2026, 8, 1), as_of_close=110.0, sma20=100.0, sma60=90.0, rsi14=50.0),
            self.row("hold_high", split_role=TechnicalRiskOOSSplitRole.HOLDOUT, evaluation_date=date(2026, 10, 1)),
        )
        result = self.evaluate(rows, roles=(TechnicalRiskOOSSplitRole.HOLDOUT, TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskOOSSplitRole.VALIDATION))

        self.assertEqual(result.evaluated_split_roles, (TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskOOSSplitRole.VALIDATION, TechnicalRiskOOSSplitRole.HOLDOUT))
        self.assertEqual(len(result.aggregate_metrics), 9)
        self.assertFalse(any(getattr(metric, "combined_split_role", None) for metric in result.aggregate_metrics))

    def test_same_frozen_inputs_same_evaluation_id_and_checksum(self):
        rows = (self.row("b", symbol="2454.TW"), self.row("a", symbol="2330.TW"))
        first = self.evaluate(rows)
        second = self.evaluate(tuple(reversed(rows)))

        self.assertEqual(first.evaluation_id, second.evaluation_id)
        self.assertEqual(first.evaluation_checksum, second.evaluation_checksum)

    def test_global_decimal_context_changes_do_not_change_evaluation_outputs(self):
        rows = (
            self.row("low", as_of_close=100, sma20=95, sma60=90, rsi14=50, mae20_value=Decimal("0"), mae60_value=Decimal("0")),
            self.row("medium", as_of_close=100, sma20=125, sma60=110, rsi14=50, mae20_value=Decimal("-0.02"), mae60_value=Decimal("-0.04")),
            self.row("high", as_of_close=100, sma20=103, sma60=109, rsi14=35, mae20_value=Decimal("-0.03"), mae60_value=Decimal("-0.05")),
        )
        baseline = self.evaluation_payload(self.evaluate(rows))

        context = getcontext()
        original_precision = context.prec
        original_rounding = context.rounding
        try:
            context.prec = 12
            context.rounding = ROUND_DOWN
            low_precision = self.evaluation_payload(self.evaluate(rows))
            context.prec = 50
            context.rounding = ROUND_UP
            high_precision = self.evaluation_payload(self.evaluate(rows))
        finally:
            context.prec = original_precision
            context.rounding = original_rounding

        self.assertEqual(baseline, low_precision)
        self.assertEqual(baseline, high_precision)

    def test_evaluator_preserves_caller_decimal_context(self):
        context = getcontext()
        original_precision = context.prec
        original_rounding = context.rounding
        context.prec = 12
        context.rounding = ROUND_DOWN
        try:
            self.evaluate((self.row(),))
            self.assertEqual(context.prec, 12)
            self.assertEqual(context.rounding, ROUND_DOWN)
        finally:
            context.prec = original_precision
            context.rounding = original_rounding

    def test_numeric_context_version_is_first_class_lineage(self):
        result = self.evaluate((self.row(),))

        self.assertEqual(TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1, 34)
        self.assertEqual(TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1, "ROUND_HALF_EVEN")
        self.assertEqual(result.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1)

    def test_numeric_context_version_enforced(self):
        dataset = self.dataset((self.row(),))
        candidate = technical_risk_candidate_a_spec()
        threshold_set = self.threshold_set()

        with self.assertRaisesRegex(TechnicalRiskCandidateEvaluationError, "numeric_context_version"):
            self.evaluation_input(dataset, candidate, threshold_set, numeric_context_version="OTHER")

    def test_identity_echo_mismatches_fail_whole_evaluation(self):
        dataset = self.dataset((self.row(),))
        candidate = technical_risk_candidate_a_spec()
        threshold_set = self.threshold_set()
        evaluator = TechnicalRiskCandidateEvaluator()

        with self.assertRaisesRegex(TechnicalRiskCandidateEvaluationError, "dataset_checksum"):
            evaluator.evaluate(dataset, candidate, threshold_set, self.evaluation_input(dataset, candidate, threshold_set, dataset_checksum="changed"))
        with self.assertRaisesRegex(TechnicalRiskCandidateEvaluationError, "candidate_structural_checksum"):
            evaluator.evaluate(dataset, candidate, threshold_set, self.evaluation_input(dataset, candidate, threshold_set, candidate_structural_checksum="changed"))
        with self.assertRaisesRegex(TechnicalRiskCandidateEvaluationError, "threshold_set_checksum"):
            evaluator.evaluate(dataset, candidate, threshold_set, self.evaluation_input(dataset, candidate, threshold_set, threshold_set_checksum="changed"))

    def test_threshold_candidate_and_split_changes_affect_evaluation_identity(self):
        dataset = self.dataset((self.row(),))
        candidate = technical_risk_candidate_a_spec()
        threshold_set = self.threshold_set()
        base = TechnicalRiskCandidateEvaluator().evaluate(dataset, candidate, threshold_set, self.evaluation_input(dataset, candidate, threshold_set))
        changed_threshold = self.threshold_set(
            dimensions=(
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF, "-0.06"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF, "-0.05"),
                self.threshold_dimension(TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF, "40"),
            )
        )
        changed_candidate = replace(technical_risk_candidate_b_spec(), candidate_structural_checksum=None)

        threshold_result = TechnicalRiskCandidateEvaluator().evaluate(dataset, candidate, changed_threshold, self.evaluation_input(dataset, candidate, changed_threshold))
        candidate_result = TechnicalRiskCandidateEvaluator().evaluate(dataset, changed_candidate, threshold_set, self.evaluation_input(dataset, changed_candidate, threshold_set))
        split_result = TechnicalRiskCandidateEvaluator().evaluate(
            dataset,
            candidate,
            threshold_set,
            self.evaluation_input(dataset, candidate, threshold_set, roles=(TechnicalRiskOOSSplitRole.DEVELOPMENT, TechnicalRiskOOSSplitRole.VALIDATION)),
        )

        self.assertNotEqual(base.evaluation_id, threshold_result.evaluation_id)
        self.assertNotEqual(base.evaluation_id, candidate_result.evaluation_id)
        self.assertNotEqual(base.evaluation_id, split_result.evaluation_id)

    def evaluation_payload(self, result):
        return {
            "evaluation_id": result.evaluation_id,
            "evaluation_checksum": result.evaluation_checksum,
            "rows": tuple(
                (
                    row.row_id,
                    str(row.close_vs_sma20),
                    str(row.close_vs_sma60),
                    str(row.relative_sma_spread),
                    tuple((state.predicate_id.value, state.is_triggered) for state in row.predicate_states),
                    row.severity.value,
                    row.matched_rule_id,
                    row.reason_codes,
                )
                for row in result.row_evaluations
            ),
            "metrics": tuple(
                (
                    metric.split_role.value,
                    metric.severity.value,
                    metric.sample_count,
                    str(metric.coverage_ratio),
                    None if metric.mae20_mean is None else str(metric.mae20_mean),
                    None if metric.mae20_median is None else str(metric.mae20_median),
                    None if metric.mae20_p25 is None else str(metric.mae20_p25),
                    None if metric.mae20_p75 is None else str(metric.mae20_p75),
                    None if metric.mae60_mean is None else str(metric.mae60_mean),
                    None if metric.mae60_median is None else str(metric.mae60_median),
                    None if metric.mae60_p25 is None else str(metric.mae60_p25),
                    None if metric.mae60_p75 is None else str(metric.mae60_p75),
                )
                for metric in result.aggregate_metrics
            ),
            "monotonicity": tuple(
                (
                    item.split_role.value,
                    item.horizon,
                    item.status.value,
                    None if item.low_median is None else str(item.low_median),
                    None if item.medium_median is None else str(item.medium_median),
                    None if item.high_median is None else str(item.high_median),
                    item.reason_code,
                )
                for item in result.monotonicity_results
            ),
        }

    def test_invalid_raw_feature_fails_whole_evaluation(self):
        with self.assertRaisesRegex(TechnicalRiskCandidateEvaluationError, "sma20"):
            self.evaluate((self.row(sma20=0.0),))

    def test_no_threshold_search_binary_or_production_boundary(self):
        source = (SRC_PATH / "risk_oos" / "candidate_evaluator.py").read_text()
        forbidden = (
            "def search",
            "def optimize",
            "evaluate_best",
            "threshold_grid",
            "candidate_list",
            "best_threshold",
            "best_candidate",
            "false_alert",
            "downside_capture",
            "precision",
            "recall",
            "binary severe downside",
            "from risk import RiskSeverity",
            "from risk import RiskSignal",
            "TechnicalRiskSignalProducer",
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "pdf",
            "open(",
        )
        for term in forbidden:
            self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
