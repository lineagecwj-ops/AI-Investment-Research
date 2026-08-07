from dataclasses import dataclass
from datetime import date
from datetime import datetime
import hashlib
from statistics import mean
from statistics import median

from database import utc_now
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OverlappingSignalPolicy
from models import SignalDefinition
from models import SignalEvent
from models import TechnicalIndicatorSeries
from signal_outcome_service import apply_signal_cooldown
from signal_outcome_service import evaluate_historical_outcome
from signal_outcome_service import find_signal_events


class BacktestError(Exception):
    """Base error for historical backtest failures."""


class BacktestConfigurationError(BacktestError):
    """Raised when a backtest config is ambiguous or invalid."""


class BacktestDataError(BacktestError):
    """Raised when price and technical inputs cannot be aligned."""


@dataclass(frozen=True)
class BacktestConfig:

    signal_definition: SignalDefinition

    outcome_definition: OutcomeDefinition

    overlap_policy: OverlappingSignalPolicy = OverlappingSignalPolicy.ALLOW_ALL

    cooldown_bars: int | None = None

    start_date: date | None = None

    end_date: date | None = None

    def __post_init__(self):
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise BacktestConfigurationError("Backtest start_date cannot be after end_date.")
        if self.overlap_policy is OverlappingSignalPolicy.COOLDOWN:
            if self.cooldown_bars is None or self.cooldown_bars <= 0:
                raise BacktestConfigurationError("COOLDOWN policy requires a positive cooldown_bars value.")
        elif self.overlap_policy is OverlappingSignalPolicy.ALLOW_ALL:
            if self.cooldown_bars is not None:
                raise BacktestConfigurationError("ALLOW_ALL policy does not accept cooldown_bars.")
        else:
            raise BacktestConfigurationError(f"Unsupported overlap policy: {self.overlap_policy}")


@dataclass(frozen=True)
class HistoricalBacktestCase:

    symbol: str

    signal_event: SignalEvent

    outcome: HistoricalOutcomeResult

    case_id: str

    @property
    def status(self) -> OutcomeEvaluationStatus:
        return self.outcome.status


@dataclass(frozen=True)
class HistoricalBacktestReport:

    symbol: str

    signal_definition_id: str

    outcome_definition_id: str

    overlap_policy: OverlappingSignalPolicy

    cooldown_bars: int | None

    start_date: date | None

    end_date: date | None

    backtest_id: str

    raw_signal_count: int

    filtered_signal_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    average_max_close_return: float | None

    median_max_close_return: float | None

    average_max_adverse_return: float | None

    median_max_adverse_return: float | None

    average_end_return: float | None

    median_end_return: float | None

    average_hit_bar_index: float | None

    median_hit_bar_index: float | None

    max_return_sample_count: int

    max_adverse_sample_count: int

    end_return_sample_count: int

    hit_bar_sample_count: int

    raw_events: tuple[SignalEvent, ...]

    evaluated_events: tuple[SignalEvent, ...]

    cases: tuple[HistoricalBacktestCase, ...]

    generated_at: datetime

    @property
    def hit_cases(self) -> tuple[HistoricalBacktestCase, ...]:
        return _cases_with_status(self.cases, OutcomeEvaluationStatus.HIT)

    @property
    def miss_cases(self) -> tuple[HistoricalBacktestCase, ...]:
        return _cases_with_status(self.cases, OutcomeEvaluationStatus.MISS)

    @property
    def incomplete_cases(self) -> tuple[HistoricalBacktestCase, ...]:
        return _cases_with_status(self.cases, OutcomeEvaluationStatus.INCOMPLETE)

    @property
    def not_evaluable_cases(self) -> tuple[HistoricalBacktestCase, ...]:
        return _cases_with_status(self.cases, OutcomeEvaluationStatus.NOT_EVALUABLE)


def run_historical_backtest(
    price_series: HistoricalPriceSeries,
    technical_series: TechnicalIndicatorSeries,
    config: BacktestConfig,
) -> HistoricalBacktestReport:
    _validate_series_consistency(price_series, technical_series)

    raw_events = find_signal_events(
        technical_series,
        config.signal_definition,
        price_series=price_series,
    )
    date_filtered_events = tuple(
        event for event in raw_events
        if _event_in_date_range(event, config.start_date, config.end_date)
    )

    if config.overlap_policy is OverlappingSignalPolicy.COOLDOWN:
        evaluated_events = apply_signal_cooldown(
            date_filtered_events,
            price_series,
            cooldown_bars=config.cooldown_bars,
        )
    else:
        evaluated_events = date_filtered_events

    cases = tuple(
        _build_backtest_case(
            event,
            evaluate_historical_outcome(event, price_series, config.outcome_definition),
        )
        for event in evaluated_events
    )
    cases = tuple(sorted(cases, key=lambda case: (case.signal_event.signal_date, case.case_id)))

    return aggregate_backtest_cases(
        cases,
        symbol=price_series.symbol,
        config=config,
        raw_events=raw_events,
        evaluated_events=evaluated_events,
        generated_at=utc_now(),
    )


def aggregate_backtest_cases(
    cases: tuple[HistoricalBacktestCase, ...],
    *,
    symbol: str,
    config: BacktestConfig,
    raw_events: tuple[SignalEvent, ...] = tuple(),
    evaluated_events: tuple[SignalEvent, ...] = tuple(),
    generated_at: datetime | None = None,
) -> HistoricalBacktestReport:
    sorted_cases = tuple(sorted(cases, key=lambda case: (case.signal_event.signal_date, case.case_id)))
    hit_count = _count_status(sorted_cases, OutcomeEvaluationStatus.HIT)
    miss_count = _count_status(sorted_cases, OutcomeEvaluationStatus.MISS)
    incomplete_count = _count_status(sorted_cases, OutcomeEvaluationStatus.INCOMPLETE)
    not_evaluable_count = _count_status(sorted_cases, OutcomeEvaluationStatus.NOT_EVALUABLE)
    resolved_count = hit_count + miss_count

    max_returns = _non_none_values(case.outcome.max_close_return for case in sorted_cases)
    max_adverse_returns = _non_none_values(case.outcome.max_adverse_return for case in sorted_cases)
    end_returns = _non_none_values(case.outcome.end_of_window_return for case in sorted_cases)
    hit_bar_indexes = _non_none_values(
        _target_hit_bar_index(case.outcome)
        for case in sorted_cases
        if case.status is OutcomeEvaluationStatus.HIT
    )

    return HistoricalBacktestReport(
        symbol=symbol,
        signal_definition_id=config.signal_definition.id,
        outcome_definition_id=config.outcome_definition.id,
        overlap_policy=config.overlap_policy,
        cooldown_bars=config.cooldown_bars,
        start_date=config.start_date,
        end_date=config.end_date,
        backtest_id=build_backtest_id(symbol, config),
        raw_signal_count=len(raw_events),
        filtered_signal_count=len(evaluated_events) if evaluated_events else len(sorted_cases),
        hit_count=hit_count,
        miss_count=miss_count,
        incomplete_count=incomplete_count,
        not_evaluable_count=not_evaluable_count,
        resolved_count=resolved_count,
        historical_hit_rate=None if resolved_count == 0 else hit_count / resolved_count,
        average_max_close_return=_mean_or_none(max_returns),
        median_max_close_return=_median_or_none(max_returns),
        average_max_adverse_return=_mean_or_none(max_adverse_returns),
        median_max_adverse_return=_median_or_none(max_adverse_returns),
        average_end_return=_mean_or_none(end_returns),
        median_end_return=_median_or_none(end_returns),
        average_hit_bar_index=_mean_or_none(hit_bar_indexes),
        median_hit_bar_index=_median_or_none(hit_bar_indexes),
        max_return_sample_count=len(max_returns),
        max_adverse_sample_count=len(max_adverse_returns),
        end_return_sample_count=len(end_returns),
        hit_bar_sample_count=len(hit_bar_indexes),
        raw_events=tuple(sorted(raw_events, key=lambda event: (event.signal_date, event.symbol, event.signal_id))),
        evaluated_events=tuple(sorted(evaluated_events, key=lambda event: (event.signal_date, event.symbol, event.signal_id))),
        cases=sorted_cases,
        generated_at=generated_at or utc_now(),
    )


def build_backtest_id(symbol: str, config: BacktestConfig) -> str:
    identity = "|".join(
        (
            symbol,
            config.signal_definition.id,
            config.outcome_definition.id,
            config.overlap_policy.value,
            "" if config.cooldown_bars is None else str(config.cooldown_bars),
            "" if config.start_date is None else config.start_date.isoformat(),
            "" if config.end_date is None else config.end_date.isoformat(),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"backtest_{digest}"


def build_case_id(symbol: str, signal_event: SignalEvent, outcome: HistoricalOutcomeResult) -> str:
    return "|".join(
        (
            symbol,
            signal_event.signal_id,
            signal_event.signal_date.isoformat(),
            outcome.outcome_definition_id,
        )
    )


def get_backtest_case_price_window(
    price_series: HistoricalPriceSeries,
    signal_date: date,
    pre_bars: int,
    post_bars: int,
) -> tuple[HistoricalPriceBar, ...]:
    if pre_bars < 0 or post_bars < 0:
        raise BacktestConfigurationError("pre_bars and post_bars cannot be negative.")

    before = [bar for bar in price_series.bars if bar.trading_date < signal_date]
    on_or_after = [bar for bar in price_series.bars if bar.trading_date >= signal_date]
    selected_before = [] if pre_bars == 0 else before[-pre_bars:]
    return tuple(selected_before + on_or_after[:post_bars + 1])


def _build_backtest_case(
    signal_event: SignalEvent,
    outcome: HistoricalOutcomeResult,
) -> HistoricalBacktestCase:
    if signal_event.symbol != outcome.symbol:
        raise BacktestDataError("Signal event symbol does not match outcome symbol.")
    if signal_event.signal_id != outcome.signal_id or signal_event.signal_date != outcome.signal_date:
        raise BacktestDataError("Signal event identity does not match outcome identity.")
    return HistoricalBacktestCase(
        symbol=signal_event.symbol,
        signal_event=signal_event,
        outcome=outcome,
        case_id=build_case_id(signal_event.symbol, signal_event, outcome),
    )


def _validate_series_consistency(
    price_series: HistoricalPriceSeries,
    technical_series: TechnicalIndicatorSeries,
) -> None:
    if price_series.symbol != technical_series.symbol:
        raise BacktestDataError("Price series symbol must match technical series symbol.")

    price_dates = {bar.trading_date for bar in price_series.bars}
    missing_snapshot_dates = [
        snapshot.trading_date
        for snapshot in technical_series.snapshots
        if snapshot.trading_date not in price_dates
    ]
    if missing_snapshot_dates:
        raise BacktestDataError("Technical snapshot dates must exist in the price series.")


def _event_in_date_range(
    event: SignalEvent,
    start_date: date | None,
    end_date: date | None,
) -> bool:
    if start_date is not None and event.signal_date < start_date:
        return False
    if end_date is not None and event.signal_date > end_date:
        return False
    return True


def _count_status(cases, status: OutcomeEvaluationStatus) -> int:
    return sum(case.status is status for case in cases)


def _cases_with_status(
    cases: tuple[HistoricalBacktestCase, ...],
    status: OutcomeEvaluationStatus,
) -> tuple[HistoricalBacktestCase, ...]:
    return tuple(case for case in cases if case.status is status)


def _target_hit_bar_index(outcome: HistoricalOutcomeResult) -> int | None:
    if outcome.intraday_target_hit_bar_index is not None:
        return outcome.intraday_target_hit_bar_index
    return outcome.close_target_hit_bar_index


def _non_none_values(values) -> tuple[float, ...]:
    return tuple(value for value in values if value is not None)


def _mean_or_none(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return mean(values)


def _median_or_none(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return median(values)
