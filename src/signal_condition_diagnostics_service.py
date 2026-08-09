from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime

from historical_price_service import get_historical_prices
from models import EvaluatedSignalCondition
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import SignalMatch
from models import TechnicalIndicatorSeries
from signal_outcome_service import evaluate_signal_conditions
from symbol_utils import normalize_stock_symbol
from technical_indicator_service import build_technical_indicator_series
from ui_terminology import get_diagnostic_condition_label


class HistoricalConditionDiagnosticsError(Exception):
    """Raised when historical condition diagnostics inputs are invalid."""


@dataclass(frozen=True)
class HistoricalConditionDiagnosticsConfig:

    start_date: date

    end_date: date

    signal_definition: SignalDefinition

    force_refresh: bool = False

    def __post_init__(self):
        if self.start_date > self.end_date:
            raise HistoricalConditionDiagnosticsError("start_date cannot be after end_date.")


@dataclass(frozen=True)
class ConditionDiagnosticObservation:

    symbol: str

    trading_date: date

    signal_definition_id: str

    status: SignalEvaluationStatus

    evaluated_conditions: tuple[EvaluatedSignalCondition, ...]

    matched_condition_count: int

    total_condition_count: int

    passed_condition_ids: tuple[str, ...]

    missing_condition_ids: tuple[str, ...]

    not_evaluable_condition_ids: tuple[str, ...]

    source_snapshot: object

    @property
    def is_evaluable(self) -> bool:
        return self.status is not SignalEvaluationStatus.NOT_EVALUABLE


@dataclass(frozen=True)
class MatchCountDistributionRow:

    matched_count: int

    total_count: int

    observation_count: int

    share_of_evaluated_observations: float | None


@dataclass(frozen=True)
class ConditionPassSummary:

    condition_id: str

    display_name: str

    passed_count: int

    failed_count: int

    evaluated_count: int

    pass_rate: float | None


@dataclass(frozen=True)
class MissingConditionSummary:

    condition_id: str

    display_name: str

    observation_count: int

    share_of_4_of_5_observations: float | None


@dataclass(frozen=True)
class ConditionCombinationSummary:

    passed_condition_ids: tuple[str, ...]

    display_names: tuple[str, ...]

    matched_count: int

    observation_count: int

    share_of_evaluated_observations: float | None


@dataclass(frozen=True)
class SymbolConditionDiagnosticsSummary:

    symbol: str

    total_observation_count: int

    evaluated_observation_count: int

    not_evaluable_observation_count: int

    match_count_distribution: tuple[MatchCountDistributionRow, ...]

    condition_pass_summaries: tuple[ConditionPassSummary, ...]

    missing_condition_summaries: tuple[MissingConditionSummary, ...]

    condition_combination_summaries: tuple[ConditionCombinationSummary, ...]

    total_4_of_5_count: int


@dataclass(frozen=True)
class HistoricalConditionDiagnosticsResult:

    config: HistoricalConditionDiagnosticsConfig

    requested_symbols: tuple[str, ...]

    normalized_symbols: tuple[str, ...]

    observations: tuple[ConditionDiagnosticObservation, ...]

    total_observation_count: int

    evaluated_observation_count: int

    not_evaluable_observation_count: int

    match_count_distribution: tuple[MatchCountDistributionRow, ...]

    condition_pass_summaries: tuple[ConditionPassSummary, ...]

    missing_condition_summaries: tuple[MissingConditionSummary, ...]

    condition_combination_summaries: tuple[ConditionCombinationSummary, ...]

    per_symbol_summaries: tuple[SymbolConditionDiagnosticsSummary, ...]

    total_4_of_5_count: int

    generated_at: datetime


class HistoricalConditionDiagnosticsService:

    def __init__(
        self,
        *,
        price_loader=get_historical_prices,
        technical_builder=build_technical_indicator_series,
    ):
        self.price_loader = price_loader
        self.technical_builder = technical_builder

    def run_diagnostics(
        self,
        symbols,
        config: HistoricalConditionDiagnosticsConfig,
        *,
        technical_series_by_symbol: dict[str, TechnicalIndicatorSeries] | None = None,
    ) -> HistoricalConditionDiagnosticsResult:
        requested_symbols = tuple(symbols)
        normalized_symbols = _normalize_unique_symbols(requested_symbols)
        observations = []

        for symbol in normalized_symbols:
            technical_series = self._technical_series_for_symbol(
                symbol,
                config,
                technical_series_by_symbol=technical_series_by_symbol,
            )
            observations.extend(_observe_technical_series(technical_series, config))

        return summarize_condition_diagnostics(
            tuple(observations),
            config=config,
            requested_symbols=requested_symbols,
            normalized_symbols=normalized_symbols,
        )

    def _technical_series_for_symbol(
        self,
        symbol: str,
        config: HistoricalConditionDiagnosticsConfig,
        *,
        technical_series_by_symbol: dict[str, TechnicalIndicatorSeries] | None,
    ) -> TechnicalIndicatorSeries:
        if technical_series_by_symbol is not None and symbol in technical_series_by_symbol:
            return technical_series_by_symbol[symbol]
        price_series = self.price_loader(symbol, force_refresh=config.force_refresh)
        return self.technical_builder(price_series)


def run_historical_condition_diagnostics(
    symbols,
    config: HistoricalConditionDiagnosticsConfig,
) -> HistoricalConditionDiagnosticsResult:
    return HistoricalConditionDiagnosticsService().run_diagnostics(symbols, config)


def summarize_condition_diagnostics(
    observations: tuple[ConditionDiagnosticObservation, ...],
    *,
    config: HistoricalConditionDiagnosticsConfig,
    requested_symbols: tuple[str, ...] = tuple(),
    normalized_symbols: tuple[str, ...] = tuple(),
    generated_at: datetime | None = None,
) -> HistoricalConditionDiagnosticsResult:
    sorted_observations = tuple(sorted(observations, key=lambda item: (item.symbol, item.trading_date)))
    summary = _build_summary(
        sorted_observations,
        config.signal_definition,
        symbol="ALL",
    )
    symbols = normalized_symbols or tuple(sorted({observation.symbol for observation in sorted_observations}))
    per_symbol = tuple(
        _build_summary(
            tuple(observation for observation in sorted_observations if observation.symbol == symbol),
            config.signal_definition,
            symbol=symbol,
        )
        for symbol in symbols
    )
    return HistoricalConditionDiagnosticsResult(
        config=config,
        requested_symbols=requested_symbols,
        normalized_symbols=symbols,
        observations=sorted_observations,
        total_observation_count=summary.total_observation_count,
        evaluated_observation_count=summary.evaluated_observation_count,
        not_evaluable_observation_count=summary.not_evaluable_observation_count,
        match_count_distribution=summary.match_count_distribution,
        condition_pass_summaries=summary.condition_pass_summaries,
        missing_condition_summaries=summary.missing_condition_summaries,
        condition_combination_summaries=summary.condition_combination_summaries,
        per_symbol_summaries=per_symbol,
        total_4_of_5_count=summary.total_4_of_5_count,
        generated_at=generated_at or datetime.now(UTC),
    )


def _observe_technical_series(
    technical_series: TechnicalIndicatorSeries,
    config: HistoricalConditionDiagnosticsConfig,
) -> tuple[ConditionDiagnosticObservation, ...]:
    observations = []
    for snapshot in technical_series.snapshots:
        if snapshot.trading_date < config.start_date or snapshot.trading_date > config.end_date:
            continue
        signal_match = evaluate_signal_conditions(snapshot, config.signal_definition)
        observations.append(build_condition_diagnostic_observation(signal_match))
    return tuple(observations)


def build_condition_diagnostic_observation(
    signal_match: SignalMatch,
) -> ConditionDiagnosticObservation:
    passed_ids = []
    missing_ids = []
    not_evaluable_ids = []
    for condition in signal_match.evaluated_conditions:
        condition_id = condition_diagnostic_id(condition)
        if condition.status is SignalEvaluationStatus.NOT_EVALUABLE:
            not_evaluable_ids.append(condition_id)
        elif condition.matched is True:
            passed_ids.append(condition_id)
        else:
            missing_ids.append(condition_id)

    return ConditionDiagnosticObservation(
        symbol=signal_match.symbol,
        trading_date=signal_match.trading_date,
        signal_definition_id=signal_match.signal_id,
        status=signal_match.status,
        evaluated_conditions=signal_match.evaluated_conditions,
        matched_condition_count=len(passed_ids),
        total_condition_count=len(signal_match.evaluated_conditions),
        passed_condition_ids=tuple(passed_ids),
        missing_condition_ids=tuple(missing_ids),
        not_evaluable_condition_ids=tuple(not_evaluable_ids),
        source_snapshot=signal_match.feature_snapshot,
    )


def condition_diagnostic_id(condition: EvaluatedSignalCondition) -> str:
    if condition.secondary_metric is not None:
        return f"{condition.metric}_vs_{condition.secondary_metric}"
    return condition.metric


def _build_summary(
    observations: tuple[ConditionDiagnosticObservation, ...],
    signal_definition: SignalDefinition,
    *,
    symbol: str,
) -> SymbolConditionDiagnosticsSummary:
    condition_ids = _condition_ids_from_definition(signal_definition)
    evaluated = tuple(observation for observation in observations if observation.is_evaluable)
    not_evaluable_count = len(observations) - len(evaluated)
    distribution = _match_count_distribution(evaluated, total_count=len(condition_ids))
    pass_summaries = _condition_pass_summaries(evaluated, condition_ids)
    missing_summaries, total_4_of_5_count = _missing_condition_summaries(evaluated, condition_ids)
    combinations = _condition_combination_summaries(evaluated, condition_ids)
    return SymbolConditionDiagnosticsSummary(
        symbol=symbol,
        total_observation_count=len(observations),
        evaluated_observation_count=len(evaluated),
        not_evaluable_observation_count=not_evaluable_count,
        match_count_distribution=distribution,
        condition_pass_summaries=pass_summaries,
        missing_condition_summaries=missing_summaries,
        condition_combination_summaries=combinations,
        total_4_of_5_count=total_4_of_5_count,
    )


def _condition_ids_from_definition(signal_definition: SignalDefinition) -> tuple[str, ...]:
    return tuple(
        f"{condition.metric}_vs_{condition.secondary_metric}"
        if condition.secondary_metric is not None else condition.metric
        for condition in signal_definition.conditions
    )


def _match_count_distribution(
    evaluated_observations: tuple[ConditionDiagnosticObservation, ...],
    *,
    total_count: int,
) -> tuple[MatchCountDistributionRow, ...]:
    denominator = len(evaluated_observations)
    rows = []
    for matched_count in range(total_count + 1):
        count = sum(
            observation.matched_condition_count == matched_count
            for observation in evaluated_observations
        )
        rows.append(
            MatchCountDistributionRow(
                matched_count=matched_count,
                total_count=total_count,
                observation_count=count,
                share_of_evaluated_observations=None if denominator == 0 else count / denominator,
            )
        )
    return tuple(rows)


def _condition_pass_summaries(
    evaluated_observations: tuple[ConditionDiagnosticObservation, ...],
    condition_ids: tuple[str, ...],
) -> tuple[ConditionPassSummary, ...]:
    rows = []
    evaluated_count = len(evaluated_observations)
    for condition_id in condition_ids:
        passed_count = sum(
            condition_id in observation.passed_condition_ids
            for observation in evaluated_observations
        )
        failed_count = sum(
            condition_id in observation.missing_condition_ids
            for observation in evaluated_observations
        )
        rows.append(
            ConditionPassSummary(
                condition_id=condition_id,
                display_name=get_diagnostic_condition_label(condition_id),
                passed_count=passed_count,
                failed_count=failed_count,
                evaluated_count=evaluated_count,
                pass_rate=None if evaluated_count == 0 else passed_count / evaluated_count,
            )
        )
    return tuple(rows)


def _missing_condition_summaries(
    evaluated_observations: tuple[ConditionDiagnosticObservation, ...],
    condition_ids: tuple[str, ...],
) -> tuple[tuple[MissingConditionSummary, ...], int]:
    four_of_five = tuple(
        observation for observation in evaluated_observations
        if observation.matched_condition_count == observation.total_condition_count - 1
    )
    total = len(four_of_five)
    if total == 0:
        return tuple(), total
    rows = []
    for condition_id in condition_ids:
        count = sum(
            observation.missing_condition_ids == (condition_id,)
            for observation in four_of_five
        )
        rows.append(
            MissingConditionSummary(
                condition_id=condition_id,
                display_name=get_diagnostic_condition_label(condition_id),
                observation_count=count,
                share_of_4_of_5_observations=None if total == 0 else count / total,
            )
        )
    return tuple(sorted(rows, key=lambda row: (-row.observation_count, condition_ids.index(row.condition_id)))), total


def _condition_combination_summaries(
    evaluated_observations: tuple[ConditionDiagnosticObservation, ...],
    condition_ids: tuple[str, ...],
) -> tuple[ConditionCombinationSummary, ...]:
    denominator = len(evaluated_observations)
    order = {condition_id: index for index, condition_id in enumerate(condition_ids)}
    counts: dict[tuple[str, ...], int] = {}
    for observation in evaluated_observations:
        canonical = tuple(
            sorted(observation.passed_condition_ids, key=lambda condition_id: order[condition_id])
        )
        counts[canonical] = counts.get(canonical, 0) + 1
    rows = [
        ConditionCombinationSummary(
            passed_condition_ids=combination,
            display_names=tuple(get_diagnostic_condition_label(condition_id) for condition_id in combination),
            matched_count=len(combination),
            observation_count=count,
            share_of_evaluated_observations=None if denominator == 0 else count / denominator,
        )
        for combination, count in counts.items()
    ]
    return tuple(
        sorted(
            rows,
            key=lambda row: (-row.observation_count, -row.matched_count, row.passed_condition_ids),
        )
    )


def _normalize_unique_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    normalized = []
    seen = set()
    for raw_symbol in symbols:
        symbol = normalize_stock_symbol(raw_symbol)
        if symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return tuple(normalized)
