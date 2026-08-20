from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.development_exploration import TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1
from risk_oos.development_exploration import ThresholdCandidateGenerationContract
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos.rule_candidates import TechnicalRiskCandidateFamily
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateError
from risk_oos.rule_candidates import TechnicalRiskThresholdDimension
from risk_oos.rule_candidates import TechnicalRiskThresholdDimensionId
from risk_oos.rule_candidates import TechnicalRiskThresholdOperator
from risk_oos.rule_candidates import TechnicalRiskThresholdSet


TECH_RISK_THRESHOLD_GRID_SPEC_V1 = "TECH_RISK_THRESHOLD_GRID_SPEC_V1"
TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1 = "TECH_RISK_FIXED_THRESHOLD_GRID_METHOD_V1"
TECH_RISK_THRESHOLD_GRID_RESULT_V1 = "TECH_RISK_THRESHOLD_GRID_RESULT_V1"


class TechnicalRiskThresholdGridError(Exception):
    """Raised when Technical Risk threshold grid materialization is invalid."""


@dataclass(frozen=True)
class TechnicalRiskThresholdGridSpec:
    """Explicit four-axis threshold candidate grid specification."""

    grid_spec_id: str | None
    grid_spec_version: str
    generation_method_id: str
    generation_method_version: str
    source_spec_version: str
    candidate_family: TechnicalRiskCandidateFamily
    compatible_candidate_families: tuple[TechnicalRiskCandidateFamily, ...]
    close_vs_sma20_values: tuple[object, ...]
    close_vs_sma60_values: tuple[object, ...]
    relative_sma_spread_values: tuple[object, ...]
    rsi14_values: tuple[object, ...]
    threshold_set_version: str = "v1"
    numeric_representation_version: str = TECH_RISK_NUMERIC_REPRESENTATION_V1
    numeric_context_version: str = TECH_RISK_DECIMAL_CONTEXT_V1

    def __post_init__(self) -> None:
        _require_version(self.grid_spec_version, TECH_RISK_THRESHOLD_GRID_SPEC_V1, "grid_spec_version")
        _require_text(self.generation_method_id, "generation_method_id")
        _require_text(self.generation_method_version, "generation_method_version")
        _require_text(self.source_spec_version, "source_spec_version")
        _require_text(self.threshold_set_version, "threshold_set_version")
        _require_version(self.numeric_representation_version, TECH_RISK_NUMERIC_REPRESENTATION_V1, "numeric_representation_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        if not isinstance(self.candidate_family, TechnicalRiskCandidateFamily):
            object.__setattr__(self, "candidate_family", TechnicalRiskCandidateFamily(self.candidate_family))
        families = _normalize_candidate_families(self.compatible_candidate_families)
        object.__setattr__(self, "compatible_candidate_families", families)
        axes = {
            TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF: self.close_vs_sma20_values,
            TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF: self.close_vs_sma60_values,
            TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF: self.relative_sma_spread_values,
            TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF: self.rsi14_values,
        }
        canonical_axes = {
            dimension_id: _canonical_axis_values(dimension_id, values)
            for dimension_id, values in axes.items()
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
        checksum = _grid_spec_checksum(self)
        identity = _stable_id("technical_risk_threshold_grid_spec", {"grid_spec_checksum": checksum})
        if self.grid_spec_id is not None and self.grid_spec_id != identity:
            raise TechnicalRiskThresholdGridError("grid_spec_id mismatch.")
        object.__setattr__(self, "grid_spec_id", identity)

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


@dataclass(frozen=True)
class TechnicalRiskThresholdGridResult:
    """In-memory materialized threshold grid result."""

    grid_result_id: str | None
    grid_result_version: str
    grid_spec: TechnicalRiskThresholdGridSpec
    threshold_sets: tuple[TechnicalRiskThresholdSet, ...]
    generation_contract: ThresholdCandidateGenerationContract
    grid_result_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.grid_result_version, "grid_result_version")
        if self.grid_result_version != TECH_RISK_THRESHOLD_GRID_RESULT_V1:
            raise TechnicalRiskThresholdGridError("Unsupported grid_result_version.")
        threshold_sets = tuple(self.threshold_sets)
        if not threshold_sets:
            raise TechnicalRiskThresholdGridError("threshold_sets must not be empty.")
        threshold_ids = tuple(threshold.threshold_set_id for threshold in threshold_sets)
        threshold_checksums = tuple(threshold.threshold_set_checksum for threshold in threshold_sets)
        if len(set(threshold_ids)) != len(threshold_ids):
            raise TechnicalRiskThresholdGridError("Duplicate threshold_set_id.")
        if len(set(threshold_checksums)) != len(threshold_checksums):
            raise TechnicalRiskThresholdGridError("Duplicate threshold_set_checksum.")
        ordered_sets = tuple(sorted(threshold_sets, key=lambda item: item.threshold_set_id))
        ordered_ids = tuple(threshold.threshold_set_id for threshold in ordered_sets)
        ordered_checksums = tuple(threshold.threshold_set_checksum for threshold in ordered_sets)
        expected_ids = tuple(self.generation_contract.generated_threshold_set_ids)
        expected_checksums = tuple(self.generation_contract.generated_threshold_set_checksums)
        if ordered_ids != expected_ids:
            raise TechnicalRiskThresholdGridError("generation threshold ids do not match materialized threshold sets.")
        if ordered_checksums != expected_checksums:
            raise TechnicalRiskThresholdGridError("generation threshold checksums do not match materialized threshold sets.")
        object.__setattr__(self, "threshold_sets", ordered_sets)
        checksum = _grid_result_checksum(self)
        identity = _stable_id("technical_risk_threshold_grid_result", {"grid_result_checksum": checksum})
        if self.grid_result_id is not None and self.grid_result_id != identity:
            raise TechnicalRiskThresholdGridError("grid_result_id mismatch.")
        if self.grid_result_checksum is not None and self.grid_result_checksum != checksum:
            raise TechnicalRiskThresholdGridError("grid_result_checksum mismatch.")
        object.__setattr__(self, "grid_result_id", identity)
        object.__setattr__(self, "grid_result_checksum", checksum)


class TechnicalRiskThresholdGridMaterializer:
    """Materializes explicit threshold axes into existing TechnicalRiskThresholdSet objects."""

    def materialize(self, spec: TechnicalRiskThresholdGridSpec) -> TechnicalRiskThresholdGridResult:
        threshold_sets = tuple(
            sorted(
                (
                    _threshold_set_from_values(spec, values)
                    for values in product(
                        spec.close_vs_sma20_values,
                        spec.close_vs_sma60_values,
                        spec.relative_sma_spread_values,
                        spec.rsi14_values,
                    )
                ),
                key=lambda item: item.threshold_set_id,
            )
        )
        if len({threshold.threshold_set_checksum for threshold in threshold_sets}) != len(threshold_sets):
            raise TechnicalRiskThresholdGridError("Duplicate semantic threshold set in materialized grid.")
        generation_contract = ThresholdCandidateGenerationContract(
            generation_id=None,
            generation_version=TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1,
            generation_method_id=spec.generation_method_id,
            generation_method_version=spec.generation_method_version,
            numeric_representation_version=spec.numeric_representation_version,
            numeric_context_version=spec.numeric_context_version,
            candidate_family=spec.candidate_family,
            source_spec_version=spec.source_spec_version,
            generated_threshold_set_ids=tuple(threshold.threshold_set_id for threshold in threshold_sets),
            generated_threshold_set_checksums=tuple(threshold.threshold_set_checksum for threshold in threshold_sets),
        )
        return TechnicalRiskThresholdGridResult(
            grid_result_id=None,
            grid_result_version=TECH_RISK_THRESHOLD_GRID_RESULT_V1,
            grid_spec=spec,
            threshold_sets=threshold_sets,
            generation_contract=generation_contract,
        )


def _threshold_set_from_values(
    spec: TechnicalRiskThresholdGridSpec,
    values: tuple[str, str, str, str],
) -> TechnicalRiskThresholdSet:
    dimensions = (
        TechnicalRiskThresholdDimension(
            TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
            TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            values[0],
        ),
        TechnicalRiskThresholdDimension(
            TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF,
            TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            values[1],
        ),
        TechnicalRiskThresholdDimension(
            TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF,
            TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            values[2],
        ),
        TechnicalRiskThresholdDimension(
            TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF,
            TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
            values[3],
        ),
    )
    probe = TechnicalRiskThresholdSet(
        threshold_set_id="technical_risk_threshold_set_pending",
        threshold_set_version=spec.threshold_set_version,
        numeric_representation_version=spec.numeric_representation_version,
        dimensions=dimensions,
        compatible_candidate_families=spec.compatible_candidate_families,
    )
    threshold_set_id = _stable_id("technical_risk_threshold_set", {"threshold_set_checksum": probe.threshold_set_checksum})
    return TechnicalRiskThresholdSet(
        threshold_set_id=threshold_set_id,
        threshold_set_version=spec.threshold_set_version,
        numeric_representation_version=spec.numeric_representation_version,
        dimensions=dimensions,
        compatible_candidate_families=spec.compatible_candidate_families,
        threshold_set_checksum=probe.threshold_set_checksum,
    )


def _canonical_axis_values(
    dimension_id: TechnicalRiskThresholdDimensionId,
    values: tuple[object, ...],
) -> tuple[str, ...]:
    raw_values = tuple(values)
    if not raw_values:
        raise TechnicalRiskThresholdGridError(f"{dimension_id.value} axis must not be empty.")
    canonical_values: list[str] = []
    for value in raw_values:
        try:
            dimension = TechnicalRiskThresholdDimension(
                dimension_id,
                TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL,
                value,
            )
        except TechnicalRiskRuleCandidateError as exc:
            raise TechnicalRiskThresholdGridError(f"Invalid {dimension_id.value} axis value: {exc}") from exc
        canonical_values.append(dimension.canonical_value)
    if len(set(canonical_values)) != len(canonical_values):
        raise TechnicalRiskThresholdGridError(f"Duplicate {dimension_id.value} axis value.")
    return tuple(sorted(canonical_values))


def _normalize_candidate_families(values: tuple[TechnicalRiskCandidateFamily, ...]) -> tuple[TechnicalRiskCandidateFamily, ...]:
    families = tuple(value if isinstance(value, TechnicalRiskCandidateFamily) else TechnicalRiskCandidateFamily(value) for value in values)
    if not families:
        raise TechnicalRiskThresholdGridError("compatible_candidate_families must not be empty.")
    if len(set(families)) != len(families):
        raise TechnicalRiskThresholdGridError("Duplicate compatible candidate family.")
    return tuple(sorted(families, key=lambda item: item.value))


def _grid_spec_checksum(spec: TechnicalRiskThresholdGridSpec) -> str:
    return _stable_hash(
        {
            "grid_spec_version": spec.grid_spec_version,
            "generation_method_id": spec.generation_method_id,
            "generation_method_version": spec.generation_method_version,
            "source_spec_version": spec.source_spec_version,
            "candidate_family": spec.candidate_family.value,
            "compatible_candidate_families": [family.value for family in spec.compatible_candidate_families],
            "threshold_set_version": spec.threshold_set_version,
            "numeric_representation_version": spec.numeric_representation_version,
            "numeric_context_version": spec.numeric_context_version,
            "axes": {
                dimension_id.value: values
                for dimension_id, values in spec.axis_values_by_dimension.items()
            },
        }
    )


def _grid_result_checksum(result: TechnicalRiskThresholdGridResult) -> str:
    return _stable_hash(
        {
            "grid_result_version": result.grid_result_version,
            "grid_spec_id": result.grid_spec.grid_spec_id,
            "generation_id": result.generation_contract.generation_id,
            "generation_checksum": result.generation_contract.generation_checksum,
            "threshold_sets": [
                {
                    "threshold_set_id": threshold.threshold_set_id,
                    "threshold_set_checksum": threshold.threshold_set_checksum,
                }
                for threshold in result.threshold_sets
            ],
        }
    )


def _require_version(value: object, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskThresholdGridError(f"Unsupported {field_name}.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskThresholdGridError(f"{field_name} must be a non-empty string.")


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, TechnicalRiskCandidateFamily):
        return value.value
    if isinstance(value, TechnicalRiskThresholdDimensionId):
        return value.value
    return value
