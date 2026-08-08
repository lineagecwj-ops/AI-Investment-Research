from dataclasses import dataclass
from datetime import date

from backtest_service import HistoricalBacktestCase
from backtest_service import HistoricalBacktestReport
from historical_price_service import get_analysis_close
from models import EvaluatedSignalCondition
from models import HistoricalOutcomeResult
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from models import OutcomeEvaluationStatus
from models import SignalEvent
from models import TechnicalIndicatorSnapshot


class HistoricalCaseDataError(Exception):
    """Raised when historical case inputs cannot be represented safely."""


@dataclass(frozen=True)
class HistoricalCaseWindowConfig:

    pre_signal_bars: int = 60

    post_signal_bars: int = 20

    def __post_init__(self):
        if self.pre_signal_bars < 0:
            raise HistoricalCaseDataError("pre_signal_bars cannot be negative.")
        if self.post_signal_bars < 0:
            raise HistoricalCaseDataError("post_signal_bars cannot be negative.")


@dataclass(frozen=True)
class HistoricalCasePricePoint:

    trading_date: date

    relative_bar_index: int

    raw_open: float | None

    raw_high: float

    raw_low: float

    raw_close: float

    adjusted_close: float | None

    analysis_close: float

    volume: int | None

    is_signal_date: bool

    is_target_hit_date: bool

    before_or_after_signal: str


@dataclass(frozen=True)
class HistoricalCaseConditionDetail:

    metric: str

    actual_value: float | bool | None

    operator: str

    expected_value: float | bool | tuple[float, float] | None

    secondary_metric: str | None

    secondary_actual_value: float | bool | None

    evaluation_status: str

    matched: bool | None


@dataclass(frozen=True)
class HistoricalCaseView:

    case_id: str

    symbol: str

    currency: str | None

    signal_id: str

    outcome_definition_id: str

    signal_date: date

    signal_analysis_close: float

    signal_raw_close: float | None

    reference_high: float | None

    reference_low: float | None

    outcome_status: OutcomeEvaluationStatus

    target_hit_date: date | None

    target_hit_bar_index: int | None

    max_close_return: float | None

    max_close_return_date: date | None

    max_adverse_return: float | None

    max_adverse_return_date: date | None

    end_of_window_return: float | None

    horizon_bars: int

    available_future_bars: int

    pre_signal_bars: int

    post_signal_bars: int

    price_points: tuple[HistoricalCasePricePoint, ...]

    condition_details: tuple[HistoricalCaseConditionDetail, ...]

    technical_snapshot_summary: tuple[tuple[str, float | bool | None], ...]

    is_window_complete_before: bool

    is_window_complete_after: bool


def build_case_price_window(
    price_series: HistoricalPriceSeries,
    signal_date: date,
    pre_bars: int,
    post_bars: int,
) -> tuple[HistoricalPriceBar, ...]:
    if pre_bars < 0 or post_bars < 0:
        raise HistoricalCaseDataError("pre_bars and post_bars cannot be negative.")

    bars = tuple(price_series.bars)
    signal_index = _signal_bar_index(bars, signal_date)
    start_index = max(0, signal_index - pre_bars)
    end_index = min(len(bars), signal_index + post_bars + 1)
    return bars[start_index:end_index]


def build_historical_case_views(
    price_series: HistoricalPriceSeries,
    backtest_report: HistoricalBacktestReport,
    window_config: HistoricalCaseWindowConfig | None = None,
) -> tuple[HistoricalCaseView, ...]:
    window_config = window_config or HistoricalCaseWindowConfig()
    _validate_report(price_series, backtest_report)
    views = tuple(
        _build_case_view(price_series, backtest_report, case, window_config)
        for case in backtest_report.cases
    )
    return tuple(sorted(views, key=lambda view: (view.signal_date, view.case_id)))


def _build_case_view(
    price_series: HistoricalPriceSeries,
    report: HistoricalBacktestReport,
    case: HistoricalBacktestCase,
    window_config: HistoricalCaseWindowConfig,
) -> HistoricalCaseView:
    _validate_case(report, case)

    price_window = build_case_price_window(
        price_series,
        case.signal_event.signal_date,
        window_config.pre_signal_bars,
        window_config.post_signal_bars,
    )
    relative_index_by_date = _relative_index_by_date(price_series, case.signal_event.signal_date)
    target_hit_date = _target_hit_date(case.outcome)
    target_hit_bar_index = _target_hit_bar_index(case.outcome)
    signal_index = _signal_bar_index(tuple(price_series.bars), case.signal_event.signal_date)
    last_index = len(price_series.bars) - 1

    return HistoricalCaseView(
        case_id=case.case_id,
        symbol=case.symbol,
        currency=price_series.currency,
        signal_id=case.signal_event.signal_id,
        outcome_definition_id=case.outcome.outcome_definition_id,
        signal_date=case.signal_event.signal_date,
        signal_analysis_close=case.signal_event.signal_analysis_close,
        signal_raw_close=case.signal_event.signal_raw_close,
        reference_high=case.signal_event.reference_high,
        reference_low=case.signal_event.reference_low,
        outcome_status=case.outcome.status,
        target_hit_date=target_hit_date,
        target_hit_bar_index=target_hit_bar_index,
        max_close_return=case.outcome.max_close_return,
        max_close_return_date=case.outcome.max_close_return_date,
        max_adverse_return=case.outcome.max_adverse_return,
        max_adverse_return_date=case.outcome.max_adverse_return_date,
        end_of_window_return=case.outcome.end_of_window_return,
        horizon_bars=case.outcome.horizon_bars,
        available_future_bars=case.outcome.available_future_bars,
        pre_signal_bars=window_config.pre_signal_bars,
        post_signal_bars=window_config.post_signal_bars,
        price_points=tuple(
            _price_point(bar, relative_index_by_date[bar.trading_date], target_hit_date)
            for bar in price_window
        ),
        condition_details=tuple(
            _condition_detail(condition)
            for condition in case.signal_event.evaluated_conditions
        ),
        technical_snapshot_summary=_technical_snapshot_summary(case.signal_event.feature_snapshot),
        is_window_complete_before=signal_index >= window_config.pre_signal_bars,
        is_window_complete_after=(last_index - signal_index) >= window_config.post_signal_bars,
    )


def _validate_report(
    price_series: HistoricalPriceSeries,
    report: HistoricalBacktestReport,
) -> None:
    if price_series.symbol != report.symbol:
        raise HistoricalCaseDataError("Price series symbol must match backtest report symbol.")


def _validate_case(
    report: HistoricalBacktestReport,
    case: HistoricalBacktestCase,
) -> None:
    event = case.signal_event
    outcome = case.outcome
    if case.symbol != report.symbol or event.symbol != report.symbol or outcome.symbol != report.symbol:
        raise HistoricalCaseDataError("Case symbol must match backtest report symbol.")
    if event.signal_id != report.signal_definition_id:
        raise HistoricalCaseDataError("Case signal id must match backtest report signal id.")
    if outcome.outcome_definition_id != report.outcome_definition_id:
        raise HistoricalCaseDataError("Case outcome id must match backtest report outcome id.")
    if event.signal_id != outcome.signal_id or event.signal_date != outcome.signal_date:
        raise HistoricalCaseDataError("Case signal event identity must match outcome identity.")


def _signal_bar_index(
    bars: tuple[HistoricalPriceBar, ...],
    signal_date: date,
) -> int:
    for index, bar in enumerate(bars):
        if bar.trading_date == signal_date:
            return index
    raise HistoricalCaseDataError("Signal date is absent from the price series.")


def _relative_index_by_date(
    price_series: HistoricalPriceSeries,
    signal_date: date,
) -> dict[date, int]:
    signal_index = _signal_bar_index(tuple(price_series.bars), signal_date)
    return {
        bar.trading_date: index - signal_index
        for index, bar in enumerate(price_series.bars)
    }


def _price_point(
    bar: HistoricalPriceBar,
    relative_bar_index: int,
    target_hit_date: date | None,
) -> HistoricalCasePricePoint:
    return HistoricalCasePricePoint(
        trading_date=bar.trading_date,
        relative_bar_index=relative_bar_index,
        raw_open=bar.open,
        raw_high=bar.high,
        raw_low=bar.low,
        raw_close=bar.close,
        adjusted_close=bar.adjusted_close,
        analysis_close=get_analysis_close(bar),
        volume=bar.volume,
        is_signal_date=relative_bar_index == 0,
        is_target_hit_date=target_hit_date == bar.trading_date,
        before_or_after_signal=_before_or_after_signal(relative_bar_index),
    )


def _before_or_after_signal(relative_bar_index: int) -> str:
    if relative_bar_index < 0:
        return "BEFORE_SIGNAL"
    if relative_bar_index > 0:
        return "AFTER_SIGNAL"
    return "SIGNAL_DATE"


def _condition_detail(condition: EvaluatedSignalCondition) -> HistoricalCaseConditionDetail:
    return HistoricalCaseConditionDetail(
        metric=condition.metric,
        actual_value=condition.actual_value,
        operator=condition.operator.value,
        expected_value=condition.expected_value,
        secondary_metric=condition.secondary_metric,
        secondary_actual_value=condition.secondary_actual_value,
        evaluation_status=condition.status.value,
        matched=condition.matched,
    )


def _technical_snapshot_summary(
    snapshot: TechnicalIndicatorSnapshot,
) -> tuple[tuple[str, float | bool | None], ...]:
    metrics = (
        "analysis_close",
        "sma_20",
        "sma_60",
        "sma_120",
        "sma_200",
        "rsi_14",
        "macd",
        "macd_signal",
        "atr_14_pct",
        "volume_ratio_20",
        "distance_to_prior_60d_high",
        "return_20d",
        "return_60d",
    )
    return tuple((metric, getattr(snapshot, metric, None)) for metric in metrics)


def _target_hit_date(outcome: HistoricalOutcomeResult) -> date | None:
    if outcome.intraday_target_hit_date is not None:
        return outcome.intraday_target_hit_date
    return outcome.close_target_hit_date


def _target_hit_bar_index(outcome: HistoricalOutcomeResult) -> int | None:
    if outcome.intraday_target_hit_bar_index is not None:
        return outcome.intraday_target_hit_bar_index
    return outcome.close_target_hit_bar_index
