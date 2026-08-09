from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from database import DEFAULT_DB_PATH
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_END
from volume_threshold_robustness_service import DEFAULT_OBSERVATION_START
from volume_threshold_robustness_service import DEFAULT_OUTCOME_HORIZON_BARS
from volume_threshold_robustness_service import DEFAULT_WARMUP_TRADING_BARS


UNIVERSE_VERSION = "2026-08-current-etf-constituent-v1"
SOURCE_STATUS_AVAILABLE = "AVAILABLE"
SOURCE_STATUS_UNAVAILABLE = "SOURCE_UNAVAILABLE"
SOURCE_STATUS_AVAILABLE_HOLDINGS_ENDPOINT_UNRESOLVED = "SOURCE_AVAILABLE_HOLDINGS_ENDPOINT_UNRESOLVED"
SOURCE_STATUS_NOT_RETRIEVED = "NOT_RETRIEVED"
PARSER_STATUS_NOT_RUN = "PARSER_NOT_RUN"
PARSER_STATUS_PARSED = "PARSED"
PARSER_STATUS_FAILED = "PARSER_FAILED"
TRANSPORT_REQUESTS_VERIFIED = "TRANSPORT_REQUESTS_VERIFIED"
TRANSPORT_CURL_VERIFIED = "TRANSPORT_CURL_VERIFIED"
UNIVERSE_STATUS_NOT_FINALIZED = "NOT_FINALIZED"
UNIVERSE_STATUS_FINALIZED = "FINALIZED"
COMPLETENESS_UNKNOWN = "COMPLETENESS_UNKNOWN"
PARSED_INCOMPLETE = "PARSED_INCOMPLETE"
PARSED_COMPLETE = "PARSED_COMPLETE"
SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS = "issuer_official_holdings"
SOURCE_TYPE_ISSUER_OFFICIAL_PCF = "issuer_official_pcf"

COVERAGE_AVAILABLE_LOCAL = "AVAILABLE_LOCAL"
COVERAGE_MISSING_LOCAL = "MISSING_LOCAL"
COVERAGE_INSUFFICIENT = "INSUFFICIENT_COVERAGE"
COVERAGE_INVALID_SYMBOL = "INVALID_SYMBOL"

EXCLUSION_NON_STOCK = "NON_STOCK"
EXCLUSION_INVALID_SYMBOL = "INVALID_SYMBOL"
EXCLUSION_UNKNOWN_EXCHANGE = "UNKNOWN_EXCHANGE"

TWSE = "TWSE"
TPEX = "TPEx"

_TWSE_CODES = frozenset(
    {
        "0050",
        "0051",
        "0052",
        "0056",
        "1101",
        "1102",
        "1216",
        "1301",
        "1303",
        "1402",
        "2002",
        "2303",
        "2308",
        "2317",
        "2327",
        "2330",
        "2337",
        "2345",
        "2357",
        "2379",
        "2382",
        "2383",
        "2404",
        "2454",
        "2880",
        "2881",
        "2882",
        "2883",
        "2884",
        "2885",
        "2886",
        "2887",
        "2890",
        "2891",
        "3711",
        "3037",
    }
)

_TPEX_CODES = frozenset({"6488"})
_NON_STOCK_IDENTIFIERS = frozenset({"CASH", "TX", "NYF", "ETF", "BOND", "FUTURE"})
_OFFICIAL_EXPECTED_CONSTITUENT_COUNTS = MappingProxyType({"0050": 50, "0051": 100, "0056": 50})


class ETFConstituentUniverseError(Exception):
    """Raised when ETF constituent universe inputs are not valid."""


@dataclass(frozen=True)
class ETFUniverseSource:

    etf_code: str

    etf_name: str

    issuer: str

    category: str

    official_source_url: str

    source_type: str

    source_status: str = SOURCE_STATUS_NOT_RETRIEVED

    holdings_date: date | None = None

    retrieved_date: date | None = None

    raw_constituent_count: int = 0

    unavailable_reason: str | None = None

    parser_status: str = PARSER_STATUS_NOT_RUN

    parser_error: str | None = None

    completeness_status: str = COMPLETENESS_UNKNOWN

    official_expected_count: int | None = None

    visible_preview_count: int = 0

    full_row_count: int = 0

    dedup_constituent_count: int = 0

    source_semantics: str | None = None


@dataclass(frozen=True)
class OfficialSourceAccessAudit:

    etf_code: str

    canonical_url: str

    http_status: int | None

    final_url: str | None

    tls_verified: bool

    source_access_status: str

    page_title: str | None

    constituent_table_available: bool

    holdings_date: date | None

    parser_status: str

    raw_constituent_count: int

    transport_method: str | None = None

    raw_dom_stock_row_count: int = 0

    full_row_count: int = 0

    dedup_constituent_count: int = 0

    official_expected_count: int | None = None

    completeness_status: str = COMPLETENESS_UNKNOWN

    source_semantics: str | None = None

    error: str | None = None


@dataclass(frozen=True)
class ETFConstituentRecord:

    etf_code: str

    stock_code: str

    stock_name: str

    raw_market_info: str | None = None

    raw_weight: float | None = None

    holdings_date: date | None = None

    source_url: str | None = None


@dataclass(frozen=True)
class ETFConstituentSnapshot:

    source: ETFUniverseSource

    constituents: tuple[ETFConstituentRecord, ...]


@dataclass(frozen=True)
class ETFConstituentMembership:

    symbol: str

    stock_code: str

    stock_name: str

    exchange: str

    source_etfs: tuple[str, ...]

    etf_membership_count: int


@dataclass(frozen=True)
class ETFConstituentExclusion:

    raw_identifier: str

    source_etf: str

    reason: str

    detail: str | None = None


@dataclass(frozen=True)
class FrozenETFUniverse:

    universe_version: str

    sources: tuple[ETFUniverseSource, ...]

    memberships: tuple[ETFConstituentMembership, ...]

    exclusions: tuple[ETFConstituentExclusion, ...]

    retrieval_timestamps: tuple[datetime, ...]

    holdings_dates: tuple[date, ...]

    raw_membership_count: int

    normalized_membership_count: int

    unique_stock_count: int

    dedup_count: int

    twse_count: int

    tpex_count: int

    excluded_count: int


@dataclass(frozen=True)
class PartialParsedUniverseAudit:

    universe_version: str

    universe_status: str

    parsed_source_count: int

    raw_membership_count: int

    normalized_membership_count: int

    unique_stock_count: int

    excluded_count: int

    blocker: str | None


@dataclass(frozen=True)
class ETFUniverseFinalizationAudit:

    universe_version: str

    universe_status: str

    complete_source_count: int

    incomplete_source_count: int

    unresolved_source_count: int

    blocker: str | None


@dataclass(frozen=True)
class SymbolCoverageAudit:

    symbol: str

    coverage_status: str

    earliest_raw_price_date: date | None

    latest_raw_price_date: date | None

    total_rows: int

    observation_window_rows: int

    warmup_available_bars: int

    post_window_available_bars: int

    duplicate_date_count: int

    invalid_ohlcv_rows: int

    detail: str | None = None


@dataclass(frozen=True)
class DatabaseFileAudit:

    path: str

    size_bytes: int

    mtime_ns: int

    sha256: str


@dataclass(frozen=True)
class ETFUniverseBuildResult:

    universe: FrozenETFUniverse

    coverage_audits: tuple[SymbolCoverageAudit, ...]

    db_before: DatabaseFileAudit | None

    db_after: DatabaseFileAudit | None


PREDEFINED_ETF_SOURCES = (
    ETFUniverseSource(
        etf_code="0050",
        etf_name="元大台灣50",
        issuer="元大投信",
        category="大型權值",
        official_source_url="https://www.yuantaetfs.com/tradeInfo/pcf/0050",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_PCF,
    ),
    ETFUniverseSource(
        etf_code="0051",
        etf_name="元大中型100",
        issuer="元大投信",
        category="中型股 breadth",
        official_source_url="https://www.yuantaetfs.com/tradeInfo/pcf/0051",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_PCF,
    ),
    ETFUniverseSource(
        etf_code="0052",
        etf_name="富邦科技",
        issuer="富邦投信",
        category="科技",
        official_source_url="https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=0052",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="0056",
        etf_name="元大高股息",
        issuer="元大投信",
        category="高股息",
        official_source_url="https://www.yuantaetfs.com/tradeInfo/pcf/0056",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_PCF,
    ),
    ETFUniverseSource(
        etf_code="00733",
        etf_name="富邦臺灣中小",
        issuer="富邦投信",
        category="中小型 / 動能",
        official_source_url="https://websys.fsit.com.tw/FubonETF/Fund/Assets.aspx?stkId=00733",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="00878",
        etf_name="國泰永續高股息",
        issuer="國泰投信",
        category="ESG + 高股息",
        official_source_url=(
            "https://www.cathaysite.com.tw/ETF/purchase?"
            "code=CN&name=Cathay+MSCI+Taiwan+ESG+Sustainability+High+Dividend+Yield+ETF"
        ),
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="00919",
        etf_name="群益台灣精選高息",
        issuer="群益投信",
        category="另一套高股息 selection methodology",
        official_source_url="https://www.capitalfund.com.tw/etf/product/detail/195/portfolio",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="00936",
        etf_name="台新永續高息中小",
        issuer="台新投信",
        category="上市 + 上櫃中小型 / ESG / 高息",
        official_source_url="https://www.tsit.com.tw/ETF/Home/ETFSeriesDetail/00936",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
)


def predefined_etf_sources() -> tuple[ETFUniverseSource, ...]:
    return PREDEFINED_ETF_SOURCES


def mark_sources_unavailable(
    *,
    reason_by_etf: dict[str, str] | None = None,
    retrieved_date: date | None = None,
) -> tuple[ETFUniverseSource, ...]:
    reasons = MappingProxyType(dict(reason_by_etf or {}))
    stamp = retrieved_date or datetime.now(UTC).date()
    return tuple(
        ETFUniverseSource(
            etf_code=source.etf_code,
            etf_name=source.etf_name,
            issuer=source.issuer,
            category=source.category,
            official_source_url=source.official_source_url,
            source_type=source.source_type,
            source_status=SOURCE_STATUS_UNAVAILABLE,
            holdings_date=None,
            retrieved_date=stamp,
            raw_constituent_count=0,
            unavailable_reason=reasons.get(source.etf_code, "Official source was not available in this run."),
            parser_status=PARSER_STATUS_NOT_RUN,
            completeness_status=COMPLETENESS_UNKNOWN,
        )
        for source in PREDEFINED_ETF_SOURCES
    )


def build_frozen_etf_universe(
    snapshots,
    *,
    universe_version: str = UNIVERSE_VERSION,
    retrieved_at: datetime | None = None,
) -> FrozenETFUniverse:
    snapshot_tuple = tuple(snapshots)
    _validate_snapshot_sources(snapshot_tuple)
    retrieved_at = retrieved_at or datetime.now(UTC)

    normalized_by_symbol: dict[str, ETFConstituentMembership] = {}
    source_etfs_by_symbol: dict[str, list[str]] = {}
    exclusions: list[ETFConstituentExclusion] = []
    raw_membership_count = 0
    normalized_membership_count = 0

    for snapshot in snapshot_tuple:
        raw_membership_count += len(snapshot.constituents)
        for record in snapshot.constituents:
            normalized = normalize_constituent_record(record)
            if isinstance(normalized, ETFConstituentExclusion):
                exclusions.append(normalized)
                continue
            normalized_membership_count += 1
            source_etfs_by_symbol.setdefault(normalized.symbol, []).append(record.etf_code)
            existing = normalized_by_symbol.get(normalized.symbol)
            if existing is None:
                normalized_by_symbol[normalized.symbol] = normalized
            elif existing.stock_name != normalized.stock_name:
                normalized_by_symbol[normalized.symbol] = ETFConstituentMembership(
                    symbol=existing.symbol,
                    stock_code=existing.stock_code,
                    stock_name=existing.stock_name,
                    exchange=existing.exchange,
                    source_etfs=existing.source_etfs,
                    etf_membership_count=existing.etf_membership_count,
                )

    memberships = []
    for symbol in sorted(normalized_by_symbol):
        membership = normalized_by_symbol[symbol]
        source_etfs = tuple(sorted(set(source_etfs_by_symbol[symbol]), key=_etf_order_index))
        memberships.append(
            ETFConstituentMembership(
                symbol=membership.symbol,
                stock_code=membership.stock_code,
                stock_name=membership.stock_name,
                exchange=membership.exchange,
                source_etfs=source_etfs,
                etf_membership_count=len(source_etfs),
            )
        )

    sources = tuple(snapshot.source for snapshot in snapshot_tuple)
    holdings_dates = tuple(
        sorted({source.holdings_date for source in sources if source.holdings_date is not None})
    )
    retrieval_timestamps = (retrieved_at,)
    twse_count = sum(1 for membership in memberships if membership.exchange == TWSE)
    tpex_count = sum(1 for membership in memberships if membership.exchange == TPEX)
    return FrozenETFUniverse(
        universe_version=universe_version,
        sources=sources,
        memberships=tuple(memberships),
        exclusions=tuple(exclusions),
        retrieval_timestamps=retrieval_timestamps,
        holdings_dates=holdings_dates,
        raw_membership_count=raw_membership_count,
        normalized_membership_count=normalized_membership_count,
        unique_stock_count=len(memberships),
        dedup_count=normalized_membership_count - len(memberships),
        twse_count=twse_count,
        tpex_count=tpex_count,
        excluded_count=len(exclusions),
    )


def build_source_unavailable_universe(
    *,
    reason_by_etf: dict[str, str] | None = None,
    retrieved_at: datetime | None = None,
) -> FrozenETFUniverse:
    retrieved_at = retrieved_at or datetime.now(UTC)
    sources = mark_sources_unavailable(
        reason_by_etf=reason_by_etf,
        retrieved_date=retrieved_at.date(),
    )
    return FrozenETFUniverse(
        universe_version=UNIVERSE_VERSION,
        sources=sources,
        memberships=tuple(),
        exclusions=tuple(),
        retrieval_timestamps=(retrieved_at,),
        holdings_dates=tuple(),
        raw_membership_count=0,
        normalized_membership_count=0,
        unique_stock_count=0,
        dedup_count=0,
        twse_count=0,
        tpex_count=0,
        excluded_count=0,
    )


def audit_etf_universe_finalization(
    audits: tuple[OfficialSourceAccessAudit, ...],
    *,
    required_source_count: int = 8,
) -> ETFUniverseFinalizationAudit:
    complete = sum(1 for audit in audits if audit.completeness_status == PARSED_COMPLETE)
    incomplete = sum(1 for audit in audits if audit.completeness_status == PARSED_INCOMPLETE)
    unresolved = sum(
        1
        for audit in audits
        if audit.completeness_status != PARSED_COMPLETE and audit.completeness_status != PARSED_INCOMPLETE
    )
    blocker = None
    status = UNIVERSE_STATUS_FINALIZED
    if complete != required_source_count or len(audits) != required_source_count:
        status = UNIVERSE_STATUS_NOT_FINALIZED
        blocker = (
            f"Final frozen ETF universe requires {required_source_count}/{required_source_count} "
            f"PARSED_COMPLETE sources; got {complete}/{required_source_count}."
        )
    return ETFUniverseFinalizationAudit(
        universe_version=UNIVERSE_VERSION,
        universe_status=status,
        complete_source_count=complete,
        incomplete_source_count=incomplete,
        unresolved_source_count=unresolved,
        blocker=blocker,
    )


def normalize_constituent_record(
    record: ETFConstituentRecord,
) -> ETFConstituentMembership | ETFConstituentExclusion:
    raw_code = str(record.stock_code).strip().upper()
    raw_name = record.stock_name.strip()
    if not raw_code:
        return ETFConstituentExclusion(
            raw_identifier=record.stock_code,
            source_etf=record.etf_code,
            reason=EXCLUSION_INVALID_SYMBOL,
            detail="Empty stock code.",
        )
    if raw_code in _NON_STOCK_IDENTIFIERS or _is_non_stock_name(raw_name):
        return ETFConstituentExclusion(
            raw_identifier=raw_code,
            source_etf=record.etf_code,
            reason=EXCLUSION_NON_STOCK,
            detail=raw_name or record.raw_market_info,
        )
    if not (raw_code.isdigit() and len(raw_code) == 4):
        return ETFConstituentExclusion(
            raw_identifier=raw_code,
            source_etf=record.etf_code,
            reason=EXCLUSION_INVALID_SYMBOL,
            detail="Taiwan common stock code must be four digits.",
        )

    exchange = infer_exchange(raw_code, record.raw_market_info)
    if exchange is None:
        return ETFConstituentExclusion(
            raw_identifier=raw_code,
            source_etf=record.etf_code,
            reason=EXCLUSION_UNKNOWN_EXCHANGE,
            detail="No official market metadata or existing normalization rule mapped this code.",
        )
    suffix = "TW" if exchange == TWSE else "TWO"
    return ETFConstituentMembership(
        symbol=f"{raw_code}.{suffix}",
        stock_code=raw_code,
        stock_name=raw_name,
        exchange=exchange,
        source_etfs=(record.etf_code,),
        etf_membership_count=1,
    )


def infer_exchange(stock_code: str, raw_market_info: str | None = None) -> str | None:
    market_info = (raw_market_info or "").strip().upper()
    if market_info in {"TWSE", "上市", "TSE"}:
        return TWSE
    if market_info in {"TPEX", "TPEx".upper(), "上櫃", "OTC"}:
        return TPEX
    if stock_code in _TWSE_CODES:
        return TWSE
    if stock_code in _TPEX_CODES:
        return TPEX
    return None


def audit_official_source_access(
    source: ETFUniverseSource,
    *,
    fetcher=None,
) -> OfficialSourceAccessAudit:
    response = None
    try:
        if fetcher is None:
            response = _fetch_official_source_strict_tls(source.official_source_url)
        else:
            response = fetcher(source.official_source_url)
        html = response["text"]
        title = _extract_title(html)
        holdings_date = _extract_holdings_date(html)
        constituent_table_available = _has_constituent_table(html)
        parser_status = PARSER_STATUS_NOT_RUN
        parser_error = None
        raw_count = 0
        raw_dom_count = 0
        full_row_count = 0
        dedup_count = 0
        official_expected_count = _OFFICIAL_EXPECTED_CONSTITUENT_COUNTS.get(source.etf_code)
        source_semantics = None
        if source.etf_code in {"0050", "0051", "0056"} and constituent_table_available:
            try:
                records, pcf_stock_count = parse_yuanta_pcf_page(
                    html,
                    etf_code=source.etf_code,
                    holdings_date=holdings_date,
                    source_url=response["final_url"],
                )
                parser_status = PARSER_STATUS_PARSED
                raw_count = len(records)
                raw_dom_count = _count_yuanta_visible_pcf_rows(html)
                full_row_count = raw_count
                dedup_count = _dedup_stock_count(records)
                source_semantics = (
                    "Official Yuanta PCF payload; FundWeights stock set is cross-checked "
                    "against InKind FundComposition stock basket."
                )
                if pcf_stock_count and pcf_stock_count != raw_count:
                    official_expected_count = pcf_stock_count
            except Exception as exc:
                parser_status = PARSER_STATUS_FAILED
                parser_error = f"{type(exc).__name__}: {exc}"
        elif source.etf_code in {"0052", "00733"} and constituent_table_available:
            try:
                records = parse_fubon_asset_page(
                    html,
                    etf_code=source.etf_code,
                    holdings_date=holdings_date,
                    source_url=response["final_url"],
                )
                parser_status = PARSER_STATUS_PARSED
                raw_count = len(records)
                raw_dom_count = len(records)
                full_row_count = raw_count
                dedup_count = _dedup_stock_count(records)
                source_semantics = "Official Fubon asset page stock holdings table."
            except Exception as exc:
                parser_status = PARSER_STATUS_FAILED
                parser_error = f"{type(exc).__name__}: {exc}"
        elif (
            source.etf_code == "00878"
            and (fetcher is None or response.get("cathay_stock_list_json") is not None)
            and (
            constituent_table_available or "查看基金持股權重" in html or "持股權重" in html
            )
        ):
            try:
                stock_payload = response.get("cathay_stock_list_json")
                stock_holdings_date = holdings_date
                if stock_payload is None and fetcher is None:
                    stock_payload, stock_holdings_date = _fetch_cathay_stock_list_json()
                if stock_payload is None:
                    raise ETFConstituentUniverseError("Cathay stock holdings endpoint payload is not available.")
                records = parse_cathay_stock_list_json(
                    stock_payload,
                    etf_code=source.etf_code,
                    holdings_date=stock_holdings_date,
                    source_url="https://cwapi.cathaysite.com.tw/api/ETF/GetETFDetailStockList",
                )
                parser_status = PARSER_STATUS_PARSED
                raw_count = len(records)
                raw_dom_count = 10 if "查看全部" in html else raw_count
                full_row_count = raw_count
                dedup_count = _dedup_stock_count(records)
                official_expected_count = raw_count
                holdings_date = stock_holdings_date
                source_semantics = (
                    "Official Cathay ETF detail stock holdings API; SearchDate is taken from "
                    "the official ETF assets preDate."
                )
            except Exception as exc:
                parser_status = PARSER_STATUS_FAILED
                parser_error = f"{type(exc).__name__}: {exc}"
        elif source.etf_code == "00919" and constituent_table_available:
            try:
                capital_payload = response.get("capital_buyback_json")
                try:
                    _, raw_dom_count = parse_capital_portfolio_page(
                        html,
                        etf_code=source.etf_code,
                        holdings_date=holdings_date,
                        source_url=response["final_url"],
                    )
                except Exception:
                    raw_dom_count = 0
                if capital_payload is None and fetcher is None:
                    capital_payload = _fetch_capital_buyback_json()
                if capital_payload is None:
                    records, raw_dom_count = parse_capital_portfolio_page(
                        html,
                        etf_code=source.etf_code,
                        holdings_date=holdings_date,
                        source_url=response["final_url"],
                    )
                    source_semantics = "Official Capital portfolio page visible stock rows."
                else:
                    records = parse_capital_buyback_json(
                        capital_payload,
                        etf_code=source.etf_code,
                        holdings_date=holdings_date,
                        source_url="https://www.capitalfund.com.tw/CFWeb/api/etf/buyback",
                    )
                    official_expected_count = len(records)
                    source_semantics = "Official Capital CFWeb buyback API full stock holdings list."
                parser_status = PARSER_STATUS_PARSED
                raw_count = len(records)
                full_row_count = raw_count
                dedup_count = _dedup_stock_count(records)
            except Exception as exc:
                parser_status = PARSER_STATUS_FAILED
                parser_error = f"{type(exc).__name__}: {exc}"
        elif source.etf_code == "00936" and constituent_table_available:
            try:
                records = parse_taishin_holdings_page(
                    html,
                    etf_code=source.etf_code,
                    holdings_date=holdings_date,
                    source_url=response["final_url"],
                )
                parser_status = PARSER_STATUS_PARSED
                raw_count = len(records)
                raw_dom_count = len(records)
                full_row_count = raw_count
                dedup_count = _dedup_stock_count(records)
                source_semantics = "Official Taishin detail page stock holdings table."
            except Exception as exc:
                parser_status = PARSER_STATUS_FAILED
                parser_error = f"{type(exc).__name__}: {exc}"
        source_access_status = SOURCE_STATUS_AVAILABLE
        if source.etf_code == "00878" and parser_status != PARSER_STATUS_PARSED:
            source_access_status = SOURCE_STATUS_AVAILABLE_HOLDINGS_ENDPOINT_UNRESOLVED
        completeness_status = _completeness_status(
            parser_status=parser_status,
            parsed_count=dedup_count or raw_count,
            official_expected_count=official_expected_count,
            raw_dom_count=raw_dom_count,
            source=source,
        )
        return OfficialSourceAccessAudit(
            etf_code=source.etf_code,
            canonical_url=source.official_source_url,
            http_status=response["http_status"],
            final_url=response["final_url"],
            tls_verified=True,
            source_access_status=source_access_status,
            page_title=title,
            constituent_table_available=constituent_table_available,
            holdings_date=holdings_date,
            parser_status=parser_status,
            raw_constituent_count=raw_count,
            transport_method=response.get("transport_method"),
            raw_dom_stock_row_count=raw_dom_count,
            full_row_count=full_row_count,
            dedup_constituent_count=dedup_count,
            official_expected_count=official_expected_count,
            completeness_status=completeness_status,
            source_semantics=source_semantics,
            error=parser_error,
        )
    except Exception as exc:
        return OfficialSourceAccessAudit(
            etf_code=source.etf_code,
            canonical_url=source.official_source_url,
            http_status=response["http_status"] if response else None,
            final_url=response["final_url"] if response else None,
            tls_verified=False,
            source_access_status=SOURCE_STATUS_UNAVAILABLE,
            page_title=None,
            constituent_table_available=False,
            holdings_date=None,
            parser_status=PARSER_STATUS_NOT_RUN,
            raw_constituent_count=0,
            transport_method=response.get("transport_method") if response else None,
            raw_dom_stock_row_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def parse_yuanta_ratio_page(
    html: str,
    *,
    etf_code: str,
    holdings_date: date | None,
    source_url: str,
) -> tuple[ETFConstituentRecord, ...]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = soup.find(lambda tag: tag.name == "h3" and tag.get_text(strip=True) == "基金權重-股票")
    if title is None:
        raise ETFConstituentUniverseError(f"No Yuanta stock weights section found for {etf_code}.")
    title_parent = title.find_parent("div")
    section = (
        title_parent.find_next("div", class_="each_table")
        if title_parent is not None
        else title.find_next("div", class_="each_table")
    )
    if section is None:
        raise ETFConstituentUniverseError(f"No Yuanta stock weights table found for {etf_code}.")
    records = []
    for row in section.find_all("div", class_="tr"):
        cells = []
        for cell in row.find_all("div", class_="td", recursive=False):
            spans = cell.find_all("span")
            cells.append(spans[-1].get_text(strip=True) if spans else cell.get_text(strip=True))
        if len(cells) < 4 or not _is_four_digit_code(cells[0]):
            continue
        records.append(
            ETFConstituentRecord(
                etf_code=etf_code,
                stock_code=cells[0],
                stock_name=cells[1],
                raw_market_info=None,
                raw_weight=_parse_percent(cells[3]),
                holdings_date=holdings_date,
                source_url=source_url,
            )
        )
    if not records:
        raise ETFConstituentUniverseError(f"No Yuanta stock rows found for {etf_code}.")
    return tuple(records)


def parse_yuanta_pcf_page(
    html: str,
    *,
    etf_code: str,
    holdings_date: date | None,
    source_url: str,
) -> tuple[tuple[ETFConstituentRecord, ...], int]:
    stock_weights = _extract_yuanta_nuxt_array(html, ("pcfData", "FundWeights", "StockWeights"))
    fund_composition = _extract_yuanta_nuxt_array(html, ("pcfData", "InKind", "FundComposition"))
    if not stock_weights:
        raise ETFConstituentUniverseError(f"No Yuanta PCF StockWeights payload found for {etf_code}.")

    records = []
    for row in stock_weights:
        stock_code = str(row.get("code") or "").strip()
        if not _is_four_digit_code(stock_code):
            continue
        records.append(
            ETFConstituentRecord(
                etf_code=etf_code,
                stock_code=stock_code,
                stock_name=str(row.get("name") or "").strip(),
                raw_market_info=None,
                raw_weight=_coerce_float(row.get("weights")),
                holdings_date=holdings_date,
                source_url=source_url,
            )
        )
    if not records:
        raise ETFConstituentUniverseError(f"No Yuanta PCF stock rows found for {etf_code}.")
    return tuple(records), len(fund_composition)


def parse_fubon_asset_page(
    html: str,
    *,
    etf_code: str,
    holdings_date: date | None,
    source_url: str,
) -> tuple[ETFConstituentRecord, ...]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = tuple(cell.get_text(strip=True) for cell in rows[0].find_all(["td", "th"]))
        if header[:5] != ("股票代碼", "股票名稱", "股數", "金額", "權重(%)"):
            continue
        records = []
        for row in rows[1:]:
            cells = tuple(cell.get_text(strip=True) for cell in row.find_all(["td", "th"]))
            if len(cells) < 5:
                continue
            stock_code, stock_name, _shares, _amount, raw_weight = cells[:5]
            records.append(
                ETFConstituentRecord(
                    etf_code=etf_code,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    raw_market_info=None,
                    raw_weight=_parse_percent(raw_weight),
                    holdings_date=holdings_date,
                    source_url=source_url,
                )
            )
        if not records:
            raise ETFConstituentUniverseError(f"No stock rows found in Fubon asset table for {etf_code}.")
        return tuple(records)
    raise ETFConstituentUniverseError(f"No Fubon stock holdings table found for {etf_code}.")


def parse_capital_portfolio_page(
    html: str,
    *,
    etf_code: str,
    holdings_date: date | None,
    source_url: str,
) -> tuple[tuple[ETFConstituentRecord, ...], int]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    section = soup.find(id="buyback-stocks-section")
    if section is None:
        raise ETFConstituentUniverseError(f"No Capital buyback stock section found for {etf_code}.")
    raw_dom_rows = 0
    by_code: dict[str, ETFConstituentRecord] = {}
    for row in section.find_all("div", class_="tr"):
        cells = tuple(child.get_text(" ", strip=True) for child in row.find_all("div", recursive=False))
        if len(cells) < 4 or not _is_four_digit_code(cells[0]):
            continue
        raw_dom_rows += 1
        stock_code = cells[0]
        if stock_code in by_code:
            continue
        by_code[stock_code] = ETFConstituentRecord(
            etf_code=etf_code,
            stock_code=stock_code,
            stock_name=cells[1],
            raw_market_info=None,
            raw_weight=_parse_percent(cells[2]),
            holdings_date=holdings_date,
            source_url=source_url,
        )
    if not by_code:
        raise ETFConstituentUniverseError(f"No Capital stock rows found for {etf_code}.")
    return tuple(by_code[code] for code in sorted(by_code)), raw_dom_rows


def parse_capital_buyback_json(
    payload: str | dict[str, object],
    *,
    etf_code: str,
    holdings_date: date | None,
    source_url: str,
) -> tuple[ETFConstituentRecord, ...]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if data.get("code") != 200:
        raise ETFConstituentUniverseError(f"Capital buyback API did not return code=200 for {etf_code}.")
    body = data.get("data")
    if not isinstance(body, dict):
        raise ETFConstituentUniverseError(f"Capital buyback API did not return data object for {etf_code}.")
    stocks = body.get("stocks")
    if not isinstance(stocks, list):
        raise ETFConstituentUniverseError(f"Capital buyback API did not return stocks list for {etf_code}.")
    records = []
    for row in stocks:
        if not isinstance(row, dict):
            continue
        stock_code = str(row.get("stocNo") or "").strip()
        if not _is_four_digit_code(stock_code):
            continue
        records.append(
            ETFConstituentRecord(
                etf_code=etf_code,
                stock_code=stock_code,
                stock_name=str(row.get("stocName") or "").strip(),
                raw_market_info=None,
                raw_weight=_coerce_float(row.get("weightRound", row.get("weight"))),
                holdings_date=holdings_date,
                source_url=source_url,
            )
        )
    if not records:
        raise ETFConstituentUniverseError(f"No Capital buyback stock rows found for {etf_code}.")
    return tuple(records)


def parse_cathay_stock_list_json(
    payload: str | dict[str, object],
    *,
    etf_code: str,
    holdings_date: date | None,
    source_url: str,
) -> tuple[ETFConstituentRecord, ...]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if data.get("returnCode") != "2000":
        raise ETFConstituentUniverseError(f"Cathay stock list API did not return 2000 for {etf_code}.")
    rows = data.get("result")
    if not isinstance(rows, list):
        raise ETFConstituentUniverseError(f"Cathay stock list API did not return result list for {etf_code}.")
    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stock_code = str(row.get("stockCode") or "").strip()
        if not _is_four_digit_code(stock_code):
            continue
        records.append(
            ETFConstituentRecord(
                etf_code=etf_code,
                stock_code=stock_code,
                stock_name=str(row.get("stockName") or "").strip(),
                raw_market_info=None,
                raw_weight=_parse_percent(row.get("weights")),
                holdings_date=holdings_date,
                source_url=source_url,
            )
        )
    if not records:
        raise ETFConstituentUniverseError(f"No Cathay stock rows found for {etf_code}.")
    return tuple(records)


def parse_taishin_holdings_page(
    html: str,
    *,
    etf_code: str,
    holdings_date: date | None,
    source_url: str,
) -> tuple[ETFConstituentRecord, ...]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = tuple(cell.get_text(strip=True) for cell in rows[0].find_all(["td", "th"]))
        if header[:4] != ("代號", "名稱", "股數", "持股權重"):
            continue
        records = []
        for row in rows[1:]:
            cells = tuple(cell.get_text(strip=True) for cell in row.find_all(["td", "th"]))
            if len(cells) < 4:
                continue
            stock_code = _raw_taiwan_code(cells[0])
            if stock_code is None:
                continue
            records.append(
                ETFConstituentRecord(
                    etf_code=etf_code,
                    stock_code=stock_code,
                    stock_name=cells[1],
                    raw_market_info=None,
                    raw_weight=_parse_percent(cells[3]),
                    holdings_date=holdings_date,
                    source_url=source_url,
                )
            )
        if not records:
            raise ETFConstituentUniverseError(f"No Taishin stock rows found for {etf_code}.")
        return tuple(records)
    raise ETFConstituentUniverseError(f"No Taishin stock holdings table found for {etf_code}.")


def build_partial_parsed_universe_audit(
    snapshots,
    *,
    audits: tuple[OfficialSourceAccessAudit, ...] = tuple(),
) -> PartialParsedUniverseAudit:
    snapshot_tuple = tuple(snapshots)
    raw_count = sum(len(snapshot.constituents) for snapshot in snapshot_tuple)
    normalized = []
    exclusions = []
    for snapshot in snapshot_tuple:
        for record in snapshot.constituents:
            normalized_record = normalize_constituent_record(record)
            if isinstance(normalized_record, ETFConstituentExclusion):
                exclusions.append(normalized_record)
            else:
                normalized.append(normalized_record)
    parsed_source_count = len(snapshot_tuple)
    blocker = _partial_snapshot_blocker(audits)
    return PartialParsedUniverseAudit(
        universe_version=UNIVERSE_VERSION,
        universe_status=UNIVERSE_STATUS_NOT_FINALIZED,
        parsed_source_count=parsed_source_count,
        raw_membership_count=raw_count,
        normalized_membership_count=len(normalized),
        unique_stock_count=len({membership.symbol for membership in normalized}),
        excluded_count=len(exclusions),
        blocker=blocker,
    )


def audit_universe_local_coverage(
    universe: FrozenETFUniverse,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    start_date: date = DEFAULT_OBSERVATION_START,
    end_date: date = DEFAULT_OBSERVATION_END,
    warmup_trading_bars: int = DEFAULT_WARMUP_TRADING_BARS,
    outcome_horizon_bars: int = DEFAULT_OUTCOME_HORIZON_BARS,
) -> tuple[SymbolCoverageAudit, ...]:
    symbols = tuple(membership.symbol for membership in universe.memberships)
    if not symbols:
        return tuple()
    rows = _coverage_rows(symbols, db_path=db_path, start_date=start_date, end_date=end_date)
    audits = []
    for symbol in symbols:
        if not _is_valid_taiwan_symbol(symbol):
            audits.append(_invalid_symbol_audit(symbol))
            continue
        row = rows.get(symbol)
        if row is None:
            audits.append(
                SymbolCoverageAudit(
                    symbol=symbol,
                    coverage_status=COVERAGE_MISSING_LOCAL,
                    earliest_raw_price_date=None,
                    latest_raw_price_date=None,
                    total_rows=0,
                    observation_window_rows=0,
                    warmup_available_bars=0,
                    post_window_available_bars=0,
                    duplicate_date_count=0,
                    invalid_ohlcv_rows=0,
                    detail="No historical_prices rows found in local stocks.db.",
                )
            )
            continue
        audits.append(
            _coverage_audit_from_row(
                row,
                warmup_trading_bars=warmup_trading_bars,
                outcome_horizon_bars=outcome_horizon_bars,
            )
        )
    return tuple(audits)


def build_universe_with_coverage_audit(
    snapshots,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    retrieved_at: datetime | None = None,
) -> ETFUniverseBuildResult:
    db_before = database_file_audit(db_path)
    universe = build_frozen_etf_universe(snapshots, retrieved_at=retrieved_at)
    coverage = audit_universe_local_coverage(universe, db_path=db_path)
    db_after = database_file_audit(db_path)
    return ETFUniverseBuildResult(
        universe=universe,
        coverage_audits=coverage,
        db_before=db_before,
        db_after=db_after,
    )


def database_file_audit(db_path: Path | str = DEFAULT_DB_PATH) -> DatabaseFileAudit:
    path = Path(db_path)
    stat = path.stat()
    return DatabaseFileAudit(
        path=str(path),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=_sha256(path),
    )


def _validate_snapshot_sources(snapshots: tuple[ETFConstituentSnapshot, ...]) -> None:
    expected_order = tuple(source.etf_code for source in PREDEFINED_ETF_SOURCES)
    actual_order = tuple(snapshot.source.etf_code for snapshot in snapshots)
    if actual_order != expected_order:
        raise ETFConstituentUniverseError(
            f"ETF sources must be exactly {expected_order} in frozen order; got {actual_order}."
        )


def _coverage_rows(
    symbols: tuple[str, ...],
    *,
    db_path: Path | str,
    start_date: date,
    end_date: date,
) -> dict[str, sqlite3.Row]:
    placeholders = ",".join("?" for _ in symbols)
    connection = _connect_read_only(db_path)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT
                symbol,
                MIN(trading_date) AS earliest,
                MAX(trading_date) AS latest,
                COUNT(*) AS total_rows,
                COUNT(DISTINCT trading_date) AS distinct_dates,
                SUM(CASE WHEN trading_date < ? THEN 1 ELSE 0 END) AS pre_rows,
                SUM(CASE WHEN trading_date BETWEEN ? AND ? THEN 1 ELSE 0 END) AS window_rows,
                SUM(CASE WHEN trading_date > ? THEN 1 ELSE 0 END) AS post_rows,
                SUM(
                    CASE
                        WHEN high IS NULL OR low IS NULL OR close IS NULL
                          OR high <= 0 OR low <= 0 OR close <= 0
                          OR high < low OR high < close OR low > close
                          OR (open IS NOT NULL AND open <= 0)
                          OR (adjusted_close IS NOT NULL AND adjusted_close <= 0)
                          OR (volume IS NOT NULL AND volume < 0)
                        THEN 1 ELSE 0
                    END
                ) AS invalid_ohlcv_rows
            FROM historical_prices
            WHERE symbol IN ({placeholders})
            GROUP BY symbol
            ORDER BY symbol ASC
            """,
            (
                start_date.isoformat(),
                start_date.isoformat(),
                end_date.isoformat(),
                end_date.isoformat(),
                *symbols,
            ),
        ).fetchall()
    finally:
        connection.close()
    return {row["symbol"]: row for row in rows}


def _coverage_audit_from_row(
    row: sqlite3.Row,
    *,
    warmup_trading_bars: int,
    outcome_horizon_bars: int,
) -> SymbolCoverageAudit:
    issues = []
    if row["pre_rows"] < warmup_trading_bars:
        issues.append(f"warmup bars {row['pre_rows']} < {warmup_trading_bars}")
    if row["window_rows"] <= 0:
        issues.append("no rows in observation window")
    if row["post_rows"] < outcome_horizon_bars:
        issues.append(f"post-window bars {row['post_rows']} < {outcome_horizon_bars}")
    duplicate_dates = row["total_rows"] - row["distinct_dates"]
    if duplicate_dates > 0:
        issues.append(f"duplicate dates {duplicate_dates}")
    if row["invalid_ohlcv_rows"] > 0:
        issues.append(f"invalid OHLCV rows {row['invalid_ohlcv_rows']}")
    return SymbolCoverageAudit(
        symbol=row["symbol"],
        coverage_status=COVERAGE_INSUFFICIENT if issues else COVERAGE_AVAILABLE_LOCAL,
        earliest_raw_price_date=date.fromisoformat(row["earliest"]) if row["earliest"] else None,
        latest_raw_price_date=date.fromisoformat(row["latest"]) if row["latest"] else None,
        total_rows=row["total_rows"],
        observation_window_rows=row["window_rows"],
        warmup_available_bars=row["pre_rows"],
        post_window_available_bars=row["post_rows"],
        duplicate_date_count=duplicate_dates,
        invalid_ohlcv_rows=row["invalid_ohlcv_rows"],
        detail="; ".join(issues) if issues else None,
    )


def _invalid_symbol_audit(symbol: str) -> SymbolCoverageAudit:
    return SymbolCoverageAudit(
        symbol=symbol,
        coverage_status=COVERAGE_INVALID_SYMBOL,
        earliest_raw_price_date=None,
        latest_raw_price_date=None,
        total_rows=0,
        observation_window_rows=0,
        warmup_available_bars=0,
        post_window_available_bars=0,
        duplicate_date_count=0,
        invalid_ohlcv_rows=0,
        detail="Symbol is not a normalized Taiwan stock symbol.",
    )


def _connect_read_only(db_path: Path | str) -> sqlite3.Connection:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _fetch_official_source_strict_tls(url: str) -> dict[str, object]:
    import requests

    if "yuantaetfs.com" in url:
        return _fetch_official_source_with_verified_curl(url)
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
        verify=True,
        allow_redirects=True,
    )
    response.raise_for_status()
    return {
        "http_status": response.status_code,
        "final_url": response.url,
        "text": response.text,
        "transport_method": TRANSPORT_REQUESTS_VERIFIED,
    }


def _fetch_official_source_with_verified_curl(url: str) -> dict[str, object]:
    command = _verified_curl_command(url)
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    marker = "\n__ETF_SOURCE_META__"
    if marker not in result.stdout:
        raise ETFConstituentUniverseError("Verified curl response did not include response metadata.")
    html, metadata = result.stdout.rsplit(marker, 1)
    status_text, final_url = metadata.strip().split(" ", 1)
    return {
        "http_status": int(status_text),
        "final_url": final_url.strip(),
        "text": html,
        "transport_method": TRANSPORT_CURL_VERIFIED,
    }


def _verified_curl_command(url: str) -> list[str]:
    command = [
        "curl",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--write-out",
        "\n__ETF_SOURCE_META__%{http_code} %{url_effective}",
        url,
    ]
    if any(arg in {"-k", "--insecure"} for arg in command):
        raise ETFConstituentUniverseError("Verified curl transport must not disable TLS verification.")
    return command


def _fetch_cathay_stock_list_json() -> tuple[dict[str, object], date | None]:
    assets_url = "https://cwapi.cathaysite.com.tw/api/ETF/GetETFAssets"
    stock_url = "https://cwapi.cathaysite.com.tw/api/ETF/GetETFDetailStockList"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.cathaysite.com.tw/ETF/detail/ECN?tab=etf3",
        "Accept": "application/json, text/plain, */*",
    }
    assets = _get_official_json(
        assets_url,
        params={"FundCode": "CN", "status": 1},
        headers=headers,
    )
    pre_date_text = None
    if isinstance(assets.get("result"), dict):
        pre_date_text = assets["result"].get("preDate")
    search_date = _date_from_slash_text(pre_date_text)
    if search_date is None:
        raise ETFConstituentUniverseError("Cathay ETF assets API did not return preDate for 00878.")
    stock_payload = _get_official_json(
        stock_url,
        params={"FundCode": "CN", "SearchDate": search_date.isoformat(), "status": 1},
        headers=headers,
    )
    return stock_payload, search_date


def _fetch_capital_buyback_json() -> dict[str, object]:
    return _post_official_json(
        "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback",
        payload={"fundId": 195},
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.capitalfund.com.tw/etf/product/detail/195/portfolio",
            "Origin": "https://www.capitalfund.com.tw",
            "Accept": "application/json, text/plain, */*",
        },
    )


def _get_official_json(
    url: str,
    *,
    params: dict[str, object],
    headers: dict[str, str],
) -> dict[str, object]:
    import requests

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=20,
        verify=True,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def _post_official_json(
    url: str,
    *,
    payload: dict[str, object],
    headers: dict[str, str],
) -> dict[str, object]:
    import requests

    request_headers = dict(headers)
    request_headers["Content-Type"] = "application/json;charset=UTF-8"
    response = requests.post(
        url,
        json=payload,
        headers=request_headers,
        timeout=20,
        verify=True,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def _date_from_slash_text(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", value)
    if match is None:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _extract_title(html: str) -> str | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return " ".join(soup.title.string.split())
    return None


def _extract_holdings_date(html: str) -> date | None:
    searchable = html
    try:
        from bs4 import BeautifulSoup

        searchable = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        searchable = html
    patterns = (
        r"交易日期[：: \s]*(20\d{2})[/-](\d{1,2})[/-](\d{1,2})",
        r"資料日期[：: \s]*(20\d{2})[/-](\d{1,2})[/-](\d{1,2})",
        r"於\s*(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s*提供",
    )
    match = None
    for pattern in patterns:
        match = re.search(pattern, searchable)
        if match is not None:
            break
    if match is None:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _has_constituent_table(html: str) -> bool:
    return (
        ("股票代碼" in html and "股票名稱" in html and "權重" in html)
        or ("股票實物申贖" in html and "股票代碼" in html and "股票名稱" in html)
        or ("商品代碼" in html and "商品名稱" in html and "商品權重" in html)
        or ("股票代號" in html and "股票名稱" in html and "持股權重" in html)
        or ("代號" in html and "名稱" in html and "持股權重" in html)
    )


def _completeness_status(
    *,
    parser_status: str,
    parsed_count: int,
    official_expected_count: int | None,
    raw_dom_count: int,
    source: ETFUniverseSource,
) -> str:
    if parser_status != PARSER_STATUS_PARSED:
        return COMPLETENESS_UNKNOWN
    if official_expected_count is not None:
        return PARSED_COMPLETE if parsed_count >= official_expected_count else PARSED_INCOMPLETE
    if source.etf_code == "00919" and parsed_count <= 10 and raw_dom_count <= 10:
        return PARSED_INCOMPLETE
    if source.etf_code == "00878":
        return COMPLETENESS_UNKNOWN
    return PARSED_COMPLETE


def _count_yuanta_visible_pcf_rows(html: str) -> int:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        title = soup.find(lambda tag: tag.name == "h3" and "股票實物申贖" in tag.get_text(" ", strip=True))
        if title is None:
            return 0
        count = 0
        for row in title.find_all_next("div", class_="tr"):
            text = row.get_text(" ", strip=True)
            if "Notice" in text:
                break
            cells = row.find_all("div", recursive=False)
            if cells and _raw_taiwan_code(cells[0].get_text(" ", strip=True)):
                count += 1
        return count
    except Exception:
        return 0


def _dedup_stock_count(records: tuple[ETFConstituentRecord, ...]) -> int:
    return len({record.stock_code for record in records if _is_four_digit_code(record.stock_code)})


def _extract_yuanta_nuxt_array(html: str, path_markers: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    script_marker = "window.__NUXT__="
    script_start = html.find(script_marker)
    if script_start < 0:
        return tuple()
    script_end = html.find("</script>", script_start)
    if script_end < 0:
        return tuple()
    script = html[script_start + len(script_marker) : script_end].strip()
    header_match = re.search(r"^\(function\((?P<params>[^)]*)\)\{", script, re.S)
    call_index = script.rfind("}(")
    call_offset = 2
    if call_index < 0:
        call_index = script.rfind("})(")
        call_offset = 3
    if header_match is None or call_index < 0:
        return tuple()
    args_text = script[call_index + call_offset :]
    if args_text.endswith(");"):
        args_text = args_text[:-2]
    if args_text.endswith(")"):
        args_text = args_text[:-1]
    variable_map = _yuanta_nuxt_variable_map(
        header_match.group("params"),
        args_text,
    )
    body = script
    marker_index = body.find(path_markers[-1] + ":[")
    if marker_index < 0:
        return tuple()
    array_start = body.find("[", marker_index)
    array_text = _balanced_segment(body, array_start, "[", "]")
    if not array_text:
        return tuple()
    rows = []
    for item_text in _split_top_level(array_text[1:-1], ","):
        item_text = item_text.strip()
        if not item_text.startswith("{"):
            continue
        rows.append(_parse_yuanta_object_literal(item_text, variable_map))
    return tuple(rows)


def _yuanta_nuxt_variable_map(params_text: str, args_text: str) -> dict[str, object]:
    params = [param.strip() for param in params_text.split(",") if param.strip()]
    args = _split_top_level(args_text, ",")
    values = {}
    for param, raw_value in zip(params, args, strict=False):
        raw_value = raw_value.strip()
        if raw_value == "null":
            values[param] = None
        elif raw_value == "true":
            values[param] = True
        elif raw_value == "false":
            values[param] = False
        elif re.fullmatch(r"-?(?:\d+(?:\.\d+)?|\.\d+)", raw_value):
            values[param] = float(raw_value) if "." in raw_value else int(raw_value)
        elif raw_value.startswith('"') and raw_value.endswith('"'):
            values[param] = json.loads(raw_value)
    return values


def _parse_yuanta_object_literal(text: str, variable_map: dict[str, object]) -> dict[str, object]:
    body = text.strip()[1:-1]
    parsed = {}
    for item in _split_top_level(body, ","):
        if ":" not in item:
            continue
        key, raw_value = item.split(":", 1)
        parsed[key.strip()] = _resolve_yuanta_value(raw_value.strip(), variable_map)
    return parsed


def _resolve_yuanta_value(raw_value: str, variable_map: dict[str, object]) -> object:
    if raw_value in variable_map:
        return variable_map[raw_value]
    if raw_value == "null":
        return None
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    if re.fullmatch(r"-?(?:\d+(?:\.\d+)?|\.\d+)", raw_value):
        return float(raw_value) if "." in raw_value else int(raw_value)
    if raw_value.startswith('"') and raw_value.endswith('"'):
        return json.loads(raw_value)
    return raw_value


def _balanced_segment(text: str, start: int, opener: str, closer: str) -> str:
    if start < 0 or start >= len(text) or text[start] != opener:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _split_top_level(text: str, separator: str) -> list[str]:
    parts = []
    start = 0
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return _parse_percent(str(value))


def _parse_percent(value: str) -> float | None:
    cleaned = value.replace(",", "").replace("%", "").strip()
    if not cleaned:
        return None
    return float(cleaned)


def _is_four_digit_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", value.strip()))


def _raw_taiwan_code(value: str) -> str | None:
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", value)
    return match.group(1) if match else None


def _partial_snapshot_blocker(audits: tuple[OfficialSourceAccessAudit, ...]) -> str | None:
    if not audits:
        return "Not all 8 ETF sources have PARSED status."
    unresolved = tuple(audit.etf_code for audit in audits if audit.parser_status != PARSER_STATUS_PARSED)
    if not unresolved:
        return None
    return "Not all 8 ETF sources parsed: " + ", ".join(unresolved)


def _is_valid_taiwan_symbol(symbol: str) -> bool:
    if not (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        return False
    code = symbol.split(".", 1)[0]
    return code.isdigit() and len(code) == 4


def _is_non_stock_name(name: str) -> bool:
    upper_name = name.strip().upper()
    return any(term in upper_name for term in ("現金", "期貨", "債券", "ETF", "FUTURE", "CASH", "BOND"))


def _etf_order_index(etf_code: str) -> int:
    order = {source.etf_code: index for index, source in enumerate(PREDEFINED_ETF_SOURCES)}
    return order[etf_code]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
