from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityResult
from risk_oos.candidate_evaluator import TechnicalRiskSeverityMAEMetrics
from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.rule_candidates import TechnicalRiskThresholdDimensionId
from risk_oos.threshold_axis_set import materialize_technical_risk_v1_threshold_grid
from risk_oos.threshold_grid import TechnicalRiskThresholdGridResult
from risk_oos.validation_candidate_evaluation import TechnicalRiskValidationCandidateEvaluationRecord
from risk_oos.validation_evidence_artifact import TechnicalRiskValidationEvidenceArtifact
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1
from risk_oos.validation_selection_methodology import TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1
from risk_oos.validation_selection_methodology import TechnicalRiskValidationGridPoint
from risk_oos.validation_selection_methodology import TechnicalRiskValidationRobustRegion
from risk_oos.validation_selection_methodology import TechnicalRiskValidationSelectionMethodology
from risk_oos.validation_selection_methodology import TechnicalRiskValidationSelectionMethodologyApprovalStatus
from risk_oos.validation_selection_methodology import build_technical_risk_v1_validation_selection_methodology


TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_RESULT_V1 = "TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_RESULT_V1"
TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_EXECUTOR_V1 = "TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_EXECUTOR_V1"
TECH_RISK_DESCRIPTIVE_SHORTLIST_ONLY_V1 = "DESCRIPTIVE_SHORTLIST_ONLY"

_THRESHOLD_DIMENSION_ORDER = (
    TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF,
)


class TechnicalRiskValidationEvidenceShortlistError(Exception):
    """Raised when VALIDATION evidence shortlist execution fails closed."""


@dataclass(frozen=True)
class TechnicalRiskValidationEvidencePoint:
    """One dual-horizon PASS/PASS Validation evidence point."""

    validation_evidence_artifact_id: str
    validation_evidence_artifact_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    threshold_values: Mapping[str, str]
    grid_coordinates: tuple[int, int, int, int]
    evaluation_id: str
    evaluation_checksum: str
    coverage_by_severity: Mapping[str, str]
    sample_count_by_severity: Mapping[str, int]
    mae20_median_by_severity: Mapping[str, str | None]
    mae60_median_by_severity: Mapping[str, str | None]
    mae20_high_minus_low: str | None
    mae60_high_minus_low: str | None

    def __post_init__(self) -> None:
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
        for field_name in (
            "candidate_id",
            "candidate_version",
            "candidate_structural_checksum",
            "threshold_set_id",
            "threshold_set_version",
            "threshold_set_checksum",
            "evaluation_id",
            "evaluation_checksum",
        ):
            _require_text(getattr(self, field_name), field_name)
        coordinates = tuple(self.grid_coordinates)
        if len(coordinates) != 4 or any(not isinstance(value, int) or isinstance(value, bool) for value in coordinates):
            raise TechnicalRiskValidationEvidenceShortlistError("grid_coordinates must contain four integer indexes.")
        object.__setattr__(self, "grid_coordinates", coordinates)
        object.__setattr__(self, "threshold_values", MappingProxyType(dict(self.threshold_values)))
        object.__setattr__(self, "coverage_by_severity", MappingProxyType(dict(self.coverage_by_severity)))
        object.__setattr__(self, "sample_count_by_severity", MappingProxyType(dict(self.sample_count_by_severity)))
        object.__setattr__(self, "mae20_median_by_severity", MappingProxyType(dict(self.mae20_median_by_severity)))
        object.__setattr__(self, "mae60_median_by_severity", MappingProxyType(dict(self.mae60_median_by_severity)))


@dataclass(frozen=True)
class TechnicalRiskValidationEvidenceRegion:
    """One robust region with source-linked descriptive evidence only."""

    robust_region_id: str
    candidate_id: str
    robust_region_size: int
    threshold_set_ids: tuple[str, ...]
    evaluation_ids: tuple[str, ...]
    grid_coordinates: tuple[tuple[int, int, int, int], ...]
    evidence_points: tuple[TechnicalRiskValidationEvidencePoint, ...]
    coverage_summary_by_severity: Mapping[str, tuple[str, ...]]
    sample_count_summary_by_severity: Mapping[str, tuple[int, ...]]
    mae20_separation_summary: tuple[str | None, ...]
    mae60_separation_summary: tuple[str | None, ...]

    def __post_init__(self) -> None:
        _require_text(self.robust_region_id, "robust_region_id")
        _require_text(self.candidate_id, "candidate_id")
        points = tuple(self.evidence_points)
        if not points:
            raise TechnicalRiskValidationEvidenceShortlistError("evidence_points must not be empty.")
        if self.robust_region_size != len(points):
            raise TechnicalRiskValidationEvidenceShortlistError("robust_region_size mismatch.")
        if any(point.candidate_id != self.candidate_id for point in points):
            raise TechnicalRiskValidationEvidenceShortlistError("Region evidence must stay within one candidate.")
        expected_thresholds = tuple(point.threshold_set_id for point in points)
        expected_evaluations = tuple(point.evaluation_id for point in points)
        expected_coordinates = tuple(point.grid_coordinates for point in points)
        if tuple(self.threshold_set_ids) != expected_thresholds:
            raise TechnicalRiskValidationEvidenceShortlistError("threshold_set_ids must echo region evidence.")
        if tuple(self.evaluation_ids) != expected_evaluations:
            raise TechnicalRiskValidationEvidenceShortlistError("evaluation_ids must echo region evidence.")
        if tuple(self.grid_coordinates) != expected_coordinates:
            raise TechnicalRiskValidationEvidenceShortlistError("grid_coordinates must echo region evidence.")
        object.__setattr__(self, "threshold_set_ids", expected_thresholds)
        object.__setattr__(self, "evaluation_ids", expected_evaluations)
        object.__setattr__(self, "grid_coordinates", expected_coordinates)
        object.__setattr__(self, "evidence_points", points)
        object.__setattr__(self, "coverage_summary_by_severity", MappingProxyType(dict(self.coverage_summary_by_severity)))
        object.__setattr__(self, "sample_count_summary_by_severity", MappingProxyType(dict(self.sample_count_summary_by_severity)))
        object.__setattr__(self, "mae20_separation_summary", tuple(self.mae20_separation_summary))
        object.__setattr__(self, "mae60_separation_summary", tuple(self.mae60_separation_summary))


@dataclass(frozen=True)
class TechnicalRiskValidationEvidenceShortlist:
    """In-memory descriptive shortlist from saved VALIDATION evidence."""

    evidence_shortlist_id: str | None
    evidence_shortlist_version: str
    executor_version: str
    shortlist_type: str
    validation_evidence_artifact_id: str
    validation_evidence_artifact_checksum: str
    validation_result_id: str
    validation_result_checksum: str
    methodology_id: str
    methodology_version: str
    methodology_checksum: str
    numeric_floor_policy: str
    pass_pass_evaluation_count: int
    robust_region_count: int
    robust_region_counts_by_candidate: Mapping[str, int]
    robust_regions: tuple[TechnicalRiskValidationEvidenceRegion, ...]
    descriptive_shortlist_regions: tuple[TechnicalRiskValidationEvidenceRegion, ...]
    evidence_shortlist_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(self.evidence_shortlist_version, TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_RESULT_V1, "evidence_shortlist_version")
        _require_version(self.executor_version, TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_EXECUTOR_V1, "executor_version")
        _require_version(self.shortlist_type, TECH_RISK_DESCRIPTIVE_SHORTLIST_ONLY_V1, "shortlist_type")
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
        _require_text(self.validation_result_id, "validation_result_id")
        _require_text(self.validation_result_checksum, "validation_result_checksum")
        _require_text(self.methodology_id, "methodology_id")
        _require_version(self.methodology_version, TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1, "methodology_version")
        _require_text(self.methodology_checksum, "methodology_checksum")
        _require_version(self.numeric_floor_policy, TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1, "numeric_floor_policy")
        regions = tuple(self.robust_regions)
        shortlist_regions = tuple(self.descriptive_shortlist_regions)
        if self.pass_pass_evaluation_count != sum(region.robust_region_size for region in regions):
            raise TechnicalRiskValidationEvidenceShortlistError("pass_pass_evaluation_count mismatch.")
        if self.robust_region_count != len(regions):
            raise TechnicalRiskValidationEvidenceShortlistError("robust_region_count mismatch.")
        if not shortlist_regions:
            raise TechnicalRiskValidationEvidenceShortlistError("descriptive_shortlist_regions must not be empty.")
        if len(shortlist_regions) > 15:
            raise TechnicalRiskValidationEvidenceShortlistError("descriptive_shortlist_regions must not exceed 15.")
        region_ids = {region.robust_region_id for region in regions}
        if any(region.robust_region_id not in region_ids for region in shortlist_regions):
            raise TechnicalRiskValidationEvidenceShortlistError("descriptive shortlist must reference robust regions.")
        expected_counts = _counts_by_candidate(regions)
        if dict(self.robust_region_counts_by_candidate) != expected_counts:
            raise TechnicalRiskValidationEvidenceShortlistError("robust_region_counts_by_candidate mismatch.")
        object.__setattr__(self, "robust_region_counts_by_candidate", MappingProxyType(expected_counts))
        object.__setattr__(self, "robust_regions", regions)
        object.__setattr__(self, "descriptive_shortlist_regions", shortlist_regions)
        checksum = _shortlist_checksum(self)
        identity = _stable_id("technical_risk_validation_evidence_shortlist", {"evidence_shortlist_checksum": checksum})
        if self.evidence_shortlist_id is not None and self.evidence_shortlist_id != identity:
            raise TechnicalRiskValidationEvidenceShortlistError("evidence_shortlist_id mismatch.")
        if self.evidence_shortlist_checksum is not None and self.evidence_shortlist_checksum != checksum:
            raise TechnicalRiskValidationEvidenceShortlistError("evidence_shortlist_checksum mismatch.")
        object.__setattr__(self, "evidence_shortlist_id", identity)
        object.__setattr__(self, "evidence_shortlist_checksum", checksum)


def build_technical_risk_validation_evidence_shortlist(
    artifact: TechnicalRiskValidationEvidenceArtifact,
    *,
    methodology: TechnicalRiskValidationSelectionMethodology | None = None,
    threshold_grid_result: TechnicalRiskThresholdGridResult | None = None,
) -> TechnicalRiskValidationEvidenceShortlist:
    if not isinstance(artifact, TechnicalRiskValidationEvidenceArtifact):
        raise TechnicalRiskValidationEvidenceShortlistError("artifact must be TechnicalRiskValidationEvidenceArtifact.")
    methodology = methodology or build_technical_risk_v1_validation_selection_methodology()
    if methodology.approval_status != TechnicalRiskValidationSelectionMethodologyApprovalStatus.APPROVED_FOR_VALIDATION_SELECTION:
        raise TechnicalRiskValidationEvidenceShortlistError("Methodology must be approved for Validation selection.")
    if artifact.artifact_id != methodology.validation_evidence_artifact_id:
        raise TechnicalRiskValidationEvidenceShortlistError("Validation evidence artifact id mismatch.")
    if artifact.artifact_checksum != methodology.validation_evidence_artifact_checksum:
        raise TechnicalRiskValidationEvidenceShortlistError("Validation evidence artifact checksum mismatch.")
    threshold_grid_result = threshold_grid_result or materialize_technical_risk_v1_threshold_grid()
    result = artifact.validation_result
    if result.threshold_grid_result_id != threshold_grid_result.grid_result_id:
        raise TechnicalRiskValidationEvidenceShortlistError("threshold grid result id mismatch.")
    if result.threshold_grid_result_checksum != threshold_grid_result.grid_result_checksum:
        raise TechnicalRiskValidationEvidenceShortlistError("threshold grid result checksum mismatch.")
    threshold_context = _threshold_context(threshold_grid_result)
    _validate_threshold_identities(result.threshold_identities, threshold_context)
    evidence_points = _pass_pass_points(artifact, methodology, threshold_context)
    robust_regions = methodology.connected_robust_regions(
        tuple(
            TechnicalRiskValidationGridPoint(
                candidate_id=point.candidate_id,
                threshold_set_id=point.threshold_set_id,
                grid_coordinates=point.grid_coordinates,
                mae20_monotonicity_status="PASS",
                mae60_monotonicity_status="PASS",
            )
            for point in evidence_points
        )
    )
    regions = _evidence_regions(robust_regions, evidence_points)
    canonical_regions = tuple(sorted(regions, key=_region_canonical_key))
    return TechnicalRiskValidationEvidenceShortlist(
        evidence_shortlist_id=None,
        evidence_shortlist_version=TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_RESULT_V1,
        executor_version=TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_EXECUTOR_V1,
        shortlist_type=TECH_RISK_DESCRIPTIVE_SHORTLIST_ONLY_V1,
        validation_evidence_artifact_id=artifact.artifact_id,
        validation_evidence_artifact_checksum=artifact.artifact_checksum,
        validation_result_id=result.result_id,
        validation_result_checksum=result.result_checksum,
        methodology_id=methodology.methodology_id,
        methodology_version=methodology.methodology_version,
        methodology_checksum=methodology.methodology_checksum,
        numeric_floor_policy=methodology.numeric_floor_policy,
        pass_pass_evaluation_count=len(evidence_points),
        robust_region_count=len(canonical_regions),
        robust_region_counts_by_candidate=_counts_by_candidate(canonical_regions),
        robust_regions=canonical_regions,
        descriptive_shortlist_regions=canonical_regions[:15],
    )


def _threshold_context(grid_result: TechnicalRiskThresholdGridResult) -> Mapping[str, tuple[str, tuple[int, int, int, int], Mapping[str, str]]]:
    axis_values = grid_result.grid_spec.axis_values_by_dimension
    context = {}
    for threshold_set in grid_result.threshold_sets:
        values = {
            dimension.value: threshold_set.dimensions_by_id[dimension].canonical_value
            for dimension in _THRESHOLD_DIMENSION_ORDER
        }
        coordinates = tuple(
            axis_values[dimension].index(threshold_set.dimensions_by_id[dimension].canonical_value)
            for dimension in _THRESHOLD_DIMENSION_ORDER
        )
        context[threshold_set.threshold_set_id] = (
            threshold_set.threshold_set_checksum,
            coordinates,
            values,
        )
    return MappingProxyType(context)


def _validate_threshold_identities(
    identities: tuple[tuple[str, str], ...],
    threshold_context: Mapping[str, tuple[str, tuple[int, int, int, int], Mapping[str, str]]],
) -> None:
    expected = tuple(sorted((threshold_id, values[0]) for threshold_id, values in threshold_context.items()))
    actual = tuple(sorted(identities))
    if actual != expected:
        raise TechnicalRiskValidationEvidenceShortlistError("Validation artifact threshold identities do not match approved grid.")


def _pass_pass_points(
    artifact: TechnicalRiskValidationEvidenceArtifact,
    methodology: TechnicalRiskValidationSelectionMethodology,
    threshold_context: Mapping[str, tuple[str, tuple[int, int, int, int], Mapping[str, str]]],
) -> tuple[TechnicalRiskValidationEvidencePoint, ...]:
    points = []
    for record in artifact.validation_result.evaluation_records:
        monotonicity = _monotonicity_by_horizon(record)
        if not methodology.is_dual_horizon_eligible(
            mae20_monotonicity_status=monotonicity[20].status,
            mae60_monotonicity_status=monotonicity[60].status,
        ):
            continue
        threshold_checksum, coordinates, threshold_values = threshold_context[record.threshold_set_id]
        if record.threshold_set_checksum != threshold_checksum:
            raise TechnicalRiskValidationEvidenceShortlistError("Evaluation threshold checksum mismatch.")
        metrics = _metrics_by_severity(record)
        points.append(
            TechnicalRiskValidationEvidencePoint(
                validation_evidence_artifact_id=artifact.artifact_id,
                validation_evidence_artifact_checksum=artifact.artifact_checksum,
                candidate_id=record.candidate_id,
                candidate_version=record.candidate_version,
                candidate_structural_checksum=record.candidate_structural_checksum,
                threshold_set_id=record.threshold_set_id,
                threshold_set_version=record.threshold_set_version,
                threshold_set_checksum=record.threshold_set_checksum,
                threshold_values=threshold_values,
                grid_coordinates=coordinates,
                evaluation_id=record.evaluation_id,
                evaluation_checksum=record.evaluation_checksum,
                coverage_by_severity={severity.value: _decimal_text(metrics[severity].coverage_ratio) for severity in TechnicalRiskCandidateSeverity},
                sample_count_by_severity={severity.value: metrics[severity].sample_count for severity in TechnicalRiskCandidateSeverity},
                mae20_median_by_severity={severity.value: _optional_decimal_text(metrics[severity].mae20_median) for severity in TechnicalRiskCandidateSeverity},
                mae60_median_by_severity={severity.value: _optional_decimal_text(metrics[severity].mae60_median) for severity in TechnicalRiskCandidateSeverity},
                mae20_high_minus_low=_separation(metrics, "mae20_median"),
                mae60_high_minus_low=_separation(metrics, "mae60_median"),
            )
        )
    return tuple(sorted(points, key=_point_key))


def _evidence_regions(
    robust_regions: tuple[TechnicalRiskValidationRobustRegion, ...],
    evidence_points: tuple[TechnicalRiskValidationEvidencePoint, ...],
) -> tuple[TechnicalRiskValidationEvidenceRegion, ...]:
    by_key = {(point.candidate_id, point.threshold_set_id): point for point in evidence_points}
    regions = []
    for region in robust_regions:
        points = tuple(by_key[(region.candidate_id, threshold_set_id)] for threshold_set_id in region.threshold_set_ids)
        regions.append(
            TechnicalRiskValidationEvidenceRegion(
                robust_region_id=region.robust_region_id,
                candidate_id=region.candidate_id,
                robust_region_size=region.robust_region_size,
                threshold_set_ids=tuple(point.threshold_set_id for point in points),
                evaluation_ids=tuple(point.evaluation_id for point in points),
                grid_coordinates=tuple(point.grid_coordinates for point in points),
                evidence_points=points,
                coverage_summary_by_severity=_summary_tuple(points, "coverage_by_severity"),
                sample_count_summary_by_severity=_summary_tuple(points, "sample_count_by_severity"),
                mae20_separation_summary=tuple(point.mae20_high_minus_low for point in points),
                mae60_separation_summary=tuple(point.mae60_high_minus_low for point in points),
            )
        )
    return tuple(regions)


def _monotonicity_by_horizon(record: TechnicalRiskValidationCandidateEvaluationRecord) -> Mapping[int, TechnicalRiskMonotonicityResult]:
    mapping = {item.horizon: item for item in record.monotonicity_results}
    if set(mapping) != {20, 60}:
        raise TechnicalRiskValidationEvidenceShortlistError("Evaluation must include MAE20 and MAE60 monotonicity.")
    return MappingProxyType(mapping)


def _metrics_by_severity(record: TechnicalRiskValidationCandidateEvaluationRecord) -> Mapping[TechnicalRiskCandidateSeverity, TechnicalRiskSeverityMAEMetrics]:
    mapping = {item.severity: item for item in record.aggregate_metrics}
    if set(mapping) != set(TechnicalRiskCandidateSeverity):
        raise TechnicalRiskValidationEvidenceShortlistError("Evaluation must include LOW, MEDIUM, and HIGH metrics.")
    return MappingProxyType(mapping)


def _summary_tuple(points: tuple[TechnicalRiskValidationEvidencePoint, ...], field_name: str) -> Mapping[str, tuple]:
    return {
        severity.value: tuple(getattr(point, field_name)[severity.value] for point in points)
        for severity in TechnicalRiskCandidateSeverity
    }


def _separation(metrics: Mapping[TechnicalRiskCandidateSeverity, TechnicalRiskSeverityMAEMetrics], field_name: str) -> str | None:
    low = getattr(metrics[TechnicalRiskCandidateSeverity.LOW], field_name)
    high = getattr(metrics[TechnicalRiskCandidateSeverity.HIGH], field_name)
    if low is None or high is None:
        return None
    return _decimal_text(high - low)


def _counts_by_candidate(regions: tuple[TechnicalRiskValidationEvidenceRegion, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for region in regions:
        counts[region.candidate_id] = counts.get(region.candidate_id, 0) + 1
    return dict(sorted(counts.items()))


def _region_canonical_key(region: TechnicalRiskValidationEvidenceRegion) -> tuple[str, tuple[int, int, int, int], str]:
    return region.candidate_id, region.grid_coordinates[0], region.robust_region_id


def _point_key(point: TechnicalRiskValidationEvidencePoint) -> tuple[str, tuple[int, int, int, int], str]:
    return point.candidate_id, point.grid_coordinates, point.threshold_set_id


def _shortlist_checksum(shortlist: TechnicalRiskValidationEvidenceShortlist) -> str:
    return _stable_hash(
        {
            "evidence_shortlist_version": shortlist.evidence_shortlist_version,
            "executor_version": shortlist.executor_version,
            "shortlist_type": shortlist.shortlist_type,
            "validation_evidence_artifact_id": shortlist.validation_evidence_artifact_id,
            "validation_evidence_artifact_checksum": shortlist.validation_evidence_artifact_checksum,
            "validation_result_id": shortlist.validation_result_id,
            "validation_result_checksum": shortlist.validation_result_checksum,
            "methodology_id": shortlist.methodology_id,
            "methodology_version": shortlist.methodology_version,
            "methodology_checksum": shortlist.methodology_checksum,
            "numeric_floor_policy": shortlist.numeric_floor_policy,
            "pass_pass_evaluation_count": shortlist.pass_pass_evaluation_count,
            "robust_regions": tuple(_region_payload(region) for region in shortlist.robust_regions),
            "descriptive_shortlist_region_ids": tuple(region.robust_region_id for region in shortlist.descriptive_shortlist_regions),
        }
    )


def _region_payload(region: TechnicalRiskValidationEvidenceRegion) -> Mapping[str, object]:
    return {
        "robust_region_id": region.robust_region_id,
        "candidate_id": region.candidate_id,
        "robust_region_size": region.robust_region_size,
        "threshold_set_ids": region.threshold_set_ids,
        "evaluation_ids": region.evaluation_ids,
        "grid_coordinates": region.grid_coordinates,
    }


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _decimal_text(value: Decimal) -> str:
    return str(value)


def _optional_decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else _decimal_text(value)


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskValidationEvidenceShortlistError(f"{field_name} must be a non-empty string.")


def _require_version(actual: object, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskValidationEvidenceShortlistError(f"Unsupported {field_name}.")
