import inspect
import sys
import unittest
from dataclasses import fields
from dataclasses import replace
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos
import risk_oos.holdout_region_evaluation as evaluation_module
from risk_oos import TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1
from risk_oos import TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT
from risk_oos import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE
from risk_oos import TECH_RISK_HOLDOUT_REGION_EVALUATION_REQUEST_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1
from risk_oos import TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import TechnicalRiskCandidateEvaluator
from risk_oos import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos import TechnicalRiskHoldoutRegionEvaluationError
from risk_oos import TechnicalRiskHoldoutRegionEvaluationResult
from risk_oos import TechnicalRiskHoldoutRegionEvaluator
from risk_oos import TechnicalRiskOOSDatasetResult
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskRealOOSDatasetMaterializationResult
from risk_oos import build_technical_risk_v1_holdout_region_confirmation_contract
from risk_oos import build_technical_risk_v1_holdout_region_evaluation_request
from risk_oos import materialize_technical_risk_v1_threshold_grid


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
        self.calls.append((candidate.policy_candidate_id, threshold_set.threshold_set_id, evaluation_input.allowed_split_roles))
        return self.delegate.evaluate_compact(dataset, candidate, threshold_set, evaluation_input)


class TechnicalRiskHoldoutRegionEvaluationTestCase(unittest.TestCase):
    def setUp(self):
        self.contract = build_technical_risk_v1_holdout_region_confirmation_contract()

    def row(
        self,
        row_id,
        *,
        as_of_close,
        sma20,
        sma60,
        rsi14,
        split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
        evaluation_date=None,
        mae20_value=-0.05,
        mae60_value=-0.08,
    ):
        evaluation_date = evaluation_date or date(2024, 6, 3)
        return AlignedTechnicalRiskOOSRow(
            row_id=row_id,
            observation_id=f"obs_{row_id}",
            symbol="2330.TW",
            evaluation_date=evaluation_date,
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
            split_id=f"{split_role.value.lower()}_split",
            split_role=split_role,
            dataset_spec_id="technical_risk_holdout_region_dataset_fixture",
            dataset_spec_version="v1",
        )

    def dataset(self, rows=None):
        rows = rows or (
            self.row("row_high", as_of_close=80.0, sma20=100.0, sma60=110.0, rsi14=25.0, mae20_value=-0.20, mae60_value=-0.30),
            self.row("row_medium", as_of_close=96.0, sma20=100.0, sma60=105.0, rsi14=45.0, mae20_value=-0.10, mae60_value=-0.20),
            self.row("row_low", as_of_close=110.0, sma20=100.0, sma60=95.0, rsi14=55.0, mae20_value=-0.02, mae60_value=-0.04),
        )
        return TechnicalRiskOOSDatasetResult(
            included_rows=tuple(rows),
            excluded_records=(),
            dataset_id="technical_risk_holdout_region_dataset_fixture",
            dataset_checksum="dataset_checksum_holdout_fixture",
            summary_counts={"included_rows": len(rows), "holdout_included": len(rows)},
        )

    def request(self, **overrides):
        values = {
            "research_db_path": "/tmp/research.db",
            "research_manifest_path": "/tmp/research_manifest.json",
            "source_snapshot_id": "research_snapshot_v1",
            "source_snapshot_checksum": "research_snapshot_checksum_v1",
            "symbols": ("2330.TW", "2317.TW"),
            "contract": self.contract,
        }
        values.update(overrides)
        return build_technical_risk_v1_holdout_region_evaluation_request(**values)

    def evaluate(self, dataset=None):
        materializer = FakeHoldoutDatasetMaterializer(dataset or self.dataset())
        evaluator = CountingCandidateEvaluator()
        result = TechnicalRiskHoldoutRegionEvaluator(
            dataset_materializer=materializer,
            candidate_evaluator=evaluator,
        ).evaluate(self.request(), contract=self.contract)
        return result, materializer, evaluator

    def test_request_preserves_contract_and_frozen_holdout_scope(self):
        request = self.request()

        self.assertEqual(request.request_version, TECH_RISK_HOLDOUT_REGION_EVALUATION_REQUEST_V1)
        self.assertEqual(request.contract_id, self.contract.contract_id)
        self.assertEqual(request.contract_version, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1)
        self.assertEqual(request.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID)
        self.assertEqual(request.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID)
        self.assertEqual(request.threshold_set_ids, TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1)
        self.assertEqual(len(request.threshold_set_ids), 69)
        self.assertEqual(request.methodology_version, TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1)
        self.assertEqual(request.axis_set_version, TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1)
        self.assertEqual(request.holdout_start_date, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE)
        self.assertEqual(request.holdout_end_date, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE)

    def test_evaluates_candidate_c_across_exact_frozen_region_thresholds_once(self):
        result, materializer, evaluator = self.evaluate()

        self.assertEqual(result.result_version, TECH_RISK_HOLDOUT_REGION_EVALUATION_RESULT_V1)
        self.assertEqual(result.evaluator_version, TECH_RISK_HOLDOUT_REGION_EVALUATOR_V1)
        self.assertEqual(result.split_role, TechnicalRiskOOSSplitRole.HOLDOUT)
        self.assertEqual(result.holdout_start_date, date(2024, 1, 1))
        self.assertEqual(result.holdout_end_date, date(2025, 12, 31))
        self.assertEqual(result.candidate_id, "TECH_POLICY_CANDIDATE_C")
        self.assertEqual(result.region_id, "technical_risk_validation_robust_region_3df35aa1395ead5d")
        self.assertEqual(result.threshold_count, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT)
        self.assertEqual(result.evaluation_count, 69)
        self.assertEqual(result.dataset_materialization_count, 1)
        self.assertEqual(len(materializer.calls), 1)
        self.assertEqual(len(evaluator.calls), 69)
        self.assertEqual(
            materializer.calls[0].required_output_split_roles,
            (TechnicalRiskOOSSplitRole.HOLDOUT,),
        )

    def test_threshold_identities_are_exact_frozen_region_subset(self):
        result, _, _ = self.evaluate()
        grid = materialize_technical_risk_v1_threshold_grid()
        checksums_by_id = {threshold.threshold_set_id: threshold.threshold_set_checksum for threshold in grid.threshold_sets}

        self.assertEqual(tuple(identity[0] for identity in result.threshold_identities), TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1)
        self.assertEqual(
            tuple(identity[1] for identity in result.threshold_identities),
            tuple(checksums_by_id[threshold_id] for threshold_id in TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1),
        )

    def test_threshold_evidence_preserves_complete_metric_structure(self):
        result, _, _ = self.evaluate()
        record = result.threshold_records[0]
        threshold_result = record.threshold_result

        self.assertEqual(threshold_result.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID)
        self.assertEqual(threshold_result.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID)
        self.assertEqual({item.severity.value for item in threshold_result.severity_evidence}, {"LOW", "MEDIUM", "HIGH"})
        for evidence in threshold_result.severity_evidence:
            self.assertIsNotNone(evidence.coverage_ratio)
            self.assertIsInstance(evidence.sample_count, int)
            self.assertTrue(hasattr(evidence, "mae20_mean"))
            self.assertTrue(hasattr(evidence, "mae20_median"))
            self.assertTrue(hasattr(evidence, "mae20_p25"))
            self.assertTrue(hasattr(evidence, "mae20_p75"))
            self.assertTrue(hasattr(evidence, "mae60_mean"))
            self.assertTrue(hasattr(evidence, "mae60_median"))
            self.assertTrue(hasattr(evidence, "mae60_p25"))
            self.assertTrue(hasattr(evidence, "mae60_p75"))
        self.assertTrue(threshold_result.mae20_monotonicity_status)
        self.assertTrue(threshold_result.mae60_monotonicity_status)
        self.assertEqual(threshold_result.mae20_separation_evidence.horizon.value, "MAE20")
        self.assertEqual(threshold_result.mae60_separation_evidence.horizon.value, "MAE60")

    def test_region_summary_is_descriptive_and_requires_review_without_numeric_rule(self):
        result, _, _ = self.evaluate()
        summary = result.region_summary

        self.assertEqual(summary.total_threshold_count, 69)
        self.assertEqual(summary.confirmed_threshold_count, 0)
        self.assertEqual(summary.not_confirmed_threshold_count, 0)
        self.assertEqual(summary.review_required_threshold_count, 69)
        self.assertTrue(summary.monotonicity_stability_summary)
        self.assertTrue(summary.separation_stability_summary)
        self.assertTrue(summary.coverage_stability_summary)
        self.assertEqual(
            {record.threshold_result.confirmation_status for record in result.threshold_records},
            {TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED},
        )

    def test_result_identity_and_ordering_are_deterministic(self):
        first, _, _ = self.evaluate()
        second, _, _ = self.evaluate()

        self.assertEqual(first.result_id, second.result_id)
        self.assertEqual(first.result_checksum, second.result_checksum)
        self.assertEqual(
            tuple(record.evaluation_id for record in first.threshold_records),
            tuple(record.evaluation_id for record in second.threshold_records),
        )

    def test_rejects_validation_development_or_out_of_window_rows(self):
        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            self.evaluate(self.dataset((self.row("validation", as_of_close=90.0, sma20=100.0, sma60=110.0, rsi14=30.0, split_role=TechnicalRiskOOSSplitRole.VALIDATION),)))
        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            self.evaluate(self.dataset((self.row("development", as_of_close=90.0, sma20=100.0, sma60=110.0, rsi14=30.0, split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT),)))
        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            self.evaluate(self.dataset((self.row("bad_date", as_of_close=90.0, sma20=100.0, sma60=110.0, rsi14=30.0, evaluation_date=date(2023, 12, 29)),)))

    def test_rejects_threshold_candidate_region_or_date_mutation(self):
        request = self.request()

        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            replace(request, candidate_id="TECH_POLICY_CANDIDATE_A")
        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            replace(request, region_id="other_region")
        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            replace(request, threshold_set_ids=TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1[:-1])
        with self.assertRaises(TechnicalRiskHoldoutRegionEvaluationError):
            replace(request, holdout_start_date=date(2023, 1, 1))

    def test_no_final_policy_or_artifact_fields_exist(self):
        field_names = {field.name for field in fields(TechnicalRiskHoldoutRegionEvaluationResult)}
        forbidden = {
            "production_policy",
            "policy_artifact",
            "freeze_artifact",
            "selected_candidate",
            "selected_threshold",
            "score",
            "weighted_score",
        }
        self.assertTrue(field_names.isdisjoint(forbidden))

    def test_source_has_no_production_or_selection_dependency(self):
        source = inspect.getsource(evaluation_module)
        forbidden_tokens = (
            "production_runtime",
            "sqlite3",
            "yfinance",
            "requests",
            "data/production",
            "selected_candidate",
            "selected_threshold",
            "weighted_score",
            "winner",
            "best_threshold",
            "ranking",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_public_api_exports_evaluator_without_artifact(self):
        self.assertIn("TechnicalRiskHoldoutRegionEvaluator", risk_oos.__all__)
        self.assertIn("build_technical_risk_v1_holdout_region_evaluation_request", risk_oos.__all__)
        self.assertNotIn("TechnicalRiskHoldoutRegionConfirmationArtifact", risk_oos.__all__)


if __name__ == "__main__":
    unittest.main()
