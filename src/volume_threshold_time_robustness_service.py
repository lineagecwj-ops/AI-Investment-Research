from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime

from historical_condition_outcome_service import ConditionOutcomeObservation
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonResult
from historical_condition_outcome_service import OutcomeStatusSummary
from models import OutcomeEvaluationStatus
from volume_threshold_sensitivity_service import _other_v1_conditions_pass
from volume_threshold_sensitivity_service import _validate_unique_observations
from volume_threshold_sensitivity_service import _validate_volume_condition
from volume_threshold_sensitivity_service import _volume_ratio_qualifies


ACTIVE_V1_1_RESEARCH_THRESHOLDS = (1.10, 1.20)
FORMAL_V1_BASELINE_THRESHOLD = 1.20
FROZEN_TIME_ROBUSTNESS_PERIODS = (
    ("PERIOD_A", date(2018, 1, 1), date(2020, 12, 31)),
    ("PERIOD_B", date(2021, 1, 1), date(2023, 12, 31)),
    ("PERIOD_C", date(2024, 1, 1), date(2024, 12, 31)),
    ("PERIOD_D", date(2025, 1, 1), date(2025, 12, 31)),
)


class VolumeThresholdTimeRobustnessAnalysisError(Exception):
    """Raised when V1.1 time robustness inputs are invalid."""


@dataclass(frozen=True)
class TimeRobustnessPeriod:

    name: str

    start_date: date

    end_date: date


@dataclass(frozen=True)
class ThresholdOutcomeSummary:

    threshold: float

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    observation_count_delta_vs_1_20: int

    observation_count_change_rate_vs_1_20: float | None

    hit_count_delta_vs_1_20: int

    miss_count_delta_vs_1_20: int

    historical_hit_rate_delta_vs_1_20_pp: float | None


@dataclass(frozen=True)
class PeriodThresholdSummary:

    period_name: str

    period_start: date

    period_end: date

    eligible_symbol_count: int

    threshold_summary: ThresholdOutcomeSummary


@dataclass(frozen=True)
class PeriodSymbolBreadthSummary:

    period_name: str

    candidate_threshold: float

    baseline_threshold: float

    baseline_resolved_symbols: int

    candidate_positive_delta_symbols: int

    candidate_negative_delta_symbols: int

    candidate_same_delta_symbols: int

    candidate_unavailable_symbols: int

    candidate_added_sample_symbols: tuple[str, ...]

    baseline_resolved_sample_sizes: tuple[int, ...]

    candidate_resolved_sample_sizes: tuple[int, ...]


@dataclass(frozen=True)
class PeriodConcentrationSummary:

    period_name: str

    threshold: float

    observation_count: int

    largest_symbol: str | None

    largest_symbol_observation_count: int

    top_1_symbol_share: float | None

    top_2_symbol_share: float | None

    top_5_symbol_share: float | None

    top_10_symbol_share: float | None


@dataclass(frozen=True)
class FirstQualificationEvent:

    symbol: str

    event_start_trading_date: date

    signal_definition_id: str

    threshold: float

    source_observation: ConditionOutcomeObservation

    @property
    def outcome_status(self) -> OutcomeEvaluationStatus:
        return self.source_observation.status


@dataclass(frozen=True)
class EventThresholdSummary:

    threshold: float

    daily_qualified_observation_count: int

    first_qualification_event_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    event_hit_rate: float | None

    event_count_delta_vs_1_20: int

    event_count_change_rate_vs_1_20: float | None

    hit_count_delta_vs_1_20: int

    miss_count_delta_vs_1_20: int

    event_hit_rate_delta_vs_1_20_pp: float | None

    contributing_symbols: int


@dataclass(frozen=True)
class EventPeriodSummary:

    period_name: str

    period_start: date

    period_end: date

    threshold_summary: ThresholdOutcomeSummary


@dataclass(frozen=True)
class EventConcentrationSummary:

    threshold: float

    event_count: int

    year_2025_share: float | None

    largest_year: int | None

    largest_year_share: float | None

    top_1_symbol_share: float | None

    top_2_symbol_share: float | None

    top_5_symbol_share: float | None

    top_10_symbol_share: float | None


@dataclass(frozen=True)
class TimeRobustnessResult:

    thresholds: tuple[float, ...]

    baseline_threshold: float

    periods: tuple[TimeRobustnessPeriod, ...]

    daily_summaries: tuple[ThresholdOutcomeSummary, ...]

    period_summaries: tuple[PeriodThresholdSummary, ...]

    period_symbol_breadth: tuple[PeriodSymbolBreadthSummary, ...]

    period_concentration: tuple[PeriodConcentrationSummary, ...]

    excluding_2025_summaries: tuple[ThresholdOutcomeSummary, ...]

    first_qualification_events: tuple[FirstQualificationEvent, ...]

    event_summaries: tuple[EventThresholdSummary, ...]

    event_period_summaries: tuple[EventPeriodSummary, ...]

    event_concentration: tuple[EventConcentrationSummary, ...]

    generated_at: datetime


def analyze_volume_threshold_time_robustness(
    comparison_result: HistoricalConditionOutcomeComparisonResult,
    *,
    thresholds: tuple[float, ...] = ACTIVE_V1_1_RESEARCH_THRESHOLDS,
    periods: tuple[TimeRobustnessPeriod, ...] | None = None,
    generated_at: datetime | None = None,
) -> TimeRobustnessResult:
    thresholds = _validate_active_thresholds(thresholds)
    periods = periods or _default_periods()
    observations = tuple(comparison_result.outcome_observations)
    _validate_unique_observations(observations)
    _validate_volume_condition(comparison_result)
    _validate_periods(periods)
    symbols = comparison_result.diagnostics_result.normalized_symbols or tuple(
        sorted({observation.symbol for observation in observations})
    )
    qualified_by_threshold = {
        threshold: _qualified_observations(observations, threshold)
        for threshold in thresholds
    }
    baseline_summary = _outcome_summary(qualified_by_threshold[FORMAL_V1_BASELINE_THRESHOLD])
    daily_summaries = tuple(
        _threshold_summary(
            threshold,
            _outcome_summary(qualified_by_threshold[threshold]),
            baseline_summary=baseline_summary,
        )
        for threshold in thresholds
    )
    period_summaries = _period_summaries(periods, thresholds, qualified_by_threshold, observations)
    events_by_threshold = {
        threshold: _first_qualification_events(observations, threshold)
        for threshold in thresholds
    }
    all_events = tuple(
        event
        for threshold in thresholds
        for event in events_by_threshold[threshold]
    )
    event_baseline_summary = _event_outcome_summary(events_by_threshold[FORMAL_V1_BASELINE_THRESHOLD])
    return TimeRobustnessResult(
        thresholds=thresholds,
        baseline_threshold=FORMAL_V1_BASELINE_THRESHOLD,
        periods=periods,
        daily_summaries=daily_summaries,
        period_summaries=period_summaries,
        period_symbol_breadth=_period_symbol_breadth(periods, thresholds, qualified_by_threshold, symbols),
        period_concentration=_period_concentration(periods, thresholds, qualified_by_threshold),
        excluding_2025_summaries=_excluding_2025_summaries(periods, thresholds, qualified_by_threshold),
        first_qualification_events=all_events,
        event_summaries=tuple(
            _event_threshold_summary(
                threshold,
                daily_qualified_observation_count=len(qualified_by_threshold[threshold]),
                events=events_by_threshold[threshold],
                baseline_summary=event_baseline_summary,
            )
            for threshold in thresholds
        ),
        event_period_summaries=_event_period_summaries(periods, thresholds, events_by_threshold),
        event_concentration=tuple(
            _event_concentration(threshold, events_by_threshold[threshold])
            for threshold in thresholds
        ),
        generated_at=generated_at or datetime.now(UTC),
    )


def _default_periods() -> tuple[TimeRobustnessPeriod, ...]:
    return tuple(TimeRobustnessPeriod(name, start, end) for name, start, end in FROZEN_TIME_ROBUSTNESS_PERIODS)


def _validate_active_thresholds(thresholds: tuple[float, ...]) -> tuple[float, ...]:
    normalized = tuple(float(threshold) for threshold in thresholds)
    if normalized != ACTIVE_V1_1_RESEARCH_THRESHOLDS:
        raise VolumeThresholdTimeRobustnessAnalysisError(
            "V1.1 Batch 2 active thresholds must be exactly 1.10 and 1.20."
        )
    return normalized


def _validate_periods(periods: tuple[TimeRobustnessPeriod, ...]) -> None:
    previous_end = None
    for period in periods:
        if period.start_date > period.end_date:
            raise VolumeThresholdTimeRobustnessAnalysisError("Period start date cannot be after end date.")
        if previous_end is not None and period.start_date <= previous_end:
            raise VolumeThresholdTimeRobustnessAnalysisError("Periods must be non-overlapping and ascending.")
        previous_end = period.end_date


def _qualified_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
    threshold: float,
) -> tuple[ConditionOutcomeObservation, ...]:
    return tuple(
        observation
        for observation in observations
        if _qualifies(observation, threshold)
    )


def _qualifies(observation: ConditionOutcomeObservation, threshold: float) -> bool:
    return _other_v1_conditions_pass(observation) and _volume_ratio_qualifies(observation, threshold)


def _period_summaries(
    periods: tuple[TimeRobustnessPeriod, ...],
    thresholds: tuple[float, ...],
    qualified_by_threshold: dict[float, tuple[ConditionOutcomeObservation, ...]],
    observations: tuple[ConditionOutcomeObservation, ...],
) -> tuple[PeriodThresholdSummary, ...]:
    rows = []
    eligible_symbol_count_by_period = {
        period.name: len({
            observation.symbol
            for observation in observations
            if period.start_date <= observation.trading_date <= period.end_date
            and observation.status is not OutcomeEvaluationStatus.NOT_EVALUABLE
        })
        for period in periods
    }
    for period in periods:
        baseline = _outcome_summary(_filter_observations_for_period(
            qualified_by_threshold[FORMAL_V1_BASELINE_THRESHOLD],
            period,
        ))
        for threshold in thresholds:
            summary = _outcome_summary(_filter_observations_for_period(qualified_by_threshold[threshold], period))
            rows.append(
                PeriodThresholdSummary(
                    period_name=period.name,
                    period_start=period.start_date,
                    period_end=period.end_date,
                    eligible_symbol_count=eligible_symbol_count_by_period[period.name],
                    threshold_summary=_threshold_summary(threshold, summary, baseline_summary=baseline),
                )
            )
    return tuple(rows)


def _period_symbol_breadth(
    periods: tuple[TimeRobustnessPeriod, ...],
    thresholds: tuple[float, ...],
    qualified_by_threshold: dict[float, tuple[ConditionOutcomeObservation, ...]],
    symbols: tuple[str, ...],
) -> tuple[PeriodSymbolBreadthSummary, ...]:
    rows = []
    for period in periods:
        baseline_by_symbol = _symbol_summaries(
            symbols,
            _filter_observations_for_period(qualified_by_threshold[FORMAL_V1_BASELINE_THRESHOLD], period),
        )
        for threshold in thresholds:
            if threshold == FORMAL_V1_BASELINE_THRESHOLD:
                continue
            candidate_by_symbol = _symbol_summaries(
                symbols,
                _filter_observations_for_period(qualified_by_threshold[threshold], period),
            )
            positive = negative = same = unavailable = baseline_resolved = 0
            added = []
            baseline_sizes = []
            candidate_sizes = []
            for symbol in symbols:
                baseline = baseline_by_symbol[symbol]
                candidate = candidate_by_symbol[symbol]
                if baseline.resolved_count > 0:
                    baseline_resolved += 1
                    baseline_sizes.append(baseline.resolved_count)
                if candidate.resolved_count > 0:
                    candidate_sizes.append(candidate.resolved_count)
                if baseline.observation_count == 0 and candidate.observation_count > 0:
                    added.append(symbol)
                if baseline.historical_hit_rate is None or candidate.historical_hit_rate is None:
                    unavailable += 1
                elif candidate.historical_hit_rate > baseline.historical_hit_rate:
                    positive += 1
                elif candidate.historical_hit_rate < baseline.historical_hit_rate:
                    negative += 1
                else:
                    same += 1
            rows.append(
                PeriodSymbolBreadthSummary(
                    period_name=period.name,
                    candidate_threshold=threshold,
                    baseline_threshold=FORMAL_V1_BASELINE_THRESHOLD,
                    baseline_resolved_symbols=baseline_resolved,
                    candidate_positive_delta_symbols=positive,
                    candidate_negative_delta_symbols=negative,
                    candidate_same_delta_symbols=same,
                    candidate_unavailable_symbols=unavailable,
                    candidate_added_sample_symbols=tuple(added),
                    baseline_resolved_sample_sizes=tuple(sorted(baseline_sizes)),
                    candidate_resolved_sample_sizes=tuple(sorted(candidate_sizes)),
                )
            )
    return tuple(rows)


def _period_concentration(
    periods: tuple[TimeRobustnessPeriod, ...],
    thresholds: tuple[float, ...],
    qualified_by_threshold: dict[float, tuple[ConditionOutcomeObservation, ...]],
) -> tuple[PeriodConcentrationSummary, ...]:
    return tuple(
        _concentration(period.name, threshold, _filter_observations_for_period(qualified_by_threshold[threshold], period))
        for period in periods
        for threshold in thresholds
    )


def _excluding_2025_summaries(
    periods: tuple[TimeRobustnessPeriod, ...],
    thresholds: tuple[float, ...],
    qualified_by_threshold: dict[float, tuple[ConditionOutcomeObservation, ...]],
) -> tuple[ThresholdOutcomeSummary, ...]:
    included_periods = tuple(period for period in periods if period.end_date < date(2025, 1, 1))
    by_threshold = {
        threshold: tuple(
            observation
            for period in included_periods
            for observation in _filter_observations_for_period(qualified_by_threshold[threshold], period)
        )
        for threshold in thresholds
    }
    baseline = _outcome_summary(by_threshold[FORMAL_V1_BASELINE_THRESHOLD])
    return tuple(
        _threshold_summary(threshold, _outcome_summary(by_threshold[threshold]), baseline_summary=baseline)
        for threshold in thresholds
    )


def _first_qualification_events(
    observations: tuple[ConditionOutcomeObservation, ...],
    threshold: float,
) -> tuple[FirstQualificationEvent, ...]:
    events = []
    by_symbol: dict[str, list[ConditionOutcomeObservation]] = {}
    for observation in observations:
        by_symbol.setdefault(observation.symbol, []).append(observation)
    for symbol in sorted(by_symbol):
        was_qualified = False
        for observation in sorted(by_symbol[symbol], key=lambda item: (item.trading_date, item.signal_definition_id)):
            is_qualified = _qualifies(observation, threshold)
            if is_qualified and not was_qualified:
                events.append(
                    FirstQualificationEvent(
                        symbol=observation.symbol,
                        event_start_trading_date=observation.trading_date,
                        signal_definition_id=observation.signal_definition_id,
                        threshold=threshold,
                        source_observation=observation,
                    )
                )
            was_qualified = is_qualified
    _validate_unique_events(tuple(events))
    return tuple(events)


def _event_threshold_summary(
    threshold: float,
    *,
    daily_qualified_observation_count: int,
    events: tuple[FirstQualificationEvent, ...],
    baseline_summary: OutcomeStatusSummary,
) -> EventThresholdSummary:
    summary = _event_outcome_summary(events)
    return EventThresholdSummary(
        threshold=threshold,
        daily_qualified_observation_count=daily_qualified_observation_count,
        first_qualification_event_count=summary.observation_count,
        hit_count=summary.hit_count,
        miss_count=summary.miss_count,
        incomplete_count=summary.incomplete_count,
        not_evaluable_count=summary.not_evaluable_count,
        resolved_count=summary.resolved_count,
        event_hit_rate=summary.historical_hit_rate,
        event_count_delta_vs_1_20=summary.observation_count - baseline_summary.observation_count,
        event_count_change_rate_vs_1_20=_change_rate(baseline_summary.observation_count, summary.observation_count),
        hit_count_delta_vs_1_20=summary.hit_count - baseline_summary.hit_count,
        miss_count_delta_vs_1_20=summary.miss_count - baseline_summary.miss_count,
        event_hit_rate_delta_vs_1_20_pp=_hit_rate_delta_percentage_points(
            baseline_summary.historical_hit_rate,
            summary.historical_hit_rate,
        ),
        contributing_symbols=len({event.symbol for event in events}),
    )


def _event_period_summaries(
    periods: tuple[TimeRobustnessPeriod, ...],
    thresholds: tuple[float, ...],
    events_by_threshold: dict[float, tuple[FirstQualificationEvent, ...]],
) -> tuple[EventPeriodSummary, ...]:
    rows = []
    for period in periods:
        baseline = _event_outcome_summary(_filter_events_for_period(
            events_by_threshold[FORMAL_V1_BASELINE_THRESHOLD],
            period,
        ))
        for threshold in thresholds:
            summary = _event_outcome_summary(_filter_events_for_period(events_by_threshold[threshold], period))
            rows.append(
                EventPeriodSummary(
                    period_name=period.name,
                    period_start=period.start_date,
                    period_end=period.end_date,
                    threshold_summary=_threshold_summary(threshold, summary, baseline_summary=baseline),
                )
            )
    return tuple(rows)


def _event_concentration(
    threshold: float,
    events: tuple[FirstQualificationEvent, ...],
) -> EventConcentrationSummary:
    total = len(events)
    by_year: dict[int, int] = {}
    by_symbol: dict[str, int] = {}
    for event in events:
        by_year[event.event_start_trading_date.year] = by_year.get(event.event_start_trading_date.year, 0) + 1
        by_symbol[event.symbol] = by_symbol.get(event.symbol, 0) + 1
    largest_year = min(
        (year for year, count in by_year.items() if count == max(by_year.values(), default=0)),
        default=None,
    )
    largest_year_count = 0 if largest_year is None else by_year[largest_year]
    top_counts = sorted(by_symbol.values(), reverse=True)
    return EventConcentrationSummary(
        threshold=threshold,
        event_count=total,
        year_2025_share=_share(by_year.get(2025, 0), total),
        largest_year=largest_year,
        largest_year_share=_share(largest_year_count, total),
        top_1_symbol_share=_share(sum(top_counts[:1]), total),
        top_2_symbol_share=_share(sum(top_counts[:2]), total),
        top_5_symbol_share=_share(sum(top_counts[:5]), total),
        top_10_symbol_share=_share(sum(top_counts[:10]), total),
    )


def _symbol_summaries(
    symbols: tuple[str, ...],
    observations: tuple[ConditionOutcomeObservation, ...],
) -> dict[str, OutcomeStatusSummary]:
    return {
        symbol: _outcome_summary(tuple(observation for observation in observations if observation.symbol == symbol))
        for symbol in symbols
    }


def _concentration(
    period_name: str,
    threshold: float,
    observations: tuple[ConditionOutcomeObservation, ...],
) -> PeriodConcentrationSummary:
    total = len(observations)
    by_symbol: dict[str, int] = {}
    for observation in observations:
        by_symbol[observation.symbol] = by_symbol.get(observation.symbol, 0) + 1
    largest_count = max(by_symbol.values(), default=0)
    largest_symbol = min((symbol for symbol, count in by_symbol.items() if count == largest_count), default=None)
    top_counts = sorted(by_symbol.values(), reverse=True)
    return PeriodConcentrationSummary(
        period_name=period_name,
        threshold=threshold,
        observation_count=total,
        largest_symbol=largest_symbol,
        largest_symbol_observation_count=largest_count,
        top_1_symbol_share=_share(sum(top_counts[:1]), total),
        top_2_symbol_share=_share(sum(top_counts[:2]), total),
        top_5_symbol_share=_share(sum(top_counts[:5]), total),
        top_10_symbol_share=_share(sum(top_counts[:10]), total),
    )


def _threshold_summary(
    threshold: float,
    summary: OutcomeStatusSummary,
    *,
    baseline_summary: OutcomeStatusSummary,
) -> ThresholdOutcomeSummary:
    return ThresholdOutcomeSummary(
        threshold=threshold,
        observation_count=summary.observation_count,
        hit_count=summary.hit_count,
        miss_count=summary.miss_count,
        incomplete_count=summary.incomplete_count,
        not_evaluable_count=summary.not_evaluable_count,
        resolved_count=summary.resolved_count,
        historical_hit_rate=summary.historical_hit_rate,
        observation_count_delta_vs_1_20=summary.observation_count - baseline_summary.observation_count,
        observation_count_change_rate_vs_1_20=_change_rate(
            baseline_summary.observation_count,
            summary.observation_count,
        ),
        hit_count_delta_vs_1_20=summary.hit_count - baseline_summary.hit_count,
        miss_count_delta_vs_1_20=summary.miss_count - baseline_summary.miss_count,
        historical_hit_rate_delta_vs_1_20_pp=_hit_rate_delta_percentage_points(
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


def _event_outcome_summary(events: tuple[FirstQualificationEvent, ...]) -> OutcomeStatusSummary:
    return _outcome_summary(tuple(event.source_observation for event in events))


def _filter_observations_for_period(
    observations: tuple[ConditionOutcomeObservation, ...],
    period: TimeRobustnessPeriod,
) -> tuple[ConditionOutcomeObservation, ...]:
    return tuple(
        observation
        for observation in observations
        if period.start_date <= observation.trading_date <= period.end_date
    )


def _filter_events_for_period(
    events: tuple[FirstQualificationEvent, ...],
    period: TimeRobustnessPeriod,
) -> tuple[FirstQualificationEvent, ...]:
    return tuple(
        event
        for event in events
        if period.start_date <= event.event_start_trading_date <= period.end_date
    )


def _validate_unique_events(events: tuple[FirstQualificationEvent, ...]) -> None:
    seen = set()
    for event in events:
        identity = (
            event.symbol,
            event.event_start_trading_date,
            event.signal_definition_id,
            event.threshold,
        )
        if identity in seen:
            raise VolumeThresholdTimeRobustnessAnalysisError("First qualification event identity must be unique.")
        seen.add(identity)


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


def _share(count: int, total: int) -> float | None:
    if total == 0:
        return None
    return count / total


def _count_status(observations, status: OutcomeEvaluationStatus) -> int:
    return sum(observation.status is status for observation in observations)
