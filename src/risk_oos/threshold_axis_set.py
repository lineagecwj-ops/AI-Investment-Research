from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos.rule_candidates import TechnicalRiskCandidateFamily
from risk_oos.rule_candidates import TechnicalRiskThresholdDimension
from risk_oos.rule_candidates import TechnicalRiskThresholdDimensionId
from risk_oos.rule_candidates import TechnicalRiskThresholdOperator
from risk_oos.temporal_split_methodology import TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1
from risk_oos.threshold_grid import TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1
from risk_oos.threshold_grid import TECH_RISK_THRESHOLD_GRID_SPEC_V1
from risk_oos.threshold_grid import TechnicalRiskThresholdGridMaterializer
from risk_oos.threshold_grid import TechnicalRiskThresholdGridResult
from risk_oos.threshold_grid import TechnicalRiskThresholdGridSpec


TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1 = "TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1"
TECHNICAL_RISK_V1_THRESHOLD_AXIS_EVIDENCE_NEAREST_RANK_LOWER_TAIL_V1 = (
    "TECHNICAL_RISK_V1_THRESHOLD_AXIS_EVIDENCE_NEAREST_RANK_LOWER_TAIL_V1"
)
TECHNICAL_RISK_V1_VALIDATION_SEARCH_USAGE = "VALIDATION_SEARCH"


class TechnicalRiskThresholdAxisSetApprovalStatus(StrEnum):
    APPROVED_FOR_VALIDATION_SEARCH = "APPROVED_FOR_VALIDATION_SEARCH"


class TechnicalRiskThresholdAxisSetError(Exception):
    """Raised when an approved Technical Risk threshold axis-set contract is invalid."""


@dataclass(frozen=True)
class TechnicalRiskV1ThresholdAxisSet:
    """Research-owned approved threshold axes for Technical Risk v1 validation search."""

    axis_set_id: str | None
    axis_set_version: str
    approval_status: TechnicalRiskThresholdAxisSetApprovalStatus | str
    eligible_usage: str
    methodology_version: str
    evidence_split_role: TechnicalRiskOOSSplitRole | str
    evidence_window_start: date
    evidence_window_end: date
    evidence_quantile_method_version: str
    evidence_quantile_anchors: tuple[str, ...]
    close_vs_sma20_values: tuple[object, ...]
    close_vs_sma60_values: tuple[object, ...]
    relative_sma_spread_values: tuple[object, ...]
    rsi14_values: tuple[object, ...]
    axis_set_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(self.axis_set_version, TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1, "axis_set_version")
        status = _coerce_approval_status(self.approval_status)
        object.__setattr__(self, "approval_status", status)
        _require_version(self.eligible_usage, TECHNICAL_RISK_V1_VALIDATION_SEARCH_USAGE, "eligible_usage")
        _require_version(self.methodology_version, TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1, "methodology_version")
        role = _coerce_split_role(self.evidence_split_role)
        if role != TechnicalRiskOOSSplitRole.DEVELOPMENT:
            raise TechnicalRiskThresholdAxisSetError("Threshold axis evidence must use DEVELOPMENT only.")
        object.__setattr__(self, "evidence_split_role", role)
        if self.evidence_window_start != date(2018, 1, 1) or self.evidence_window_end != date(2021, 12, 31):
            raise TechnicalRiskThresholdAxisSetError("Unsupported threshold axis evidence window.")
        _require_version(
            self.evidence_quantile_method_version,
            TECHNICAL_RISK_V1_THRESHOLD_AXIS_EVIDENCE_NEAREST_RANK_LOWER_TAIL_V1,
            "evidence_quantile_method_version",
        )
        if tuple(self.evidence_quantile_anchors) != ("p10", "p20", "p30"):
            raise TechnicalRiskThresholdAxisSetError("Unsupported evidence_quantile_anchors.")
        canonical_axes = {
            TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF: _canonical_axis_values(
                TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
                self.close_vs_sma20_values,
            ),
            TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF: _canonical_axis_values(
                TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF,
                self.close_vs_sma60_values,
            ),
            TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF: _canonical_axis_values(
                TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF,
                self.relative_sma_spread_values,
            ),
            TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF: _canonical_axis_values(
                TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF,
                self.rsi14_values,
            ),
        }
        object.__setattr__(
            self,
            "close_vs_sma20_values",
            canonical_axes[TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF],
        )
        object.__setattr__(
            self,
            "close_vs_sma60_values",
            canonical_axes[TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF],
        )
        object.__setattr__(
            self,
            "relative_sma_spread_values",
            canonical_axes[TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF],
        )
        object.__setattr__(
            self,
            "rsi14_values",
            canonical_axes[TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF],
        )
        checksum = _axis_set_checksum(self)
        identity = _stable_id("technical_risk_v1_threshold_axis_set", {"axis_set_checksum": checksum})
        if self.axis_set_id is not None and self.axis_set_id != identity:
            raise TechnicalRiskThresholdAxisSetError("axis_set_id mismatch.")
        if self.axis_set_checksum is not None and self.axis_set_checksum != checksum:
            raise TechnicalRiskThresholdAxisSetError("axis_set_checksum mismatch.")
        object.__setattr__(self, "axis_set_id", identity)
        object.__setattr__(self, "axis_set_checksum", checksum)

    @property
    def axis_values_by_dimension(self) -> Mapping[TechnicalRiskThresholdDimensionId, tuple[str, ...]]:
        return MappingProxyType(
            {
                TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF: self.close_vs_sma20_values,
                TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF: self.close_vs_sma60_values,
                TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF: self.relative_sma_spread_values,
                TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF: self.rsi14_values,
            }
        )

    def to_grid_spec(self) -> TechnicalRiskThresholdGridSpec:
        return TechnicalRiskThresholdGridSpec(
            grid_spec_id=None,
            grid_spec_version=TECH_RISK_THRESHOLD_GRID_SPEC_V1,
            generation_method_id=TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1,
            generation_method_version=self.axis_set_version,
            source_spec_version=self.axis_set_version,
            candidate_family=TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC,
            compatible_candidate_families=tuple(TechnicalRiskCandidateFamily),
            close_vs_sma20_values=self.close_vs_sma20_values,
            close_vs_sma60_values=self.close_vs_sma60_values,
            relative_sma_spread_values=self.relative_sma_spread_values,
            rsi14_values=self.rsi14_values,
            numeric_representation_version=TECH_RISK_NUMERIC_REPRESENTATION_V1,
            numeric_context_version=TECH_RISK_DECIMAL_CONTEXT_V1,
        )

    def materialize_grid(self) -> TechnicalRiskThresholdGridResult:
        return TechnicalRiskThresholdGridMaterializer().materialize(self.to_grid_spec())


def build_technical_risk_v1_threshold_axis_set() -> TechnicalRiskV1ThresholdAxisSet:
    """Build Hank-approved Technical Risk v1 threshold axes for validation search."""

    return TechnicalRiskV1ThresholdAxisSet(
        axis_set_id=None,
        axis_set_version=TECHNICAL_RISK_V1_THRESHOLD_AXIS_SET_V1,
        approval_status=TechnicalRiskThresholdAxisSetApprovalStatus.APPROVED_FOR_VALIDATION_SEARCH,
        eligible_usage=TECHNICAL_RISK_V1_VALIDATION_SEARCH_USAGE,
        methodology_version=TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1,
        evidence_split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT,
        evidence_window_start=date(2018, 1, 1),
        evidence_window_end=date(2021, 12, 31),
        evidence_quantile_method_version=TECHNICAL_RISK_V1_THRESHOLD_AXIS_EVIDENCE_NEAREST_RANK_LOWER_TAIL_V1,
        evidence_quantile_anchors=("p10", "p20", "p30"),
        close_vs_sma20_values=("-0.050", "-0.030", "-0.015"),
        close_vs_sma60_values=("-0.085", "-0.045", "-0.025"),
        relative_sma_spread_values=("-0.060", "-0.035", "-0.015"),
        rsi14_values=("29", "37", "43"),
    )


def materialize_technical_risk_v1_threshold_grid() -> TechnicalRiskThresholdGridResult:
    """Materialize the approved Technical Risk v1 validation-search threshold grid."""

    return build_technical_risk_v1_threshold_axis_set().materialize_grid()


def _canonical_axis_values(
    dimension_id: TechnicalRiskThresholdDimensionId,
    values: tuple[object, ...],
) -> tuple[str, ...]:
    raw_values = tuple(values)
    if not raw_values:
        raise TechnicalRiskThresholdAxisSetError(f"{dimension_id.value} axis must not be empty.")
    canonical_values = tuple(
        TechnicalRiskThresholdDimension(
            dimension_id,
            TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            value,
        ).canonical_value
        for value in raw_values
    )
    if len(set(canonical_values)) != len(canonical_values):
        raise TechnicalRiskThresholdAxisSetError(f"Duplicate {dimension_id.value} axis value.")
    return tuple(sorted(canonical_values))


def _axis_set_checksum(axis_set: TechnicalRiskV1ThresholdAxisSet) -> str:
    return _stable_hash(
        {
            "axis_set_version": axis_set.axis_set_version,
            "approval_status": axis_set.approval_status.value,
            "eligible_usage": axis_set.eligible_usage,
            "methodology_version": axis_set.methodology_version,
            "evidence_split_role": axis_set.evidence_split_role.value,
            "evidence_window": {
                "start": axis_set.evidence_window_start.isoformat(),
                "end": axis_set.evidence_window_end.isoformat(),
            },
            "evidence_quantile_method_version": axis_set.evidence_quantile_method_version,
            "evidence_quantile_anchors": axis_set.evidence_quantile_anchors,
            "axes": {
                dimension_id.value: values
                for dimension_id, values in axis_set.axis_values_by_dimension.items()
            },
        }
    )


def _coerce_approval_status(value: TechnicalRiskThresholdAxisSetApprovalStatus | str) -> TechnicalRiskThresholdAxisSetApprovalStatus:
    try:
        return value if isinstance(value, TechnicalRiskThresholdAxisSetApprovalStatus) else TechnicalRiskThresholdAxisSetApprovalStatus(value)
    except ValueError as exc:
        raise TechnicalRiskThresholdAxisSetError("Unsupported approval_status.") from exc


def _coerce_split_role(value: TechnicalRiskOOSSplitRole | str) -> TechnicalRiskOOSSplitRole:
    try:
        return value if isinstance(value, TechnicalRiskOOSSplitRole) else TechnicalRiskOOSSplitRole(value)
    except ValueError as exc:
        raise TechnicalRiskThresholdAxisSetError("Unsupported evidence_split_role.") from exc


def _require_version(value: object, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskThresholdAxisSetError(f"Unsupported {field_name}.")


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value
