from __future__ import annotations

import json
import logging
import re
import ssl
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

from company_name_service import TPEX_OTC_COMPANIES_URL
from company_name_service import TWSE_LISTED_COMPANIES_URL
from company_name_service import is_taiwan_stock_symbol
from models import Stock


LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = PROJECT_ROOT / "data" / "taiwan_company_summaries.json"
TAIWAN_COMPANY_SUMMARY_CACHE_TTL = timedelta(days=7)

GCIS_COMPANY_REGISTRATION_URL = (
    "https://data.gcis.nat.gov.tw/od/data/api/"
    "236EE382-4942-41A9-BD03-CA0709025E7C"
)

CODE_KEYS = ("公司代號", "有價證券代號", "證券代號", "Code", "SecuritiesCompanyCode")
NAME_KEYS = ("公司名稱", "公司簡稱", "有價證券名稱", "證券名稱", "Name", "CompanyName")
INDUSTRY_KEYS = ("產業別", "Industry")
BUSINESS_ACCOUNTING_KEYS = (
    "營利事業統一編號",
    "統一編號",
    "Business_Accounting_NO",
    "BusinessAccountingNo",
)
BUSINESS_ITEM_KEYS = ("Business_Item_Desc", "營業項目", "營業項目名稱", "Cmp_Business")

OFFICIAL_SECTION_TITLE = "公司登記業務概覽"
OFFICIAL_FULL_SUMMARY_TITLE = "查看完整登記營業項目"
OFFICIAL_SOURCE_NOTE = (
    "資料說明：以下內容來自台灣官方公司登記與公開基本資料，"
    "僅用於了解公司登記業務範圍，"
    "不代表各項業務的實際營收占比、主要產品或核心業務。"
)

_memory_cache: dict[str, "CompanySummaryDisplay"] | None = None


@dataclass(frozen=True)
class CompanySummaryDisplay:

    section_title: str

    short_summary: str

    full_summary: str | None

    full_summary_title: str | None

    source_note: str

    is_localized: bool

    original_yahoo_summary: str | None = None


class CompanySummarySourceError(Exception):
    """Raised when official company summary data cannot be loaded."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def build_company_summary_display(
    stock: Stock,
    cache_path: Path | str = DEFAULT_CACHE_PATH,
    fetch_json: Callable[[str], list[dict]] = None,
) -> CompanySummaryDisplay:
    english_summary = clean_text(stock.company_summary)
    localized_summary = get_localized_company_summary(
        stock,
        cache_path=cache_path,
        fetch_json=fetch_json,
    )
    if localized_summary:
        return attach_original_yahoo_summary(localized_summary, english_summary)

    if english_summary:
        return CompanySummaryDisplay(
            section_title="公司簡介",
            short_summary=shorten_summary(english_summary),
            full_summary=english_summary,
            full_summary_title="查看 Yahoo Finance 詳細公司介紹",
            source_note="公司簡介優先使用台灣官方公開資料；若無可用中文內容，則顯示 Yahoo Finance 英文介紹。",
            is_localized=False,
        )

    return CompanySummaryDisplay(
        section_title="公司簡介",
        short_summary="公司簡介目前為 N/A。",
        full_summary=None,
        full_summary_title=None,
        source_note="目前沒有可顯示的公司簡介資料。",
        is_localized=False,
    )


def get_localized_company_summary(
    stock: Stock,
    cache_path: Path | str = DEFAULT_CACHE_PATH,
    fetch_json: Callable[[str], list[dict]] = None,
) -> CompanySummaryDisplay | None:
    if not stock.symbol or not is_taiwan_stock_symbol(stock.symbol):
        return None

    symbol = stock.symbol.upper()
    resolved_cache_path = Path(cache_path)
    summaries = load_taiwan_company_summaries(cache_path=resolved_cache_path)
    if symbol in summaries:
        return summaries[symbol]

    try:
        summary = fetch_taiwan_company_summary(symbol, fetch_json=fetch_json)
    except CompanySummarySourceError as exc:
        LOGGER.warning("Taiwan company summary source refresh failed: %s", exc)
        return None

    summaries[symbol] = summary
    update_memory_cache(summaries)

    try:
        write_cache(resolved_cache_path, summaries, utc_now())
    except OSError as exc:
        LOGGER.warning("Taiwan company summary cache write failed: %s", exc)

    return summary


def load_taiwan_company_summaries(
    cache_path: Path | str = DEFAULT_CACHE_PATH,
    fetch_json: Callable[[str], list[dict]] = None,
    now: datetime | None = None,
) -> dict[str, CompanySummaryDisplay]:
    global _memory_cache

    if _memory_cache is not None:
        return _memory_cache

    resolved_now = now or utc_now()
    resolved_cache_path = Path(cache_path)
    cached_summaries = read_fresh_cache(resolved_cache_path, resolved_now)
    if cached_summaries is not None:
        _memory_cache = cached_summaries
        return cached_summaries

    stale_summaries = read_cache_summaries(resolved_cache_path)
    _memory_cache = stale_summaries
    return stale_summaries


def fetch_taiwan_company_summary(
    symbol: str,
    fetch_json: Callable[[str], list[dict]] = None,
) -> CompanySummaryDisplay:
    json_loader = fetch_json or request_json
    profile = fetch_taiwan_company_profile(symbol, fetch_json=json_loader)
    business_no = profile.get("business_accounting_no")
    if not business_no:
        raise CompanySummarySourceError(f"{symbol} profile does not include business accounting number.")

    records = json_loader(build_gcis_company_registration_url(business_no))
    business_items = parse_business_items(records)
    if not business_items:
        raise CompanySummarySourceError(
            f"{symbol} has no parsed MOEA business items from company registration response."
        )

    return build_official_summary(profile, business_items)


def fetch_taiwan_company_profile(
    symbol: str,
    fetch_json: Callable[[str], list[dict]],
) -> dict[str, str | None]:
    normalized_symbol = symbol.upper()
    failures: list[str] = []

    for url, suffix, market in [
        (TWSE_LISTED_COMPANIES_URL, ".TW", "TWSE"),
        (TPEX_OTC_COMPANIES_URL, ".TWO", "TPEx"),
    ]:
        if not normalized_symbol.endswith(suffix):
            continue

        try:
            profiles = parse_company_profile_records(fetch_json(url), suffix)
        except Exception as exc:
            failures.append(f"{market}: {exc}")
            continue

        if normalized_symbol in profiles:
            return profiles[normalized_symbol]

    raise CompanySummarySourceError("; ".join(failures) or f"{symbol} not found in official profile data.")


def request_json(url: str) -> list[dict]:
    try:
        with urlopen(url, timeout=10) as response:
            payload = response.read().decode("utf-8-sig")
    except HTTPError as exc:
        raise CompanySummarySourceError(f"HTTP {exc.code} while requesting {url}") from exc
    except (OSError, URLError) as exc:
        raise CompanySummarySourceError(describe_transport_error(url, exc)) from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CompanySummarySourceError(f"Invalid JSON response from {url}: {exc}") from exc

    if not isinstance(data, list):
        raise CompanySummarySourceError(f"Official API response from {url} is not a list.")

    return data


def parse_company_profile_records(records: list[dict], symbol_suffix: str) -> dict[str, dict[str, str | None]]:
    profiles = {}

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

        symbol = f"{match.group(1)}{symbol_suffix}"
        profiles[symbol] = {
            "symbol": symbol,
            "code": match.group(1),
            "name": name,
            "industry": first_text_value(record, INDUSTRY_KEYS),
            "business_accounting_no": first_text_value(record, BUSINESS_ACCOUNTING_KEYS),
        }

    return profiles


def build_gcis_company_registration_url(business_accounting_no: str) -> str:
    filter_value = quote(f"Business_Accounting_NO eq {business_accounting_no}", safe="")
    return f"{GCIS_COMPANY_REGISTRATION_URL}?$format=json&$filter={filter_value}&$skip=0&$top=100"


def parse_business_items(records: list[dict]) -> list[str]:
    items = []
    seen = set()

    for record in records:
        if not isinstance(record, dict):
            continue

        candidate_items = extract_business_item_candidates(record)

        for item in candidate_items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            items.append(normalized)

    return items


def extract_business_item_candidates(record: dict) -> list[str]:
    candidates = []

    nested_business_items = record.get("Cmp_Business")
    if isinstance(nested_business_items, list):
        for item_record in nested_business_items:
            if not isinstance(item_record, dict):
                continue

            item = first_text_value(item_record, BUSINESS_ITEM_KEYS)
            if item:
                candidates.append(item)

    item = first_text_value(record, BUSINESS_ITEM_KEYS)
    if item:
        candidates.append(item)

    return candidates


def describe_transport_error(url: str, error: Exception) -> str:
    reason = error.reason if isinstance(error, URLError) else error

    if isinstance(reason, ssl.SSLCertVerificationError):
        return f"TLS certificate verification failed while requesting {url}: {reason}"

    return f"Transport error while requesting {url}: {error}"


def build_official_summary(
    profile: dict[str, str | None],
    business_items: list[str],
) -> CompanySummaryDisplay:
    name = profile["name"] or profile["symbol"]
    code = profile["code"] or profile["symbol"]
    industry = profile.get("industry")
    highlighted_items = business_items[:4]
    item_text = "、".join(highlighted_items)
    industry_text = build_industry_text(industry)
    short_summary = (
        f"{name}（{code}）{industry_text}依台灣官方公開資料，"
        f"登記營業項目包含：{item_text}。"
    )
    full_summary = (
        short_summary
        + "\n\n官方登記營業項目：\n"
        + "\n".join(f"- {item}" for item in business_items)
    )

    return CompanySummaryDisplay(
        section_title=OFFICIAL_SECTION_TITLE,
        short_summary=short_summary,
        full_summary=full_summary,
        full_summary_title=OFFICIAL_FULL_SUMMARY_TITLE,
        source_note=OFFICIAL_SOURCE_NOTE,
        is_localized=True,
    )


def first_text_value(record: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def build_industry_text(industry: str | None) -> str:
    if not industry:
        return ""

    normalized = industry.strip()
    if not normalized or normalized.isdigit():
        return ""

    return f"屬於 {normalized} 產業，"


def shorten_summary(summary: str, max_sentences: int = 3, max_chars: int = 360) -> str:
    cleaned_summary = clean_text(summary)
    if not cleaned_summary:
        return "公司簡介目前為 N/A。"

    sentences = re.split(r"(?<=[.!?。！？])\s+", cleaned_summary)
    short_summary = " ".join(sentence for sentence in sentences[:max_sentences] if sentence).strip()
    if not short_summary:
        short_summary = cleaned_summary

    if len(short_summary) <= max_chars:
        return short_summary

    return short_summary[:max_chars].rstrip() + "..."


def clean_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""

    return re.sub(r"\s+", " ", value).strip()


def read_fresh_cache(cache_path: Path, now: datetime) -> dict[str, CompanySummaryDisplay] | None:
    if not cache_path.exists():
        return None

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    if now - fetched_at > TAIWAN_COMPANY_SUMMARY_CACHE_TTL:
        return None

    return parse_cached_summaries(payload.get("summaries"))


def read_cache_summaries(cache_path: Path) -> dict[str, CompanySummaryDisplay]:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return parse_cached_summaries(payload.get("summaries")) or {}


def parse_cached_summaries(payload) -> dict[str, CompanySummaryDisplay] | None:
    if not isinstance(payload, dict):
        return None

    summaries = {}
    for symbol, data in payload.items():
        if not isinstance(symbol, str) or not isinstance(data, dict):
            continue

        short_summary = data.get("short_summary")
        source_note = data.get("source_note")
        is_localized = data.get("is_localized")
        if not isinstance(short_summary, str) or not isinstance(source_note, str):
            continue

        localized = bool(is_localized)
        summaries[symbol.strip().upper()] = CompanySummaryDisplay(
            section_title=OFFICIAL_SECTION_TITLE
            if localized
            else (
                data.get("section_title")
                if isinstance(data.get("section_title"), str)
                else "公司簡介"
            ),
            short_summary=short_summary,
            full_summary=data.get("full_summary") if isinstance(data.get("full_summary"), str) else None,
            full_summary_title=OFFICIAL_FULL_SUMMARY_TITLE
            if localized
            else (
                data.get("full_summary_title")
                if isinstance(data.get("full_summary_title"), str)
                else None
            ),
            source_note=OFFICIAL_SOURCE_NOTE if localized else source_note,
            is_localized=localized,
        )

    return summaries


def write_cache(
    cache_path: Path,
    summaries: dict[str, CompanySummaryDisplay],
    fetched_at: datetime,
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": fetched_at.isoformat(),
        "sources": [
            {"name": "TWSE listed company profile", "url": TWSE_LISTED_COMPANIES_URL},
            {"name": "TPEx OTC company profile", "url": TPEX_OTC_COMPANIES_URL},
            {"name": "MOEA company registration business items", "url": GCIS_COMPANY_REGISTRATION_URL},
        ],
        "summaries": {
            symbol: {
                "section_title": summary.section_title,
                "short_summary": summary.short_summary,
                "full_summary": summary.full_summary,
                "full_summary_title": summary.full_summary_title,
                "source_note": summary.source_note,
                "is_localized": summary.is_localized,
            }
            for symbol, summary in sorted(summaries.items())
        },
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_company_summary_memory_cache() -> None:
    global _memory_cache

    _memory_cache = None


def update_memory_cache(summaries: dict[str, CompanySummaryDisplay]) -> None:
    global _memory_cache

    _memory_cache = summaries


def attach_original_yahoo_summary(
    display: CompanySummaryDisplay,
    original_yahoo_summary: str,
) -> CompanySummaryDisplay:
    if not original_yahoo_summary:
        return display

    return CompanySummaryDisplay(
        section_title=display.section_title,
        short_summary=display.short_summary,
        full_summary=display.full_summary,
        full_summary_title=display.full_summary_title,
        source_note=display.source_note,
        is_localized=display.is_localized,
        original_yahoo_summary=original_yahoo_summary,
    )
