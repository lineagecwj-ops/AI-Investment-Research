from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from enum import Enum
import hashlib
import math

from backtest_service import BacktestConfig
from backtest_service import HistoricalBacktestReport
from backtest_service import run_historical_backtest
from historical_price_service import get_historical_prices
from live_data_store import LiveDataStore
from models import OutcomeDefinition
from models import OverlappingSignalPolicy
from models import SignalDefinition
from models import SignalEvaluationStatus
from models import SignalMatch
from models import TechnicalIndicatorSeries
from models import TechnicalIndicatorSnapshot
from signal_outcome_service import evaluate_signal_conditions
from symbol_utils import normalize_stock_symbol
from technical_indicator_service import build_technical_indicator_series


SWING_RESEARCH_RANK_POLICY_V1 = "swing_research_rank_v1"
LATEST_BAR_PROVISIONAL_LIMITATION = (
    "Latest daily bar may be provisional if the current trading session is not complete."
)


class SampleSizeStatus(Enum):

    NO_RESOLVED_SAMPLES = "NO_RESOLVED_SAMPLES"
    BELOW_PREFERRED_MINIMUM = "BELOW_PREFERRED_MINIMUM"
    MEETS_PREFERRED_MINIMUM = "MEETS_PREFERRED_MINIMUM"


@dataclass(frozen=True)
class SwingScannerConfig:

    signal_definition: SignalDefinition

    outcome_definition: OutcomeDefinition

    overlap_policy: OverlappingSignalPolicy = OverlappingSignalPolicy.ALLOW_ALL

    cooldown_bars: int | None = None

    backtest_start_date: date | None = None

    backtest_end_date: date | None = None

    minimum_resolved_samples: int = 20

    force_refresh: bool = False

    def __post_init__(self):
        if self.minimum_resolved_samples < 0:
            raise ValueError("minimum_resolved_samples cannot be negative.")
        if (
            self.backtest_start_date is not None
            and self.backtest_end_date is not None
            and self.backtest_start_date > self.backtest_end_date
        ):
            raise ValueError("backtest_start_date cannot be after backtest_end_date.")
        if self.overlap_policy is OverlappingSignalPolicy.COOLDOWN:
            if self.cooldown_bars is None or self.cooldown_bars <= 0:
                raise ValueError("COOLDOWN policy requires a positive cooldown_bars value.")
        elif self.overlap_policy is OverlappingSignalPolicy.ALLOW_ALL:
            if self.cooldown_bars is not None:
                raise ValueError("ALLOW_ALL policy does not accept cooldown_bars.")
        else:
            raise ValueError(f"Unsupported overlap policy: {self.overlap_policy}")

    @property
    def scanner_config_id(self) -> str:
        identity = "|".join(
            (
                self.signal_definition.id,
                self.outcome_definition.id,
                self.overlap_policy.value,
                "" if self.cooldown_bars is None else str(self.cooldown_bars),
                "" if self.backtest_start_date is None else self.backtest_start_date.isoformat(),
                "" if self.backtest_end_date is None else self.backtest_end_date.isoformat(),
                str(self.minimum_resolved_samples),
            )
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        return f"swing_scanner_{digest}"

    def to_backtest_config(self) -> BacktestConfig:
        return BacktestConfig(
            signal_definition=self.signal_definition,
            outcome_definition=self.outcome_definition,
            overlap_policy=self.overlap_policy,
            cooldown_bars=self.cooldown_bars,
            start_date=self.backtest_start_date,
            end_date=self.backtest_end_date,
        )


@dataclass(frozen=True)
class RankComponent:

    name: str

    source_metric: str

    value: object


@dataclass(frozen=True)
class SwingScanFailure:

    symbol: str

    error_type: str

    message: str


@dataclass(frozen=True)
class SwingScanCurrentSignalAudit:

    symbol: str

    status: SignalEvaluationStatus

    missing_required_features: tuple[str, ...] = tuple()

    failed_conditions: tuple[str, ...] = tuple()


@dataclass(frozen=True)
class SwingOpportunityCandidate:

    symbol: str

    signal_id: str

    latest_trading_date: date

    current_snapshot: TechnicalIndicatorSnapshot

    signal_match: SignalMatch

    historical_backtest_report: HistoricalBacktestReport

    sample_size_status: SampleSizeStatus

    historical_hit_rate: float | None

    resolved_count: int

    hit_count: int

    miss_count: int

    incomplete_count: int

    not_evaluable_count: int

    raw_signal_count: int

    filtered_signal_count: int

    median_max_close_return: float | None

    median_max_adverse_return: float | None

    median_end_return: float | None

    median_hit_bar_index: float | None

    average_max_close_return: float | None

    average_max_adverse_return: float | None

    average_end_return: float | None

    average_hit_bar_index: float | None

    source_price_fetched_at: datetime

    source_price_is_stale: bool

    is_provisional_possible: bool

    overlap_policy: OverlappingSignalPolicy

    cooldown_bars: int | None

    backtest_start_date: date | None

    backtest_end_date: date | None

    research_rank_policy: str

    research_rank: int | None = None

    rank_components: tuple[RankComponent, ...] = tuple()

    limitations: tuple[str, ...] = tuple()


@dataclass(frozen=True)
class SwingScannerResult:

    config: SwingScannerConfig

    requested_symbols: tuple[str, ...]

    normalized_symbols: tuple[str, ...]

    matched_candidates: tuple[SwingOpportunityCandidate, ...]

    no_match_symbols: tuple[str, ...]

    no_match_details: tuple[SwingScanCurrentSignalAudit, ...]

    not_evaluable_symbols: tuple[SwingScanCurrentSignalAudit, ...]

    failed_symbols: tuple[SwingScanFailure, ...]

    generated_at: datetime

    current_signal_details: tuple[SignalMatch, ...] = tuple()

    limitations: tuple[str, ...] = (LATEST_BAR_PROVISIONAL_LIMITATION,)

    @property
    def requested_count(self) -> int:
        return len(self.requested_symbols)

    @property
    def scanned_count(self) -> int:
        return len(self.normalized_symbols)

    @property
    def matched_count(self) -> int:
        return len(self.matched_candidates)

    @property
    def no_match_count(self) -> int:
        return len(self.no_match_symbols)

    @property
    def not_evaluable_count(self) -> int:
        return len(self.not_evaluable_symbols)

    @property
    def failure_count(self) -> int:
        return len(self.failed_symbols)


class SwingScannerService:

    def __init__(
        self,
        *,
        live_data_store: LiveDataStore | None = None,
        price_loader=None,
        technical_builder=build_technical_indicator_series,
        backtest_runner=run_historical_backtest,
    ):
        self.live_data_store = live_data_store or LiveDataStore()
        self.price_loader = price_loader or live_data_store_price_loader(self.live_data_store)
        self.technical_builder = technical_builder
        self.backtest_runner = backtest_runner

    def scan(
        self,
        symbols,
        config: SwingScannerConfig,
    ) -> SwingScannerResult:
        requested_symbols = tuple(symbols)
        normalized_symbols = _normalize_unique_symbols(requested_symbols)
        candidates = []
        no_match_symbols = []
        no_match_details = []
        not_evaluable_symbols = []
        failed_symbols = []
        current_signal_details = []

        for symbol in normalized_symbols:
            try:
                if not symbol:
                    raise ValueError("Symbol is empty after normalization.")
                scan_result = self._scan_symbol(symbol, config)
            except Exception as exc:
                failed_symbols.append(_safe_failure(symbol, exc))
                continue

            signal_match = scan_result.signal_match
            if signal_match.status is SignalEvaluationStatus.MATCH:
                candidates.append(scan_result.candidate)
                current_signal_details.append(signal_match)
            elif signal_match.status is SignalEvaluationStatus.NO_MATCH:
                no_match_symbols.append(symbol)
                current_signal_details.append(signal_match)
                no_match_details.append(
                    _current_signal_audit(symbol, signal_match, config.signal_definition)
                )
            elif signal_match.status is SignalEvaluationStatus.NOT_EVALUABLE:
                not_evaluable_symbols.append(
                    _current_signal_audit(symbol, signal_match, config.signal_definition)
                )
            else:
                failed_symbols.append(
                    SwingScanFailure(
                        symbol=symbol,
                        error_type="UnsupportedSignalStatus",
                        message=f"Unsupported signal status: {signal_match.status}",
                    )
                )

        ranked_candidates = rank_swing_candidates(tuple(candidates))
        return SwingScannerResult(
            config=config,
            requested_symbols=requested_symbols,
            normalized_symbols=normalized_symbols,
            matched_candidates=ranked_candidates,
            no_match_symbols=tuple(no_match_symbols),
            no_match_details=tuple(no_match_details),
            not_evaluable_symbols=tuple(not_evaluable_symbols),
            failed_symbols=tuple(failed_symbols),
            generated_at=datetime.now(UTC),
            current_signal_details=tuple(current_signal_details),
        )

    def _scan_symbol(self, symbol: str, config: SwingScannerConfig):
        price_series = self.price_loader(
            symbol,
            force_refresh=config.force_refresh,
        )
        technical_series = self.technical_builder(price_series)
        if not technical_series.snapshots:
            return _SymbolScanResult(
                signal_match=_empty_not_evaluable_match(symbol, config.signal_definition),
                candidate=None,
            )

        latest_snapshot = technical_series.snapshots[-1]
        signal_match = evaluate_signal_conditions(latest_snapshot, config.signal_definition)
        if signal_match.status is not SignalEvaluationStatus.MATCH:
            return _SymbolScanResult(signal_match=signal_match, candidate=None)

        report = self.backtest_runner(
            price_series,
            technical_series,
            config.to_backtest_config(),
        )
        return _SymbolScanResult(
            signal_match=signal_match,
            candidate=build_swing_candidate(
                signal_match=signal_match,
                technical_series=technical_series,
                report=report,
                config=config,
            ),
        )


@dataclass(frozen=True)
class _SymbolScanResult:

    signal_match: SignalMatch

    candidate: SwingOpportunityCandidate | None


def scan_swing_opportunities(symbols, config: SwingScannerConfig) -> SwingScannerResult:
    return SwingScannerService().scan(symbols, config)


def live_data_store_price_loader(live_data_store: LiveDataStore):
    def load_price_series(symbol: str, *, force_refresh: bool = False):
        return get_historical_prices(
            symbol,
            force_refresh=force_refresh,
            live_store=live_data_store,
        )

    return load_price_series


def build_swing_candidate(
    *,
    signal_match: SignalMatch,
    technical_series: TechnicalIndicatorSeries,
    report: HistoricalBacktestReport,
    config: SwingScannerConfig,
) -> SwingOpportunityCandidate:
    sample_status = get_sample_size_status(
        report.resolved_count,
        config.minimum_resolved_samples,
    )
    limitations = _candidate_limitations(
        sample_status=sample_status,
        minimum_resolved_samples=config.minimum_resolved_samples,
        source_price_is_stale=technical_series.source_price_is_stale,
        overlap_policy=config.overlap_policy,
    )
    candidate = SwingOpportunityCandidate(
        symbol=signal_match.symbol,
        signal_id=signal_match.signal_id,
        latest_trading_date=signal_match.trading_date,
        current_snapshot=signal_match.feature_snapshot,
        signal_match=signal_match,
        historical_backtest_report=report,
        sample_size_status=sample_status,
        historical_hit_rate=report.historical_hit_rate,
        resolved_count=report.resolved_count,
        hit_count=report.hit_count,
        miss_count=report.miss_count,
        incomplete_count=report.incomplete_count,
        not_evaluable_count=report.not_evaluable_count,
        raw_signal_count=report.raw_signal_count,
        filtered_signal_count=report.filtered_signal_count,
        median_max_close_return=report.median_max_close_return,
        median_max_adverse_return=report.median_max_adverse_return,
        median_end_return=report.median_end_return,
        median_hit_bar_index=report.median_hit_bar_index,
        average_max_close_return=report.average_max_close_return,
        average_max_adverse_return=report.average_max_adverse_return,
        average_end_return=report.average_end_return,
        average_hit_bar_index=report.average_hit_bar_index,
        source_price_fetched_at=technical_series.source_price_fetched_at,
        source_price_is_stale=technical_series.source_price_is_stale,
        is_provisional_possible=True,
        overlap_policy=config.overlap_policy,
        cooldown_bars=config.cooldown_bars,
        backtest_start_date=config.backtest_start_date,
        backtest_end_date=config.backtest_end_date,
        research_rank_policy=SWING_RESEARCH_RANK_POLICY_V1,
        rank_components=tuple(),
        limitations=limitations,
    )
    return replace(candidate, rank_components=get_candidate_rank_components(candidate))


def rank_swing_candidates(
    candidates: tuple[SwingOpportunityCandidate, ...],
) -> tuple[SwingOpportunityCandidate, ...]:
    sorted_candidates = tuple(sorted(candidates, key=_rank_key))
    return tuple(
        replace(
            candidate,
            research_rank=index,
            rank_components=get_candidate_rank_components(candidate),
        )
        for index, candidate in enumerate(sorted_candidates, start=1)
    )


def get_candidate_rank_components(
    candidate: SwingOpportunityCandidate,
) -> tuple[RankComponent, ...]:
    return (
        RankComponent("sample_size_status", "sample_size_status", candidate.sample_size_status.value),
        RankComponent("historical_hit_rate", "historical_hit_rate", candidate.historical_hit_rate),
        RankComponent("resolved_count", "resolved_count", candidate.resolved_count),
        RankComponent("median_max_adverse_return", "median_max_adverse_return", candidate.median_max_adverse_return),
        RankComponent("median_max_close_return", "median_max_close_return", candidate.median_max_close_return),
        RankComponent("median_end_return", "median_end_return", candidate.median_end_return),
        RankComponent("symbol", "symbol", candidate.symbol),
    )


def get_sample_size_status(
    resolved_count: int,
    minimum_resolved_samples: int,
) -> SampleSizeStatus:
    if resolved_count <= 0:
        return SampleSizeStatus.NO_RESOLVED_SAMPLES
    if resolved_count < minimum_resolved_samples:
        return SampleSizeStatus.BELOW_PREFERRED_MINIMUM
    return SampleSizeStatus.MEETS_PREFERRED_MINIMUM


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


def _rank_key(candidate: SwingOpportunityCandidate):
    return (
        _sample_status_rank(candidate.sample_size_status),
        _descending_optional(candidate.historical_hit_rate),
        -candidate.resolved_count,
        _descending_optional(candidate.median_max_adverse_return),
        _descending_optional(candidate.median_max_close_return),
        _descending_optional(candidate.median_end_return),
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


def _candidate_limitations(
    *,
    sample_status: SampleSizeStatus,
    minimum_resolved_samples: int,
    source_price_is_stale: bool,
    overlap_policy: OverlappingSignalPolicy,
) -> tuple[str, ...]:
    limitations = [LATEST_BAR_PROVISIONAL_LIMITATION]
    if sample_status is SampleSizeStatus.NO_RESOLVED_SAMPLES:
        limitations.append("Historical resolved sample size is zero for this configuration.")
    elif sample_status is SampleSizeStatus.BELOW_PREFERRED_MINIMUM:
        limitations.append(
            "Historical resolved sample size is below the configured preferred minimum "
            f"of {minimum_resolved_samples}."
        )
    if source_price_is_stale:
        limitations.append("Current signal was evaluated from stale cached historical price data.")
    if overlap_policy is OverlappingSignalPolicy.ALLOW_ALL:
        limitations.append(
            "Historical events may overlap and are not statistically independent."
        )
    elif overlap_policy is OverlappingSignalPolicy.COOLDOWN:
        limitations.append(
            "Cooldown reduces nearby repeated signals but does not guarantee statistical independence."
        )
    return tuple(limitations)


def _current_signal_audit(
    symbol: str,
    signal_match: SignalMatch,
    signal_definition: SignalDefinition,
) -> SwingScanCurrentSignalAudit:
    missing_required = tuple(
        metric
        for metric in signal_definition.minimum_required_features
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
    return SwingScanCurrentSignalAudit(
        symbol=symbol,
        status=signal_match.status,
        missing_required_features=missing_required or not_evaluable_conditions,
        failed_conditions=failed_conditions,
    )


def _empty_not_evaluable_match(
    symbol: str,
    signal_definition: SignalDefinition,
) -> SignalMatch:
    snapshot = TechnicalIndicatorSnapshot(
        symbol=symbol,
        trading_date=date.min,
        analysis_close=0.0,
        sma_5=None,
        sma_10=None,
        sma_20=None,
        sma_60=None,
        sma_120=None,
        sma_200=None,
        ema_12=None,
        ema_26=None,
        rsi_14=None,
        macd=None,
        macd_signal=None,
        macd_histogram=None,
        atr_14=None,
        atr_14_pct=None,
        volume_sma_20=None,
        volume_ratio_20=None,
        return_5d=None,
        return_20d=None,
        return_60d=None,
        return_volatility_20d=None,
        high_20d=None,
        high_60d=None,
        high_252d=None,
        low_20d=None,
        low_60d=None,
        prior_high_20d=None,
        prior_high_60d=None,
        prior_high_252d=None,
        prior_low_20d=None,
        prior_low_60d=None,
        distance_to_prior_20d_high=None,
        distance_to_prior_60d_high=None,
        distance_to_prior_52_week_high=None,
        is_above_prior_20d_high=None,
        is_above_prior_60d_high=None,
        is_above_prior_52_week_high=None,
        close_above_sma20=None,
        close_above_sma60=None,
        sma20_above_sma60=None,
        sma60_above_sma120=None,
        sma20_change_5d=None,
        sma60_change_5d=None,
        position_in_prior_60d_range=None,
    )
    return SignalMatch(
        symbol=symbol,
        trading_date=snapshot.trading_date,
        signal_id=signal_definition.id,
        status=SignalEvaluationStatus.NOT_EVALUABLE,
        matched=False,
        evaluated_conditions=tuple(),
        feature_snapshot=snapshot,
    )


def _safe_failure(symbol: str, exc: Exception) -> SwingScanFailure:
    message = str(exc) or exc.__class__.__name__
    return SwingScanFailure(
        symbol=symbol,
        error_type=exc.__class__.__name__,
        message=message.splitlines()[0],
    )


def _is_usable_value(value) -> bool:
    if isinstance(value, bool):
        return True
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))
