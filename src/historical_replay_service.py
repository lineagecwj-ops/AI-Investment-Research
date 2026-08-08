from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from statistics import mean
from statistics import median

from backtest_service import BacktestConfig
from backtest_service import HistoricalBacktestCase
from backtest_service import run_historical_backtest
from historical_price_service import get_historical_prices
from historical_price_service import slice_price_series_as_of
from models import HistoricalOutcomeResult
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OverlappingSignalPolicy
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import SignalMatch
from signal_outcome_service import build_signal_event
from signal_outcome_service import evaluate_historical_outcome
from signal_outcome_service import evaluate_signal_conditions
from signal_outcome_service import get_future_bars_after
from swing_scanner_service import RankComponent
from swing_scanner_service import SWING_RESEARCH_RANK_POLICY_V1
from swing_scanner_service import SampleSizeStatus
from swing_scanner_service import get_sample_size_status
from symbol_utils import normalize_stock_symbol
from technical_indicator_service import build_technical_indicator_series


@dataclass(frozen=True)
class HistoricalReplayConfig:

    replay_date: date

    signal_definition: SignalDefinition

    outcome_definition: OutcomeDefinition

    overlap_policy: OverlappingSignalPolicy = OverlappingSignalPolicy.ALLOW_ALL

    cooldown_bars: int | None = None

    historical_start_date: date | None = None

    preferred_resolved_samples: int = 20

    force_refresh: bool = False

    def __post_init__(self):
        if self.preferred_resolved_samples < 0:
            raise ValueError("preferred_resolved_samples cannot be negative.")
        if self.overlap_policy is OverlappingSignalPolicy.COOLDOWN:
            if self.cooldown_bars is None or self.cooldown_bars <= 0:
                raise ValueError("COOLDOWN policy requires a positive cooldown_bars value.")
        elif self.overlap_policy is OverlappingSignalPolicy.ALLOW_ALL:
            if self.cooldown_bars is not None:
                raise ValueError("ALLOW_ALL policy does not accept cooldown_bars.")
        else:
            raise ValueError(f"Unsupported overlap policy: {self.overlap_policy}")

    def to_backtest_config(self, *, actual_signal_date: date) -> BacktestConfig:
        return BacktestConfig(
            signal_definition=self.signal_definition,
            outcome_definition=self.outcome_definition,
            overlap_policy=self.overlap_policy,
            cooldown_bars=self.cooldown_bars,
            start_date=self.historical_start_date,
            end_date=actual_signal_date,
        )


@dataclass(frozen=True)
class PointInTimeBacktestSummary:

    historical_start_date: date | None

    replay_date: date

    actual_signal_date: date

    raw_signal_count: int

    evaluated_signal_count: int

    resolved_as_of_count: int

    hit_as_of_count: int

    miss_as_of_count: int

    incomplete_as_of_count: int

    not_evaluable_as_of_count: int

    historical_hit_rate_as_of: float | None

    average_max_close_return_as_of: float | None

    median_max_close_return_as_of: float | None

    average_max_adverse_return_as_of: float | None

    median_max_adverse_return_as_of: float | None

    average_end_return_as_of: float | None

    median_end_return_as_of: float | None

    average_hit_bar_index_as_of: float | None

    median_hit_bar_index_as_of: float | None

    max_return_sample_count_as_of: int

    max_adverse_sample_count_as_of: int

    end_return_sample_count_as_of: int

    hit_bar_sample_count_as_of: int

    known_cases: tuple[HistoricalBacktestCase, ...]

    metric_known_cases: tuple[HistoricalBacktestCase, ...]


@dataclass(frozen=True)
class HistoricalReplaySignalAudit:

    symbol: str

    requested_replay_date: date

    status: SignalEvaluationStatus

    actual_signal_date: date | None = None

    missing_required_features: tuple[str, ...] = tuple()

    failed_conditions: tuple[str, ...] = tuple()

    reason: str | None = None


@dataclass(frozen=True)
class HistoricalReplayFailure:

    symbol: str

    error_type: str

    message: str


@dataclass(frozen=True)
class HistoricalReplayCandidate:

    symbol: str

    requested_replay_date: date

    actual_signal_date: date

    signal_id: str

    signal_match: SignalMatch

    technical_snapshot: object

    point_in_time_backtest_summary: PointInTimeBacktestSummary

    post_replay_outcome: HistoricalOutcomeResult

    source_price_fetched_at: datetime

    source_price_is_stale: bool

    sample_size_status: SampleSizeStatus

    research_rank_policy: str

    research_rank: int | None = None

    rank_components: tuple[RankComponent, ...] = tuple()


@dataclass(frozen=True)
class HistoricalReplayResult:

    config: HistoricalReplayConfig

    requested_symbols: tuple[str, ...]

    normalized_symbols: tuple[str, ...]

    match_candidates: tuple[HistoricalReplayCandidate, ...]

    no_match_symbols: tuple[str, ...]

    no_match_details: tuple[HistoricalReplaySignalAudit, ...]

    not_evaluable_symbols: tuple[HistoricalReplaySignalAudit, ...]

    failed_symbols: tuple[HistoricalReplayFailure, ...]

    generated_at: datetime

    @property
    def scanned_count(self) -> int:
        return len(self.normalized_symbols)

    @property
    def matched_count(self) -> int:
        return len(self.match_candidates)

    @property
    def no_match_count(self) -> int:
        return len(self.no_match_symbols)

    @property
    def not_evaluable_count(self) -> int:
        return len(self.not_evaluable_symbols)

    @property
    def failure_count(self) -> int:
        return len(self.failed_symbols)


class HistoricalReplayService:

    def __init__(
        self,
        *,
        price_loader=get_historical_prices,
        technical_builder=build_technical_indicator_series,
        backtest_runner=run_historical_backtest,
    ):
        self.price_loader = price_loader
        self.technical_builder = technical_builder
        self.backtest_runner = backtest_runner

    def replay_scan(
        self,
        symbols,
        config: HistoricalReplayConfig,
        *,
        price_series_by_symbol: dict[str, HistoricalPriceSeries] | None = None,
    ) -> HistoricalReplayResult:
        requested_symbols = tuple(symbols)
        normalized_symbols = _normalize_unique_symbols(requested_symbols)
        candidates = []
        no_match_symbols = []
        no_match_details = []
        not_evaluable_symbols = []
        failed_symbols = []

        for symbol in normalized_symbols:
            try:
                replay_result = self._replay_symbol(
                    symbol,
                    config,
                    price_series_by_symbol=price_series_by_symbol,
                )
            except Exception as exc:
                failed_symbols.append(_safe_failure(symbol, exc))
                continue

            signal_match = replay_result.signal_match
            if signal_match.status is SignalEvaluationStatus.MATCH:
                candidates.append(replay_result.candidate)
            elif signal_match.status is SignalEvaluationStatus.NO_MATCH:
                no_match_symbols.append(symbol)
                no_match_details.append(_signal_audit(signal_match, config))
            elif signal_match.status is SignalEvaluationStatus.NOT_EVALUABLE:
                not_evaluable_symbols.append(_signal_audit(signal_match, config, reason=replay_result.reason))
            else:
                failed_symbols.append(
                    HistoricalReplayFailure(
                        symbol=symbol,
                        error_type="UnsupportedSignalStatus",
                        message=f"Unsupported signal status: {signal_match.status}",
                    )
                )

        ranked_candidates = rank_historical_replay_candidates(tuple(candidates))
        return HistoricalReplayResult(
            config=config,
            requested_symbols=requested_symbols,
            normalized_symbols=normalized_symbols,
            match_candidates=ranked_candidates,
            no_match_symbols=tuple(no_match_symbols),
            no_match_details=tuple(no_match_details),
            not_evaluable_symbols=tuple(not_evaluable_symbols),
            failed_symbols=tuple(failed_symbols),
            generated_at=datetime.now(UTC),
        )

    def _replay_symbol(
        self,
        symbol: str,
        config: HistoricalReplayConfig,
        *,
        price_series_by_symbol: dict[str, HistoricalPriceSeries] | None = None,
    ):
        if price_series_by_symbol is not None and symbol in price_series_by_symbol:
            full_price_series = price_series_by_symbol[symbol]
        else:
            full_price_series = self.price_loader(
                symbol,
                force_refresh=config.force_refresh,
            )
        replay_price_series = slice_price_series_as_of(full_price_series, config.replay_date)
        if not replay_price_series.bars:
            return _SymbolReplayResult(
                signal_match=_empty_not_evaluable_match(symbol, config),
                candidate=None,
                reason="no market data available on or before replay date",
            )

        replay_technical_series = self.technical_builder(replay_price_series)
        if not replay_technical_series.snapshots:
            return _SymbolReplayResult(
                signal_match=_empty_not_evaluable_match(
                    symbol,
                    config,
                    actual_signal_date=replay_price_series.bars[-1].trading_date,
                ),
                candidate=None,
                reason="insufficient technical history on or before replay date",
            )

        replay_snapshot = replay_technical_series.snapshots[-1]
        signal_match = evaluate_signal_conditions(replay_snapshot, config.signal_definition)
        if signal_match.status is not SignalEvaluationStatus.MATCH:
            return _SymbolReplayResult(signal_match=signal_match, candidate=None, reason=None)

        full_technical_series = self.technical_builder(full_price_series)
        report = self.backtest_runner(
            full_price_series,
            full_technical_series,
            config.to_backtest_config(actual_signal_date=signal_match.trading_date),
        )
        point_in_time_summary = build_point_in_time_backtest_summary(
            report.cases,
            price_series=full_price_series,
            config=config,
            actual_signal_date=signal_match.trading_date,
            raw_events=report.raw_events,
            evaluated_events=report.evaluated_events,
        )
        post_replay_outcome = evaluate_historical_outcome(
            build_signal_event(
                signal_match,
                signal_raw_close=_raw_close_for_date(full_price_series, signal_match.trading_date),
            ),
            full_price_series,
            config.outcome_definition,
        )
        return _SymbolReplayResult(
            signal_match=signal_match,
            candidate=build_historical_replay_candidate(
                signal_match=signal_match,
                summary=point_in_time_summary,
                post_replay_outcome=post_replay_outcome,
                price_series=full_price_series,
                config=config,
            ),
            reason=None,
        )


@dataclass(frozen=True)
class _SymbolReplayResult:

    signal_match: SignalMatch

    candidate: HistoricalReplayCandidate | None

    reason: str | None


def build_point_in_time_backtest_summary(
    cases: tuple[HistoricalBacktestCase, ...],
    *,
    price_series: HistoricalPriceSeries,
    config: HistoricalReplayConfig,
    actual_signal_date: date,
    raw_events=tuple(),
    evaluated_events=tuple(),
) -> PointInTimeBacktestSummary:
    as_of_cases = tuple(
        case for case in cases
        if _case_in_historical_range(case, config.historical_start_date, actual_signal_date)
    )
    known_cases = tuple(
        case for case in as_of_cases
        if is_outcome_known_as_of(case, price_series, config.replay_date)
    )
    metric_known_cases = tuple(
        case for case in known_cases
        if are_return_metrics_known_as_of(case, price_series, config.replay_date)
    )

    hit_cases = tuple(case for case in known_cases if case.status is OutcomeEvaluationStatus.HIT)
    miss_cases = tuple(case for case in known_cases if case.status is OutcomeEvaluationStatus.MISS)
    not_evaluable_cases = tuple(case for case in known_cases if case.status is OutcomeEvaluationStatus.NOT_EVALUABLE)
    unresolved_count = len(as_of_cases) - len(known_cases)
    resolved_count = len(hit_cases) + len(miss_cases)
    max_returns = _non_none_values(case.outcome.max_close_return for case in metric_known_cases)
    max_adverse_returns = _non_none_values(case.outcome.max_adverse_return for case in metric_known_cases)
    end_returns = _non_none_values(case.outcome.end_of_window_return for case in metric_known_cases)
    hit_bar_indexes = _non_none_values(
        _target_hit_bar_index(case.outcome)
        for case in hit_cases
    )

    return PointInTimeBacktestSummary(
        historical_start_date=config.historical_start_date,
        replay_date=config.replay_date,
        actual_signal_date=actual_signal_date,
        raw_signal_count=sum(
            1 for event in raw_events
            if _event_in_historical_range(event, config.historical_start_date, actual_signal_date)
        ),
        evaluated_signal_count=sum(
            1 for event in evaluated_events
            if _event_in_historical_range(event, config.historical_start_date, actual_signal_date)
        ) if evaluated_events else len(as_of_cases),
        resolved_as_of_count=resolved_count,
        hit_as_of_count=len(hit_cases),
        miss_as_of_count=len(miss_cases),
        incomplete_as_of_count=unresolved_count,
        not_evaluable_as_of_count=len(not_evaluable_cases),
        historical_hit_rate_as_of=None if resolved_count == 0 else len(hit_cases) / resolved_count,
        average_max_close_return_as_of=_mean_or_none(max_returns),
        median_max_close_return_as_of=_median_or_none(max_returns),
        average_max_adverse_return_as_of=_mean_or_none(max_adverse_returns),
        median_max_adverse_return_as_of=_median_or_none(max_adverse_returns),
        average_end_return_as_of=_mean_or_none(end_returns),
        median_end_return_as_of=_median_or_none(end_returns),
        average_hit_bar_index_as_of=_mean_or_none(hit_bar_indexes),
        median_hit_bar_index_as_of=_median_or_none(hit_bar_indexes),
        max_return_sample_count_as_of=len(max_returns),
        max_adverse_sample_count_as_of=len(max_adverse_returns),
        end_return_sample_count_as_of=len(end_returns),
        hit_bar_sample_count_as_of=len(hit_bar_indexes),
        known_cases=known_cases,
        metric_known_cases=metric_known_cases,
    )


def is_outcome_known_as_of(
    case: HistoricalBacktestCase,
    price_series: HistoricalPriceSeries,
    replay_date: date,
) -> bool:
    outcome = case.outcome
    if outcome.status is OutcomeEvaluationStatus.HIT:
        hit_date = _target_hit_date(outcome)
        return hit_date is not None and hit_date <= replay_date
    if outcome.status is OutcomeEvaluationStatus.MISS:
        horizon_end_date = full_horizon_end_date(case, price_series)
        return horizon_end_date is not None and horizon_end_date <= replay_date
    if outcome.status is OutcomeEvaluationStatus.NOT_EVALUABLE:
        return case.signal_event.signal_date <= replay_date
    return False


def are_return_metrics_known_as_of(
    case: HistoricalBacktestCase,
    price_series: HistoricalPriceSeries,
    replay_date: date,
) -> bool:
    horizon_end_date = full_horizon_end_date(case, price_series)
    return horizon_end_date is not None and horizon_end_date <= replay_date


def full_horizon_end_date(
    case: HistoricalBacktestCase,
    price_series: HistoricalPriceSeries,
) -> date | None:
    future_bars = get_future_bars_after(
        price_series,
        case.signal_event.signal_date,
        case.outcome.horizon_bars,
    )
    if len(future_bars) < case.outcome.horizon_bars:
        return None
    return future_bars[-1].trading_date


def build_historical_replay_candidate(
    *,
    signal_match: SignalMatch,
    summary: PointInTimeBacktestSummary,
    post_replay_outcome: HistoricalOutcomeResult,
    price_series: HistoricalPriceSeries,
    config: HistoricalReplayConfig,
) -> HistoricalReplayCandidate:
    sample_status = get_sample_size_status(
        summary.resolved_as_of_count,
        config.preferred_resolved_samples,
    )
    candidate = HistoricalReplayCandidate(
        symbol=signal_match.symbol,
        requested_replay_date=config.replay_date,
        actual_signal_date=signal_match.trading_date,
        signal_id=signal_match.signal_id,
        signal_match=signal_match,
        technical_snapshot=signal_match.feature_snapshot,
        point_in_time_backtest_summary=summary,
        post_replay_outcome=post_replay_outcome,
        source_price_fetched_at=price_series.fetched_at,
        source_price_is_stale=price_series.is_stale,
        sample_size_status=sample_status,
        research_rank_policy=SWING_RESEARCH_RANK_POLICY_V1,
    )
    return replace(candidate, rank_components=get_historical_replay_rank_components(candidate))


def rank_historical_replay_candidates(
    candidates: tuple[HistoricalReplayCandidate, ...],
) -> tuple[HistoricalReplayCandidate, ...]:
    sorted_candidates = tuple(sorted(candidates, key=_rank_key))
    return tuple(
        replace(
            candidate,
            research_rank=index,
            rank_components=get_historical_replay_rank_components(candidate),
        )
        for index, candidate in enumerate(sorted_candidates, start=1)
    )


def get_historical_replay_rank_components(
    candidate: HistoricalReplayCandidate,
) -> tuple[RankComponent, ...]:
    summary = candidate.point_in_time_backtest_summary
    return (
        RankComponent("sample_size_status", "sample_size_status_as_of", candidate.sample_size_status.value),
        RankComponent("historical_hit_rate", "historical_hit_rate_as_of", summary.historical_hit_rate_as_of),
        RankComponent("resolved_count", "resolved_as_of_count", summary.resolved_as_of_count),
        RankComponent("median_max_adverse_return", "median_max_adverse_return_as_of", summary.median_max_adverse_return_as_of),
        RankComponent("median_max_close_return", "median_max_close_return_as_of", summary.median_max_close_return_as_of),
        RankComponent("median_end_return", "median_end_return_as_of", summary.median_end_return_as_of),
        RankComponent("symbol", "symbol", candidate.symbol),
    )


def _rank_key(candidate: HistoricalReplayCandidate):
    summary = candidate.point_in_time_backtest_summary
    return (
        _sample_status_rank(candidate.sample_size_status),
        _descending_optional(summary.historical_hit_rate_as_of),
        -summary.resolved_as_of_count,
        _descending_optional(summary.median_max_adverse_return_as_of),
        _descending_optional(summary.median_max_close_return_as_of),
        _descending_optional(summary.median_end_return_as_of),
        candidate.symbol,
    )


def _sample_status_rank(status: SampleSizeStatus) -> int:
    order = {
        SampleSizeStatus.MEETS_PREFERRED_MINIMUM: 0,
        SampleSizeStatus.BELOW_PREFERRED_MINIMUM: 1,
        SampleSizeStatus.NO_RESOLVED_SAMPLES: 2,
    }
    return order[status]


def _descending_optional(value: float | None):
    if value is None:
        return (1, 0.0)
    return (0, -value)


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


def _case_in_historical_range(
    case: HistoricalBacktestCase,
    start_date: date | None,
    end_date: date,
) -> bool:
    return _event_in_historical_range(case.signal_event, start_date, end_date)


def _event_in_historical_range(event, start_date: date | None, end_date: date) -> bool:
    if start_date is not None and event.signal_date < start_date:
        return False
    return event.signal_date <= end_date


def _target_hit_date(outcome: HistoricalOutcomeResult) -> date | None:
    return outcome.intraday_target_hit_date or outcome.close_target_hit_date


def _target_hit_bar_index(outcome: HistoricalOutcomeResult) -> int | None:
    return outcome.intraday_target_hit_bar_index or outcome.close_target_hit_bar_index


def _raw_close_for_date(price_series: HistoricalPriceSeries, trading_date: date) -> float | None:
    for bar in price_series.bars:
        if bar.trading_date == trading_date:
            return bar.close
    return None


def _safe_failure(symbol: str, exc: Exception) -> HistoricalReplayFailure:
    message = str(exc) or exc.__class__.__name__
    return HistoricalReplayFailure(
        symbol=symbol,
        error_type=exc.__class__.__name__,
        message=message.splitlines()[0],
    )


def _signal_audit(
    signal_match: SignalMatch,
    config: HistoricalReplayConfig,
    *,
    reason: str | None = None,
) -> HistoricalReplaySignalAudit:
    missing_required = tuple(
        metric
        for metric in config.signal_definition.minimum_required_features
        if not _is_usable_value(getattr(signal_match.feature_snapshot, metric, None))
    )
    failed_conditions = tuple(
        condition.metric
        for condition in signal_match.evaluated_conditions
        if condition.status is SignalEvaluationStatus.NO_MATCH
    )
    not_evaluable_conditions = tuple(
        condition.metric
        for condition in signal_match.evaluated_conditions
        if condition.status is SignalEvaluationStatus.NOT_EVALUABLE
    )
    return HistoricalReplaySignalAudit(
        symbol=signal_match.symbol,
        requested_replay_date=config.replay_date,
        actual_signal_date=None if signal_match.trading_date == date.min else signal_match.trading_date,
        status=signal_match.status,
        missing_required_features=missing_required or not_evaluable_conditions,
        failed_conditions=failed_conditions,
        reason=reason,
    )


def _empty_not_evaluable_match(
    symbol: str,
    config: HistoricalReplayConfig,
    *,
    actual_signal_date: date | None = None,
) -> SignalMatch:
    from swing_scanner_service import _empty_not_evaluable_match as scanner_empty_match

    match = scanner_empty_match(symbol, config.signal_definition)
    if actual_signal_date is None:
        return match
    return replace(match, trading_date=actual_signal_date)


def _is_usable_value(value) -> bool:
    if isinstance(value, bool):
        return True
    if not isinstance(value, (int, float)):
        return False
    return value == value and value not in (float("inf"), float("-inf"))


def _non_none_values(values) -> tuple[float, ...]:
    return tuple(value for value in values if value is not None)


def _mean_or_none(values: tuple[float, ...]) -> float | None:
    return None if not values else mean(values)


def _median_or_none(values: tuple[float, ...]) -> float | None:
    return None if not values else median(values)
