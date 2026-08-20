from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from types import MappingProxyType
from typing import Mapping

from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitSpec


TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1 = "TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1"


class TechnicalRiskTemporalSplitMethodologyError(Exception):
    """Raised when Technical Risk temporal split methodology is invalid."""


@dataclass(frozen=True)
class TechnicalRiskV1TemporalSplitMethodology:
    """Frozen Technical Risk v1 temporal split methodology contract."""

    methodology_id: str | None
    methodology_version: str
    split_specs: tuple[TechnicalRiskOOSSplitSpec, ...]
    methodology_checksum: str | None = None

    def __post_init__(self) -> None:
        if self.methodology_version != TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1:
            raise TechnicalRiskTemporalSplitMethodologyError("Unsupported methodology_version.")
        specs = tuple(self.split_specs)
        _validate_exact_split_specs(specs)
        object.__setattr__(self, "split_specs", specs)
        checksum = _methodology_checksum(self)
        identity = _stable_id("technical_risk_v1_temporal_split", {"methodology_checksum": checksum})
        if self.methodology_id is not None and self.methodology_id != identity:
            raise TechnicalRiskTemporalSplitMethodologyError("methodology_id mismatch.")
        if self.methodology_checksum is not None and self.methodology_checksum != checksum:
            raise TechnicalRiskTemporalSplitMethodologyError("methodology_checksum mismatch.")
        object.__setattr__(self, "methodology_id", identity)
        object.__setattr__(self, "methodology_checksum", checksum)

    @property
    def split_specs_by_role(self) -> Mapping[TechnicalRiskOOSSplitRole, TechnicalRiskOOSSplitSpec]:
        return MappingProxyType({spec.split_role: spec for spec in self.split_specs})

    @property
    def threshold_axis_evidence_eligible_roles(self) -> tuple[TechnicalRiskOOSSplitRole, ...]:
        return (TechnicalRiskOOSSplitRole.DEVELOPMENT,)

    @property
    def validation_selection_eligible_roles(self) -> tuple[TechnicalRiskOOSSplitRole, ...]:
        return (TechnicalRiskOOSSplitRole.VALIDATION,)

    @property
    def holdout_confirmation_eligible_roles(self) -> tuple[TechnicalRiskOOSSplitRole, ...]:
        return (TechnicalRiskOOSSplitRole.HOLDOUT,)


def build_technical_risk_v1_temporal_split_methodology() -> TechnicalRiskV1TemporalSplitMethodology:
    """Build the approved Technical Risk v1 temporal split methodology."""

    return TechnicalRiskV1TemporalSplitMethodology(
        methodology_id=None,
        methodology_version=TECHNICAL_RISK_V1_TEMPORAL_SPLIT_V1,
        split_specs=build_technical_risk_v1_temporal_split_specs(),
    )


def build_technical_risk_v1_temporal_split_specs() -> tuple[TechnicalRiskOOSSplitSpec, ...]:
    """Build exact existing OOS split specs for the approved methodology."""

    return (
        TechnicalRiskOOSSplitSpec(
            split_id="technical_risk_v1_development_2018_2021",
            split_role=TechnicalRiskOOSSplitRole.DEVELOPMENT,
            start_date=date(2018, 1, 1),
            end_date=date(2021, 12, 31),
        ),
        TechnicalRiskOOSSplitSpec(
            split_id="technical_risk_v1_validation_2022_2023",
            split_role=TechnicalRiskOOSSplitRole.VALIDATION,
            start_date=date(2022, 1, 1),
            end_date=date(2023, 12, 31),
        ),
        TechnicalRiskOOSSplitSpec(
            split_id="technical_risk_v1_holdout_2024_2025",
            split_role=TechnicalRiskOOSSplitRole.HOLDOUT,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
        ),
    )


def _validate_exact_split_specs(specs: tuple[TechnicalRiskOOSSplitSpec, ...]) -> None:
    expected = build_technical_risk_v1_temporal_split_specs()
    if specs != expected:
        raise TechnicalRiskTemporalSplitMethodologyError("Temporal split specs do not match Technical Risk v1 methodology.")
    _validate_non_overlapping_chronological(specs)


def _validate_non_overlapping_chronological(specs: tuple[TechnicalRiskOOSSplitSpec, ...]) -> None:
    previous_end: date | None = None
    for spec in specs:
        if previous_end is not None and spec.start_date <= previous_end:
            raise TechnicalRiskTemporalSplitMethodologyError("Temporal split specs must be chronological and non-overlapping.")
        previous_end = spec.end_date


def _methodology_checksum(methodology: TechnicalRiskV1TemporalSplitMethodology) -> str:
    return _stable_hash(
        {
            "methodology_version": methodology.methodology_version,
            "split_specs": [
                {
                    "split_id": spec.split_id,
                    "split_role": spec.split_role.value,
                    "start_date": spec.start_date.isoformat(),
                    "end_date": spec.end_date.isoformat(),
                }
                for spec in methodology.split_specs
            ],
            "eligibility": {
                "threshold_axis_evidence": [role.value for role in methodology.threshold_axis_evidence_eligible_roles],
                "validation_selection": [role.value for role in methodology.validation_selection_eligible_roles],
                "holdout_confirmation": [role.value for role in methodology.holdout_confirmation_eligible_roles],
            },
        }
    )


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
