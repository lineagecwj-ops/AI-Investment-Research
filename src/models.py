from dataclasses import dataclass
from datetime import date
from datetime import datetime


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
