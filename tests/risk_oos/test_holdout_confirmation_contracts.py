import inspect
import sys
import unittest
from dataclasses import fields
from dataclasses import replace
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos import TECH_RISK_HOLDOUT_CONFIRMATION_ARTIFACT_V1
from risk_oos import TECH_RISK_HOLDOUT_CONFIRMATION_CRITERIA_V1
from risk_oos import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos import TechnicalRiskCandidateEvaluator
from risk_oos import TechnicalRiskHoldoutConfirmationArtifact
from risk_oos import TechnicalRiskHoldoutConfirmationCriteria
from risk_oos import TechnicalRiskHoldoutConfirmationDecision
from risk_oos import TechnicalRiskHoldoutConfirmationError
from risk_oos import TechnicalRiskHoldoutConfirmationReasonCode
from risk_oos import TechnicalRiskHoldoutConfirmationStatus
from risk_oos import TechnicalRiskHoldoutConsistencyRequirement
from risk_oos import TechnicalRiskHoldoutContaminationPolicy
from risk_oos import TechnicalRiskHoldoutCoverageHandling
from risk_oos import TechnicalRiskHoldoutEvaluationReference
from risk_oos import TechnicalRiskHoldoutMonotonicityHandling
from risk_oos import TechnicalRiskHoldoutWarningHandling
from risk_oos import TechnicalRiskOOSSplitRole
from risk_oos import TechnicalRiskValidationCombinationOutcome
from risk_oos import TechnicalRiskValidationSelectionReasonCode
from risk_oos import TechnicalRiskValidationSelectionStatus
from risk_oos import technical_risk_candidate_a_spec
from risk_oos import technical_risk_candidate_b_spec
from tests.risk_oos.test_validation_selection_contracts import TechnicalRiskValidationSelectionContractTestCase


class TechnicalRiskHoldoutConfirmationContractTestCase(unittest.TestCase):

    def setUp(self):
        self.helper = TechnicalRiskValidationSelectionContractTestCase(methodName="runTest")

    def full_dataset(self, dataset_checksum="full_oos_dataset_checksum_001"):
        return self.helper.dataset(
            (
                self.helper.row(row_id="development_row_001", split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT),
                self.helper.row(row_id="validation_row_001", split_role=TechnicalRiskOOSSplitRole.VALIDATION),
                self.helper.row(row_id="holdout_row_001", split_role=TechnicalRiskOOSSplitRole.HOLDOUT),
            ),
            dataset_checksum=dataset_checksum,
        )

    def threshold_a(self):
        return self.helper.threshold_set("threshold_set_001")

    def threshold_b(self):
        return self.helper.threshold_set("threshold_set_002", close_vs_sma20="-0.06")

    def validation_selection_bundle(self, status=TechnicalRiskValidationSelectionStatus.SELECTED):
        dataset = self.full_dataset()
        validation_evaluations = self.helper.validation_evaluations(dataset)
        if status == TechnicalRiskValidationSelectionStatus.SELECTED:
            decision = self.helper.decision(selected_evaluation=validation_evaluations[0])
            considered = self.helper.considered(validation_evaluations)
        elif status == TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION:
            decision = self.helper.decision(status=TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION)
            considered = self.helper.considered(
                validation_evaluations,
                outcomes=(TechnicalRiskValidationCombinationOutcome.NOT_SELECTED, TechnicalRiskValidationCombinationOutcome.NOT_SELECTED),
                reason_codes=(
                    (TechnicalRiskValidationSelectionReasonCode.NO_VALID_SELECTION_EVIDENCE,),
                    (TechnicalRiskValidationSelectionReasonCode.NO_VALID_SELECTION_EVIDENCE,),
                ),
            )
        else:
            decision = self.helper.decision(status=TechnicalRiskValidationSelectionStatus.TIE_REQUIRES_METHOD_DECISION)
            considered = self.helper.considered(
                validation_evaluations,
                outcomes=(TechnicalRiskValidationCombinationOutcome.UNRESOLVED_TIE, TechnicalRiskValidationCombinationOutcome.UNRESOLVED_TIE),
                reason_codes=(
                    (TechnicalRiskValidationSelectionReasonCode.TIE_REQUIRES_METHOD_DECISION,),
                    (TechnicalRiskValidationSelectionReasonCode.TIE_REQUIRES_METHOD_DECISION,),
                ),
            )
        selection = self.helper.selection_artifact(
            dataset=dataset,
            evaluations=validation_evaluations,
            decision=decision,
            considered=considered,
        )
        return dataset, selection, validation_evaluations[0]

    def holdout_evaluation(self, dataset=None, candidate=None, threshold_set=None, roles=(TechnicalRiskOOSSplitRole.HOLDOUT,), **overrides):
        dataset = self.full_dataset() if dataset is None else dataset
        candidate = technical_risk_candidate_a_spec() if candidate is None else candidate
        threshold_set = self.threshold_a() if threshold_set is None else threshold_set
        return TechnicalRiskCandidateEvaluator().evaluate(
            dataset,
            candidate,
            threshold_set,
            self.helper.evaluation_input(dataset, candidate, threshold_set, roles=roles, **overrides),
        )

    def criteria(self, **overrides):
        values = {
            "criteria_id": None,
            "criteria_version": TECH_RISK_HOLDOUT_CONFIRMATION_CRITERIA_V1,
            "monotonicity_handling": TechnicalRiskHoldoutMonotonicityHandling.RETAIN_STRUCTURED_EVIDENCE,
            "coverage_handling": TechnicalRiskHoldoutCoverageHandling.RETAIN_COVERAGE_EVIDENCE,
            "methodology_warning_handling": TechnicalRiskHoldoutWarningHandling.RETAIN_METHOD_WARNINGS,
            "consistency_requirement": TechnicalRiskHoldoutConsistencyRequirement.REQUIRE_VALIDATION_HOLDOUT_VERSION_CONTINUITY,
            "contamination_policy": TechnicalRiskHoldoutContaminationPolicy.ALLOW_GOVERNANCE_DECLARATION,
            "derived_evidence_version": TECH_RISK_DERIVED_EVIDENCE_V1,
            "evaluator_version": TECH_RISK_CANDIDATE_EVALUATOR_V1,
            "metric_version": TECH_RISK_CONTINUOUS_MAE_METRIC_V1,
            "quantile_version": TECH_RISK_QUANTILE_NEAREST_RANK_V1,
            "numeric_context_version": TECH_RISK_DECIMAL_CONTEXT_V1,
        }
        values.update(overrides)
        return TechnicalRiskHoldoutConfirmationCriteria(**values)

    def decision(self, holdout_evaluation, status=TechnicalRiskHoldoutConfirmationStatus.CONFIRMED, **overrides):
        reasons = {
            TechnicalRiskHoldoutConfirmationStatus.CONFIRMED: (TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_EVIDENCE_CONFIRMED,),
            TechnicalRiskHoldoutConfirmationStatus.NOT_CONFIRMED: (TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_NOT_CONFIRMED,),
            TechnicalRiskHoldoutConfirmationStatus.REVIEW_REQUIRED: (TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_METHOD_REVIEW_REQUIRED,),
            TechnicalRiskHoldoutConfirmationStatus.CONTAMINATION_DECLARED: (TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_CONTAMINATION_DECLARED,),
        }[status]
        values = {
            "confirmation_status": status,
            "confirmed_candidate_id": holdout_evaluation.candidate_id,
            "confirmed_candidate_structural_checksum": holdout_evaluation.candidate_structural_checksum,
            "confirmed_threshold_set_id": holdout_evaluation.threshold_set_id,
            "confirmed_threshold_set_checksum": holdout_evaluation.threshold_set_checksum,
            "holdout_evaluation_id": holdout_evaluation.evaluation_id,
            "holdout_evaluation_checksum": holdout_evaluation.evaluation_checksum,
            "structured_confirmation_reason_codes": reasons,
        }
        values.update(overrides)
        return TechnicalRiskHoldoutConfirmationDecision(**values)

    def artifact(self, dataset=None, selection=None, accepted_validation=None, holdout_evaluation=None, reference=None, criteria=None, decision=None, **overrides):
        if dataset is None or selection is None or accepted_validation is None:
            dataset, selection, accepted_validation = self.validation_selection_bundle()
        holdout_evaluation = self.holdout_evaluation(dataset=dataset) if holdout_evaluation is None else holdout_evaluation
        reference = TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(holdout_evaluation) if reference is None else reference
        criteria = self.criteria() if criteria is None else criteria
        decision = self.decision(holdout_evaluation) if decision is None else decision
        return TechnicalRiskHoldoutConfirmationArtifact.from_holdout_contracts(
            validation_selection=selection,
            holdout_dataset=dataset,
            accepted_validation_evaluation=accepted_validation,
            holdout_evaluation=holdout_evaluation,
            holdout_reference=reference,
            confirmation_criteria=criteria,
            confirmation_decision=decision,
            **overrides,
        )

    def test_valid_selected_validation_selection_enters_holdout(self):
        artifact = self.artifact()

        self.assertEqual(artifact.confirmation_version, TECH_RISK_HOLDOUT_CONFIRMATION_ARTIFACT_V1)
        self.assertTrue(artifact.confirmation_id.startswith("technical_risk_holdout_confirmation_"))
        self.assertEqual(artifact.confirmation_status, TechnicalRiskHoldoutConfirmationStatus.CONFIRMED)
        self.assertEqual(artifact.selected_candidate_id, "TECH_POLICY_CANDIDATE_A")
        self.assertEqual(len(artifact.holdout_aggregate_metrics), 3)
        self.assertEqual(len(artifact.holdout_monotonicity_results), 2)

    def test_no_valid_selection_and_tie_rejected(self):
        for status in (
            TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION,
            TechnicalRiskValidationSelectionStatus.TIE_REQUIRES_METHOD_DECISION,
        ):
            dataset, selection, accepted_validation = self.validation_selection_bundle(status=status)
            with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "SELECTED"):
                self.artifact(dataset=dataset, selection=selection, accepted_validation=accepted_validation)

    def test_exact_selected_candidate_and_threshold_required(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        alternate_candidate = self.holdout_evaluation(dataset=dataset, candidate=technical_risk_candidate_b_spec(), threshold_set=self.threshold_a())
        alternate_threshold = self.holdout_evaluation(dataset=dataset, threshold_set=self.threshold_b())

        with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "candidate"):
            self.artifact(
                dataset=dataset,
                selection=selection,
                accepted_validation=accepted_validation,
                holdout_evaluation=alternate_candidate,
                reference=TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(alternate_candidate),
                decision=self.decision(alternate_candidate),
            )
        with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "threshold"):
            self.artifact(
                dataset=dataset,
                selection=selection,
                accepted_validation=accepted_validation,
                holdout_evaluation=alternate_threshold,
                reference=TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(alternate_threshold),
                decision=self.decision(alternate_threshold),
            )

    def test_holdout_only_evaluation_required(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        for roles in (
            (TechnicalRiskOOSSplitRole.DEVELOPMENT,),
            (TechnicalRiskOOSSplitRole.VALIDATION,),
            (TechnicalRiskOOSSplitRole.VALIDATION, TechnicalRiskOOSSplitRole.HOLDOUT),
        ):
            evaluation = replace(self.holdout_evaluation(dataset=dataset), evaluated_split_roles=roles)
            with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "HOLDOUT only"):
                self.artifact(
                    dataset=dataset,
                    selection=selection,
                    accepted_validation=accepted_validation,
                    holdout_evaluation=evaluation,
                    reference=TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(self.holdout_evaluation(dataset=dataset)),
                    decision=self.decision(evaluation),
                )

    def test_holdout_dataset_lineage_mismatch_rejected(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        changed_id = replace(evaluation, dataset_id="changed_dataset_id")
        changed_checksum = replace(evaluation, dataset_checksum="changed_dataset_checksum")

        for bad_evaluation in (changed_id, changed_checksum):
            with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "dataset"):
                self.artifact(
                    dataset=dataset,
                    selection=selection,
                    accepted_validation=accepted_validation,
                    holdout_evaluation=bad_evaluation,
                    reference=TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(bad_evaluation),
                    decision=self.decision(bad_evaluation),
                )

    def test_version_continuity_rejected(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        cases = (
            replace(evaluation, derived_evidence_version="OTHER_DERIVED_EVIDENCE"),
            replace(evaluation, evaluator_version="OTHER_EVALUATOR"),
            replace(evaluation, metric_version="OTHER_METRIC"),
            replace(evaluation, quantile_version="OTHER_QUANTILE"),
            replace(evaluation, numeric_context_version="OTHER_CONTEXT"),
        )

        for bad_evaluation in cases:
            with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "mismatch|Unsupported"):
                self.artifact(
                    dataset=dataset,
                    selection=selection,
                    accepted_validation=accepted_validation,
                    holdout_evaluation=bad_evaluation,
                    reference=TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(evaluation),
                    decision=self.decision(bad_evaluation),
                )

    def test_reference_and_validation_selection_echo_mismatch_rejected(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        reference = replace(
            TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(evaluation),
            holdout_evaluation_checksum="changed_checksum",
        )
        bad_accepted = replace(accepted_validation, evaluation_checksum="changed_validation_checksum")

        with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "reference echo"):
            self.artifact(dataset=dataset, selection=selection, accepted_validation=accepted_validation, holdout_evaluation=evaluation, reference=reference)
        with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "accepted Validation"):
            self.artifact(dataset=dataset, selection=selection, accepted_validation=bad_accepted, holdout_evaluation=evaluation)

    def test_confirmation_status_semantics(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        for status in TechnicalRiskHoldoutConfirmationStatus:
            artifact = self.artifact(
                dataset=dataset,
                selection=selection,
                accepted_validation=accepted_validation,
                holdout_evaluation=evaluation,
                decision=self.decision(evaluation, status=status),
            )
            self.assertEqual(artifact.confirmation_status, status)

    def test_status_reason_required(self):
        evaluation = self.holdout_evaluation()

        with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "requires structured reason"):
            self.decision(
                evaluation,
                status=TechnicalRiskHoldoutConfirmationStatus.CONFIRMED,
                structured_confirmation_reason_codes=(TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_NOT_CONFIRMED,),
            )

    def test_status_primary_reasons_are_mutually_exclusive(self):
        evaluation = self.holdout_evaluation()
        primary_reasons = {
            TechnicalRiskHoldoutConfirmationStatus.CONFIRMED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_EVIDENCE_CONFIRMED,
            TechnicalRiskHoldoutConfirmationStatus.NOT_CONFIRMED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_NOT_CONFIRMED,
            TechnicalRiskHoldoutConfirmationStatus.REVIEW_REQUIRED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_METHOD_REVIEW_REQUIRED,
            TechnicalRiskHoldoutConfirmationStatus.CONTAMINATION_DECLARED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_CONTAMINATION_DECLARED,
        }

        for status, required_reason in primary_reasons.items():
            with self.subTest(status=status, reason=required_reason):
                decision = self.decision(
                    evaluation,
                    status=status,
                    structured_confirmation_reason_codes=(required_reason,),
                )
                self.assertEqual(decision.confirmation_status, status)

            for prohibited_reason in set(primary_reasons.values()) - {required_reason}:
                with self.subTest(status=status, prohibited_reason=prohibited_reason):
                    with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "contradictory structured reason"):
                        self.decision(
                            evaluation,
                            status=status,
                            structured_confirmation_reason_codes=(required_reason, prohibited_reason),
                        )

                with self.subTest(status=status, missing_required_reason=prohibited_reason):
                    with self.assertRaisesRegex(TechnicalRiskHoldoutConfirmationError, "requires structured reason"):
                        self.decision(
                            evaluation,
                            status=status,
                            structured_confirmation_reason_codes=(prohibited_reason,),
                        )

    def test_supplementary_concern_reasons_do_not_change_status(self):
        evaluation = self.holdout_evaluation()
        decision = self.decision(
            evaluation,
            structured_confirmation_reason_codes=(
                TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_EVIDENCE_CONFIRMED,
                TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_MONOTONICITY_CONCERN,
                TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_COVERAGE_CONCERN,
            ),
        )

        self.assertEqual(decision.confirmation_status, TechnicalRiskHoldoutConfirmationStatus.CONFIRMED)

    def test_audit_metadata_does_not_change_checksum(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        first = self.artifact(
            dataset=dataset,
            selection=selection,
            accepted_validation=accepted_validation,
            holdout_evaluation=evaluation,
            decision=self.decision(
                evaluation,
                approved_by="Alice",
                approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                human_rationale="first rationale.",
            ),
        )
        second = self.artifact(
            dataset=dataset,
            selection=selection,
            accepted_validation=accepted_validation,
            holdout_evaluation=evaluation,
            decision=self.decision(
                evaluation,
                approved_by="Bob",
                approved_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                human_rationale="second rationale!",
            ),
        )

        self.assertEqual(first.confirmation_id, second.confirmation_id)
        self.assertEqual(first.confirmation_checksum, second.confirmation_checksum)

    def test_same_semantic_confirmation_same_id_and_checksum(self):
        self.assertEqual(self.artifact().confirmation_id, self.artifact().confirmation_id)
        self.assertEqual(self.artifact().confirmation_checksum, self.artifact().confirmation_checksum)

    def test_semantic_changes_change_checksum(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        first = self.artifact(dataset=dataset, selection=selection, accepted_validation=accepted_validation, holdout_evaluation=evaluation)
        changed_eval = replace(evaluation, evaluation_checksum="changed_holdout_checksum")
        status_changed = self.artifact(
            dataset=dataset,
            selection=selection,
            accepted_validation=accepted_validation,
            holdout_evaluation=evaluation,
            decision=self.decision(evaluation, status=TechnicalRiskHoldoutConfirmationStatus.REVIEW_REQUIRED),
        )
        criteria_changed = self.artifact(
            dataset=dataset,
            selection=selection,
            accepted_validation=accepted_validation,
            holdout_evaluation=evaluation,
            criteria=self.criteria(monotonicity_handling=TechnicalRiskHoldoutMonotonicityHandling.REQUIRE_METHOD_REVIEW_ON_WARNING),
        )
        evaluation_changed = self.artifact(
            dataset=dataset,
            selection=selection,
            accepted_validation=accepted_validation,
            holdout_evaluation=changed_eval,
            reference=TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(changed_eval),
            decision=self.decision(changed_eval),
        )

        self.assertNotEqual(first.confirmation_checksum, evaluation_changed.confirmation_checksum)
        self.assertNotEqual(first.confirmation_checksum, status_changed.confirmation_checksum)
        self.assertNotEqual(first.confirmation_checksum, criteria_changed.confirmation_checksum)

    def test_copied_metric_value_change_changes_checksum(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        first = self.artifact(dataset=dataset, selection=selection, accepted_validation=accepted_validation, holdout_evaluation=evaluation)
        changed_metric = replace(evaluation.aggregate_metrics[0], mae20_mean=Decimal("-0.123456789123456789"))
        changed_evaluation = replace(evaluation, aggregate_metrics=(changed_metric,) + evaluation.aggregate_metrics[1:])

        changed = self.artifact(
            dataset=dataset,
            selection=selection,
            accepted_validation=accepted_validation,
            holdout_evaluation=changed_evaluation,
            reference=TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(changed_evaluation),
            decision=self.decision(changed_evaluation),
        )

        self.assertNotEqual(first.confirmation_checksum, changed.confirmation_checksum)
        self.assertIsInstance(changed.holdout_aggregate_metrics[0].mae20_mean, Decimal)

    def test_metrics_copied_from_frozen_evaluation_only(self):
        dataset, selection, accepted_validation = self.validation_selection_bundle()
        evaluation = self.holdout_evaluation(dataset=dataset)
        original_metrics = evaluation.aggregate_metrics
        original_monotonicity = evaluation.monotonicity_results
        artifact = self.artifact(dataset=dataset, selection=selection, accepted_validation=accepted_validation, holdout_evaluation=evaluation)

        self.assertEqual(artifact.holdout_aggregate_metrics, evaluation.aggregate_metrics)
        self.assertEqual(artifact.holdout_monotonicity_results, evaluation.monotonicity_results)
        self.assertEqual([metric.severity.value for metric in artifact.holdout_aggregate_metrics], ["LOW", "MEDIUM", "HIGH"])
        self.assertNotEqual([metric.severity.value for metric in artifact.holdout_aggregate_metrics], ["HIGH", "LOW", "MEDIUM"])
        self.assertEqual(evaluation.aggregate_metrics, original_metrics)
        self.assertEqual(evaluation.monotonicity_results, original_monotonicity)

    def test_no_search_api_alternate_pair_freeze_or_production_boundary(self):
        import risk_oos

        source = inspect.getsource(__import__("risk_oos.holdout_confirmation", fromlist=[""]))
        forbidden_tokens = (
            "def search",
            "search_holdout",
            "search_thresholds",
            "generate_thresholds",
            "def optimize",
            "grid_search",
            "rank(",
            "find_best",
            "select_best",
            "evaluate_best",
            "candidate_list",
            "threshold_list",
            "alternative_pair",
            "holdout_execution_count",
            "TechnicalRiskPolicyFreezeArtifact",
            "freeze_id",
            "freeze_checksum",
            "RiskEvaluationPolicy",
            "RiskSignal",
            "TechnicalRiskSignalProducer",
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "open(",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)
        self.assertIn("TechnicalRiskHoldoutConfirmationArtifact", risk_oos.__all__)
        self.assertTrue({"confirmation_id", "confirmation_checksum"}.issubset({field.name for field in fields(TechnicalRiskHoldoutConfirmationArtifact)}))


if __name__ == "__main__":
    unittest.main()
