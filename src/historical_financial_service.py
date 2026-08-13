from contextlib import redirect_stderr
from contextlib import redirect_stdout
from datetime import date
from datetime import datetime
from io import StringIO
import logging
import math
from numbers import Real
from pathlib import Path

import yfinance as yf

from database import log_cache_warning
from live_data_store import LiveDataStore
from models import HistoricalFinancialPeriod
from models import HistoricalFinancialSeries
from stock_service import optional_text


class HistoricalFinancialServiceError(Exception):
    """Base error for historical financial data lookup failures."""


FIELD_ALIASES = {
    "revenue": ["Total Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "eps": ["Diluted EPS", "Basic EPS"],
    "operating_cash_flow": ["Operating Cash Flow"],
    "capital_expenditure": ["Capital Expenditure"],
    "free_cash_flow": ["Free Cash Flow"],
    "total_assets": ["Total Assets"],
    "total_debt": ["Total Debt"],
    "total_equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    "cash_and_cash_equivalents": [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
    ],
}


INCOME_STATEMENT_FIELDS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps",
]

CASHFLOW_FIELDS = [
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
]

BALANCE_SHEET_FIELDS = [
    "total_assets",
    "total_debt",
    "total_equity",
    "cash_and_cash_equivalents",
]


def get_historical_financials(
    symbol: str,
    db_path: Path | str | None = None,
    live_store: LiveDataStore | None = None,
) -> HistoricalFinancialSeries:
    store = live_store or LiveDataStore(db_path=db_path)
    cached_series = store.get_cached_historical_financials(symbol)
    if cached_series is not None:
        return cached_series

    try:
        series = fetch_historical_financials_from_yahoo(symbol)
    except Exception as exc:
        stale_series = store.get_cached_historical_financials(
            symbol,
            include_expired=True,
        )
        if stale_series is not None:
            stale_series.is_stale = True
            log_cache_warning("Yahoo historical financial refresh failed; using stale cache", exc)
            return stale_series
        if isinstance(exc, HistoricalFinancialServiceError):
            raise
        raise HistoricalFinancialServiceError(
            "Yahoo Finance historical financial 查詢失敗，請稍後再試。"
        ) from exc

    try:
        store.save_historical_financials(series)
    except Exception as exc:
        log_cache_warning("SQLite historical financial cache write failed", exc)

    return series


def fetch_historical_financials_from_yahoo(symbol: str) -> HistoricalFinancialSeries:
    try:
        ticker = yf.Ticker(symbol)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            info = ticker.info
            income_stmt = ticker.income_stmt
            cashflow = ticker.cashflow
            balance_sheet = ticker.balance_sheet
    except (OSError, TimeoutError) as exc:
        raise HistoricalFinancialServiceError(
            "Yahoo Finance historical financial 查詢失敗，請確認網路連線後再試。"
        ) from exc
    except Exception as exc:
        raise HistoricalFinancialServiceError(
            "Yahoo Finance historical financial 查詢失敗，請稍後再試。"
        ) from exc

    currency = None
    if isinstance(info, dict):
        currency = optional_text(info.get("financialCurrency")) or optional_text(info.get("currency"))

    return build_historical_financial_series(
        symbol=symbol,
        currency=currency,
        income_stmt=income_stmt,
        cashflow=cashflow,
        balance_sheet=balance_sheet,
    )


def build_historical_financial_series(
    symbol: str,
    currency: str | None,
    income_stmt=None,
    cashflow=None,
    balance_sheet=None,
) -> HistoricalFinancialSeries:
    period_ends = sorted(
        {
            period_end
            for statement in [income_stmt, cashflow, balance_sheet]
            for period_end in statement_period_ends(statement)
        }
    )

    periods = [
        build_historical_financial_period(
            symbol=symbol,
            currency=currency,
            period_end=period_end,
            income_stmt=income_stmt,
            cashflow=cashflow,
            balance_sheet=balance_sheet,
        )
        for period_end in period_ends
    ]
    periods = [period for period in periods if has_modeled_financial_value(period)]

    return HistoricalFinancialSeries(
        symbol=symbol,
        currency=currency,
        periods=periods,
    )


def build_historical_financial_period(
    symbol: str,
    currency: str | None,
    period_end: date,
    income_stmt=None,
    cashflow=None,
    balance_sheet=None,
) -> HistoricalFinancialPeriod:
    income_values = {
        field: statement_value(income_stmt, field, period_end)
        for field in INCOME_STATEMENT_FIELDS
    }
    cashflow_values = {
        field: statement_value(cashflow, field, period_end)
        for field in CASHFLOW_FIELDS
    }
    balance_sheet_values = {
        field: statement_value(balance_sheet, field, period_end)
        for field in BALANCE_SHEET_FIELDS
    }

    free_cash_flow = cashflow_values["free_cash_flow"]
    if free_cash_flow is None:
        free_cash_flow = calculate_free_cash_flow(
            cashflow_values["operating_cash_flow"],
            cashflow_values["capital_expenditure"],
        )

    return HistoricalFinancialPeriod(
        symbol=symbol,
        period_end=period_end,
        period_year=period_end.year,
        currency=currency,
        revenue=income_values["revenue"],
        gross_profit=income_values["gross_profit"],
        operating_income=income_values["operating_income"],
        net_income=income_values["net_income"],
        eps=income_values["eps"],
        gross_margin=calculate_margin(income_values["gross_profit"], income_values["revenue"]),
        operating_margin=calculate_margin(
            income_values["operating_income"],
            income_values["revenue"],
        ),
        net_margin=calculate_margin(income_values["net_income"], income_values["revenue"]),
        operating_cash_flow=cashflow_values["operating_cash_flow"],
        capital_expenditure=cashflow_values["capital_expenditure"],
        free_cash_flow=free_cash_flow,
        total_assets=balance_sheet_values["total_assets"],
        total_debt=balance_sheet_values["total_debt"],
        total_equity=balance_sheet_values["total_equity"],
        cash_and_cash_equivalents=balance_sheet_values["cash_and_cash_equivalents"],
    )


def statement_value(statement, field: str, period_end: date) -> float | None:
    if is_empty_statement(statement):
        return None

    column = find_statement_column(statement, period_end)
    if column is None:
        return None

    row_label = find_statement_row(statement, FIELD_ALIASES[field])
    if row_label is None:
        return None

    try:
        value = statement.loc[row_label, column]
    except Exception as exc:
        logging.debug("Unable to read historical statement value: %s", exc)
        return None

    if hasattr(value, "iloc"):
        if len(value) == 0:
            return None
        value = value.iloc[0]

    return optional_number(value)


def statement_period_ends(statement) -> list[date]:
    if is_empty_statement(statement):
        return []

    period_ends = []
    seen = set()
    for column in statement.columns:
        period_end = normalize_period_end(column)
        if period_end is None or period_end in seen:
            continue
        period_ends.append(period_end)
        seen.add(period_end)

    return period_ends


def find_statement_column(statement, period_end: date):
    for column in statement.columns:
        if normalize_period_end(column) == period_end:
            return column
    return None


def find_statement_row(statement, aliases: list[str]):
    normalized_rows = {
        str(row_label).strip().lower(): row_label
        for row_label in statement.index
    }

    for alias in aliases:
        row_label = normalized_rows.get(alias.strip().lower())
        if row_label is not None:
            return row_label

    return None


def normalize_period_end(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        return to_pydatetime().date()

    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def optional_number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None

    return numeric_value


def calculate_margin(numerator: float | None, revenue: float | None) -> float | None:
    if numerator is None or revenue is None or revenue == 0:
        return None
    if not math.isfinite(numerator) or not math.isfinite(revenue):
        return None

    return numerator / revenue


def calculate_free_cash_flow(
    operating_cash_flow: float | None,
    capital_expenditure: float | None,
) -> float | None:
    if operating_cash_flow is None or capital_expenditure is None:
        return None
    if not math.isfinite(operating_cash_flow) or not math.isfinite(capital_expenditure):
        return None

    return operating_cash_flow + capital_expenditure


def has_modeled_financial_value(period: HistoricalFinancialPeriod) -> bool:
    field_names = [
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "eps",
        "operating_cash_flow",
        "capital_expenditure",
        "free_cash_flow",
        "total_assets",
        "total_debt",
        "total_equity",
        "cash_and_cash_equivalents",
    ]

    return any(getattr(period, field_name) is not None for field_name in field_names)


def is_empty_statement(statement) -> bool:
    if statement is None:
        return True

    empty = getattr(statement, "empty", True)
    return bool(empty)
