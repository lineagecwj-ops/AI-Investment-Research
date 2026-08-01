from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen

from models import Stock


LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = PROJECT_ROOT / "data" / "taiwan_company_names.json"
TAIWAN_COMPANY_NAME_CACHE_TTL = timedelta(days=7)

TWSE_LISTED_COMPANIES_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_OTC_COMPANIES_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

TAIWAN_MARKET_SUFFIXES = (".TW", ".TWO")
CODE_KEYS = ("公司代號", "有價證券代號", "證券代號", "Code", "SecuritiesCompanyCode")
NAME_KEYS = ("公司簡稱", "公司名稱", "有價證券名稱", "證券名稱", "Name", "CompanyName")

_memory_cache: dict[str, str] | None = None


@dataclass(frozen=True)
class TaiwanCompanyNameSource:

    market: str

    url: str

    symbol_suffix: str


TAIWAN_COMPANY_NAME_SOURCES = (
    TaiwanCompanyNameSource("TWSE", TWSE_LISTED_COMPANIES_URL, ".TW"),
    TaiwanCompanyNameSource("TPEx", TPEX_OTC_COMPANIES_URL, ".TWO"),
)


class CompanyNameSourceError(Exception):
    """Raised when official company name data cannot be loaded."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_taiwan_stock_symbol(symbol: str | None) -> bool:
    if not symbol:
        return False

    return symbol.upper().endswith(TAIWAN_MARKET_SUFFIXES)


def yahoo_company_name(stock: Stock) -> str:
    return stock.company_name or "N/A"


def get_display_company_name(
    stock: Stock,
    cache_path: Path | str = DEFAULT_CACHE_PATH,
) -> str:
    localized_name = get_localized_company_name(stock.symbol, cache_path=cache_path)
    if localized_name:
        return localized_name

    return yahoo_company_name(stock)


def get_localized_company_name(
    symbol: str | None,
    cache_path: Path | str = DEFAULT_CACHE_PATH,
) -> str | None:
    if not is_taiwan_stock_symbol(symbol):
        return None

    names = load_taiwan_company_names(cache_path=cache_path)
    return names.get(symbol.upper())


def load_taiwan_company_names(
    cache_path: Path | str = DEFAULT_CACHE_PATH,
    fetch_json: Callable[[str], list[dict]] = None,
    now: datetime | None = None,
) -> dict[str, str]:
    global _memory_cache

    if _memory_cache is not None:
        return _memory_cache

    resolved_now = now or utc_now()
    resolved_cache_path = Path(cache_path)
    cached_names = read_fresh_cache(resolved_cache_path, resolved_now)
    if cached_names is not None:
        _memory_cache = cached_names
        return cached_names

    stale_names = read_cache_names(resolved_cache_path)

    try:
        names = fetch_taiwan_company_names(fetch_json=fetch_json)
    except CompanyNameSourceError as exc:
        LOGGER.warning("Taiwan company name source refresh failed: %s", exc)
        _memory_cache = stale_names
        return stale_names

    try:
        write_cache(resolved_cache_path, names, resolved_now)
    except OSError as exc:
        LOGGER.warning("Taiwan company name cache write failed: %s", exc)

    _memory_cache = names
    return names


def fetch_taiwan_company_names(
    fetch_json: Callable[[str], list[dict]] = None,
) -> dict[str, str]:
    json_loader = fetch_json or request_json
    names: dict[str, str] = {}
    failures: list[str] = []

    for source in TAIWAN_COMPANY_NAME_SOURCES:
        try:
            records = json_loader(source.url)
            names.update(parse_company_name_records(records, source.symbol_suffix))
        except Exception as exc:
            failures.append(f"{source.market}: {exc}")

    if not names:
        raise CompanyNameSourceError("; ".join(failures) or "No official data returned.")

    return names


def request_json(url: str) -> list[dict]:
    try:
        with urlopen(url, timeout=10) as response:
            payload = response.read().decode("utf-8-sig")
    except (OSError, URLError) as exc:
        raise CompanyNameSourceError(str(exc)) from exc

    data = json.loads(payload)
    if not isinstance(data, list):
        raise CompanyNameSourceError("Official API response is not a list.")

    return data


def parse_company_name_records(records: list[dict], symbol_suffix: str) -> dict[str, str]:
    names = {}

    for record in records:
        if not isinstance(record, dict):
            continue

        code = first_text_value(record, CODE_KEYS)
        name = first_text_value(record, NAME_KEYS)
        if not code or not name:
            continue

        match = re.match(r"^\s*(\d+[A-Z]?)", code.strip().upper())
        if not match:
            continue

        names[f"{match.group(1)}{symbol_suffix}"] = name.strip()

    return names


def first_text_value(record: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return None


def read_fresh_cache(cache_path: Path, now: datetime) -> dict[str, str] | None:
    if not cache_path.exists():
        return None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    if now - fetched_at > TAIWAN_COMPANY_NAME_CACHE_TTL:
        return None

    names = payload.get("names")
    if not isinstance(names, dict):
        return None

    return normalize_cached_names(names)


def read_cache_names(cache_path: Path) -> dict[str, str]:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    names = payload.get("names")
    if not isinstance(names, dict):
        return {}

    return normalize_cached_names(names)


def normalize_cached_names(names: dict) -> dict[str, str]:
    normalized_names = {}

    for symbol, name in names.items():
        if not isinstance(symbol, str) or not isinstance(name, str):
            continue
        if not symbol.strip() or not name.strip():
            continue

        normalized_names[symbol.strip().upper()] = name.strip()

    return normalized_names


def write_cache(cache_path: Path, names: dict[str, str], fetched_at: datetime) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": fetched_at.isoformat(),
        "sources": [
            {"market": source.market, "url": source.url}
            for source in TAIWAN_COMPANY_NAME_SOURCES
        ],
        "names": dict(sorted(names.items())),
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_company_name_memory_cache() -> None:
    global _memory_cache

    _memory_cache = None
