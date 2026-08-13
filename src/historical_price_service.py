from contextlib import redirect_stderr
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import date
from datetime import timedelta
from io import StringIO
import logging
import math
from numbers import Integral
from numbers import Real
from pathlib import Path

import pandas as pd
import yfinance as yf

from database import log_cache_warning
from live_data_store import LiveDataStore
from database import utc_now
from models import HistoricalPriceBar
from models import HistoricalPriceSeries
from stock_service import optional_text
from symbol_utils import normalize_stock_symbol


PRICE_SOURCE = "Yahoo Finance"
YAHOO_AUTO_ADJUST = False
YAHOO_ACTIONS = True
PRICE_HISTORY_CACHE_TTL_HOURS = 12

YAHOO_COLUMNS = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "adjusted_close": "Adj Close",
    "volume": "Volume",
    "dividends": "Dividends",
    "stock_splits": "Stock Splits",
}


class HistoricalPriceError(Exception):
    """Base error for historical price lookup failures."""


class HistoricalPriceSourceError(HistoricalPriceError):
    """Raised when the price provider cannot be reached or queried."""


class HistoricalPriceDataError(HistoricalPriceError):
    """Raised when provider price data cannot form usable daily bars."""


@dataclass(frozen=True)
class HistoricalPriceQuality:

    raw_rows: int

    retained_rows: int

    filtered_rows: int

    duplicate_dates: int

    conflicting_duplicate_dates: int

    invalid_prices: int

    non_finite_values: int

    negative_volume: int

    price_relationship_violations: int

    earliest_date: date | None

    latest_date: date | None


def get_historical_prices(
    symbol: str,
    *,
    start: date | None = None,
    end: date | None = None,
    force_refresh: bool = False,
    db_path: Path | str | None = None,
    live_store: LiveDataStore | None = None,
) -> HistoricalPriceSeries:
    normalized_symbol = normalize_stock_symbol(symbol)
    require_full_history = start is None
    store = live_store or LiveDataStore(db_path=db_path)

    if not force_refresh:
        cached_series = store.get_cached_historical_prices(
            normalized_symbol,
            start=start,
            end=end,
            require_full_history=require_full_history,
        )
        if cached_series is not None:
            return cached_series

    try:
        series = fetch_historical_prices_from_yahoo(
            normalized_symbol,
            start=start,
            end=end,
        )
    except Exception as exc:
        stale_series = store.get_cached_historical_prices(
            normalized_symbol,
            start=start,
            end=end,
            include_expired=True,
            require_full_history=require_full_history,
        )
        if stale_series is not None:
            log_cache_warning("Yahoo historical price refresh failed; using stale cache", exc)
            return HistoricalPriceSeries(
                symbol=stale_series.symbol,
                currency=stale_series.currency,
                bars=stale_series.bars,
                fetched_at=stale_series.fetched_at,
                is_stale=True,
                source=stale_series.source,
            )
        if isinstance(exc, HistoricalPriceError):
            raise
        raise HistoricalPriceSourceError(
            "Yahoo Finance historical price 查詢失敗，請稍後再試。"
        ) from exc

    try:
        store.save_historical_prices(
            series,
            full_history_fetched=start is None,
        )
    except Exception as exc:
        log_cache_warning("SQLite historical price cache write failed", exc)

    return series


def fetch_historical_prices_from_yahoo(
    symbol: str,
    *,
    start: date | None = None,
    end: date | None = None,
) -> HistoricalPriceSeries:
    try:
        ticker = yf.Ticker(symbol)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            frame = fetch_yahoo_history(ticker, start=start, end=end)
            currency = fetch_yahoo_currency(ticker)
    except (OSError, TimeoutError) as exc:
        raise HistoricalPriceSourceError(
            "Yahoo Finance historical price 查詢失敗，請確認網路連線後再試。"
        ) from exc
    except HistoricalPriceError:
        raise
    except Exception as exc:
        raise HistoricalPriceSourceError(
            "Yahoo Finance historical price 查詢失敗，請稍後再試。"
        ) from exc

    series, quality = build_historical_price_series(
        symbol=symbol,
        currency=currency,
        frame=frame,
    )
    if not series.bars:
        raise HistoricalPriceDataError("Yahoo Finance 沒有回傳可用的 historical price bars。")
    if quality.filtered_rows:
        logging.info(
            "Filtered %s invalid historical price rows for %s",
            quality.filtered_rows,
            symbol,
        )
    return series


def fetch_yahoo_history(ticker, *, start: date | None, end: date | None):
    if start is None and end is None:
        return ticker.history(
            period="max",
            auto_adjust=YAHOO_AUTO_ADJUST,
            actions=YAHOO_ACTIONS,
        )

    kwargs = {
        "auto_adjust": YAHOO_AUTO_ADJUST,
        "actions": YAHOO_ACTIONS,
    }
    if start is not None:
        kwargs["start"] = start.isoformat()
    if end is not None:
        kwargs["end"] = (end + timedelta(days=1)).isoformat()
    return ticker.history(**kwargs)


def fetch_yahoo_currency(ticker) -> str | None:
    try:
        fast_info = ticker.fast_info
        if fast_info is not None:
            currency = optional_text(fast_info.get("currency"))
            if currency:
                return currency
    except Exception as exc:
        logging.debug("Unable to read Yahoo fast_info currency: %s", exc)

    try:
        info = ticker.info
    except Exception as exc:
        logging.debug("Unable to read Yahoo info currency: %s", exc)
        return None

    if not isinstance(info, dict):
        return None
    return optional_text(info.get("currency")) or optional_text(info.get("financialCurrency"))


def build_historical_price_series(
    *,
    symbol: str,
    currency: str | None,
    frame,
    fetched_at=None,
) -> tuple[HistoricalPriceSeries, HistoricalPriceQuality]:
    fetched_at = fetched_at or utc_now()
    if frame is None or getattr(frame, "empty", True):
        raise HistoricalPriceDataError("Yahoo Finance historical price response is empty.")
    if isinstance(getattr(frame, "columns", None), pd.MultiIndex):
        raise HistoricalPriceDataError("Yahoo Finance historical price response has MultiIndex columns.")

    rows_by_date: dict[date, HistoricalPriceBar] = {}
    row_signatures_by_date: dict[date, tuple] = {}
    raw_rows = len(frame)
    duplicate_dates = 0
    conflicting_duplicate_dates = 0
    invalid_prices = 0
    non_finite_values = 0
    negative_volume = 0
    price_relationship_violations = 0

    for index_value, row in frame.iterrows():
        trading_date = normalize_trading_date(index_value)
        if trading_date is None:
            non_finite_values += 1
            continue

        try:
            bar = price_bar_from_provider_row(symbol, trading_date, row)
        except HistoricalPriceDataError as exc:
            reason = str(exc)
            if "negative volume" in reason:
                negative_volume += 1
            elif "relationship" in reason:
                price_relationship_violations += 1
            elif "finite" in reason:
                non_finite_values += 1
            else:
                invalid_prices += 1
            continue

        signature = historical_price_bar_signature(bar)
        if trading_date in rows_by_date:
            duplicate_dates += 1
            if row_signatures_by_date[trading_date] != signature:
                conflicting_duplicate_dates += 1
            rows_by_date[trading_date] = bar
            row_signatures_by_date[trading_date] = signature
            continue

        rows_by_date[trading_date] = bar
        row_signatures_by_date[trading_date] = signature

    bars = tuple(rows_by_date[trading_date] for trading_date in sorted(rows_by_date))
    quality = HistoricalPriceQuality(
        raw_rows=raw_rows,
        retained_rows=len(bars),
        filtered_rows=raw_rows - len(bars) - duplicate_dates,
        duplicate_dates=duplicate_dates,
        conflicting_duplicate_dates=conflicting_duplicate_dates,
        invalid_prices=invalid_prices,
        non_finite_values=non_finite_values,
        negative_volume=negative_volume,
        price_relationship_violations=price_relationship_violations,
        earliest_date=bars[0].trading_date if bars else None,
        latest_date=bars[-1].trading_date if bars else None,
    )
    if not bars:
        raise HistoricalPriceDataError("No valid historical price bars remain after validation.")

    return (
        HistoricalPriceSeries(
            symbol=symbol,
            currency=currency,
            bars=bars,
            fetched_at=fetched_at,
            source=PRICE_SOURCE,
        ),
        quality,
    )


def price_bar_from_provider_row(
    symbol: str,
    trading_date: date,
    row,
) -> HistoricalPriceBar:
    open_price = optional_provider_float(row_value(row, YAHOO_COLUMNS["open"]))
    high = required_positive_float(row_value(row, YAHOO_COLUMNS["high"]), "high")
    low = required_positive_float(row_value(row, YAHOO_COLUMNS["low"]), "low")
    close = required_positive_float(row_value(row, YAHOO_COLUMNS["close"]), "close")
    adjusted_close = optional_positive_float(row_value(row, YAHOO_COLUMNS["adjusted_close"]))
    volume = optional_provider_int(row_value(row, YAHOO_COLUMNS["volume"]))
    dividends = optional_non_negative_float(row_value(row, YAHOO_COLUMNS["dividends"]))
    stock_splits = optional_non_negative_float(row_value(row, YAHOO_COLUMNS["stock_splits"]))

    if has_column(row, YAHOO_COLUMNS["open"]) and open_price is None:
        raise HistoricalPriceDataError("open price is not finite")
    if open_price is not None and open_price <= 0:
        raise HistoricalPriceDataError("open price is invalid")
    if adjusted_close is not None and adjusted_close <= 0:
        raise HistoricalPriceDataError("adjusted close price is invalid")
    if volume is not None and volume < 0:
        raise HistoricalPriceDataError("negative volume")
    if high < low:
        raise HistoricalPriceDataError("price relationship violation")
    if open_price is not None and (high < open_price or low > open_price):
        raise HistoricalPriceDataError("price relationship violation")
    if high < close or low > close:
        raise HistoricalPriceDataError("price relationship violation")

    return HistoricalPriceBar(
        symbol=symbol,
        trading_date=trading_date,
        open=open_price,
        high=high,
        low=low,
        close=close,
        adjusted_close=adjusted_close,
        volume=volume,
        dividends=dividends,
        stock_splits=stock_splits,
    )


def normalize_trading_date(value) -> date | None:
    if isinstance(value, pd.Timestamp):
        return value.date()
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().date()
    if isinstance(value, date):
        return value
    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def row_value(row, column: str):
    if not has_column(row, column):
        return None
    try:
        return row[column]
    except Exception:
        return None


def has_column(row, column: str) -> bool:
    return column in getattr(row, "index", [])


def required_positive_float(value, field_name: str) -> float:
    numeric_value = optional_provider_float(value)
    if numeric_value is None:
        raise HistoricalPriceDataError(f"{field_name} price is not finite")
    if numeric_value <= 0:
        raise HistoricalPriceDataError(f"{field_name} price is invalid")
    return numeric_value


def optional_positive_float(value) -> float | None:
    numeric_value = optional_provider_float(value)
    if numeric_value is None:
        return None
    if numeric_value <= 0:
        return numeric_value
    return numeric_value


def optional_non_negative_float(value) -> float | None:
    numeric_value = optional_provider_float(value)
    if numeric_value is None:
        return None
    if numeric_value < 0:
        return None
    return numeric_value


def optional_provider_float(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None

    return numeric_value


def optional_provider_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        numeric_value = float(value)
        if math.isfinite(numeric_value) and numeric_value.is_integer():
            return int(numeric_value)
    return None


def historical_price_bar_signature(bar: HistoricalPriceBar) -> tuple:
    return (
        bar.open,
        bar.high,
        bar.low,
        bar.close,
        bar.adjusted_close,
        bar.volume,
        bar.dividends,
        bar.stock_splits,
    )


def get_analysis_close(bar: HistoricalPriceBar) -> float:
    return bar.adjusted_close if bar.adjusted_close is not None else bar.close


def slice_price_series_as_of(
    series: HistoricalPriceSeries,
    as_of_date: date,
) -> HistoricalPriceSeries:
    return HistoricalPriceSeries(
        symbol=series.symbol,
        currency=series.currency,
        bars=tuple(bar for bar in series.bars if bar.trading_date <= as_of_date),
        fetched_at=series.fetched_at,
        is_stale=series.is_stale,
        source=series.source,
    )


def get_recent_bars(
    series: HistoricalPriceSeries,
    end_date: date,
    count: int,
) -> tuple[HistoricalPriceBar, ...]:
    if count <= 0:
        return tuple()

    eligible_bars = [
        bar for bar in series.bars
        if bar.trading_date <= end_date
    ]
    return tuple(eligible_bars[-count:])
