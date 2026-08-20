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

from risk_oos import TECH_RISK_VALIDATION_CANDIDATE_EVALUATION_REQUEST_V1
from risk_oos import TECH_RISK_VALIDATION_CANDIDATE_IDS_V1
from risk_oos import TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1
from risk_oos import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos import AlignedTechnicalRiskOOSRow
from risk_oos import TechnicalRiskCandidateEvaluationInput
from risk_oos import TechnicalRiskCandidateEvaluator
from risk_oos import TechnicalRiskOOSDatasetResult
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskRealOOSDatasetMaterializationResult
from risk_oos import TechnicalRiskValidationCandidateEvaluationError
from risk_oos import TechnicalRiskValidationCandidateEvaluationOrchestrator
from risk_oos import build_technical_risk_v1_validation_candidate_evaluation_request
from risk_oos import materialize_technical_risk_v1_threshold_grid
from risk_oos.validation_candidate_evaluation import _candidate_specs
from risk_oos.validation_candidate_evaluation import _validate_validation_dataset
import risk_oos.validation_candidate_evaluation as validation_candidate_evaluation


class FakeValidationDatasetMaterializer:
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
                "validation": len(self.dataset.included_rows),
                "holdout": 0,
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
        self.calls.append((candidate.policy_candidate_id, threshold_set.threshold_set_id, evaluation_input.allowed_split_roles))
        return self.delegate.evaluate(dataset, candidate, threshold_set, evaluation_input)


class TechnicalRiskValidationCandidateEvaluationTestCase(unittest.TestCase):
    def row(self, row_id, *, as_of_close, sma20, sma60, rsi14, split_role=TechnicalRiskOOSSplitRole.VALIDATION, evaluation_date=None):
        evaluation_date = evaluation_date or date(2022, 6, 1)
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
            mae20_value=-0.05,
            mae20_target_checksum=f"mae20_checksum_{row_id}",
            mae20_calculation_id=f"mae20_calc_{row_id}",
            mae20_target_start_date=date(2022, 6, 2),
            mae20_target_end_date=date(2022, 6, 29),
            mae60_value=-0.08,
            mae60_target_checksum=f"mae60_checksum_{row_id}",
            mae60_calculation_id=f"mae60_calc_{row_id}",
            mae60_target_start_date=date(2022, 6, 2),
            mae60_target_end_date=date(2022, 7, 30),
            split_id=f"{split_role.value.lower()}_split",
            split_role=split_role,
            dataset_spec_id="technical_risk_validation_candidate_dataset_fixture",
            dataset_spec_version="v1",
        )

    def dataset(self, rows=None):
        rows = rows or (
            self.row("row_high", as_of_close=80.0, sma20=100.0, sma60=110.0, rsi14=25.0),
            self.row("row_medium", as_of_close=96.0, sma20=100.0, sma60=105.0, rsi14=45.0),
            self.row("row_low", as_of_close=110.0, sma20=100.0, sma60=95.0, rsi14=55.0),
        )
        return TechnicalRiskOOSDatasetResult(
            included_rows=tuple(rows),
            excluded_records=(),
            dataset_id="technical_risk_validation_candidate_dataset_fixture",
            dataset_checksum="dataset_checksum_validation_fixture",
            summary_counts={"included_rows": len(rows), "validation_included": len(rows)},
        )

    def request(self, **overrides):
        values = {
            "research_db_path": "/tmp/research.db",
            "research_manifest_path": "/tmp/research_manifest.json",
            "source_snapshot_id": "research_snapshot_v1",
            "source_snapshot_checksum": "research_snapshot_checksum_v1",
            "symbols": ("2330.TW", "2317.TW"),
        }
        values.update(overrides)
        return build_technical_risk_v1_validation_candidate_evaluation_request(**values)

    def evaluate(self, dataset=None):
        materializer = FakeValidationDatasetMaterializer(dataset or self.dataset())
        evaluator = CountingCandidateEvaluator()
        result = TechnicalRiskValidationCandidateEvaluationOrchestrator(
            dataset_materializer=materializer,
            candidate_evaluator=evaluator,
        ).evaluate(self.request())
        return result, materializer, evaluator

    def test_evaluates_exact_candidate_threshold_matrix_and_materializes_dataset_once(self):
        result, materializer, evaluator = self.evaluate()

        self.assertEqual(result.split_role, TechnicalRiskOOSSplitRole.VALIDATION)
        self.assertEqual(result.validation_start_date, date(2022, 1, 1))
        self.assertEqual(result.validation_end_date, date(2023, 12, 31))
        self.assertEqual(result.candidate_count, 4)
        self.assertEqual(tuple(identity[0] for identity in result.candidate_identities), TECH_RISK_VALIDATION_CANDIDATE_IDS_V1)
        self.assertEqual(result.threshold_set_count, 81)
        self.assertEqual(result.evaluation_count, 324)
        self.assertEqual(len(result.evaluation_records), 324)
        self.assertEqual(result.dataset_materialization_count, 1)
        self.assertEqual(len(materializer.calls), 1)
        self.assertEqual(len(evaluator.calls), 324)
        self.assertEqual(
            materializer.calls[0].required_output_split_roles,
            (TechnicalRiskOOSSplitRole.VALIDATION,),
        )

    def test_each_candidate_has_exactly_eighty_one_threshold_evaluations(self):
        result, _, _ = self.evaluate()

        counts = {summary.candidate_id: summary.evaluation_count for summary in result.candidate_summaries}

        self.assertEqual(counts, {candidate_id: 81 for candidate_id in TECH_RISK_VALIDATION_CANDIDATE_IDS_V1})

    def test_reuses_existing_candidate_evaluator_and_preserves_metric_evidence(self):
        result, _, evaluator = self.evaluate()
        first_record = result.evaluation_records[0]

        self.assertEqual(len(evaluator.calls), 324)
        self.assertTrue(first_record.aggregate_metrics)
        self.assertTrue(first_record.monotonicity_results)
        self.assertTrue(any(metric.mae20_mean is not None for metric in first_record.aggregate_metrics))
        self.assertTrue(any(metric.mae60_mean is not None for metric in first_record.aggregate_metrics))
        self.assertTrue(any(metric.coverage_ratio is not None for metric in first_record.aggregate_metrics))

    def test_compact_evaluator_has_exact_standard_evaluator_parity(self):
        dataset = self.dataset()
        candidate = _candidate_specs()[0]
        threshold = materialize_technical_risk_v1_threshold_grid().threshold_sets[0]
        evaluation_input = TechnicalRiskCandidateEvaluationInput(
            evaluation_input_version=TECH_RISK_CANDIDATE_EVALUATION_INPUT_V1,
            dataset_id=dataset.dataset_id,
            dataset_checksum=dataset.dataset_checksum,
            candidate_id=candidate.policy_candidate_id,
            candidate_version=candidate.candidate_version,
            candidate_structural_checksum=candidate.candidate_structural_checksum,
            threshold_set_id=threshold.threshold_set_id,
            threshold_set_version=threshold.threshold_set_version,
            threshold_set_checksum=threshold.threshold_set_checksum,
            derived_evidence_version=TECH_RISK_DERIVED_EVIDENCE_V1,
            evaluator_version=TECH_RISK_CANDIDATE_EVALUATOR_V1,
            metric_version=TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            quantile_version=TECH_RISK_QUANTILE_NEAREST_RANK_V1,
            numeric_context_version=TECH_RISK_DECIMAL_CONTEXT_V1,
            allowed_split_roles=(TechnicalRiskOOSSplitRole.VALIDATION,),
        )

        standard = TechnicalRiskCandidateEvaluator().evaluate(dataset, candidate, threshold, evaluation_input)
        compact = TechnicalRiskCandidateEvaluator().evaluate_compact(dataset, candidate, threshold, evaluation_input)

        self.assertEqual(compact.evaluated_row_count, len(standard.row_evaluations))
        self.assertEqual(compact.evaluation_id, standard.evaluation_id)
        self.assertEqual(compact.evaluation_checksum, standard.evaluation_checksum)
        self.assertEqual(compact.aggregate_metrics, standard.aggregate_metrics)
        self.assertEqual(compact.monotonicity_results, standard.monotonicity_results)

    def test_result_identity_and_ordering_are_deterministic(self):
        first, _, _ = self.evaluate()
        second, _, _ = self.evaluate()

        self.assertEqual(first.result_id, second.result_id)
        self.assertEqual(first.result_checksum, second.result_checksum)
        self.assertEqual(
            tuple(record.evaluation_id for record in first.evaluation_records),
            tuple(record.evaluation_id for record in second.evaluation_records),
        )

    def test_rejects_development_or_holdout_rows(self):
        development_row = self.row(
            "development",
            as_of_close=90.0,
            sma20=100.0,
            sma60=110.0,
            rsi14=30.0,
            split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT,
            evaluation_date=date(2021, 12, 31),
        )
        holdout_row = self.row(
            "holdout",
            as_of_close=90.0,
            sma20=100.0,
            sma60=110.0,
            rsi14=30.0,
            split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
            evaluation_date=date(2024, 1, 1),
        )

        with self.assertRaises(TechnicalRiskValidationCandidateEvaluationError):
            _validate_validation_dataset(self.dataset((development_row,)))
        with self.assertRaises(TechnicalRiskValidationCandidateEvaluationError):
            _validate_validation_dataset(self.dataset((holdout_row,)))

    def test_request_rejects_non_canonical_candidates_or_dates(self):
        request = self.request()

        with self.assertRaises(TechnicalRiskValidationCandidateEvaluationError):
            replace(request, candidate_ids=("TECH_POLICY_CANDIDATE_A",))
        with self.assertRaises(TechnicalRiskValidationCandidateEvaluationError):
            replace(request, validation_start_date=date(2021, 1, 1))

    def test_grid_and_candidates_are_exact_contract_inventory(self):
        grid = materialize_technical_risk_v1_threshold_grid()
        candidates = _candidate_specs()

        self.assertEqual(len(grid.threshold_sets), 81)
        self.assertEqual(tuple(candidate.policy_candidate_id for candidate in candidates), TECH_RISK_VALIDATION_CANDIDATE_IDS_V1)

    def test_result_has_no_winner_or_selection_fields(self):
        result, _, _ = self.evaluate()

        forbidden_attributes = (
            "winner",
            "winner_candidate",
            "best_candidate",
            "best_threshold",
            "selected_candidate",
            "selected_threshold",
            "approved_threshold",
        )
        for attribute in forbidden_attributes:
            self.assertFalse(hasattr(result, attribute), attribute)

    def test_source_boundary_excludes_selection_persistence_network_and_production_runtime(self):
        source = inspect.getsource(validation_candidate_evaluation)

        forbidden_tokens = (
            "winner",
            "best_candidate",
            "best_threshold",
            "selected_threshold",
            "sqlite3",
            "yfinance",
            "Yahoo",
            "requests",
            "data/production",
            "production_runtime",
            "TechnicalRiskSignalProducer",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
