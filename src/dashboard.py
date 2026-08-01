from dataclasses import dataclass
from typing import Callable

from models import Stock
from stock_service import get_stock
from stock_service import StockServiceError


@dataclass
class StockQueryFailure:

    symbol: str

    message: str


def format_na(value) -> str:
    if value is None or value == "":
        return "N/A"

    return str(value)


def format_integer(value) -> str:
    if value is None:
        return "N/A"

    return f"{value:,}"


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
        "Market Cap": format_integer(stock.market_cap),
        "Trailing PE": format_decimal(stock.trailing_pe),
        "Forward PE": format_decimal(stock.forward_pe),
        "EPS": format_decimal(stock.trailing_eps),
        "ROE": format_percentage(stock.return_on_equity),
        "Sector": format_na(stock.sector),
        "Industry": format_na(stock.industry),
    }


def stock_comparison_row(stock: Stock) -> dict[str, str]:
    return {
        "Symbol": format_na(stock.symbol),
        "Company": format_na(stock.company_name),
        "Current Price": format_decimal(stock.current_price),
        "Currency": format_na(stock.currency),
        "Market Cap": format_integer(stock.market_cap),
        "Trailing PE": format_decimal(stock.trailing_pe),
        "Forward PE": format_decimal(stock.forward_pe),
        "EPS": format_decimal(stock.trailing_eps),
        "ROE": format_percentage(stock.return_on_equity),
        "Sector": format_na(stock.sector),
        "Industry": format_na(stock.industry),
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
