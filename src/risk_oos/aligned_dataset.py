from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import hashlib
import json
from numbers import Real
from types import MappingProxyType
from typing import Iterable
from typing import Mapping

from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_oos.historical_features import FEATURE_RSI14
from risk_oos.historical_features import FEATURE_SMA20
from risk_oos.historical_features import FEATURE_SMA60
from risk_oos.historical_features import HISTORICAL_RISK_FEATURE_SET_V1
from risk_oos.historical_features import HistoricalRiskFeatureExclusion
from risk_oos.historical_features import HistoricalRiskFeatureObservation
from targets import TARGET_ARTIFACT_SCHEMA_VERSION
from targets import TARGET_CHECKSUM_CONTRACT_VERSION
from targets import TargetArtifact


TARGET_MAE20 = "TARGET_MAE_20D_REG_V1"
TARGET_MAE60 = "TARGET_MAE_60D_REG_V1"
TARGET_VERSION_V1 = "v1"
TECHNICAL_RISK_OOS_DATASET_SCHEMA_VERSION = "technical_risk_oos_dataset_v1"
TECHNICAL_RISK_OOS_DATASET_BUILDER_VERSION = "technical_risk_oos_aligned_dataset_builder_v1"
TECHNICAL_RISK_V1_FEATURE_SET_ID = "technical_risk_v1_required_features"
TECHNICAL_RISK_V1_TARGET_IDENTITIES = (
    (TARGET_MAE20, TARGET_VERSION_V1),
    (TARGET_MAE60, TARGET_VERSION_V1),
)


class TechnicalRiskOOSDatasetError(Exception):
    """Raised when aligned OOS dataset configuration is corrupt."""


class TechnicalRiskOOSSplitRole(StrEnum):
    DEVELOPMENT = "DEVELOPMENT"
    VALIDATION = "VALIDATION"
    HOLDOUT = "HOLDOUT"


class TechnicalRiskOOSExclusionReason(StrEnum):
    EXCLUDED_INCOMPLETE_MAE20 = "EXCLUDED_INCOMPLETE_MAE20"
    EXCLUDED_INCOMPLETE_MAE60 = "EXCLUDED_INCOMPLETE_MAE60"
    EXCLUDED_TARGET_ALIGNMENT_MISMATCH = "EXCLUDED_TARGET_ALIGNMENT_MISMATCH"
    EXCLUDED_TARGET_CROSSES_SPLIT_BOUNDARY = "EXCLUDED_TARGET_CROSSES_SPLIT_BOUNDARY"
    EXCLUDED_OUTSIDE_SPLIT = "EXCLUDED_OUTSIDE_SPLIT"
    EXCLUDED_DUPLICATE_OBSERVATION = "EXCLUDED_DUPLICATE_OBSERVATION"
    EXCLUDED_DUPLICATE_TARGET = "EXCLUDED_DUPLICATE_TARGET"
    UPSTREAM_FEATURE_EXCLUSION = "UPSTREAM_FEATURE_EXCLUSION"


@dataclass(frozen=True)
class TechnicalRiskOOSSplitSpec:
    """Inclusive OOS split membership definition."""

    split_id: str
    split_role: TechnicalRiskOOSSplitRole
    start_date: date
    end_date: date

    def __post_init__(self):
        _require_text(self.split_id, "split_id")
        _require_date(self.start_date, "start_date")
        _require_date(self.end_date, "end_date")
        if not isinstance(self.split_role, TechnicalRiskOOSSplitRole):
            object.__setattr__(self, "split_role", TechnicalRiskOOSSplitRole(self.split_role))
        if self.start_date > self.end_date:
            raise TechnicalRiskOOSDatasetError("split start_date cannot be after end_date.")


@dataclass(frozen=True)
class TechnicalRiskOOSDatasetSpec:
    """Research-scoped aligned Technical Risk v1 OOS dataset specification."""

    dataset_spec_id: str
    dataset_spec_version: str
    feature_set_id: str
    split_specs: tuple[TechnicalRiskOOSSplitSpec, ...]
    required_feature_ids: tuple[str, ...] = HISTORICAL_RISK_FEATURE_SET_V1
    required_target_identities: tuple[tuple[str, str], ...] = TECHNICAL_RISK_V1_TARGET_IDENTITIES
    builder_version: str = TECHNICAL_RISK_OOS_DATASET_BUILDER_VERSION
    schema_version: str = TECHNICAL_RISK_OOS_DATASET_SCHEMA_VERSION

    def __post_init__(self):
        _require_text(self.dataset_spec_id, "dataset_spec_id")
        _require_text(self.dataset_spec_version, "dataset_spec_version")
        _require_text(self.feature_set_id, "feature_set_id")
        _require_text(self.builder_version, "builder_version")
        _require_text(self.schema_version, "schema_version")
        object.__setattr__(self, "split_specs", tuple(self.split_specs))
        if tuple(self.required_feature_ids) != HISTORICAL_RISK_FEATURE_SET_V1:
            raise TechnicalRiskOOSDatasetError("Technical Risk v1 dataset requires the exact feature set.")
        if tuple(self.required_target_identities) != TECHNICAL_RISK_V1_TARGET_IDENTITIES:
            raise TechnicalRiskOOSDatasetError("Technical Risk v1 dataset requires exact MAE target identities.")
        _validate_split_specs(self.split_specs)


@dataclass(frozen=True)
class AlignedTechnicalRiskOOSRow:
    """Self-contained aligned row for Technical Risk v1 OOS research."""

    row_id: str
    observation_id: str
    symbol: str
    evaluation_date: date
    as_of_close: float
    sma20: float
    sma60: float
    rsi14: float
    feature_observation_checksum: str
    mae20_value: float
    mae20_target_checksum: str
    mae20_calculation_id: str
    mae20_target_start_date: date
    mae20_target_end_date: date
    mae60_value: float
    mae60_target_checksum: str
    mae60_calculation_id: str
    mae60_target_start_date: date
    mae60_target_end_date: date
    split_id: str
    split_role: TechnicalRiskOOSSplitRole
    dataset_spec_id: str
    dataset_spec_version: str


@dataclass(frozen=True)
class TechnicalRiskOOSExclusionRecord:
    """Deterministic row-level exclusion accounting."""

    exclusion_id: str
    symbol: str
    evaluation_date: date
    reason: TechnicalRiskOOSExclusionReason
    dataset_spec_id: str
    dataset_spec_version: str
    observation_id: str | None = None
    observation_checksum: str | None = None
    feature_set_id: str | None = None
    target_id: str | None = None
    target_version: str | None = None
    target_checksum: str | None = None
    split_id: str | None = None
    upstream_exclusion_id: str | None = None
    upstream_reason: str | None = None
    detail_code: str | None = None


@dataclass(frozen=True)
class TechnicalRiskOOSDatasetResult:
    """Deterministic aligned OOS dataset build result."""

    included_rows: tuple[AlignedTechnicalRiskOOSRow, ...]
    excluded_records: tuple[TechnicalRiskOOSExclusionRecord, ...]
    dataset_id: str
    dataset_checksum: str
    summary_counts: Mapping[str, int]

    def __post_init__(self):
        object.__setattr__(self, "included_rows", tuple(self.included_rows))
        object.__setattr__(self, "excluded_records", tuple(self.excluded_records))
        object.__setattr__(self, "summary_counts", MappingProxyType(dict(self.summary_counts)))


class TechnicalRiskOOSDatasetBuilder:
    """Aligns frozen historical risk features with frozen MAE targets and OOS splits."""

    def build(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        feature_observations: Iterable[HistoricalRiskFeatureObservation],
        mae20_targets: Iterable[TargetArtifact],
        mae60_targets: Iterable[TargetArtifact],
        upstream_feature_exclusions: Iterable[HistoricalRiskFeatureExclusion] = (),
    ) -> TechnicalRiskOOSDatasetResult:
        observations = tuple(feature_observations)
        mae20_index = self._target_index(tuple(mae20_targets), TARGET_MAE20, 20)
        mae60_index = self._target_index(tuple(mae60_targets), TARGET_MAE60, 60)
        observation_groups = self._observation_groups(observations, spec)
        observation_dates_by_symbol = self._observation_dates_by_symbol(observations)

        rows: list[AlignedTechnicalRiskOOSRow] = []
        exclusions: list[TechnicalRiskOOSExclusionRecord] = []
        for key in sorted(observation_groups, key=lambda item: (item[0], item[1], item[2])):
            grouped = observation_groups[key]
            if len(grouped) != 1:
                exclusions.append(self._exclude_duplicate_observation(spec, grouped))
                continue
            observation = grouped[0]
            split = self._split_for_date(spec, observation.evaluation_date)
            if split is None:
                exclusions.append(self._exclude_observation(spec, observation, TechnicalRiskOOSExclusionReason.EXCLUDED_OUTSIDE_SPLIT))
                continue
            mae20_key = (observation.symbol, observation.evaluation_date, TARGET_MAE20, TARGET_VERSION_V1)
            mae60_key = (observation.symbol, observation.evaluation_date, TARGET_MAE60, TARGET_VERSION_V1)
            mae20_status = mae20_index.get(mae20_key)
            mae60_status = mae60_index.get(mae60_key)
            exclusion = self._target_exclusion(
                spec,
                observation,
                split,
                mae20_key,
                mae60_key,
                mae20_status,
                mae60_status,
                mae20_index,
                mae60_index,
                observation_dates_by_symbol,
            )
            if exclusion is not None:
                exclusions.append(exclusion)
                continue
            rows.append(self._row(spec, observation, split, mae20_status.artifact, mae60_status.artifact))

        exclusions.extend(
            self._upstream_exclusion(spec, upstream)
            for upstream in sorted(
                tuple(upstream_feature_exclusions),
                key=lambda item: (item.symbol, item.evaluation_date, item.reason, item.exclusion_id),
            )
        )
        ordered_rows = tuple(sorted(rows, key=_row_sort_key))
        ordered_exclusions = tuple(sorted(exclusions, key=_exclusion_sort_key))
        summary = self._summary_counts(observations, ordered_rows, ordered_exclusions)
        checksum = self._dataset_checksum(spec, ordered_rows, ordered_exclusions)
        dataset_id = _stable_id(
            "technical_risk_oos_dataset",
            {
                "dataset_spec_id": spec.dataset_spec_id,
                "dataset_spec_version": spec.dataset_spec_version,
                "dataset_checksum": checksum,
            },
        )
        return TechnicalRiskOOSDatasetResult(
            included_rows=ordered_rows,
            excluded_records=ordered_exclusions,
            dataset_id=dataset_id,
            dataset_checksum=checksum,
            summary_counts=summary,
        )

    def _observation_groups(
        self,
        observations: tuple[HistoricalRiskFeatureObservation, ...],
        spec: TechnicalRiskOOSDatasetSpec,
    ) -> dict[tuple[str, date, str], tuple[HistoricalRiskFeatureObservation, ...]]:
        groups: dict[tuple[str, date, str], list[HistoricalRiskFeatureObservation]] = {}
        for observation in observations:
            self._validate_observation_contract(observation, spec)
            key = (observation.symbol, observation.evaluation_date, observation.feature_set_id)
            groups.setdefault(key, []).append(observation)
        return {key: tuple(value) for key, value in groups.items()}

    def _target_index(
        self,
        targets: tuple[TargetArtifact, ...],
        expected_target_id: str,
        expected_window: int,
    ) -> dict[tuple[str, date, str, str], "_TargetStatus"]:
        groups: dict[tuple[str, date, str, str], list[TargetArtifact]] = {}
        for target in targets:
            if target.target_id != expected_target_id or target.target_version != TARGET_VERSION_V1:
                raise TechnicalRiskOOSDatasetError("Unsupported target definition for Technical Risk v1 aligned dataset.")
            key = (target.symbol, target.reference_date, target.target_id, target.target_version)
            groups.setdefault(key, []).append(target)

        indexed: dict[tuple[str, date, str, str], _TargetStatus] = {}
        for key, grouped in groups.items():
            if len(grouped) != 1:
                duplicate_signature = _stable_hash(
                    {
                        "duplicates": [
                            {
                                "checksum": item.checksum,
                                "calculation_id": item.calculation_id,
                                "target_value": item.target_value,
                                "target_start_date": (
                                    item.window_lineage.target_start_date.isoformat()
                                    if item.window_lineage is not None
                                    else None
                                ),
                                "target_end_date": (
                                    item.window_lineage.target_end_date.isoformat()
                                    if item.window_lineage is not None
                                    else None
                                ),
                            }
                            for item in sorted(grouped, key=lambda value: (value.checksum or "", value.calculation_id, str(value.target_value)))
                        ]
                    }
                )[:16]
                indexed[key] = _TargetStatus(duplicate=True, contract_error=f"DUPLICATE_TARGET:{duplicate_signature}")
                continue
            target = grouped[0]
            error = self._target_contract_error(target, expected_window)
            indexed[key] = _TargetStatus(artifact=target, contract_error=error)
        return indexed

    def _target_contract_error(self, target: TargetArtifact, expected_window: int) -> str | None:
        if target.validation_status != "PASS":
            return "TARGET_VALIDATION_NOT_PASS"
        if target.checksum is None:
            return "TARGET_CHECKSUM_MISSING"
        if target.schema_version != TARGET_ARTIFACT_SCHEMA_VERSION:
            return "TARGET_SCHEMA_VERSION_MISMATCH"
        if target.checksum_contract_version != TARGET_CHECKSUM_CONTRACT_VERSION:
            return "TARGET_CHECKSUM_CONTRACT_MISMATCH"
        if target.window_lineage is None:
            return "TARGET_WINDOW_LINEAGE_MISSING"
        if target.window_lineage.observations_used != expected_window:
            return "TARGET_WINDOW_OBSERVATIONS_MISMATCH"
        if target.reference_date >= target.window_lineage.target_start_date:
            return "TARGET_WINDOW_START_NOT_AFTER_REFERENCE"
        if not _is_number(target.target_value):
            return "TARGET_VALUE_INVALID"
        return None

    def _target_exclusion(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        observation: HistoricalRiskFeatureObservation,
        split: TechnicalRiskOOSSplitSpec,
        mae20_key: tuple[str, date, str, str],
        mae60_key: tuple[str, date, str, str],
        mae20_status: "_TargetStatus | None",
        mae60_status: "_TargetStatus | None",
        mae20_index: dict[tuple[str, date, str, str], "_TargetStatus"],
        mae60_index: dict[tuple[str, date, str, str], "_TargetStatus"],
        observation_dates_by_symbol: dict[str, frozenset[date]],
    ) -> TechnicalRiskOOSExclusionRecord | None:
        if mae20_status is not None and mae20_status.duplicate:
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_DUPLICATE_TARGET,
                split_id=split.split_id,
                target_id=TARGET_MAE20,
                target_version=TARGET_VERSION_V1,
                detail_code=mae20_status.contract_error,
            )
        if mae60_status is not None and mae60_status.duplicate:
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_DUPLICATE_TARGET,
                split_id=split.split_id,
                target_id=TARGET_MAE60,
                target_version=TARGET_VERSION_V1,
                detail_code=mae60_status.contract_error,
            )
        if mae20_status is not None and mae20_status.contract_error is not None:
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_ALIGNMENT_MISMATCH,
                split_id=split.split_id,
                target_id=TARGET_MAE20,
                target_version=TARGET_VERSION_V1,
                target_checksum=mae20_status.artifact.checksum,
                detail_code=mae20_status.contract_error,
            )
        if mae60_status is not None and mae60_status.contract_error is not None:
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_ALIGNMENT_MISMATCH,
                split_id=split.split_id,
                target_id=TARGET_MAE60,
                target_version=TARGET_VERSION_V1,
                target_checksum=mae60_status.artifact.checksum,
                detail_code=mae60_status.contract_error,
            )
        if mae20_status is None and self._has_misaligned_target(mae20_index, mae20_key, observation_dates_by_symbol):
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_ALIGNMENT_MISMATCH,
                split_id=split.split_id,
                target_id=TARGET_MAE20,
                target_version=TARGET_VERSION_V1,
                detail_code="TARGET_REFERENCE_DATE_MISMATCH",
            )
        if mae60_status is None and self._has_misaligned_target(mae60_index, mae60_key, observation_dates_by_symbol):
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_ALIGNMENT_MISMATCH,
                split_id=split.split_id,
                target_id=TARGET_MAE60,
                target_version=TARGET_VERSION_V1,
                detail_code="TARGET_REFERENCE_DATE_MISMATCH",
            )
        if mae20_status is None:
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_INCOMPLETE_MAE20,
                split_id=split.split_id,
                target_id=TARGET_MAE20,
                target_version=TARGET_VERSION_V1,
            )
        if mae60_status is None:
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_INCOMPLETE_MAE60,
                split_id=split.split_id,
                target_id=TARGET_MAE60,
                target_version=TARGET_VERSION_V1,
            )
        if (
            mae20_status.artifact.window_lineage.target_end_date > split.end_date
            or mae60_status.artifact.window_lineage.target_end_date > split.end_date
        ):
            return self._exclude_observation(
                spec,
                observation,
                TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_CROSSES_SPLIT_BOUNDARY,
                split_id=split.split_id,
                target_id="TARGET_MAE_20D_REG_V1+TARGET_MAE_60D_REG_V1",
                detail_code="TARGET_END_AFTER_SPLIT_END",
            )
        return None

    def _has_misaligned_target(
        self,
        index: dict[tuple[str, date, str, str], "_TargetStatus"],
        key: tuple[str, date, str, str],
        observation_dates_by_symbol: dict[str, frozenset[date]],
    ) -> bool:
        symbol, reference_date, target_id, target_version = key
        observation_dates = observation_dates_by_symbol.get(symbol, frozenset())
        return any(
            indexed_symbol == symbol
            and indexed_reference_date != reference_date
            and indexed_reference_date not in observation_dates
            and indexed_target_id == target_id
            and indexed_target_version == target_version
            for indexed_symbol, indexed_reference_date, indexed_target_id, indexed_target_version in index
        )

    def _observation_dates_by_symbol(
        self,
        observations: tuple[HistoricalRiskFeatureObservation, ...],
    ) -> dict[str, frozenset[date]]:
        grouped: dict[str, set[date]] = {}
        for observation in observations:
            grouped.setdefault(observation.symbol, set()).add(observation.evaluation_date)
        return {symbol: frozenset(dates) for symbol, dates in grouped.items()}

    def _row(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        observation: HistoricalRiskFeatureObservation,
        split: TechnicalRiskOOSSplitSpec,
        mae20: TargetArtifact,
        mae60: TargetArtifact,
    ) -> AlignedTechnicalRiskOOSRow:
        row_payload = {
            "observation_id": observation.observation_id,
            "observation_checksum": observation.observation_checksum,
            "mae20_checksum": mae20.checksum,
            "mae60_checksum": mae60.checksum,
            "split_id": split.split_id,
            "split_role": split.split_role.value,
            "dataset_spec_id": spec.dataset_spec_id,
            "dataset_spec_version": spec.dataset_spec_version,
        }
        return AlignedTechnicalRiskOOSRow(
            row_id=_stable_id("technical_risk_oos_row", row_payload),
            observation_id=observation.observation_id,
            symbol=observation.symbol,
            evaluation_date=observation.evaluation_date,
            as_of_close=observation.as_of_close,
            sma20=observation.sma20,
            sma60=observation.sma60,
            rsi14=observation.rsi14,
            feature_observation_checksum=observation.observation_checksum,
            mae20_value=float(mae20.target_value),
            mae20_target_checksum=mae20.checksum,
            mae20_calculation_id=mae20.calculation_id,
            mae20_target_start_date=mae20.window_lineage.target_start_date,
            mae20_target_end_date=mae20.window_lineage.target_end_date,
            mae60_value=float(mae60.target_value),
            mae60_target_checksum=mae60.checksum,
            mae60_calculation_id=mae60.calculation_id,
            mae60_target_start_date=mae60.window_lineage.target_start_date,
            mae60_target_end_date=mae60.window_lineage.target_end_date,
            split_id=split.split_id,
            split_role=split.split_role,
            dataset_spec_id=spec.dataset_spec_id,
            dataset_spec_version=spec.dataset_spec_version,
        )

    def _split_for_date(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        evaluation_date: date,
    ) -> TechnicalRiskOOSSplitSpec | None:
        matches = tuple(split for split in spec.split_specs if split.start_date <= evaluation_date <= split.end_date)
        if len(matches) > 1:
            raise TechnicalRiskOOSDatasetError("Ambiguous split membership.")
        return matches[0] if matches else None

    def _validate_observation_contract(
        self,
        observation: HistoricalRiskFeatureObservation,
        spec: TechnicalRiskOOSDatasetSpec,
    ) -> None:
        if observation.feature_set_id != spec.feature_set_id:
            raise TechnicalRiskOOSDatasetError("Observation feature_set_id does not match dataset specification.")
        if tuple(observation.feature_ids) != spec.required_feature_ids:
            raise TechnicalRiskOOSDatasetError("Observation does not contain the exact Technical Risk v1 feature set.")
        for feature_id in spec.required_feature_ids:
            if observation.feature_versions.get(feature_id) != "v1":
                raise TechnicalRiskOOSDatasetError("Observation feature version mismatch.")
        for value in (observation.as_of_close, observation.sma20, observation.sma60, observation.rsi14):
            if not _is_number(value):
                raise TechnicalRiskOOSDatasetError("Observation feature value must be numeric.")
        if observation.as_of_close <= 0:
            raise TechnicalRiskOOSDatasetError("Observation as_of_close must be positive.")

    def _exclude_duplicate_observation(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        observations: tuple[HistoricalRiskFeatureObservation, ...],
    ) -> TechnicalRiskOOSExclusionRecord:
        first = sorted(observations, key=lambda item: (item.observation_id, item.observation_checksum))[0]
        duplicate_signature = _stable_hash(
            {
                "duplicates": [
                    {
                        "observation_id": item.observation_id,
                        "observation_checksum": item.observation_checksum,
                    }
                    for item in sorted(observations, key=lambda value: (value.observation_id, value.observation_checksum))
                ]
            }
        )[:16]
        return self._exclude_observation(
            spec,
            first,
            TechnicalRiskOOSExclusionReason.EXCLUDED_DUPLICATE_OBSERVATION,
            detail_code=f"DUPLICATE_SYMBOL_EVALUATION_DATE_FEATURE_SET:{duplicate_signature}",
        )

    def _exclude_observation(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        observation: HistoricalRiskFeatureObservation,
        reason: TechnicalRiskOOSExclusionReason,
        *,
        split_id: str | None = None,
        target_id: str | None = None,
        target_version: str | None = None,
        target_checksum: str | None = None,
        detail_code: str | None = None,
    ) -> TechnicalRiskOOSExclusionRecord:
        payload = {
            "symbol": observation.symbol,
            "evaluation_date": observation.evaluation_date.isoformat(),
            "reason": reason.value,
            "observation_id": observation.observation_id,
            "observation_checksum": observation.observation_checksum,
            "split_id": split_id,
            "target_id": target_id,
            "target_version": target_version,
            "target_checksum": target_checksum,
            "detail_code": detail_code,
            "dataset_spec_id": spec.dataset_spec_id,
            "dataset_spec_version": spec.dataset_spec_version,
        }
        return TechnicalRiskOOSExclusionRecord(
            exclusion_id=_stable_id("technical_risk_oos_exclusion", payload),
            symbol=observation.symbol,
            evaluation_date=observation.evaluation_date,
            reason=reason,
            dataset_spec_id=spec.dataset_spec_id,
            dataset_spec_version=spec.dataset_spec_version,
            observation_id=observation.observation_id,
            observation_checksum=observation.observation_checksum,
            feature_set_id=observation.feature_set_id,
            target_id=target_id,
            target_version=target_version,
            target_checksum=target_checksum,
            split_id=split_id,
            detail_code=detail_code,
        )

    def _upstream_exclusion(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        upstream: HistoricalRiskFeatureExclusion,
    ) -> TechnicalRiskOOSExclusionRecord:
        payload = {
            "upstream_exclusion_id": upstream.exclusion_id,
            "upstream_reason": upstream.reason,
            "dataset_spec_id": spec.dataset_spec_id,
            "dataset_spec_version": spec.dataset_spec_version,
        }
        return TechnicalRiskOOSExclusionRecord(
            exclusion_id=_stable_id("technical_risk_oos_upstream_exclusion", payload),
            symbol=upstream.symbol,
            evaluation_date=upstream.evaluation_date,
            reason=TechnicalRiskOOSExclusionReason.UPSTREAM_FEATURE_EXCLUSION,
            dataset_spec_id=spec.dataset_spec_id,
            dataset_spec_version=spec.dataset_spec_version,
            feature_set_id=upstream.feature_set_id,
            upstream_exclusion_id=upstream.exclusion_id,
            upstream_reason=upstream.reason,
            detail_code=upstream.feature_id,
        )

    def _summary_counts(
        self,
        observations: tuple[HistoricalRiskFeatureObservation, ...],
        rows: tuple[AlignedTechnicalRiskOOSRow, ...],
        exclusions: tuple[TechnicalRiskOOSExclusionRecord, ...],
    ) -> dict[str, int]:
        counts: dict[str, int] = {
            "input_feature_observations": len(observations),
            "included_rows": len(rows),
            "total_excluded": len(exclusions),
            "development_included": sum(1 for row in rows if row.split_role == TechnicalRiskOOSSplitRole.DEVELOPMENT),
            "validation_included": sum(1 for row in rows if row.split_role == TechnicalRiskOOSSplitRole.VALIDATION),
            "holdout_included": sum(1 for row in rows if row.split_role == TechnicalRiskOOSSplitRole.HOLDOUT),
        }
        for reason in TechnicalRiskOOSExclusionReason:
            counts[f"excluded_{reason.value.lower()}"] = sum(1 for exclusion in exclusions if exclusion.reason == reason)
        return counts

    def _dataset_checksum(
        self,
        spec: TechnicalRiskOOSDatasetSpec,
        rows: tuple[AlignedTechnicalRiskOOSRow, ...],
        exclusions: tuple[TechnicalRiskOOSExclusionRecord, ...],
    ) -> str:
        return _stable_hash(
            {
                "dataset_spec_id": spec.dataset_spec_id,
                "dataset_spec_version": spec.dataset_spec_version,
                "schema_version": spec.schema_version,
                "builder_version": spec.builder_version,
                "feature_set_id": spec.feature_set_id,
                "required_feature_ids": spec.required_feature_ids,
                "required_target_identities": spec.required_target_identities,
                "split_specs": [
                    {
                        "split_id": split.split_id,
                        "split_role": split.split_role.value,
                        "start_date": split.start_date.isoformat(),
                        "end_date": split.end_date.isoformat(),
                    }
                    for split in sorted(spec.split_specs, key=_split_sort_key)
                ],
                "included_rows": [_row_payload(row) for row in rows],
                "excluded_records": [_exclusion_payload(exclusion) for exclusion in exclusions],
            }
        )


@dataclass(frozen=True)
class _TargetStatus:
    artifact: TargetArtifact | None = None
    duplicate: bool = False
    contract_error: str | None = None


def _validate_split_specs(split_specs: tuple[TechnicalRiskOOSSplitSpec, ...]) -> None:
    if not split_specs:
        raise TechnicalRiskOOSDatasetError("At least one split spec is required.")
    split_ids: set[str] = set()
    sorted_splits = sorted(split_specs, key=_split_sort_key)
    for split in sorted_splits:
        if split.split_id in split_ids:
            raise TechnicalRiskOOSDatasetError("Duplicate split_id in Technical Risk OOS dataset spec.")
        split_ids.add(split.split_id)
    for previous, current in zip(sorted_splits, sorted_splits[1:]):
        if current.start_date <= previous.end_date:
            raise TechnicalRiskOOSDatasetError("Overlapping split ranges in Technical Risk OOS dataset spec.")


def _split_sort_key(split: TechnicalRiskOOSSplitSpec) -> tuple[int, date, str]:
    return (_split_role_order(split.split_role), split.start_date, split.split_id)


def _split_role_order(role: TechnicalRiskOOSSplitRole) -> int:
    return {
        TechnicalRiskOOSSplitRole.DEVELOPMENT: 0,
        TechnicalRiskOOSSplitRole.VALIDATION: 1,
        TechnicalRiskOOSSplitRole.HOLDOUT: 2,
    }[role]


def _row_sort_key(row: AlignedTechnicalRiskOOSRow) -> tuple[int, str, date, str]:
    return (_split_role_order(row.split_role), row.symbol, row.evaluation_date, row.observation_id)


def _exclusion_sort_key(record: TechnicalRiskOOSExclusionRecord) -> tuple[str, date, str, str, str]:
    return (
        record.symbol,
        record.evaluation_date,
        record.reason.value,
        record.target_id or "",
        record.observation_id or record.upstream_exclusion_id or "",
    )


def _row_payload(row: AlignedTechnicalRiskOOSRow) -> dict[str, object]:
    return {
        "row_id": row.row_id,
        "observation_id": row.observation_id,
        "symbol": row.symbol,
        "evaluation_date": row.evaluation_date.isoformat(),
        "as_of_close": row.as_of_close,
        "sma20": row.sma20,
        "sma60": row.sma60,
        "rsi14": row.rsi14,
        "feature_observation_checksum": row.feature_observation_checksum,
        "mae20_value": row.mae20_value,
        "mae20_target_checksum": row.mae20_target_checksum,
        "mae20_calculation_id": row.mae20_calculation_id,
        "mae20_target_start_date": row.mae20_target_start_date.isoformat(),
        "mae20_target_end_date": row.mae20_target_end_date.isoformat(),
        "mae60_value": row.mae60_value,
        "mae60_target_checksum": row.mae60_target_checksum,
        "mae60_calculation_id": row.mae60_calculation_id,
        "mae60_target_start_date": row.mae60_target_start_date.isoformat(),
        "mae60_target_end_date": row.mae60_target_end_date.isoformat(),
        "split_id": row.split_id,
        "split_role": row.split_role.value,
        "dataset_spec_id": row.dataset_spec_id,
        "dataset_spec_version": row.dataset_spec_version,
    }


def _exclusion_payload(record: TechnicalRiskOOSExclusionRecord) -> dict[str, object]:
    return {
        "exclusion_id": record.exclusion_id,
        "symbol": record.symbol,
        "evaluation_date": record.evaluation_date.isoformat(),
        "reason": record.reason.value,
        "dataset_spec_id": record.dataset_spec_id,
        "dataset_spec_version": record.dataset_spec_version,
        "observation_id": record.observation_id,
        "observation_checksum": record.observation_checksum,
        "feature_set_id": record.feature_set_id,
        "target_id": record.target_id,
        "target_version": record.target_version,
        "target_checksum": record.target_checksum,
        "split_id": record.split_id,
        "upstream_exclusion_id": record.upstream_exclusion_id,
        "upstream_reason": record.upstream_reason,
        "detail_code": record.detail_code,
    }


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskOOSDatasetError(f"{field_name} must be a non-empty string.")


def _require_date(value: object, field_name: str) -> None:
    if not isinstance(value, date):
        raise TechnicalRiskOOSDatasetError(f"{field_name} must be a date.")


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, MappingProxyType):
        return dict(value)
    return value
