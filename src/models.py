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

    fiscal_year: int | None = None

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
