from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
import math

from historical_condition_outcome_service import ConditionOutcomeObservation
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonResult
from historical_condition_outcome_service import OutcomeStatusSummary
from models import OutcomeEvaluationStatus


OBSERVATION_UNIT_DAILY = "DAILY"
VOLUME_CONDITION_ID = "volume_ratio_20"
DEFAULT_VOLUME_THRESHOLD_GRID = (0.80, 1.00, 1.10, 1.20, 1.30, 1.50)
DEFAULT_BASELINE_THRESHOLD = 1.20


class VolumeThresholdSensitivityAnalysisError(Exception):
    """Raised when volume threshold sensitivity inputs are invalid."""


@dataclass(frozen=True)
class VolumeThresholdSensitivityConfig:

    thresholds: tuple[float, ...] = DEFAULT_VOLUME_THRESHOLD_GRID

    baseline_threshold: float = DEFAULT_BASELINE_THRESHOLD

    analysis_name: str = "成交量門檻變化測試"

    advanced_method_name: str = "Volume Threshold Sensitivity Analysis"

    observation_unit: str = OBSERVATION_UNIT_DAILY

    overlap_possible: bool = True

    def __post_init__(self):
        normalized_thresholds = _validate_thresholds(self.thresholds)
        if not _is_finite_positive_number(self.baseline_threshold):
            raise VolumeThresholdSensitivityAnalysisError("baseline_threshold must be finite and greater than zero.")
        if self.baseline_threshold not in normalized_thresholds:
            raise VolumeThresholdSensitivityAnalysisError("thresholds must include the baseline threshold.")
        object.__setattr__(self, "thresholds", normalized_thresholds)


@dataclass(frozen=True)
class VolumeThresholdSensitivityPoint:

    threshold: float

    is_current_v1_baseline: bool

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    observation_count_delta_vs_v1: int

    observation_count_change_rate_vs_v1: float | None

    resolved_count_delta_vs_v1: int

    hit_count_delta_vs_v1: int

    miss_count_delta_vs_v1: int

    historical_hit_rate_delta_percentage_points_vs_v1: float | None


@dataclass(frozen=True)
class VolumeThresholdSensitivitySymbolSummary:

    symbol: str

    points: tuple[VolumeThresholdSensitivityPoint, ...]


@dataclass(frozen=True)
class VolumeThresholdSensitivityResult:

    config: VolumeThresholdSensitivityConfig

    threshold_grid: tuple[float, ...]

    baseline_threshold: float

    source_signal_definition_id: str

    source_outcome_definition_id: str

    source_warmup_trading_bars: int

    source_observation_count: int

    aggregate_points: tuple[VolumeThresholdSensitivityPoint, ...]

    per_symbol_summaries: tuple[VolumeThresholdSensitivitySymbolSummary, ...]

    observation_unit: str

    overlap_possible: bool

    generated_at: datetime


def analyze_volume_threshold_sensitivity(
    comparison_result: HistoricalConditionOutcomeComparisonResult,
    *,
    config: VolumeThresholdSensitivityConfig | None = None,
    generated_at: datetime | None = None,
) -> VolumeThresholdSensitivityResult:
    config = config or VolumeThresholdSensitivityConfig(
        observation_unit=comparison_result.observation_unit,
        overlap_possible=comparison_result.overlap_possible,
    )
    observations = tuple(comparison_result.outcome_observations)
    _validate_unique_observations(observations)
    _validate_volume_condition(comparison_result)

    aggregate_points, aggregate_ids = _points_for_observations(observations, config)
    _validate_sample_count_monotonic(aggregate_points)
    _validate_qualified_id_subsets(config.thresholds, aggregate_ids)
    symbols = comparison_result.diagnostics_result.normalized_symbols or tuple(
        sorted({observation.symbol for observation in observations})
    )

    return VolumeThresholdSensitivityResult(
        config=config,
        threshold_grid=config.thresholds,
        baseline_threshold=config.baseline_threshold,
        source_signal_definition_id=comparison_result.diagnostics_result.config.signal_definition.id,
        source_outcome_definition_id=comparison_result.config.outcome_definition.id,
        source_warmup_trading_bars=comparison_result.config.warmup_trading_bars,
        source_observation_count=len(observations),
        aggregate_points=aggregate_points,
        per_symbol_summaries=tuple(
            VolumeThresholdSensitivitySymbolSummary(
                symbol=symbol,
                points=_points_for_observations(
                    tuple(observation for observation in observations if observation.symbol == symbol),
                    config,
                )[0],
            )
            for symbol in symbols
        ),
        observation_unit=config.observation_unit,
        overlap_possible=config.overlap_possible,
        generated_at=generated_at or datetime.now(UTC),
    )


def _points_for_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
    config: VolumeThresholdSensitivityConfig,
) -> tuple[tuple[VolumeThresholdSensitivityPoint, ...], dict[float, set[tuple[str, object, str]]]]:
    summaries = {}
    qualified_ids = {}
    for threshold in config.thresholds:
        qualified = _qualified_observations(observations, threshold)
        summaries[threshold] = _outcome_summary(qualified)
        qualified_ids[threshold] = {
            _observation_identity(observation)
            for observation in qualified
        }

    baseline_summary = summaries[config.baseline_threshold]
    points = tuple(
        _point(
            threshold,
            summary=summaries[threshold],
            baseline_threshold=config.baseline_threshold,
            baseline_summary=baseline_summary,
        )
        for threshold in config.thresholds
    )
    return points, qualified_ids


def _qualified_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
    threshold: float,
) -> tuple[ConditionOutcomeObservation, ...]:
    return tuple(
        observation for observation in observations
        if _other_v1_conditions_pass(observation)
        and _volume_ratio_qualifies(observation, threshold)
    )


def _other_v1_conditions_pass(observation: ConditionOutcomeObservation) -> bool:
    expected_other_conditions = observation.total_condition_count - 1
    if observation.matched_condition_count < expected_other_conditions:
        return False
    return all(
        condition_id == VOLUME_CONDITION_ID or condition_id in observation.passed_condition_ids
        for condition_id in _condition_ids_from_observation(observation)
    )


def _volume_ratio_qualifies(observation: ConditionOutcomeObservation, threshold: float) -> bool:
    value = getattr(observation.diagnostic_observation.source_snapshot, VOLUME_CONDITION_ID, None)
    return _is_finite_number(value) and value >= threshold


def _point(
    threshold: float,
    *,
    summary: OutcomeStatusSummary,
    baseline_threshold: float,
    baseline_summary: OutcomeStatusSummary,
) -> VolumeThresholdSensitivityPoint:
    return VolumeThresholdSensitivityPoint(
        threshold=threshold,
        is_current_v1_baseline=threshold == baseline_threshold,
        observation_count=summary.observation_count,
        hit_count=summary.hit_count,
        miss_count=summary.miss_count,
        incomplete_count=summary.incomplete_count,
        not_evaluable_count=summary.not_evaluable_count,
        resolved_count=summary.resolved_count,
        historical_hit_rate=summary.historical_hit_rate,
        observation_count_delta_vs_v1=summary.observation_count - baseline_summary.observation_count,
        observation_count_change_rate_vs_v1=_change_rate(
            baseline_summary.observation_count,
            summary.observation_count,
        ),
        resolved_count_delta_vs_v1=summary.resolved_count - baseline_summary.resolved_count,
        hit_count_delta_vs_v1=summary.hit_count - baseline_summary.hit_count,
        miss_count_delta_vs_v1=summary.miss_count - baseline_summary.miss_count,
        historical_hit_rate_delta_percentage_points_vs_v1=_hit_rate_delta_percentage_points(
            baseline_summary.historical_hit_rate,
            summary.historical_hit_rate,
        ),
    )


def _outcome_summary(
    observations: tuple[ConditionOutcomeObservation, ...],
) -> OutcomeStatusSummary:
    hit_count = _count_status(observations, OutcomeEvaluationStatus.HIT)
    miss_count = _count_status(observations, OutcomeEvaluationStatus.MISS)
    incomplete_count = _count_status(observations, OutcomeEvaluationStatus.INCOMPLETE)
    not_evaluable_count = _count_status(observations, OutcomeEvaluationStatus.NOT_EVALUABLE)
    resolved_count = hit_count + miss_count
    return OutcomeStatusSummary(
        observation_count=len(observations),
        hit_count=hit_count,
        miss_count=miss_count,
        incomplete_count=incomplete_count,
        not_evaluable_count=not_evaluable_count,
        resolved_count=resolved_count,
        historical_hit_rate=None if resolved_count == 0 else hit_count / resolved_count,
    )


def _validate_thresholds(thresholds: tuple[float, ...]) -> tuple[float, ...]:
    if not thresholds:
        raise VolumeThresholdSensitivityAnalysisError("thresholds cannot be empty.")
    normalized = tuple(float(threshold) for threshold in thresholds)
    if any(not _is_finite_positive_number(threshold) for threshold in normalized):
        raise VolumeThresholdSensitivityAnalysisError("thresholds must be finite and greater than zero.")
    if len(set(normalized)) != len(normalized):
        raise VolumeThresholdSensitivityAnalysisError("thresholds cannot contain duplicates.")
    return tuple(sorted(normalized))


def _validate_volume_condition(comparison_result: HistoricalConditionOutcomeComparisonResult) -> None:
    signal_definition = comparison_result.diagnostics_result.config.signal_definition
    volume_conditions = [
        condition for condition in signal_definition.conditions
        if condition.metric == VOLUME_CONDITION_ID and condition.secondary_metric is None
    ]
    if len(volume_conditions) != 1:
        raise VolumeThresholdSensitivityAnalysisError("V1 signal definition must contain one volume_ratio_20 condition.")
    condition = volume_conditions[0]
    if getattr(condition.operator, "value", None) != ">=" or condition.value != DEFAULT_BASELINE_THRESHOLD:
        raise VolumeThresholdSensitivityAnalysisError("V1 volume condition must be volume_ratio_20 >= 1.20.")


def _validate_sample_count_monotonic(points: tuple[VolumeThresholdSensitivityPoint, ...]) -> None:
    previous_count = None
    for point in points:
        if previous_count is not None and previous_count < point.observation_count:
            raise VolumeThresholdSensitivityAnalysisError(
                "Qualified observation counts must not increase as threshold increases."
            )
        previous_count = point.observation_count


def _validate_qualified_id_subsets(
    thresholds: tuple[float, ...],
    qualified_ids: dict[float, set[tuple[str, object, str]]],
) -> None:
    for lower, higher in zip(thresholds, thresholds[1:]):
        if not qualified_ids[higher].issubset(qualified_ids[lower]):
            raise VolumeThresholdSensitivityAnalysisError(
                "Higher threshold qualified IDs must be a subset of lower threshold IDs."
            )


def _validate_unique_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
) -> None:
    seen = set()
    for observation in observations:
        identity = _observation_identity(observation)
        if identity in seen:
            raise VolumeThresholdSensitivityAnalysisError(
                "Volume threshold sensitivity observations must be unique by symbol, trading_date, and signal id."
            )
        seen.add(identity)


def _condition_ids_from_observation(observation: ConditionOutcomeObservation) -> tuple[str, ...]:
    return tuple(
        condition.secondary_metric and f"{condition.metric}_vs_{condition.secondary_metric}" or condition.metric
        for condition in observation.diagnostic_observation.evaluated_conditions
    )


def _observation_identity(observation: ConditionOutcomeObservation) -> tuple[str, object, str]:
    return (
        observation.symbol,
        observation.trading_date,
        observation.signal_definition_id,
    )


def _change_rate(baseline_count: int, count: int) -> float | None:
    if baseline_count == 0:
        return None
    return (count - baseline_count) / baseline_count


def _hit_rate_delta_percentage_points(
    baseline_rate: float | None,
    rate: float | None,
) -> float | None:
    if baseline_rate is None or rate is None:
        return None
    return (rate - baseline_rate) * 100


def _is_finite_positive_number(value) -> bool:
    return _is_finite_number(value) and value > 0


def _is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _count_status(observations, status: OutcomeEvaluationStatus) -> int:
    return sum(observation.status is status for observation in observations)
