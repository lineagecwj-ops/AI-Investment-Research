from dataclasses import dataclass
from datetime import date
from typing import Callable

from company_name_service import get_display_company_name
from models import HistoricalFinancialSeries
from models import Stock
from research_metrics import historical_yoy_growth_by_field
from stock_service import get_stock
from stock_service import StockServiceError


@dataclass
class StockQueryFailure:

    symbol: str

    message: str


@dataclass(frozen=True)
class HistoricalOverviewDisplay:

    symbol: str

    company_name: str

    currency: str

    annual_periods: str

    period_range: str

    available_periods: str

    cache_status: str

    stale_warning: str | None


@dataclass(frozen=True)
class HistoricalTrendDisplay:

    overview: HistoricalOverviewDisplay

    revenue_rows: list[dict[str, str]]

    earnings_rows: list[dict[str, str]]

    margin_rows: list[dict[str, str]]

    cash_flow_rows: list[dict[str, str]]

    financial_position_rows: list[dict[str, str]]

    historical_table_rows: list[dict[str, str]]

    missing_data_notes: list[str]


INDICATOR_LABELS = {
    "company_name": "Company Name（公司名稱）",
    "symbol": "Symbol（股票代號）",
    "company_summary": "Company Summary（公司業務摘要）",
    "current_price": "Current Price（目前股價）",
    "currency": "Currency（交易幣別）",
    "market_cap": "Market Cap（市值）",
    "trailing_pe": "Trailing P/E（歷史本益比）",
    "forward_pe": "Forward P/E（預估本益比）",
    "trailing_eps": "EPS（每股盈餘）",
    "return_on_equity": "ROE（股東權益報酬率）",
    "gross_margin": "Gross Margin（毛利率）",
    "operating_margin": "Operating Margin（營業利益率）",
    "net_margin": "Net Margin（淨利率）",
    "revenue_growth": "Revenue Growth（營收成長率）",
    "earnings_growth": "Earnings Growth（盈餘成長率）",
    "total_cash": "Total Cash（現金）",
    "total_debt": "Total Debt（總負債）",
    "debt_to_equity": "Debt to Equity（負債權益比）",
    "operating_cash_flow": "Operating Cash Flow（營業現金流）",
    "free_cash_flow": "Free Cash Flow（自由現金流）",
    "price_to_book": "Price to Book（股價淨值比）",
    "fifty_two_week_high": "52-week High（52 週高點）",
    "fifty_two_week_low": "52-week Low（52 週低點）",
    "fifty_two_week_position": "52-week Position（52 週區間位置）",
    "fifty_day_average": "50-day Average（50 日均價）",
    "two_hundred_day_average": "200-day Average（200 日均價）",
    "sector": "Sector（產業類別）",
    "industry": "Industry（細分產業）",
}


INDICATOR_HELP_TEXT = {
    "current_price": "目前市場交易價格。不同交易幣別不可直接比較高低。",
    "market_cap": "公司總市值，通常用來理解企業規模；仍需搭配獲利、成長與風險一起看。",
    "trailing_pe": "以過去獲利計算的本益比，可觀察市場願意為歷史盈餘付出的價格倍數。",
    "forward_pe": "以預估獲利計算的本益比，反映市場對未來盈餘的期待，但預估可能修正。",
    "trailing_eps": "每股盈餘，代表每股可分攤的獲利能力，需搭配成長性與品質判斷。",
    "return_on_equity": "股東權益報酬率，衡量公司運用股東資本創造獲利的效率；需搭配槓桿、產業與獲利品質一起看。",
    "gross_margin": "毛利率，衡量營收扣除銷貨成本後的比例；常用來觀察產品組合與定價能力，但不能單獨判斷好壞。",
    "operating_margin": "營業利益率，衡量本業營運產生利潤的比例；常用來觀察營運效率，但需搭配成長與產業模式。",
    "net_margin": "淨利率，衡量營收最後轉為淨利的比例；常用來看整體獲利品質，但可能受一次性項目影響。",
    "revenue_growth": "營收成長率，觀察近期營收變化；本頁使用 Yahoo Finance 提供的近期數據，不能直接視為多年 CAGR。",
    "earnings_growth": "盈餘成長率，觀察近期盈餘變化；本頁使用 Yahoo Finance 提供的近期數據，需搭配利潤率與一次性項目判讀。",
    "total_cash": "公司持有的現金與約當現金；顯示時保留 Yahoo 提供的幣別脈絡。",
    "total_debt": "公司總負債；需搭配現金、現金流、利息費用與到期結構一起看。",
    "debt_to_equity": (
        "Yahoo Finance 此欄位以百分比尺度提供，表示總負債相對股東權益的比例。"
        "例如 15.17 代表約 15.17%，不是 15.17 倍。"
        "此指標需搭配產業特性、現金、現金流與債務結構理解，不能單獨判定公司財務好壞。"
    ),
    "operating_cash_flow": "營業現金流，觀察本業產生現金的能力；單期數值需搭配營運週期與歷史趨勢。",
    "free_cash_flow": "自由現金流，通常為營業現金流扣除資本支出後的概念；負值需進一步檢查投資與營運背景。",
    "price_to_book": "股價淨值比，觀察價格相對帳面淨值的倍數；不同產業適用性不同。",
    "fifty_two_week_high": "近 52 週高點，用來理解目前價格所在區間；不是買賣訊號。",
    "fifty_two_week_low": "近 52 週低點，用來理解目前價格所在區間；需確認資料時間一致性。",
    "fifty_two_week_position": "目前價格在 52 週高低區間的位置；不是強弱評分，也不是買賣訊號。",
    "fifty_day_average": "50 日均價，提供近期價格位置參考；不是完整技術分析結論。",
    "two_hundred_day_average": "200 日均價，提供較長期價格位置參考；需搭配基本面與事件脈絡。",
    "sector": "公司所屬主要產業類別，可用來理解景氣循環與同業比較背景。",
    "industry": "公司更細分的產業分類，適合用於較精準的同業比較。",
}


HISTORICAL_METRIC_HELP_TEXT = {
    "revenue": "Revenue（營收）：公司在該年度認列的收入，是觀察規模與需求變化的起點。",
    "net_income": "Net Income（淨利）：扣除成本、費用、稅與其他影響後的獲利，不等於現金流。",
    "eps": "EPS（每股盈餘）：每股可分攤的獲利。若 Yahoo Finance 未提供，本頁不自行計算。",
    "gross_margin": "Gross Margin（毛利率）：看產品 / 服務本身的毛利結構。",
    "operating_margin": "Operating Margin（營業利益率）：加入營業費用後的本業獲利能力。",
    "net_margin": "Net Margin（淨利率）：包含更多非營業與稅後影響後的最終獲利率。",
    "operating_cash_flow": "Operating Cash Flow（營業現金流）：公司本業活動產生的現金流入或流出。",
    "free_cash_flow": "Free Cash Flow（自由現金流）：通常用來觀察營運現金流扣除資本支出後留下的現金。",
    "capital_expenditure": (
        "Capital Expenditure（資本支出）：通常代表公司投入廠房、設備等長期資產的現金支出。"
        "Yahoo Finance 此資料常以負數表示 cash outflow。"
    ),
    "total_debt": "Total Debt（總負債）：公司債務規模，需搭配現金、現金流與債務到期結構理解。",
    "total_equity": "Total Equity（股東權益）：資產扣除負債後歸屬股東的帳面權益。",
}


HISTORICAL_TABLE_COLUMNS = {
    "period_end": "Period End",
    "revenue": "Revenue",
    "revenue_yoy": "Revenue YoY",
    "gross_profit": "Gross Profit",
    "operating_income": "Operating Income",
    "net_income": "Net Income",
    "eps": "EPS",
    "eps_yoy": "EPS YoY",
    "gross_margin": "Gross Margin",
    "operating_margin": "Operating Margin",
    "net_margin": "Net Margin",
    "operating_cash_flow": "Operating Cash Flow",
    "capital_expenditure": "Capital Expenditure",
    "free_cash_flow": "Free Cash Flow",
    "total_assets": "Total Assets",
    "total_debt": "Total Debt",
    "total_equity": "Total Equity",
    "cash_and_cash_equivalents": "Cash",
}


HISTORICAL_CHART_LABELS = {
    "revenue": "Revenue",
    "net_income": "Net Income",
    "eps": "EPS",
    "gross_margin": "Gross Margin",
    "operating_margin": "Operating Margin",
    "net_margin": "Net Margin",
    "operating_cash_flow": "Operating Cash Flow",
    "capital_expenditure": "Capital Expenditure",
    "free_cash_flow": "Free Cash Flow",
    "total_assets": "Total Assets",
    "total_debt": "Total Debt",
    "total_equity": "Total Equity",
    "cash_and_cash_equivalents": "Cash",
}


SECTOR_TRANSLATIONS = {
    "Technology": "科技",
    "Healthcare": "醫療保健",
    "Financial Services": "金融服務",
    "Consumer Cyclical": "非必需消費",
    "Consumer Defensive": "必需消費",
    "Industrials": "工業",
    "Energy": "能源",
    "Basic Materials": "原物料",
    "Communication Services": "通訊服務",
    "Real Estate": "房地產",
    "Utilities": "公用事業",
}


INDUSTRY_TRANSLATIONS = {
    "Semiconductors": "半導體",
    "Consumer Electronics": "消費性電子",
    "Software - Infrastructure": "基礎架構軟體",
    "Software - Application": "應用軟體",
    "Banks - Diversified": "多元化銀行",
    "Credit Services": "信貸服務",
    "Drug Manufacturers - General": "綜合製藥",
    "Medical Devices": "醫療器材",
    "Oil & Gas Integrated": "綜合石油天然氣",
    "Telecom Services": "電信服務",
    "Utilities - Regulated Electric": "受監管電力公用事業",
}


def indicator_label(indicator: str) -> str:
    return INDICATOR_LABELS[indicator]


def indicator_help(indicator: str) -> str | None:
    return INDICATOR_HELP_TEXT.get(indicator)


def format_na(value) -> str:
    if value is None or value == "":
        return "N/A"

    return str(value)


def format_missing(value) -> str:
    return format_na(value)


def format_integer(value) -> str:
    if value is None:
        return "N/A"

    return f"{value:,}"


def format_compact_number(value: int | float | None) -> str:
    if value is None:
        return "N/A"

    absolute_value = abs(value)
    units = [
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
    ]

    for factor, suffix in units:
        if absolute_value >= factor:
            return f"{value / factor:.2f}{suffix}"

    return f"{value:,.0f}"


def format_market_cap(value: int | None, currency: str | None = None) -> str:
    compact_value = format_compact_number(value)
    if compact_value == "N/A":
        return "N/A"

    if currency:
        return f"{currency} {compact_value}"

    return compact_value


def format_currency_value(value: int | float | None, currency: str | None = None) -> str:
    compact_value = format_compact_number(value)
    if compact_value == "N/A":
        return "N/A"

    if currency:
        return f"{currency} {compact_value}"

    return compact_value


def format_currency_amount(value: int | float | None, currency: str | None = None) -> str:
    return format_currency_value(value, currency)


def format_decimal(value) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}"


def format_eps(value: float | None) -> str:
    return format_decimal(value)


def format_price(value: int | float | None, currency: str | None = None) -> str:
    formatted_value = format_decimal(value)
    if formatted_value == "N/A":
        return "N/A"

    if currency:
        return f"{currency} {formatted_value}"

    return formatted_value


def format_ratio(value: float | None) -> str:
    return format_decimal(value)


def format_debt_to_equity(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}%"


def format_percentage(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


def format_yoy(value: float | None) -> str:
    return format_percentage(value)


def format_period_end(value: date | None) -> str:
    if value is None:
        return "N/A"

    return f"FY ending {value.isoformat()}"


def format_chart_period_label(value: date | None, period_year: int | None = None) -> str:
    if period_year is not None:
        return f"FY {period_year}"

    if value is None:
        return "N/A"

    return f"FY {value.year}"


def historical_metric_help(metric: str) -> str | None:
    return HISTORICAL_METRIC_HELP_TEXT.get(metric)


def format_localized_classification(
    value: str | None,
    translations: dict[str, str],
) -> str:
    if value is None or value == "":
        return "N/A"

    translation = translations.get(value)
    if translation is None:
        return value

    return f"{value}（{translation}）"


def format_sector(value: str | None) -> str:
    return format_localized_classification(value, SECTOR_TRANSLATIONS)


def format_industry(value: str | None) -> str:
    return format_localized_classification(value, INDUSTRY_TRANSLATIONS)


def stock_display_data(stock: Stock) -> dict[str, str]:
    return {
        "Company Name": format_na(get_display_company_name(stock)),
        "Symbol": format_na(stock.symbol),
        "Current Price": format_decimal(stock.current_price),
        "Currency": format_na(stock.currency),
        "Market Cap": format_market_cap(stock.market_cap, stock.currency),
        "Trailing PE": format_decimal(stock.trailing_pe),
        "Forward PE": format_decimal(stock.forward_pe),
        "EPS": format_decimal(stock.trailing_eps),
        "ROE": format_percentage(stock.return_on_equity),
        "Sector": format_sector(stock.sector),
        "Industry": format_industry(stock.industry),
    }


def build_historical_trend_display(
    series: HistoricalFinancialSeries,
    stock: Stock | None = None,
) -> HistoricalTrendDisplay:
    periods = list(series.periods or [])
    revenue_yoy = historical_yoy_lookup(series, "revenue")
    eps_yoy = historical_yoy_lookup(series, "eps")

    return HistoricalTrendDisplay(
        overview=build_historical_overview(series, stock),
        revenue_rows=[
            {
                "Period End": format_period_end(period.period_end),
                "Revenue": format_currency_amount(period.revenue, period.currency or series.currency),
                "YoY": format_yoy(revenue_yoy.get(period.period_end)),
            }
            for period in periods
        ],
        earnings_rows=[
            {
                "Period End": format_period_end(period.period_end),
                "Net Income": format_currency_amount(period.net_income, period.currency or series.currency),
                "EPS": format_eps(period.eps),
                "EPS YoY": format_yoy(eps_yoy.get(period.period_end)),
            }
            for period in periods
        ],
        margin_rows=[
            {
                "Period End": format_period_end(period.period_end),
                "Gross Margin": format_percentage(period.gross_margin),
                "Operating Margin": format_percentage(period.operating_margin),
                "Net Margin": format_percentage(period.net_margin),
            }
            for period in periods
        ],
        cash_flow_rows=[
            {
                "Period End": format_period_end(period.period_end),
                "Operating Cash Flow": format_currency_amount(
                    period.operating_cash_flow,
                    period.currency or series.currency,
                ),
                "Capital Expenditure": format_currency_amount(
                    period.capital_expenditure,
                    period.currency or series.currency,
                ),
                "Free Cash Flow": format_currency_amount(
                    period.free_cash_flow,
                    period.currency or series.currency,
                ),
            }
            for period in periods
        ],
        financial_position_rows=[
            {
                "Period End": format_period_end(period.period_end),
                "Total Assets": format_currency_amount(period.total_assets, period.currency or series.currency),
                "Total Debt": format_currency_amount(period.total_debt, period.currency or series.currency),
                "Total Equity": format_currency_amount(period.total_equity, period.currency or series.currency),
                "Cash": format_currency_amount(
                    period.cash_and_cash_equivalents,
                    period.currency or series.currency,
                ),
            }
            for period in periods
        ],
        historical_table_rows=build_historical_table_rows(series),
        missing_data_notes=build_historical_missing_data_notes(series),
    )


def build_historical_overview(
    series: HistoricalFinancialSeries,
    stock: Stock | None = None,
) -> HistoricalOverviewDisplay:
    periods = list(series.periods or [])
    company_name = get_display_company_name(stock) if stock is not None else None
    currency = series.currency or (stock.currency if stock is not None else None)

    if periods:
        first_period = periods[0]
        last_period = periods[-1]
        year_values = [period.period_year for period in periods if period.period_year is not None]
        annual_periods = (
            f"{min(year_values)}–{max(year_values)}"
            if year_values
            else "N/A"
        )
        period_range = (
            f"{format_period_end(first_period.period_end)} – "
            f"{format_period_end(last_period.period_end)}"
        )
    else:
        annual_periods = "N/A"
        period_range = "N/A"

    return HistoricalOverviewDisplay(
        symbol=format_na(series.symbol or (stock.symbol if stock is not None else None)),
        company_name=format_na(company_name),
        currency=format_na(currency),
        annual_periods=annual_periods,
        period_range=period_range,
        available_periods=str(len(periods)),
        cache_status=historical_cache_status_text(series),
        stale_warning=historical_stale_warning_text(series),
    )


def historical_cache_status_text(series: HistoricalFinancialSeries) -> str:
    if series.is_stale:
        return "歷史資料：顯示本機較舊快取"

    return "歷史資料：已使用 7 天內快取或剛更新資料"


def historical_stale_warning_text(series: HistoricalFinancialSeries) -> str | None:
    if not series.is_stale:
        return None

    return "目前 Yahoo Finance 查詢失敗，顯示本機較舊的歷史資料。"


def build_historical_table_rows(series: HistoricalFinancialSeries) -> list[dict[str, str]]:
    revenue_yoy = historical_yoy_lookup(series, "revenue")
    eps_yoy = historical_yoy_lookup(series, "eps")
    rows = []

    for period in series.periods or []:
        currency = period.currency or series.currency
        rows.append(
            {
                HISTORICAL_TABLE_COLUMNS["period_end"]: format_period_end(period.period_end),
                HISTORICAL_TABLE_COLUMNS["revenue"]: format_currency_amount(period.revenue, currency),
                HISTORICAL_TABLE_COLUMNS["revenue_yoy"]: format_yoy(revenue_yoy.get(period.period_end)),
                HISTORICAL_TABLE_COLUMNS["gross_profit"]: format_currency_amount(period.gross_profit, currency),
                HISTORICAL_TABLE_COLUMNS["operating_income"]: format_currency_amount(
                    period.operating_income,
                    currency,
                ),
                HISTORICAL_TABLE_COLUMNS["net_income"]: format_currency_amount(period.net_income, currency),
                HISTORICAL_TABLE_COLUMNS["eps"]: format_eps(period.eps),
                HISTORICAL_TABLE_COLUMNS["eps_yoy"]: format_yoy(eps_yoy.get(period.period_end)),
                HISTORICAL_TABLE_COLUMNS["gross_margin"]: format_percentage(period.gross_margin),
                HISTORICAL_TABLE_COLUMNS["operating_margin"]: format_percentage(period.operating_margin),
                HISTORICAL_TABLE_COLUMNS["net_margin"]: format_percentage(period.net_margin),
                HISTORICAL_TABLE_COLUMNS["operating_cash_flow"]: format_currency_amount(
                    period.operating_cash_flow,
                    currency,
                ),
                HISTORICAL_TABLE_COLUMNS["capital_expenditure"]: format_currency_amount(
                    period.capital_expenditure,
                    currency,
                ),
                HISTORICAL_TABLE_COLUMNS["free_cash_flow"]: format_currency_amount(
                    period.free_cash_flow,
                    currency,
                ),
                HISTORICAL_TABLE_COLUMNS["total_assets"]: format_currency_amount(period.total_assets, currency),
                HISTORICAL_TABLE_COLUMNS["total_debt"]: format_currency_amount(period.total_debt, currency),
                HISTORICAL_TABLE_COLUMNS["total_equity"]: format_currency_amount(period.total_equity, currency),
                HISTORICAL_TABLE_COLUMNS["cash_and_cash_equivalents"]: format_currency_amount(
                    period.cash_and_cash_equivalents,
                    currency,
                ),
            }
        )

    return rows


def build_historical_chart_rows(
    series: HistoricalFinancialSeries,
    fields: list[str],
) -> list[dict[str, float | str | None]]:
    rows = []
    for period in series.periods or []:
        row: dict[str, float | str | None] = {
            "Period": format_chart_period_label(period.period_end, period.period_year),
            "Period End": format_period_end(period.period_end),
        }
        for field in fields:
            row[HISTORICAL_CHART_LABELS.get(field, field)] = getattr(period, field)
        rows.append(row)

    return rows


def has_enough_historical_data(
    series: HistoricalFinancialSeries,
    fields: list[str],
    minimum_points: int = 2,
) -> bool:
    for field in fields:
        count = sum(
            1
            for period in series.periods or []
            if getattr(period, field) is not None
        )
        if count >= minimum_points:
            return True

    return False


def build_historical_missing_data_notes(series: HistoricalFinancialSeries) -> list[str]:
    notes = []
    periods = list(series.periods or [])

    if not periods:
        return ["目前可取得的歷史資料不足，暫不顯示趨勢。"]

    eps_missing_periods = [
        format_period_end(period.period_end)
        for period in periods
        if period.eps is None
    ]
    if eps_missing_periods:
        notes.append(
            "Yahoo Finance 目前未提供此期 EPS："
            + "、".join(eps_missing_periods)
            + "。"
        )

    missing_groups = [
        (
            "Cash Flow（現金流）",
            ["operating_cash_flow", "capital_expenditure", "free_cash_flow"],
        ),
        (
            "Financial Position（財務結構）",
            ["total_assets", "total_debt", "total_equity", "cash_and_cash_equivalents"],
        ),
    ]
    for title, fields in missing_groups:
        if not any(
            getattr(period, field) is not None
            for period in periods
            for field in fields
        ):
            notes.append(f"{title} 目前可取得的歷史資料不足，暫不顯示趨勢。")

    return notes


def historical_yoy_lookup(
    series: HistoricalFinancialSeries,
    field_name: str,
) -> dict[date, float | None]:
    yoy_values = historical_yoy_growth_by_field(series, field_name)
    lookup = {}

    for period, (_period_year, growth) in zip(series.periods or [], yoy_values):
        lookup[period.period_end] = growth

    return lookup


def stock_comparison_row(stock: Stock) -> dict[str, str]:
    return {
        indicator_label("symbol"): format_na(stock.symbol),
        indicator_label("company_name"): format_na(get_display_company_name(stock)),
        indicator_label("current_price"): format_decimal(stock.current_price),
        indicator_label("currency"): format_na(stock.currency),
        indicator_label("market_cap"): format_market_cap(stock.market_cap, stock.currency),
        indicator_label("trailing_pe"): format_decimal(stock.trailing_pe),
        indicator_label("forward_pe"): format_decimal(stock.forward_pe),
        indicator_label("trailing_eps"): format_decimal(stock.trailing_eps),
        indicator_label("return_on_equity"): format_percentage(stock.return_on_equity),
        indicator_label("sector"): format_sector(stock.sector),
        indicator_label("industry"): format_industry(stock.industry),
    }


def build_comparison_rows(stocks: list[Stock]) -> list[dict[str, str]]:
    return [stock_comparison_row(stock) for stock in stocks]


def query_stock_batch(
    symbols: list[str],
    stock_lookup: Callable[[str], Stock] = get_stock,
) -> tuple[list[Stock], list[StockQueryFailure]]:
    stocks = []
    failures = []

    for symbol in symbols:
        try:
            stocks.append(stock_lookup(symbol))
        except StockServiceError as error:
            failures.append(StockQueryFailure(symbol=symbol, message=str(error)))

    return stocks, failures
