import inspect
import sys
import unittest
from dataclasses import fields
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos
import risk_oos.validation_selection_decision_package as package_module
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1
from risk_oos import TECH_RISK_DESCRIPTIVE_VALIDATION_SELECTION_DECISION_PACKAGE
from risk_oos import TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1
from risk_oos import TECH_RISK_VALIDATION_SELECTION_DECISION_PACKAGE_V1
from risk_oos import TechnicalRiskTiePolicy
from risk_oos import TechnicalRiskValidationSelectionDecisionPackage
from risk_oos import build_technical_risk_v1_validation_selection_methodology
from risk_oos import build_technical_risk_validation_evidence_shortlist
from risk_oos import build_technical_risk_validation_selection_decision_package
from risk_oos import load_validation_evidence_artifact


OFFICIAL_EVIDENCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "technical_risk_validation_evidence"
    / "technical_risk_validation_evidence_95cb2cc4a385b5ec.json"
)


class TechnicalRiskValidationSelectionDecisionPackageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = load_validation_evidence_artifact(OFFICIAL_EVIDENCE_PATH)
        cls.methodology = build_technical_risk_v1_validation_selection_methodology()
        cls.shortlist = build_technical_risk_validation_evidence_shortlist(
            cls.artifact,
            methodology=cls.methodology,
        )
        cls.package = build_technical_risk_validation_selection_decision_package(
            cls.shortlist,
            methodology=cls.methodology,
        )

    def test_package_loads_official_inputs(self):
        self.assertEqual(self.package.validation_evidence_artifact_id, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID)
        self.assertEqual(self.package.validation_evidence_artifact_checksum, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM)
        self.assertEqual(self.package.methodology_version, TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1)
        self.assertEqual(self.package.package_type, TECH_RISK_DESCRIPTIVE_VALIDATION_SELECTION_DECISION_PACKAGE)

    def test_package_preserves_all_descriptive_regions(self):
        self.assertEqual(self.package.decision_package_version, TECH_RISK_VALIDATION_SELECTION_DECISION_PACKAGE_V1)
        self.assertEqual(self.package.region_count, 5)
        self.assertEqual(len(self.package.region_comparisons), self.shortlist.robust_region_count)
        self.assertEqual(
            tuple(region.region_id for region in self.package.region_comparisons),
            tuple(region.robust_region_id for region in self.shortlist.robust_regions),
        )

    def test_region_comparison_preserves_identity_and_evidence_lineage(self):
        for source_region, package_region in zip(self.shortlist.robust_regions, self.package.region_comparisons):
            self.assertEqual(package_region.region_id, source_region.robust_region_id)
            self.assertEqual(package_region.candidate_id, source_region.candidate_id)
            self.assertEqual(package_region.region_size, source_region.robust_region_size)
            self.assertEqual(package_region.pass_pass_count, source_region.robust_region_size)
            self.assertEqual(package_region.threshold_set_count, len(source_region.threshold_set_ids))
            self.assertEqual(package_region.threshold_set_ids, source_region.threshold_set_ids)
            self.assertEqual(package_region.evaluation_ids, source_region.evaluation_ids)
            self.assertEqual(package_region.grid_coordinates, source_region.grid_coordinates)

    def test_region_comparison_contains_required_evidence_profiles(self):
        for region in self.package.region_comparisons:
            self.assertEqual(set(region.coverage_profile_by_severity), {"LOW", "MEDIUM", "HIGH"})
            self.assertEqual(set(region.sample_profile_by_severity), {"LOW", "MEDIUM", "HIGH"})
            self.assertEqual(set(region.mae20_median_profile_by_severity), {"LOW", "MEDIUM", "HIGH"})
            self.assertEqual(set(region.mae60_median_profile_by_severity), {"LOW", "MEDIUM", "HIGH"})
            self.assertEqual(len(region.mae20_separation_profile), 2)
            self.assertEqual(len(region.mae60_separation_profile), 2)
            self.assertEqual(set(region.threshold_values_by_threshold_set), set(region.threshold_set_ids))

    def test_region_comparison_contains_threshold_ranges_and_neighbor_information(self):
        expected_dimensions = {
            "close_vs_sma20_weakness_cutoff",
            "close_vs_sma60_weakness_cutoff",
            "relative_sma_spread_weakness_cutoff",
            "rsi14_weakness_confirmation_cutoff",
        }
        for region in self.package.region_comparisons:
            self.assertEqual(set(region.threshold_range_by_dimension), expected_dimensions)
            self.assertEqual(set(region.neighbor_count_by_threshold_set), set(region.threshold_set_ids))
            self.assertGreaterEqual(region.neighbor_link_count, 0)
            if region.region_size > 1:
                self.assertGreater(region.neighbor_link_count, 0)

    def test_candidate_comparison_preserves_candidate_level_counts(self):
        self.assertEqual(self.package.candidate_count, 4)
        self.assertEqual(
            {candidate.candidate_id: candidate.robust_region_count for candidate in self.package.candidate_comparisons},
            {
                "TECH_POLICY_CANDIDATE_A": 1,
                "TECH_POLICY_CANDIDATE_B": 1,
                "TECH_POLICY_CANDIDATE_C": 1,
                "TECH_POLICY_CANDIDATE_D": 2,
            },
        )
        self.assertEqual(
            {candidate.candidate_id: candidate.pass_pass_count for candidate in self.package.candidate_comparisons},
            {
                "TECH_POLICY_CANDIDATE_A": 45,
                "TECH_POLICY_CANDIDATE_B": 48,
                "TECH_POLICY_CANDIDATE_C": 69,
                "TECH_POLICY_CANDIDATE_D": 6,
            },
        )

    def test_methodology_compliance_is_preserved(self):
        self.assertEqual(self.package.numeric_floor_policy, TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1)
        self.assertEqual(self.package.tie_policy, TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION)
        self.assertEqual(self.package.remaining_decision_status, TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION)
        self.assertFalse(self.methodology.weighted_score_allowed)
        self.assertFalse(self.methodology.candidate_preference_allowed)

    def test_no_final_selection_fields_exist(self):
        field_names = {field.name for field in fields(TechnicalRiskValidationSelectionDecisionPackage)}
        forbidden_fields = {
            "winner",
            "selected_candidate",
            "selected_candidate_id",
            "selected_threshold",
            "selected_threshold_set_id",
            "production_policy",
            "holdout_request",
            "ranking",
            "score",
            "weighted_score",
        }
        self.assertTrue(field_names.isdisjoint(forbidden_fields))

    def test_deterministic_output(self):
        first = build_technical_risk_validation_selection_decision_package(
            self.shortlist,
            methodology=self.methodology,
        )
        second = build_technical_risk_validation_selection_decision_package(
            self.shortlist,
            methodology=self.methodology,
        )
        self.assertEqual(first.decision_package_id, second.decision_package_id)
        self.assertEqual(first.decision_package_checksum, second.decision_package_checksum)
        self.assertEqual(first.region_comparisons, second.region_comparisons)

    def test_no_holdout_production_or_network_dependency(self):
        source = inspect.getsource(package_module)
        forbidden_tokens = (
            "TechnicalRiskHoldout",
            "2024-01-01",
            "2025-12-31",
            "data/production",
            "production_runtime",
            "yfinance",
            "requests",
            "sqlite3",
            "write_text",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_public_api_exports_decision_package_only(self):
        self.assertIn("TechnicalRiskValidationSelectionDecisionPackage", risk_oos.__all__)
        self.assertIn("build_technical_risk_validation_selection_decision_package", risk_oos.__all__)
        self.assertNotIn("TechnicalRiskValidationSelectionExecutor", risk_oos.__all__)


if __name__ == "__main__":
    unittest.main()
