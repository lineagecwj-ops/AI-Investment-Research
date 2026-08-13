from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from risk_evaluation.feature_input import RiskFeatureInput
from risk_evaluation.validation import RiskSignalProductionInputError
from risk_evaluation.validation import normalize_text_tuple
from risk_evaluation.validation import require_date
from risk_evaluation.validation import require_non_empty_text


MetadataValue = str | int | float | Decimal


@dataclass(frozen=True)
class RiskSignalProductionInput:
    """Frozen per-position input for deterministic risk signal production."""

    portfolio_id: str
    position_id: str
    symbol: str
    as_of_date: date
    valuation_date: date
    feature_version: str
    feature_values: tuple[RiskFeatureInput, ...]
    model_version: str | None
    model_metadata: Mapping[str, MetadataValue] | None
    exposure_metadata: Mapping[str, MetadataValue] | None
    source_artifact_ids: tuple[str, ...]
    source_checksums: tuple[str, ...]
    calculation_id: str

    def __post_init__(self):
        require_non_empty_text(self.portfolio_id, "portfolio_id", RiskSignalProductionInputError)
        require_non_empty_text(self.position_id, "position_id", RiskSignalProductionInputError)
        require_non_empty_text(self.symbol, "symbol", RiskSignalProductionInputError)
        require_date(self.as_of_date, "as_of_date", RiskSignalProductionInputError)
        require_date(self.valuation_date, "valuation_date", RiskSignalProductionInputError)
        require_non_empty_text(self.feature_version, "feature_version", RiskSignalProductionInputError)
        require_non_empty_text(self.calculation_id, "calculation_id", RiskSignalProductionInputError)
        if self.model_version is not None and (not isinstance(self.model_version, str) or not self.model_version):
            raise RiskSignalProductionInputError("model_version must be None or a non-empty string.")
        if not isinstance(self.feature_values, tuple):
            raise RiskSignalProductionInputError("feature_values must be a tuple.")

        ordered_features = tuple(sorted(self.feature_values, key=lambda item: item.identity))
        seen_features: set[tuple[str, str]] = set()
        for feature in ordered_features:
            if not isinstance(feature, RiskFeatureInput):
                raise RiskSignalProductionInputError("feature_values must contain RiskFeatureInput instances.")
            if feature.portfolio_id != self.portfolio_id:
                raise RiskSignalProductionInputError("feature portfolio_id mismatch.")
            if feature.position_id != self.position_id:
                raise RiskSignalProductionInputError("feature position_id mismatch.")
            if feature.symbol != self.symbol:
                raise RiskSignalProductionInputError("feature symbol mismatch.")
            if feature.as_of_date != self.as_of_date:
                raise RiskSignalProductionInputError("feature as_of_date mismatch.")
            if feature.calculation_id != self.calculation_id:
                raise RiskSignalProductionInputError("feature calculation_id mismatch.")
            if feature.identity in seen_features:
                raise RiskSignalProductionInputError("duplicate feature id/version.")
            seen_features.add(feature.identity)

        source_artifact_ids = normalize_text_tuple(
            self.source_artifact_ids,
            "source_artifact_ids",
            RiskSignalProductionInputError,
        )
        source_checksums = normalize_text_tuple(
            self.source_checksums,
            "source_checksums",
            RiskSignalProductionInputError,
        )
        if not source_artifact_ids:
            raise RiskSignalProductionInputError("source_artifact_ids cannot be empty.")
        if not source_checksums:
            raise RiskSignalProductionInputError("source_checksums cannot be empty.")
        missing_artifacts = tuple(
            feature.source_artifact_id
            for feature in ordered_features
            if feature.source_artifact_id not in source_artifact_ids
        )
        if missing_artifacts:
            raise RiskSignalProductionInputError("feature source_artifact_id is missing from source_artifact_ids.")
        missing_checksums = tuple(
            feature.source_checksum for feature in ordered_features if feature.source_checksum not in source_checksums
        )
        if missing_checksums:
            raise RiskSignalProductionInputError("feature source_checksum is missing from source_checksums.")

        object.__setattr__(self, "feature_values", ordered_features)
        object.__setattr__(self, "source_artifact_ids", source_artifact_ids)
        object.__setattr__(self, "source_checksums", source_checksums)
        object.__setattr__(self, "model_metadata", MappingProxyType(self._normalize_metadata(self.model_metadata, "model_metadata")))
        object.__setattr__(
            self,
            "exposure_metadata",
            MappingProxyType(self._normalize_metadata(self.exposure_metadata, "exposure_metadata")),
        )

    @property
    def feature_ids(self) -> tuple[str, ...]:
        return tuple(feature.feature_id for feature in self.feature_values)

    def _normalize_metadata(
        self,
        metadata: Mapping[str, MetadataValue] | None,
        field_name: str,
    ) -> dict[str, MetadataValue]:
        if metadata is None:
            return {}
        if not isinstance(metadata, Mapping):
            raise RiskSignalProductionInputError(f"{field_name} must be a mapping.")
        normalized: dict[str, MetadataValue] = {}
        for key, value in sorted(metadata.items(), key=lambda item: str(item[0])):
            if not isinstance(key, str) or not key:
                raise RiskSignalProductionInputError(f"{field_name} keys must be non-empty strings.")
            if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
                raise RiskSignalProductionInputError(f"{field_name} values must be scalar metadata.")
            normalized[key] = value
        return normalized
