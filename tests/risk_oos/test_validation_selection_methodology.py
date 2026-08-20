import inspect
import unittest
from dataclasses import replace

from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1
from risk_oos import TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1
from risk_oos import TECH_RISK_ROBUST_REGION_APPROVED_GRID_TOPOLOGY_V1
from risk_oos import TechnicalRiskMonotonicityStatus
from risk_oos import TechnicalRiskTiePolicy
from risk_oos import TechnicalRiskValidationGridPoint
from risk_oos import TechnicalRiskValidationSelectionMethodology
from risk_oos import TechnicalRiskValidationSelectionMethodologyApprovalStatus
from risk_oos import TechnicalRiskValidationSelectionMethodologyError
from risk_oos import TechnicalRiskValidationSelectionMethodologyName
from risk_oos import TechnicalRiskValidationSelectionMethodologyProvenance
from risk_oos import build_technical_risk_v1_validation_selection_methodology
import risk_oos
import risk_oos.validation_selection_methodology as methodology_module


class TechnicalRiskValidationSelectionMethodologyTestCase(unittest.TestCase):
    def methodology(self, **overrides):
        values = {
            "methodology_id": None,
            "methodology_version": TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
            "methodology_name": TechnicalRiskValidationSelectionMethodologyName.ROBUST_REGION_FIRST,
            "approval_status": TechnicalRiskValidationSelectionMethodologyApprovalStatus.APPROVED_FOR_VALIDATION_SELECTION,
            "provenance": TechnicalRiskValidationSelectionMethodologyProvenance.POST_VALIDATION_METHOD_DECISION,
            "validation_evidence_artifact_id": TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID,
            "validation_evidence_artifact_checksum": TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
            "required_monotonicity_status": TechnicalRiskMonotonicityStatus.PASS,
            "required_monotonicity_horizons": (20, 60),
            "robust_region_topology_version": TECH_RISK_ROBUST_REGION_APPROVED_GRID_TOPOLOGY_V1,
            "structured_evidence_dimensions": methodology_module.APPROVED_STRUCTURED_EVIDENCE_DIMENSIONS_V1,
            "numeric_floor_policy": TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1,
            "tie_policy": TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION,
            "weighted_score_allowed": False,
            "candidate_preference_allowed": False,
            "methodology_checksum": None,
        }
        values.update(overrides)
        return TechnicalRiskValidationSelectionMethodology(**values)

    def point(self, candidate="TECH_POLICY_CANDIDATE_A", threshold="threshold_1", coordinates=(0, 0, 0, 0), mae20="PASS", mae60="PASS"):
        return TechnicalRiskValidationGridPoint(
            candidate_id=candidate,
            threshold_set_id=threshold,
            grid_coordinates=coordinates,
            mae20_monotonicity_status=mae20,
            mae60_monotonicity_status=mae60,
        )

    def test_exact_methodology_version_and_builder(self):
        methodology = build_technical_risk_v1_validation_selection_methodology()

        self.assertEqual(methodology.methodology_version, TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1)
        self.assertEqual(methodology.methodology_name, TechnicalRiskValidationSelectionMethodologyName.ROBUST_REGION_FIRST)

    def test_approval_status(self):
        methodology = self.methodology()

        self.assertEqual(
            methodology.approval_status,
            TechnicalRiskValidationSelectionMethodologyApprovalStatus.APPROVED_FOR_VALIDATION_SELECTION,
        )

    def test_post_validation_provenance(self):
        methodology = self.methodology()

        self.assertEqual(
            methodology.provenance,
            TechnicalRiskValidationSelectionMethodologyProvenance.POST_VALIDATION_METHOD_DECISION,
        )

    def test_mae20_pass_required(self):
        methodology = self.methodology()

        self.assertFalse(
            methodology.is_dual_horizon_eligible(
                mae20_monotonicity_status=TechnicalRiskMonotonicityStatus.WARNING,
                mae60_monotonicity_status=TechnicalRiskMonotonicityStatus.PASS,
            )
        )

    def test_mae60_pass_required(self):
        methodology = self.methodology()

        self.assertFalse(
            methodology.is_dual_horizon_eligible(
                mae20_monotonicity_status=TechnicalRiskMonotonicityStatus.PASS,
                mae60_monotonicity_status=TechnicalRiskMonotonicityStatus.WARNING,
            )
        )

    def test_pass_pass_eligible(self):
        methodology = self.methodology()

        self.assertTrue(
            methodology.is_dual_horizon_eligible(
                mae20_monotonicity_status="PASS",
                mae60_monotonicity_status="PASS",
            )
        )

    def test_pass_warning_rejected_from_robust_region(self):
        methodology = self.methodology()

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionMethodologyError, "PASS/PASS"):
            methodology.connected_robust_regions((self.point(mae20="PASS", mae60="WARNING"),))

    def test_warning_pass_rejected_from_robust_region(self):
        methodology = self.methodology()

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionMethodologyError, "PASS/PASS"):
            methodology.connected_robust_regions((self.point(mae20="WARNING", mae60="PASS"),))

    def test_warning_warning_rejected_from_robust_region(self):
        methodology = self.methodology()

        with self.assertRaisesRegex(TechnicalRiskValidationSelectionMethodologyError, "PASS/PASS"):
            methodology.connected_robust_regions((self.point(mae20="WARNING", mae60="WARNING"),))

    def test_adjacent_one_axis_grid_point_is_neighbor(self):
        methodology = self.methodology()

        self.assertTrue(methodology.are_neighboring_grid_points(self.point(), self.point(threshold="threshold_2", coordinates=(1, 0, 0, 0))))

    def test_two_axis_change_is_not_neighbor(self):
        methodology = self.methodology()

        self.assertFalse(methodology.are_neighboring_grid_points(self.point(), self.point(threshold="threshold_2", coordinates=(1, 1, 0, 0))))

    def test_non_adjacent_same_axis_step_is_not_neighbor(self):
        methodology = self.methodology()

        self.assertFalse(methodology.are_neighboring_grid_points(self.point(), self.point(threshold="threshold_2", coordinates=(2, 0, 0, 0))))

    def test_different_candidate_never_connected(self):
        methodology = self.methodology()

        self.assertFalse(
            methodology.are_neighboring_grid_points(
                self.point(candidate="TECH_POLICY_CANDIDATE_A"),
                self.point(candidate="TECH_POLICY_CANDIDATE_B", threshold="threshold_2", coordinates=(1, 0, 0, 0)),
            )
        )

    def test_connected_component_deterministic(self):
        methodology = self.methodology()
        points = (
            self.point(threshold="threshold_3", coordinates=(2, 0, 0, 0)),
            self.point(threshold="threshold_1", coordinates=(0, 0, 0, 0)),
            self.point(threshold="threshold_2", coordinates=(1, 0, 0, 0)),
            self.point(candidate="TECH_POLICY_CANDIDATE_B", threshold="threshold_b", coordinates=(0, 0, 0, 0)),
        )

        first = methodology.connected_robust_regions(points)
        second = methodology.connected_robust_regions(tuple(reversed(points)))

        self.assertEqual(first, second)
        self.assertEqual(tuple(region.robust_region_size for region in first), (3, 1))

    def test_no_numeric_floors(self):
        methodology = self.methodology()

        self.assertEqual(methodology.numeric_floor_policy, TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1)
        self.assertFalse(any("floor" in field for field in methodology.__dataclass_fields__ if field != "numeric_floor_policy"))
        self.assertFalse(any("minimum" in field or "cutoff" in field for field in methodology.__dataclass_fields__))

    def test_no_weighted_score(self):
        methodology = self.methodology()

        self.assertFalse(methodology.weighted_score_allowed)
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionMethodologyError, "Weighted score"):
            replace(methodology, methodology_id=None, methodology_checksum=None, weighted_score_allowed=True)

    def test_tie_policy_retained(self):
        methodology = self.methodology()

        self.assertEqual(methodology.tie_policy, TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION)

    def test_no_candidate_c_preference(self):
        methodology = self.methodology()

        self.assertFalse(methodology.candidate_preference_allowed)
        self.assertNotIn("TECH_POLICY_CANDIDATE_C", str(methodology))
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionMethodologyError, "Candidate-specific"):
            replace(methodology, methodology_id=None, methodology_checksum=None, candidate_preference_allowed=True)

    def test_validation_artifact_identity_retained(self):
        methodology = self.methodology()

        self.assertEqual(methodology.validation_evidence_artifact_id, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID)
        self.assertEqual(methodology.validation_evidence_artifact_checksum, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM)

    def test_no_holdout_dependency(self):
        source = inspect.getsource(methodology_module)

        self.assertNotIn("HOLDOUT", source)
        self.assertNotIn("2024-01-01", source)
        self.assertNotIn("2025-12-31", source)

    def test_no_production_path(self):
        source = inspect.getsource(methodology_module)

        self.assertNotIn("data/production", source)
        self.assertNotIn("production_runtime", source)

    def test_deterministic_identity_and_checksum(self):
        first = self.methodology()
        second = self.methodology()

        self.assertEqual(first.methodology_id, second.methodology_id)
        self.assertEqual(first.methodology_checksum, second.methodology_checksum)

    def test_validation_artifact_checksum_change_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskValidationSelectionMethodologyError, "validation_evidence_artifact_checksum"):
            self.methodology(validation_evidence_artifact_checksum="changed_checksum")

    def test_public_api_exports_methodology_contract(self):
        self.assertIn("TechnicalRiskValidationSelectionMethodology", risk_oos.__all__)
        self.assertIn("build_technical_risk_v1_validation_selection_methodology", risk_oos.__all__)


if __name__ == "__main__":
    unittest.main()
