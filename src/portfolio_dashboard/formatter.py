from datetime import date
from datetime import datetime
from enum import Enum


EMPTY_DISPLAY = "N/A"
FORBIDDEN_DISPLAY_TERMS = (
    "buy",
    "sell",
    "hold",
    "entry",
    "exit",
    "take profit",
    "stop loss",
    "買進",
    "賣出",
    "持有",
    "進場",
    "出場",
    "停利",
    "停損",
    "推薦",
    "建議買",
    "建議賣",
)


def format_value(value) -> str:
    if value is None:
        return EMPTY_DISPLAY
    if isinstance(value, Enum):
        return format_enum(value)
    if isinstance(value, datetime):
        return format_datetime(value)
    if isinstance(value, date):
        return format_date(value)
    return str(value)


def format_enum(value: Enum) -> str:
    return str(value.value)


def format_datetime(value: datetime) -> str:
    return value.isoformat()


def format_date(value: date) -> str:
    return value.isoformat()


def format_checksum(value: str | None) -> str:
    if not value:
        return EMPTY_DISPLAY
    return value


def format_optional_checksum(value: str | None) -> str:
    return format_checksum(value)


def contains_forbidden_wording(text: str) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in FORBIDDEN_DISPLAY_TERMS)


def validate_no_forbidden_wording(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_DISPLAY_TERMS:
        if term.lower() in lowered:
            raise ValueError(f"Display text contains forbidden term: {term}")
