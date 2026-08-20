import inspect
import sys
import unittest
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1
from risk_oos import TECHNICAL_RISK_V1_THRESHOLD_AXIS_EVIDENCE_NEAREST_RANK_LOWER_TAIL_V1
from risk_oos import TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_SEARCH_USAGE
from risk_oos import TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1
from risk_oos import TechnicalRiskCandidateFamily
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskThresholdAxisSetApprovalStatus
from risk_oos import TechnicalRiskThresholdAxisSetError
from risk_oos import TechnicalRiskThresholdDimensionId
from risk_oos import TechnicalRiskThresholdGridMaterializer
from risk_oos import TechnicalRiskThresholdOperator
from risk_oos import build_technical_risk_v1_threshold_axis_set
from risk_oos import materialize_technical_risk_v1_threshold_grid


class TechnicalRiskThresholdAxisSetTestCase(unittest.TestCase):
    def axis_set(self):
        return build_technical_risk_v1_threshold_axis_set()

    def test_exact_axis_set_version_and_approval_status(self):
        axis_set = self.axis_set()

        self.assertEqual(axis_set.axis_set_version, TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1)
        self.assertEqual(
            axis_set.approval_status,
            TechnicalRiskThresholdAxisSetApprovalStatus.APPROVED_FOR_VALIDATION_SEARCH,
        )
        self.assertEqual(axis_set.eligible_usage, TECHNICAL_RISK_V1_VALIDATION_SEARCH_USAGE)

    def test_exact_approved_axis_values_are_canonical_decimal_strings(self):
        axis_set = self.axis_set()

        self.assertEqual(axis_set.close_vs_sma20_values, ("-0.015", "-0.03", "-0.05"))
        self.assertEqual(axis_set.close_vs_sma60_values, ("-0.025", "-0.045", "-0.085"))
        self.assertEqual(axis_set.relative_sma_spread_values, ("-0.015", "-0.035", "-0.06"))
        self.assertEqual(axis_set.rsi14_values, ("29", "37", "43"))

    def test_exact_four_dimensions_and_less_than_or_equal_operator(self):
        axis_set = self.axis_set()
        spec = axis_set.to_grid_spec()
        result = TechnicalRiskThresholdGridMaterializer().materialize(spec)

        self.assertEqual(set(axis_set.axis_values_by_dimension), set(TechnicalRiskThresholdDimensionId))
        for threshold_set in result.threshold_sets:
            self.assertEqual(set(threshold_set.dimensions_by_id), set(TechnicalRiskThresholdDimensionId))
            self.assertTrue(
                all(
                    dimension.operator == TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL
                    for dimension in threshold_set.dimensions
                )
            )

    def test_evidence_lineage_is_development_only_and_methodology_bound(self):
        axis_set = self.axis_set()

        self.assertEqual(axis_set.methodology_version, TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1)
        self.assertEqual(axis_set.evidence_split_role, TechnicalRiskOOSSplitRole.DEVELOPMENT)
        self.assertEqual(axis_set.evidence_window_start.isoformat(), "2018-01-01")
        self.assertEqual(axis_set.evidence_window_end.isoformat(), "2021-12-31")
        self.assertEqual(
            axis_set.evidence_quantile_method_version,
            TECHNICAL_RISK_V1_THRESHOLD_AXIS_EVIDENCE_NEAREST_RANK_LOWER_TAIL_V1,
        )
        self.assertEqual(axis_set.evidence_quantile_anchors, ("p10", "p20", "p30"))

    def test_validation_and_holdout_are_not_accepted_as_evidence_roles(self):
        axis_set = self.axis_set()

        with self.assertRaisesRegex(TechnicalRiskThresholdAxisSetError, "DEVELOPMENT"):
            replace(axis_set, axis_set_id=None, axis_set_checksum=None, evidence_split_role=TechnicalRiskOOSSplitRole.VALIDATION)
        with self.assertRaisesRegex(TechnicalRiskThresholdAxisSetError, "DEVELOPMENT"):
            replace(axis_set, axis_set_id=None, axis_set_checksum=None, evidence_split_role=TechnicalRiskOOSSplitRole.HOLDOUT)

    def test_axis_set_identity_and_checksum_are_deterministic(self):
        first = self.axis_set()
        second = self.axis_set()

        self.assertEqual(first.axis_set_id, second.axis_set_id)
        self.assertEqual(first.axis_set_checksum, second.axis_set_checksum)

    def test_axis_value_mutation_changes_identity_and_checksum(self):
        first = self.axis_set()
        changed = replace(
            first,
            axis_set_id=None,
            axis_set_checksum=None,
            close_vs_sma20_values=("-0.051", "-0.030", "-0.015"),
        )

        self.assertNotEqual(first.axis_set_id, changed.axis_set_id)
        self.assertNotEqual(first.axis_set_checksum, changed.axis_set_checksum)

    def test_status_mutation_fails_closed(self):
        axis_set = self.axis_set()

        with self.assertRaisesRegex(TechnicalRiskThresholdAxisSetError, "approval_status"):
            replace(axis_set, axis_set_id=None, axis_set_checksum=None, approval_status="APPROVED_FOR_PRODUCTION")

    def test_repeated_factory_result_and_grid_result_are_identical(self):
        first = materialize_technical_risk_v1_threshold_grid()
        second = materialize_technical_risk_v1_threshold_grid()

        self.assertEqual(first.grid_result_id, second.grid_result_id)
        self.assertEqual(first.grid_result_checksum, second.grid_result_checksum)
        self.assertEqual(
            tuple(threshold.threshold_set_id for threshold in first.threshold_sets),
            tuple(threshold.threshold_set_id for threshold in second.threshold_sets),
        )

    def test_existing_grid_materializer_is_reused_and_exact_grid_size_is_81(self):
        axis_set = self.axis_set()
        spec = axis_set.to_grid_spec()
        result = materialize_technical_risk_v1_threshold_grid()

        self.assertEqual(spec.generation_method_id, TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1)
        self.assertEqual(set(spec.compatible_candidate_families), set(TechnicalRiskCandidateFamily))
        self.assertEqual(len(result.threshold_sets), 81)
        self.assertEqual(len({threshold.threshold_set_id for threshold in result.threshold_sets}), 81)
        self.assertEqual(len({threshold.threshold_set_checksum for threshold in result.threshold_sets}), 81)

    def test_grid_materialization_preserves_generation_contract(self):
        result = materialize_technical_risk_v1_threshold_grid()

        self.assertEqual(
            result.generation_contract.generated_threshold_set_ids,
            tuple(threshold.threshold_set_id for threshold in result.threshold_sets),
        )
        self.assertEqual(
            result.generation_contract.generated_threshold_set_checksums,
            tuple(threshold.threshold_set_checksum for threshold in result.threshold_sets),
        )

    def test_candidate_outcome_holdout_persistence_and_network_boundaries(self):
        import risk_oos.threshold_axis_set as threshold_axis_set

        source = inspect.getsource(threshold_axis_set)
        forbidden_tokens = (
            "TECH_POLICY_CANDIDATE_A",
            "TECH_POLICY_CANDIDATE_B",
            "TECH_POLICY_CANDIDATE_C",
            "TECH_POLICY_CANDIDATE_D",
            "selected_policy",
            "selected_threshold",
            "winner",
            "best_threshold",
            "APPROVED_FOR_PRODUCTION",
            "HOLDOUT_CONFIRMED",
            "FROZEN",
            "MAE20",
            "MAE60",
            "sqlite",
            "write_text",
            "open(",
            "production_runtime",
            "data/production",
            "Yahoo",
            "yfinance",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
