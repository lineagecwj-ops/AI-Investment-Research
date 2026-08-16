from __future__ import annotations

from contextlib import redirect_stderr
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from io import StringIO
import math
from numbers import Real
import re
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from market_inputs.production_market_contracts import MarketSourceUnavailableError
from market_inputs.production_market_contracts import TechnicalCloseSeriesRequest
from market_inputs.production_market_contracts import TechnicalMarketDataProvider
from market_inputs.technical_close_observation import MarketInputValidationError
from market_inputs.technical_close_observation import TechnicalCloseObservation
from market_inputs.technical_close_observation import TechnicalCloseObservationSeries
from market_inputs.technical_close_observation import YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1


_CLOSE_COLUMN = "Close"
_ADJUSTED_CLOSE_COLUMN = "Adj Close"
_PROVIDER_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]*$")


@dataclass(frozen=True)
class YahooFinanceTechnicalCloseSeriesSource:
    """Yahoo Finance source for canonical production technical close series."""

    ticker_factory: Callable[[str], object] | None = None
    clock: Callable[[], datetime] | None = None

    def fetch(self, request: TechnicalCloseSeriesRequest) -> TechnicalCloseObservationSeries:
        if not isinstance(request, TechnicalCloseSeriesRequest):
            raise MarketInputValidationError("request must be TechnicalCloseSeriesRequest.")
        if request.provider != TechnicalMarketDataProvider.YAHOO_FINANCE_V1:
            raise MarketInputValidationError("Yahoo source only supports YAHOO_FINANCE_V1.")
        _validate_provider_symbol(request.provider_symbol)

        try:
            ticker = self._ticker_factory()(request.provider_symbol)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                frame = ticker.history(
                    interval="1d",
                    auto_adjust=False,
                    actions=True,
                    start=request.start_date.isoformat(),
                    end=(request.valuation_date + timedelta(days=1)).isoformat(),
                )
        except Exception as exc:
            raise MarketSourceUnavailableError(_safe_unavailable_message(request)) from exc

        if frame is None or getattr(frame, "empty", False):
            raise MarketSourceUnavailableError(_safe_unavailable_message(request))

        observations = _observations_from_frame(request, frame)
        if not observations:
            raise MarketSourceUnavailableError(_safe_unavailable_message(request))

        fetched_at = self._clock()()
        _require_aware_datetime(fetched_at, "fetched_at")

        series = TechnicalCloseObservationSeries(
            symbol=request.symbol,
            provider=TechnicalMarketDataProvider.YAHOO_FINANCE_V1.value,
            provider_symbol=request.provider_symbol,
            timezone=request.timezone,
            close_basis=request.close_basis,
            valuation_date=request.valuation_date,
            observations=tuple(observations),
            fetched_at=fetched_at,
            producer_version=YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1,
        )
        _verify_request_output_consistency(request, series)
        return series

    def _ticker_factory(self) -> Callable[[str], object]:
        return self.ticker_factory or yf.Ticker

    def _clock(self) -> Callable[[], datetime]:
        return self.clock or _utc_now


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _validate_provider_symbol(provider_symbol: str) -> None:
    if provider_symbol.strip() != provider_symbol:
        raise MarketInputValidationError("provider_symbol must not contain leading or trailing whitespace.")
    if provider_symbol.isdigit():
        raise MarketInputValidationError("provider_symbol must include an explicit Yahoo exchange suffix when numeric.")
    if _PROVIDER_SYMBOL_PATTERN.fullmatch(provider_symbol) is None:
        raise MarketInputValidationError("provider_symbol is not a supported Yahoo ticker identifier.")


def _observations_from_frame(
    request: TechnicalCloseSeriesRequest,
    frame: object,
) -> list[TechnicalCloseObservation]:
    if not isinstance(frame, pd.DataFrame):
        raise MarketInputValidationError("Yahoo response must be a pandas DataFrame.")
    if frame.empty:
        return []
    if isinstance(frame.columns, pd.MultiIndex):
        raise MarketInputValidationError("Yahoo response must not have MultiIndex columns.")
    if frame.columns.has_duplicates:
        raise MarketInputValidationError("Yahoo response must not contain duplicate columns.")
    if _CLOSE_COLUMN not in frame.columns:
        raise MarketInputValidationError("Yahoo response missing Close column.")

    timezone = ZoneInfo(request.timezone)
    observations: list[TechnicalCloseObservation] = []
    seen_dates: set[date] = set()
    for index_value, row in frame.iterrows():
        market_session_date = _normalize_market_session_date(index_value, timezone)
        if market_session_date < request.start_date or market_session_date > request.valuation_date:
            continue
        if market_session_date in seen_dates:
            raise MarketInputValidationError("duplicate normalized market_session_date.")
        seen_dates.add(market_session_date)
        observations.append(
            TechnicalCloseObservation(
                market_session_date=market_session_date,
                technical_close=_select_technical_close(row),
            )
        )

    if not observations:
        return observations
    if request.valuation_date not in seen_dates:
        raise MarketInputValidationError("valuation_date must exist in Yahoo response.")
    return observations


def _normalize_market_session_date(index_value: object, timezone: ZoneInfo) -> date:
    if isinstance(index_value, pd.Timestamp):
        timestamp = index_value
    elif isinstance(index_value, datetime):
        timestamp = pd.Timestamp(index_value)
    else:
        raise MarketInputValidationError("Yahoo response index must be datetime-like.")

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return timestamp.to_pydatetime().date()
    return timestamp.to_pydatetime().astimezone(timezone).date()


def _select_technical_close(row: pd.Series) -> float:
    close = _require_positive_number(row[_CLOSE_COLUMN], "Close")
    if _ADJUSTED_CLOSE_COLUMN not in row.index:
        return close

    adjusted = row[_ADJUSTED_CLOSE_COLUMN]
    if _is_missing_or_non_finite(adjusted):
        return close
    return _require_positive_number(adjusted, "Adj Close")


def _require_positive_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise MarketInputValidationError(f"{field_name} must be numeric.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise MarketInputValidationError(f"{field_name} must be finite.")
    if numeric <= 0:
        raise MarketInputValidationError(f"{field_name} must be positive.")
    return numeric


def _is_missing_or_non_finite(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        raise MarketInputValidationError("Adj Close must not be bool.")
    if not isinstance(value, Real):
        raise MarketInputValidationError("Adj Close must be numeric when present.")
    return not math.isfinite(float(value))


def _require_aware_datetime(value: object, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise MarketInputValidationError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarketInputValidationError(f"{field_name} must be timezone-aware.")


def _verify_request_output_consistency(
    request: TechnicalCloseSeriesRequest,
    series: TechnicalCloseObservationSeries,
) -> None:
    if series.symbol != request.symbol:
        raise MarketInputValidationError("output symbol mismatch.")
    if series.provider_symbol != request.provider_symbol:
        raise MarketInputValidationError("output provider_symbol mismatch.")
    if series.provider != TechnicalMarketDataProvider.YAHOO_FINANCE_V1.value:
        raise MarketInputValidationError("output provider mismatch.")
    if series.timezone != request.timezone:
        raise MarketInputValidationError("output timezone mismatch.")
    if series.close_basis != request.close_basis:
        raise MarketInputValidationError("output close_basis mismatch.")
    if series.valuation_date != request.valuation_date:
        raise MarketInputValidationError("output valuation_date mismatch.")


def _safe_unavailable_message(request: TechnicalCloseSeriesRequest) -> str:
    return (
        "Yahoo Finance technical close unavailable "
        f"provider={request.provider.value} symbol={request.symbol} "
        f"provider_symbol={request.provider_symbol} "
        f"valuation_date={request.valuation_date.isoformat()}"
    )
