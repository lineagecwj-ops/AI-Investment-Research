from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

import yfinance as yf

from models import Stock


class StockServiceError(Exception):
    """Base error for stock data lookup failures."""


class StockDataError(StockServiceError):
    """Raised when Yahoo Finance returns incomplete stock data."""


def stock_from_yahoo_info(info: dict, requested_symbol: str) -> Stock:
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")

    return Stock(
        symbol=info.get("symbol") or requested_symbol,
        company_name=info.get("longName") or info.get("shortName"),
        price=current_price,
        current_price=current_price,
        currency=info.get("currency"),
        market_cap=info.get("marketCap"),
        trailing_pe=info.get("trailingPE"),
        forward_pe=info.get("forwardPE"),
        trailing_eps=info.get("trailingEps"),
        return_on_equity=info.get("returnOnEquity"),
        sector=info.get("sector"),
        industry=info.get("industry"),
    )


def validate_stock(stock: Stock) -> None:
    if stock.current_price is None:
        raise StockDataError("Yahoo Finance 回傳資料缺少目前價格。")


def get_stock(symbol: str) -> Stock:
    try:
        yahoo_stock = yf.Ticker(symbol)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            info = yahoo_stock.info
    except (OSError, TimeoutError) as exc:
        raise StockServiceError("Yahoo Finance 查詢失敗，請確認網路連線後再試。") from exc
    except Exception as exc:
        raise StockServiceError("Yahoo Finance 查詢失敗，請稍後再試。") from exc

    if not isinstance(info, dict) or not info:
        raise StockDataError("Yahoo Finance 沒有回傳可用的股票資料。")

    stock = stock_from_yahoo_info(info, symbol)
    validate_stock(stock)

    return stock
