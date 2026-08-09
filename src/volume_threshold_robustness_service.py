from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime

from historical_condition_outcome_service import ConditionOutcomeObservation
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonResult
from historical_condition_outcome_service import OutcomeStatusSummary
from models import OutcomeEvaluationStatus
from models import HistoricalPriceSeries
from volume_threshold_sensitivity_service import DEFAULT_BASELINE_THRESHOLD
from volume_threshold_sensitivity_service import VOLUME_CONDITION_ID
from volume_threshold_sensitivity_service import _other_v1_conditions_pass
from volume_threshold_sensitivity_service import _validate_volume_condition
from volume_threshold_sensitivity_service import _volume_ratio_qualifies


OBSERVATION_UNIT_DAILY = "DAILY"
DEFAULT_ROBUSTNESS_THRESHOLDS = (1.00, 1.10, 1.20)
DEFAULT_OBSERVATION_START = date(2018, 1, 1)
DEFAULT_OBSERVATION_END = date(2025, 12, 31)
DEFAULT_WARMUP_TRADING_BARS = 60
DEFAULT_OUTCOME_HORIZON_BARS = 20
DEFAULT_OVERLAP_REDUCTION_SPACING_BARS = 20


class VolumeThresholdRobustnessAnalysisError(Exception):
    """Raised when volume threshold robustness inputs are invalid."""


@dataclass(frozen=True)
class VolumeThresholdRobustnessConfig:

    candidate_thresholds: tuple[float, ...] = DEFAULT_ROBUSTNESS_THRESHOLDS

    baseline_threshold: float = DEFAULT_BASELINE_THRESHOLD

    symbols: tuple[str, ...] = tuple()

    start_date: date = DEFAULT_OBSERVATION_START

    end_date: date = DEFAULT_OBSERVATION_END

    warmup_trading_bars: int = DEFAULT_WARMUP_TRADING_BARS

    outcome_horizon_bars: int = DEFAULT_OUTCOME_HORIZON_BARS

    overlap_reduction_spacing_bars: int = DEFAULT_OVERLAP_REDUCTION_SPACING_BARS

    analysis_name: str = "成交量門檻穩健性分析"

    advanced_method_name: str = "Volume Threshold Robustness Analysis"

    observation_unit: str = OBSERVATION_UNIT_DAILY

    overlap_possible: bool = True

    def __post_init__(self):
        normalized = tuple(float(threshold) for threshold in self.candidate_thresholds)
        if normalized != DEFAULT_ROBUSTNESS_THRESHOLDS:
            raise VolumeThresholdRobustnessAnalysisError(
                "candidate_thresholds must be exactly 1.00, 1.10, and 1.20."
            )
        if self.baseline_threshold != DEFAULT_BASELINE_THRESHOLD:
            raise VolumeThresholdRobustnessAnalysisError("baseline_threshold must be exactly 1.20.")
        if self.start_date > self.end_date:
            raise VolumeThresholdRobustnessAnalysisError("start_date cannot be after end_date.")
        if self.warmup_trading_bars != DEFAULT_WARMUP_TRADING_BARS:
            raise VolumeThresholdRobustnessAnalysisError("warmup_trading_bars must be exactly 60.")
        if self.outcome_horizon_bars != DEFAULT_OUTCOME_HORIZON_BARS:
            raise VolumeThresholdRobustnessAnalysisError("outcome_horizon_bars must be exactly 20.")
        if self.overlap_reduction_spacing_bars != DEFAULT_OVERLAP_REDUCTION_SPACING_BARS:
            raise VolumeThresholdRobustnessAnalysisError(
                "overlap_reduction_spacing_bars must be exactly 20."
            )
        object.__setattr__(self, "candidate_thresholds", normalized)


@dataclass(frozen=True)
class ThresholdDailyRobustnessSummary:

    threshold: float

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None

    observation_count_delta_vs_1_20: int

    observation_count_change_rate_vs_1_20: float | None


@dataclass(frozen=True)
class ThresholdSymbolRobustnessSummary:

    symbol: str

    threshold: float

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None

    observation_count_delta_vs_1_20: int

    observation_count_change_rate_vs_1_20: float | None


@dataclass(frozen=True)
class ThresholdYearRobustnessSummary:

    year: int

    threshold: float

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    delta_hit_rate_vs_1_20_pp: float | None

    observation_count_delta_vs_1_20: int


@dataclass(frozen=True)
class OverlapReducedSelectedObservation:

    symbol: str

    trading_date: date

    signal_definition_id: str

    trading_bar_index: int

    outcome_status: OutcomeEvaluationStatus


@dataclass(frozen=True)
class OverlapReducedThresholdSummary:

    threshold: float

    daily_observation_count: int

    overlap_reduced_observation_count: int

    daily_hit_count: int

    daily_miss_count: int

    daily_resolved_count: int

    daily_hit_rate: float | None

    overlap_reduced_hit_count: int

    overlap_reduced_miss_count: int

    overlap_reduced_incomplete_count: int

    overlap_reduced_not_evaluable_count: int

    overlap_reduced_resolved_count: int

    overlap_reduced_hit_rate: float | None

    overlap_reduced_hit_rate_delta_vs_1_20_pp: float | None

    selected_observations: tuple[OverlapReducedSelectedObservation, ...]

    selected_spacing_invariant_passed: bool


@dataclass(frozen=True)
class VolumeThresholdRobustnessResult:

    config: VolumeThresholdRobustnessConfig

    signal_definition_id: str

    candidate_thresholds: tuple[float, ...]

    baseline_threshold: float

    symbols: tuple[str, ...]

    start_date: date

    end_date: date

    warmup_trading_bars: int

    outcome_horizon_bars: int

    daily_summaries: tuple[ThresholdDailyRobustnessSummary, ...]

    per_symbol_summaries: tuple[ThresholdSymbolRobustnessSummary, ...]

    per_year_summaries: tuple[ThresholdYearRobustnessSummary, ...]

    overlap_reduced_summaries: tuple[OverlapReducedThresholdSummary, ...]

    observation_unit: str

    overlap_possible: bool

    overlap_reduction_spacing_bars: int

    generated_at: datetime


def analyze_volume_threshold_robustness(
    comparison_result: HistoricalConditionOutcomeComparisonResult,
    *,
    config: VolumeThresholdRobustnessConfig | None = None,
    price_series_by_symbol: dict[str, HistoricalPriceSeries] | None = None,
    trading_bar_index_by_identity: dict[tuple[str, object, str], int] | None = None,
    generated_at: datetime | None = None,
) -> VolumeThresholdRobustnessResult:
    config = config or VolumeThresholdRobustnessConfig(
        symbols=comparison_result.diagnostics_result.normalized_symbols,
        observation_unit=comparison_result.observation_unit,
        overlap_possible=comparison_result.overlap_possible,
    )
    observations = tuple(comparison_result.outcome_observations)
    _validate_unique_observations(observations)
    _validate_volume_condition(comparison_result)
    _validate_observation_dates(observations, config)

    symbols = config.symbols or comparison_result.diagnostics_result.normalized_symbols or tuple(
        sorted({observation.symbol for observation in observations})
    )
    qualified_by_threshold = {
        threshold: _qualified_observations(observations, threshold)
        for threshold in config.candidate_thresholds
    }
    baseline_summary = _outcome_summary(qualified_by_threshold[config.baseline_threshold])
    daily_summaries = tuple(
        _daily_summary(
            threshold,
            summary=_outcome_summary(qualified_by_threshold[threshold]),
            baseline_summary=baseline_summary,
        )
        for threshold in config.candidate_thresholds
    )

    bar_index_by_identity = trading_bar_index_by_identity
    if bar_index_by_identity is None and price_series_by_symbol is not None:
        bar_index_by_identity = _prepared_trading_bar_index_by_identity(
            observations,
            price_series_by_symbol,
        )
    if bar_index_by_identity is None:
        bar_index_by_identity = _trading_bar_index_by_identity(observations)
    overlap_baseline = _overlap_reduced_observations(
        qualified_by_threshold[config.baseline_threshold],
        bar_index_by_identity,
        spacing_bars=config.overlap_reduction_spacing_bars,
    )
    overlap_baseline_summary = _outcome_summary(overlap_baseline)

    return VolumeThresholdRobustnessResult(
        config=config,
        signal_definition_id=comparison_result.diagnostics_result.config.signal_definition.id,
        candidate_thresholds=config.candidate_thresholds,
        baseline_threshold=config.baseline_threshold,
        symbols=tuple(symbols),
        start_date=config.start_date,
        end_date=config.end_date,
        warmup_trading_bars=config.warmup_trading_bars,
        outcome_horizon_bars=config.outcome_horizon_bars,
        daily_summaries=daily_summaries,
        per_symbol_summaries=_per_symbol_summaries(
            symbols,
            qualified_by_threshold,
            config=config,
        ),
        per_year_summaries=_per_year_summaries(
            qualified_by_threshold,
            config=config,
        ),
        overlap_reduced_summaries=tuple(
            _overlap_summary(
                threshold,
                daily_observations=qualified_by_threshold[threshold],
                overlap_reduced_observations=_overlap_reduced_observations(
                    qualified_by_threshold[threshold],
                    bar_index_by_identity,
                    spacing_bars=config.overlap_reduction_spacing_bars,
                ),
                bar_index_by_identity=bar_index_by_identity,
                baseline_overlap_summary=overlap_baseline_summary,
                spacing_bars=config.overlap_reduction_spacing_bars,
            )
            for threshold in config.candidate_thresholds
        ),
        observation_unit=config.observation_unit,
        overlap_possible=config.overlap_possible,
        overlap_reduction_spacing_bars=config.overlap_reduction_spacing_bars,
        generated_at=generated_at or datetime.now(UTC),
    )


def _qualified_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
    threshold: float,
) -> tuple[ConditionOutcomeObservation, ...]:
    return tuple(
        observation for observation in observations
        if _other_v1_conditions_pass(observation)
        and _volume_ratio_qualifies(observation, threshold)
    )


def _per_symbol_summaries(
    symbols,
    qualified_by_threshold: dict[float, tuple[ConditionOutcomeObservation, ...]],
    *,
    config: VolumeThresholdRobustnessConfig,
) -> tuple[ThresholdSymbolRobustnessSummary, ...]:
    rows = []
    for symbol in symbols:
        by_threshold = {
            threshold: tuple(
                observation for observation in qualified
                if observation.symbol == symbol
            )
            for threshold, qualified in qualified_by_threshold.items()
        }
        baseline_summary = _outcome_summary(by_threshold[config.baseline_threshold])
        for threshold in config.candidate_thresholds:
            summary = _outcome_summary(by_threshold[threshold])
            rows.append(
                ThresholdSymbolRobustnessSummary(
                    symbol=symbol,
                    threshold=threshold,
                    observation_count=summary.observation_count,
                    hit_count=summary.hit_count,
                    miss_count=summary.miss_count,
                    incomplete_count=summary.incomplete_count,
                    not_evaluable_count=summary.not_evaluable_count,
                    resolved_count=summary.resolved_count,
                    historical_hit_rate=summary.historical_hit_rate,
                    delta_hit_rate_vs_1_20_pp=_hit_rate_delta_percentage_points(
                        baseline_summary.historical_hit_rate,
                        summary.historical_hit_rate,
                    ),
                    observation_count_delta_vs_1_20=summary.observation_count - baseline_summary.observation_count,
                    observation_count_change_rate_vs_1_20=_change_rate(
                        baseline_summary.observation_count,
                        summary.observation_count,
                    ),
                )
            )
    return tuple(rows)


def _per_year_summaries(
    qualified_by_threshold: dict[float, tuple[ConditionOutcomeObservation, ...]],
    *,
    config: VolumeThresholdRobustnessConfig,
) -> tuple[ThresholdYearRobustnessSummary, ...]:
    rows = []
    for year in range(config.start_date.year, config.end_date.year + 1):
        by_threshold = {
            threshold: tuple(
                observation for observation in qualified
                if observation.trading_date.year == year
            )
            for threshold, qualified in qualified_by_threshold.items()
        }
        baseline_summary = _outcome_summary(by_threshold[config.baseline_threshold])
        for threshold in config.candidate_thresholds:
            summary = _outcome_summary(by_threshold[threshold])
            rows.append(
                ThresholdYearRobustnessSummary(
                    year=year,
                    threshold=threshold,
                    observation_count=summary.observation_count,
                    hit_count=summary.hit_count,
                    miss_count=summary.miss_count,
                    incomplete_count=summary.incomplete_count,
                    not_evaluable_count=summary.not_evaluable_count,
                    resolved_count=summary.resolved_count,
                    historical_hit_rate=summary.historical_hit_rate,
                    delta_hit_rate_vs_1_20_pp=_hit_rate_delta_percentage_points(
                        baseline_summary.historical_hit_rate,
                        summary.historical_hit_rate,
                    ),
                    observation_count_delta_vs_1_20=summary.observation_count - baseline_summary.observation_count,
                )
            )
    return tuple(rows)


def _daily_summary(
    threshold: float,
    *,
    summary: OutcomeStatusSummary,
    baseline_summary: OutcomeStatusSummary,
) -> ThresholdDailyRobustnessSummary:
    return ThresholdDailyRobustnessSummary(
        threshold=threshold,
        observation_count=summary.observation_count,
        hit_count=summary.hit_count,
        miss_count=summary.miss_count,
        incomplete_count=summary.incomplete_count,
        not_evaluable_count=summary.not_evaluable_count,
        resolved_count=summary.resolved_count,
        historical_hit_rate=summary.historical_hit_rate,
        delta_hit_rate_vs_1_20_pp=_hit_rate_delta_percentage_points(
            baseline_summary.historical_hit_rate,
            summary.historical_hit_rate,
        ),
        observation_count_delta_vs_1_20=summary.observation_count - baseline_summary.observation_count,
        observation_count_change_rate_vs_1_20=_change_rate(
            baseline_summary.observation_count,
            summary.observation_count,
        ),
    )


def _overlap_summary(
    threshold: float,
    *,
    daily_observations: tuple[ConditionOutcomeObservation, ...],
    overlap_reduced_observations: tuple[ConditionOutcomeObservation, ...],
    bar_index_by_identity: dict[tuple[str, object, str], int],
    baseline_overlap_summary: OutcomeStatusSummary,
    spacing_bars: int,
) -> OverlapReducedThresholdSummary:
    daily = _outcome_summary(daily_observations)
    reduced = _outcome_summary(overlap_reduced_observations)
    selected = tuple(
        OverlapReducedSelectedObservation(
            symbol=observation.symbol,
            trading_date=observation.trading_date,
            signal_definition_id=observation.signal_definition_id,
            trading_bar_index=bar_index_by_identity[_observation_identity(observation)],
            outcome_status=observation.status,
        )
        for observation in overlap_reduced_observations
    )
    return OverlapReducedThresholdSummary(
        threshold=threshold,
        daily_observation_count=daily.observation_count,
        overlap_reduced_observation_count=reduced.observation_count,
        daily_hit_count=daily.hit_count,
        daily_miss_count=daily.miss_count,
        daily_resolved_count=daily.resolved_count,
        daily_hit_rate=daily.historical_hit_rate,
        overlap_reduced_hit_count=reduced.hit_count,
        overlap_reduced_miss_count=reduced.miss_count,
        overlap_reduced_incomplete_count=reduced.incomplete_count,
        overlap_reduced_not_evaluable_count=reduced.not_evaluable_count,
        overlap_reduced_resolved_count=reduced.resolved_count,
        overlap_reduced_hit_rate=reduced.historical_hit_rate,
        overlap_reduced_hit_rate_delta_vs_1_20_pp=_hit_rate_delta_percentage_points(
            baseline_overlap_summary.historical_hit_rate,
            reduced.historical_hit_rate,
        ),
        selected_observations=selected,
        selected_spacing_invariant_passed=_selected_spacing_invariant(selected, spacing_bars),
    )


def _overlap_reduced_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
    bar_index_by_identity: dict[tuple[str, object, str], int],
    *,
    spacing_bars: int,
) -> tuple[ConditionOutcomeObservation, ...]:
    selected = []
    last_selected_index_by_symbol: dict[str, int] = {}
    for observation in sorted(observations, key=lambda item: (item.symbol, item.trading_date)):
        bar_index = bar_index_by_identity[_observation_identity(observation)]
        last_index = last_selected_index_by_symbol.get(observation.symbol)
        if last_index is None or bar_index - last_index >= spacing_bars:
            selected.append(observation)
            last_selected_index_by_symbol[observation.symbol] = bar_index
    return tuple(selected)


def _trading_bar_index_by_identity(
    observations: tuple[ConditionOutcomeObservation, ...],
) -> dict[tuple[str, object, str], int]:
    by_symbol: dict[str, list[ConditionOutcomeObservation]] = {}
    for observation in observations:
        by_symbol.setdefault(observation.symbol, []).append(observation)

    result = {}
    for symbol_observations in by_symbol.values():
        for index, observation in enumerate(sorted(symbol_observations, key=lambda item: item.trading_date)):
            result[_observation_identity(observation)] = index
    return result


def _prepared_trading_bar_index_by_identity(
    observations: tuple[ConditionOutcomeObservation, ...],
    price_series_by_symbol: dict[str, HistoricalPriceSeries],
) -> dict[tuple[str, object, str], int]:
    wanted = {_observation_identity(observation): observation for observation in observations}
    result = {}
    for symbol, price_series in price_series_by_symbol.items():
        index_by_date = {
            bar.trading_date: index
            for index, bar in enumerate(sorted(price_series.bars, key=lambda item: item.trading_date))
        }
        for identity, observation in wanted.items():
            if observation.symbol != symbol:
                continue
            if observation.trading_date not in index_by_date:
                raise VolumeThresholdRobustnessAnalysisError(
                    "Prepared trading-bar index is missing an outcome observation date."
                )
            result[identity] = index_by_date[observation.trading_date]
    missing = set(wanted) - set(result)
    if missing:
        raise VolumeThresholdRobustnessAnalysisError(
            "Prepared trading-bar index is missing one or more observation symbols."
        )
    return result


def _selected_spacing_invariant(
    selected: tuple[OverlapReducedSelectedObservation, ...],
    spacing_bars: int,
) -> bool:
    last_index_by_symbol: dict[str, int] = {}
    for observation in sorted(selected, key=lambda item: (item.symbol, item.trading_bar_index)):
        last_index = last_index_by_symbol.get(observation.symbol)
        if last_index is not None and observation.trading_bar_index - last_index < spacing_bars:
            return False
        last_index_by_symbol[observation.symbol] = observation.trading_bar_index
    return True


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


def _validate_observation_dates(
    observations: tuple[ConditionOutcomeObservation, ...],
    config: VolumeThresholdRobustnessConfig,
) -> None:
    outside = [
        observation for observation in observations
        if observation.trading_date < config.start_date or observation.trading_date > config.end_date
    ]
    if outside:
        raise VolumeThresholdRobustnessAnalysisError(
            "Robustness observations must stay inside the configured observation date window."
        )


def _validate_unique_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
) -> None:
    seen = set()
    for observation in observations:
        identity = _observation_identity(observation)
        if identity in seen:
            raise VolumeThresholdRobustnessAnalysisError(
                "Volume threshold robustness observations must be unique by symbol, trading_date, and signal id."
            )
        seen.add(identity)


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


def _count_status(observations, status: OutcomeEvaluationStatus) -> int:
    return sum(observation.status is status for observation in observations)
