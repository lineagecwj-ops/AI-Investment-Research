from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from typing import Mapping

from risk_oos.candidate_evaluator import TechnicalRiskMonotonicityStatus
from risk_oos.validation_selection import TechnicalRiskTiePolicy


TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1 = "TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1"
TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID = "technical_risk_validation_evidence_95cb2cc4a385b5ec"
TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM = (
    "fc8a289542207084c2ddb637d21e81584406d2d8c0caaef49f55502ea506234f"
)
TECH_RISK_ROBUST_REGION_APPROVED_GRID_TOPOLOGY_V1 = "TECH_RISK_ROBUST_REGION_APPROVED_GRID_TOPOLOGY_V1"
TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1 = "NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1"


class TechnicalRiskValidationSelectionMethodologyError(Exception):
    """Raised when the approved Validation selection methodology contract is invalid."""


class TechnicalRiskValidationSelectionMethodologyName(StrEnum):
    ROBUST_REGION_FIRST = "ROBUST_REGION_FIRST"


class TechnicalRiskValidationSelectionMethodologyApprovalStatus(StrEnum):
    APPROVED_FOR_VALIDATION_SELECTION = "APPROVED_FOR_VALIDATION_SELECTION"


class TechnicalRiskValidationSelectionMethodologyProvenance(StrEnum):
    POST_VALIDATION_METHOD_DECISION = "POST_VALIDATION_METHOD_DECISION"


class TechnicalRiskStructuredEvidenceDimension(StrEnum):
    LOW_COVERAGE = "LOW_COVERAGE"
    MEDIUM_COVERAGE = "MEDIUM_COVERAGE"
    HIGH_COVERAGE = "HIGH_COVERAGE"
    LOW_SAMPLE_COUNT = "LOW_SAMPLE_COUNT"
    MEDIUM_SAMPLE_COUNT = "MEDIUM_SAMPLE_COUNT"
    HIGH_SAMPLE_COUNT = "HIGH_SAMPLE_COUNT"
    MAE20_LOW_MEDIAN = "MAE20_LOW_MEDIAN"
    MAE20_MEDIUM_MEDIAN = "MAE20_MEDIUM_MEDIAN"
    MAE20_HIGH_MEDIAN = "MAE20_HIGH_MEDIAN"
    MAE20_HIGH_MINUS_LOW = "MAE20_HIGH_MINUS_LOW"
    MAE60_LOW_MEDIAN = "MAE60_LOW_MEDIAN"
    MAE60_MEDIUM_MEDIAN = "MAE60_MEDIUM_MEDIAN"
    MAE60_HIGH_MEDIAN = "MAE60_HIGH_MEDIAN"
    MAE60_HIGH_MINUS_LOW = "MAE60_HIGH_MINUS_LOW"
    THRESHOLD_NEIGHBOR_STABILITY = "THRESHOLD_NEIGHBOR_STABILITY"
    ROBUST_REGION_IDENTITY = "ROBUST_REGION_IDENTITY"
    ROBUST_REGION_SIZE = "ROBUST_REGION_SIZE"


APPROVED_STRUCTURED_EVIDENCE_DIMENSIONS_V1 = tuple(TechnicalRiskStructuredEvidenceDimension)


@dataclass(frozen=True)
class TechnicalRiskValidationGridPoint:
    """One candidate-threshold grid point eligible for robust-region review."""

    candidate_id: str
    threshold_set_id: str
    grid_coordinates: tuple[int, int, int, int]
    mae20_monotonicity_status: TechnicalRiskMonotonicityStatus | str
    mae60_monotonicity_status: TechnicalRiskMonotonicityStatus | str

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.threshold_set_id, "threshold_set_id")
        object.__setattr__(self, "grid_coordinates", _canonical_coordinates(self.grid_coordinates))
        object.__setattr__(
            self,
            "mae20_monotonicity_status",
            _coerce_monotonicity_status(self.mae20_monotonicity_status, "mae20_monotonicity_status"),
        )
        object.__setattr__(
            self,
            "mae60_monotonicity_status",
            _coerce_monotonicity_status(self.mae60_monotonicity_status, "mae60_monotonicity_status"),
        )


@dataclass(frozen=True)
class TechnicalRiskValidationRobustRegion:
    """Deterministic connected component of dual-horizon PASS/PASS grid points."""

    robust_region_id: str | None
    candidate_id: str
    threshold_set_ids: tuple[str, ...]
    grid_coordinates: tuple[tuple[int, int, int, int], ...]
    robust_region_size: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        threshold_ids = tuple(self.threshold_set_ids)
        coordinates = tuple(_canonical_coordinates(coordinates) for coordinates in self.grid_coordinates)
        if not threshold_ids:
            raise TechnicalRiskValidationSelectionMethodologyError("threshold_set_ids must not be empty.")
        if len(threshold_ids) != len(coordinates):
            raise TechnicalRiskValidationSelectionMethodologyError("region threshold ids and coordinates must have matching lengths.")
        pairs = tuple(sorted(zip(threshold_ids, coordinates), key=lambda item: (item[1], item[0])))
        if len({threshold_id for threshold_id, _ in pairs}) != len(pairs):
            raise TechnicalRiskValidationSelectionMethodologyError("Duplicate threshold_set_id in robust region.")
        if len({coordinates for _, coordinates in pairs}) != len(pairs):
            raise TechnicalRiskValidationSelectionMethodologyError("Duplicate grid_coordinates in robust region.")
        object.__setattr__(self, "threshold_set_ids", tuple(threshold_id for threshold_id, _ in pairs))
        object.__setattr__(self, "grid_coordinates", tuple(coordinates for _, coordinates in pairs))
        size = len(pairs)
        if self.robust_region_size is not None and self.robust_region_size != size:
            raise TechnicalRiskValidationSelectionMethodologyError("robust_region_size mismatch.")
        object.__setattr__(self, "robust_region_size", size)
        identity = _stable_id(
            "technical_risk_validation_robust_region",
            {
                "candidate_id": self.candidate_id,
                "threshold_set_ids": self.threshold_set_ids,
                "grid_coordinates": self.grid_coordinates,
            },
        )
        if self.robust_region_id is not None and self.robust_region_id != identity:
            raise TechnicalRiskValidationSelectionMethodologyError("robust_region_id mismatch.")
        object.__setattr__(self, "robust_region_id", identity)


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionMethodology:
    """Approved post-Validation methodology contract for Technical Risk v1 selection review."""

    methodology_id: str | None
    methodology_version: str
    methodology_name: TechnicalRiskValidationSelectionMethodologyName | str
    approval_status: TechnicalRiskValidationSelectionMethodologyApprovalStatus | str
    provenance: TechnicalRiskValidationSelectionMethodologyProvenance | str
    validation_evidence_artifact_id: str
    validation_evidence_artifact_checksum: str
    required_monotonicity_status: TechnicalRiskMonotonicityStatus | str
    required_monotonicity_horizons: tuple[int, ...]
    robust_region_topology_version: str
    structured_evidence_dimensions: tuple[TechnicalRiskStructuredEvidenceDimension | str, ...]
    numeric_floor_policy: str
    tie_policy: TechnicalRiskTiePolicy | str
    weighted_score_allowed: bool
    candidate_preference_allowed: bool
    methodology_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(
            self.methodology_version,
            TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
            "methodology_version",
        )
        object.__setattr__(
            self,
            "methodology_name",
            _coerce_enum(
                self.methodology_name,
                TechnicalRiskValidationSelectionMethodologyName,
                "methodology_name",
            ),
        )
        object.__setattr__(
            self,
            "approval_status",
            _coerce_enum(
                self.approval_status,
                TechnicalRiskValidationSelectionMethodologyApprovalStatus,
                "approval_status",
            ),
        )
        object.__setattr__(
            self,
            "provenance",
            _coerce_enum(
                self.provenance,
                TechnicalRiskValidationSelectionMethodologyProvenance,
                "provenance",
            ),
        )
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
        object.__setattr__(
            self,
            "required_monotonicity_status",
            _coerce_monotonicity_status(self.required_monotonicity_status, "required_monotonicity_status"),
        )
        if self.required_monotonicity_status != TechnicalRiskMonotonicityStatus.PASS:
            raise TechnicalRiskValidationSelectionMethodologyError("Dual-horizon eligibility requires PASS monotonicity.")
        if tuple(self.required_monotonicity_horizons) != (20, 60):
            raise TechnicalRiskValidationSelectionMethodologyError("Dual-horizon eligibility requires MAE20 and MAE60.")
        _require_version(
            self.robust_region_topology_version,
            TECH_RISK_ROBUST_REGION_APPROVED_GRID_TOPOLOGY_V1,
            "robust_region_topology_version",
        )
        dimensions = tuple(
            _coerce_enum(dimension, TechnicalRiskStructuredEvidenceDimension, "structured_evidence_dimension")
            for dimension in self.structured_evidence_dimensions
        )
        if dimensions != APPROVED_STRUCTURED_EVIDENCE_DIMENSIONS_V1:
            raise TechnicalRiskValidationSelectionMethodologyError("Structured evidence dimensions must match Technical Risk v1 methodology.")
        object.__setattr__(self, "structured_evidence_dimensions", dimensions)
        _require_version(
            self.numeric_floor_policy,
            TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1,
            "numeric_floor_policy",
        )
        object.__setattr__(self, "tie_policy", _coerce_enum(self.tie_policy, TechnicalRiskTiePolicy, "tie_policy"))
        if self.tie_policy != TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION:
            raise TechnicalRiskValidationSelectionMethodologyError("Tie policy must require explicit methodology decision.")
        if self.weighted_score_allowed:
            raise TechnicalRiskValidationSelectionMethodologyError("Weighted score is not allowed.")
        if self.candidate_preference_allowed:
            raise TechnicalRiskValidationSelectionMethodologyError("Candidate-specific preference is not allowed.")
        checksum = _methodology_checksum(self)
        identity = _stable_id("technical_risk_validation_selection_methodology", {"methodology_checksum": checksum})
        if self.methodology_id is not None and self.methodology_id != identity:
            raise TechnicalRiskValidationSelectionMethodologyError("methodology_id mismatch.")
        if self.methodology_checksum is not None and self.methodology_checksum != checksum:
            raise TechnicalRiskValidationSelectionMethodologyError("methodology_checksum mismatch.")
        object.__setattr__(self, "methodology_id", identity)
        object.__setattr__(self, "methodology_checksum", checksum)

    def is_dual_horizon_eligible(
        self,
        *,
        mae20_monotonicity_status: TechnicalRiskMonotonicityStatus | str,
        mae60_monotonicity_status: TechnicalRiskMonotonicityStatus | str,
    ) -> bool:
        mae20_status = _coerce_monotonicity_status(mae20_monotonicity_status, "mae20_monotonicity_status")
        mae60_status = _coerce_monotonicity_status(mae60_monotonicity_status, "mae60_monotonicity_status")
        return mae20_status == self.required_monotonicity_status and mae60_status == self.required_monotonicity_status

    def are_neighboring_grid_points(self, first: TechnicalRiskValidationGridPoint, second: TechnicalRiskValidationGridPoint) -> bool:
        if first.candidate_id != second.candidate_id:
            return False
        diffs = tuple(abs(left - right) for left, right in zip(first.grid_coordinates, second.grid_coordinates))
        return sum(diff != 0 for diff in diffs) == 1 and 1 in diffs and max(diffs) == 1

    def connected_robust_regions(
        self,
        grid_points: tuple[TechnicalRiskValidationGridPoint, ...],
    ) -> tuple[TechnicalRiskValidationRobustRegion, ...]:
        points = tuple(grid_points)
        _validate_unique_grid_points(points)
        ineligible = tuple(point for point in points if not self.is_dual_horizon_eligible(
            mae20_monotonicity_status=point.mae20_monotonicity_status,
            mae60_monotonicity_status=point.mae60_monotonicity_status,
        ))
        if ineligible:
            raise TechnicalRiskValidationSelectionMethodologyError("Robust regions require dual-horizon PASS/PASS points only.")
        remaining = set(points)
        regions: list[TechnicalRiskValidationRobustRegion] = []
        while remaining:
            seed = min(remaining, key=_grid_point_sort_key)
            stack = [seed]
            component: set[TechnicalRiskValidationGridPoint] = set()
            remaining.remove(seed)
            while stack:
                current = stack.pop()
                component.add(current)
                neighbors = tuple(point for point in remaining if self.are_neighboring_grid_points(current, point))
                for neighbor in neighbors:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
            ordered = tuple(sorted(component, key=_grid_point_sort_key))
            regions.append(
                TechnicalRiskValidationRobustRegion(
                    robust_region_id=None,
                    candidate_id=ordered[0].candidate_id,
                    threshold_set_ids=tuple(point.threshold_set_id for point in ordered),
                    grid_coordinates=tuple(point.grid_coordinates for point in ordered),
                )
            )
        return tuple(sorted(regions, key=lambda region: (region.candidate_id, region.robust_region_size, region.robust_region_id)))


def build_technical_risk_v1_validation_selection_methodology() -> TechnicalRiskValidationSelectionMethodology:
    """Build Hank-approved Option C robust-region-first Validation selection methodology."""

    return TechnicalRiskValidationSelectionMethodology(
        methodology_id=None,
        methodology_version=TECHNICAL_RISK_V1_VALIDATION_SELECTION_METHODOLOGY_V1,
        methodology_name=TechnicalRiskValidationSelectionMethodologyName.ROBUST_REGION_FIRST,
        approval_status=TechnicalRiskValidationSelectionMethodologyApprovalStatus.APPROVED_FOR_VALIDATION_SELECTION,
        provenance=TechnicalRiskValidationSelectionMethodologyProvenance.POST_VALIDATION_METHOD_DECISION,
        validation_evidence_artifact_id=TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_ID,
        validation_evidence_artifact_checksum=TECHNICAL_RISK_V1_VALIDATION_EVIDENCE_ARTIFACT_CHECKSUM,
        required_monotonicity_status=TechnicalRiskMonotonicityStatus.PASS,
        required_monotonicity_horizons=(20, 60),
        robust_region_topology_version=TECH_RISK_ROBUST_REGION_APPROVED_GRID_TOPOLOGY_V1,
        structured_evidence_dimensions=APPROVED_STRUCTURED_EVIDENCE_DIMENSIONS_V1,
        numeric_floor_policy=TECH_RISK_NO_NEW_NUMERIC_ACCEPTANCE_FLOORS_V1,
        tie_policy=TechnicalRiskTiePolicy.TIE_REQUIRES_METHOD_DECISION,
        weighted_score_allowed=False,
        candidate_preference_allowed=False,
    )


def _validate_unique_grid_points(points: tuple[TechnicalRiskValidationGridPoint, ...]) -> None:
    identities = tuple((point.candidate_id, point.threshold_set_id) for point in points)
    if len(set(identities)) != len(identities):
        raise TechnicalRiskValidationSelectionMethodologyError("Duplicate candidate-threshold grid point.")
    coordinates = tuple((point.candidate_id, point.grid_coordinates) for point in points)
    if len(set(coordinates)) != len(coordinates):
        raise TechnicalRiskValidationSelectionMethodologyError("Duplicate candidate-coordinate grid point.")


def _grid_point_sort_key(point: TechnicalRiskValidationGridPoint) -> tuple[str, tuple[int, int, int, int], str]:
    return point.candidate_id, point.grid_coordinates, point.threshold_set_id


def _canonical_coordinates(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    coordinates = tuple(value)
    if len(coordinates) != 4:
        raise TechnicalRiskValidationSelectionMethodologyError("grid_coordinates must contain four approved axes.")
    for coordinate in coordinates:
        if not isinstance(coordinate, int) or isinstance(coordinate, bool):
            raise TechnicalRiskValidationSelectionMethodologyError("grid_coordinates must be integer axis indexes.")
        if coordinate < 0 or coordinate > 2:
            raise TechnicalRiskValidationSelectionMethodologyError("grid_coordinates must use approved 3x3x3x3 axis indexes.")
    return coordinates  # type: ignore[return-value]


def _coerce_monotonicity_status(value: TechnicalRiskMonotonicityStatus | str, field_name: str) -> TechnicalRiskMonotonicityStatus:
    return _coerce_enum(value, TechnicalRiskMonotonicityStatus, field_name)


def _coerce_enum(value, enum_cls, field_name: str):
    try:
        return value if isinstance(value, enum_cls) else enum_cls(value)
    except ValueError as exc:
        raise TechnicalRiskValidationSelectionMethodologyError(f"Unsupported {field_name}.") from exc


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskValidationSelectionMethodologyError(f"{field_name} must be a non-empty string.")


def _require_version(value: object, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskValidationSelectionMethodologyError(f"Unsupported {field_name}.")


def _methodology_checksum(methodology: TechnicalRiskValidationSelectionMethodology) -> str:
    return _stable_hash(
        {
            "methodology_version": methodology.methodology_version,
            "methodology_name": methodology.methodology_name.value,
            "approval_status": methodology.approval_status.value,
            "provenance": methodology.provenance.value,
            "validation_evidence_artifact_id": methodology.validation_evidence_artifact_id,
            "validation_evidence_artifact_checksum": methodology.validation_evidence_artifact_checksum,
            "required_monotonicity_status": methodology.required_monotonicity_status.value,
            "required_monotonicity_horizons": methodology.required_monotonicity_horizons,
            "robust_region_topology_version": methodology.robust_region_topology_version,
            "structured_evidence_dimensions": tuple(dimension.value for dimension in methodology.structured_evidence_dimensions),
            "numeric_floor_policy": methodology.numeric_floor_policy,
            "tie_policy": methodology.tie_policy.value,
            "weighted_score_allowed": methodology.weighted_score_allowed,
            "candidate_preference_allowed": methodology.candidate_preference_allowed,
        }
    )


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
