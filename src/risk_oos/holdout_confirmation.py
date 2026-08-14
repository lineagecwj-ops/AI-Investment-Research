from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import hashlib
import json

from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetResult
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.candidate_evaluator import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos.candidate_evaluator import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos.candidate_evaluator import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluationResult
from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityResult
from risk_oos.candidate_evaluator import TechnicalRiskSeverityMAEMetrics
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_DERIVED_EVIDENCE_V1
from risk_oos.validation_selection import TechnicalRiskValidationSelectionArtifact
from risk_oos.validation_selection import TechnicalRiskValidationSelectionStatus


TECH_RISK_HOLDOUT_CONFIRMATION_ARTIFACT_V1 = "TECH_RISK_HOLDOUT_CONFIRMATION_ARTIFACT_V1"
TECH_RISK_HOLDOUT_CONFIRMATION_CRITERIA_V1 = "TECH_RISK_HOLDOUT_CONFIRMATION_CRITERIA_V1"


class TechnicalRiskHoldoutConfirmationError(Exception):
    """Raised when Technical Risk Holdout confirmation contracts are invalid."""


class TechnicalRiskHoldoutConfirmationStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONTAMINATION_DECLARED = "CONTAMINATION_DECLARED"


class TechnicalRiskHoldoutConfirmationReasonCode(StrEnum):
    HOLDOUT_EVIDENCE_CONFIRMED = "HOLDOUT_EVIDENCE_CONFIRMED"
    HOLDOUT_MONOTONICITY_CONCERN = "HOLDOUT_MONOTONICITY_CONCERN"
    HOLDOUT_COVERAGE_CONCERN = "HOLDOUT_COVERAGE_CONCERN"
    HOLDOUT_METHOD_REVIEW_REQUIRED = "HOLDOUT_METHOD_REVIEW_REQUIRED"
    HOLDOUT_NOT_CONFIRMED = "HOLDOUT_NOT_CONFIRMED"
    HOLDOUT_CONTAMINATION_DECLARED = "HOLDOUT_CONTAMINATION_DECLARED"


class TechnicalRiskHoldoutMonotonicityHandling(StrEnum):
    RETAIN_STRUCTURED_EVIDENCE = "RETAIN_STRUCTURED_EVIDENCE"
    REQUIRE_METHOD_REVIEW_ON_WARNING = "REQUIRE_METHOD_REVIEW_ON_WARNING"


class TechnicalRiskHoldoutCoverageHandling(StrEnum):
    RETAIN_COVERAGE_EVIDENCE = "RETAIN_COVERAGE_EVIDENCE"
    REQUIRE_METHOD_REVIEW_ON_EMPTY_BUCKET = "REQUIRE_METHOD_REVIEW_ON_EMPTY_BUCKET"


class TechnicalRiskHoldoutWarningHandling(StrEnum):
    RETAIN_METHOD_WARNINGS = "RETAIN_METHOD_WARNINGS"
    REQUIRE_EXPLICIT_REVIEW = "REQUIRE_EXPLICIT_REVIEW"


class TechnicalRiskHoldoutConsistencyRequirement(StrEnum):
    REQUIRE_VALIDATION_HOLDOUT_VERSION_CONTINUITY = "REQUIRE_VALIDATION_HOLDOUT_VERSION_CONTINUITY"


class TechnicalRiskHoldoutContaminationPolicy(StrEnum):
    ALLOW_GOVERNANCE_DECLARATION = "ALLOW_GOVERNANCE_DECLARATION"


@dataclass(frozen=True)
class TechnicalRiskHoldoutEvaluationReference:
    """Integrity echo for one frozen HOLDOUT candidate evaluation result."""

    holdout_dataset_id: str
    holdout_dataset_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    holdout_evaluation_id: str
    holdout_evaluation_checksum: str
    evaluated_split_roles: tuple[TechnicalRiskOOSSplitRole, ...]
    derived_evidence_version: str
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str

    def __post_init__(self):
        _require_text(self.holdout_dataset_id, "holdout_dataset_id")
        _require_text(self.holdout_dataset_checksum, "holdout_dataset_checksum")
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.candidate_version, "candidate_version")
        _require_text(self.candidate_structural_checksum, "candidate_structural_checksum")
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_version, "threshold_set_version")
        _require_text(self.threshold_set_checksum, "threshold_set_checksum")
        _require_text(self.holdout_evaluation_id, "holdout_evaluation_id")
        _require_text(self.holdout_evaluation_checksum, "holdout_evaluation_checksum")
        roles = _canonical_split_roles(self.evaluated_split_roles)
        if roles != (TechnicalRiskOOSSplitRole.HOLDOUT,):
            raise TechnicalRiskHoldoutConfirmationError("Holdout evaluation evidence must be HOLDOUT only.")
        object.__setattr__(self, "evaluated_split_roles", roles)
        _require_version(self.derived_evidence_version, TECH_RISK_DERIVED_EVIDENCE_V1, "derived_evidence_version")
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")

    @classmethod
    def from_evaluation_result(cls, evaluation_result: TechnicalRiskCandidateEvaluationResult) -> "TechnicalRiskHoldoutEvaluationReference":
        return cls(
            holdout_dataset_id=evaluation_result.dataset_id,
            holdout_dataset_checksum=evaluation_result.dataset_checksum,
            candidate_id=evaluation_result.candidate_id,
            candidate_version=evaluation_result.candidate_version,
            candidate_structural_checksum=evaluation_result.candidate_structural_checksum,
            threshold_set_id=evaluation_result.threshold_set_id,
            threshold_set_version=evaluation_result.threshold_set_version,
            threshold_set_checksum=evaluation_result.threshold_set_checksum,
            holdout_evaluation_id=evaluation_result.evaluation_id,
            holdout_evaluation_checksum=evaluation_result.evaluation_checksum,
            evaluated_split_roles=evaluation_result.evaluated_split_roles,
            derived_evidence_version=evaluation_result.derived_evidence_version,
            evaluator_version=evaluation_result.evaluator_version,
            metric_version=evaluation_result.metric_version,
            quantile_version=evaluation_result.quantile_version,
            numeric_context_version=evaluation_result.numeric_context_version,
        )


@dataclass(frozen=True)
class TechnicalRiskHoldoutConfirmationCriteria:
    """Frozen declarative methodology criteria for Holdout confirmation review."""

    criteria_id: str | None
    criteria_version: str
    monotonicity_handling: TechnicalRiskHoldoutMonotonicityHandling
    coverage_handling: TechnicalRiskHoldoutCoverageHandling
    methodology_warning_handling: TechnicalRiskHoldoutWarningHandling
    consistency_requirement: TechnicalRiskHoldoutConsistencyRequirement
    contamination_policy: TechnicalRiskHoldoutContaminationPolicy
    derived_evidence_version: str
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str
    criteria_checksum: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    human_rationale: str | None = None

    def __post_init__(self):
        _require_version(self.criteria_version, TECH_RISK_HOLDOUT_CONFIRMATION_CRITERIA_V1, "criteria_version")
        object.__setattr__(
            self,
            "monotonicity_handling",
            _coerce_enum(self.monotonicity_handling, TechnicalRiskHoldoutMonotonicityHandling, "monotonicity_handling"),
        )
        object.__setattr__(
            self,
            "coverage_handling",
            _coerce_enum(self.coverage_handling, TechnicalRiskHoldoutCoverageHandling, "coverage_handling"),
        )
        object.__setattr__(
            self,
            "methodology_warning_handling",
            _coerce_enum(self.methodology_warning_handling, TechnicalRiskHoldoutWarningHandling, "methodology_warning_handling"),
        )
        object.__setattr__(
            self,
            "consistency_requirement",
            _coerce_enum(self.consistency_requirement, TechnicalRiskHoldoutConsistencyRequirement, "consistency_requirement"),
        )
        object.__setattr__(
            self,
            "contamination_policy",
            _coerce_enum(self.contamination_policy, TechnicalRiskHoldoutContaminationPolicy, "contamination_policy"),
        )
        _require_version(self.derived_evidence_version, TECH_RISK_DERIVED_EVIDENCE_V1, "derived_evidence_version")
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        checksum = _criteria_checksum(self)
        identity = _stable_id("technical_risk_holdout_confirmation_criteria", {"criteria_checksum": checksum})
        if self.criteria_id is not None and self.criteria_id != identity:
            raise TechnicalRiskHoldoutConfirmationError("criteria_id mismatch.")
        if self.criteria_checksum is not None and self.criteria_checksum != checksum:
            raise TechnicalRiskHoldoutConfirmationError("criteria_checksum mismatch.")
        object.__setattr__(self, "criteria_id", identity)
        object.__setattr__(self, "criteria_checksum", checksum)


@dataclass(frozen=True)
class TechnicalRiskHoldoutConfirmationDecision:
    """Explicit methodology decision over frozen Holdout evidence."""

    confirmation_status: TechnicalRiskHoldoutConfirmationStatus
    confirmed_candidate_id: str
    confirmed_candidate_structural_checksum: str
    confirmed_threshold_set_id: str
    confirmed_threshold_set_checksum: str
    holdout_evaluation_id: str
    holdout_evaluation_checksum: str
    structured_confirmation_reason_codes: tuple[TechnicalRiskHoldoutConfirmationReasonCode, ...]
    approved_by: str | None = None
    approved_at: datetime | None = None
    human_rationale: str | None = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "confirmation_status",
            _coerce_enum(self.confirmation_status, TechnicalRiskHoldoutConfirmationStatus, "confirmation_status"),
        )
        _require_text(self.confirmed_candidate_id, "confirmed_candidate_id")
        _require_text(self.confirmed_candidate_structural_checksum, "confirmed_candidate_structural_checksum")
        _require_text(self.confirmed_threshold_set_id, "confirmed_threshold_set_id")
        _require_text(self.confirmed_threshold_set_checksum, "confirmed_threshold_set_checksum")
        _require_text(self.holdout_evaluation_id, "holdout_evaluation_id")
        _require_text(self.holdout_evaluation_checksum, "holdout_evaluation_checksum")
        reasons = _canonical_reason_codes(self.structured_confirmation_reason_codes)
        _validate_status_reason(self.confirmation_status, reasons)
        object.__setattr__(self, "structured_confirmation_reason_codes", reasons)


@dataclass(frozen=True)
class TechnicalRiskHoldoutConfirmationArtifact:
    """Frozen research confirmation evidence for the selected Technical Risk method."""

    confirmation_id: str | None
    confirmation_version: str
    validation_selection_id: str
    validation_selection_checksum: str
    selected_candidate_id: str
    selected_candidate_version: str
    selected_candidate_structural_checksum: str
    selected_threshold_set_id: str
    selected_threshold_set_version: str
    selected_threshold_set_checksum: str
    accepted_validation_evaluation_id: str
    accepted_validation_evaluation_checksum: str
    holdout_dataset_id: str
    holdout_dataset_checksum: str
    holdout_evaluation_id: str
    holdout_evaluation_checksum: str
    holdout_aggregate_metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...]
    holdout_monotonicity_results: tuple[TechnicalRiskMonotonicityResult, ...]
    confirmation_criteria_id: str
    confirmation_criteria_version: str
    confirmation_criteria_checksum: str
    confirmation_status: TechnicalRiskHoldoutConfirmationStatus
    structured_confirmation_reason_codes: tuple[TechnicalRiskHoldoutConfirmationReasonCode, ...]
    derived_evidence_version: str
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str
    confirmation_checksum: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    human_rationale: str | None = None

    def __post_init__(self):
        _require_version(self.confirmation_version, TECH_RISK_HOLDOUT_CONFIRMATION_ARTIFACT_V1, "confirmation_version")
        for field_name in (
            "validation_selection_id",
            "validation_selection_checksum",
            "selected_candidate_id",
            "selected_candidate_version",
            "selected_candidate_structural_checksum",
            "selected_threshold_set_id",
            "selected_threshold_set_version",
            "selected_threshold_set_checksum",
            "accepted_validation_evaluation_id",
            "accepted_validation_evaluation_checksum",
            "holdout_dataset_id",
            "holdout_dataset_checksum",
            "holdout_evaluation_id",
            "holdout_evaluation_checksum",
            "confirmation_criteria_id",
            "confirmation_criteria_checksum",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_version(self.confirmation_criteria_version, TECH_RISK_HOLDOUT_CONFIRMATION_CRITERIA_V1, "confirmation_criteria_version")
        object.__setattr__(
            self,
            "confirmation_status",
            _coerce_enum(self.confirmation_status, TechnicalRiskHoldoutConfirmationStatus, "confirmation_status"),
        )
        reasons = _canonical_reason_codes(self.structured_confirmation_reason_codes)
        _validate_status_reason(self.confirmation_status, reasons)
        object.__setattr__(self, "structured_confirmation_reason_codes", reasons)
        object.__setattr__(self, "holdout_aggregate_metrics", _canonical_metrics(self.holdout_aggregate_metrics))
        object.__setattr__(self, "holdout_monotonicity_results", _canonical_monotonicity(self.holdout_monotonicity_results))
        _require_version(self.derived_evidence_version, TECH_RISK_DERIVED_EVIDENCE_V1, "derived_evidence_version")
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        checksum = _confirmation_checksum(self)
        identity = _stable_id("technical_risk_holdout_confirmation", {"confirmation_checksum": checksum})
        if self.confirmation_id is not None and self.confirmation_id != identity:
            raise TechnicalRiskHoldoutConfirmationError("confirmation_id mismatch.")
        if self.confirmation_checksum is not None and self.confirmation_checksum != checksum:
            raise TechnicalRiskHoldoutConfirmationError("confirmation_checksum mismatch.")
        object.__setattr__(self, "confirmation_id", identity)
        object.__setattr__(self, "confirmation_checksum", checksum)

    @classmethod
    def from_holdout_contracts(
        cls,
        *,
        validation_selection: TechnicalRiskValidationSelectionArtifact,
        holdout_dataset: TechnicalRiskOOSDatasetResult,
        accepted_validation_evaluation: TechnicalRiskCandidateEvaluationResult,
        holdout_evaluation: TechnicalRiskCandidateEvaluationResult,
        holdout_reference: TechnicalRiskHoldoutEvaluationReference,
        confirmation_criteria: TechnicalRiskHoldoutConfirmationCriteria,
        confirmation_decision: TechnicalRiskHoldoutConfirmationDecision,
        confirmation_id: str | None = None,
        confirmation_version: str = TECH_RISK_HOLDOUT_CONFIRMATION_ARTIFACT_V1,
        confirmation_checksum: str | None = None,
    ) -> "TechnicalRiskHoldoutConfirmationArtifact":
        _validate_validation_selection(validation_selection, accepted_validation_evaluation)
        _validate_holdout_reference(holdout_reference, holdout_evaluation)
        _validate_holdout_evaluation(validation_selection, holdout_dataset, accepted_validation_evaluation, holdout_evaluation)
        _validate_confirmation_criteria(confirmation_criteria, accepted_validation_evaluation, holdout_evaluation)
        _validate_confirmation_decision(validation_selection, holdout_evaluation, confirmation_decision)
        return cls(
            confirmation_id=confirmation_id,
            confirmation_version=confirmation_version,
            validation_selection_id=validation_selection.selection_id,
            validation_selection_checksum=validation_selection.selection_checksum,
            selected_candidate_id=holdout_evaluation.candidate_id,
            selected_candidate_version=holdout_evaluation.candidate_version,
            selected_candidate_structural_checksum=holdout_evaluation.candidate_structural_checksum,
            selected_threshold_set_id=holdout_evaluation.threshold_set_id,
            selected_threshold_set_version=holdout_evaluation.threshold_set_version,
            selected_threshold_set_checksum=holdout_evaluation.threshold_set_checksum,
            accepted_validation_evaluation_id=accepted_validation_evaluation.evaluation_id,
            accepted_validation_evaluation_checksum=accepted_validation_evaluation.evaluation_checksum,
            holdout_dataset_id=holdout_dataset.dataset_id,
            holdout_dataset_checksum=holdout_dataset.dataset_checksum,
            holdout_evaluation_id=holdout_evaluation.evaluation_id,
            holdout_evaluation_checksum=holdout_evaluation.evaluation_checksum,
            holdout_aggregate_metrics=holdout_evaluation.aggregate_metrics,
            holdout_monotonicity_results=holdout_evaluation.monotonicity_results,
            confirmation_criteria_id=confirmation_criteria.criteria_id,
            confirmation_criteria_version=confirmation_criteria.criteria_version,
            confirmation_criteria_checksum=confirmation_criteria.criteria_checksum,
            confirmation_status=confirmation_decision.confirmation_status,
            structured_confirmation_reason_codes=confirmation_decision.structured_confirmation_reason_codes,
            derived_evidence_version=holdout_evaluation.derived_evidence_version,
            evaluator_version=holdout_evaluation.evaluator_version,
            metric_version=holdout_evaluation.metric_version,
            quantile_version=holdout_evaluation.quantile_version,
            numeric_context_version=holdout_evaluation.numeric_context_version,
            confirmation_checksum=confirmation_checksum,
            approved_by=confirmation_decision.approved_by,
            approved_at=confirmation_decision.approved_at,
            human_rationale=confirmation_decision.human_rationale,
        )


def _validate_validation_selection(
    validation_selection: TechnicalRiskValidationSelectionArtifact,
    accepted_validation_evaluation: TechnicalRiskCandidateEvaluationResult,
) -> None:
    if validation_selection.selection_status != TechnicalRiskValidationSelectionStatus.SELECTED:
        raise TechnicalRiskHoldoutConfirmationError("Holdout confirmation requires SELECTED Validation selection.")
    for field_name in (
        "selected_candidate_id",
        "selected_candidate_structural_checksum",
        "selected_threshold_set_id",
        "selected_threshold_set_checksum",
        "accepted_validation_evaluation_id",
        "accepted_validation_evaluation_checksum",
    ):
        _require_text(getattr(validation_selection, field_name), field_name)
    if accepted_validation_evaluation.evaluation_id != validation_selection.accepted_validation_evaluation_id:
        raise TechnicalRiskHoldoutConfirmationError("accepted Validation evaluation id mismatch.")
    if accepted_validation_evaluation.evaluation_checksum != validation_selection.accepted_validation_evaluation_checksum:
        raise TechnicalRiskHoldoutConfirmationError("accepted Validation evaluation checksum mismatch.")
    if accepted_validation_evaluation.candidate_id != validation_selection.selected_candidate_id:
        raise TechnicalRiskHoldoutConfirmationError("accepted Validation candidate mismatch.")
    if accepted_validation_evaluation.candidate_structural_checksum != validation_selection.selected_candidate_structural_checksum:
        raise TechnicalRiskHoldoutConfirmationError("accepted Validation candidate checksum mismatch.")
    if accepted_validation_evaluation.threshold_set_id != validation_selection.selected_threshold_set_id:
        raise TechnicalRiskHoldoutConfirmationError("accepted Validation threshold mismatch.")
    if accepted_validation_evaluation.threshold_set_checksum != validation_selection.selected_threshold_set_checksum:
        raise TechnicalRiskHoldoutConfirmationError("accepted Validation threshold checksum mismatch.")


def _validate_holdout_reference(
    holdout_reference: TechnicalRiskHoldoutEvaluationReference,
    holdout_evaluation: TechnicalRiskCandidateEvaluationResult,
) -> None:
    expected = TechnicalRiskHoldoutEvaluationReference.from_evaluation_result(holdout_evaluation)
    if holdout_reference != expected:
        raise TechnicalRiskHoldoutConfirmationError("Holdout evaluation reference echo mismatch.")


def _validate_holdout_evaluation(
    validation_selection: TechnicalRiskValidationSelectionArtifact,
    holdout_dataset: TechnicalRiskOOSDatasetResult,
    accepted_validation_evaluation: TechnicalRiskCandidateEvaluationResult,
    holdout_evaluation: TechnicalRiskCandidateEvaluationResult,
) -> None:
    if holdout_evaluation.dataset_id != holdout_dataset.dataset_id:
        raise TechnicalRiskHoldoutConfirmationError("Holdout dataset_id mismatch.")
    if holdout_evaluation.dataset_checksum != holdout_dataset.dataset_checksum:
        raise TechnicalRiskHoldoutConfirmationError("Holdout dataset_checksum mismatch.")
    if _canonical_split_roles(holdout_evaluation.evaluated_split_roles) != (TechnicalRiskOOSSplitRole.HOLDOUT,):
        raise TechnicalRiskHoldoutConfirmationError("Holdout evaluation evidence must be HOLDOUT only.")
    if holdout_evaluation.candidate_id != validation_selection.selected_candidate_id:
        raise TechnicalRiskHoldoutConfirmationError("Holdout candidate mismatch.")
    if holdout_evaluation.candidate_version != accepted_validation_evaluation.candidate_version:
        raise TechnicalRiskHoldoutConfirmationError("Holdout candidate_version mismatch.")
    if holdout_evaluation.candidate_structural_checksum != validation_selection.selected_candidate_structural_checksum:
        raise TechnicalRiskHoldoutConfirmationError("Holdout candidate checksum mismatch.")
    if holdout_evaluation.threshold_set_id != validation_selection.selected_threshold_set_id:
        raise TechnicalRiskHoldoutConfirmationError("Holdout threshold mismatch.")
    if holdout_evaluation.threshold_set_version != accepted_validation_evaluation.threshold_set_version:
        raise TechnicalRiskHoldoutConfirmationError("Holdout threshold_version mismatch.")
    if holdout_evaluation.threshold_set_checksum != validation_selection.selected_threshold_set_checksum:
        raise TechnicalRiskHoldoutConfirmationError("Holdout threshold checksum mismatch.")
    for field_name in (
        "derived_evidence_version",
        "evaluator_version",
        "metric_version",
        "quantile_version",
        "numeric_context_version",
    ):
        if getattr(holdout_evaluation, field_name) != getattr(accepted_validation_evaluation, field_name):
            raise TechnicalRiskHoldoutConfirmationError(f"Holdout {field_name} mismatch.")


def _validate_confirmation_criteria(
    criteria: TechnicalRiskHoldoutConfirmationCriteria,
    accepted_validation_evaluation: TechnicalRiskCandidateEvaluationResult,
    holdout_evaluation: TechnicalRiskCandidateEvaluationResult,
) -> None:
    for field_name in (
        "derived_evidence_version",
        "evaluator_version",
        "metric_version",
        "quantile_version",
        "numeric_context_version",
    ):
        if getattr(criteria, field_name) != getattr(accepted_validation_evaluation, field_name):
            raise TechnicalRiskHoldoutConfirmationError(f"Holdout criteria {field_name} mismatch.")
        if getattr(criteria, field_name) != getattr(holdout_evaluation, field_name):
            raise TechnicalRiskHoldoutConfirmationError(f"Holdout criteria {field_name} mismatch.")


def _validate_confirmation_decision(
    validation_selection: TechnicalRiskValidationSelectionArtifact,
    holdout_evaluation: TechnicalRiskCandidateEvaluationResult,
    decision: TechnicalRiskHoldoutConfirmationDecision,
) -> None:
    if decision.confirmed_candidate_id != validation_selection.selected_candidate_id:
        raise TechnicalRiskHoldoutConfirmationError("confirmation decision candidate mismatch.")
    if decision.confirmed_candidate_structural_checksum != validation_selection.selected_candidate_structural_checksum:
        raise TechnicalRiskHoldoutConfirmationError("confirmation decision candidate checksum mismatch.")
    if decision.confirmed_threshold_set_id != validation_selection.selected_threshold_set_id:
        raise TechnicalRiskHoldoutConfirmationError("confirmation decision threshold mismatch.")
    if decision.confirmed_threshold_set_checksum != validation_selection.selected_threshold_set_checksum:
        raise TechnicalRiskHoldoutConfirmationError("confirmation decision threshold checksum mismatch.")
    if decision.holdout_evaluation_id != holdout_evaluation.evaluation_id:
        raise TechnicalRiskHoldoutConfirmationError("confirmation decision Holdout evaluation id mismatch.")
    if decision.holdout_evaluation_checksum != holdout_evaluation.evaluation_checksum:
        raise TechnicalRiskHoldoutConfirmationError("confirmation decision Holdout evaluation checksum mismatch.")


def _validate_status_reason(
    status: TechnicalRiskHoldoutConfirmationStatus,
    reasons: tuple[TechnicalRiskHoldoutConfirmationReasonCode, ...],
) -> None:
    primary_reasons = {
        TechnicalRiskHoldoutConfirmationStatus.CONFIRMED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_EVIDENCE_CONFIRMED,
        TechnicalRiskHoldoutConfirmationStatus.NOT_CONFIRMED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_NOT_CONFIRMED,
        TechnicalRiskHoldoutConfirmationStatus.REVIEW_REQUIRED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_METHOD_REVIEW_REQUIRED,
        TechnicalRiskHoldoutConfirmationStatus.CONTAMINATION_DECLARED: TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_CONTAMINATION_DECLARED,
    }
    required = primary_reasons[status]
    if required not in reasons:
        raise TechnicalRiskHoldoutConfirmationError(f"{status.value} requires structured reason {required.value}.")
    prohibited = set(primary_reasons.values()) - {required}
    contradicted = prohibited.intersection(reasons)
    if contradicted:
        names = ", ".join(sorted(reason.value for reason in contradicted))
        raise TechnicalRiskHoldoutConfirmationError(f"{status.value} contains contradictory structured reason: {names}.")


def _canonical_metrics(
    metrics: tuple[TechnicalRiskSeverityMAEMetrics, ...],
) -> tuple[TechnicalRiskSeverityMAEMetrics, ...]:
    return tuple(metrics)


def _canonical_monotonicity(
    results: tuple[TechnicalRiskMonotonicityResult, ...],
) -> tuple[TechnicalRiskMonotonicityResult, ...]:
    return tuple(results)


def _canonical_split_roles(values: tuple[TechnicalRiskOOSSplitRole, ...]) -> tuple[TechnicalRiskOOSSplitRole, ...]:
    roles = tuple(value if isinstance(value, TechnicalRiskOOSSplitRole) else TechnicalRiskOOSSplitRole(value) for value in values)
    if len(set(roles)) != len(roles):
        raise TechnicalRiskHoldoutConfirmationError("Duplicate split role.")
    return tuple(sorted(roles, key=lambda role: role.value))


def _canonical_reason_codes(
    reason_codes: tuple[TechnicalRiskHoldoutConfirmationReasonCode, ...],
) -> tuple[TechnicalRiskHoldoutConfirmationReasonCode, ...]:
    try:
        normalized = tuple(
            code if isinstance(code, TechnicalRiskHoldoutConfirmationReasonCode) else TechnicalRiskHoldoutConfirmationReasonCode(code)
            for code in reason_codes
        )
    except ValueError as exc:
        raise TechnicalRiskHoldoutConfirmationError("Unsupported Holdout confirmation reason code.") from exc
    if not normalized:
        raise TechnicalRiskHoldoutConfirmationError("structured confirmation reason codes must not be empty.")
    if len(set(normalized)) != len(normalized):
        raise TechnicalRiskHoldoutConfirmationError("Duplicate Holdout confirmation reason code.")
    return tuple(sorted(normalized, key=lambda code: code.value))


def _criteria_checksum(criteria: TechnicalRiskHoldoutConfirmationCriteria) -> str:
    return _stable_hash(
        {
            "criteria_version": criteria.criteria_version,
            "monotonicity_handling": criteria.monotonicity_handling.value,
            "coverage_handling": criteria.coverage_handling.value,
            "methodology_warning_handling": criteria.methodology_warning_handling.value,
            "consistency_requirement": criteria.consistency_requirement.value,
            "contamination_policy": criteria.contamination_policy.value,
            "derived_evidence_version": criteria.derived_evidence_version,
            "evaluator_version": criteria.evaluator_version,
            "metric_version": criteria.metric_version,
            "quantile_version": criteria.quantile_version,
            "numeric_context_version": criteria.numeric_context_version,
        }
    )


def _confirmation_checksum(artifact: TechnicalRiskHoldoutConfirmationArtifact) -> str:
    return _stable_hash(
        {
            "confirmation_version": artifact.confirmation_version,
            "validation_selection_id": artifact.validation_selection_id,
            "validation_selection_checksum": artifact.validation_selection_checksum,
            "selected_candidate_id": artifact.selected_candidate_id,
            "selected_candidate_version": artifact.selected_candidate_version,
            "selected_candidate_structural_checksum": artifact.selected_candidate_structural_checksum,
            "selected_threshold_set_id": artifact.selected_threshold_set_id,
            "selected_threshold_set_version": artifact.selected_threshold_set_version,
            "selected_threshold_set_checksum": artifact.selected_threshold_set_checksum,
            "accepted_validation_evaluation_id": artifact.accepted_validation_evaluation_id,
            "accepted_validation_evaluation_checksum": artifact.accepted_validation_evaluation_checksum,
            "holdout_dataset_id": artifact.holdout_dataset_id,
            "holdout_dataset_checksum": artifact.holdout_dataset_checksum,
            "holdout_evaluation_id": artifact.holdout_evaluation_id,
            "holdout_evaluation_checksum": artifact.holdout_evaluation_checksum,
            "holdout_aggregate_metrics": [_metric_payload(metric) for metric in artifact.holdout_aggregate_metrics],
            "holdout_monotonicity_results": [_monotonicity_payload(result) for result in artifact.holdout_monotonicity_results],
            "confirmation_criteria_id": artifact.confirmation_criteria_id,
            "confirmation_criteria_version": artifact.confirmation_criteria_version,
            "confirmation_criteria_checksum": artifact.confirmation_criteria_checksum,
            "confirmation_status": artifact.confirmation_status.value,
            "structured_confirmation_reason_codes": [reason.value for reason in artifact.structured_confirmation_reason_codes],
            "derived_evidence_version": artifact.derived_evidence_version,
            "evaluator_version": artifact.evaluator_version,
            "metric_version": artifact.metric_version,
            "quantile_version": artifact.quantile_version,
            "numeric_context_version": artifact.numeric_context_version,
        }
    )


def _metric_payload(metric: TechnicalRiskSeverityMAEMetrics) -> dict[str, object]:
    return {
        "split_role": metric.split_role.value,
        "severity": metric.severity.value,
        "sample_count": metric.sample_count,
        "coverage_ratio": _decimal_payload(metric.coverage_ratio),
        "mae20_mean": _decimal_payload(metric.mae20_mean),
        "mae20_median": _decimal_payload(metric.mae20_median),
        "mae20_p25": _decimal_payload(metric.mae20_p25),
        "mae20_p75": _decimal_payload(metric.mae20_p75),
        "mae60_mean": _decimal_payload(metric.mae60_mean),
        "mae60_median": _decimal_payload(metric.mae60_median),
        "mae60_p25": _decimal_payload(metric.mae60_p25),
        "mae60_p75": _decimal_payload(metric.mae60_p75),
    }


def _monotonicity_payload(result: TechnicalRiskMonotonicityResult) -> dict[str, object]:
    return {
        "split_role": result.split_role.value,
        "horizon": result.horizon,
        "status": result.status.value,
        "low_median": _decimal_payload(result.low_median),
        "medium_median": _decimal_payload(result.medium_median),
        "high_median": _decimal_payload(result.high_median),
        "reason_code": result.reason_code,
    }


def _decimal_payload(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _coerce_enum(value: object, enum_type: type[StrEnum], field_name: str) -> StrEnum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        raise TechnicalRiskHoldoutConfirmationError(f"Unsupported {field_name}.") from exc


def _require_version(value: object, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskHoldoutConfirmationError(f"Unsupported {field_name}.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskHoldoutConfirmationError(f"{field_name} must be a non-empty string.")


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
