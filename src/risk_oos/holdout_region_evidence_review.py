from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT
from risk_oos.holdout_region_confirmation import TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE
from risk_oos.holdout_region_confirmation import TechnicalRiskHoldoutRegionConfirmationStatus
from risk_oos.holdout_region_evaluation import TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1
from risk_oos.holdout_region_evaluation import TechnicalRiskHoldoutRegionEvaluationResult
from risk_oos.holdout_region_evaluation import TechnicalRiskHoldoutRegionThresholdEvaluationRecord
from risk_oos.holdout_region_evidence_artifact import TechnicalRiskHoldoutRegionEvidenceArtifact
from risk_oos.holdout_region_evidence_artifact import load_holdout_region_evidence_artifact
from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.rule_candidates import TechnicalRiskThresholdDimensionId
from risk_oos.threshold_axis_set import materialize_technical_risk_v1_threshold_grid
from risk_oos.validation_candidate_evaluation import TechnicalRiskValidationCandidateEvaluationRecord
from risk_oos.validation_evidence_artifact import TechnicalRiskValidationEvidenceArtifact
from risk_oos.validation_evidence_artifact import load_validation_evidence_artifact
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1


TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEW_PACKAGE_V1 = (
    "TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEW_PACKAGE_V1"
)
TECH_RISK_DESCRIPTIVE_HOLDOUT_REGION_EVIDENCE_REVIEW = (
    "DESCRIPTIVE_HOLDOUT_REGION_EVIDENCE_REVIEW"
)
TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEWER_V1 = (
    "TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEWER_V1"
)
TECH_RISK_HOLDOUT_REGION_REVIEW_REQUIRES_POST_REVIEW_DECISION = (
    "REVIEW_REQUIRED_PENDING_POST_HOLDOUT_METHOD_DECISION"
)

_THRESHOLD_DIMENSION_ORDER = (
    TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF,
)


class TechnicalRiskHoldoutRegionEvidenceReviewError(Exception):
    """Raised when Holdout region evidence review cannot be built safely."""


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionDistributionProfile:
    """Small descriptive distribution profile without acceptance semantics."""

    count: int
    minimum: str | None
    median: str | None
    maximum: str | None

    def __post_init__(self) -> None:
        if self.count < 0:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("count cannot be negative.")


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionPeriodEvidenceSummary:
    """One period summary for the frozen Candidate C robust region."""

    period_label: str
    split_role: TechnicalRiskOOSSplitRole | str
    row_count: int
    evaluation_count: int
    mae20_monotonicity_counts: Mapping[str, int]
    mae60_monotonicity_counts: Mapping[str, int]
    mae20_high_minus_low_distribution: TechnicalRiskHoldoutRegionDistributionProfile
    mae60_high_minus_low_distribution: TechnicalRiskHoldoutRegionDistributionProfile
    coverage_distribution_by_severity: Mapping[str, TechnicalRiskHoldoutRegionDistributionProfile]
    sample_count_distribution_by_severity: Mapping[str, TechnicalRiskHoldoutRegionDistributionProfile]

    def __post_init__(self) -> None:
        _require_text(self.period_label, "period_label")
        object.__setattr__(self, "split_role", TechnicalRiskOOSSplitRole(self.split_role))
        if self.row_count <= 0:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("row_count must be positive.")
        if self.evaluation_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("evaluation_count mismatch.")
        object.__setattr__(self, "mae20_monotonicity_counts", MappingProxyType(dict(self.mae20_monotonicity_counts)))
        object.__setattr__(self, "mae60_monotonicity_counts", MappingProxyType(dict(self.mae60_monotonicity_counts)))
        object.__setattr__(
            self,
            "coverage_distribution_by_severity",
            MappingProxyType(dict(self.coverage_distribution_by_severity)),
        )
        object.__setattr__(
            self,
            "sample_count_distribution_by_severity",
            MappingProxyType(dict(self.sample_count_distribution_by_severity)),
        )


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionEvidenceShiftSummary:
    """Descriptive Validation to Holdout movement for the frozen region."""

    mae20_pass_count_shift: int
    mae60_pass_count_shift: int
    mae20_high_minus_low_median_shift: str | None
    mae60_high_minus_low_median_shift: str | None
    coverage_shift_by_severity: Mapping[str, str | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "coverage_shift_by_severity", MappingProxyType(dict(self.coverage_shift_by_severity)))


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionThresholdStabilitySummary:
    """Threshold-level descriptive stability without preference ordering."""

    total_threshold_count: int
    mae20_warning_threshold_count: int
    mae60_warning_threshold_count: int
    region_wide_degradation: bool
    partial_degradation: bool
    warning_axis_counts: Mapping[str, Mapping[str, Mapping[str, int]]]

    def __post_init__(self) -> None:
        if self.total_threshold_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("total_threshold_count mismatch.")
        object.__setattr__(self, "warning_axis_counts", _freeze_nested_axis_counts(self.warning_axis_counts))


@dataclass(frozen=True)
class TechnicalRiskHoldoutRegionEvidenceReviewPackage:
    """In-memory descriptive review package for Holdout region evidence."""

    review_package_id: str | None
    review_package_version: str
    review_type: str
    reviewer_version: str
    validation_evidence_artifact_id: str
    validation_evidence_artifact_checksum: str
    validation_selection_methodology_version: str
    holdout_evaluation_result_id: str
    holdout_evaluation_result_checksum: str
    candidate_id: str
    region_id: str
    threshold_count: int
    holdout_start_date: object
    holdout_end_date: object
    validation_period_label: str
    holdout_period_label: str
    validation_summary: TechnicalRiskHoldoutRegionPeriodEvidenceSummary
    holdout_summary: TechnicalRiskHoldoutRegionPeriodEvidenceSummary
    shift_summary: TechnicalRiskHoldoutRegionEvidenceShiftSummary
    threshold_stability_summary: TechnicalRiskHoldoutRegionThresholdStabilitySummary
    market_regime_notes: tuple[str, ...]
    decision_state: TechnicalRiskHoldoutRegionConfirmationStatus | str
    production_policy_created: bool
    artifact_created: bool
    review_package_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(
            self.review_package_version,
            TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEW_PACKAGE_V1,
            "review_package_version",
        )
        _require_version(
            self.review_type,
            TECH_RISK_DESCRIPTIVE_HOLDOUT_REGION_EVIDENCE_REVIEW,
            "review_type",
        )
        _require_version(self.reviewer_version, TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEWER_V1, "reviewer_version")
        _require_version(
            self.validation_evidence_artifact_id,
            TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID,
            "validation_evidence_artifact_id",
        )
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
        _require_text(self.holdout_evaluation_result_id, "holdout_evaluation_result_id")
        _require_text(self.holdout_evaluation_result_checksum, "holdout_evaluation_result_checksum")
        _require_version(self.candidate_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, "candidate_id")
        _require_version(self.region_id, TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID, "region_id")
        if self.threshold_count != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("threshold_count mismatch.")
        if self.holdout_start_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_START_DATE:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("holdout_start_date mismatch.")
        if self.holdout_end_date != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_END_DATE:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("holdout_end_date mismatch.")
        if TechnicalRiskHoldoutRegionConfirmationStatus(self.decision_state) != TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("review package must remain REVIEW_REQUIRED.")
        object.__setattr__(self, "decision_state", TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED)
        if self.production_policy_created:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("Review package cannot create production policy.")
        if self.artifact_created:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("Review package cannot create persisted artifact.")
        object.__setattr__(self, "market_regime_notes", tuple(self.market_regime_notes))
        checksum = _review_checksum(self)
        identity = _stable_id("technical_risk_holdout_region_evidence_review", {"review_package_checksum": checksum})
        if self.review_package_id is not None and self.review_package_id != identity:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("review_package_id mismatch.")
        if self.review_package_checksum is not None and self.review_package_checksum != checksum:
            raise TechnicalRiskHoldoutRegionEvidenceReviewError("review_package_checksum mismatch.")
        object.__setattr__(self, "review_package_id", identity)
        object.__setattr__(self, "review_package_checksum", checksum)


def build_technical_risk_holdout_region_evidence_review_package(
    holdout_result: TechnicalRiskHoldoutRegionEvaluationResult,
    *,
    validation_artifact: TechnicalRiskValidationEvidenceArtifact | None = None,
) -> TechnicalRiskHoldoutRegionEvidenceReviewPackage:
    if not isinstance(holdout_result, TechnicalRiskHoldoutRegionEvaluationResult):
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("holdout_result type mismatch.")
    validation_artifact = validation_artifact or load_official_validation_evidence_artifact()
    _validate_inputs(holdout_result, validation_artifact)
    validation_records = _validation_records_for_frozen_region(validation_artifact)
    holdout_records = holdout_result.threshold_records
    threshold_values = _threshold_values_for_frozen_region()
    validation_summary = _period_summary(
        period_label="VALIDATION_2022_2023",
        split_role=TechnicalRiskOOSSplitRole.VALIDATION,
        row_count=validation_artifact.validation_result.validation_row_count,
        validation_records=validation_records,
    )
    holdout_summary = _period_summary(
        period_label="HOLDOUT_2024_2025",
        split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
        row_count=holdout_result.holdout_row_count,
        holdout_records=holdout_records,
    )
    stability = _threshold_stability(holdout_records, threshold_values)
    shift = _shift_summary(validation_summary, holdout_summary)
    return TechnicalRiskHoldoutRegionEvidenceReviewPackage(
        review_package_id=None,
        review_package_version=TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEW_PACKAGE_V1,
        review_type=TECH_RISK_DESCRIPTIVE_HOLDOUT_REGION_EVIDENCE_REVIEW,
        reviewer_version=TECH_RISK_HOLDOUT_REGION_EVIDENCE_REVIEWER_V1,
        validation_evidence_artifact_id=validation_artifact.artifact_id,
        validation_evidence_artifact_checksum=validation_artifact.artifact_checksum,
        validation_selection_methodology_version=TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
        holdout_evaluation_result_id=holdout_result.result_id,
        holdout_evaluation_result_checksum=holdout_result.result_checksum,
        candidate_id=holdout_result.candidate_id,
        region_id=holdout_result.region_id,
        threshold_count=holdout_result.threshold_count,
        holdout_start_date=holdout_result.holdout_start_date,
        holdout_end_date=holdout_result.holdout_end_date,
        validation_period_label=validation_summary.period_label,
        holdout_period_label=holdout_summary.period_label,
        validation_summary=validation_summary,
        holdout_summary=holdout_summary,
        shift_summary=shift,
        threshold_stability_summary=stability,
        market_regime_notes=(
            "Validation covers 2022-2023; Holdout covers 2024-2025.",
            "Observed shift is descriptive and may reflect a different market regime.",
            "No threshold, candidate, or methodology change is authorized by this review.",
        ),
        decision_state=TechnicalRiskHoldoutRegionConfirmationStatus.REVIEW_REQUIRED,
        production_policy_created=False,
        artifact_created=False,
    )


def build_technical_risk_holdout_region_evidence_review_package_from_artifact(
    artifact: TechnicalRiskHoldoutRegionEvidenceArtifact,
    *,
    validation_artifact: TechnicalRiskValidationEvidenceArtifact | None = None,
) -> TechnicalRiskHoldoutRegionEvidenceReviewPackage:
    if not isinstance(artifact, TechnicalRiskHoldoutRegionEvidenceArtifact):
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("artifact type mismatch.")
    return build_technical_risk_holdout_region_evidence_review_package(
        artifact.holdout_evaluation_result,
        validation_artifact=validation_artifact,
    )


def load_holdout_region_evidence_review_package_from_artifact(
    path: object,
    *,
    validation_artifact: TechnicalRiskValidationEvidenceArtifact | None = None,
) -> TechnicalRiskHoldoutRegionEvidenceReviewPackage:
    return build_technical_risk_holdout_region_evidence_review_package_from_artifact(
        load_holdout_region_evidence_artifact(path),
        validation_artifact=validation_artifact,
    )


def load_official_validation_evidence_artifact() -> TechnicalRiskValidationEvidenceArtifact:
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    return load_validation_evidence_artifact(
        project_root
        / "data"
        / "research"
        / "technical_risk_validation_evidence"
        / "technical_risk_validation_evidence_95cb2cc4a385b5ec.json"
    )


def _validate_inputs(
    holdout_result: TechnicalRiskHoldoutRegionEvaluationResult,
    validation_artifact: TechnicalRiskValidationEvidenceArtifact,
) -> None:
    if holdout_result.split_role != TechnicalRiskOOSSplitRole.HOLDOUT:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("holdout_result must be HOLDOUT.")
    if holdout_result.candidate_id != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("candidate_id mismatch.")
    if holdout_result.region_id != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_ID:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("region_id mismatch.")
    if tuple(identity[0] for identity in holdout_result.threshold_identities) != TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("holdout thresholds must match frozen region.")
    if validation_artifact.artifact_id != TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("Validation artifact id mismatch.")
    if validation_artifact.artifact_checksum != TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("Validation artifact checksum mismatch.")
    if validation_artifact.validation_result.split_role != TechnicalRiskOOSSplitRole.VALIDATION:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("Validation artifact split mismatch.")


def _validation_records_for_frozen_region(
    validation_artifact: TechnicalRiskValidationEvidenceArtifact,
) -> tuple[TechnicalRiskValidationCandidateEvaluationRecord, ...]:
    records_by_key = {
        (record.candidate_id, record.threshold_set_id): record
        for record in validation_artifact.validation_result.evaluation_records
    }
    try:
        records = tuple(
            records_by_key[(TECH_RISK_HOLDOUT_REGION_CONFIRMATION_CANDIDATE_ID, threshold_id)]
            for threshold_id in TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1
        )
    except KeyError as exc:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("Frozen threshold missing from Validation artifact.") from exc
    if len(records) != TECH_RISK_HOLDOUT_REGION_CONFIRMATION_REGION_THRESHOLD_COUNT:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("Validation frozen region count mismatch.")
    return records


def _threshold_values_for_frozen_region() -> Mapping[str, Mapping[str, str]]:
    by_id = {threshold.threshold_set_id: threshold for threshold in materialize_technical_risk_v1_threshold_grid().threshold_sets}
    values = {}
    for threshold_id in TECH_RISK_HOLDOUT_REGION_FROZEN_THRESHOLD_SET_IDS_V1:
        threshold = by_id[threshold_id]
        values[threshold_id] = {
            dimension.value: threshold.dimensions_by_id[dimension].canonical_value
            for dimension in _THRESHOLD_DIMENSION_ORDER
        }
    return values


def _period_summary(
    *,
    period_label: str,
    split_role: TechnicalRiskOOSSplitRole,
    row_count: int,
    validation_records: tuple[TechnicalRiskValidationCandidateEvaluationRecord, ...] | None = None,
    holdout_records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...] | None = None,
) -> TechnicalRiskHoldoutRegionPeriodEvidenceSummary:
    records = validation_records if validation_records is not None else holdout_records
    if records is None:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError("records missing.")
    mae20_statuses = []
    mae60_statuses = []
    mae20_separations = []
    mae60_separations = []
    coverage_by_severity: dict[str, list[Decimal]] = {severity.value: [] for severity in TechnicalRiskCandidateSeverity}
    sample_by_severity: dict[str, list[int]] = {severity.value: [] for severity in TechnicalRiskCandidateSeverity}
    for record in records:
        metrics = _record_metrics(record)
        monotonicity = _record_monotonicity(record)
        mae20_statuses.append(monotonicity[20]["status"])
        mae60_statuses.append(monotonicity[60]["status"])
        mae20_separations.append(monotonicity[20]["high_minus_low"])
        mae60_separations.append(monotonicity[60]["high_minus_low"])
        for metric in metrics:
            coverage_by_severity[metric["severity"]].append(metric["coverage_ratio"])
            sample_by_severity[metric["severity"]].append(metric["sample_count"])
    return TechnicalRiskHoldoutRegionPeriodEvidenceSummary(
        period_label=period_label,
        split_role=split_role,
        row_count=row_count,
        evaluation_count=len(records),
        mae20_monotonicity_counts=dict(sorted(Counter(mae20_statuses).items())),
        mae60_monotonicity_counts=dict(sorted(Counter(mae60_statuses).items())),
        mae20_high_minus_low_distribution=_decimal_profile(mae20_separations),
        mae60_high_minus_low_distribution=_decimal_profile(mae60_separations),
        coverage_distribution_by_severity={
            severity: _decimal_profile(tuple(values))
            for severity, values in coverage_by_severity.items()
        },
        sample_count_distribution_by_severity={
            severity: _int_profile(tuple(values))
            for severity, values in sample_by_severity.items()
        },
    )


def _record_metrics(record) -> tuple[Mapping[str, object], ...]:
    if isinstance(record, TechnicalRiskHoldoutRegionThresholdEvaluationRecord):
        return tuple(
            {
                "severity": evidence.severity.value,
                "coverage_ratio": evidence.coverage_ratio,
                "sample_count": evidence.sample_count,
            }
            for evidence in record.threshold_result.severity_evidence
        )
    return tuple(
        {
            "severity": metric.severity.value,
            "coverage_ratio": metric.coverage_ratio,
            "sample_count": metric.sample_count,
        }
        for metric in record.aggregate_metrics
    )


def _record_monotonicity(record) -> Mapping[int, Mapping[str, object]]:
    if isinstance(record, TechnicalRiskHoldoutRegionThresholdEvaluationRecord):
        result = record.threshold_result
        return {
            20: {
                "status": result.mae20_monotonicity_status,
                "high_minus_low": result.mae20_separation_evidence.high_minus_low,
            },
            60: {
                "status": result.mae60_monotonicity_status,
                "high_minus_low": result.mae60_separation_evidence.high_minus_low,
            },
        }
    by_horizon = {item.horizon: item for item in record.monotonicity_results}
    return {
        20: {
            "status": by_horizon[20].status.value,
            "high_minus_low": _optional_difference(by_horizon[20].high_median, by_horizon[20].low_median),
        },
        60: {
            "status": by_horizon[60].status.value,
            "high_minus_low": _optional_difference(by_horizon[60].high_median, by_horizon[60].low_median),
        },
    }


def _threshold_stability(
    records: tuple[TechnicalRiskHoldoutRegionThresholdEvaluationRecord, ...],
    threshold_values: Mapping[str, Mapping[str, str]],
) -> TechnicalRiskHoldoutRegionThresholdStabilitySummary:
    mae20_warning_count = 0
    mae60_warning_count = 0
    axis_counts: dict[str, dict[str, Counter]] = {
        "MAE20": {dimension.value: Counter() for dimension in _THRESHOLD_DIMENSION_ORDER},
        "MAE60": {dimension.value: Counter() for dimension in _THRESHOLD_DIMENSION_ORDER},
    }
    for record in records:
        threshold_id = record.threshold_result.threshold_set_id
        values = threshold_values[threshold_id]
        if record.threshold_result.mae20_monotonicity_status != "PASS":
            mae20_warning_count += 1
            for dimension, value in values.items():
                axis_counts["MAE20"][dimension][value] += 1
        if record.threshold_result.mae60_monotonicity_status != "PASS":
            mae60_warning_count += 1
            for dimension, value in values.items():
                axis_counts["MAE60"][dimension][value] += 1
    total = len(records)
    return TechnicalRiskHoldoutRegionThresholdStabilitySummary(
        total_threshold_count=total,
        mae20_warning_threshold_count=mae20_warning_count,
        mae60_warning_threshold_count=mae60_warning_count,
        region_wide_degradation=mae20_warning_count == total and mae60_warning_count == total,
        partial_degradation=(mae20_warning_count > 0 or mae60_warning_count > 0)
        and not (mae20_warning_count == total and mae60_warning_count == total),
        warning_axis_counts={
            horizon: {
                dimension: dict(sorted(counter.items()))
                for dimension, counter in dimensions.items()
            }
            for horizon, dimensions in axis_counts.items()
        },
    )


def _shift_summary(
    validation_summary: TechnicalRiskHoldoutRegionPeriodEvidenceSummary,
    holdout_summary: TechnicalRiskHoldoutRegionPeriodEvidenceSummary,
) -> TechnicalRiskHoldoutRegionEvidenceShiftSummary:
    return TechnicalRiskHoldoutRegionEvidenceShiftSummary(
        mae20_pass_count_shift=_pass_count(holdout_summary.mae20_monotonicity_counts)
        - _pass_count(validation_summary.mae20_monotonicity_counts),
        mae60_pass_count_shift=_pass_count(holdout_summary.mae60_monotonicity_counts)
        - _pass_count(validation_summary.mae60_monotonicity_counts),
        mae20_high_minus_low_median_shift=_optional_decimal_string_difference(
            holdout_summary.mae20_high_minus_low_distribution.median,
            validation_summary.mae20_high_minus_low_distribution.median,
        ),
        mae60_high_minus_low_median_shift=_optional_decimal_string_difference(
            holdout_summary.mae60_high_minus_low_distribution.median,
            validation_summary.mae60_high_minus_low_distribution.median,
        ),
        coverage_shift_by_severity={
            severity.value: _optional_decimal_string_difference(
                holdout_summary.coverage_distribution_by_severity[severity.value].median,
                validation_summary.coverage_distribution_by_severity[severity.value].median,
            )
            for severity in TechnicalRiskCandidateSeverity
        },
    )


def _decimal_profile(values: tuple[Decimal | None, ...]) -> TechnicalRiskHoldoutRegionDistributionProfile:
    present = tuple(sorted(value for value in values if value is not None))
    if not present:
        return TechnicalRiskHoldoutRegionDistributionProfile(count=0, minimum=None, median=None, maximum=None)
    return TechnicalRiskHoldoutRegionDistributionProfile(
        count=len(present),
        minimum=_decimal_to_string(present[0]),
        median=_decimal_to_string(_median(present)),
        maximum=_decimal_to_string(present[-1]),
    )


def _int_profile(values: tuple[int, ...]) -> TechnicalRiskHoldoutRegionDistributionProfile:
    if not values:
        return TechnicalRiskHoldoutRegionDistributionProfile(count=0, minimum=None, median=None, maximum=None)
    present = tuple(sorted(values))
    return TechnicalRiskHoldoutRegionDistributionProfile(
        count=len(present),
        minimum=str(present[0]),
        median=_decimal_to_string(_median(tuple(Decimal(value) for value in present))),
        maximum=str(present[-1]),
    )


def _median(values: tuple[Decimal, ...]) -> Decimal:
    midpoint = len(values) // 2
    if len(values) % 2 == 1:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / Decimal("2")


def _optional_difference(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left - right


def _optional_decimal_string_difference(left: str | None, right: str | None) -> str | None:
    if left is None or right is None:
        return None
    return _decimal_to_string(Decimal(left) - Decimal(right))


def _pass_count(counts: Mapping[str, int]) -> int:
    return counts.get("PASS", 0)


def _decimal_to_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


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


def _review_checksum(package: TechnicalRiskHoldoutRegionEvidenceReviewPackage) -> str:
    return _stable_hash(
        {
            "review_package_version": package.review_package_version,
            "review_type": package.review_type,
            "reviewer_version": package.reviewer_version,
            "validation_evidence_artifact_id": package.validation_evidence_artifact_id,
            "validation_evidence_artifact_checksum": package.validation_evidence_artifact_checksum,
            "holdout_evaluation_result_id": package.holdout_evaluation_result_id,
            "holdout_evaluation_result_checksum": package.holdout_evaluation_result_checksum,
            "candidate_id": package.candidate_id,
            "region_id": package.region_id,
            "validation_summary": _period_payload(package.validation_summary),
            "holdout_summary": _period_payload(package.holdout_summary),
            "shift_summary": {
                "mae20_pass_count_shift": package.shift_summary.mae20_pass_count_shift,
                "mae60_pass_count_shift": package.shift_summary.mae60_pass_count_shift,
                "mae20_high_minus_low_median_shift": package.shift_summary.mae20_high_minus_low_median_shift,
                "mae60_high_minus_low_median_shift": package.shift_summary.mae60_high_minus_low_median_shift,
                "coverage_shift_by_severity": dict(package.shift_summary.coverage_shift_by_severity),
            },
            "threshold_stability_summary": {
                "total_threshold_count": package.threshold_stability_summary.total_threshold_count,
                "mae20_warning_threshold_count": package.threshold_stability_summary.mae20_warning_threshold_count,
                "mae60_warning_threshold_count": package.threshold_stability_summary.mae60_warning_threshold_count,
                "region_wide_degradation": package.threshold_stability_summary.region_wide_degradation,
                "partial_degradation": package.threshold_stability_summary.partial_degradation,
                "warning_axis_counts": _thaw_axis_counts(package.threshold_stability_summary.warning_axis_counts),
            },
            "market_regime_notes": package.market_regime_notes,
            "decision_state": TechnicalRiskHoldoutRegionConfirmationStatus(package.decision_state).value,
            "production_policy_created": package.production_policy_created,
            "artifact_created": package.artifact_created,
        }
    )


def _period_payload(summary: TechnicalRiskHoldoutRegionPeriodEvidenceSummary) -> Mapping[str, object]:
    return {
        "period_label": summary.period_label,
        "split_role": summary.split_role.value,
        "row_count": summary.row_count,
        "evaluation_count": summary.evaluation_count,
        "mae20_monotonicity_counts": dict(summary.mae20_monotonicity_counts),
        "mae60_monotonicity_counts": dict(summary.mae60_monotonicity_counts),
        "mae20_high_minus_low_distribution": summary.mae20_high_minus_low_distribution.__dict__,
        "mae60_high_minus_low_distribution": summary.mae60_high_minus_low_distribution.__dict__,
        "coverage_distribution_by_severity": {
            key: value.__dict__
            for key, value in summary.coverage_distribution_by_severity.items()
        },
        "sample_count_distribution_by_severity": {
            key: value.__dict__
            for key, value in summary.sample_count_distribution_by_severity.items()
        },
    }


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
        raise TechnicalRiskHoldoutRegionEvidenceReviewError(f"{field_name} mismatch.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskHoldoutRegionEvidenceReviewError(f"{field_name} must be a non-empty string.")
