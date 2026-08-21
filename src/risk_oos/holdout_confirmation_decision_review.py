from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos.holdout_region_evidence_artifact import TechnicalRiskHoldoutRegionEvidenceArtifact
from risk_oos.holdout_region_evidence_artifact import load_holdout_region_evidence_artifact
from risk_oos.holdout_region_evidence_review import TechnicalRiskHoldoutRegionDistributionProfile
from risk_oos.holdout_region_evidence_review import TechnicalRiskHoldoutRegionEvidenceReviewPackage
from risk_oos.holdout_region_evidence_review import build_technical_risk_holdout_region_evidence_review_package_from_artifact


TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_PACKAGE_V1 = (
    "TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_PACKAGE_V1"
)
TECH_RISK_DESCRIPTIVE_HOLDOUT_CONFIRMATION_DECISION_REVIEW = (
    "DESCRIPTIVE_HOLDOUT_CONFIRMATION_DECISION_REVIEW"
)
TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEWER_V1 = (
    "TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEWER_V1"
)
TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_REQUIRES_DECISION = (
    "REVIEW_REQUIRED_NO_CONFIRMATION_DECISION"
)


class TechnicalRiskHoldoutConfirmationDecisionReviewError(Exception):
    """Raised when Holdout confirmation decision review cannot be built safely."""


@dataclass(frozen=True)
class TechnicalRiskHoldoutConfirmationComparison:
    """Descriptive comparison for one metric family."""

    validation: TechnicalRiskHoldoutRegionDistributionProfile
    holdout: TechnicalRiskHoldoutRegionDistributionProfile
    median_change: str | None
    range_change: tuple[str | None, str | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "range_change", tuple(self.range_change))
        if len(self.range_change) != 2:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("range_change must contain min and max movement.")


@dataclass(frozen=True)
class TechnicalRiskHoldoutConfirmationThresholdStabilityReview:
    """Region-level descriptive threshold pattern summary without ordering."""

    stable_pattern_count: int
    degraded_pattern_count: int
    unclear_pattern_count: int
    mae20_warning_count: int
    mae60_warning_count: int
    warning_axis_counts: Mapping[str, Mapping[str, Mapping[str, int]]]

    def __post_init__(self) -> None:
        total = self.stable_pattern_count + self.degraded_pattern_count + self.unclear_pattern_count
        if total != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("threshold stability counts mismatch.")
        object.__setattr__(self, "warning_axis_counts", _freeze_nested_axis_counts(self.warning_axis_counts))


@dataclass(frozen=True)
class TechnicalRiskHoldoutConfirmationDecisionReviewPackage:
    """In-memory descriptive Holdout decision review; not a confirmation artifact."""

    decision_review_id: str | None
    decision_review_version: str
    review_type: str
    reviewer_version: str
    holdout_evidence_artifact_id: str
    holdout_evidence_artifact_checksum: str
    holdout_evaluation_result_id: str
    holdout_evaluation_result_checksum: str
    evidence_review_id: str
    evidence_review_checksum: str
    candidate_id: str
    region_id: str
    threshold_count: int
    holdout_start_date: object
    holdout_end_date: object
    validation_monotonicity_counts: Mapping[str, Mapping[str, int]]
    holdout_monotonicity_counts: Mapping[str, Mapping[str, int]]
    monotonicity_shift: Mapping[str, int]
    separation_comparison: Mapping[str, TechnicalRiskHoldoutConfirmationComparison]
    coverage_comparison_by_severity: Mapping[str, TechnicalRiskHoldoutConfirmationComparison]
    sample_count_comparison_by_severity: Mapping[str, TechnicalRiskHoldoutConfirmationComparison]
    threshold_stability_review: TechnicalRiskHoldoutConfirmationThresholdStabilityReview
    market_regime_notes: tuple[str, ...]
    decision_boundary: str
    decision_state: TechnicalRiskHoldoutRegionConfirmationStatus | str
    production_policy_created: bool
    freeze_artifact_created: bool
    confirmation_decision_made: bool
    decision_review_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(
            self.decision_review_version,
            TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_PACKAGE_V1,
            "decision_review_version",
        )
        _require_version(
            self.review_type,
            TECH_RISK_DESCRIPTIVE_HOLDOUT_CONFIRMATION_DECISION_REVIEW,
            "review_type",
        )
        _require_version(self.reviewer_version, TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEWER_V1, "reviewer_version")
        _require_text(self.holdout_evidence_artifact_id, "holdout_evidence_artifact_id")
        _require_text(self.holdout_evidence_artifact_checksum, "holdout_evidence_artifact_checksum")
        _require_text(self.holdout_evaluation_result_id, "holdout_evaluation_result_id")
        _require_text(self.holdout_evaluation_result_checksum, "holdout_evaluation_result_checksum")
        _require_text(self.evidence_review_id, "evidence_review_id")
        _require_text(self.evidence_review_checksum, "evidence_review_checksum")
        _require_version(self.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
        _require_version(self.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "region_id")
        if self.threshold_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("threshold_count mismatch.")
        if self.holdout_start_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("holdout_start_date mismatch.")
        if self.holdout_end_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("holdout_end_date mismatch.")
        _require_version(
            self.decision_boundary,
            TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_REQUIRES_DECISION,
            "decision_boundary",
        )
        if TechnicalRiskHoldoutRegionConfirmationStatus(self.decision_state) != TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("decision_state must remain REVIEW_REQUIRED.")
        object.__setattr__(self, "decision_state", TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED)
        if self.production_policy_created:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("Decision review cannot create production policy.")
        if self.freeze_artifact_created:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("Decision review cannot create freeze artifact.")
        if self.confirmation_decision_made:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("Decision review cannot make confirmation decision.")
        object.__setattr__(self, "validation_monotonicity_counts", _freeze_nested_int_counts(self.validation_monotonicity_counts))
        object.__setattr__(self, "holdout_monotonicity_counts", _freeze_nested_int_counts(self.holdout_monotonicity_counts))
        object.__setattr__(self, "monotonicity_shift", MappingProxyType(dict(self.monotonicity_shift)))
        object.__setattr__(self, "separation_comparison", MappingProxyType(dict(self.separation_comparison)))
        object.__setattr__(self, "coverage_comparison_by_severity", MappingProxyType(dict(self.coverage_comparison_by_severity)))
        object.__setattr__(self, "sample_count_comparison_by_severity", MappingProxyType(dict(self.sample_count_comparison_by_severity)))
        object.__setattr__(self, "market_regime_notes", tuple(self.market_regime_notes))
        checksum = _decision_review_checksum(self)
        identity = _stable_id("technical_risk_holdout_confirmation_decision_review", {"decision_review_checksum": checksum})
        if self.decision_review_id is not None and self.decision_review_id != identity:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("decision_review_id mismatch.")
        if self.decision_review_checksum is not None and self.decision_review_checksum != checksum:
            raise TechnicalRiskHoldoutConfirmationDecisionReviewError("decision_review_checksum mismatch.")
        object.__setattr__(self, "decision_review_id", identity)
        object.__setattr__(self, "decision_review_checksum", checksum)


def build_technical_risk_holdout_confirmation_decision_review_package(
    artifact: TechnicalRiskHoldoutRegionEvidenceArtifact,
    *,
    evidence_review: TechnicalRiskHoldoutRegionEvidenceReviewPackage | None = None,
) -> TechnicalRiskHoldoutConfirmationDecisionReviewPackage:
    if not isinstance(artifact, TechnicalRiskHoldoutRegionEvidenceArtifact):
        raise TechnicalRiskHoldoutConfirmationDecisionReviewError("artifact type mismatch.")
    evidence_review = evidence_review or build_technical_risk_holdout_region_evidence_review_package_from_artifact(artifact)
    _validate_evidence_review(artifact, evidence_review)
    return TechnicalRiskHoldoutConfirmationDecisionReviewPackage(
        decision_review_id=None,
        decision_review_version=TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_PACKAGE_V1,
        review_type=TECH_RISK_DESCRIPTIVE_HOLDOUT_CONFIRMATION_DECISION_REVIEW,
        reviewer_version=TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEWER_V1,
        holdout_evidence_artifact_id=artifact.artifact_id,
        holdout_evidence_artifact_checksum=artifact.artifact_checksum,
        holdout_evaluation_result_id=artifact.holdout_evaluation_result.result_id,
        holdout_evaluation_result_checksum=artifact.holdout_evaluation_result.result_checksum,
        evidence_review_id=evidence_review.review_package_id,
        evidence_review_checksum=evidence_review.review_package_checksum,
        candidate_id=artifact.holdout_evaluation_result.candidate_id,
        region_id=artifact.holdout_evaluation_result.region_id,
        threshold_count=artifact.holdout_evaluation_result.threshold_count,
        holdout_start_date=artifact.holdout_evaluation_result.holdout_start_date,
        holdout_end_date=artifact.holdout_evaluation_result.holdout_end_date,
        validation_monotonicity_counts={
            "MAE20": dict(evidence_review.validation_summary.mae20_monotonicity_counts),
            "MAE60": dict(evidence_review.validation_summary.mae60_monotonicity_counts),
        },
        holdout_monotonicity_counts={
            "MAE20": dict(evidence_review.holdout_summary.mae20_monotonicity_counts),
            "MAE60": dict(evidence_review.holdout_summary.mae60_monotonicity_counts),
        },
        monotonicity_shift={
            "MAE20_PASS_SHIFT": evidence_review.shift_summary.mae20_pass_count_shift,
            "MAE60_PASS_SHIFT": evidence_review.shift_summary.mae60_pass_count_shift,
        },
        separation_comparison={
            "MAE20_HIGH_MINUS_LOW": _comparison(
                evidence_review.validation_summary.mae20_high_minus_low_distribution,
                evidence_review.holdout_summary.mae20_high_minus_low_distribution,
            ),
            "MAE60_HIGH_MINUS_LOW": _comparison(
                evidence_review.validation_summary.mae60_high_minus_low_distribution,
                evidence_review.holdout_summary.mae60_high_minus_low_distribution,
            ),
        },
        coverage_comparison_by_severity={
            severity: _comparison(
                evidence_review.validation_summary.coverage_distribution_by_severity[severity],
                evidence_review.holdout_summary.coverage_distribution_by_severity[severity],
            )
            for severity in ("LOW", "MEDIUM", "HIGH")
        },
        sample_count_comparison_by_severity={
            severity: _comparison(
                evidence_review.validation_summary.sample_count_distribution_by_severity[severity],
                evidence_review.holdout_summary.sample_count_distribution_by_severity[severity],
            )
            for severity in ("LOW", "MEDIUM", "HIGH")
        },
        threshold_stability_review=_threshold_stability_review(artifact, evidence_review),
        market_regime_notes=(
            "Validation period is 2022-2023; Holdout period is 2024-2025.",
            "Holdout monotonicity warnings are descriptive evidence of possible regime shift or weaker generalization.",
            "This package does not change methodology, candidate, region, or thresholds.",
        ),
        decision_boundary=TECH_RISK_HOLDOUT_CONFIRMATION_DECISION_REVIEW_REQUIRES_DECISION,
        decision_state=TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED,
        production_policy_created=False,
        freeze_artifact_created=False,
        confirmation_decision_made=False,
    )


def load_technical_risk_holdout_confirmation_decision_review_package(
    path: object,
) -> TechnicalRiskHoldoutConfirmationDecisionReviewPackage:
    return build_technical_risk_holdout_confirmation_decision_review_package(
        load_holdout_region_evidence_artifact(path)
    )


def _validate_evidence_review(
    artifact: TechnicalRiskHoldoutRegionEvidenceArtifact,
    review: TechnicalRiskHoldoutRegionEvidenceReviewPackage,
) -> None:
    if review.holdout_evaluation_result_id != artifact.holdout_evaluation_result.result_id:
        raise TechnicalRiskHoldoutConfirmationDecisionReviewError("evidence review result id mismatch.")
    if review.holdout_evaluation_result_checksum != artifact.holdout_evaluation_result.result_checksum:
        raise TechnicalRiskHoldoutConfirmationDecisionReviewError("evidence review result checksum mismatch.")
    if review.decision_state != TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED:
        raise TechnicalRiskHoldoutConfirmationDecisionReviewError("evidence review must remain REVIEW_REQUIRED.")


def _comparison(
    validation: TechnicalRiskHoldoutRegionDistributionProfile,
    holdout: TechnicalRiskHoldoutRegionDistributionProfile,
) -> TechnicalRiskHoldoutConfirmationComparison:
    return TechnicalRiskHoldoutConfirmationComparison(
        validation=validation,
        holdout=holdout,
        median_change=_optional_difference(holdout.median, validation.median),
        range_change=(
            _optional_difference(holdout.minimum, validation.minimum),
            _optional_difference(holdout.maximum, validation.maximum),
        ),
    )


def _threshold_stability_review(
    artifact: TechnicalRiskHoldoutRegionEvidenceArtifact,
    review: TechnicalRiskHoldoutRegionEvidenceReviewPackage,
) -> TechnicalRiskHoldoutConfirmationThresholdStabilityReview:
    stability = review.threshold_stability_summary
    degraded = len(
        {
            record.threshold_result.threshold_set_id
            for record in artifact.holdout_evaluation_result.threshold_records
            if record.threshold_result.mae20_monotonicity_status != "PASS"
            or record.threshold_result.mae60_monotonicity_status != "PASS"
        }
    )
    stable = TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT - degraded
    return TechnicalRiskHoldoutConfirmationThresholdStabilityReview(
        stable_pattern_count=stable,
        degraded_pattern_count=degraded,
        unclear_pattern_count=0,
        mae20_warning_count=stability.mae20_warning_threshold_count,
        mae60_warning_count=stability.mae60_warning_threshold_count,
        warning_axis_counts=stability.warning_axis_counts,
    )


def _optional_difference(left: str | None, right: str | None) -> str | None:
    if left is None or right is None:
        return None
    from decimal import Decimal

    return format((Decimal(left) - Decimal(right)).normalize(), "f")


def _freeze_nested_int_counts(value: Mapping[str, Mapping[str, int]]) -> Mapping[str, Mapping[str, int]]:
    return MappingProxyType({key: MappingProxyType(dict(counts)) for key, counts in value.items()})


def _freeze_nested_axis_counts(value: Mapping[str, Mapping[str, Mapping[str, int]]]) -> Mapping[str, Mapping[str, Mapping[str, int]]]:
    return MappingProxyType(
        {
            horizon: MappingProxyType(
                {
                    dimension: MappingProxyType(dict(counts))
                    for dimension, counts in dimensions.items()
                }
            )
            for horizon, dimensions in value.items()
        }
    )


def _decision_review_checksum(package: TechnicalRiskHoldoutConfirmationDecisionReviewPackage) -> str:
    return _stable_hash(
        {
            "decision_review_version": package.decision_review_version,
            "review_type": package.review_type,
            "reviewer_version": package.reviewer_version,
            "holdout_evidence_artifact_id": package.holdout_evidence_artifact_id,
            "holdout_evidence_artifact_checksum": package.holdout_evidence_artifact_checksum,
            "holdout_evaluation_result_id": package.holdout_evaluation_result_id,
            "holdout_evaluation_result_checksum": package.holdout_evaluation_result_checksum,
            "evidence_review_id": package.evidence_review_id,
            "evidence_review_checksum": package.evidence_review_checksum,
            "candidate_id": package.candidate_id,
            "region_id": package.region_id,
            "validation_monotonicity_counts": _thaw_nested_int_counts(package.validation_monotonicity_counts),
            "holdout_monotonicity_counts": _thaw_nested_int_counts(package.holdout_monotonicity_counts),
            "monotonicity_shift": dict(package.monotonicity_shift),
            "separation_comparison": {
                key: _comparison_payload(value)
                for key, value in package.separation_comparison.items()
            },
            "coverage_comparison_by_severity": {
                key: _comparison_payload(value)
                for key, value in package.coverage_comparison_by_severity.items()
            },
            "sample_count_comparison_by_severity": {
                key: _comparison_payload(value)
                for key, value in package.sample_count_comparison_by_severity.items()
            },
            "threshold_stability_review": {
                "stable_pattern_count": package.threshold_stability_review.stable_pattern_count,
                "degraded_pattern_count": package.threshold_stability_review.degraded_pattern_count,
                "unclear_pattern_count": package.threshold_stability_review.unclear_pattern_count,
                "mae20_warning_count": package.threshold_stability_review.mae20_warning_count,
                "mae60_warning_count": package.threshold_stability_review.mae60_warning_count,
                "warning_axis_counts": _thaw_axis_counts(package.threshold_stability_review.warning_axis_counts),
            },
            "market_regime_notes": package.market_regime_notes,
            "decision_boundary": package.decision_boundary,
            "decision_state": package.decision_state.value,
            "production_policy_created": package.production_policy_created,
            "freeze_artifact_created": package.freeze_artifact_created,
            "confirmation_decision_made": package.confirmation_decision_made,
        }
    )


def _comparison_payload(value: TechnicalRiskHoldoutConfirmationComparison) -> Mapping[str, object]:
    return {
        "validation": value.validation.__dict__,
        "holdout": value.holdout.__dict__,
        "median_change": value.median_change,
        "range_change": value.range_change,
    }


def _thaw_nested_int_counts(value: Mapping[str, Mapping[str, int]]) -> Mapping[str, Mapping[str, int]]:
    return {key: dict(counts) for key, counts in value.items()}


def _thaw_axis_counts(value: Mapping[str, Mapping[str, Mapping[str, int]]]) -> Mapping[str, Mapping[str, Mapping[str, int]]]:
    return {
        horizon: {
            dimension: dict(counts)
            for dimension, counts in dimensions.items()
        }
        for horizon, dimensions in value.items()
    }


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _require_version(actual: object, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskHoldoutConfirmationDecisionReviewError(f"{field_name} mismatch.")


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskHoldoutConfirmationDecisionReviewError(f"{field_name} must be a non-empty string.")
    return value
