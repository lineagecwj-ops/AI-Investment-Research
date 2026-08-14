import inspect
import sys
import unittest
from dataclasses import fields
from dataclasses import replace
from datetime import datetime
from datetime import timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk_oos import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos import TECH_RISK_POLICY_FREEZE_ARTIFACT_V1
from risk_oos import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos import TechnicalRiskHoldoutConfirmationReasonCode
from risk_oos import TechnicalRiskHoldoutConfirmationStatus
from risk_oos import TechnicalRiskPolicyFreezeArtifact
from risk_oos import TechnicalRiskPolicyFreezeError
from risk_oos import TechnicalRiskPolicyFreezeReasonCode
from risk_oos import TechnicalRiskPolicyFreezeStatus
from risk_oos import TechnicalRiskValidationSelectionStatus
from risk_oos import technical_risk_candidate_a_spec
from risk_oos import technical_risk_candidate_b_spec
from tests.risk_oos.test_holdout_confirmation_contracts import TechnicalRiskHoldoutConfirmationContractTestCase


TECHNICAL_POLICY_VERSION = "TECH_RISK_POLICY_V1_RESEARCH_FREEZE"


class TechnicalRiskPolicyFreezeContractTestCase(unittest.TestCase):

    def setUp(self):
        self.helper = TechnicalRiskHoldoutConfirmationContractTestCase(methodName="runTest")
        self.helper.setUp()

    def bundle(self):
        dataset, selection, accepted_validation = self.helper.validation_selection_bundle()
        holdout_evaluation = self.helper.holdout_evaluation(dataset=dataset)
        confirmation = self.helper.artifact(
            dataset=dataset,
            selection=selection,
            accepted_validation=accepted_validation,
            holdout_evaluation=holdout_evaluation,
        )
        return dataset, selection, accepted_validation, holdout_evaluation, confirmation

    def freeze(self, selection=None, confirmation=None, candidate=None, threshold_set=None, **overrides):
        if selection is None or confirmation is None:
            _, selection, _, _, confirmation = self.bundle()
        candidate = technical_risk_candidate_a_spec() if candidate is None else candidate
        threshold_set = self.helper.threshold_a() if threshold_set is None else threshold_set
        values = {"technical_policy_version": TECHNICAL_POLICY_VERSION}
        values.update(overrides)
        return TechnicalRiskPolicyFreezeArtifact.from_research_chain(
            validation_selection=selection,
            holdout_confirmation=confirmation,
            candidate=candidate,
            threshold_set=threshold_set,
            **values,
        )

    def direct_freeze_from(self, freeze, **overrides):
        values = {field.name: getattr(freeze, field.name) for field in fields(TechnicalRiskPolicyFreezeArtifact)}
        values["freeze_id"] = None
        values["freeze_checksum"] = None
        values.update(overrides)
        return TechnicalRiskPolicyFreezeArtifact(**values)

    def tamper(self, artifact, **overrides):
        for field_name, value in overrides.items():
            object.__setattr__(artifact, field_name, value)
        return artifact

    def test_selected_validation_and_confirmed_holdout_freeze_success(self):
        _, selection, _, _, confirmation = self.bundle()
        freeze = self.freeze(selection=selection, confirmation=confirmation)

        self.assertEqual(freeze.freeze_version, TECH_RISK_POLICY_FREEZE_ARTIFACT_V1)
        self.assertEqual(freeze.freeze_status, TechnicalRiskPolicyFreezeStatus.FROZEN)
        self.assertEqual(freeze.structured_freeze_reason_codes, (TechnicalRiskPolicyFreezeReasonCode.RESEARCH_POLICY_FROZEN,))
        self.assertTrue(freeze.freeze_id.startswith("technical_risk_policy_freeze_"))

    def test_validation_must_be_selected(self):
        _, _, _, _, confirmation = self.bundle()
        for status in (
            TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION,
            TechnicalRiskValidationSelectionStatus.TIE_REQUIRES_METHOD_DECISION,
        ):
            _, selection, _, _, _ = self.bundle()
            self.tamper(selection, selection_status=status)
            with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "SELECTED"):
                self.freeze(selection=selection, confirmation=confirmation)

    def test_holdout_must_be_confirmed(self):
        dataset, selection, accepted_validation = self.helper.validation_selection_bundle()
        holdout_evaluation = self.helper.holdout_evaluation(dataset=dataset)
        for status in (
            TechnicalRiskHoldoutConfirmationStatus.NOT_CONFIRMED,
            TechnicalRiskHoldoutConfirmationStatus.REVIEW_REQUIRED,
            TechnicalRiskHoldoutConfirmationStatus.CONTAMINATION_DECLARED,
        ):
            confirmation = self.helper.artifact(
                dataset=dataset,
                selection=selection,
                accepted_validation=accepted_validation,
                holdout_evaluation=holdout_evaluation,
                decision=self.helper.decision(holdout_evaluation, status=status),
            )
            with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "CONFIRMED"):
                self.freeze(selection=selection, confirmation=confirmation)

    def test_holdout_confirmed_reason_required(self):
        _, selection, _, _, confirmation = self.bundle()
        self.tamper(confirmation, structured_confirmation_reason_codes=(TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_COVERAGE_CONCERN,))

        with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "HOLDOUT_EVIDENCE_CONFIRMED"):
            self.freeze(selection=selection, confirmation=confirmation)

    def test_validation_holdout_lineage_mismatch_rejected(self):
        _, selection, _, _, confirmation = self.bundle()
        cases = (
            ("validation_selection_id", "different_selection_id", "validation_selection_id"),
            ("validation_selection_checksum", "different_selection_checksum", "validation_selection_checksum"),
            ("selected_candidate_id", "different_candidate", "candidate"),
            ("selected_candidate_structural_checksum", "different_candidate_checksum", "candidate checksum"),
            ("selected_threshold_set_id", "different_threshold", "threshold"),
            ("selected_threshold_set_checksum", "different_threshold_checksum", "threshold checksum"),
            ("accepted_validation_evaluation_id", "different_validation_eval", "accepted Validation evaluation id"),
            ("accepted_validation_evaluation_checksum", "different_validation_eval_checksum", "accepted Validation evaluation checksum"),
        )
        for field_name, value, message in cases:
            with self.subTest(field_name=field_name):
                changed = self.tamper(replace(confirmation), **{field_name: value})
                with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, message):
                    self.freeze(selection=selection, confirmation=changed)

    def test_candidate_contract_must_match_frozen_chain(self):
        _, selection, _, _, confirmation = self.bundle()
        candidate = technical_risk_candidate_a_spec()
        cases = (
            (self.tamper(replace(candidate), policy_candidate_id="TECH_POLICY_CANDIDATE_X"), "candidate id"),
            (self.tamper(replace(candidate), candidate_version="v9"), "candidate version"),
            (self.tamper(replace(candidate), candidate_structural_checksum="changed_candidate_checksum"), "candidate structural checksum"),
        )
        for changed_candidate, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, message):
                    self.freeze(selection=selection, confirmation=confirmation, candidate=changed_candidate)

    def test_alternate_candidate_rejected(self):
        _, selection, _, _, confirmation = self.bundle()
        with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "candidate"):
            self.freeze(selection=selection, confirmation=confirmation, candidate=technical_risk_candidate_b_spec())

    def test_threshold_contract_must_match_frozen_chain(self):
        _, selection, _, _, confirmation = self.bundle()
        threshold = self.helper.threshold_a()
        cases = (
            (self.tamper(replace(threshold), threshold_set_id="threshold_set_x"), "threshold id"),
            (self.tamper(replace(threshold), threshold_set_version="v9"), "threshold version"),
            (self.tamper(replace(threshold), threshold_set_checksum="changed_threshold_checksum"), "threshold checksum"),
        )
        for changed_threshold, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, message):
                    self.freeze(selection=selection, confirmation=confirmation, threshold_set=changed_threshold)

    def test_alternate_threshold_rejected(self):
        _, selection, _, _, confirmation = self.bundle()
        with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "threshold"):
            self.freeze(selection=selection, confirmation=confirmation, threshold_set=self.helper.threshold_b())

    def test_holdout_evaluation_lineage_required(self):
        _, selection, _, _, confirmation = self.bundle()
        changed = self.tamper(replace(confirmation), holdout_evaluation_id="")

        with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "holdout_evaluation_id"):
            self.freeze(selection=selection, confirmation=changed)

    def test_version_continuity_mismatch_rejected(self):
        _, selection, _, _, confirmation = self.bundle()
        cases = (
            ("evaluator_version", "CHANGED_EVALUATOR_VERSION", "evaluator_version"),
            ("metric_version", "CHANGED_METRIC_VERSION", "metric_version"),
            ("quantile_version", "CHANGED_QUANTILE_VERSION", "quantile_version"),
            ("numeric_context_version", "CHANGED_NUMERIC_CONTEXT_VERSION", "numeric_context_version"),
        )
        for field_name, value, message in cases:
            with self.subTest(field_name=field_name):
                changed = self.tamper(replace(confirmation), **{field_name: value})
                with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, message):
                    self.freeze(selection=selection, confirmation=changed)

    def test_derived_evidence_version_mismatch_rejected(self):
        _, selection, _, _, confirmation = self.bundle()
        changed = self.tamper(replace(confirmation), derived_evidence_version="CHANGED_DERIVED_EVIDENCE_VERSION")

        with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "derived_evidence_version"):
            self.freeze(selection=selection, confirmation=changed)

    def test_freeze_artifact_preserves_exact_lineage(self):
        _, selection, accepted_validation, holdout_evaluation, confirmation = self.bundle()
        candidate = technical_risk_candidate_a_spec()
        threshold_set = self.helper.threshold_a()
        freeze = self.freeze(selection=selection, confirmation=confirmation, candidate=candidate, threshold_set=threshold_set)

        self.assertEqual(freeze.candidate_id, candidate.policy_candidate_id)
        self.assertEqual(freeze.candidate_version, candidate.candidate_version)
        self.assertEqual(freeze.candidate_structural_checksum, candidate.candidate_structural_checksum)
        self.assertEqual(freeze.threshold_set_id, threshold_set.threshold_set_id)
        self.assertEqual(freeze.threshold_set_version, threshold_set.threshold_set_version)
        self.assertEqual(freeze.threshold_set_checksum, threshold_set.threshold_set_checksum)
        self.assertEqual(freeze.validation_selection_id, selection.selection_id)
        self.assertEqual(freeze.validation_selection_checksum, selection.selection_checksum)
        self.assertEqual(freeze.holdout_confirmation_id, confirmation.confirmation_id)
        self.assertEqual(freeze.holdout_confirmation_checksum, confirmation.confirmation_checksum)
        self.assertEqual(freeze.accepted_validation_evaluation_id, accepted_validation.evaluation_id)
        self.assertEqual(freeze.accepted_validation_evaluation_checksum, accepted_validation.evaluation_checksum)
        self.assertEqual(freeze.holdout_evaluation_id, holdout_evaluation.evaluation_id)
        self.assertEqual(freeze.holdout_evaluation_checksum, holdout_evaluation.evaluation_checksum)

    def test_freeze_does_not_duplicate_upstream_metrics_or_combinations(self):
        freeze_fields = {field.name for field in fields(TechnicalRiskPolicyFreezeArtifact)}

        self.assertNotIn("holdout_aggregate_metrics", freeze_fields)
        self.assertNotIn("holdout_monotonicity_results", freeze_fields)
        self.assertNotIn("considered_combinations", freeze_fields)

    def test_same_semantic_inputs_same_id_and_checksum(self):
        self.assertEqual(self.freeze().freeze_id, self.freeze().freeze_id)
        self.assertEqual(self.freeze().freeze_checksum, self.freeze().freeze_checksum)

    def test_semantic_changes_change_freeze_checksum(self):
        freeze = self.freeze()
        changes = (
            {"technical_policy_version": "TECH_RISK_POLICY_V2_RESEARCH_FREEZE"},
            {"validation_selection_checksum": "changed_selection_checksum"},
            {"holdout_confirmation_checksum": "changed_confirmation_checksum"},
            {"candidate_structural_checksum": "changed_candidate_checksum"},
            {"threshold_set_checksum": "changed_threshold_checksum"},
            {"accepted_validation_evaluation_checksum": "changed_validation_eval_checksum"},
            {"holdout_evaluation_checksum": "changed_holdout_eval_checksum"},
            {"numeric_context_version": "CHANGED_NUMERIC_CONTEXT_VERSION"},
        )

        for change in changes:
            with self.subTest(change=change):
                changed = self.direct_freeze_from(freeze, **change)
                self.assertNotEqual(freeze.freeze_checksum, changed.freeze_checksum)
                self.assertNotEqual(freeze.freeze_id, changed.freeze_id)

    def test_audit_metadata_does_not_change_freeze_identity(self):
        first = self.freeze(
            approved_by="Alice",
            approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            human_rationale="frozen.",
        )
        second = self.freeze(
            approved_by="Bob",
            approved_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            human_rationale="frozen!",
        )

        self.assertEqual(first.freeze_id, second.freeze_id)
        self.assertEqual(first.freeze_checksum, second.freeze_checksum)

    def test_reason_order_is_canonical_and_duplicate_rejected(self):
        freeze = self.freeze(
            structured_freeze_reason_codes=("RESEARCH_POLICY_FROZEN",),
        )

        self.assertEqual(freeze.structured_freeze_reason_codes, (TechnicalRiskPolicyFreezeReasonCode.RESEARCH_POLICY_FROZEN,))
        with self.assertRaisesRegex(TechnicalRiskPolicyFreezeError, "Duplicate"):
            self.freeze(
                structured_freeze_reason_codes=(
                    TechnicalRiskPolicyFreezeReasonCode.RESEARCH_POLICY_FROZEN,
                    TechnicalRiskPolicyFreezeReasonCode.RESEARCH_POLICY_FROZEN,
                ),
            )

    def test_invalid_freeze_status_semantics_absent(self):
        enum_values = {status.value for status in TechnicalRiskPolicyFreezeStatus}

        self.assertEqual(enum_values, {"FROZEN"})
        self.assertFalse({"FAILED", "INVALID", "NOT_FROZEN", "FREEZE_NOT_ALLOWED"}.intersection(enum_values))

    def test_public_api_and_production_boundary(self):
        import risk_oos

        self.assertIn("TechnicalRiskPolicyFreezeArtifact", risk_oos.__all__)
        self.assertIn("TechnicalRiskPolicyFreezeStatus", risk_oos.__all__)
        self.assertIn("TechnicalRiskPolicyFreezeReasonCode", risk_oos.__all__)
        self.assertNotIn("to_production_policy", risk_oos.__all__)
        self.assertNotIn("TechnicalRiskSignalProducer", inspect.getsource(__import__("risk_oos.research_policy_freeze", fromlist=[""])))

    def test_no_search_rerun_freeze_deployment_or_production_api(self):
        source = inspect.getsource(__import__("risk_oos.research_policy_freeze", fromlist=[""]))
        forbidden_tokens = (
            "TechnicalRiskCandidateEvaluator",
            ".evaluate(",
            "derive_technical_risk_evidence",
            "evaluate_technical_risk_predicates",
            "search_holdout",
            "search_thresholds",
            "generate_thresholds",
            "grid_search",
            "def optimize",
            "rank(",
            "find_best",
            "select_best",
            "evaluate_best",
            "candidate_list",
            "threshold_list",
            "alternative_pair",
            "to_production_policy",
            "build_producer",
            "activate_policy",
            "deploy(",
            "publish_to_live",
            "RiskEvaluationPolicy",
            "RiskSignal",
            "TechnicalRiskSignalProducer",
            "sqlite",
            "LiveDataStore",
            "ResearchDataStore",
            "yfinance",
            "scanner",
            "open(",
            "write(",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
