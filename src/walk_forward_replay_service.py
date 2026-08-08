from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from enum import Enum
import calendar
import hashlib

from historical_price_service import get_historical_prices
from historical_replay_service import HistoricalReplayConfig
from historical_replay_service import HistoricalReplayResult
from historical_replay_service import HistoricalReplayService
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OverlappingSignalPolicy
from models import SignalDefinition
from symbol_utils import normalize_stock_symbol


MAX_REPLAY_PERIODS = 120


class WalkForwardReplayFrequency(Enum):

    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"


@dataclass(frozen=True)
class WalkForwardReplayConfig:

    start_date: date

    end_date: date

    frequency: WalkForwardReplayFrequency = WalkForwardReplayFrequency.MONTHLY

    signal_definition: SignalDefinition | None = None

    outcome_definition: OutcomeDefinition | None = None

    overlap_policy: OverlappingSignalPolicy = OverlappingSignalPolicy.ALLOW_ALL

    cooldown_bars: int | None = None

    historical_start_date: date | None = None

    preferred_resolved_samples: int = 20

    force_refresh: bool = False

    max_replay_periods: int = MAX_REPLAY_PERIODS

    def __post_init__(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date.")
        if self.preferred_resolved_samples < 0:
            raise ValueError("preferred_resolved_samples cannot be negative.")
        if self.max_replay_periods <= 0:
            raise ValueError("max_replay_periods must be positive.")
        if self.overlap_policy is OverlappingSignalPolicy.COOLDOWN:
            if self.cooldown_bars is None or self.cooldown_bars <= 0:
                raise ValueError("COOLDOWN policy requires a positive cooldown_bars value.")
        elif self.overlap_policy is OverlappingSignalPolicy.ALLOW_ALL:
            if self.cooldown_bars is not None:
                raise ValueError("ALLOW_ALL policy does not accept cooldown_bars.")
        else:
            raise ValueError(f"Unsupported overlap policy: {self.overlap_policy}")
        if not isinstance(self.frequency, WalkForwardReplayFrequency):
            raise ValueError(f"Unsupported walk-forward frequency: {self.frequency}")

    def to_replay_config(self, replay_date: date) -> HistoricalReplayConfig:
        if self.signal_definition is None:
            raise ValueError("signal_definition is required.")
        if self.outcome_definition is None:
            raise ValueError("outcome_definition is required.")
        return HistoricalReplayConfig(
            replay_date=replay_date,
            signal_definition=self.signal_definition,
            outcome_definition=self.outcome_definition,
            overlap_policy=self.overlap_policy,
            cooldown_bars=self.cooldown_bars,
            historical_start_date=self.historical_start_date,
            preferred_resolved_samples=self.preferred_resolved_samples,
            force_refresh=self.force_refresh,
        )


@dataclass(frozen=True)
class WalkForwardReplayFailure:

    requested_replay_date: date

    error_type: str

    safe_message: str


@dataclass(frozen=True)
class WalkForwardReplayPeriod:

    requested_replay_date: date

    replay_result: HistoricalReplayResult | None = None

    failure: WalkForwardReplayFailure | None = None

    @property
    def scanned_count(self) -> int:
        return 0 if self.replay_result is None else self.replay_result.scanned_count

    @property
    def matched_count(self) -> int:
        return 0 if self.replay_result is None else self.replay_result.matched_count

    @property
    def no_match_count(self) -> int:
        return 0 if self.replay_result is None else self.replay_result.no_match_count

    @property
    def not_evaluable_count(self) -> int:
        return 0 if self.replay_result is None else self.replay_result.not_evaluable_count

    @property
    def failed_count(self) -> int:
        if self.failure is not None:
            return 1
        return 0 if self.replay_result is None else self.replay_result.failure_count


@dataclass(frozen=True)
class WalkForwardSymbolSummary:

    symbol: str

    candidate_occurrence_count: int

    first_candidate_date: date

    last_candidate_date: date

    post_replay_hit_count: int

    post_replay_miss_count: int

    post_replay_incomplete_count: int

    post_replay_not_evaluable_count: int


@dataclass(frozen=True)
class WalkForwardReplaySummary:

    period_count: int

    periods_with_matches: int

    periods_without_matches: int

    total_candidate_occurrences: int

    unique_candidate_symbols: int

    post_replay_hit_occurrences: int

    post_replay_miss_occurrences: int

    post_replay_incomplete_occurrences: int

    post_replay_not_evaluable_occurrences: int

    symbol_summaries: tuple[WalkForwardSymbolSummary, ...]


@dataclass(frozen=True)
class WalkForwardReplayResult:

    config: WalkForwardReplayConfig

    requested_symbols: tuple[str, ...]

    normalized_symbols: tuple[str, ...]

    replay_dates: tuple[date, ...]

    period_results: tuple[WalkForwardReplayPeriod, ...]

    summary: WalkForwardReplaySummary

    generated_at: datetime

    walk_forward_id: str


class WalkForwardReplayService:

    def __init__(
        self,
        *,
        price_loader=get_historical_prices,
        replay_service: HistoricalReplayService | None = None,
    ):
        self.price_loader = price_loader
        self.replay_service = replay_service or HistoricalReplayService(price_loader=price_loader)

    def run_walk_forward_replay(
        self,
        symbols,
        config: WalkForwardReplayConfig,
    ) -> WalkForwardReplayResult:
        requested_symbols = tuple(symbols)
        normalized_symbols = _normalize_unique_symbols(requested_symbols)
        replay_dates = generate_replay_dates(config)
        if not normalized_symbols:
            periods = tuple()
            summary = summarize_walk_forward_periods(periods)
            return WalkForwardReplayResult(
                config=config,
                requested_symbols=requested_symbols,
                normalized_symbols=normalized_symbols,
                replay_dates=replay_dates,
                period_results=periods,
                summary=summary,
                generated_at=datetime.now(UTC),
                walk_forward_id=build_walk_forward_id(normalized_symbols, config, replay_dates),
            )

        full_price_series_by_symbol = {
            symbol: self.price_loader(symbol, force_refresh=config.force_refresh)
            for symbol in normalized_symbols
        }
        periods = []
        for replay_date in replay_dates:
            try:
                replay_config = config.to_replay_config(replay_date)
                replay_result = self.replay_service.replay_scan(
                    normalized_symbols,
                    replay_config,
                    price_series_by_symbol=full_price_series_by_symbol,
                )
                periods.append(
                    WalkForwardReplayPeriod(
                        requested_replay_date=replay_date,
                        replay_result=replay_result,
                    )
                )
            except Exception as exc:
                periods.append(
                    WalkForwardReplayPeriod(
                        requested_replay_date=replay_date,
                        failure=_safe_failure(replay_date, exc),
                    )
                )

        period_results = tuple(periods)
        return WalkForwardReplayResult(
            config=config,
            requested_symbols=requested_symbols,
            normalized_symbols=normalized_symbols,
            replay_dates=replay_dates,
            period_results=period_results,
            summary=summarize_walk_forward_periods(period_results),
            generated_at=datetime.now(UTC),
            walk_forward_id=build_walk_forward_id(normalized_symbols, config, replay_dates),
        )


def generate_replay_dates(config: WalkForwardReplayConfig) -> tuple[date, ...]:
    if config.frequency is WalkForwardReplayFrequency.MONTHLY:
        replay_dates = _monthly_replay_dates(config.start_date, config.end_date)
    elif config.frequency is WalkForwardReplayFrequency.WEEKLY:
        replay_dates = _weekly_replay_dates(config.start_date, config.end_date)
    else:
        raise ValueError(f"Unsupported walk-forward frequency: {config.frequency}")
    if len(replay_dates) > config.max_replay_periods:
        raise ValueError(
            f"Walk-forward replay period count {len(replay_dates)} exceeds safety limit "
            f"{config.max_replay_periods}."
        )
    return replay_dates


def summarize_walk_forward_periods(
    periods: tuple[WalkForwardReplayPeriod, ...],
) -> WalkForwardReplaySummary:
    candidates = []
    for period in periods:
        if period.replay_result is None:
            continue
        candidates.extend(period.replay_result.match_candidates)

    hit_count = _count_outcome_status(candidates, OutcomeEvaluationStatus.HIT)
    miss_count = _count_outcome_status(candidates, OutcomeEvaluationStatus.MISS)
    incomplete_count = _count_outcome_status(candidates, OutcomeEvaluationStatus.INCOMPLETE)
    not_evaluable_count = _count_outcome_status(candidates, OutcomeEvaluationStatus.NOT_EVALUABLE)
    symbol_summaries = _summarize_symbols(candidates)

    return WalkForwardReplaySummary(
        period_count=len(periods),
        periods_with_matches=sum(1 for period in periods if period.matched_count > 0),
        periods_without_matches=sum(1 for period in periods if period.matched_count == 0),
        total_candidate_occurrences=len(candidates),
        unique_candidate_symbols=len(symbol_summaries),
        post_replay_hit_occurrences=hit_count,
        post_replay_miss_occurrences=miss_count,
        post_replay_incomplete_occurrences=incomplete_count,
        post_replay_not_evaluable_occurrences=not_evaluable_count,
        symbol_summaries=symbol_summaries,
    )


def build_walk_forward_id(
    normalized_symbols: tuple[str, ...],
    config: WalkForwardReplayConfig,
    replay_dates: tuple[date, ...],
    *,
    source_type: str = "",
) -> str:
    identity = "|".join(
        (
            source_type,
            ",".join(normalized_symbols),
            config.start_date.isoformat(),
            config.end_date.isoformat(),
            config.frequency.value,
            "" if config.signal_definition is None else config.signal_definition.id,
            "" if config.outcome_definition is None else config.outcome_definition.id,
            config.overlap_policy.value,
            "" if config.cooldown_bars is None else str(config.cooldown_bars),
            "" if config.historical_start_date is None else config.historical_start_date.isoformat(),
            str(config.preferred_resolved_samples),
            ",".join(replay_date.isoformat() for replay_date in replay_dates),
        )
    )
    return f"walk_forward_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def _monthly_replay_dates(start_date: date, end_date: date) -> tuple[date, ...]:
    replay_dates = []
    year = start_date.year
    month = start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        last_day = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day)
        if start_date <= month_end <= end_date:
            replay_dates.append(month_end)
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return tuple(replay_dates)


def _weekly_replay_dates(start_date: date, end_date: date) -> tuple[date, ...]:
    current = start_date
    while current.weekday() != 4:
        current += timedelta(days=1)
    replay_dates = []
    while current <= end_date:
        replay_dates.append(current)
        current += timedelta(days=7)
    return tuple(replay_dates)


def _summarize_symbols(candidates) -> tuple[WalkForwardSymbolSummary, ...]:
    by_symbol = {}
    for candidate in candidates:
        by_symbol.setdefault(candidate.symbol, []).append(candidate)
    summaries = []
    for symbol in sorted(by_symbol):
        symbol_candidates = by_symbol[symbol]
        candidate_dates = tuple(candidate.requested_replay_date for candidate in symbol_candidates)
        summaries.append(
            WalkForwardSymbolSummary(
                symbol=symbol,
                candidate_occurrence_count=len(symbol_candidates),
                first_candidate_date=min(candidate_dates),
                last_candidate_date=max(candidate_dates),
                post_replay_hit_count=_count_outcome_status(symbol_candidates, OutcomeEvaluationStatus.HIT),
                post_replay_miss_count=_count_outcome_status(symbol_candidates, OutcomeEvaluationStatus.MISS),
                post_replay_incomplete_count=_count_outcome_status(symbol_candidates, OutcomeEvaluationStatus.INCOMPLETE),
                post_replay_not_evaluable_count=_count_outcome_status(symbol_candidates, OutcomeEvaluationStatus.NOT_EVALUABLE),
            )
        )
    return tuple(summaries)


def _count_outcome_status(candidates, status: OutcomeEvaluationStatus) -> int:
    return sum(1 for candidate in candidates if candidate.post_replay_outcome.status is status)


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


def _safe_failure(replay_date: date, exc: Exception) -> WalkForwardReplayFailure:
    message = str(exc) or exc.__class__.__name__
    return WalkForwardReplayFailure(
        requested_replay_date=replay_date,
        error_type=exc.__class__.__name__,
        safe_message=message.splitlines()[0],
    )


def run_walk_forward_replay(symbols, config: WalkForwardReplayConfig) -> WalkForwardReplayResult:
    return WalkForwardReplayService().run_walk_forward_replay(symbols, config)
