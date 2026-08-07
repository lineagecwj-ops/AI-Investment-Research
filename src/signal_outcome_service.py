from datetime import date
import math

from historical_price_service import get_analysis_close
from models import EvaluatedSignalCondition
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OutcomeType
from models import SignalDefinition
from models import SignalEvaluationAudit
from models import SignalEvaluationStatus
from models import SignalMatch
from models import SignalConditionOperator
from models import SignalEvent
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from models import TechnicalSignalCondition


SUPPORTED_HORIZON_BARS = (5, 10, 20, 40)
DEFAULT_SIGNAL_REFERENCE_HIGH_METRIC = "prior_high_60d"
DEFAULT_SIGNAL_REFERENCE_LOW_METRIC = "prior_low_60d"


TECHNICAL_EXAMPLE_SIGNAL_V1 = SignalDefinition(
    id="technical_example_v1",
    name="Technical Example V1",
    conditions=(
        TechnicalSignalCondition(
            metric="analysis_close",
            operator=SignalConditionOperator.GREATER_THAN,
            secondary_metric="sma_20",
        ),
        TechnicalSignalCondition(
            metric="sma_20",
            operator=SignalConditionOperator.GREATER_THAN,
            secondary_metric="sma_60",
        ),
        TechnicalSignalCondition(
            metric="volume_ratio_20",
            operator=SignalConditionOperator.GREATER_THAN_OR_EQUAL,
            value=1.2,
        ),
        TechnicalSignalCondition(
            metric="rsi_14",
            operator=SignalConditionOperator.BETWEEN,
            value=(50.0, 70.0),
        ),
        TechnicalSignalCondition(
            metric="distance_to_prior_60d_high",
            operator=SignalConditionOperator.GREATER_THAN_OR_EQUAL,
            value=-0.05,
        ),
    ),
    minimum_required_features=(
        "analysis_close",
        "sma_20",
        "sma_60",
        "volume_ratio_20",
        "rsi_14",
        "distance_to_prior_60d_high",
    ),
    description="Neutral example technical research condition for Batch C tests.",
)

RAW_HIGH_BREAKOUT_60D_WITHIN_20D_V1 = OutcomeDefinition(
    id="raw_high_breakout_60d_within_20d_v1",
    outcome_type=OutcomeType.RAW_HIGH_BREAKOUT,
    horizon_bars=20,
    reference_metric="prior_high_60d",
    description="Future raw high strictly exceeds the frozen prior 60 trading-bar raw high.",
)

CLOSE_RETURN_5PCT_WITHIN_20D_V1 = OutcomeDefinition(
    id="close_return_5pct_within_20d_v1",
    outcome_type=OutcomeType.CLOSE_RETURN_TARGET,
    horizon_bars=20,
    target_return=0.05,
    description="Future analysis close reaches at least +5% from signal analysis close.",
)


class SignalOutcomeError(Exception):
    """Raised when signal or historical outcome inputs are structurally invalid."""


def evaluate_signal_conditions(
    snapshot: TechnicalIndicatorSnapshot,
    signal_definition: SignalDefinition,
) -> SignalMatch:
    required_status = _evaluate_required_features(snapshot, signal_definition)
    if required_status is SignalEvaluationStatus.NOT_EVALUABLE:
        evaluated_conditions = tuple(
            _evaluate_condition(snapshot, condition)
            for condition in signal_definition.conditions
        )
        return _signal_match(snapshot, signal_definition, evaluated_conditions)

    evaluated_conditions = tuple(
        _evaluate_condition(snapshot, condition)
        for condition in signal_definition.conditions
    )
    return _signal_match(snapshot, signal_definition, evaluated_conditions)


def find_signal_events(
    technical_series: TechnicalIndicatorSeries,
    signal_definition: SignalDefinition,
    *,
    price_series: HistoricalPriceSeries | None = None,
    reference_high_metric: str = DEFAULT_SIGNAL_REFERENCE_HIGH_METRIC,
    reference_low_metric: str = DEFAULT_SIGNAL_REFERENCE_LOW_METRIC,
) -> tuple[SignalEvent, ...]:
    raw_close_by_date = {}
    if price_series is not None:
        raw_close_by_date = {
            bar.trading_date: bar.close
            for bar in price_series.bars
        }

    seen_keys: set[tuple[str, str, date]] = set()
    events = []
    for snapshot in technical_series.snapshots:
        match = evaluate_signal_conditions(snapshot, signal_definition)
        if match.status is not SignalEvaluationStatus.MATCH:
            continue
        key = (match.symbol, match.signal_id, match.trading_date)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        events.append(
            build_signal_event(
                match,
                signal_raw_close=raw_close_by_date.get(match.trading_date),
                reference_high_metric=reference_high_metric,
                reference_low_metric=reference_low_metric,
            )
        )
    return tuple(events)


def build_signal_event(
    match: SignalMatch,
    *,
    signal_raw_close: float | None = None,
    reference_high_metric: str = DEFAULT_SIGNAL_REFERENCE_HIGH_METRIC,
    reference_low_metric: str = DEFAULT_SIGNAL_REFERENCE_LOW_METRIC,
) -> SignalEvent:
    if match.status is not SignalEvaluationStatus.MATCH:
        raise SignalOutcomeError("Only MATCH signal evaluations can become SignalEvent.")

    return SignalEvent(
        symbol=match.symbol,
        signal_id=match.signal_id,
        signal_date=match.trading_date,
        signal_analysis_close=match.feature_snapshot.analysis_close,
        signal_raw_close=signal_raw_close,
        reference_high=_metric_value(match.feature_snapshot, reference_high_metric),
        reference_low=_metric_value(match.feature_snapshot, reference_low_metric),
        evaluation_status=match.status,
        feature_snapshot=match.feature_snapshot,
        evaluated_conditions=match.evaluated_conditions,
    )


def audit_signal_evaluation(
    technical_series: TechnicalIndicatorSeries,
    signal_definition: SignalDefinition,
) -> SignalEvaluationAudit:
    matches = [
        evaluate_signal_conditions(snapshot, signal_definition)
        for snapshot in technical_series.snapshots
    ]
    return SignalEvaluationAudit(
        signal_id=signal_definition.id,
        evaluated_snapshots=len(matches),
        matched=sum(match.status is SignalEvaluationStatus.MATCH for match in matches),
        not_matched=sum(match.status is SignalEvaluationStatus.NO_MATCH for match in matches),
        not_evaluable=sum(
            match.status is SignalEvaluationStatus.NOT_EVALUABLE
            for match in matches
        ),
    )


def get_future_bars_after(
    series: HistoricalPriceSeries,
    signal_date: date,
    count: int,
) -> tuple[HistoricalPriceBar, ...]:
    if count <= 0:
        return tuple()
    return tuple(
        bar for bar in series.bars
        if bar.trading_date > signal_date
    )[:count]


def evaluate_historical_outcome(
    signal_event: SignalEvent,
    price_series: HistoricalPriceSeries,
    outcome_definition: OutcomeDefinition,
) -> HistoricalOutcomeResult:
    _validate_outcome_definition(outcome_definition)
    future_bars = get_future_bars_after(
        price_series,
        signal_event.signal_date,
        outcome_definition.horizon_bars,
    )

    if outcome_definition.outcome_type is OutcomeType.RAW_HIGH_BREAKOUT:
        return _evaluate_raw_high_breakout(signal_event, outcome_definition, future_bars)
    if outcome_definition.outcome_type is OutcomeType.CLOSE_RETURN_TARGET:
        return _evaluate_close_return_target(signal_event, outcome_definition, future_bars)
    raise SignalOutcomeError(f"Unsupported outcome type: {outcome_definition.outcome_type}")


def evaluate_signal_events(
    events: tuple[SignalEvent, ...],
    price_series: HistoricalPriceSeries,
    outcome_definition: OutcomeDefinition,
) -> tuple[HistoricalOutcomeResult, ...]:
    return tuple(
        evaluate_historical_outcome(event, price_series, outcome_definition)
        for event in events
    )


def is_outcome_complete(result: HistoricalOutcomeResult) -> bool:
    return result.status in {
        OutcomeEvaluationStatus.HIT,
        OutcomeEvaluationStatus.MISS,
    }


def apply_signal_cooldown(
    events: tuple[SignalEvent, ...],
    trading_calendar,
    *,
    cooldown_bars: int,
) -> tuple[SignalEvent, ...]:
    if cooldown_bars <= 0:
        return tuple(events)

    trading_dates = _trading_dates_from_calendar(trading_calendar)
    index_by_date = {
        trading_date: index
        for index, trading_date in enumerate(trading_dates)
    }
    grouped_events = sorted(
        events,
        key=lambda event: (
            event.symbol,
            event.signal_id,
            index_by_date.get(event.signal_date, math.inf),
            event.signal_date,
        ),
    )

    kept = []
    last_kept_index_by_key: dict[tuple[str, str], int] = {}
    for event in grouped_events:
        if event.signal_date not in index_by_date:
            raise SignalOutcomeError("Signal event date is absent from the trading calendar.")
        key = (event.symbol, event.signal_id)
        event_index = index_by_date[event.signal_date]
        last_kept_index = last_kept_index_by_key.get(key)
        if last_kept_index is not None and event_index - last_kept_index <= cooldown_bars:
            continue
        kept.append(event)
        last_kept_index_by_key[key] = event_index

    return tuple(sorted(kept, key=lambda event: (event.symbol, event.signal_id, event.signal_date)))


def _signal_match(
    snapshot: TechnicalIndicatorSnapshot,
    signal_definition: SignalDefinition,
    evaluated_conditions: tuple[EvaluatedSignalCondition, ...],
) -> SignalMatch:
    if any(
        condition.status is SignalEvaluationStatus.NOT_EVALUABLE
        for condition in evaluated_conditions
    ):
        status = SignalEvaluationStatus.NOT_EVALUABLE
    elif all(condition.matched for condition in evaluated_conditions):
        status = SignalEvaluationStatus.MATCH
    else:
        status = SignalEvaluationStatus.NO_MATCH

    return SignalMatch(
        symbol=snapshot.symbol,
        trading_date=snapshot.trading_date,
        signal_id=signal_definition.id,
        status=status,
        matched=status is SignalEvaluationStatus.MATCH,
        evaluated_conditions=evaluated_conditions,
        feature_snapshot=snapshot,
    )


def _evaluate_required_features(
    snapshot: TechnicalIndicatorSnapshot,
    signal_definition: SignalDefinition,
) -> SignalEvaluationStatus:
    for metric in signal_definition.minimum_required_features:
        if not _has_metric(snapshot, metric):
            return SignalEvaluationStatus.NOT_EVALUABLE
        if not _is_usable_value(_metric_value(snapshot, metric)):
            return SignalEvaluationStatus.NOT_EVALUABLE
    return SignalEvaluationStatus.MATCH


def _evaluate_condition(
    snapshot: TechnicalIndicatorSnapshot,
    condition: TechnicalSignalCondition,
) -> EvaluatedSignalCondition:
    actual_value = _metric_value(snapshot, condition.metric)
    secondary_actual_value = None
    expected_value = condition.value

    if condition.secondary_metric is not None:
        secondary_actual_value = _metric_value(snapshot, condition.secondary_metric)
        expected_value = secondary_actual_value

    if not _has_metric(snapshot, condition.metric):
        return _evaluated_condition(
            condition,
            actual_value,
            expected_value,
            secondary_actual_value,
            SignalEvaluationStatus.NOT_EVALUABLE,
            None,
        )
    if condition.secondary_metric is not None and not _has_metric(snapshot, condition.secondary_metric):
        return _evaluated_condition(
            condition,
            actual_value,
            expected_value,
            secondary_actual_value,
            SignalEvaluationStatus.NOT_EVALUABLE,
            None,
        )
    if not _is_usable_value(actual_value):
        return _evaluated_condition(
            condition,
            actual_value,
            expected_value,
            secondary_actual_value,
            SignalEvaluationStatus.NOT_EVALUABLE,
            None,
        )
    if condition.secondary_metric is not None and not _is_usable_value(secondary_actual_value):
        return _evaluated_condition(
            condition,
            actual_value,
            expected_value,
            secondary_actual_value,
            SignalEvaluationStatus.NOT_EVALUABLE,
            None,
        )

    matched = _compare_values(condition.operator, actual_value, expected_value)
    return _evaluated_condition(
        condition,
        actual_value,
        expected_value,
        secondary_actual_value,
        SignalEvaluationStatus.MATCH if matched else SignalEvaluationStatus.NO_MATCH,
        matched,
    )


def _evaluated_condition(
    condition: TechnicalSignalCondition,
    actual_value,
    expected_value,
    secondary_actual_value,
    status: SignalEvaluationStatus,
    matched: bool | None,
) -> EvaluatedSignalCondition:
    return EvaluatedSignalCondition(
        metric=condition.metric,
        actual_value=actual_value,
        operator=condition.operator,
        expected_value=expected_value,
        secondary_metric=condition.secondary_metric,
        secondary_actual_value=secondary_actual_value,
        status=status,
        matched=matched,
    )


def _compare_values(
    operator: SignalConditionOperator,
    actual_value: float | bool,
    expected_value: float | bool | tuple[float, float] | None,
) -> bool:
    if operator is SignalConditionOperator.EQUAL:
        if isinstance(actual_value, bool):
            if not isinstance(expected_value, bool):
                raise SignalOutcomeError("Boolean equality requires a boolean expected value.")
            return actual_value == expected_value
        if isinstance(expected_value, bool) or not _is_number(expected_value):
            raise SignalOutcomeError("Numeric equality requires a numeric expected value.")
        return actual_value == expected_value

    if operator is SignalConditionOperator.BETWEEN:
        if isinstance(actual_value, bool):
            raise SignalOutcomeError("Between comparison does not support boolean values.")
        if (
            not isinstance(expected_value, tuple)
            or len(expected_value) != 2
            or any(not _is_number(value) for value in expected_value)
        ):
            raise SignalOutcomeError("Between comparison requires a numeric (lower, upper) tuple.")
        lower, upper = expected_value
        return lower <= actual_value <= upper

    if isinstance(actual_value, bool) or isinstance(expected_value, bool):
        raise SignalOutcomeError("Ordered comparisons do not support boolean values.")
    if not _is_number(actual_value) or not _is_number(expected_value):
        raise SignalOutcomeError("Ordered comparisons require numeric values.")

    if operator is SignalConditionOperator.GREATER_THAN:
        return actual_value > expected_value
    if operator is SignalConditionOperator.GREATER_THAN_OR_EQUAL:
        return actual_value >= expected_value
    if operator is SignalConditionOperator.LESS_THAN:
        return actual_value < expected_value
    if operator is SignalConditionOperator.LESS_THAN_OR_EQUAL:
        return actual_value <= expected_value
    raise SignalOutcomeError(f"Unsupported signal operator: {operator}")


def _evaluate_raw_high_breakout(
    signal_event: SignalEvent,
    outcome_definition: OutcomeDefinition,
    future_bars: tuple[HistoricalPriceBar, ...],
) -> HistoricalOutcomeResult:
    reference_high = signal_event.reference_high
    if not _is_number(reference_high):
        return _empty_outcome_result(
            signal_event,
            outcome_definition,
            OutcomeEvaluationStatus.NOT_EVALUABLE,
            future_bars,
            reference_high,
        )

    hit_date = None
    hit_bar_index = None
    for index, bar in enumerate(future_bars, start=1):
        if bar.high > reference_high:
            hit_date = bar.trading_date
            hit_bar_index = index
            break

    return _outcome_result(
        signal_event,
        outcome_definition,
        future_bars,
        reference_high=reference_high,
        intraday_target_hit=hit_date is not None,
        intraday_target_hit_date=hit_date,
        intraday_target_hit_bar_index=hit_bar_index,
        close_target_hit=False,
        close_target_hit_date=None,
        close_target_hit_bar_index=None,
    )


def _evaluate_close_return_target(
    signal_event: SignalEvent,
    outcome_definition: OutcomeDefinition,
    future_bars: tuple[HistoricalPriceBar, ...],
) -> HistoricalOutcomeResult:
    if not _is_number(signal_event.signal_analysis_close) or signal_event.signal_analysis_close <= 0:
        return _empty_outcome_result(
            signal_event,
            outcome_definition,
            OutcomeEvaluationStatus.NOT_EVALUABLE,
            future_bars,
            signal_event.reference_high,
        )
    target_return = outcome_definition.target_return
    if not _is_number(target_return):
        raise SignalOutcomeError("CLOSE_RETURN_TARGET requires target_return.")

    hit_date = None
    hit_bar_index = None
    for index, bar in enumerate(future_bars, start=1):
        close_return = _close_return(bar, signal_event.signal_analysis_close)
        if close_return >= target_return:
            hit_date = bar.trading_date
            hit_bar_index = index
            break

    return _outcome_result(
        signal_event,
        outcome_definition,
        future_bars,
        reference_high=signal_event.reference_high,
        intraday_target_hit=False,
        intraday_target_hit_date=None,
        intraday_target_hit_bar_index=None,
        close_target_hit=hit_date is not None,
        close_target_hit_date=hit_date,
        close_target_hit_bar_index=hit_bar_index,
    )


def _outcome_result(
    signal_event: SignalEvent,
    outcome_definition: OutcomeDefinition,
    future_bars: tuple[HistoricalPriceBar, ...],
    *,
    reference_high: float | None,
    intraday_target_hit: bool,
    intraday_target_hit_date: date | None,
    intraday_target_hit_bar_index: int | None,
    close_target_hit: bool,
    close_target_hit_date: date | None,
    close_target_hit_bar_index: int | None,
) -> HistoricalOutcomeResult:
    status = _outcome_status(
        target_hit=intraday_target_hit or close_target_hit,
        available_future_bars=len(future_bars),
        horizon_bars=outcome_definition.horizon_bars,
    )
    complete_window = len(future_bars) >= outcome_definition.horizon_bars
    max_close_return = None
    max_close_return_date = None
    max_adverse_return = None
    max_adverse_return_date = None
    end_of_window_return = None

    if complete_window:
        window_bars = future_bars[:outcome_definition.horizon_bars]
        close_returns = [
            (_close_return(bar, signal_event.signal_analysis_close), bar.trading_date)
            for bar in window_bars
        ]
        max_close_return, max_close_return_date = max(
            close_returns,
            key=lambda item: item[0],
        )
        max_adverse_return, max_adverse_return_date = min(
            close_returns,
            key=lambda item: item[0],
        )
        end_of_window_return = close_returns[-1][0]

    return HistoricalOutcomeResult(
        symbol=signal_event.symbol,
        signal_id=signal_event.signal_id,
        signal_date=signal_event.signal_date,
        outcome_definition_id=outcome_definition.id,
        status=status,
        horizon_bars=outcome_definition.horizon_bars,
        available_future_bars=len(future_bars),
        reference_high=reference_high,
        intraday_target_hit=intraday_target_hit,
        intraday_target_hit_date=intraday_target_hit_date,
        intraday_target_hit_bar_index=intraday_target_hit_bar_index,
        close_target_hit=close_target_hit,
        close_target_hit_date=close_target_hit_date,
        close_target_hit_bar_index=close_target_hit_bar_index,
        max_close_return=max_close_return,
        max_close_return_date=max_close_return_date,
        max_adverse_return=max_adverse_return,
        max_adverse_return_date=max_adverse_return_date,
        end_of_window_return=end_of_window_return,
    )


def _empty_outcome_result(
    signal_event: SignalEvent,
    outcome_definition: OutcomeDefinition,
    status: OutcomeEvaluationStatus,
    future_bars: tuple[HistoricalPriceBar, ...],
    reference_high: float | None,
) -> HistoricalOutcomeResult:
    return HistoricalOutcomeResult(
        symbol=signal_event.symbol,
        signal_id=signal_event.signal_id,
        signal_date=signal_event.signal_date,
        outcome_definition_id=outcome_definition.id,
        status=status,
        horizon_bars=outcome_definition.horizon_bars,
        available_future_bars=len(future_bars),
        reference_high=reference_high,
        intraday_target_hit=False,
        intraday_target_hit_date=None,
        intraday_target_hit_bar_index=None,
        close_target_hit=False,
        close_target_hit_date=None,
        close_target_hit_bar_index=None,
        max_close_return=None,
        max_close_return_date=None,
        max_adverse_return=None,
        max_adverse_return_date=None,
        end_of_window_return=None,
    )


def _outcome_status(
    *,
    target_hit: bool,
    available_future_bars: int,
    horizon_bars: int,
) -> OutcomeEvaluationStatus:
    if target_hit:
        return OutcomeEvaluationStatus.HIT
    if available_future_bars >= horizon_bars:
        return OutcomeEvaluationStatus.MISS
    return OutcomeEvaluationStatus.INCOMPLETE


def _validate_outcome_definition(outcome_definition: OutcomeDefinition) -> None:
    if outcome_definition.horizon_bars not in SUPPORTED_HORIZON_BARS:
        raise SignalOutcomeError("Outcome horizon must be one of 5, 10, 20, or 40 trading bars.")
    if outcome_definition.outcome_type is OutcomeType.RAW_HIGH_BREAKOUT and not outcome_definition.reference_metric:
        raise SignalOutcomeError("RAW_HIGH_BREAKOUT requires a reference metric.")
    if outcome_definition.outcome_type is OutcomeType.CLOSE_RETURN_TARGET and outcome_definition.target_return is None:
        raise SignalOutcomeError("CLOSE_RETURN_TARGET requires target_return.")


def _close_return(bar: HistoricalPriceBar, signal_analysis_close: float) -> float:
    return (get_analysis_close(bar) / signal_analysis_close) - 1.0


def _trading_dates_from_calendar(trading_calendar) -> tuple[date, ...]:
    if isinstance(trading_calendar, HistoricalPriceSeries):
        return tuple(bar.trading_date for bar in trading_calendar.bars)
    if isinstance(trading_calendar, TechnicalIndicatorSeries):
        return tuple(snapshot.trading_date for snapshot in trading_calendar.snapshots)
    return tuple(trading_calendar)


def _has_metric(snapshot: TechnicalIndicatorSnapshot, metric: str) -> bool:
    return hasattr(snapshot, metric)


def _metric_value(snapshot: TechnicalIndicatorSnapshot, metric: str):
    return getattr(snapshot, metric, None)


def _is_usable_value(value) -> bool:
    if isinstance(value, bool):
        return True
    return _is_number(value)


def _is_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))
