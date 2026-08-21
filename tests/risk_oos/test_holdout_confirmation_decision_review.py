import inspect
import sys
import unittest
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos
import risk_oos.holdout_confirmation_decision_review as review_module
from risk_oos import TECH_RISK_DESCRIPTIVE_HOLDOUT_CONFIRMATION_DECISION_REVIEW
from risk_oos import TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEWER_V1
from risk_oos import TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_PACKAGE_V1
from risk_oos import TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_REQUIRES_DECISION
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos import TechnicalRiskHoldoutConfirmationDecisionReviewError
from risk_oos import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos import build_technical_risk_holdout_confirmation_decision_review_package
from risk_oos import build_technical_risk_holdout_region_evidence_review_package_from_artifact
from risk_oos import load_holdout_region_evidence_artifact
from risk_oos import load_technical_risk_holdout_confirmation_decision_review_package


ARTIFACT_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "technical_risk_holdout_region_evidence"
    / "technical_risk_holdout_region_evidence_3e42ef8d303c50ab.json"
)


class TechnicalRiskHoldoutConfirmationDecisionReviewTestCase(unittest.TestCase):
    def artifact(self):
        return load_holdout_region_evidence_artifact(ARTIFACT_PATH)

    def package(self):
        return build_technical_risk_holdout_confirmation_decision_review_package(self.artifact())

    def test_loads_holdout_artifact_and_builds_descriptive_review(self):
        package = self.package()

        self.assertEqual(package.decision_review_version, TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_PACKAGE_V1)
        self.assertEqual(package.review_type, TECH_RISK_DESCRIPTIVE_HOLDOUT_CONFIRMATION_DECISION_REVIEW)
        self.assertEqual(package.reviewer_version, TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEWER_V1)
        self.assertEqual(package.holdout_evidence_artifact_id, "technical_risk_holdout_region_evidence_3e42ef8d303c50ab")
        self.assertEqual(package.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID)
        self.assertEqual(package.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID)
        self.assertEqual(package.threshold_count, 69)

    def test_monotonicity_shift_remains_review_required(self):
        package = self.package()

        self.assertEqual(package.validation_monotonicity_counts["MAE20"], {"PASS": 69})
        self.assertEqual(package.validation_monotonicity_counts["MAE60"], {"PASS": 69})
        self.assertEqual(package.holdout_monotonicity_counts["MAE20"], {"PASS": 13, "WARNING": 56})
        self.assertEqual(package.holdout_monotonicity_counts["MAE60"], {"PASS": 27, "WARNING": 42})
        self.assertEqual(package.monotonicity_shift["MAE20_PASS_SHIFT"], -56)
        self.assertEqual(package.monotonicity_shift["MAE60_PASS_SHIFT"], -42)
        self.assertEqual(package.decision_state, TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED)
        self.assertEqual(package.decision_boundary, TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_REQUIRES_DECISION)
        self.assertFalse(package.confirmation_decision_made)

    def test_separation_and_coverage_comparisons_are_descriptive(self):
        package = self.package()

        mae20 = package.separation_comparison["MAE20_HIGH_MINUS_LOW"]
        mae60 = package.separation_comparison["MAE60_HIGH_MINUS_LOW"]
        self.assertEqual(mae20.validation.count, 69)
        self.assertEqual(mae20.holdout.count, 69)
        self.assertEqual(mae20.holdout.median, "-0.00118678361237512")
        self.assertEqual(mae60.holdout.median, "-0.00659940688845695")
        self.assertEqual(package.coverage_comparison_by_severity["LOW"].holdout.count, 69)
        self.assertEqual(package.coverage_comparison_by_severity["MEDIUM"].holdout.count, 69)
        self.assertEqual(package.coverage_comparison_by_severity["HIGH"].holdout.count, 69)
        self.assertEqual(package.sample_count_comparison_by_severity["HIGH"].holdout.minimum, "1883")

    def test_threshold_stability_classifies_without_ranking(self):
        package = self.package()
        stability = package.threshold_stability_review

        self.assertEqual(stability.stable_pattern_count + stability.degraded_pattern_count + stability.unclear_pattern_count, 69)
        self.assertEqual(stability.mae20_warning_count, 56)
        self.assertEqual(stability.mae60_warning_count, 42)
        self.assertGreater(stability.degraded_pattern_count, 0)
        self.assertIn("MAE20", stability.warning_axis_counts)
        self.assertIn("close_vs_sma20_weakness_cutoff", stability.warning_axis_counts["MAE20"])

    def test_deterministic_review_identity(self):
        first = self.package()
        second = self.package()

        self.assertEqual(first.decision_review_id, second.decision_review_id)
        self.assertEqual(first.decision_review_checksum, second.decision_review_checksum)

    def test_rejects_mismatched_evidence_review(self):
        artifact = self.artifact()
        review = build_technical_risk_holdout_region_evidence_review_package_from_artifact(artifact)
        bad_review = replace(
            review,
            review_package_id=None,
            review_package_checksum=None,
            holdout_evaluation_result_checksum="wrong_checksum",
        )

        with self.assertRaises(TechnicalRiskHoldoutConfirmationDecisionReviewError):
            build_technical_risk_holdout_confirmation_decision_review_package(
                artifact,
                evidence_review=bad_review,
            )

    def test_loader_builds_review_from_artifact_path(self):
        package = load_technical_risk_holdout_confirmation_decision_review_package(ARTIFACT_PATH)

        self.assertEqual(package.holdout_evaluation_result_id, "technical_risk_holdout_region_evaluation_d218108530685a44")
        self.assertFalse(package.production_policy_created)
        self.assertFalse(package.freeze_artifact_created)

    def test_source_has_no_production_or_final_decision_dependency(self):
        source = inspect.getsource(review_module)
        forbidden_terms = (
            "production_runtime",
            "data/production",
            "ProductionTechnicalRiskPolicy",
            "yfinance",
            "requests",
            "urllib",
            "sqlite3",
        )
        for term in forbidden_terms:
            self.assertNotIn(term, source)

    def test_public_api_exports_decision_review(self):
        self.assertIs(
            risk_oos.build_technical_risk_holdout_confirmation_decision_review_package,
            review_module.build_technical_risk_holdout_confirmation_decision_review_package,
        )
        self.assertIs(
            risk_oos.load_technical_risk_holdout_confirmation_decision_review_package,
            review_module.load_technical_risk_holdout_confirmation_decision_review_package,
        )


if __name__ == "__main__":
    unittest.main()
