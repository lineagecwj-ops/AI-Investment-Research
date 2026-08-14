from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json

from risk_oos.holdout_confirmation import TechnicalRiskHoldoutConfirmationArtifact
from risk_oos.holdout_confirmation import TechnicalRiskHoldoutConfirmationReasonCode
from risk_oos.holdout_confirmation import TechnicalRiskHoldoutConfirmationStatus
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateSpec
from risk_oos.rule_candidates import TechnicalRiskThresholdSet
from risk_oos.validation_selection import TechnicalRiskValidationSelectionArtifact
from risk_oos.validation_selection import TechnicalRiskValidationSelectionStatus


TECH_RISK_POLICY_FREEZE_ARTIFACT_V1 = "TECH_RISK_POLICY_FREEZE_ARTIFACT_V1"


class TechnicalRiskPolicyFreezeError(Exception):
    """Raised when a Technical Risk research policy freeze cannot be trusted."""


class TechnicalRiskPolicyFreezeStatus(StrEnum):
    FROZEN = "FROZEN"


class TechnicalRiskPolicyFreezeReasonCode(StrEnum):
    RESEARCH_POLICY_FROZEN = "RESEARCH_POLICY_FROZEN"


@dataclass(frozen=True)
class TechnicalRiskPolicyFreezeArtifact:
    """Successful research policy freeze evidence for one confirmed Technical Risk methodology."""

    freeze_id: str | None
    freeze_version: str
    freeze_checksum: str | None
    technical_policy_version: str
    validation_selection_id: str
    validation_selection_checksum: str
    holdout_confirmation_id: str
    holdout_confirmation_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    accepted_validation_evaluation_id: str
    accepted_validation_evaluation_checksum: str
    holdout_evaluation_id: str
    holdout_evaluation_checksum: str
    derived_evidence_version: str
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str
    freeze_status: TechnicalRiskPolicyFreezeStatus
    structured_freeze_reason_codes: tuple[TechnicalRiskPolicyFreezeReasonCode, ...]
    approved_by: str | None = None
    approved_at: datetime | None = None
    human_rationale: str | None = None

    def __post_init__(self):
        _require_version(self.freeze_version, TECH_RISK_POLICY_FREEZE_ARTIFACT_V1, "freeze_version")
        _require_text(self.technical_policy_version, "technical_policy_version")
        for field_name in (
            "validation_selection_id",
            "validation_selection_checksum",
            "holdout_confirmation_id",
            "holdout_confirmation_checksum",
            "candidate_id",
            "candidate_version",
            "candidate_structural_checksum",
            "threshold_set_id",
            "threshold_set_version",
            "threshold_set_checksum",
            "accepted_validation_evaluation_id",
            "accepted_validation_evaluation_checksum",
            "holdout_evaluation_id",
            "holdout_evaluation_checksum",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_text(self.derived_evidence_version, "derived_evidence_version")
        _require_text(self.evaluator_version, "evaluator_version")
        _require_text(self.metric_version, "metric_version")
        _require_text(self.quantile_version, "quantile_version")
        _require_text(self.numeric_context_version, "numeric_context_version")
        object.__setattr__(
            self,
            "freeze_status",
            _coerce_enum(self.freeze_status, TechnicalRiskPolicyFreezeStatus, "freeze_status"),
        )
        if self.freeze_status != TechnicalRiskPolicyFreezeStatus.FROZEN:
            raise TechnicalRiskPolicyFreezeError("Research policy freeze artifact only supports FROZEN status.")
        reasons = _canonical_freeze_reason_codes(self.structured_freeze_reason_codes)
        if TechnicalRiskPolicyFreezeReasonCode.RESEARCH_POLICY_FROZEN not in reasons:
            raise TechnicalRiskPolicyFreezeError("FROZEN requires structured reason RESEARCH_POLICY_FROZEN.")
        object.__setattr__(self, "structured_freeze_reason_codes", reasons)
        checksum = _freeze_checksum(self)
        identity = _stable_id("technical_risk_policy_freeze", {"freeze_checksum": checksum})
        if self.freeze_id is not None and self.freeze_id != identity:
            raise TechnicalRiskPolicyFreezeError("freeze_id mismatch.")
        if self.freeze_checksum is not None and self.freeze_checksum != checksum:
            raise TechnicalRiskPolicyFreezeError("freeze_checksum mismatch.")
        object.__setattr__(self, "freeze_id", identity)
        object.__setattr__(self, "freeze_checksum", checksum)

    @classmethod
    def from_research_chain(
        cls,
        *,
        validation_selection: TechnicalRiskValidationSelectionArtifact,
        holdout_confirmation: TechnicalRiskHoldoutConfirmationArtifact,
        candidate: TechnicalRiskRuleCandidateSpec,
        threshold_set: TechnicalRiskThresholdSet,
        technical_policy_version: str,
        structured_freeze_reason_codes: tuple[TechnicalRiskPolicyFreezeReasonCode, ...] = (
            TechnicalRiskPolicyFreezeReasonCode.RESEARCH_POLICY_FROZEN,
        ),
        freeze_id: str | None = None,
        freeze_version: str = TECH_RISK_POLICY_FREEZE_ARTIFACT_V1,
        freeze_checksum: str | None = None,
        approved_by: str | None = None,
        approved_at: datetime | None = None,
        human_rationale: str | None = None,
    ) -> "TechnicalRiskPolicyFreezeArtifact":
        _validate_freeze_eligibility(validation_selection, holdout_confirmation)
        _validate_validation_holdout_chain(validation_selection, holdout_confirmation)
        _validate_candidate(candidate, validation_selection, holdout_confirmation)
        _validate_threshold(threshold_set, validation_selection, holdout_confirmation)
        return cls(
            freeze_id=freeze_id,
            freeze_version=freeze_version,
            freeze_checksum=freeze_checksum,
            technical_policy_version=technical_policy_version,
            validation_selection_id=validation_selection.selection_id,
            validation_selection_checksum=validation_selection.selection_checksum,
            holdout_confirmation_id=holdout_confirmation.confirmation_id,
            holdout_confirmation_checksum=holdout_confirmation.confirmation_checksum,
            candidate_id=candidate.policy_candidate_id,
            candidate_version=candidate.candidate_version,
            candidate_structural_checksum=candidate.candidate_structural_checksum,
            threshold_set_id=threshold_set.threshold_set_id,
            threshold_set_version=threshold_set.threshold_set_version,
            threshold_set_checksum=threshold_set.threshold_set_checksum,
            accepted_validation_evaluation_id=holdout_confirmation.accepted_validation_evaluation_id,
            accepted_validation_evaluation_checksum=holdout_confirmation.accepted_validation_evaluation_checksum,
            holdout_evaluation_id=holdout_confirmation.holdout_evaluation_id,
            holdout_evaluation_checksum=holdout_confirmation.holdout_evaluation_checksum,
            derived_evidence_version=holdout_confirmation.derived_evidence_version,
            evaluator_version=holdout_confirmation.evaluator_version,
            metric_version=holdout_confirmation.metric_version,
            quantile_version=holdout_confirmation.quantile_version,
            numeric_context_version=holdout_confirmation.numeric_context_version,
            freeze_status=TechnicalRiskPolicyFreezeStatus.FROZEN,
            structured_freeze_reason_codes=structured_freeze_reason_codes,
            approved_by=approved_by,
            approved_at=approved_at,
            human_rationale=human_rationale,
        )


def _validate_freeze_eligibility(
    validation_selection: TechnicalRiskValidationSelectionArtifact,
    holdout_confirmation: TechnicalRiskHoldoutConfirmationArtifact,
) -> None:
    if validation_selection.selection_status != TechnicalRiskValidationSelectionStatus.SELECTED:
        raise TechnicalRiskPolicyFreezeError("Research policy freeze requires SELECTED Validation selection.")
    for field_name in (
        "selected_candidate_id",
        "selected_candidate_structural_checksum",
        "selected_threshold_set_id",
        "selected_threshold_set_checksum",
        "accepted_validation_evaluation_id",
        "accepted_validation_evaluation_checksum",
    ):
        _require_text(getattr(validation_selection, field_name), field_name)
    if holdout_confirmation.confirmation_status != TechnicalRiskHoldoutConfirmationStatus.CONFIRMED:
        raise TechnicalRiskPolicyFreezeError("Research policy freeze requires CONFIRMED Holdout confirmation.")
    if TechnicalRiskHoldoutConfirmationReasonCode.HOLDOUT_EVIDENCE_CONFIRMED not in holdout_confirmation.structured_confirmation_reason_codes:
        raise TechnicalRiskPolicyFreezeError("CONFIRMED Holdout confirmation requires HOLDOUT_EVIDENCE_CONFIRMED.")


def _validate_validation_holdout_chain(
    validation_selection: TechnicalRiskValidationSelectionArtifact,
    holdout_confirmation: TechnicalRiskHoldoutConfirmationArtifact,
) -> None:
    if holdout_confirmation.validation_selection_id != validation_selection.selection_id:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation validation_selection_id mismatch.")
    if holdout_confirmation.validation_selection_checksum != validation_selection.selection_checksum:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation validation_selection_checksum mismatch.")
    if holdout_confirmation.selected_candidate_id != validation_selection.selected_candidate_id:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation candidate mismatch.")
    if holdout_confirmation.selected_candidate_structural_checksum != validation_selection.selected_candidate_structural_checksum:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation candidate checksum mismatch.")
    if holdout_confirmation.selected_threshold_set_id != validation_selection.selected_threshold_set_id:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation threshold mismatch.")
    if holdout_confirmation.selected_threshold_set_checksum != validation_selection.selected_threshold_set_checksum:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation threshold checksum mismatch.")
    if holdout_confirmation.accepted_validation_evaluation_id != validation_selection.accepted_validation_evaluation_id:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation accepted Validation evaluation id mismatch.")
    if holdout_confirmation.accepted_validation_evaluation_checksum != validation_selection.accepted_validation_evaluation_checksum:
        raise TechnicalRiskPolicyFreezeError("Holdout confirmation accepted Validation evaluation checksum mismatch.")
    for field_name in ("evaluator_version", "metric_version", "quantile_version", "numeric_context_version"):
        if getattr(holdout_confirmation, field_name) != getattr(validation_selection, field_name):
            raise TechnicalRiskPolicyFreezeError(f"Holdout confirmation {field_name} mismatch.")
    _require_text(holdout_confirmation.holdout_evaluation_id, "holdout_evaluation_id")
    _require_text(holdout_confirmation.holdout_evaluation_checksum, "holdout_evaluation_checksum")


def _validate_candidate(
    candidate: TechnicalRiskRuleCandidateSpec,
    validation_selection: TechnicalRiskValidationSelectionArtifact,
    holdout_confirmation: TechnicalRiskHoldoutConfirmationArtifact,
) -> None:
    if candidate.policy_candidate_id != validation_selection.selected_candidate_id:
        raise TechnicalRiskPolicyFreezeError("candidate id mismatch.")
    if candidate.policy_candidate_id != holdout_confirmation.selected_candidate_id:
        raise TechnicalRiskPolicyFreezeError("candidate id mismatch.")
    if candidate.candidate_version != holdout_confirmation.selected_candidate_version:
        raise TechnicalRiskPolicyFreezeError("candidate version mismatch.")
    if candidate.candidate_structural_checksum != validation_selection.selected_candidate_structural_checksum:
        raise TechnicalRiskPolicyFreezeError("candidate structural checksum mismatch.")
    if candidate.candidate_structural_checksum != holdout_confirmation.selected_candidate_structural_checksum:
        raise TechnicalRiskPolicyFreezeError("candidate structural checksum mismatch.")
    if candidate.derived_evidence_version != holdout_confirmation.derived_evidence_version:
        raise TechnicalRiskPolicyFreezeError("candidate derived_evidence_version mismatch.")


def _validate_threshold(
    threshold_set: TechnicalRiskThresholdSet,
    validation_selection: TechnicalRiskValidationSelectionArtifact,
    holdout_confirmation: TechnicalRiskHoldoutConfirmationArtifact,
) -> None:
    if threshold_set.threshold_set_id != validation_selection.selected_threshold_set_id:
        raise TechnicalRiskPolicyFreezeError("threshold id mismatch.")
    if threshold_set.threshold_set_id != holdout_confirmation.selected_threshold_set_id:
        raise TechnicalRiskPolicyFreezeError("threshold id mismatch.")
    if threshold_set.threshold_set_version != holdout_confirmation.selected_threshold_set_version:
        raise TechnicalRiskPolicyFreezeError("threshold version mismatch.")
    if threshold_set.threshold_set_checksum != validation_selection.selected_threshold_set_checksum:
        raise TechnicalRiskPolicyFreezeError("threshold checksum mismatch.")
    if threshold_set.threshold_set_checksum != holdout_confirmation.selected_threshold_set_checksum:
        raise TechnicalRiskPolicyFreezeError("threshold checksum mismatch.")


def _canonical_freeze_reason_codes(
    reason_codes: tuple[TechnicalRiskPolicyFreezeReasonCode, ...],
) -> tuple[TechnicalRiskPolicyFreezeReasonCode, ...]:
    try:
        normalized = tuple(
            code if isinstance(code, TechnicalRiskPolicyFreezeReasonCode) else TechnicalRiskPolicyFreezeReasonCode(code)
            for code in reason_codes
        )
    except ValueError as exc:
        raise TechnicalRiskPolicyFreezeError("Unsupported research policy freeze reason code.") from exc
    if not normalized:
        raise TechnicalRiskPolicyFreezeError("structured freeze reason codes must not be empty.")
    if len(set(normalized)) != len(normalized):
        raise TechnicalRiskPolicyFreezeError("Duplicate research policy freeze reason code.")
    return tuple(sorted(normalized, key=lambda code: code.value))


def _freeze_checksum(artifact: TechnicalRiskPolicyFreezeArtifact) -> str:
    return _stable_hash(
        {
            "freeze_version": artifact.freeze_version,
            "technical_policy_version": artifact.technical_policy_version,
            "validation_selection_id": artifact.validation_selection_id,
            "validation_selection_checksum": artifact.validation_selection_checksum,
            "holdout_confirmation_id": artifact.holdout_confirmation_id,
            "holdout_confirmation_checksum": artifact.holdout_confirmation_checksum,
            "candidate_id": artifact.candidate_id,
            "candidate_version": artifact.candidate_version,
            "candidate_structural_checksum": artifact.candidate_structural_checksum,
            "threshold_set_id": artifact.threshold_set_id,
            "threshold_set_version": artifact.threshold_set_version,
            "threshold_set_checksum": artifact.threshold_set_checksum,
            "accepted_validation_evaluation_id": artifact.accepted_validation_evaluation_id,
            "accepted_validation_evaluation_checksum": artifact.accepted_validation_evaluation_checksum,
            "holdout_evaluation_id": artifact.holdout_evaluation_id,
            "holdout_evaluation_checksum": artifact.holdout_evaluation_checksum,
            "derived_evidence_version": artifact.derived_evidence_version,
            "evaluator_version": artifact.evaluator_version,
            "metric_version": artifact.metric_version,
            "quantile_version": artifact.quantile_version,
            "numeric_context_version": artifact.numeric_context_version,
            "freeze_status": artifact.freeze_status.value,
            "structured_freeze_reason_codes": [reason.value for reason in artifact.structured_freeze_reason_codes],
        }
    )


def _coerce_enum(value: object, enum_type: type[StrEnum], field_name: str) -> StrEnum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        raise TechnicalRiskPolicyFreezeError(f"Unsupported {field_name}.") from exc


def _require_version(value: object, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskPolicyFreezeError(f"Unsupported {field_name}.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskPolicyFreezeError(f"{field_name} must be a non-empty string.")


def _stable_id(prefix: str, payload: dict[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
