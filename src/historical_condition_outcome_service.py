from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from models import HistoricalOutcomeResult
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import SignalEvent
from signal_condition_diagnostics_service import ConditionDiagnosticObservation
from signal_condition_diagnostics_service import HistoricalConditionDiagnosticsResult
from signal_condition_diagnostics_service import condition_diagnostic_id
from signal_outcome_service import evaluate_historical_outcome
from technical_indicator_service import build_technical_indicator_series
from ui_terminology import get_diagnostic_condition_label


DEFAULT_DIAGNOSTIC_WARMUP_TRADING_BARS = 60
OBSERVATION_UNIT_DAILY = "DAILY"


class HistoricalConditionOutcomeComparisonError(Exception):
    """Raised when historical condition/outcome comparison inputs are invalid."""


@dataclass(frozen=True)
class HistoricalConditionOutcomeComparisonConfig:

    outcome_definition: OutcomeDefinition

    warmup_trading_bars: int = DEFAULT_DIAGNOSTIC_WARMUP_TRADING_BARS

    observation_unit: str = OBSERVATION_UNIT_DAILY

    overlap_possible: bool = True

    def __post_init__(self):
        if self.warmup_trading_bars < 0:
            raise HistoricalConditionOutcomeComparisonError("warmup_trading_bars cannot be negative.")


@dataclass(frozen=True)
class ConditionOutcomeObservation:

    source_observation_id: str

    symbol: str

    trading_date: object

    signal_definition_id: str

    outcome_definition_id: str

    matched_condition_count: int

    total_condition_count: int

    passed_condition_ids: tuple[str, ...]

    missing_condition_ids: tuple[str, ...]

    diagnostic_observation: ConditionDiagnosticObservation

    outcome: HistoricalOutcomeResult

    @property
    def status(self) -> OutcomeEvaluationStatus:
        return self.outcome.status


@dataclass(frozen=True)
class OutcomeStatusSummary:

    observation_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None


@dataclass(frozen=True)
class MatchCountOutcomeSummary:

    matched_count: int

    total_count: int

    outcome_summary: OutcomeStatusSummary


@dataclass(frozen=True)
class MissingConditionOutcomeSummary:

    condition_id: str

    display_name: str

    outcome_summary: OutcomeStatusSummary


@dataclass(frozen=True)
class ConditionCombinationOutcomeSummary:

    passed_condition_ids: tuple[str, ...]

    display_names: tuple[str, ...]

    matched_count: int

    outcome_summary: OutcomeStatusSummary


@dataclass(frozen=True)
class SymbolConditionOutcomeComparisonSummary:

    symbol: str

    observation_count: int

    match_count_outcome_summaries: tuple[MatchCountOutcomeSummary, ...]

    missing_condition_outcome_summaries: tuple[MissingConditionOutcomeSummary, ...]

    condition_combination_outcome_summaries: tuple[ConditionCombinationOutcomeSummary, ...]


@dataclass(frozen=True)
class HistoricalConditionOutcomeComparisonResult:

    config: HistoricalConditionOutcomeComparisonConfig

    diagnostics_result: HistoricalConditionDiagnosticsResult

    source_observations: tuple[ConditionDiagnosticObservation, ...]

    outcome_observations: tuple[ConditionOutcomeObservation, ...]

    observation_count: int

    match_count_outcome_summaries: tuple[MatchCountOutcomeSummary, ...]

    missing_condition_outcome_summaries: tuple[MissingConditionOutcomeSummary, ...]

    condition_combination_outcome_summaries: tuple[ConditionCombinationOutcomeSummary, ...]

    per_symbol_summaries: tuple[SymbolConditionOutcomeComparisonSummary, ...]

    observation_unit: str

    overlap_possible: bool

    generated_at: datetime


def compare_historical_condition_outcomes(
    diagnostics_result: HistoricalConditionDiagnosticsResult,
    *,
    price_series_by_symbol: dict[str, HistoricalPriceSeries],
    config: HistoricalConditionOutcomeComparisonConfig,
    outcome_evaluator=evaluate_historical_outcome,
    generated_at: datetime | None = None,
) -> HistoricalConditionOutcomeComparisonResult:
    source_observations = tuple(
        observation for observation in diagnostics_result.observations
        if observation.is_evaluable
    )
    outcome_observations = tuple(
        _build_outcome_observation(
            observation,
            price_series_by_symbol,
            config,
            outcome_evaluator=outcome_evaluator,
        )
        for observation in source_observations
    )
    _validate_outcome_observation_count(source_observations, outcome_observations)

    condition_ids = _condition_ids_from_diagnostics(diagnostics_result)
    symbols = diagnostics_result.normalized_symbols or tuple(
        sorted({observation.symbol for observation in source_observations})
    )
    return HistoricalConditionOutcomeComparisonResult(
        config=config,
        diagnostics_result=diagnostics_result,
        source_observations=source_observations,
        outcome_observations=outcome_observations,
        observation_count=len(outcome_observations),
        match_count_outcome_summaries=_match_count_outcome_summaries(
            outcome_observations,
            total_count=len(condition_ids),
        ),
        missing_condition_outcome_summaries=_missing_condition_outcome_summaries(
            outcome_observations,
            condition_ids,
        ),
        condition_combination_outcome_summaries=_condition_combination_outcome_summaries(
            outcome_observations,
            condition_ids,
        ),
        per_symbol_summaries=tuple(
            _symbol_summary(symbol, outcome_observations, condition_ids)
            for symbol in symbols
        ),
        observation_unit=config.observation_unit,
        overlap_possible=config.overlap_possible,
        generated_at=generated_at or datetime.now(UTC),
    )


def prepare_diagnostic_research_series(
    price_series: HistoricalPriceSeries,
    *,
    observation_start,
    observation_end,
    outcome_horizon_bars: int,
    warmup_trading_bars: int = DEFAULT_DIAGNOSTIC_WARMUP_TRADING_BARS,
) -> HistoricalPriceSeries:
    if warmup_trading_bars < 0 or outcome_horizon_bars < 0:
        raise HistoricalConditionOutcomeComparisonError("warmup and outcome horizon cannot be negative.")
    if observation_start > observation_end:
        raise HistoricalConditionOutcomeComparisonError("observation_start cannot be after observation_end.")

    sorted_bars = tuple(sorted(price_series.bars, key=lambda bar: bar.trading_date))
    before = [bar for bar in sorted_bars if bar.trading_date < observation_start]
    observations = [bar for bar in sorted_bars if observation_start <= bar.trading_date <= observation_end]
    after = [bar for bar in sorted_bars if bar.trading_date > observation_end]
    selected_before = [] if warmup_trading_bars == 0 else before[-warmup_trading_bars:]
    selected_after = after[:outcome_horizon_bars]
    return HistoricalPriceSeries(
        symbol=price_series.symbol,
        currency=price_series.currency,
        bars=tuple(selected_before + observations + selected_after),
        fetched_at=price_series.fetched_at,
        is_stale=price_series.is_stale,
        source=price_series.source,
    )


def build_diagnostic_technical_series(
    price_series: HistoricalPriceSeries,
):
    return build_technical_indicator_series(price_series)


def _build_outcome_observation(
    observation: ConditionDiagnosticObservation,
    price_series_by_symbol: dict[str, HistoricalPriceSeries],
    config: HistoricalConditionOutcomeComparisonConfig,
    *,
    outcome_evaluator,
) -> ConditionOutcomeObservation:
    price_series = price_series_by_symbol.get(observation.symbol)
    if price_series is None:
        raise HistoricalConditionOutcomeComparisonError(
            f"Missing price series for diagnostic observation symbol: {observation.symbol}"
        )
    signal_event = _signal_event_from_observation(observation, price_series)
    outcome = outcome_evaluator(signal_event, price_series, config.outcome_definition)
    return ConditionOutcomeObservation(
        source_observation_id=build_source_observation_id(observation),
        symbol=observation.symbol,
        trading_date=observation.trading_date,
        signal_definition_id=observation.signal_definition_id,
        outcome_definition_id=config.outcome_definition.id,
        matched_condition_count=observation.matched_condition_count,
        total_condition_count=observation.total_condition_count,
        passed_condition_ids=observation.passed_condition_ids,
        missing_condition_ids=observation.missing_condition_ids,
        diagnostic_observation=observation,
        outcome=outcome,
    )


def build_source_observation_id(observation: ConditionDiagnosticObservation) -> str:
    return "|".join(
        (
            observation.symbol,
            observation.signal_definition_id,
            observation.trading_date.isoformat(),
            str(observation.matched_condition_count),
            ",".join(observation.passed_condition_ids),
            ",".join(observation.missing_condition_ids),
        )
    )


def _signal_event_from_observation(
    observation: ConditionDiagnosticObservation,
    price_series: HistoricalPriceSeries,
) -> SignalEvent:
    snapshot = observation.source_snapshot
    return SignalEvent(
        symbol=observation.symbol,
        signal_id=observation.signal_definition_id,
        signal_date=observation.trading_date,
        signal_analysis_close=snapshot.analysis_close,
        signal_raw_close=_raw_close_for_date(price_series, observation.trading_date),
        reference_high=getattr(snapshot, "prior_high_60d", None),
        reference_low=getattr(snapshot, "prior_low_60d", None),
        evaluation_status=observation.status,
        feature_snapshot=snapshot,
        evaluated_conditions=observation.evaluated_conditions,
    )


def _match_count_outcome_summaries(
    observations: tuple[ConditionOutcomeObservation, ...],
    *,
    total_count: int,
) -> tuple[MatchCountOutcomeSummary, ...]:
    rows = []
    for matched_count in range(total_count + 1):
        bucket = tuple(
            observation for observation in observations
            if observation.matched_condition_count == matched_count
        )
        rows.append(
            MatchCountOutcomeSummary(
                matched_count=matched_count,
                total_count=total_count,
                outcome_summary=_outcome_summary(bucket),
            )
        )
    return tuple(rows)


def _missing_condition_outcome_summaries(
    observations: tuple[ConditionOutcomeObservation, ...],
    condition_ids: tuple[str, ...],
) -> tuple[MissingConditionOutcomeSummary, ...]:
    four_of_five = tuple(
        observation for observation in observations
        if observation.matched_condition_count == observation.total_condition_count - 1
    )
    rows = []
    for condition_id in condition_ids:
        bucket = tuple(
            observation for observation in four_of_five
            if observation.missing_condition_ids == (condition_id,)
        )
        rows.append(
            MissingConditionOutcomeSummary(
                condition_id=condition_id,
                display_name=get_diagnostic_condition_label(condition_id),
                outcome_summary=_outcome_summary(bucket),
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.outcome_summary.observation_count, condition_ids.index(row.condition_id))))


def _condition_combination_outcome_summaries(
    observations: tuple[ConditionOutcomeObservation, ...],
    condition_ids: tuple[str, ...],
) -> tuple[ConditionCombinationOutcomeSummary, ...]:
    order = {condition_id: index for index, condition_id in enumerate(condition_ids)}
    grouped: dict[tuple[str, ...], list[ConditionOutcomeObservation]] = {}
    for observation in observations:
        canonical = tuple(
            sorted(observation.passed_condition_ids, key=lambda condition_id: order[condition_id])
        )
        grouped.setdefault(canonical, []).append(observation)

    rows = [
        ConditionCombinationOutcomeSummary(
            passed_condition_ids=combination,
            display_names=tuple(get_diagnostic_condition_label(condition_id) for condition_id in combination),
            matched_count=len(combination),
            outcome_summary=_outcome_summary(tuple(bucket)),
        )
        for combination, bucket in grouped.items()
    ]
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                -row.outcome_summary.observation_count,
                -row.matched_count,
                row.passed_condition_ids,
            ),
        )
    )


def _symbol_summary(
    symbol: str,
    observations: tuple[ConditionOutcomeObservation, ...],
    condition_ids: tuple[str, ...],
) -> SymbolConditionOutcomeComparisonSummary:
    symbol_observations = tuple(observation for observation in observations if observation.symbol == symbol)
    return SymbolConditionOutcomeComparisonSummary(
        symbol=symbol,
        observation_count=len(symbol_observations),
        match_count_outcome_summaries=_match_count_outcome_summaries(
            symbol_observations,
            total_count=len(condition_ids),
        ),
        missing_condition_outcome_summaries=_missing_condition_outcome_summaries(
            symbol_observations,
            condition_ids,
        ),
        condition_combination_outcome_summaries=_condition_combination_outcome_summaries(
            symbol_observations,
            condition_ids,
        ),
    )


def _outcome_summary(observations: tuple[ConditionOutcomeObservation, ...]) -> OutcomeStatusSummary:
    hit_count = _count_status(observations, OutcomeEvaluationStatus.HIT)
    miss_count = _count_status(observations, OutcomeEvaluationStatus.MISS)
    incomplete_count = _count_status(observations, OutcomeEvaluationStatus.INCOMPLETE)
    not_evaluable_count = _count_status(observations, OutcomeEvaluationStatus.NOT_EVALUABLE)
    resolved_count = hit_count + miss_count
    summary = OutcomeStatusSummary(
        observation_count=len(observations),
        hit_count=hit_count,
        miss_count=miss_count,
        incomplete_count=incomplete_count,
        not_evaluable_count=not_evaluable_count,
        resolved_count=resolved_count,
        historical_hit_rate=None if resolved_count == 0 else hit_count / resolved_count,
    )
    _validate_status_sum(summary)
    return summary


def _validate_status_sum(summary: OutcomeStatusSummary) -> None:
    status_total = (
        summary.hit_count
        + summary.miss_count
        + summary.incomplete_count
        + summary.not_evaluable_count
    )
    if status_total != summary.observation_count:
        raise HistoricalConditionOutcomeComparisonError(
            "Outcome status counts must equal observation_count."
        )


def _validate_outcome_observation_count(
    source_observations: tuple[ConditionDiagnosticObservation, ...],
    outcome_observations: tuple[ConditionOutcomeObservation, ...],
) -> None:
    if len(source_observations) != len(outcome_observations):
        raise HistoricalConditionOutcomeComparisonError(
            "Outcome observations must match source diagnostic observations."
        )


def _condition_ids_from_diagnostics(
    diagnostics_result: HistoricalConditionDiagnosticsResult,
) -> tuple[str, ...]:
    return tuple(
        condition_diagnostic_id(condition)
        for condition in diagnostics_result.config.signal_definition.conditions
    )


def _raw_close_for_date(price_series: HistoricalPriceSeries, trading_date) -> float | None:
    for bar in price_series.bars:
        if bar.trading_date == trading_date:
            return bar.close
    return None


def _count_status(observations, status: OutcomeEvaluationStatus) -> int:
    return sum(observation.status is status for observation in observations)
