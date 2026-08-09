from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from historical_condition_outcome_service import ConditionOutcomeObservation
from historical_condition_outcome_service import HistoricalConditionOutcomeComparisonResult
from historical_condition_outcome_service import OutcomeStatusSummary
from models import OutcomeEvaluationStatus
from ui_terminology import get_diagnostic_condition_label


OBSERVATION_UNIT_DAILY = "DAILY"


class ConditionContributionAnalysisError(Exception):
    """Raised when condition contribution analysis inputs are invalid."""


@dataclass(frozen=True)
class ConditionContributionConfig:

    analysis_name: str = "單一條件影響分析"

    advanced_method_name: str = "Leave-One-Out Condition Analysis"

    observation_unit: str = OBSERVATION_UNIT_DAILY

    overlap_possible: bool = True


@dataclass(frozen=True)
class ConditionContributionComparison:

    condition_id: str

    condition_display_label: str

    baseline_observation_count: int

    baseline_hit_count: int

    baseline_miss_count: int

    baseline_incomplete_count: int

    baseline_not_evaluable_count: int

    baseline_resolved_count: int

    baseline_historical_hit_rate: float | None

    leave_one_out_observation_count: int

    leave_one_out_hit_count: int

    leave_one_out_miss_count: int

    leave_one_out_incomplete_count: int

    leave_one_out_not_evaluable_count: int

    leave_one_out_resolved_count: int

    leave_one_out_historical_hit_rate: float | None

    added_observation_count: int

    added_resolved_count: int

    added_hit_count: int

    added_miss_count: int

    observation_increase_rate: float | None

    historical_hit_rate_delta_percentage_points: float | None


@dataclass(frozen=True)
class ConditionContributionSymbolSummary:

    symbol: str

    comparisons: tuple[ConditionContributionComparison, ...]


@dataclass(frozen=True)
class ConditionContributionResult:

    config: ConditionContributionConfig

    source_signal_definition_id: str

    source_outcome_definition_id: str

    source_warmup_trading_bars: int

    baseline_summary: OutcomeStatusSummary

    condition_comparisons: tuple[ConditionContributionComparison, ...]

    per_symbol_summaries: tuple[ConditionContributionSymbolSummary, ...]

    aggregate_summary: tuple[ConditionContributionComparison, ...]

    observation_unit: str

    overlap_possible: bool

    generated_at: datetime


def analyze_condition_contribution(
    comparison_result: HistoricalConditionOutcomeComparisonResult,
    *,
    config: ConditionContributionConfig | None = None,
    generated_at: datetime | None = None,
) -> ConditionContributionResult:
    config = config or ConditionContributionConfig(
        observation_unit=comparison_result.observation_unit,
        overlap_possible=comparison_result.overlap_possible,
    )
    condition_ids = _condition_ids_from_result(comparison_result)
    observations = tuple(comparison_result.outcome_observations)
    _validate_unique_observations(observations)

    baseline = _baseline_observations(observations)
    baseline_summary = _outcome_summary(baseline)
    comparisons = _condition_comparisons(
        observations,
        condition_ids,
        baseline=baseline,
        baseline_summary=baseline_summary,
    )
    symbols = comparison_result.diagnostics_result.normalized_symbols or tuple(
        sorted({observation.symbol for observation in observations})
    )

    return ConditionContributionResult(
        config=config,
        source_signal_definition_id=comparison_result.diagnostics_result.config.signal_definition.id,
        source_outcome_definition_id=comparison_result.config.outcome_definition.id,
        source_warmup_trading_bars=comparison_result.config.warmup_trading_bars,
        baseline_summary=baseline_summary,
        condition_comparisons=comparisons,
        per_symbol_summaries=tuple(
            ConditionContributionSymbolSummary(
                symbol=symbol,
                comparisons=_condition_comparisons(
                    tuple(observation for observation in observations if observation.symbol == symbol),
                    condition_ids,
                    baseline=tuple(observation for observation in baseline if observation.symbol == symbol),
                    baseline_summary=_outcome_summary(
                        tuple(observation for observation in baseline if observation.symbol == symbol)
                    ),
                ),
            )
            for symbol in symbols
        ),
        aggregate_summary=comparisons,
        observation_unit=config.observation_unit,
        overlap_possible=config.overlap_possible,
        generated_at=generated_at or datetime.now(UTC),
    )


def _condition_comparisons(
    observations: tuple[ConditionOutcomeObservation, ...],
    condition_ids: tuple[str, ...],
    *,
    baseline: tuple[ConditionOutcomeObservation, ...],
    baseline_summary: OutcomeStatusSummary,
) -> tuple[ConditionContributionComparison, ...]:
    baseline_by_key = {
        _observation_identity(observation): observation
        for observation in baseline
    }
    rows = []
    for condition_id in condition_ids:
        added = _only_missing_condition_observations(observations, condition_id)
        added_by_key = {
            _observation_identity(observation): observation
            for observation in added
        }
        overlap = set(baseline_by_key).intersection(added_by_key)
        if overlap:
            raise ConditionContributionAnalysisError(
                "Baseline and only-missing observations must not overlap."
            )
        leave_one_out = tuple(baseline_by_key.values()) + tuple(added_by_key.values())
        if len(leave_one_out) != len(baseline_by_key) + len(added_by_key):
            raise ConditionContributionAnalysisError("Leave-one-out observations must not be duplicated.")
        leave_one_out_summary = _outcome_summary(leave_one_out)
        added_summary = _outcome_summary(tuple(added_by_key.values()))
        rows.append(
            _comparison(
                condition_id,
                baseline_summary=baseline_summary,
                leave_one_out_summary=leave_one_out_summary,
                added_summary=added_summary,
            )
        )
    return tuple(rows)


def _comparison(
    condition_id: str,
    *,
    baseline_summary: OutcomeStatusSummary,
    leave_one_out_summary: OutcomeStatusSummary,
    added_summary: OutcomeStatusSummary,
) -> ConditionContributionComparison:
    return ConditionContributionComparison(
        condition_id=condition_id,
        condition_display_label=get_diagnostic_condition_label(condition_id),
        baseline_observation_count=baseline_summary.observation_count,
        baseline_hit_count=baseline_summary.hit_count,
        baseline_miss_count=baseline_summary.miss_count,
        baseline_incomplete_count=baseline_summary.incomplete_count,
        baseline_not_evaluable_count=baseline_summary.not_evaluable_count,
        baseline_resolved_count=baseline_summary.resolved_count,
        baseline_historical_hit_rate=baseline_summary.historical_hit_rate,
        leave_one_out_observation_count=leave_one_out_summary.observation_count,
        leave_one_out_hit_count=leave_one_out_summary.hit_count,
        leave_one_out_miss_count=leave_one_out_summary.miss_count,
        leave_one_out_incomplete_count=leave_one_out_summary.incomplete_count,
        leave_one_out_not_evaluable_count=leave_one_out_summary.not_evaluable_count,
        leave_one_out_resolved_count=leave_one_out_summary.resolved_count,
        leave_one_out_historical_hit_rate=leave_one_out_summary.historical_hit_rate,
        added_observation_count=added_summary.observation_count,
        added_resolved_count=added_summary.resolved_count,
        added_hit_count=added_summary.hit_count,
        added_miss_count=added_summary.miss_count,
        observation_increase_rate=_increase_rate(
            baseline_summary.observation_count,
            leave_one_out_summary.observation_count,
        ),
        historical_hit_rate_delta_percentage_points=_hit_rate_delta_percentage_points(
            baseline_summary.historical_hit_rate,
            leave_one_out_summary.historical_hit_rate,
        ),
    )


def _baseline_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
) -> tuple[ConditionOutcomeObservation, ...]:
    return tuple(
        observation for observation in observations
        if observation.matched_condition_count == observation.total_condition_count
    )


def _only_missing_condition_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
    condition_id: str,
) -> tuple[ConditionOutcomeObservation, ...]:
    return tuple(
        observation for observation in observations
        if observation.matched_condition_count == observation.total_condition_count - 1
        and observation.missing_condition_ids == (condition_id,)
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


def _validate_unique_observations(
    observations: tuple[ConditionOutcomeObservation, ...],
) -> None:
    seen = set()
    for observation in observations:
        identity = _observation_identity(observation)
        if identity in seen:
            raise ConditionContributionAnalysisError(
                "Condition contribution observations must be unique by symbol, trading_date, and signal id."
            )
        seen.add(identity)


def _observation_identity(observation: ConditionOutcomeObservation) -> tuple[str, object, str]:
    return (
        observation.symbol,
        observation.trading_date,
        observation.signal_definition_id,
    )


def _condition_ids_from_result(
    comparison_result: HistoricalConditionOutcomeComparisonResult,
) -> tuple[str, ...]:
    return tuple(
        summary.condition_id
        for summary in comparison_result.diagnostics_result.condition_pass_summaries
    )


def _increase_rate(baseline_count: int, leave_one_out_count: int) -> float | None:
    if baseline_count == 0:
        return None
    return (leave_one_out_count - baseline_count) / baseline_count


def _hit_rate_delta_percentage_points(
    baseline_rate: float | None,
    leave_one_out_rate: float | None,
) -> float | None:
    if baseline_rate is None or leave_one_out_rate is None:
        return None
    return (leave_one_out_rate - baseline_rate) * 100


def _count_status(observations, status: OutcomeEvaluationStatus) -> int:
    return sum(observation.status is status for observation in observations)
