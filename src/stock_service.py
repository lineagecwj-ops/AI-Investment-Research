from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import math
from numbers import Integral
from numbers import Real
from pathlib import Path

import yfinance as yf

from database import log_cache_warning
from live_data_store import LiveDataStore
from models import Stock


class StockServiceError(Exception):
    """Base error for stock data lookup failures."""


class StockDataError(StockServiceError):
    """Raised when Yahoo Finance returns incomplete stock data."""


def optional_float(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None

    return numeric_value


def optional_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, Integral):
        return None

    return int(value)


def optional_text(value) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    return text


def stock_from_yahoo_info(info: dict, requested_symbol: str) -> Stock:
    current_price = optional_float(info.get("currentPrice"))
    if current_price is None:
        current_price = optional_float(info.get("regularMarketPrice"))

    return Stock(
        symbol=optional_text(info.get("symbol")) or requested_symbol,
        company_name=optional_text(info.get("longName")) or optional_text(info.get("shortName")),
        current_price=current_price,
        currency=optional_text(info.get("currency")),
        market_cap=optional_int(info.get("marketCap")),
        trailing_pe=optional_float(info.get("trailingPE")),
        forward_pe=optional_float(info.get("forwardPE")),
        trailing_eps=optional_float(info.get("trailingEps")),
        return_on_equity=optional_float(info.get("returnOnEquity")),
        company_summary=optional_text(info.get("longBusinessSummary")),
        gross_margin=optional_float(info.get("grossMargins")),
        operating_margin=optional_float(info.get("operatingMargins")),
        net_margin=optional_float(info.get("profitMargins")),
        revenue_growth=optional_float(info.get("revenueGrowth")),
        earnings_growth=optional_float(info.get("earningsGrowth")),
        total_cash=optional_int(info.get("totalCash")),
        total_debt=optional_int(info.get("totalDebt")),
        debt_to_equity=optional_float(info.get("debtToEquity")),
        operating_cash_flow=optional_int(info.get("operatingCashflow")),
        free_cash_flow=optional_int(info.get("freeCashflow")),
        price_to_book=optional_float(info.get("priceToBook")),
        fifty_two_week_high=optional_float(info.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=optional_float(info.get("fiftyTwoWeekLow")),
        fifty_day_average=optional_float(info.get("fiftyDayAverage")),
        two_hundred_day_average=optional_float(info.get("twoHundredDayAverage")),
        sector=optional_text(info.get("sector")),
        industry=optional_text(info.get("industry")),
    )


def validate_stock(stock: Stock) -> None:
    if stock.current_price is None:
        raise StockDataError("Yahoo Finance 回傳資料缺少目前價格。")


def get_stock(
    symbol: str,
    db_path: Path | str | None = None,
    live_store: LiveDataStore | None = None,
    *,
    force_refresh: bool = False,
) -> Stock:
    store = live_store or LiveDataStore(db_path=db_path)
    if not force_refresh:
        try:
            cached_stock = store.get_cached_stock(symbol)
        except Exception as exc:
            log_cache_warning("SQLite cache read failed", exc)
        else:
            if cached_stock is not None:
                return cached_stock

    stock = fetch_stock_from_yahoo(symbol)

    try:
        store.save_stock(stock)
    except Exception as exc:
        log_cache_warning("SQLite cache write failed", exc)

    return stock


def fetch_stock_from_yahoo(symbol: str) -> Stock:
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
