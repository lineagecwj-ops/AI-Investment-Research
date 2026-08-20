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
import risk_oos.validation_evidence_shortlist as shortlist_module
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1
from risk_oos import TECH_RISK_DESCRIPTIVE_SHORTLIST_ONLY_V1
from risk_oos import TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1
from risk_oos import TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1
from risk_oos import TECH_RISK_THRESHOLD_GRID_SPEC_V1
from risk_oos import TechnicalRiskCandidateFamily
from risk_oos import TechnicalRiskThresholdGridMaterializer
from risk_oos import TechnicalRiskThresholdGridSpec
from risk_oos import TechnicalRiskValidationEvidenceShortlist
from risk_oos import TechnicalRiskValidationEvidenceShortlistError
from risk_oos import build_technical_risk_v1_validation_selection_methodology
from risk_oos import build_technical_risk_validation_evidence_shortlist
from risk_oos import load_validation_evidence_artifact


OFFICIAL_EVIDENCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "technical_risk_validation_evidence"
    / "technical_risk_validation_evidence_95cb2cc4a385b5ec.json"
)


class TechnicalRiskValidationEvidenceShortlistTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = load_validation_evidence_artifact(OFFICIAL_EVIDENCE_PATH)
        cls.methodology = build_technical_risk_v1_validation_selection_methodology()
        cls.shortlist = build_technical_risk_validation_evidence_shortlist(cls.artifact, methodology=cls.methodology)

    def test_official_artifact_and_methodology_are_loaded(self):
        self.assertEqual(self.artifact.artifact_id, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID)
        self.assertEqual(self.artifact.artifact_checksum, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM)
        self.assertEqual(self.methodology.methodology_version, TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1)
        self.assertEqual(self.shortlist.shortlist_type, TECH_RISK_DESCRIPTIVE_SHORTLIST_ONLY_V1)

    def test_pass_pass_filtering_uses_dual_horizon_only(self):
        self.assertEqual(self.shortlist.pass_pass_evaluation_count, 168)
        counts = {}
        for region in self.shortlist.robust_regions:
            counts[region.candidate_id] = counts.get(region.candidate_id, 0) + region.robust_region_size
        self.assertEqual(
            counts,
            {
                "TECH_POLICY_CANDIDATE_A": 45,
                "TECH_POLICY_CANDIDATE_B": 48,
                "TECH_POLICY_CANDIDATE_C": 69,
                "TECH_POLICY_CANDIDATE_D": 6,
            },
        )

    def test_non_pass_pass_evaluations_are_excluded(self):
        included_ids = {
            point.evaluation_id
            for region in self.shortlist.robust_regions
            for point in region.evidence_points
        }
        all_records = self.artifact.validation_result.evaluation_records
        self.assertEqual(len(all_records), 324)
        self.assertEqual(len(included_ids), 168)
        self.assertTrue(any(record.evaluation_id not in included_ids for record in all_records))

    def test_robust_region_generation_uses_approved_topology(self):
        self.assertEqual(self.shortlist.robust_region_count, 5)
        self.assertEqual(
            dict(self.shortlist.robust_region_counts_by_candidate),
            {
                "TECH_POLICY_CANDIDATE_A": 1,
                "TECH_POLICY_CANDIDATE_B": 1,
                "TECH_POLICY_CANDIDATE_C": 1,
                "TECH_POLICY_CANDIDATE_D": 2,
            },
        )
        for region in self.shortlist.robust_regions:
            for point in region.evidence_points:
                self.assertEqual(point.candidate_id, region.candidate_id)

    def test_structured_shortlist_is_descriptive_and_contains_every_region_here(self):
        self.assertEqual(self.shortlist.shortlist_type, TECH_RISK_DESCRIPTIVE_SHORTLIST_ONLY_V1)
        self.assertEqual(self.shortlist.descriptive_shortlist_regions, self.shortlist.robust_regions)
        self.assertLessEqual(len(self.shortlist.descriptive_shortlist_regions), 15)

    def test_region_evidence_preserves_threshold_values_coordinates_and_evaluation_lineage(self):
        first_region = self.shortlist.robust_regions[0]
        first_point = first_region.evidence_points[0]

        self.assertEqual(first_point.validation_evidence_artifact_id, self.artifact.artifact_id)
        self.assertEqual(first_point.validation_evidence_artifact_checksum, self.artifact.artifact_checksum)
        self.assertTrue(first_point.threshold_set_id.startswith("technical_risk_threshold_set_"))
        self.assertEqual(set(first_point.threshold_values), {
            "close_vs_sma20_weakness_cutoff",
            "close_vs_sma60_weakness_cutoff",
            "relative_sma_spread_weakness_cutoff",
            "rsi14_weakness_confirmation_cutoff",
        })
        self.assertEqual(len(first_point.grid_coordinates), 4)
        self.assertTrue(first_point.evaluation_id.startswith("technical_risk_candidate_evaluation_"))
        self.assertIn("LOW", first_point.coverage_by_severity)
        self.assertIn("MEDIUM", first_point.sample_count_by_severity)
        self.assertIn("HIGH", first_point.mae20_median_by_severity)

    def test_deterministic_identity_and_checksum(self):
        first = build_technical_risk_validation_evidence_shortlist(self.artifact, methodology=self.methodology)
        second = build_technical_risk_validation_evidence_shortlist(self.artifact, methodology=self.methodology)

        self.assertEqual(first.evidence_shortlist_id, second.evidence_shortlist_id)
        self.assertEqual(first.evidence_shortlist_checksum, second.evidence_shortlist_checksum)
        self.assertEqual(first.robust_regions, second.robust_regions)

    def test_threshold_grid_mismatch_fails_closed(self):
        bad_grid = TechnicalRiskThresholdGridMaterializer().materialize(
            TechnicalRiskThresholdGridSpec(
                grid_spec_id=None,
                grid_spec_version=TECH_RISK_THRESHOLD_GRID_SPEC_V1,
                generation_method_id=TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1,
                generation_method_version="different_test_grid_v1",
                source_spec_version="different_test_grid_v1",
                candidate_family=TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC,
                compatible_candidate_families=tuple(TechnicalRiskCandidateFamily),
                close_vs_sma20_values=("-0.010", "-0.020", "-0.030"),
                close_vs_sma60_values=("-0.040", "-0.050", "-0.060"),
                relative_sma_spread_values=("-0.010", "-0.020", "-0.030"),
                rsi14_values=("30", "40", "50"),
            )
        )

        with self.assertRaisesRegex(TechnicalRiskValidationEvidenceShortlistError, "grid result id"):
            build_technical_risk_validation_evidence_shortlist(
                self.artifact,
                methodology=self.methodology,
                threshold_grid_result=bad_grid,
            )

    def test_no_final_selection_fields_exist(self):
        field_names = {field.name for field in fields(TechnicalRiskValidationEvidenceShortlist)}

        self.assertNotIn("selected_candidate_id", field_names)
        self.assertNotIn("selected_threshold_set_id", field_names)
        self.assertNotIn("production_policy", field_names)
        self.assertNotIn("freeze_artifact", field_names)
        self.assertNotIn("holdout_request", field_names)

    def test_no_numeric_floor_policy_is_added(self):
        self.assertEqual(self.shortlist.numeric_floor_policy, TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1)

    def test_no_holdout_production_or_network_dependency(self):
        source = inspect.getsource(shortlist_module)
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
            "open(",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_public_api_exports_shortlist_only(self):
        self.assertIn("TechnicalRiskValidationEvidenceShortlist", risk_oos.__all__)
        self.assertIn("build_technical_risk_validation_evidence_shortlist", risk_oos.__all__)
        self.assertNotIn("TechnicalRiskValidationDecisionExecutor", risk_oos.__all__)


if __name__ == "__main__":
    unittest.main()
