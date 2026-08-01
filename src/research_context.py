from dataclasses import dataclass
from dataclasses import fields
from dataclasses import is_dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
import math
from numbers import Real
from typing import Any

from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from models import Stock
from research_metrics import calculate_eps_yoy_growth
from research_metrics import calculate_yoy_growth
from research_service import ResearchNextStep
from research_service import ResearchObservation
from research_service import ResearchReport
from historical_research_service import HistoricalResearchReport


class ResearchContextError(Exception):
    """Raised when Research Context inputs or output are inconsistent."""


@dataclass(frozen=True)
class CompanyContext:

    symbol: str | None

    company_name: str | None

    display_name: str | None

    sector: str | None

    industry: str | None

    company_summary: str | None


@dataclass(frozen=True)
class MarketContext:

    current_price: float | None

    currency: str | None

    market_cap: int | None

    fifty_two_week_high: float | None

    fifty_two_week_low: float | None

    fifty_day_average: float | None

    two_hundred_day_average: float | None

    fifty_two_week_position: float | None


@dataclass(frozen=True)
class ProfitabilityContext:

    return_on_equity: float | None

    gross_margin: float | None

    operating_margin: float | None

    net_margin: float | None

    trailing_eps: float | None


@dataclass(frozen=True)
class GrowthContext:

    revenue_growth: float | None

    earnings_growth: float | None


@dataclass(frozen=True)
class FinancialHealthContext:

    total_cash: int | None

    total_debt: int | None

    debt_to_equity: float | None

    operating_cash_flow: int | None

    free_cash_flow: int | None


@dataclass(frozen=True)
class ValuationContext:

    trailing_pe: float | None

    forward_pe: float | None

    price_to_book: float | None


@dataclass(frozen=True)
class CurrentSnapshotContext:

    company: CompanyContext

    market: MarketContext

    profitability: ProfitabilityContext

    growth: GrowthContext

    financial_health: FinancialHealthContext

    valuation: ValuationContext


@dataclass(frozen=True)
class FundamentalResearchContext:

    market_position_note: str

    valuation_observations: list[ResearchObservation]

    risk_signals: list[ResearchObservation]

    next_steps: list[ResearchNextStep]

    missing_critical_fields: list[str]


@dataclass(frozen=True)
class HistoricalPeriodContext:

    period_end: date

    period_year: int | None

    currency: str | None

    revenue: float | None

    gross_profit: float | None

    operating_income: float | None

    net_income: float | None

    eps: float | None

    gross_margin: float | None

    operating_margin: float | None

    net_margin: float | None

    operating_cash_flow: float | None

    capital_expenditure: float | None

    free_cash_flow: float | None

    total_assets: float | None

    total_debt: float | None

    total_equity: float | None

    cash_and_cash_equivalents: float | None


@dataclass(frozen=True)
class HistoricalFinancialsContext:

    symbol: str

    currency: str | None

    fetched_at: datetime | None

    is_stale: bool

    periods: list[HistoricalPeriodContext]


@dataclass(frozen=True)
class HistoricalResearchContext:

    observations: list[ResearchObservation]

    next_steps: list[ResearchNextStep]


@dataclass(frozen=True)
class EvidenceItem:

    id: str

    category: str

    metric: str

    value: int | float | str | None

    unit: str | None

    currency: str | None

    period_end: date | None

    period_year: int | None

    source: str

    source_type: str

    derived_from: tuple[str, ...] = ()

    note: str | None = None


@dataclass(frozen=True)
class MissingDataItem:

    id: str

    area: str

    metric: str

    period_end: date | None

    period_year: int | None

    reason: str

    impact: str

    source: str | None = None


@dataclass(frozen=True)
class ResearchLimitation:

    id: str

    category: str

    message: str

    scope: str


@dataclass(frozen=True)
class ObservationEvidenceLink:

    id: str

    observation_scope: str

    observation_index: int

    category: str

    metric: str

    evidence_ids: tuple[str, ...] = ()

    missing_data_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchContext:

    symbol: str | None

    display_name: str | None

    currency: str | None

    generated_at: datetime

    current_snapshot: CurrentSnapshotContext

    fundamental_research: FundamentalResearchContext

    historical_financials: HistoricalFinancialsContext | None

    historical_research: HistoricalResearchContext | None

    evidence: list[EvidenceItem]

    observation_links: list[ObservationEvidenceLink]

    limitations: list[ResearchLimitation]

    missing_data: list[MissingDataItem]

    def to_dict(self) -> dict[str, Any]:
        return json_safe_value(self)


CURRENT_EVIDENCE_FIELDS = [
    "current_price",
    "market_cap",
    "trailing_pe",
    "forward_pe",
    "trailing_eps",
    "return_on_equity",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "revenue_growth",
    "earnings_growth",
    "total_cash",
    "total_debt",
    "debt_to_equity",
    "operating_cash_flow",
    "free_cash_flow",
    "price_to_book",
    "fifty_two_week_high",
    "fifty_two_week_low",
    "fifty_day_average",
    "two_hundred_day_average",
    "sector",
    "industry",
]


CURRENT_CONTEXT_FIELDS = [
    "symbol",
    "company_name",
    "currency",
    "company_summary",
    *CURRENT_EVIDENCE_FIELDS,
]


HISTORICAL_PERIOD_FIELDS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "total_assets",
    "total_debt",
    "total_equity",
    "cash_and_cash_equivalents",
]


PERCENT_METRICS = {
    "return_on_equity",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "revenue_growth",
    "earnings_growth",
    "debt_to_equity",
    "fifty_two_week_position",
    "revenue_yoy",
    "eps_yoy",
}


MONETARY_METRICS = {
    "current_price",
    "market_cap",
    "total_cash",
    "total_debt",
    "operating_cash_flow",
    "free_cash_flow",
    "fifty_two_week_high",
    "fifty_two_week_low",
    "fifty_day_average",
    "two_hundred_day_average",
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "capital_expenditure",
    "total_assets",
    "total_equity",
    "cash_and_cash_equivalents",
}


RATIO_METRICS = {
    "trailing_pe",
    "forward_pe",
    "price_to_book",
}


TEXT_METRICS = {
    "sector",
    "industry",
}


CURRENT_MISSING_IMPACTS = {
    "current_price": "Current price context and 52-week position cannot be fully evaluated.",
    "market_cap": "Company size context is incomplete.",
    "trailing_pe": "Trailing valuation comparison is incomplete.",
    "forward_pe": "Forward valuation comparison is incomplete.",
    "trailing_eps": "Current EPS context is incomplete.",
    "return_on_equity": "Profitability efficiency context is incomplete.",
    "gross_margin": "Gross margin context is incomplete.",
    "operating_margin": "Operating margin context is incomplete.",
    "net_margin": "Net margin context is incomplete.",
    "revenue_growth": "Current revenue growth observation cannot be evaluated.",
    "earnings_growth": "Current earnings growth observation cannot be evaluated.",
    "total_cash": "Cash versus debt context is incomplete.",
    "total_debt": "Cash versus debt context is incomplete.",
    "debt_to_equity": "Leverage context is incomplete.",
    "operating_cash_flow": "Operating cash flow context is incomplete.",
    "free_cash_flow": "Free cash flow context is incomplete.",
    "price_to_book": "Price-to-book valuation context is incomplete.",
    "fifty_two_week_high": "52-week position cannot be calculated.",
    "fifty_two_week_low": "52-week position cannot be calculated.",
    "fifty_day_average": "Shorter moving-average price context is incomplete.",
    "two_hundred_day_average": "Longer moving-average price context is incomplete.",
    "sector": "Sector comparison context is incomplete.",
    "industry": "Industry comparison context is incomplete.",
    "symbol": "Context identity is incomplete.",
    "company_name": "Company identity context is incomplete.",
    "currency": "Currency context is incomplete.",
    "company_summary": "Company overview context is incomplete.",
}


HISTORICAL_MISSING_IMPACTS = {
    "revenue": "Revenue trend and Revenue YoY cannot be calculated for this period.",
    "gross_profit": "Gross profit context is incomplete for this period.",
    "operating_income": "Operating income context is incomplete for this period.",
    "net_income": "Net income trend context is incomplete for this period.",
    "eps": "EPS YoY cannot be calculated for this period.",
    "gross_margin": "Gross margin trend context is incomplete for this period.",
    "operating_margin": "Operating margin trend context is incomplete for this period.",
    "net_margin": "Net margin trend context is incomplete for this period.",
    "operating_cash_flow": "Operating cash flow trend context is incomplete for this period.",
    "capital_expenditure": "Capital expenditure context is incomplete for this period.",
    "free_cash_flow": "Free cash flow trend context is incomplete for this period.",
    "total_assets": "Total assets context is incomplete for this period.",
    "total_debt": "Total debt context is incomplete for this period.",
    "total_equity": "Total equity context is incomplete for this period.",
    "cash_and_cash_equivalents": "Cash context is incomplete for this period.",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def build_research_context(
    *,
    stock: Stock,
    research_report: ResearchReport,
    historical_series: HistoricalFinancialSeries | None = None,
    historical_research_report: HistoricalResearchReport | None = None,
    display_name: str | None = None,
    generated_at: datetime | None = None,
) -> ResearchContext:
    resolved_generated_at = generated_at or utc_now()
    resolved_display_name = display_name or stock.company_name or stock.symbol
    validate_input_consistency(stock, research_report, historical_series, historical_research_report)

    current_snapshot = build_current_snapshot_context(
        stock,
        research_report,
        resolved_display_name,
    )
    historical_financials = (
        build_historical_financials_context(historical_series)
        if historical_series is not None
        else None
    )
    historical_research = (
        build_historical_research_context(historical_research_report)
        if historical_research_report is not None
        else None
    )
    missing_data = build_missing_data_items(stock, historical_series)
    evidence = build_evidence_items(stock, research_report, historical_series)
    limitations = build_limitations(research_report, historical_series)
    observation_links = build_observation_links(
        research_report,
        historical_research_report,
        evidence,
        missing_data,
    )

    context = ResearchContext(
        symbol=stock.symbol,
        display_name=resolved_display_name,
        currency=stock.currency,
        generated_at=resolved_generated_at,
        current_snapshot=current_snapshot,
        fundamental_research=build_fundamental_research_context(research_report),
        historical_financials=historical_financials,
        historical_research=historical_research,
        evidence=evidence,
        observation_links=observation_links,
        limitations=limitations,
        missing_data=missing_data,
    )
    validate_research_context(context)
    return context


def validate_input_consistency(
    stock: Stock,
    research_report: ResearchReport,
    historical_series: HistoricalFinancialSeries | None,
    historical_research_report: HistoricalResearchReport | None,
) -> None:
    stock_symbol = normalized_symbol(stock.symbol)
    report_symbol = normalized_symbol(research_report.stock.symbol)

    if stock_symbol != report_symbol:
        raise ResearchContextError(
            f"Stock symbol mismatch: stock={stock.symbol}, research_report={research_report.stock.symbol}"
        )

    if historical_series is not None and normalized_symbol(historical_series.symbol) != stock_symbol:
        raise ResearchContextError(
            f"Historical series symbol mismatch: stock={stock.symbol}, historical_series={historical_series.symbol}"
        )

    if historical_research_report is not None:
        report_series_symbol = normalized_symbol(historical_research_report.series.symbol)
        if report_series_symbol != stock_symbol:
            raise ResearchContextError(
                "Historical research report symbol mismatch: "
                f"stock={stock.symbol}, historical_report={historical_research_report.series.symbol}"
            )
        if historical_series is not None and report_series_symbol != normalized_symbol(historical_series.symbol):
            raise ResearchContextError(
                "Historical report and historical series symbols do not match: "
                f"historical_report={historical_research_report.series.symbol}, "
                f"historical_series={historical_series.symbol}"
            )


def normalized_symbol(symbol: str | None) -> str | None:
    return symbol.upper() if symbol else None


def build_current_snapshot_context(
    stock: Stock,
    research_report: ResearchReport,
    display_name: str | None,
) -> CurrentSnapshotContext:
    return CurrentSnapshotContext(
        company=CompanyContext(
            symbol=stock.symbol,
            company_name=stock.company_name,
            display_name=display_name,
            sector=stock.sector,
            industry=stock.industry,
            company_summary=stock.company_summary,
        ),
        market=MarketContext(
            current_price=stock.current_price,
            currency=stock.currency,
            market_cap=stock.market_cap,
            fifty_two_week_high=stock.fifty_two_week_high,
            fifty_two_week_low=stock.fifty_two_week_low,
            fifty_day_average=stock.fifty_day_average,
            two_hundred_day_average=stock.two_hundred_day_average,
            fifty_two_week_position=research_report.fifty_two_week_position,
        ),
        profitability=ProfitabilityContext(
            return_on_equity=stock.return_on_equity,
            gross_margin=stock.gross_margin,
            operating_margin=stock.operating_margin,
            net_margin=stock.net_margin,
            trailing_eps=stock.trailing_eps,
        ),
        growth=GrowthContext(
            revenue_growth=stock.revenue_growth,
            earnings_growth=stock.earnings_growth,
        ),
        financial_health=FinancialHealthContext(
            total_cash=stock.total_cash,
            total_debt=stock.total_debt,
            debt_to_equity=stock.debt_to_equity,
            operating_cash_flow=stock.operating_cash_flow,
            free_cash_flow=stock.free_cash_flow,
        ),
        valuation=ValuationContext(
            trailing_pe=stock.trailing_pe,
            forward_pe=stock.forward_pe,
            price_to_book=stock.price_to_book,
        ),
    )


def build_fundamental_research_context(
    report: ResearchReport,
) -> FundamentalResearchContext:
    return FundamentalResearchContext(
        market_position_note=report.market_position_note,
        valuation_observations=report.valuation_observations,
        risk_signals=report.risk_signals,
        next_steps=report.next_steps,
        missing_critical_fields=report.missing_critical_fields,
    )


def build_historical_financials_context(
    series: HistoricalFinancialSeries,
) -> HistoricalFinancialsContext:
    return HistoricalFinancialsContext(
        symbol=series.symbol,
        currency=series.currency,
        fetched_at=series.fetched_at,
        is_stale=series.is_stale,
        periods=[
            build_historical_period_context(period)
            for period in series.periods or []
        ],
    )


def build_historical_period_context(
    period: HistoricalFinancialPeriod,
) -> HistoricalPeriodContext:
    return HistoricalPeriodContext(
        period_end=period.period_end,
        period_year=period.period_year,
        currency=period.currency,
        revenue=period.revenue,
        gross_profit=period.gross_profit,
        operating_income=period.operating_income,
        net_income=period.net_income,
        eps=period.eps,
        gross_margin=period.gross_margin,
        operating_margin=period.operating_margin,
        net_margin=period.net_margin,
        operating_cash_flow=period.operating_cash_flow,
        capital_expenditure=period.capital_expenditure,
        free_cash_flow=period.free_cash_flow,
        total_assets=period.total_assets,
        total_debt=period.total_debt,
        total_equity=period.total_equity,
        cash_and_cash_equivalents=period.cash_and_cash_equivalents,
    )


def build_historical_research_context(
    report: HistoricalResearchReport,
) -> HistoricalResearchContext:
    return HistoricalResearchContext(
        observations=report.observations,
        next_steps=report.next_steps,
    )


def build_evidence_items(
    stock: Stock,
    research_report: ResearchReport,
    historical_series: HistoricalFinancialSeries | None,
) -> list[EvidenceItem]:
    evidence = []
    evidence.extend(build_current_evidence(stock))
    evidence.extend(build_current_derived_evidence(research_report))
    if historical_series is not None:
        evidence.extend(build_historical_evidence(historical_series))
        evidence.extend(build_historical_derived_evidence(historical_series))
    return evidence


def build_current_evidence(stock: Stock) -> list[EvidenceItem]:
    evidence = []
    for metric in CURRENT_EVIDENCE_FIELDS:
        value = getattr(stock, metric)
        if value is None:
            continue
        evidence.append(
            EvidenceItem(
                id=current_evidence_id(metric),
                category="current_snapshot",
                metric=metric,
                value=value,
                unit=metric_unit(metric),
                currency=stock.currency if metric in MONETARY_METRICS else None,
                period_end=None,
                period_year=None,
                source="Yahoo Finance current snapshot",
                source_type="source",
            )
        )
    return evidence


def build_current_derived_evidence(
    research_report: ResearchReport,
) -> list[EvidenceItem]:
    stock = research_report.stock
    source_ids = (
        current_evidence_id("current_price"),
        current_evidence_id("fifty_two_week_low"),
        current_evidence_id("fifty_two_week_high"),
    )
    if research_report.fifty_two_week_position is None:
        return []
    if not all(getattr(stock, metric) is not None for metric in [
        "current_price",
        "fifty_two_week_low",
        "fifty_two_week_high",
    ]):
        return []

    return [
        EvidenceItem(
            id="derived:52_week_position",
            category="current_derived",
            metric="fifty_two_week_position",
            value=research_report.fifty_two_week_position,
            unit=metric_unit("fifty_two_week_position"),
            currency=None,
            period_end=None,
            period_year=None,
            source="research_metrics.calculate_52_week_position",
            source_type="derived",
            derived_from=source_ids,
        )
    ]


def build_historical_evidence(series: HistoricalFinancialSeries) -> list[EvidenceItem]:
    evidence = []
    for period in series.periods or []:
        for metric in HISTORICAL_PERIOD_FIELDS:
            value = getattr(period, metric)
            if value is None:
                continue
            evidence.append(
                EvidenceItem(
                    id=historical_evidence_id(metric, period.period_end),
                    category="historical_financials",
                    metric=metric,
                    value=value,
                    unit=metric_unit(metric),
                    currency=(period.currency or series.currency) if metric in MONETARY_METRICS else None,
                    period_end=period.period_end,
                    period_year=period.period_year,
                    source="Yahoo Finance annual financial statement",
                    source_type="source",
                    note="Annual historical financial statement value.",
                )
            )
    return evidence


def build_historical_derived_evidence(series: HistoricalFinancialSeries) -> list[EvidenceItem]:
    evidence = []
    evidence.extend(build_historical_yoy_evidence(series, "revenue"))
    evidence.extend(build_historical_yoy_evidence(series, "eps"))
    return evidence


def build_historical_yoy_evidence(
    series: HistoricalFinancialSeries,
    metric: str,
) -> list[EvidenceItem]:
    evidence = []
    previous_period = None
    previous_value = None
    previous_year = None

    for period in series.periods or []:
        current_value = getattr(period, metric)
        if metric == "eps":
            growth = calculate_eps_yoy_growth(
                current_value,
                previous_value,
                period.period_year,
                previous_year,
            )
        else:
            growth = calculate_yoy_growth(
                current_value,
                previous_value,
                period.period_year,
                previous_year,
            )

        if growth is not None and previous_period is not None:
            current_source_id = historical_evidence_id(metric, period.period_end)
            previous_source_id = historical_evidence_id(metric, previous_period.period_end)
            evidence.append(
                EvidenceItem(
                    id=derived_yoy_evidence_id(metric, period.period_end),
                    category="historical_derived",
                    metric=f"{metric}_yoy",
                    value=growth,
                    unit=metric_unit(f"{metric}_yoy"),
                    currency=None,
                    period_end=period.period_end,
                    period_year=period.period_year,
                    source=f"research_metrics.calculate_{metric}_yoy_growth"
                    if metric == "eps"
                    else "research_metrics.calculate_yoy_growth",
                    source_type="derived",
                    derived_from=(previous_source_id, current_source_id),
                )
            )

        previous_period = period
        previous_value = current_value
        previous_year = period.period_year

    return evidence


def build_missing_data_items(
    stock: Stock,
    historical_series: HistoricalFinancialSeries | None,
) -> list[MissingDataItem]:
    missing = []

    for metric in CURRENT_CONTEXT_FIELDS:
        value = getattr(stock, metric)
        if value is None or value == "":
            missing.append(
                MissingDataItem(
                    id=missing_current_id(metric),
                    area="current_snapshot",
                    metric=metric,
                    period_end=None,
                    period_year=None,
                    reason="Yahoo current snapshot value unavailable",
                    impact=CURRENT_MISSING_IMPACTS[metric],
                    source="Yahoo Finance current snapshot",
                )
            )

    if historical_series is None:
        missing.append(
            MissingDataItem(
                id="missing:historical:series",
                area="historical_financials",
                metric="series",
                period_end=None,
                period_year=None,
                reason="Historical financial series was not supplied",
                impact="Historical financial trend evidence and historical observations are unavailable.",
                source=None,
            )
        )
        return missing

    for period in historical_series.periods or []:
        for metric in HISTORICAL_PERIOD_FIELDS:
            if getattr(period, metric) is None:
                missing.append(
                    MissingDataItem(
                        id=missing_historical_id(metric, period.period_end),
                        area="historical_financials",
                        metric=metric,
                        period_end=period.period_end,
                        period_year=period.period_year,
                        reason="Yahoo Finance annual statement value unavailable",
                        impact=HISTORICAL_MISSING_IMPACTS[metric],
                        source="Yahoo Finance annual financial statement",
                    )
                )

    missing.extend(build_missing_yoy_items(historical_series))
    return missing


def build_missing_yoy_items(series: HistoricalFinancialSeries) -> list[MissingDataItem]:
    missing = []
    missing.extend(build_missing_yoy_by_metric(series, "revenue"))
    missing.extend(build_missing_yoy_by_metric(series, "eps"))
    return missing


def build_missing_yoy_by_metric(
    series: HistoricalFinancialSeries,
    metric: str,
) -> list[MissingDataItem]:
    missing = []
    previous_period = None
    previous_value = None
    previous_year = None

    for period in series.periods or []:
        current_value = getattr(period, metric)
        reason = missing_yoy_reason(metric, current_value, previous_value, period.period_year, previous_year)
        if reason is not None and previous_period is not None:
            missing.append(
                MissingDataItem(
                    id=missing_historical_id(f"{metric}_yoy", period.period_end),
                    area="historical_derived",
                    metric=f"{metric}_yoy",
                    period_end=period.period_end,
                    period_year=period.period_year,
                    reason=reason,
                    impact=f"FY{period.period_year} {metric.upper()} YoY cannot be calculated.",
                    source="research_metrics historical YoY semantics",
                )
            )
        previous_period = period
        previous_value = current_value
        previous_year = period.period_year

    return missing


def missing_yoy_reason(
    metric: str,
    current_value: float | None,
    previous_value: float | None,
    current_year: int | None,
    previous_year: int | None,
) -> str | None:
    if previous_year is None:
        return None
    if current_year is None or current_year != previous_year + 1:
        return "Fiscal period years are not consecutive"
    if current_value is None:
        return f"Yahoo Finance annual {metric} value unavailable for current period"
    if previous_value is None:
        return f"Yahoo Finance annual {metric} value unavailable for previous period"
    if metric == "eps" and previous_value <= 0:
        return "EPS YoY calculation is not applicable when previous EPS is less than or equal to zero"
    if metric != "eps" and previous_value == 0:
        return f"{metric.upper()} YoY calculation is not applicable when previous value is zero"
    return None


def build_limitations(
    research_report: ResearchReport,
    historical_series: HistoricalFinancialSeries | None,
) -> list[ResearchLimitation]:
    limitations = [
        ResearchLimitation(
            id="global:annual_historical_data_only",
            category="data_scope",
            message="Historical financial context uses annual financial statement periods only.",
            scope="global",
        ),
        ResearchLimitation(
            id="global:no_quarterly_or_ttm",
            category="data_scope",
            message="Research Context does not include quarterly or trailing-twelve-month historical data.",
            scope="global",
        ),
        ResearchLimitation(
            id="global:no_fx_conversion",
            category="currency",
            message="Research Context preserves provider currency values and does not perform FX conversion.",
            scope="global",
        ),
    ]

    if research_report.missing_critical_fields:
        limitations.append(
            ResearchLimitation(
                id="context:missing_critical_research_fields",
                category="missing_data",
                message=(
                    "Current snapshot is missing critical research fields: "
                    + ", ".join(research_report.missing_critical_fields)
                ),
                scope="context",
            )
        )

    stock_currency = research_report.stock.currency
    if historical_series is None:
        limitations.append(
            ResearchLimitation(
                id="context:no_historical_series",
                category="missing_data",
                message="Historical financial series was not supplied to this context.",
                scope="context",
            )
        )
        return limitations

    if historical_series.is_stale:
        limitations.append(
            ResearchLimitation(
                id="context:stale_historical_data",
                category="freshness",
                message="Historical financial series is from stale cache.",
                scope="context",
            )
        )

    if not historical_series.periods:
        limitations.append(
            ResearchLimitation(
                id="context:insufficient_historical_periods",
                category="missing_data",
                message="Historical financial series has no usable annual periods.",
                scope="context",
            )
        )

    historical_currency = historical_series.currency
    if stock_currency and historical_currency and stock_currency != historical_currency:
        limitations.append(
            ResearchLimitation(
                id="context:currency_mismatch",
                category="currency",
                message=(
                    "Current snapshot currency "
                    f"({stock_currency}) differs from historical financial currency "
                    f"({historical_currency}); monetary values must not be directly compared "
                    "without currency context."
                ),
                scope="context",
            )
        )

    return limitations


def build_observation_links(
    research_report: ResearchReport,
    historical_report: HistoricalResearchReport | None,
    evidence: list[EvidenceItem],
    missing_data: list[MissingDataItem],
) -> list[ObservationEvidenceLink]:
    evidence_ids = {item.id for item in evidence}
    missing_ids = {item.id for item in missing_data}
    links = []

    current_observations = (
        research_report.valuation_observations
        + research_report.risk_signals
    )
    for index, observation in enumerate(current_observations):
        link = build_current_observation_link(index, observation, evidence_ids, missing_ids)
        if link is not None:
            links.append(link)

    if historical_report is not None:
        for index, observation in enumerate(historical_report.observations):
            link = build_historical_observation_link(index, observation, evidence_ids, missing_ids)
            if link is not None:
                links.append(link)

    return links


def build_current_observation_link(
    index: int,
    observation: ResearchObservation,
    evidence_ids: set[str],
    missing_ids: set[str],
) -> ObservationEvidenceLink | None:
    evidence_map = {
        "forward_pe": ("current:trailing_pe", "current:forward_pe"),
        "revenue_growth": ("current:revenue_growth",),
        "earnings_growth": tuple(
            item
            for item in ("current:earnings_growth", "current:revenue_growth")
            if item in evidence_ids
        ),
        "free_cash_flow": ("current:free_cash_flow",),
        "operating_cash_flow": ("current:operating_cash_flow",),
        "total_debt": ("current:total_debt", "current:total_cash"),
        "two_hundred_day_average": (
            "current:current_price",
            "current:two_hundred_day_average",
        ),
        "fifty_two_week_position": ("derived:52_week_position",),
    }
    missing_data_ids = ()
    linked_evidence_ids = evidence_map.get(observation.metric, ())

    if observation.metric == "missing_fields":
        linked_evidence_ids = ()
        missing_data_ids = tuple(sorted(item for item in missing_ids if item.startswith("missing:current:")))

    linked_evidence_ids = tuple(item for item in linked_evidence_ids if item in evidence_ids)
    missing_data_ids = tuple(item for item in missing_data_ids if item in missing_ids)
    if not linked_evidence_ids and not missing_data_ids:
        return None

    return ObservationEvidenceLink(
        id=f"current:{index}:{observation.metric}",
        observation_scope="current",
        observation_index=index,
        category=observation.category,
        metric=observation.metric,
        evidence_ids=linked_evidence_ids,
        missing_data_ids=missing_data_ids,
    )


def build_historical_observation_link(
    index: int,
    observation: ResearchObservation,
    evidence_ids: set[str],
    missing_ids: set[str],
) -> ObservationEvidenceLink | None:
    linked_evidence_ids = ()
    missing_data_ids = ()

    if observation.metric == "revenue":
        linked_evidence_ids = tuple(
            sorted(item for item in evidence_ids if item.startswith("derived:revenue_yoy:"))
        )
    elif observation.metric == "eps" and "unavailable" in observation.title.lower():
        missing_data_ids = tuple(
            sorted(item for item in missing_ids if item.startswith("missing:historical:eps:"))
        )
    elif observation.metric == "eps":
        linked_evidence_ids = tuple(
            sorted(item for item in evidence_ids if item.startswith("derived:eps_yoy:"))
        )
        missing_data_ids = tuple(
            sorted(item for item in missing_ids if item.startswith("missing:historical:eps_yoy:"))
        )
    elif observation.metric in HISTORICAL_PERIOD_FIELDS:
        linked_evidence_ids = tuple(
            sorted(item for item in evidence_ids if item.startswith(f"historical:{observation.metric}:"))
        )

    linked_evidence_ids = tuple(item for item in linked_evidence_ids if item in evidence_ids)
    missing_data_ids = tuple(item for item in missing_data_ids if item in missing_ids)
    if not linked_evidence_ids and not missing_data_ids:
        return None

    return ObservationEvidenceLink(
        id=f"historical:{index}:{observation.metric}",
        observation_scope="historical",
        observation_index=index,
        category=observation.category,
        metric=observation.metric,
        evidence_ids=linked_evidence_ids,
        missing_data_ids=missing_data_ids,
    )


def current_evidence_id(metric: str) -> str:
    return f"current:{metric}"


def historical_evidence_id(metric: str, period_end: date) -> str:
    return f"historical:{metric}:{period_end.isoformat()}"


def derived_yoy_evidence_id(metric: str, period_end: date) -> str:
    return f"derived:{metric}_yoy:{period_end.isoformat()}"


def missing_current_id(metric: str) -> str:
    return f"missing:current:{metric}"


def missing_historical_id(metric: str, period_end: date) -> str:
    return f"missing:historical:{metric}:{period_end.isoformat()}"


def metric_unit(metric: str) -> str | None:
    if metric in PERCENT_METRICS:
        return "ratio"
    if metric in MONETARY_METRICS:
        return "currency_amount"
    if metric in RATIO_METRICS:
        return "multiple"
    if metric == "trailing_eps" or metric == "eps":
        return "per_share"
    if metric in TEXT_METRICS:
        return "text"
    return None


def validate_research_context(context: ResearchContext) -> None:
    ensure_no_non_finite(context)
    validate_evidence(context.evidence)
    validate_missing_data(context.missing_data)
    validate_observation_links(context.observation_links, context.evidence, context.missing_data)


def validate_evidence(evidence: list[EvidenceItem]) -> None:
    seen = set()
    evidence_ids = set()

    for item in evidence:
        if not item.id:
            raise ResearchContextError("Evidence ID must be non-empty.")
        if item.id in seen:
            raise ResearchContextError(f"Duplicate evidence ID: {item.id}")
        seen.add(item.id)
        evidence_ids.add(item.id)

        if item.source_type == "derived":
            if not item.derived_from:
                raise ResearchContextError(f"Derived evidence must have lineage: {item.id}")
        elif item.derived_from:
            raise ResearchContextError(f"Source evidence cannot have derived_from: {item.id}")

        if item.period_end is not None and item.period_year is not None:
            if item.period_end.year != item.period_year:
                raise ResearchContextError(
                    f"Evidence period_end and period_year mismatch: {item.id}"
                )

    for item in evidence:
        for source_id in item.derived_from:
            if source_id not in evidence_ids:
                raise ResearchContextError(
                    f"Evidence {item.id} references missing derived_from ID: {source_id}"
                )


def validate_missing_data(missing_data: list[MissingDataItem]) -> None:
    seen = set()
    for item in missing_data:
        if not item.id:
            raise ResearchContextError("Missing data ID must be non-empty.")
        if item.id in seen:
            raise ResearchContextError(f"Duplicate missing data ID: {item.id}")
        seen.add(item.id)
        if item.period_end is not None and item.period_year is not None:
            if item.period_end.year != item.period_year:
                raise ResearchContextError(
                    f"Missing data period_end and period_year mismatch: {item.id}"
                )


def validate_observation_links(
    links: list[ObservationEvidenceLink],
    evidence: list[EvidenceItem],
    missing_data: list[MissingDataItem],
) -> None:
    evidence_ids = {item.id for item in evidence}
    missing_ids = {item.id for item in missing_data}
    seen = set()
    for link in links:
        if not link.id:
            raise ResearchContextError("Observation evidence link ID must be non-empty.")
        if link.id in seen:
            raise ResearchContextError(f"Duplicate observation evidence link ID: {link.id}")
        seen.add(link.id)
        for evidence_id in link.evidence_ids:
            if evidence_id not in evidence_ids:
                raise ResearchContextError(
                    f"Observation link {link.id} references missing evidence ID: {evidence_id}"
                )
        for missing_data_id in link.missing_data_ids:
            if missing_data_id not in missing_ids:
                raise ResearchContextError(
                    f"Observation link {link.id} references missing data ID: {missing_data_id}"
                )


def ensure_no_non_finite(value, path: str = "context") -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, Real):
        if not math.isfinite(float(value)):
            raise ResearchContextError(f"Non-finite numeric value at {path}.")
        return
    if isinstance(value, (str, date, datetime)):
        return
    if isinstance(value, dict):
        for key, item in value.items():
            ensure_no_non_finite(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            ensure_no_non_finite(item, f"{path}[{index}]")
        return
    if is_dataclass(value):
        for field in fields(value):
            ensure_no_non_finite(getattr(value, field.name), f"{path}.{field.name}")


def json_safe_value(value):
    if is_dataclass(value):
        return {
            field.name: json_safe_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [json_safe_value(item) for item in value]
    if isinstance(value, list):
        return [json_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: json_safe_value(item)
            for key, item in value.items()
        }
    if isinstance(value, Real) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            raise ResearchContextError("Cannot serialize non-finite numeric value.")
    return value
