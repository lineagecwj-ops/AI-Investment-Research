from dataclasses import dataclass
from datetime import date
from datetime import datetime
from enum import Enum


@dataclass
class Stock:

    symbol: str | None = None

    company_name: str | None = None

    currency: str | None = None

    current_price: float | None = None

    market_cap: int | None = None

    trailing_pe: float | None = None

    forward_pe: float | None = None

    trailing_eps: float | None = None

    return_on_equity: float | None = None

    company_summary: str | None = None

    gross_margin: float | None = None

    operating_margin: float | None = None

    net_margin: float | None = None

    revenue_growth: float | None = None

    earnings_growth: float | None = None

    total_cash: int | None = None

    total_debt: int | None = None

    debt_to_equity: float | None = None

    operating_cash_flow: int | None = None

    free_cash_flow: int | None = None

    price_to_book: float | None = None

    fifty_two_week_high: float | None = None

    fifty_two_week_low: float | None = None

    fifty_day_average: float | None = None

    two_hundred_day_average: float | None = None

    sector: str | None = None

    industry: str | None = None


@dataclass
class HistoricalFinancialPeriod:

    symbol: str

    period_end: date

    period_year: int | None = None

    currency: str | None = None

    revenue: float | None = None

    gross_profit: float | None = None

    operating_income: float | None = None

    net_income: float | None = None

    eps: float | None = None

    gross_margin: float | None = None

    operating_margin: float | None = None

    net_margin: float | None = None

    operating_cash_flow: float | None = None

    capital_expenditure: float | None = None

    free_cash_flow: float | None = None

    total_assets: float | None = None

    total_debt: float | None = None

    total_equity: float | None = None

    cash_and_cash_equivalents: float | None = None


@dataclass
class HistoricalFinancialSeries:

    symbol: str

    currency: str | None = None

    periods: list[HistoricalFinancialPeriod] | None = None

    fetched_at: datetime | None = None

    is_stale: bool = False

    def __post_init__(self):
        if self.periods is None:
            self.periods = []


@dataclass(frozen=True)
class HistoricalPriceBar:

    symbol: str

    trading_date: date

    open: float | None

    high: float

    low: float

    close: float

    adjusted_close: float | None

    volume: int | None

    dividends: float | None = None

    stock_splits: float | None = None


@dataclass(frozen=True)
class HistoricalPriceSeries:

    symbol: str

    currency: str | None

    bars: tuple[HistoricalPriceBar, ...]

    fetched_at: datetime

    is_stale: bool = False

    source: str = "Yahoo Finance"


@dataclass(frozen=True)
class ResearchUniverse:

    id: str

    name: str

    symbols: tuple[str, ...]

    created_at: datetime

    updated_at: datetime

    description: str | None = None

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)


@dataclass(frozen=True)
class TechnicalIndicatorSnapshot:

    symbol: str

    trading_date: date

    analysis_close: float

    sma_5: float | None
    sma_10: float | None
    sma_20: float | None
    sma_60: float | None
    sma_120: float | None
    sma_200: float | None

    ema_12: float | None
    ema_26: float | None

    rsi_14: float | None

    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None

    atr_14: float | None
    atr_14_pct: float | None

    volume_sma_20: float | None
    volume_ratio_20: float | None

    return_5d: float | None
    return_20d: float | None
    return_60d: float | None
    return_volatility_20d: float | None

    high_20d: float | None
    high_60d: float | None
    high_252d: float | None
    low_20d: float | None
    low_60d: float | None

    prior_high_20d: float | None
    prior_high_60d: float | None
    prior_high_252d: float | None
    prior_low_20d: float | None
    prior_low_60d: float | None

    distance_to_prior_20d_high: float | None
    distance_to_prior_60d_high: float | None
    distance_to_prior_52_week_high: float | None

    is_above_prior_20d_high: bool | None
    is_above_prior_60d_high: bool | None
    is_above_prior_52_week_high: bool | None

    close_above_sma20: bool | None
    close_above_sma60: bool | None
    sma20_above_sma60: bool | None
    sma60_above_sma120: bool | None

    sma20_change_5d: float | None
    sma60_change_5d: float | None

    position_in_prior_60d_range: float | None


@dataclass(frozen=True)
class TechnicalIndicatorSeries:

    symbol: str

    snapshots: tuple[TechnicalIndicatorSnapshot, ...]

    generated_at: datetime

    source_price_fetched_at: datetime

    source_price_is_stale: bool = False


class SignalConditionOperator(Enum):

    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    EQUAL = "=="
    BETWEEN = "between"


class SignalEvaluationStatus(Enum):

    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class OverlappingSignalPolicy(Enum):

    ALLOW_ALL = "ALLOW_ALL"
    COOLDOWN = "COOLDOWN"


class OutcomeType(Enum):

    RAW_HIGH_BREAKOUT = "RAW_HIGH_BREAKOUT"
    CLOSE_RETURN_TARGET = "CLOSE_RETURN_TARGET"


class OutcomeEvaluationStatus(Enum):

    HIT = "HIT"
    MISS = "MISS"
    INCOMPLETE = "INCOMPLETE"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True)
class TechnicalSignalCondition:

    metric: str

    operator: SignalConditionOperator

    value: float | bool | tuple[float, float] | None = None

    secondary_metric: str | None = None


@dataclass(frozen=True)
class EvaluatedSignalCondition:

    metric: str

    actual_value: float | bool | None

    operator: SignalConditionOperator

    expected_value: float | bool | tuple[float, float] | None

    secondary_metric: str | None

    secondary_actual_value: float | bool | None

    status: SignalEvaluationStatus

    matched: bool | None


@dataclass(frozen=True)
class SignalDefinition:

    id: str

    name: str

    conditions: tuple[TechnicalSignalCondition, ...]

    minimum_required_features: tuple[str, ...]

    description: str


@dataclass(frozen=True)
class SignalMatch:

    symbol: str

    trading_date: date

    signal_id: str

    status: SignalEvaluationStatus

    matched: bool

    evaluated_conditions: tuple[EvaluatedSignalCondition, ...]

    feature_snapshot: TechnicalIndicatorSnapshot


@dataclass(frozen=True)
class SignalEvent:

    symbol: str

    signal_id: str

    signal_date: date

    signal_analysis_close: float

    signal_raw_close: float | None

    reference_high: float | None

    reference_low: float | None

    evaluation_status: SignalEvaluationStatus

    feature_snapshot: TechnicalIndicatorSnapshot

    evaluated_conditions: tuple[EvaluatedSignalCondition, ...]


@dataclass(frozen=True)
class SignalEvaluationAudit:

    signal_id: str

    evaluated_snapshots: int

    matched: int

    not_matched: int

    not_evaluable: int


@dataclass(frozen=True)
class OutcomeDefinition:

    id: str

    outcome_type: OutcomeType

    horizon_bars: int = 20

    reference_metric: str | None = None

    target_return: float | None = None

    description: str = ""


@dataclass(frozen=True)
class HistoricalOutcomeResult:

    symbol: str

    signal_id: str

    signal_date: date

    outcome_definition_id: str

    status: OutcomeEvaluationStatus

    horizon_bars: int

    available_future_bars: int

    reference_high: float | None

    intraday_target_hit: bool

    intraday_target_hit_date: date | None

    intraday_target_hit_bar_index: int | None

    close_target_hit: bool

    close_target_hit_date: date | None

    close_target_hit_bar_index: int | None

    max_close_return: float | None

    max_close_return_date: date | None

    max_adverse_return: float | None

    max_adverse_return_date: date | None

    end_of_window_return: float | None
