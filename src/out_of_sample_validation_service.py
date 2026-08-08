from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from enum import Enum
import hashlib
import json

from historical_price_service import get_historical_prices
from historical_replay_service import HistoricalReplayService
from models import HistoricalPriceSeries
from models import OutcomeDefinition
from models import OutcomeEvaluationStatus
from models import OverlappingSignalPolicy
from models import SignalDefinition
from replay_analytics_service import ReplayAnalyticsResult
from replay_analytics_service import ReplayAnalyticsService
from replay_analytics_service import ReplayOutcomeDistribution
from symbol_utils import normalize_stock_symbol
from walk_forward_replay_service import WalkForwardReplayConfig
from walk_forward_replay_service import WalkForwardReplayFailure
from walk_forward_replay_service import WalkForwardReplayFrequency
from walk_forward_replay_service import WalkForwardReplayPeriod
from walk_forward_replay_service import WalkForwardReplayResult
from walk_forward_replay_service import build_walk_forward_id
from walk_forward_replay_service import generate_replay_dates
from walk_forward_replay_service import summarize_walk_forward_periods


class OutOfSampleValidationError(Exception):
    """Base error for out-of-sample validation failures."""


class ValidationPeriodRole(Enum):

    DEVELOPMENT = "DEVELOPMENT"
    VALIDATION = "VALIDATION"
    HOLDOUT = "HOLDOUT"


@dataclass(frozen=True)
class ValidationPeriod:

    role: ValidationPeriodRole

    start_date: date

    end_date: date

    def __post_init__(self):
        if not isinstance(self.role, ValidationPeriodRole):
            raise OutOfSampleValidationError(f"Unsupported validation period role: {self.role}")
        if self.start_date > self.end_date:
            raise OutOfSampleValidationError("Validation period start_date cannot be after end_date.")


@dataclass(frozen=True)
class FrozenResearchSpecification:

    signal_definition: SignalDefinition

    outcome_definition: OutcomeDefinition

    replay_frequency: WalkForwardReplayFrequency

    overlap_policy: OverlappingSignalPolicy

    cooldown_bars: int | None

    historical_start_date: date | None

    minimum_resolved_samples: int

    generated_at: datetime

    @property
    def fingerprint(self) -> str:
        return build_research_fingerprint(self)


@dataclass(frozen=True)
class OutOfSampleValidationConfig:

    signal_definition: SignalDefinition

    outcome_definition: OutcomeDefinition

    development_period: ValidationPeriod

    validation_period: ValidationPeriod

    holdout_period: ValidationPeriod

    replay_frequency: WalkForwardReplayFrequency = WalkForwardReplayFrequency.MONTHLY

    overlap_policy: OverlappingSignalPolicy = OverlappingSignalPolicy.ALLOW_ALL

    cooldown_bars: int | None = None

    historical_start_date: date | None = None

    minimum_resolved_samples: int = 20

    force_refresh: bool = False

    max_replay_periods: int = 120

    def __post_init__(self):
        if self.development_period.role is not ValidationPeriodRole.DEVELOPMENT:
            raise OutOfSampleValidationError("development_period must use DEVELOPMENT role.")
        if self.validation_period.role is not ValidationPeriodRole.VALIDATION:
            raise OutOfSampleValidationError("validation_period must use VALIDATION role.")
        if self.holdout_period.role is not ValidationPeriodRole.HOLDOUT:
            raise OutOfSampleValidationError("holdout_period must use HOLDOUT role.")
        _validate_period_order(
            self.development_period,
            self.validation_period,
            self.holdout_period,
        )
        if self.minimum_resolved_samples < 0:
            raise OutOfSampleValidationError("minimum_resolved_samples cannot be negative.")
        if self.max_replay_periods <= 0:
            raise OutOfSampleValidationError("max_replay_periods must be positive.")
        if self.overlap_policy is OverlappingSignalPolicy.COOLDOWN:
            if self.cooldown_bars is None or self.cooldown_bars <= 0:
                raise OutOfSampleValidationError("COOLDOWN policy requires a positive cooldown_bars value.")
        elif self.overlap_policy is OverlappingSignalPolicy.ALLOW_ALL:
            if self.cooldown_bars is not None:
                raise OutOfSampleValidationError("ALLOW_ALL policy does not accept cooldown_bars.")
        else:
            raise OutOfSampleValidationError(f"Unsupported overlap policy: {self.overlap_policy}")
        if not isinstance(self.replay_frequency, WalkForwardReplayFrequency):
            raise OutOfSampleValidationError(f"Unsupported replay frequency: {self.replay_frequency}")

    @property
    def periods(self) -> tuple[ValidationPeriod, ValidationPeriod, ValidationPeriod]:
        return (self.development_period, self.validation_period, self.holdout_period)

    def frozen_specification(self, *, generated_at: datetime | None = None) -> FrozenResearchSpecification:
        return FrozenResearchSpecification(
            signal_definition=self.signal_definition,
            outcome_definition=self.outcome_definition,
            replay_frequency=self.replay_frequency,
            overlap_policy=self.overlap_policy,
            cooldown_bars=self.cooldown_bars,
            historical_start_date=self.historical_start_date,
            minimum_resolved_samples=self.minimum_resolved_samples,
            generated_at=generated_at or datetime.now(UTC),
        )

    def to_walk_forward_config(self, period: ValidationPeriod) -> WalkForwardReplayConfig:
        return WalkForwardReplayConfig(
            start_date=period.start_date,
            end_date=period.end_date,
            frequency=self.replay_frequency,
            signal_definition=self.signal_definition,
            outcome_definition=self.outcome_definition,
            overlap_policy=self.overlap_policy,
            cooldown_bars=self.cooldown_bars,
            historical_start_date=self.historical_start_date,
            preferred_resolved_samples=self.minimum_resolved_samples,
            force_refresh=self.force_refresh,
            max_replay_periods=self.max_replay_periods,
        )


@dataclass(frozen=True)
class OutOfSamplePeriodResult:

    role: ValidationPeriodRole

    start_date: date

    end_date: date

    requested_replay_period_count: int

    completed_replay_period_count: int

    periods_with_candidates: int

    periods_without_candidates: int

    unique_candidate_symbols: int

    total_candidate_occurrences: int

    candidate_period_share: float

    post_replay_hit_count: int

    post_replay_miss_count: int

    post_replay_incomplete_count: int

    post_replay_not_evaluable_count: int

    resolved_count: int

    historical_hit_rate: float | None

    replay_dates: tuple[date, ...]

    walk_forward_result: WalkForwardReplayResult

    replay_analytics: ReplayAnalyticsResult

    research_fingerprint: str


@dataclass(frozen=True)
class CrossPeriodComparison:

    candidate_period_share_differences: tuple[tuple[str, str, float], ...]

    unique_candidate_symbol_count_differences: tuple[tuple[str, str, int], ...]

    total_candidate_occurrence_differences: tuple[tuple[str, str, int], ...]

    post_replay_outcome_count_differences: tuple[tuple[str, str, tuple[int, int, int, int]], ...]

    candidate_set_jaccard: tuple[tuple[str, str, float], ...]


@dataclass(frozen=True)
class OutOfSampleValidationResult:

    config: OutOfSampleValidationConfig

    frozen_specification: FrozenResearchSpecification

    research_fingerprint: str

    requested_symbols: tuple[str, ...]

    normalized_symbols: tuple[str, ...]

    development_result: OutOfSamplePeriodResult

    validation_result: OutOfSamplePeriodResult

    holdout_result: OutOfSamplePeriodResult

    comparison: CrossPeriodComparison

    price_loader_call_count: int | None

    generated_at: datetime

    @property
    def all_periods_same_fingerprint(self) -> bool:
        fingerprints = {
            self.development_result.research_fingerprint,
            self.validation_result.research_fingerprint,
            self.holdout_result.research_fingerprint,
        }
        return fingerprints == {self.research_fingerprint}


class OutOfSampleValidationService:

    def __init__(
        self,
        *,
        price_loader=get_historical_prices,
        replay_service: HistoricalReplayService | None = None,
        analytics_service: ReplayAnalyticsService | None = None,
    ):
        self.price_loader = price_loader
        self.replay_service = replay_service or HistoricalReplayService(price_loader=price_loader)
        self.analytics_service = analytics_service or ReplayAnalyticsService()

    def run_out_of_sample_validation(
        self,
        symbols,
        config: OutOfSampleValidationConfig,
    ) -> OutOfSampleValidationResult:
        requested_symbols = tuple(symbols)
        normalized_symbols = _normalize_unique_symbols(requested_symbols)
        generated_at = datetime.now(UTC)
        frozen_specification = config.frozen_specification(generated_at=generated_at)
        research_fingerprint = frozen_specification.fingerprint
        full_price_series_by_symbol = self._load_full_price_series(normalized_symbols, config)

        period_results = tuple(
            self._run_period(
                normalized_symbols,
                config,
                period,
                price_series_by_symbol=full_price_series_by_symbol,
                research_fingerprint=research_fingerprint,
            )
            for period in config.periods
        )

        return OutOfSampleValidationResult(
            config=config,
            frozen_specification=frozen_specification,
            research_fingerprint=research_fingerprint,
            requested_symbols=requested_symbols,
            normalized_symbols=normalized_symbols,
            development_result=period_results[0],
            validation_result=period_results[1],
            holdout_result=period_results[2],
            comparison=build_cross_period_comparison(period_results),
            price_loader_call_count=_loader_call_count(self.price_loader),
            generated_at=generated_at,
        )

    def _load_full_price_series(
        self,
        normalized_symbols: tuple[str, ...],
        config: OutOfSampleValidationConfig,
    ) -> dict[str, HistoricalPriceSeries]:
        loaded = {}
        for symbol in normalized_symbols:
            try:
                loaded[symbol] = self.price_loader(symbol, force_refresh=config.force_refresh)
            except Exception:
                loaded[symbol] = HistoricalPriceSeries(
                    symbol=symbol,
                    currency=None,
                    bars=tuple(),
                    fetched_at=datetime.now(UTC),
                    is_stale=True,
                    source="Provider failure",
                )
        return loaded

    def _run_period(
        self,
        normalized_symbols: tuple[str, ...],
        config: OutOfSampleValidationConfig,
        period: ValidationPeriod,
        *,
        price_series_by_symbol: dict[str, HistoricalPriceSeries],
        research_fingerprint: str,
    ) -> OutOfSamplePeriodResult:
        walk_forward_config = config.to_walk_forward_config(period)
        replay_dates = generate_replay_dates(walk_forward_config)
        period_results = []
        for replay_date in replay_dates:
            try:
                replay_config = walk_forward_config.to_replay_config(replay_date)
                replay_result = self.replay_service.replay_scan(
                    normalized_symbols,
                    replay_config,
                    price_series_by_symbol=price_series_by_symbol,
                )
                period_results.append(
                    WalkForwardReplayPeriod(
                        requested_replay_date=replay_date,
                        replay_result=replay_result,
                    )
                )
            except Exception as exc:
                period_results.append(
                    WalkForwardReplayPeriod(
                        requested_replay_date=replay_date,
                        failure=_safe_failure(replay_date, exc),
                    )
                )
        walk_forward_result = WalkForwardReplayResult(
            config=walk_forward_config,
            requested_symbols=normalized_symbols,
            normalized_symbols=normalized_symbols,
            replay_dates=replay_dates,
            period_results=tuple(period_results),
            summary=summarize_walk_forward_periods(tuple(period_results)),
            generated_at=datetime.now(UTC),
            walk_forward_id=build_walk_forward_id(normalized_symbols, walk_forward_config, replay_dates),
        )
        replay_analytics = self.analytics_service.build_analytics(walk_forward_result)
        distribution = replay_analytics.post_replay_outcome_distribution
        resolved_count = distribution.resolved_post_replay_count
        return OutOfSamplePeriodResult(
            role=period.role,
            start_date=period.start_date,
            end_date=period.end_date,
            requested_replay_period_count=len(replay_dates),
            completed_replay_period_count=sum(
                1 for replay_period in period_results
                if replay_period.replay_result is not None
            ),
            periods_with_candidates=replay_analytics.stability_summary.periods_with_candidates,
            periods_without_candidates=replay_analytics.stability_summary.periods_without_candidates,
            unique_candidate_symbols=replay_analytics.stability_summary.unique_candidate_symbols,
            total_candidate_occurrences=replay_analytics.stability_summary.total_candidate_occurrences,
            candidate_period_share=replay_analytics.stability_summary.candidate_period_share,
            post_replay_hit_count=distribution.post_replay_hit_count,
            post_replay_miss_count=distribution.post_replay_miss_count,
            post_replay_incomplete_count=distribution.post_replay_incomplete_count,
            post_replay_not_evaluable_count=distribution.post_replay_not_evaluable_count,
            resolved_count=resolved_count,
            historical_hit_rate=None if resolved_count == 0 else distribution.post_replay_hit_count / resolved_count,
            replay_dates=replay_dates,
            walk_forward_result=walk_forward_result,
            replay_analytics=replay_analytics,
            research_fingerprint=research_fingerprint,
        )


def run_out_of_sample_validation(symbols, config: OutOfSampleValidationConfig) -> OutOfSampleValidationResult:
    return OutOfSampleValidationService().run_out_of_sample_validation(symbols, config)


def build_research_fingerprint(specification: FrozenResearchSpecification) -> str:
    payload = {
        "signal_definition": _stable_value(specification.signal_definition),
        "outcome_definition": _stable_value(specification.outcome_definition),
        "replay_frequency": specification.replay_frequency.value,
        "overlap_policy": specification.overlap_policy.value,
        "cooldown_bars": specification.cooldown_bars,
        "historical_start_date": _stable_value(specification.historical_start_date),
        "minimum_resolved_samples": specification.minimum_resolved_samples,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"oos_research_{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:16]}"


def build_cross_period_comparison(
    period_results: tuple[OutOfSamplePeriodResult, ...],
) -> CrossPeriodComparison:
    pairs = (
        (period_results[0], period_results[1]),
        (period_results[1], period_results[2]),
        (period_results[0], period_results[2]),
    )
    return CrossPeriodComparison(
        candidate_period_share_differences=tuple(
            (
                left.role.value,
                right.role.value,
                right.candidate_period_share - left.candidate_period_share,
            )
            for left, right in pairs
        ),
        unique_candidate_symbol_count_differences=tuple(
            (
                left.role.value,
                right.role.value,
                right.unique_candidate_symbols - left.unique_candidate_symbols,
            )
            for left, right in pairs
        ),
        total_candidate_occurrence_differences=tuple(
            (
                left.role.value,
                right.role.value,
                right.total_candidate_occurrences - left.total_candidate_occurrences,
            )
            for left, right in pairs
        ),
        post_replay_outcome_count_differences=tuple(
            (
                left.role.value,
                right.role.value,
                _outcome_count_delta(
                    left.replay_analytics.post_replay_outcome_distribution,
                    right.replay_analytics.post_replay_outcome_distribution,
                ),
            )
            for left, right in pairs
        ),
        candidate_set_jaccard=tuple(
            (
                left.role.value,
                right.role.value,
                _candidate_set_jaccard(left, right),
            )
            for left, right in pairs
        ),
    )


def _validate_period_order(
    development_period: ValidationPeriod,
    validation_period: ValidationPeriod,
    holdout_period: ValidationPeriod,
) -> None:
    if development_period.end_date >= validation_period.start_date:
        raise OutOfSampleValidationError(
            "DEVELOPMENT period must end before VALIDATION period starts; boundaries are inclusive."
        )
    if validation_period.end_date >= holdout_period.start_date:
        raise OutOfSampleValidationError(
            "VALIDATION period must end before HOLDOUT period starts; boundaries are inclusive."
        )


def _safe_failure(replay_date: date, exc: Exception) -> WalkForwardReplayFailure:
    message = str(exc) or exc.__class__.__name__
    return WalkForwardReplayFailure(
        requested_replay_date=replay_date,
        error_type=exc.__class__.__name__,
        safe_message=message.splitlines()[0],
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


def _loader_call_count(price_loader) -> int | None:
    calls = getattr(price_loader, "calls", None)
    if calls is None:
        return None
    return len(calls)


def _outcome_count_delta(
    left: ReplayOutcomeDistribution,
    right: ReplayOutcomeDistribution,
) -> tuple[int, int, int, int]:
    return (
        right.post_replay_hit_count - left.post_replay_hit_count,
        right.post_replay_miss_count - left.post_replay_miss_count,
        right.post_replay_incomplete_count - left.post_replay_incomplete_count,
        right.post_replay_not_evaluable_count - left.post_replay_not_evaluable_count,
    )


def _candidate_set_jaccard(
    left: OutOfSamplePeriodResult,
    right: OutOfSamplePeriodResult,
) -> float:
    left_symbols = {
        occurrence.symbol
        for occurrence in left.replay_analytics.candidate_occurrences
    }
    right_symbols = {
        occurrence.symbol
        for occurrence in right.replay_analytics.candidate_occurrences
    }
    union_count = len(left_symbols | right_symbols)
    if union_count == 0:
        return 1.0
    return len(left_symbols & right_symbols) / union_count


def _stable_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_stable_value(item) for item in value]
    if isinstance(value, list):
        return [_stable_value(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            field_name: _stable_value(getattr(value, field_name))
            for field_name in value.__dataclass_fields__
            if field_name != "generated_at"
        }
    return value
