from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.rule_candidates import TechnicalRiskCandidateSeverity
from risk_oos.validation_evidence_shortlist import TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_RESULT_V1
from risk_oos.validation_evidence_shortlist import TechnicalRiskValidationEvidenceRegion
from risk_oos.validation_evidence_shortlist import TechnicalRiskValidationEvidenceShortlist
from risk_oos.validation_evidence_shortlist import build_technical_risk_validation_evidence_shortlist
from risk_oos.validation_selection import TechnicalRiskTiePolicy
from risk_oos.validation_selection_methodology import TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1
from risk_oos.validation_selection_methodology import TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1
from risk_oos.validation_selection_methodology import TechnicalRiskValidationSelectionMethodology
from risk_oos.validation_selection_methodology import TechnicalRiskValidationSelectionMethodologyApprovalStatus
from risk_oos.validation_selection_methodology import TechnicalRiskValidationSelectionMethodologyName
from risk_oos.validation_selection_methodology import build_technical_risk_v1_validation_selection_methodology


TECH_RISK_VALIDATION_SELECTION_DECISION_PACKAGE_V1 = "TECH_RISK_VALIDATION_SELECTION_DECISION_PACKAGE_V1"
TECH_RISK_DESCRIPTIVE_VALIDATION_SELECTION_DECISION_PACKAGE = "DESCRIPTIVE_VALIDATION_SELECTION_DECISION_PACKAGE"


class TechnicalRiskValidationSelectionDecisionPackageError(Exception):
    """Raised when descriptive Validation selection decision package generation fails closed."""


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionRegionComparison:
    """Descriptive comparison payload for one robust region."""

    region_id: str
    candidate_id: str
    region_size: int
    pass_pass_count: int
    threshold_set_count: int
    threshold_set_ids: tuple[str, ...]
    evaluation_ids: tuple[str, ...]
    grid_coordinates: tuple[tuple[int, int, int, int], ...]
    threshold_values_by_threshold_set: Mapping[str, Mapping[str, str]]
    threshold_range_by_dimension: Mapping[str, tuple[str, str]]
    coverage_profile_by_severity: Mapping[str, tuple[str, str]]
    sample_profile_by_severity: Mapping[str, tuple[int, int]]
    mae20_median_profile_by_severity: Mapping[str, tuple[str | None, str | None]]
    mae60_median_profile_by_severity: Mapping[str, tuple[str | None, str | None]]
    mae20_separation_profile: tuple[str | None, str | None]
    mae60_separation_profile: tuple[str | None, str | None]
    neighbor_count_by_threshold_set: Mapping[str, int]
    neighbor_link_count: int

    def __post_init__(self) -> None:
        _require_text(self.region_id, "region_id")
        _require_text(self.candidate_id, "candidate_id")
        if self.region_size <= 0:
            raise TechnicalRiskValidationSelectionDecisionPackageError("region_size must be positive.")
        if self.pass_pass_count != self.region_size:
            raise TechnicalRiskValidationSelectionDecisionPackageError("pass_pass_count must equal region_size.")
        if self.threshold_set_count != self.region_size:
            raise TechnicalRiskValidationSelectionDecisionPackageError("threshold_set_count must equal region_size.")
        if len(self.threshold_set_ids) != self.threshold_set_count:
            raise TechnicalRiskValidationSelectionDecisionPackageError("threshold_set_ids count mismatch.")
        if len(self.evaluation_ids) != self.region_size:
            raise TechnicalRiskValidationSelectionDecisionPackageError("evaluation_ids count mismatch.")
        if len(self.grid_coordinates) != self.region_size:
            raise TechnicalRiskValidationSelectionDecisionPackageError("grid_coordinates count mismatch.")
        object.__setattr__(self, "threshold_set_ids", tuple(self.threshold_set_ids))
        object.__setattr__(self, "evaluation_ids", tuple(self.evaluation_ids))
        object.__setattr__(self, "grid_coordinates", tuple(tuple(coordinates) for coordinates in self.grid_coordinates))
        object.__setattr__(
            self,
            "threshold_values_by_threshold_set",
            MappingProxyType({
                key: MappingProxyType(dict(value))
                for key, value in self.threshold_values_by_threshold_set.items()
            }),
        )
        object.__setattr__(self, "threshold_range_by_dimension", MappingProxyType(dict(self.threshold_range_by_dimension)))
        object.__setattr__(self, "coverage_profile_by_severity", MappingProxyType(dict(self.coverage_profile_by_severity)))
        object.__setattr__(self, "sample_profile_by_severity", MappingProxyType(dict(self.sample_profile_by_severity)))
        object.__setattr__(self, "mae20_median_profile_by_severity", MappingProxyType(dict(self.mae20_median_profile_by_severity)))
        object.__setattr__(self, "mae60_median_profile_by_severity", MappingProxyType(dict(self.mae60_median_profile_by_severity)))
        object.__setattr__(self, "mae20_separation_profile", tuple(self.mae20_separation_profile))
        object.__setattr__(self, "mae60_separation_profile", tuple(self.mae60_separation_profile))
        object.__setattr__(self, "neighbor_count_by_threshold_set", MappingProxyType(dict(self.neighbor_count_by_threshold_set)))


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionCandidateComparison:
    """Candidate-level descriptive comparison without preference semantics."""

    candidate_id: str
    robust_region_count: int
    pass_pass_count: int
    region_ids: tuple[str, ...]
    region_sizes: tuple[int, ...]
    coverage_profile_by_severity: Mapping[str, tuple[str, str]]
    sample_profile_by_severity: Mapping[str, tuple[int, int]]
    mae20_separation_profile: tuple[str | None, str | None]
    mae60_separation_profile: tuple[str | None, str | None]

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        if self.robust_region_count != len(self.region_ids):
            raise TechnicalRiskValidationSelectionDecisionPackageError("candidate region count mismatch.")
        if self.robust_region_count != len(self.region_sizes):
            raise TechnicalRiskValidationSelectionDecisionPackageError("candidate region size count mismatch.")
        if self.pass_pass_count != sum(self.region_sizes):
            raise TechnicalRiskValidationSelectionDecisionPackageError("candidate pass_pass_count mismatch.")
        object.__setattr__(self, "region_ids", tuple(self.region_ids))
        object.__setattr__(self, "region_sizes", tuple(self.region_sizes))
        object.__setattr__(self, "coverage_profile_by_severity", MappingProxyType(dict(self.coverage_profile_by_severity)))
        object.__setattr__(self, "sample_profile_by_severity", MappingProxyType(dict(self.sample_profile_by_severity)))
        object.__setattr__(self, "mae20_separation_profile", tuple(self.mae20_separation_profile))
        object.__setattr__(self, "mae60_separation_profile", tuple(self.mae60_separation_profile))


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionDecisionPackage:
    """In-memory descriptive decision package for human Validation selection review."""

    decision_package_id: str | None
    decision_package_version: str
    package_type: str
    validation_evidence_artifact_id: str
    validation_evidence_artifact_checksum: str
    evidence_shortlist_id: str
    evidence_shortlist_checksum: str
    methodology_id: str
    methodology_version: str
    methodology_checksum: str
    methodology_name: TechnicalRiskValidationSelectionMethodologyName | str
    numeric_floor_policy: str
    tie_policy: TechnicalRiskTiePolicy | str
    region_count: int
    candidate_count: int
    region_comparisons: tuple[TechnicalRiskValidationSelectionRegionComparison, ...]
    candidate_comparisons: tuple[TechnicalRiskValidationSelectionCandidateComparison, ...]
    remaining_decision_status: TechnicalRiskTiePolicy | str
    decision_package_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(self.decision_package_version, TECH_RISK_VALIDATION_SELECTION_DECISION_PACKAGE_V1, "decision_package_version")
        _require_version(self.package_type, TECH_RISK_DESCRIPTIVE_VALIDATION_SELECTION_DECISION_PACKAGE, "package_type")
        _require_text(self.validation_evidence_artifact_id, "validation_evidence_artifact_id")
        _require_text(self.validation_evidence_artifact_checksum, "validation_evidence_artifact_checksum")
        _require_text(self.evidence_shortlist_id, "evidence_shortlist_id")
        _require_text(self.evidence_shortlist_checksum, "evidence_shortlist_checksum")
        _require_text(self.methodology_id, "methodology_id")
        _require_version(self.methodology_version, TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1, "methodology_version")
        _require_text(self.methodology_checksum, "methodology_checksum")
        _require_version(self.numeric_floor_policy, TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1, "numeric_floor_policy")
        methodology_name = TechnicalRiskValidationSelectionMethodologyName(self.methodology_name)
        if methodology_name != TechnicalRiskValidationSelectionMethodologyName.ROBUST_REGION_FIRST:
            raise TechnicalRiskValidationSelectionDecisionPackageError("methodology_name must be ROBUST_REGION_FIRST.")
        tie_policy = TechnicalRiskTiePolicy(self.tie_policy)
        remaining_status = TechnicalRiskTiePolicy(self.remaining_decision_status)
        if tie_policy != TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION:
            raise TechnicalRiskValidationSelectionDecisionPackageError("tie_policy must require method decision.")
        if remaining_status != tie_policy:
            raise TechnicalRiskValidationSelectionDecisionPackageError("remaining_decision_status must echo tie_policy.")
        region_comparisons = tuple(self.region_comparisons)
        candidate_comparisons = tuple(self.candidate_comparisons)
        if self.region_count != len(region_comparisons):
            raise TechnicalRiskValidationSelectionDecisionPackageError("region_count mismatch.")
        if self.candidate_count != len(candidate_comparisons):
            raise TechnicalRiskValidationSelectionDecisionPackageError("candidate_count mismatch.")
        if not region_comparisons:
            raise TechnicalRiskValidationSelectionDecisionPackageError("region_comparisons must not be empty.")
        object.__setattr__(self, "methodology_name", methodology_name)
        object.__setattr__(self, "tie_policy", tie_policy)
        object.__setattr__(self, "remaining_decision_status", remaining_status)
        object.__setattr__(self, "region_comparisons", region_comparisons)
        object.__setattr__(self, "candidate_comparisons", candidate_comparisons)
        checksum = _package_checksum(self)
        identity = _stable_id("technical_risk_validation_selection_decision_package", {"decision_package_checksum": checksum})
        if self.decision_package_id is not None and self.decision_package_id != identity:
            raise TechnicalRiskValidationSelectionDecisionPackageError("decision_package_id mismatch.")
        if self.decision_package_checksum is not None and self.decision_package_checksum != checksum:
            raise TechnicalRiskValidationSelectionDecisionPackageError("decision_package_checksum mismatch.")
        object.__setattr__(self, "decision_package_id", identity)
        object.__setattr__(self, "decision_package_checksum", checksum)


def build_technical_risk_validation_selection_decision_package(
    shortlist: TechnicalRiskValidationEvidenceShortlist | None = None,
    *,
    methodology: TechnicalRiskValidationSelectionMethodology | None = None,
) -> TechnicalRiskValidationSelectionDecisionPackage:
    methodology = methodology or build_technical_risk_v1_validation_selection_methodology()
    if methodology.approval_status != TechnicalRiskValidationSelectionMethodologyApprovalStatus.APPROVED_FOR_VALIDATION_SELECTION:
        raise TechnicalRiskValidationSelectionDecisionPackageError("methodology must be approved for Validation selection.")
    shortlist = shortlist or build_technical_risk_validation_evidence_shortlist_from_official_artifact(methodology=methodology)
    if shortlist.evidence_shortlist_version != TECH_RISK_VALIDATION_EVIDENCE_SHORTLIST_RESULT_V1:
        raise TechnicalRiskValidationSelectionDecisionPackageError("Unsupported evidence shortlist version.")
    if shortlist.validation_evidence_artifact_id != methodology.validation_evidence_artifact_id:
        raise TechnicalRiskValidationSelectionDecisionPackageError("shortlist artifact id mismatch.")
    if shortlist.validation_evidence_artifact_checksum != methodology.validation_evidence_artifact_checksum:
        raise TechnicalRiskValidationSelectionDecisionPackageError("shortlist artifact checksum mismatch.")
    if shortlist.methodology_id != methodology.methodology_id:
        raise TechnicalRiskValidationSelectionDecisionPackageError("shortlist methodology id mismatch.")
    if shortlist.methodology_version != methodology.methodology_version:
        raise TechnicalRiskValidationSelectionDecisionPackageError("shortlist methodology version mismatch.")
    if shortlist.methodology_checksum != methodology.methodology_checksum:
        raise TechnicalRiskValidationSelectionDecisionPackageError("shortlist methodology checksum mismatch.")

    regions = tuple(_region_comparison(region) for region in shortlist.descriptive_shortlist_regions)
    candidates = _candidate_comparisons(regions)
    return TechnicalRiskValidationSelectionDecisionPackage(
        decision_package_id=None,
        decision_package_version=TECH_RISK_VALIDATION_SELECTION_DECISION_PACKAGE_V1,
        package_type=TECH_RISK_DESCRIPTIVE_VALIDATION_SELECTION_DECISION_PACKAGE,
        validation_evidence_artifact_id=shortlist.validation_evidence_artifact_id,
        validation_evidence_artifact_checksum=shortlist.validation_evidence_artifact_checksum,
        evidence_shortlist_id=shortlist.evidence_shortlist_id,
        evidence_shortlist_checksum=shortlist.evidence_shortlist_checksum,
        methodology_id=methodology.methodology_id,
        methodology_version=methodology.methodology_version,
        methodology_checksum=methodology.methodology_checksum,
        methodology_name=methodology.methodology_name,
        numeric_floor_policy=methodology.numeric_floor_policy,
        tie_policy=methodology.tie_policy,
        region_count=len(regions),
        candidate_count=len(candidates),
        region_comparisons=regions,
        candidate_comparisons=candidates,
        remaining_decision_status=methodology.tie_policy,
    )


def build_technical_risk_validation_evidence_shortlist_from_official_artifact(
    *,
    methodology: TechnicalRiskValidationSelectionMethodology | None = None,
) -> TechnicalRiskValidationEvidenceShortlist:
    from pathlib import Path

    from risk_oos.validation_evidence_artifact import load_validation_evidence_artifact

    project_root = Path(__file__).resolve().parents[2]
    artifact = load_validation_evidence_artifact(
        project_root
        / "data"
        / "research"
        / "technical_risk_validation_evidence"
        / "technical_risk_validation_evidence_95cb2cc4a385b5ec.json"
    )
    return build_technical_risk_validation_evidence_shortlist(artifact, methodology=methodology)


def _region_comparison(region: TechnicalRiskValidationEvidenceRegion) -> TechnicalRiskValidationSelectionRegionComparison:
    return TechnicalRiskValidationSelectionRegionComparison(
        region_id=region.robust_region_id,
        candidate_id=region.candidate_id,
        region_size=region.robust_region_size,
        pass_pass_count=region.robust_region_size,
        threshold_set_count=len(region.threshold_set_ids),
        threshold_set_ids=region.threshold_set_ids,
        evaluation_ids=region.evaluation_ids,
        grid_coordinates=region.grid_coordinates,
        threshold_values_by_threshold_set={
            point.threshold_set_id: dict(point.threshold_values)
            for point in region.evidence_points
        },
        threshold_range_by_dimension=_threshold_ranges(region),
        coverage_profile_by_severity=_severity_decimal_profiles(region.evidence_points, "coverage_by_severity"),
        sample_profile_by_severity=_severity_int_profiles(region.evidence_points, "sample_count_by_severity"),
        mae20_median_profile_by_severity=_severity_optional_decimal_profiles(region.evidence_points, "mae20_median_by_severity"),
        mae60_median_profile_by_severity=_severity_optional_decimal_profiles(region.evidence_points, "mae60_median_by_severity"),
        mae20_separation_profile=_optional_decimal_range(region.mae20_separation_summary),
        mae60_separation_profile=_optional_decimal_range(region.mae60_separation_summary),
        neighbor_count_by_threshold_set=_neighbor_counts(region),
        neighbor_link_count=sum(_neighbor_counts(region).values()) // 2,
    )


def _candidate_comparisons(
    regions: tuple[TechnicalRiskValidationSelectionRegionComparison, ...],
) -> tuple[TechnicalRiskValidationSelectionCandidateComparison, ...]:
    candidate_ids = tuple(sorted({region.candidate_id for region in regions}))
    comparisons = []
    for candidate_id in candidate_ids:
        candidate_regions = tuple(region for region in regions if region.candidate_id == candidate_id)
        comparisons.append(
            TechnicalRiskValidationSelectionCandidateComparison(
                candidate_id=candidate_id,
                robust_region_count=len(candidate_regions),
                pass_pass_count=sum(region.pass_pass_count for region in candidate_regions),
                region_ids=tuple(region.region_id for region in candidate_regions),
                region_sizes=tuple(region.region_size for region in candidate_regions),
                coverage_profile_by_severity=_merge_decimal_profiles(
                    tuple(region.coverage_profile_by_severity for region in candidate_regions)
                ),
                sample_profile_by_severity=_merge_int_profiles(
                    tuple(region.sample_profile_by_severity for region in candidate_regions)
                ),
                mae20_separation_profile=_merge_optional_decimal_profile(
                    tuple(region.mae20_separation_profile for region in candidate_regions)
                ),
                mae60_separation_profile=_merge_optional_decimal_profile(
                    tuple(region.mae60_separation_profile for region in candidate_regions)
                ),
            )
        )
    return tuple(comparisons)


def _threshold_ranges(region: TechnicalRiskValidationEvidenceRegion) -> Mapping[str, tuple[str, str]]:
    dimensions = sorted(region.evidence_points[0].threshold_values)
    return {
        dimension: _decimal_range(tuple(point.threshold_values[dimension] for point in region.evidence_points))
        for dimension in dimensions
    }


def _severity_decimal_profiles(points: tuple, field_name: str) -> Mapping[str, tuple[str, str]]:
    return {
        severity.value: _decimal_range(tuple(getattr(point, field_name)[severity.value] for point in points))
        for severity in TechnicalRiskCandidateSeverity
    }


def _severity_optional_decimal_profiles(points: tuple, field_name: str) -> Mapping[str, tuple[str | None, str | None]]:
    return {
        severity.value: _optional_decimal_range(tuple(getattr(point, field_name)[severity.value] for point in points))
        for severity in TechnicalRiskCandidateSeverity
    }


def _severity_int_profiles(points: tuple, field_name: str) -> Mapping[str, tuple[int, int]]:
    return {
        severity.value: _int_range(tuple(getattr(point, field_name)[severity.value] for point in points))
        for severity in TechnicalRiskCandidateSeverity
    }


def _neighbor_counts(region: TechnicalRiskValidationEvidenceRegion) -> Mapping[str, int]:
    counts = {threshold_id: 0 for threshold_id in region.threshold_set_ids}
    coordinates_by_threshold = dict(zip(region.threshold_set_ids, region.grid_coordinates))
    ids = region.threshold_set_ids
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1:]:
            if _are_neighbors(coordinates_by_threshold[left_id], coordinates_by_threshold[right_id]):
                counts[left_id] += 1
                counts[right_id] += 1
    return dict(sorted(counts.items()))


def _are_neighbors(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> bool:
    diffs = tuple(abs(left - right) for left, right in zip(first, second))
    return sum(diff != 0 for diff in diffs) == 1 and max(diffs) == 1


def _merge_decimal_profiles(profiles: tuple[Mapping[str, tuple[str, str]], ...]) -> Mapping[str, tuple[str, str]]:
    return {
        severity.value: _decimal_range(tuple(value for profile in profiles for value in profile[severity.value]))
        for severity in TechnicalRiskCandidateSeverity
    }


def _merge_int_profiles(profiles: tuple[Mapping[str, tuple[int, int]], ...]) -> Mapping[str, tuple[int, int]]:
    return {
        severity.value: _int_range(tuple(value for profile in profiles for value in profile[severity.value]))
        for severity in TechnicalRiskCandidateSeverity
    }


def _merge_optional_decimal_profile(profiles: tuple[tuple[str | None, str | None], ...]) -> tuple[str | None, str | None]:
    return _optional_decimal_range(tuple(value for profile in profiles for value in profile))


def _decimal_range(values: tuple[str, ...]) -> tuple[str, str]:
    decimals = tuple(Decimal(value) for value in values)
    return str(min(decimals)), str(max(decimals))


def _optional_decimal_range(values: tuple[str | None, ...]) -> tuple[str | None, str | None]:
    decimals = tuple(Decimal(value) for value in values if value is not None)
    if not decimals:
        return None, None
    return str(min(decimals)), str(max(decimals))


def _int_range(values: tuple[int, ...]) -> tuple[int, int]:
    return min(values), max(values)


def _package_checksum(package: TechnicalRiskValidationSelectionDecisionPackage) -> str:
    return _stable_hash(
        {
            "decision_package_version": package.decision_package_version,
            "package_type": package.package_type,
            "validation_evidence_artifact_id": package.validation_evidence_artifact_id,
            "validation_evidence_artifact_checksum": package.validation_evidence_artifact_checksum,
            "evidence_shortlist_id": package.evidence_shortlist_id,
            "evidence_shortlist_checksum": package.evidence_shortlist_checksum,
            "methodology_id": package.methodology_id,
            "methodology_version": package.methodology_version,
            "methodology_checksum": package.methodology_checksum,
            "methodology_name": package.methodology_name.value,
            "numeric_floor_policy": package.numeric_floor_policy,
            "tie_policy": package.tie_policy.value,
            "region_comparisons": tuple(_region_payload(region) for region in package.region_comparisons),
            "candidate_comparisons": tuple(_candidate_payload(candidate) for candidate in package.candidate_comparisons),
            "remaining_decision_status": package.remaining_decision_status.value,
        }
    )


def _region_payload(region: TechnicalRiskValidationSelectionRegionComparison) -> Mapping[str, object]:
    return {
        "region_id": region.region_id,
        "candidate_id": region.candidate_id,
        "region_size": region.region_size,
        "threshold_set_ids": region.threshold_set_ids,
        "evaluation_ids": region.evaluation_ids,
        "grid_coordinates": region.grid_coordinates,
        "threshold_range_by_dimension": dict(region.threshold_range_by_dimension),
        "coverage_profile_by_severity": dict(region.coverage_profile_by_severity),
        "sample_profile_by_severity": dict(region.sample_profile_by_severity),
        "mae20_separation_profile": region.mae20_separation_profile,
        "mae60_separation_profile": region.mae60_separation_profile,
        "neighbor_count_by_threshold_set": dict(region.neighbor_count_by_threshold_set),
        "neighbor_link_count": region.neighbor_link_count,
    }


def _candidate_payload(candidate: TechnicalRiskValidationSelectionCandidateComparison) -> Mapping[str, object]:
    return {
        "candidate_id": candidate.candidate_id,
        "robust_region_count": candidate.robust_region_count,
        "pass_pass_count": candidate.pass_pass_count,
        "region_ids": candidate.region_ids,
        "region_sizes": candidate.region_sizes,
        "coverage_profile_by_severity": dict(candidate.coverage_profile_by_severity),
        "sample_profile_by_severity": dict(candidate.sample_profile_by_severity),
        "mae20_separation_profile": candidate.mae20_separation_profile,
        "mae60_separation_profile": candidate.mae60_separation_profile,
    }


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskValidationSelectionDecisionPackageError(f"{field_name} must be a non-empty string.")


def _require_version(actual: object, expected: str, field_name: str) -> None:
    if actual != expected:
        raise TechnicalRiskValidationSelectionDecisionPackageError(f"Unsupported {field_name}.")
