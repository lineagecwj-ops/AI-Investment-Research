import inspect
import sys
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos
import risk_oos.holdout_region_evidence_review as review_module
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import TECH_RISK_DESCRIPTIVE_HOLDOUT_REGION_EVIDENCE_REVIEW
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEWER_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEW_PACKAGE_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1
from risk_oos import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos import TechnicalRiskCandidateEvaluator
from risk_oos import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos import TechnicalRiskHoldoutRegionEvaluationError
from risk_oos import TechnicalRiskHoldoutRegionEvaluator
from risk_oos import TechnicalRiskOOSDatasetResult
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskRealOOSDatasetMaterializationResult
from risk_oos import build_technical_risk_holdout_region_evidence_review_package
from risk_oos import build_technical_risk_v1_holdout_region_confirmation_contract
from risk_oos import build_technical_risk_v1_holdout_region_evaluation_request
from risk_oos import load_official_validation_evidence_artifact


class FakeHoldoutDatasetMaterializer:
    def __init__(self, dataset):
        self.dataset = dataset
        self.calls = []

    def materialize(self, request):
        self.calls.append(request)
        return TechnicalRiskRealOOSDatasetMaterializationResult(
            oos_dataset_result=self.dataset,
            feature_observation_count=len(self.dataset.included_rows),
            feature_exclusion_count=0,
            mae20_artifact_count=len(self.dataset.included_rows),
            mae60_artifact_count=len(self.dataset.included_rows),
            aligned_row_count=len(self.dataset.included_rows),
            split_counts={
                "development": 0,
                "validation": 0,
                "holdout": len(self.dataset.included_rows),
            },
            excluded_insufficient_feature_history_count=0,
            excluded_incomplete_mae20_count=0,
            excluded_incomplete_mae60_count=0,
            excluded_split_leakage_count=0,
        )


class CountingCandidateEvaluator:
    def __init__(self):
        self.calls = []
        self.delegate = TechnicalRiskCandidateEvaluator()

    def evaluate(self, dataset, candidate, threshold_set, evaluation_input):
        raise AssertionError("compact evaluation should be used")

    def evaluate_compact(self, dataset, candidate, threshold_set, evaluation_input):
        self.calls.append((candidate.policy_candidate_id, threshold_set.threshold_set_id))
        return self.delegate.evaluate_compact(dataset, candidate, threshold_set, evaluation_input)


class TechnicalRiskHoldoutRegionEvidenceReviewTestCase(unittest.TestCase):
    def setUp(self):
        self.contract = build_technical_risk_v1_holdout_region_confirmation_contract()
        self.validation_artifact = load_official_validation_evidence_artifact()

    def row(
        self,
        row_id,
        *,
        as_of_close,
        sma20,
        sma60,
        rsi14,
        mae20_value,
        mae60_value,
    ):
        return AlignedTechnicalRiskOOSRow(
            row_id=row_id,
            observation_id=f"obs_{row_id}",
            symbol="2330.TW",
            evaluation_date=date(2024, 6, 3),
            as_of_close=as_of_close,
            sma20=sma20,
            sma60=sma60,
            rsi14=rsi14,
            feature_observation_checksum=f"feature_checksum_{row_id}",
            mae20_value=mae20_value,
            mae20_target_checksum=f"mae20_checksum_{row_id}",
            mae20_calculation_id=f"mae20_calc_{row_id}",
            mae20_target_start_date=date(2024, 6, 4),
            mae20_target_end_date=date(2024, 7, 1),
            mae60_value=mae60_value,
            mae60_target_checksum=f"mae60_checksum_{row_id}",
            mae60_calculation_id=f"mae60_calc_{row_id}",
            mae60_target_start_date=date(2024, 6, 4),
            mae60_target_end_date=date(2024, 8, 30),
            split_id="holdout_split",
            split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
            dataset_spec_id="technical_risk_holdout_region_dataset_fixture",
            dataset_spec_version="v1",
        )

    def dataset(self):
        return TechnicalRiskOOSDatasetResult(
            included_rows=(
                self.row(
                    "row_high",
                    as_of_close=80.0,
                    sma20=100.0,
                    sma60=110.0,
                    rsi14=25.0,
                    mae20_value=-0.22,
                    mae60_value=-0.32,
                ),
                self.row(
                    "row_medium",
                    as_of_close=96.0,
                    sma20=100.0,
                    sma60=105.0,
                    rsi14=45.0,
                    mae20_value=-0.11,
                    mae60_value=-0.20,
                ),
                self.row(
                    "row_low",
                    as_of_close=110.0,
                    sma20=100.0,
                    sma60=95.0,
                    rsi14=55.0,
                    mae20_value=-0.02,
                    mae60_value=-0.04,
                ),
            ),
            excluded_records=(),
            dataset_id="technical_risk_holdout_region_dataset_fixture",
            dataset_checksum="dataset_checksum_holdout_fixture",
            summary_counts={"included_rows": 3, "holdout_included": 3},
        )

    def holdout_result(self):
        request = build_technical_risk_v1_holdout_region_evaluation_request(
            research_db_path="/tmp/research.db",
            research_manifest_path="/tmp/research_manifest.json",
            source_snapshot_id="research_snapshot_v1",
            source_snapshot_checksum="research_snapshot_checksum_v1",
            symbols=("2330.TW",),
            contract=self.contract,
        )
        materializer = FakeHoldoutDatasetMaterializer(self.dataset())
        candidate_evaluator = CountingCandidateEvaluator()
        result = TechnicalRiskHoldoutRegionEvaluator(
            dataset_materializer=materializer,
            candidate_evaluator=candidate_evaluator,
        ).evaluate(request, contract=self.contract)
        return result, materializer, candidate_evaluator

    def package(self):
        result, materializer, candidate_evaluator = self.holdout_result()
        package = build_technical_risk_holdout_region_evidence_review_package(
            result,
            validation_artifact=self.validation_artifact,
        )
        return package, result, materializer, candidate_evaluator

    def test_review_package_is_descriptive_review_required_only(self):
        package, _, _, _ = self.package()

        self.assertEqual(package.review_package_version, TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEW_PACKAGE_V1)
        self.assertEqual(package.review_type, TECH_RISK_DESCRIPTIVE_HOLDOUT_REGION_EVIDENCE_REVIEW)
        self.assertEqual(package.reviewer_version, TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEWER_V1)
        self.assertEqual(package.decision_state, TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED)
        self.assertFalse(package.production_policy_created)
        self.assertFalse(package.artifact_created)

    def test_preserves_frozen_lineage_and_holdout_context(self):
        package, result, _, _ = self.package()

        self.assertEqual(package.validation_evidence_artifact_id, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID)
        self.assertEqual(package.holdout_evaluation_result_id, result.result_id)
        self.assertEqual(package.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID)
        self.assertEqual(package.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID)
        self.assertEqual(package.threshold_count, 69)
        self.assertEqual(package.holdout_start_date, date(2024, 1, 1))
        self.assertEqual(package.holdout_end_date, date(2025, 12, 31))

    def test_compares_validation_and_holdout_without_reexecuting_holdout(self):
        package, _, materializer, candidate_evaluator = self.package()

        self.assertEqual(len(materializer.calls), 1)
        self.assertEqual(len(candidate_evaluator.calls), 69)
        self.assertEqual(package.validation_summary.split_role, TechnicalRiskOOSSplitRole.VALIDATION)
        self.assertEqual(package.holdout_summary.split_role, TechnicalRiskOOSSplitRole.HOLDOUT)
        self.assertEqual(package.validation_summary.evaluation_count, 69)
        self.assertEqual(package.holdout_summary.evaluation_count, 69)
        self.assertEqual(package.validation_summary.row_count, 90322)
        self.assertEqual(package.holdout_summary.row_count, 3)

    def test_summarizes_monotonicity_separation_coverage_and_shift(self):
        package, _, _, _ = self.package()

        self.assertEqual(package.validation_summary.mae20_monotonicity_counts, {"PASS": 69})
        self.assertEqual(package.validation_summary.mae60_monotonicity_counts, {"PASS": 69})
        self.assertIn("PASS", package.holdout_summary.mae20_monotonicity_counts)
        self.assertEqual(package.holdout_summary.mae20_high_minus_low_distribution.count, 69)
        self.assertEqual(package.holdout_summary.mae60_high_minus_low_distribution.count, 69)
        self.assertEqual(
            set(package.holdout_summary.coverage_distribution_by_severity),
            {"LOW", "MEDIUM", "HIGH"},
        )
        self.assertIsInstance(package.shift_summary.mae20_pass_count_shift, int)
        self.assertIsInstance(package.shift_summary.coverage_shift_by_severity["HIGH"], str)

    def test_threshold_stability_preserves_axis_warning_patterns_without_preference(self):
        package, _, _, _ = self.package()
        stability = package.threshold_stability_summary

        self.assertEqual(stability.total_threshold_count, 69)
        self.assertLessEqual(stability.mae20_warning_threshold_count, 69)
        self.assertLessEqual(stability.mae60_warning_threshold_count, 69)
        self.assertIn("MAE20", stability.warning_axis_counts)
        self.assertIn("MAE60", stability.warning_axis_counts)
        self.assertIn("close_vs_sma20_weakness_cutoff", stability.warning_axis_counts["MAE20"])

    def test_deterministic_review_identity(self):
        first, _, _, _ = self.package()
        second, _, _, _ = self.package()

        self.assertEqual(first.review_package_id, second.review_package_id)
        self.assertEqual(first.review_package_checksum, second.review_package_checksum)

    def test_rejects_candidate_or_threshold_mutation(self):
        result, _, _ = self.holdout_result()
        with self.assertRaisesRegex(TechnicalRiskHoldoutRegionEvaluationError, "candidate_id"):
            replace(result, candidate_id="TECH_POLICY_CANDIDATE_A")
        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            replace(result, threshold_identities=(("wrong_threshold", "checksum"),))

    def test_source_has_no_production_or_final_decision_dependency(self):
        source = inspect.getsource(review_module)

        forbidden_terms = (
            "production_runtime",
            "data/production",
            "ProductionTechnicalRiskPolicy",
            "sqlite3",
            "yfinance",
            "requests",
            "urllib",
        )
        for term in forbidden_terms:
            self.assertNotIn(term, source)

    def test_public_api_exports_review_package(self):
        self.assertIs(risk_oos.TechnicalRiskHoldoutRegionEvidenceReviewPackage, review_module.TechnicalRiskHoldoutRegionEvidenceReviewPackage)
        self.assertIs(
            risk_oos.build_technical_risk_holdout_region_evidence_review_package,
            review_module.build_technical_risk_holdout_region_evidence_review_package,
        )


if __name__ == "__main__":
    unittest.main()
