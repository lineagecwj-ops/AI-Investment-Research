from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import hashlib
from types import MappingProxyType
from typing import Iterable
from typing import Mapping

from features.calculators import PriceVolumePoint
from research_data_store import ResearchDataStore
from research_data_store import ResearchDataStoreError
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetBuilder
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetError
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetResult
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetSpec
from risk_oos.aligned_dataset import TechnicalRiskOOSExclusionReason
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitSpec
from risk_oos.historical_features import EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY
from risk_oos.historical_features import HistoricalRiskFeatureExclusion
from risk_oos.historical_features import HistoricalRiskFeatureMaterializationContext
from risk_oos.historical_features import HistoricalRiskFeatureMaterializer
from risk_oos.historical_features import HistoricalRiskFeatureObservation
from risk_oos.historical_features import HistoricalRiskFeatureStatus
from targets import MaximumAdverseExcursion20DRegressionGenerator
from targets import MaximumAdverseExcursion60DRegressionGenerator
from targets import TargetArtifact
from targets import TargetArtifactGenerationError
from targets import TargetArtifactGenerator
from targets import TargetCalculationContext
from targets import TargetPricePoint


TECHNICAL_RISK_REAL_OOS_MATERIALIZER_VERSION = "technical_risk_real_oos_materializer_v1"
PRICE_BASIS_DAILY_CLOSE = "daily_close"


class TechnicalRiskRealOOSDatasetMaterializationError(Exception):
    """Raised when real OOS dataset materialization cannot safely continue."""


@dataclass(frozen=True)
class TechnicalRiskRealOOSDatasetMaterializationRequest:
    """Explicit request for read-only real Technical Risk v1 OOS materialization."""

    research_db_path: Path | str
    research_manifest_path: Path | str
    source_snapshot_id: str
    source_snapshot_checksum: str
    symbols: tuple[str, ...]
    analysis_start_date: date
    analysis_end_date: date
    split_specs: tuple[TechnicalRiskOOSSplitSpec, ...]
    dataset_spec_id: str
    dataset_spec_version: str
    feature_set_id: str
    required_output_split_roles: tuple[TechnicalRiskOOSSplitRole, ...] = (
        TechnicalRiskOOSSplitRole.VALIDATION,
        TechnicalRiskOOSSplitRole.HOLDOUT,
    )
    materializer_version: str = TECHNICAL_RISK_REAL_OOS_MATERIALIZER_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_db_path", Path(self.research_db_path))
        object.__setattr__(self, "research_manifest_path", Path(self.research_manifest_path))
        object.__setattr__(self, "symbols", _normalize_symbols(self.symbols))
        object.__setattr__(self, "split_specs", tuple(self.split_specs))
        object.__setattr__(self, "required_output_split_roles", _normalize_required_output_split_roles(self.required_output_split_roles))
        _require_text(self.source_snapshot_id, "source_snapshot_id")
        _require_text(self.source_snapshot_checksum, "source_snapshot_checksum")
        _require_text(self.dataset_spec_id, "dataset_spec_id")
        _require_text(self.dataset_spec_version, "dataset_spec_version")
        _require_text(self.feature_set_id, "feature_set_id")
        _require_text(self.materializer_version, "materializer_version")
        _require_date(self.analysis_start_date, "analysis_start_date")
        _require_date(self.analysis_end_date, "analysis_end_date")
        if self.analysis_start_date > self.analysis_end_date:
            raise TechnicalRiskRealOOSDatasetMaterializationError("analysis_start_date cannot be after analysis_end_date.")
        _reject_production_path(self.research_db_path, "research_db_path")
        _reject_production_path(self.research_manifest_path, "research_manifest_path")
        _require_split_roles(self.split_specs)


@dataclass(frozen=True)
class TechnicalRiskRealOOSDatasetMaterializationResult:
    """In-memory result for a real Technical Risk v1 OOS materialization run."""

    oos_dataset_result: TechnicalRiskOOSDatasetResult
    feature_observation_count: int
    feature_exclusion_count: int
    mae20_artifact_count: int
    mae60_artifact_count: int
    aligned_row_count: int
    split_counts: Mapping[str, int]
    excluded_insufficient_feature_history_count: int
    excluded_incomplete_mae20_count: int
    excluded_incomplete_mae60_count: int
    excluded_split_leakage_count: int
    price_basis: str = PRICE_BASIS_DAILY_CLOSE
    materializer_version: str = TECHNICAL_RISK_REAL_OOS_MATERIALIZER_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "split_counts", MappingProxyType(dict(self.split_counts)))


class TechnicalRiskRealOOSDatasetMaterializer:
    """Materializes real read-only Technical Risk v1 OOS datasets in memory."""

    def __init__(
        self,
        *,
        dataset_builder: TechnicalRiskOOSDatasetBuilder | None = None,
        target_artifact_generator: TargetArtifactGenerator | None = None,
    ) -> None:
        self._dataset_builder = dataset_builder or TechnicalRiskOOSDatasetBuilder()
        self._target_artifact_generator = target_artifact_generator or TargetArtifactGenerator()

    def materialize(
        self,
        request: TechnicalRiskRealOOSDatasetMaterializationRequest,
    ) -> TechnicalRiskRealOOSDatasetMaterializationResult:
        store = self._verified_read_only_store(request)
        dataset_spec = TechnicalRiskOOSDatasetSpec(
            dataset_spec_id=request.dataset_spec_id,
            dataset_spec_version=request.dataset_spec_version,
            feature_set_id=request.feature_set_id,
            split_specs=request.split_specs,
        )

        feature_observations: list[HistoricalRiskFeatureObservation] = []
        feature_exclusions: list[HistoricalRiskFeatureExclusion] = []
        mae20_targets: list[TargetArtifact] = []
        mae60_targets: list[TargetArtifact] = []

        for symbol in request.symbols:
            series = store.load_historical_price_series(symbol)
            self._validate_unique_raw_dates(symbol, (bar.trading_date for bar in series.bars))
            feature_points = self._feature_points(series.bars)
            target_points = self._target_points(series.bars)
            feature_materializer = HistoricalRiskFeatureMaterializer(feature_points)
            mae20_generator = MaximumAdverseExcursion20DRegressionGenerator(target_points)
            mae60_generator = MaximumAdverseExcursion60DRegressionGenerator(target_points)
            for evaluation_date in self._evaluation_dates(series.bars, request):
                self._materialize_feature(
                    request,
                    symbol,
                    evaluation_date,
                    feature_materializer,
                    feature_observations,
                    feature_exclusions,
                )
                artifact = self._materialize_mae(request, symbol, evaluation_date, 20, mae20_generator)
                if artifact is not None:
                    mae20_targets.append(artifact)
                artifact = self._materialize_mae(request, symbol, evaluation_date, 60, mae60_generator)
                if artifact is not None:
                    mae60_targets.append(artifact)

        if not feature_observations:
            raise TechnicalRiskRealOOSDatasetMaterializationError("No eligible feature observations were materialized.")

        try:
            dataset_result = self._dataset_builder.build(
                dataset_spec,
                feature_observations,
                mae20_targets,
                mae60_targets,
                upstream_feature_exclusions=feature_exclusions,
            )
        except TechnicalRiskOOSDatasetError as exc:
            raise TechnicalRiskRealOOSDatasetMaterializationError(f"OOS dataset build failed: {exc}") from exc

        _validate_required_output_splits(dataset_result, request.required_output_split_roles)

        return TechnicalRiskRealOOSDatasetMaterializationResult(
            oos_dataset_result=dataset_result,
            feature_observation_count=len(feature_observations),
            feature_exclusion_count=len(feature_exclusions),
            mae20_artifact_count=len(mae20_targets),
            mae60_artifact_count=len(mae60_targets),
            aligned_row_count=len(dataset_result.included_rows),
            split_counts={
                "development": dataset_result.summary_counts.get("development_included", 0),
                "validation": dataset_result.summary_counts.get("validation_included", 0),
                "holdout": dataset_result.summary_counts.get("holdout_included", 0),
            },
            excluded_insufficient_feature_history_count=sum(
                1 for exclusion in feature_exclusions if exclusion.reason == EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY
            ),
            excluded_incomplete_mae20_count=_excluded_count(
                dataset_result.summary_counts,
                TechnicalRiskOOSExclusionReason.EXCLUDED_INCOMPLETE_MAE20,
            ),
            excluded_incomplete_mae60_count=_excluded_count(
                dataset_result.summary_counts,
                TechnicalRiskOOSExclusionReason.EXCLUDED_INCOMPLETE_MAE60,
            ),
            excluded_split_leakage_count=_excluded_count(
                dataset_result.summary_counts,
                TechnicalRiskOOSExclusionReason.EXCLUDED_TARGET_CROSSES_SPLIT_BOUNDARY,
            ),
            materializer_version=request.materializer_version,
        )

    def _verified_read_only_store(self, request: TechnicalRiskRealOOSDatasetMaterializationRequest) -> ResearchDataStore:
        db_path = Path(request.research_db_path)
        manifest_path = Path(request.research_manifest_path)
        if not db_path.exists():
            raise TechnicalRiskRealOOSDatasetMaterializationError(f"Research DB not found: {db_path}")
        if not manifest_path.exists():
            raise TechnicalRiskRealOOSDatasetMaterializationError(f"Research manifest not found: {manifest_path}")
        db_sha256 = hashlib.sha256(db_path.read_bytes()).hexdigest()
        store = ResearchDataStore(
            db_path=db_path,
            research_snapshot_id=request.source_snapshot_id,
            manifest_path=manifest_path,
            expected_semantic_checksum=request.source_snapshot_checksum,
            expected_db_sha256=db_sha256,
            verify_default_runtime=False,
        )
        try:
            store.verify_runtime_identity(verify_db_sha=False)
        except ResearchDataStoreError as exc:
            raise TechnicalRiskRealOOSDatasetMaterializationError(f"Research snapshot identity verification failed: {exc}") from exc
        return store

    def _validate_unique_raw_dates(self, symbol: str, trading_dates: Iterable[date]) -> None:
        seen: set[date] = set()
        for trading_date in trading_dates:
            if trading_date in seen:
                raise TechnicalRiskRealOOSDatasetMaterializationError(
                    f"Duplicate raw price observation for {symbol} on {trading_date.isoformat()}."
                )
            seen.add(trading_date)

    def _feature_points(self, bars) -> tuple[PriceVolumePoint, ...]:
        return tuple(
            PriceVolumePoint(
                symbol=bar.symbol,
                trading_date=bar.trading_date,
                close=bar.close,
                volume=float(bar.volume) if bar.volume is not None else None,
            )
            for bar in bars
        )

    def _target_points(self, bars) -> tuple[TargetPricePoint, ...]:
        return tuple(TargetPricePoint(symbol=bar.symbol, trading_date=bar.trading_date, price=bar.close) for bar in bars)

    def _evaluation_dates(self, bars, request: TechnicalRiskRealOOSDatasetMaterializationRequest) -> tuple[date, ...]:
        return tuple(
            bar.trading_date
            for bar in bars
            if request.analysis_start_date <= bar.trading_date <= request.analysis_end_date
            and _date_in_split_scope(bar.trading_date, request.split_specs)
        )

    def _materialize_feature(
        self,
        request: TechnicalRiskRealOOSDatasetMaterializationRequest,
        symbol: str,
        evaluation_date: date,
        materializer: HistoricalRiskFeatureMaterializer,
        observations: list[HistoricalRiskFeatureObservation],
        exclusions: list[HistoricalRiskFeatureExclusion],
    ) -> None:
        context = HistoricalRiskFeatureMaterializationContext(
            symbol=symbol,
            evaluation_date=evaluation_date,
            source_snapshot_id=request.source_snapshot_id,
            source_snapshot_checksum=request.source_snapshot_checksum,
            feature_set_id=request.feature_set_id,
            calculation_id=_calculation_id("feature", request, symbol, evaluation_date),
        )
        result = materializer.materialize(context)
        if result.status == HistoricalRiskFeatureStatus.INCLUDED:
            observations.append(result.observation)
            return
        exclusions.append(result.exclusion)

    def _materialize_mae(
        self,
        request: TechnicalRiskRealOOSDatasetMaterializationRequest,
        symbol: str,
        reference_date: date,
        window: int,
        generator,
    ) -> TargetArtifact | None:
        context = TargetCalculationContext(
            snapshot_id=request.source_snapshot_id,
            symbol=symbol,
            reference_date=reference_date,
            evaluation_window=window,
            target_version="v1",
            calculation_id=_calculation_id(f"mae{window}", request, symbol, reference_date),
        )
        output = generator.calculate(context)
        if not generator.validate(output):
            return None
        try:
            return self._target_artifact_generator.generate(output, context, output.definition)
        except TargetArtifactGenerationError as exc:
            raise TechnicalRiskRealOOSDatasetMaterializationError(f"MAE{window} target artifact generation failed: {exc}") from exc


def _normalize_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(symbols)
    if not normalized:
        raise TechnicalRiskRealOOSDatasetMaterializationError("symbols cannot be empty.")
    for symbol in normalized:
        _require_text(symbol, "symbol")
    if len(set(normalized)) != len(normalized):
        raise TechnicalRiskRealOOSDatasetMaterializationError("symbols cannot contain duplicates.")
    return tuple(sorted(normalized))


def _require_split_roles(split_specs: tuple[TechnicalRiskOOSSplitSpec, ...]) -> None:
    roles = {split.split_role for split in split_specs}
    required = {TechnicalRiskOOSSplitRole.VALIDATION, TechnicalRiskOOSSplitRole.HOLDOUT}
    missing = sorted(role.value for role in required if role not in roles)
    if missing:
        raise TechnicalRiskRealOOSDatasetMaterializationError(f"Missing required OOS split role: {', '.join(missing)}.")


def _normalize_required_output_split_roles(
    values: tuple[TechnicalRiskOOSSplitRole, ...],
) -> tuple[TechnicalRiskOOSSplitRole, ...]:
    roles = tuple(value if isinstance(value, TechnicalRiskOOSSplitRole) else TechnicalRiskOOSSplitRole(value) for value in values)
    if not roles:
        raise TechnicalRiskRealOOSDatasetMaterializationError("required_output_split_roles must not be empty.")
    if len(set(roles)) != len(roles):
        raise TechnicalRiskRealOOSDatasetMaterializationError("Duplicate required_output_split_role.")
    unsupported = tuple(role for role in roles if role not in (TechnicalRiskOOSSplitRole.VALIDATION, TechnicalRiskOOSSplitRole.HOLDOUT))
    if unsupported:
        raise TechnicalRiskRealOOSDatasetMaterializationError("Unsupported required_output_split_role.")
    return tuple(sorted(roles, key=_required_output_split_role_order))


def _validate_required_output_splits(
    dataset_result: TechnicalRiskOOSDatasetResult,
    required_output_split_roles: tuple[TechnicalRiskOOSSplitRole, ...],
) -> None:
    for role in required_output_split_roles:
        if dataset_result.summary_counts.get(f"{role.value.lower()}_included", 0) <= 0:
            raise TechnicalRiskRealOOSDatasetMaterializationError(f"No {role.value.lower()} aligned rows were produced.")


def _required_output_split_role_order(role: TechnicalRiskOOSSplitRole) -> int:
    return {
        TechnicalRiskOOSSplitRole.VALIDATION: 0,
        TechnicalRiskOOSSplitRole.HOLDOUT: 1,
    }[role]


def _date_in_split_scope(evaluation_date: date, split_specs: tuple[TechnicalRiskOOSSplitSpec, ...]) -> bool:
    return any(split.start_date <= evaluation_date <= split.end_date for split in split_specs)


def _calculation_id(kind: str, request: TechnicalRiskRealOOSDatasetMaterializationRequest, symbol: str, evaluation_date: date) -> str:
    return (
        f"{request.materializer_version}:"
        f"{request.dataset_spec_id}:"
        f"{request.dataset_spec_version}:"
        f"{request.feature_set_id}:"
        f"{kind}:"
        f"{symbol}:"
        f"{evaluation_date.isoformat()}"
    )


def _excluded_count(summary_counts: Mapping[str, int], reason: TechnicalRiskOOSExclusionReason) -> int:
    return summary_counts.get(f"excluded_{reason.value.lower()}", 0)


def _reject_production_path(path: Path, field_name: str) -> None:
    parts = tuple(part.lower() for part in path.resolve().parts)
    for index, part in enumerate(parts[:-1]):
        if part == "data" and parts[index + 1] == "production":
            raise TechnicalRiskRealOOSDatasetMaterializationError(f"{field_name} cannot target data/production.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise TechnicalRiskRealOOSDatasetMaterializationError(f"{field_name} is required.")


def _require_date(value: object, field_name: str) -> None:
    if not isinstance(value, date):
        raise TechnicalRiskRealOOSDatasetMaterializationError(f"{field_name} must be a date.")
