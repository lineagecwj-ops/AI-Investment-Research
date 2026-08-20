from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1
from risk_oos.validation_selection_methodology import TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1


TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1 = "TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1"
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_LEVEL_V1 = "REGION_LEVEL_HOLDOUT_CONFIRMATION_ONLY"
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_POST_VALIDATION_METHOD_DECISION = "POST_VALIDATION_METHOD_DECISION"
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONFIRMED_NOT_APPROVAL = "CONFIRMED_DOES_NOT_APPROVE_PRODUCTION_POLICY"

TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID = (
    "technical_risk_validation_selection_decision_package_729bf5cad36a2aa5"
)
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM = (
    "d8c1000be8385a62346d5212b60327ed00ea10878ccce41e9a8db145dbe3fb20"
)
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID = "TECH_POLICY_CANDIDATE_C"
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID = "technical_risk_validation_robust_region_3df35aa1395ead5d"
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT = 69
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE = date(2024, 1, 1)
TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE = date(2025, 12, 31)


class TechnicalRiskHoldoutRegionConfirmationError(Exception):
    """Raised when Holdout region confirmation contracts fail closed."""


class TechnicalRiskHoldoutRegionConfirmationStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class TechnicalRiskHoldoutRegionEvidenceHorizon(StrEnum):
    MAE20 = "MAE20"
    MAE60 = "MAE60"


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionSeverityEvidence:
    """Future Holdout evidence for one severity bucket and one threshold set."""

    severity: TechnicalRiskCandidateSeverity | str
    coverage_ratio: Decimal | str
    sample_count: int
    mae20_mean: Decimal | str | None
    mae20_median: Decimal | str | None
    mae20_p25: Decimal | str | None
    mae20_p75: Decimal | str | None
    mae60_mean: Decimal | str | None
    mae60_median: Decimal | str | None
    mae60_p25: Decimal | str | None
    mae60_p75: Decimal | str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", TechnicalRiskCandidateSeverity(self.severity))
        if self.sample_count < 0:
            raise TechnicalRiskHoldoutRegionConfirmationError("sample_count cannot be negative.")
        object.__setattr__(self, "coverage_ratio", _canonical_decimal(self.coverage_ratio))
        for field_name in (
            "mae20_mean",
            "mae20_median",
            "mae20_p25",
            "mae20_p75",
            "mae60_mean",
            "mae60_median",
            "mae60_p25",
            "mae60_p75",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _canonical_decimal(value))


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionSeparationEvidence:
    """Future Holdout separation evidence for one MAE horizon."""

    horizon: TechnicalRiskHoldoutRegionEvidenceHorizon | str
    high_minus_low: Decimal | str | None
    high_minus_medium: Decimal | str | None
    medium_minus_low: Decimal | str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon", TechnicalRiskHoldoutRegionEvidenceHorizon(self.horizon))
        for field_name in ("high_minus_low", "high_minus_medium", "medium_minus_low"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _canonical_decimal(value))


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionThresholdResult:
    """Future Holdout confirmation evidence for one threshold inside the frozen region."""

    threshold_set_id: str
    threshold_checksum: str
    candidate_id: str
    region_id: str
    severity_evidence: tuple[TechnicalRiskHoldoutRegionSeverityEvidence, ...]
    mae20_monotonicity_status: str
    mae60_monotonicity_status: str
    mae20_separation_evidence: TechnicalRiskHoldoutRegionSeparationEvidence
    mae60_separation_evidence: TechnicalRiskHoldoutRegionSeparationEvidence
    confirmation_status: TechnicalRiskHoldoutRegionConfirmationStatus | str

    def __post_init__(self) -> None:
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_checksum, "threshold_checksum")
        _require_version(self.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
        _require_version(self.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "region_id")
        evidence = tuple(self.severity_evidence)
        if {item.severity for item in evidence} != set(TechnicalRiskCandidateSeverity):
            raise TechnicalRiskHoldoutRegionConfirmationError("severity_evidence must cover LOW, MEDIUM, and HIGH.")
        object.__setattr__(self, "severity_evidence", evidence)
        _require_text(self.mae20_monotonicity_status, "mae20_monotonicity_status")
        _require_text(self.mae60_monotonicity_status, "mae60_monotonicity_status")
        if self.mae20_separation_evidence.horizon != TechnicalRiskHoldoutRegionEvidenceHorizon.MAE20:
            raise TechnicalRiskHoldoutRegionConfirmationError("mae20 separation horizon mismatch.")
        if self.mae60_separation_evidence.horizon != TechnicalRiskHoldoutRegionEvidenceHorizon.MAE60:
            raise TechnicalRiskHoldoutRegionConfirmationError("mae60 separation horizon mismatch.")
        object.__setattr__(
            self,
            "confirmation_status",
            TechnicalRiskHoldoutRegionConfirmationStatus(self.confirmation_status),
        )


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionSummary:
    """Region-level confirmation summary without threshold preference semantics."""

    region_id: str
    candidate_id: str
    total_threshold_count: int
    confirmed_threshold_count: int
    not_confirmed_threshold_count: int
    review_required_threshold_count: int
    monotonicity_stability_summary: Mapping[str, int]
    separation_stability_summary: Mapping[str, int]
    coverage_stability_summary: Mapping[str, int]

    def __post_init__(self) -> None:
        _require_version(self.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "region_id")
        _require_version(self.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
        if self.total_threshold_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutRegionConfirmationError("total_threshold_count mismatch.")
        subtotal = (
            self.confirmed_threshold_count
            + self.not_confirmed_threshold_count
            + self.review_required_threshold_count
        )
        if subtotal != self.total_threshold_count:
            raise TechnicalRiskHoldoutRegionConfirmationError("region confirmation counts must sum to total_threshold_count.")
        object.__setattr__(self, "monotonicity_stability_summary", MappingProxyType(dict(self.monotonicity_stability_summary)))
        object.__setattr__(self, "separation_stability_summary", MappingProxyType(dict(self.separation_stability_summary)))
        object.__setattr__(self, "coverage_stability_summary", MappingProxyType(dict(self.coverage_stability_summary)))


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionConfirmationContract:
    """Frozen contract for future Candidate C robust-region Holdout confirmation."""

    contract_id: str | None
    contract_version: str
    contract_scope: str
    validation_evidence_artifact_id: str
    validation_evidence_artifact_checksum: str
    validation_selection_methodology_version: str
    validation_selection_decision_package_id: str
    validation_selection_decision_package_checksum: str
    candidate_id: str
    robust_region_id: str
    robust_region_threshold_count: int
    holdout_start_date: date
    holdout_end_date: date
    holdout_period_sealed_before_evaluation: bool
    region_confirmation_required: bool
    single_threshold_confirmation_allowed: bool
    numeric_acceptance_floor_policy: str
    future_numeric_criteria_decision: str
    confirmation_statuses: tuple[TechnicalRiskHoldoutRegionConfirmationStatus | str, ...]
    confirmed_status_policy: str
    contract_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(self.contract_version, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1, "contract_version")
        _require_version(self.contract_scope, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_LEVEL_V1, "contract_scope")
        _require_version(self.validation_evidence_artifact_id, TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID, "validation_evidence_artifact_id")
        _require_version(
            self.validation_evidence_artifact_checksum,
            TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
            "validation_evidence_artifact_checksum",
        )
        _require_version(
            self.validation_selection_methodology_version,
            TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
            "validation_selection_methodology_version",
        )
        _require_version(
            self.validation_selection_decision_package_id,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID,
            "validation_selection_decision_package_id",
        )
        _require_version(
            self.validation_selection_decision_package_checksum,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM,
            "validation_selection_decision_package_checksum",
        )
        _require_version(self.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
        _require_version(self.robust_region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "robust_region_id")
        if self.robust_region_threshold_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutRegionConfirmationError("robust_region_threshold_count mismatch.")
        if self.holdout_start_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE:
            raise TechnicalRiskHoldoutRegionConfirmationError("holdout_start_date mismatch.")
        if self.holdout_end_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE:
            raise TechnicalRiskHoldoutRegionConfirmationError("holdout_end_date mismatch.")
        if not self.holdout_period_sealed_before_evaluation:
            raise TechnicalRiskHoldoutRegionConfirmationError("Holdout period must be sealed before evaluation.")
        if not self.region_confirmation_required:
            raise TechnicalRiskHoldoutRegionConfirmationError("Region-level confirmation is required.")
        if self.single_threshold_confirmation_allowed:
            raise TechnicalRiskHoldoutRegionConfirmationError("Single-threshold-only confirmation is not allowed.")
        _require_version(self.numeric_acceptance_floor_policy, TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1, "numeric_acceptance_floor_policy")
        _require_version(
            self.future_numeric_criteria_decision,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_POST_VALIDATION_METHOD_DECISION,
            "future_numeric_criteria_decision",
        )
        statuses = tuple(TechnicalRiskHoldoutRegionConfirmationStatus(status) for status in self.confirmation_statuses)
        if statuses != tuple(TechnicalRiskHoldoutRegionConfirmationStatus):
            raise TechnicalRiskHoldoutRegionConfirmationError("confirmation_statuses mismatch.")
        object.__setattr__(self, "confirmation_statuses", statuses)
        _require_version(
            self.confirmed_status_policy,
            TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONFIRMED_NOT_APPROVAL,
            "confirmed_status_policy",
        )
        checksum = _contract_checksum(self)
        identity = _stable_id("technical_risk_holdout_region_confirmation_contract", {"contract_checksum": checksum})
        if self.contract_id is not None and self.contract_id != identity:
            raise TechnicalRiskHoldoutRegionConfirmationError("contract_id mismatch.")
        if self.contract_checksum is not None and self.contract_checksum != checksum:
            raise TechnicalRiskHoldoutRegionConfirmationError("contract_checksum mismatch.")
        object.__setattr__(self, "contract_id", identity)
        object.__setattr__(self, "contract_checksum", checksum)


def build_technical_risk_v1_holdout_region_confirmation_contract() -> TechnicalRiskHoldoutRegionConfirmationContract:
    return TechnicalRiskHoldoutRegionConfirmationContract(
        contract_id=None,
        contract_version=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONTRACT_V1,
        contract_scope=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_LEVEL_V1,
        validation_evidence_artifact_id=TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID,
        validation_evidence_artifact_checksum=TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
        validation_selection_methodology_version=TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
        validation_selection_decision_package_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_ID,
        validation_selection_decision_package_checksum=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_DECISION_PACKAGE_CHECKSUM,
        candidate_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID,
        robust_region_id=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID,
        robust_region_threshold_count=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT,
        holdout_start_date=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE,
        holdout_end_date=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE,
        holdout_period_sealed_before_evaluation=True,
        region_confirmation_required=True,
        single_threshold_confirmation_allowed=False,
        numeric_acceptance_floor_policy=TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1,
        future_numeric_criteria_decision=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_POST_VALIDATION_METHOD_DECISION,
        confirmation_statuses=tuple(TechnicalRiskHoldoutRegionConfirmationStatus),
        confirmed_status_policy=TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CONFIRMED_NOT_APPROVAL,
    )


def _contract_checksum(contract: TechnicalRiskHoldoutRegionConfirmationContract) -> str:
    return _stable_hash(
        {
            "contract_version": contract.contract_version,
            "contract_scope": contract.contract_scope,
            "validation_evidence_artifact_id": contract.validation_evidence_artifact_id,
            "validation_evidence_artifact_checksum": contract.validation_evidence_artifact_checksum,
            "validation_selection_methodology_version": contract.validation_selection_methodology_version,
            "validation_selection_decision_package_id": contract.validation_selection_decision_package_id,
            "validation_selection_decision_package_checksum": contract.validation_selection_decision_package_checksum,
            "candidate_id": contract.candidate_id,
            "robust_region_id": contract.robust_region_id,
            "robust_region_threshold_count": contract.robust_region_threshold_count,
            "holdout_start_date": contract.holdout_start_date.isoformat(),
            "holdout_end_date": contract.holdout_end_date.isoformat(),
            "holdout_period_sealed_before_evaluation": contract.holdout_period_sealed_before_evaluation,
            "region_confirmation_required": contract.region_confirmation_required,
            "single_threshold_confirmation_allowed": contract.single_threshold_confirmation_allowed,
            "numeric_acceptance_floor_policy": contract.numeric_acceptance_floor_policy,
            "future_numeric_criteria_decision": contract.future_numeric_criteria_decision,
            "confirmation_statuses": tuple(status.value for status in contract.confirmation_statuses),
            "confirmed_status_policy": contract.confirmed_status_policy,
        }
    )


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _canonical_decimal(value: Decimal | str) -> Decimal:
    if isinstance(value, bool):
        raise TechnicalRiskHoldoutRegionConfirmationError("Decimal values must not be bool.")
    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite():
        raise TechnicalRiskHoldoutRegionConfirmationError("Decimal values must be finite.")
    return decimal_value


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskHoldoutRegionConfirmationError(f"{field_name} must be a non-empty string.")


def _require_version(value: str, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskHoldoutRegionConfirmationError(f"{field_name} mismatch.")
