from __future__ import annotations

import hashlib
import sqlite3
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
SOURCE_STATUS_NOT_RETRIEVED = "NOT_RETRIEVED"
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
        official_source_url="https://www.yuantaetf.com/product/detail/0050/ratio",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="0051",
        etf_name="元大中型100",
        issuer="元大投信",
        category="中型股 breadth",
        official_source_url="https://www.yuantaetf.com/product/detail/0051/ratio",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="0052",
        etf_name="富邦科技",
        issuer="富邦投信",
        category="科技",
        official_source_url="https://www.fubon.com/asset-management/ph/0052/index.html",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="0056",
        etf_name="元大高股息",
        issuer="元大投信",
        category="高股息",
        official_source_url="https://www.yuantaetf.com/product/detail/0056/ratio",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="00733",
        etf_name="富邦臺灣中小",
        issuer="富邦投信",
        category="中小型 / 動能",
        official_source_url="https://www.fubon.com/asset-management/ETF/etf-detail/00733",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="00878",
        etf_name="國泰永續高股息",
        issuer="國泰投信",
        category="ESG + 高股息",
        official_source_url="https://www.cathaysite.com.tw/funds/etf/00878",
        source_type=SOURCE_TYPE_ISSUER_OFFICIAL_HOLDINGS,
    ),
    ETFUniverseSource(
        etf_code="00919",
        etf_name="群益台灣精選高息",
        issuer="群益投信",
        category="另一套高股息 selection methodology",
        official_source_url="https://www.capitalfund.com.tw/ETF/product/detail/00919",
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
