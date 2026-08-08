from dataclasses import dataclass
from datetime import date
from statistics import median

from models import OutcomeEvaluationStatus


@dataclass(frozen=True)
class ReplayAnalyticsConfig:

    include_post_replay_outcomes: bool = True


@dataclass(frozen=True)
class ReplayOutcomeDistribution:

    post_replay_hit_count: int

    post_replay_miss_count: int

    post_replay_incomplete_count: int

    post_replay_not_evaluable_count: int

    @property
    def resolved_post_replay_count(self) -> int:
        return self.post_replay_hit_count + self.post_replay_miss_count


@dataclass(frozen=True)
class ReplayPeriodSummary:

    requested_replay_date: date

    candidate_count: int

    match_count: int

    no_match_count: int

    not_evaluable_count: int

    failure_count: int

    candidate_symbols: tuple[str, ...]

    resolved_post_replay_count: int

    post_replay_hit_count: int

    post_replay_miss_count: int

    post_replay_incomplete_count: int

    post_replay_not_evaluable_count: int


@dataclass(frozen=True)
class ReplayCandidateOccurrence:

    symbol: str

    requested_replay_date: date

    actual_signal_date: date | None

    research_priority_rank: int | None

    post_replay_outcome_status: OutcomeEvaluationStatus | None


@dataclass(frozen=True)
class ReplaySymbolSummary:

    symbol: str

    candidate_occurrence_count: int

    first_candidate_date: date

    last_candidate_date: date

    candidate_dates: tuple[date, ...]

    total_period_count: int

    candidate_period_share: float

    longest_consecutive_candidate_periods: int

    post_replay_hit_count: int

    post_replay_miss_count: int

    post_replay_incomplete_count: int

    post_replay_not_evaluable_count: int

    resolved_post_replay_count: int

    best_research_priority_rank: int | None

    worst_research_priority_rank: int | None

    median_research_priority_rank: float | None


@dataclass(frozen=True)
class ReplayCandidateSetTransition:

    previous_requested_date: date

    current_requested_date: date

    previous_candidate_count: int

    current_candidate_count: int

    shared_candidate_count: int

    candidate_jaccard_similarity: float

    candidate_turnover: float


@dataclass(frozen=True)
class ReplayStabilitySummary:

    total_period_count: int

    periods_with_candidates: int

    periods_without_candidates: int

    unique_candidate_symbols: int

    total_candidate_occurrences: int

    candidate_period_share: float

    candidate_set_transitions: tuple[ReplayCandidateSetTransition, ...]


@dataclass(frozen=True)
class ReplayAnalyticsResult:

    config: ReplayAnalyticsConfig

    stability_summary: ReplayStabilitySummary

    period_summaries: tuple[ReplayPeriodSummary, ...]

    symbol_summaries: tuple[ReplaySymbolSummary, ...]

    candidate_occurrences: tuple[ReplayCandidateOccurrence, ...]

    post_replay_outcome_distribution: ReplayOutcomeDistribution


class ReplayAnalyticsService:

    def build_analytics(
        self,
        walk_forward_result,
        config: ReplayAnalyticsConfig | None = None,
    ) -> ReplayAnalyticsResult:
        analytics_config = config or ReplayAnalyticsConfig()
        ordered_periods = tuple(
            sorted(
                walk_forward_result.period_results,
                key=lambda period: period.requested_replay_date,
            )
        )
        candidate_sets_by_date = {
            period.requested_replay_date: _candidate_symbol_set(period)
            for period in ordered_periods
        }
        occurrences = _build_occurrences(ordered_periods, analytics_config)
        period_summaries = tuple(
            _build_period_summary(period, analytics_config)
            for period in ordered_periods
        )
        outcome_distribution = _outcome_distribution(occurrences)
        symbol_summaries = _build_symbol_summaries(
            occurrences,
            total_period_count=len(ordered_periods),
            replay_date_sequence=tuple(period.requested_replay_date for period in ordered_periods),
        )
        stability_summary = ReplayStabilitySummary(
            total_period_count=len(ordered_periods),
            periods_with_candidates=sum(1 for summary in period_summaries if summary.candidate_count > 0),
            periods_without_candidates=sum(1 for summary in period_summaries if summary.candidate_count == 0),
            unique_candidate_symbols=len(symbol_summaries),
            total_candidate_occurrences=len(occurrences),
            candidate_period_share=_safe_share(
                sum(1 for summary in period_summaries if summary.candidate_count > 0),
                len(ordered_periods),
            ),
            candidate_set_transitions=_build_candidate_set_transitions(
                tuple(period.requested_replay_date for period in ordered_periods),
                candidate_sets_by_date,
            ),
        )
        return ReplayAnalyticsResult(
            config=analytics_config,
            stability_summary=stability_summary,
            period_summaries=period_summaries,
            symbol_summaries=symbol_summaries,
            candidate_occurrences=occurrences,
            post_replay_outcome_distribution=outcome_distribution,
        )


def build_replay_analytics(walk_forward_result, config: ReplayAnalyticsConfig | None = None) -> ReplayAnalyticsResult:
    return ReplayAnalyticsService().build_analytics(walk_forward_result, config)


def _build_period_summary(period, config: ReplayAnalyticsConfig) -> ReplayPeriodSummary:
    candidates = _period_candidates(period)
    distribution = _outcome_distribution(_build_candidate_occurrences(candidates, config))
    return ReplayPeriodSummary(
        requested_replay_date=period.requested_replay_date,
        candidate_count=len(candidates),
        match_count=period.matched_count,
        no_match_count=period.no_match_count,
        not_evaluable_count=period.not_evaluable_count,
        failure_count=period.failed_count,
        candidate_symbols=tuple(candidate.symbol for candidate in candidates),
        resolved_post_replay_count=distribution.resolved_post_replay_count,
        post_replay_hit_count=distribution.post_replay_hit_count,
        post_replay_miss_count=distribution.post_replay_miss_count,
        post_replay_incomplete_count=distribution.post_replay_incomplete_count,
        post_replay_not_evaluable_count=distribution.post_replay_not_evaluable_count,
    )


def _build_occurrences(
    periods,
    config: ReplayAnalyticsConfig,
) -> tuple[ReplayCandidateOccurrence, ...]:
    occurrences = []
    for period in periods:
        occurrences.extend(_build_candidate_occurrences(_period_candidates(period), config))
    return tuple(
        sorted(
            occurrences,
            key=lambda item: (
                item.requested_replay_date,
                _rank_sort_value(item.research_priority_rank),
                item.symbol,
            ),
        )
    )


def _build_candidate_occurrences(
    candidates,
    config: ReplayAnalyticsConfig,
) -> tuple[ReplayCandidateOccurrence, ...]:
    return tuple(
        ReplayCandidateOccurrence(
            symbol=candidate.symbol,
            requested_replay_date=candidate.requested_replay_date,
            actual_signal_date=getattr(candidate, "actual_signal_date", None),
            research_priority_rank=getattr(candidate, "research_rank", None),
            post_replay_outcome_status=_post_replay_status(candidate) if config.include_post_replay_outcomes else None,
        )
        for candidate in candidates
    )


def _build_symbol_summaries(
    occurrences: tuple[ReplayCandidateOccurrence, ...],
    *,
    total_period_count: int,
    replay_date_sequence: tuple[date, ...],
) -> tuple[ReplaySymbolSummary, ...]:
    by_symbol = {}
    for occurrence in occurrences:
        by_symbol.setdefault(occurrence.symbol, []).append(occurrence)

    summaries = []
    replay_position = {replay_date: index for index, replay_date in enumerate(replay_date_sequence)}
    for symbol, symbol_occurrences in by_symbol.items():
        ordered = tuple(sorted(symbol_occurrences, key=lambda item: item.requested_replay_date))
        candidate_dates = tuple(item.requested_replay_date for item in ordered)
        ranks = tuple(
            item.research_priority_rank
            for item in ordered
            if item.research_priority_rank is not None
        )
        summaries.append(
            ReplaySymbolSummary(
                symbol=symbol,
                candidate_occurrence_count=len(ordered),
                first_candidate_date=min(candidate_dates),
                last_candidate_date=max(candidate_dates),
                candidate_dates=candidate_dates,
                total_period_count=total_period_count,
                candidate_period_share=_safe_share(len(ordered), total_period_count),
                longest_consecutive_candidate_periods=_longest_consecutive_periods(candidate_dates, replay_position),
                post_replay_hit_count=_count_status(ordered, OutcomeEvaluationStatus.HIT),
                post_replay_miss_count=_count_status(ordered, OutcomeEvaluationStatus.MISS),
                post_replay_incomplete_count=_count_status(ordered, OutcomeEvaluationStatus.INCOMPLETE),
                post_replay_not_evaluable_count=_count_status(ordered, OutcomeEvaluationStatus.NOT_EVALUABLE),
                resolved_post_replay_count=(
                    _count_status(ordered, OutcomeEvaluationStatus.HIT)
                    + _count_status(ordered, OutcomeEvaluationStatus.MISS)
                ),
                best_research_priority_rank=min(ranks) if ranks else None,
                worst_research_priority_rank=max(ranks) if ranks else None,
                median_research_priority_rank=median(ranks) if ranks else None,
            )
        )
    return tuple(
        sorted(
            summaries,
            key=lambda item: (
                -item.candidate_occurrence_count,
                -item.longest_consecutive_candidate_periods,
                item.symbol,
            ),
        )
    )


def _build_candidate_set_transitions(
    replay_dates: tuple[date, ...],
    candidate_sets_by_date: dict[date, set[str]],
) -> tuple[ReplayCandidateSetTransition, ...]:
    transitions = []
    for previous_date, current_date in zip(replay_dates, replay_dates[1:]):
        previous_set = candidate_sets_by_date.get(previous_date, set())
        current_set = candidate_sets_by_date.get(current_date, set())
        shared_count = len(previous_set & current_set)
        union_count = len(previous_set | current_set)
        if union_count == 0:
            similarity = 1.0
        else:
            similarity = shared_count / union_count
        transitions.append(
            ReplayCandidateSetTransition(
                previous_requested_date=previous_date,
                current_requested_date=current_date,
                previous_candidate_count=len(previous_set),
                current_candidate_count=len(current_set),
                shared_candidate_count=shared_count,
                candidate_jaccard_similarity=similarity,
                candidate_turnover=1.0 - similarity,
            )
        )
    return tuple(transitions)


def _longest_consecutive_periods(
    candidate_dates: tuple[date, ...],
    replay_position: dict[date, int],
) -> int:
    if not candidate_dates:
        return 0
    positions = sorted(replay_position[candidate_date] for candidate_date in set(candidate_dates))
    longest = 1
    current = 1
    for previous, position in zip(positions, positions[1:]):
        if position == previous + 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
    return longest


def _outcome_distribution(occurrences: tuple[ReplayCandidateOccurrence, ...]) -> ReplayOutcomeDistribution:
    return ReplayOutcomeDistribution(
        post_replay_hit_count=_count_status(occurrences, OutcomeEvaluationStatus.HIT),
        post_replay_miss_count=_count_status(occurrences, OutcomeEvaluationStatus.MISS),
        post_replay_incomplete_count=_count_status(occurrences, OutcomeEvaluationStatus.INCOMPLETE),
        post_replay_not_evaluable_count=_count_status(occurrences, OutcomeEvaluationStatus.NOT_EVALUABLE),
    )


def _period_candidates(period) -> tuple:
    if period.replay_result is None:
        return tuple()
    return tuple(period.replay_result.match_candidates)


def _candidate_symbol_set(period) -> set[str]:
    return {candidate.symbol for candidate in _period_candidates(period)}


def _post_replay_status(candidate) -> OutcomeEvaluationStatus | None:
    outcome = getattr(candidate, "post_replay_outcome", None)
    return None if outcome is None else outcome.status


def _count_status(items, status: OutcomeEvaluationStatus) -> int:
    return sum(1 for item in items if item.post_replay_outcome_status is status)


def _safe_share(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _rank_sort_value(rank: int | None) -> int:
    return 1_000_000_000 if rank is None else rank
