from dataclasses import dataclass
from typing import Callable

from models import Stock
from stock_service import get_stock
from stock_service import StockServiceError


@dataclass
class StockQueryFailure:

    symbol: str

    message: str


INDICATOR_LABELS = {
    "company_name": "Company Name（公司名稱）",
    "symbol": "Symbol（股票代號）",
    "current_price": "Current Price（目前股價）",
    "currency": "Currency（交易幣別）",
    "market_cap": "Market Cap（市值）",
    "trailing_pe": "Trailing P/E（歷史本益比）",
    "forward_pe": "Forward P/E（預估本益比）",
    "trailing_eps": "EPS（每股盈餘）",
    "return_on_equity": "ROE（股東權益報酬率）",
    "sector": "Sector（產業類別）",
    "industry": "Industry（細分產業）",
}


INDICATOR_HELP_TEXT = {
    "current_price": "目前市場交易價格。不同交易幣別不可直接比較高低。",
    "market_cap": "公司總市值，通常用來理解企業規模；仍需搭配獲利、成長與風險一起看。",
    "trailing_pe": "以過去獲利計算的本益比，可觀察市場願意為歷史盈餘付出的價格倍數。",
    "forward_pe": "以預估獲利計算的本益比，反映市場對未來盈餘的期待，但預估可能修正。",
    "trailing_eps": "每股盈餘，代表每股可分攤的獲利能力，需搭配成長性與品質判斷。",
    "return_on_equity": "股東權益報酬率，衡量公司運用股東資本創造獲利的效率。",
    "sector": "公司所屬主要產業類別，可用來理解景氣循環與同業比較背景。",
    "industry": "公司更細分的產業分類，適合用於較精準的同業比較。",
}


def indicator_label(indicator: str) -> str:
    return INDICATOR_LABELS[indicator]


def indicator_help(indicator: str) -> str | None:
    return INDICATOR_HELP_TEXT.get(indicator)


def format_na(value) -> str:
    if value is None or value == "":
        return "N/A"

    return str(value)


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


def format_decimal(value) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}"


def format_percentage(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


def stock_display_data(stock: Stock) -> dict[str, str]:
    return {
        "Company Name": format_na(stock.company_name),
        "Symbol": format_na(stock.symbol),
        "Current Price": format_decimal(stock.current_price),
        "Currency": format_na(stock.currency),
        "Market Cap": format_market_cap(stock.market_cap, stock.currency),
        "Trailing PE": format_decimal(stock.trailing_pe),
        "Forward PE": format_decimal(stock.forward_pe),
        "EPS": format_decimal(stock.trailing_eps),
        "ROE": format_percentage(stock.return_on_equity),
        "Sector": format_na(stock.sector),
        "Industry": format_na(stock.industry),
    }


def stock_comparison_row(stock: Stock) -> dict[str, str]:
    return {
        indicator_label("symbol"): format_na(stock.symbol),
        indicator_label("company_name"): format_na(stock.company_name),
        indicator_label("current_price"): format_decimal(stock.current_price),
        indicator_label("currency"): format_na(stock.currency),
        indicator_label("market_cap"): format_market_cap(stock.market_cap, stock.currency),
        indicator_label("trailing_pe"): format_decimal(stock.trailing_pe),
        indicator_label("forward_pe"): format_decimal(stock.forward_pe),
        indicator_label("trailing_eps"): format_decimal(stock.trailing_eps),
        indicator_label("return_on_equity"): format_percentage(stock.return_on_equity),
        indicator_label("sector"): format_na(stock.sector),
        indicator_label("industry"): format_na(stock.industry),
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
