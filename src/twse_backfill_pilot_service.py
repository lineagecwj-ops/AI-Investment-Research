from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path

from database import HISTORICAL_PRICE_COLUMNS
from database import initialize_historical_price_tables
from database import utc_now
from etf_constituent_universe_service import COVERAGE_AVAILABLE_LOCAL
from etf_constituent_universe_service import COVERAGE_MISSING_LOCAL
from etf_constituent_universe_service import TWSE
from etf_constituent_universe_service import ETFConstituentMembership
from etf_constituent_universe_service import FrozenETFUniverse
from etf_constituent_universe_service import SymbolCoverageAudit
from models import HistoricalPriceBar
from models import HistoricalPriceSeries


PILOT_VERSION = "2026-08-twse-backfill-pilot-v1"
PILOT_SYMBOL_COUNT = 20
SELECTION_RULE = (
    "Filter finalized ETF Frozen Universe to exchange=TWSE, suffix=.TW, "
    "coverage=MISSING_LOCAL; sort by numeric stock_code ascending; select "
    "round(i * (N - 1) / (K - 1)) for i=0..K-1 with stable nearest-index dedup."
)
PRICE_SEMANTICS_CONTRACT = {
    "source": "Yahoo Finance via yfinance",
    "auto_adjust": False,
    "actions": True,
    "db_columns": tuple(HISTORICAL_PRICE_COLUMNS),
    "technical_analysis_close": "adjusted_close first, fallback raw close",
    "missing_volume_policy": "do not coerce missing volume to 0",
}


class TWSEBackfillPilotError(Exception):
    """Raised when the TWSE backfill pilot cannot be prepared safely."""


@dataclass(frozen=True)
class PilotCandidate:
    symbol: str
    stock_code: str
    stock_name: str
    exchange: str
    coverage_status: str
    ordered_position: int


@dataclass(frozen=True)
class PilotSelection:
    candidate_count: int
    selected_count: int
    ordered_candidate_checksum: str
    selected_candidates: tuple[PilotCandidate, ...]
    selected_indexes: tuple[int, ...]
    selection_rule: str = SELECTION_RULE


@dataclass(frozen=True)
class PilotSelectionFreeze:
    pilot_version: str
    selection_rule: str
    candidate_count: int
    selected_count: int
    ordered_candidate_checksum: str
    selected_symbols: tuple[str, ...]
    selected_indexes: tuple[int, ...]
    generated_at: datetime


@dataclass(frozen=True)
class PriceSeriesQualityReport:
    symbol: str
    status: str
    row_count: int
    duplicate_dates: int
    missing_ohlcv: int
    invalid_ohlc: int
    mixed_symbol_rows: int
    detail: str | None = None


@dataclass(frozen=True)
class SQLiteBackupAudit:
    source_path: str
    backup_path: str
    size_bytes: int
    sha256: str
    integrity_check: str


def build_twse_missing_local_candidate_pool(
    universe: FrozenETFUniverse,
    coverage_audits: tuple[SymbolCoverageAudit, ...],
) -> tuple[PilotCandidate, ...]:
    coverage_by_symbol = {audit.symbol: audit for audit in coverage_audits}
    candidates = []
    for membership in universe.memberships:
        audit = coverage_by_symbol.get(membership.symbol)
        if audit is None:
            continue
        if not is_twse_missing_local_stock(membership, audit):
            continue
        candidates.append(
            PilotCandidate(
                symbol=membership.symbol,
                stock_code=membership.stock_code,
                stock_name=membership.stock_name,
                exchange=membership.exchange,
                coverage_status=audit.coverage_status,
                ordered_position=0,
            )
        )

    ordered = sorted(candidates, key=lambda item: int(item.stock_code))
    return tuple(
        PilotCandidate(
            symbol=item.symbol,
            stock_code=item.stock_code,
            stock_name=item.stock_name,
            exchange=item.exchange,
            coverage_status=item.coverage_status,
            ordered_position=index,
        )
        for index, item in enumerate(ordered)
    )


def is_twse_missing_local_stock(
    membership: ETFConstituentMembership,
    audit: SymbolCoverageAudit,
) -> bool:
    return (
        membership.exchange == TWSE
        and membership.symbol.endswith(".TW")
        and not membership.symbol.endswith(".TWO")
        and audit.coverage_status == COVERAGE_MISSING_LOCAL
    )


def select_twse_backfill_pilot(
    universe: FrozenETFUniverse,
    coverage_audits: tuple[SymbolCoverageAudit, ...],
    *,
    k: int = PILOT_SYMBOL_COUNT,
) -> PilotSelection:
    candidates = build_twse_missing_local_candidate_pool(universe, coverage_audits)
    if len(candidates) < k:
        raise TWSEBackfillPilotError(
            f"TWSE MISSING_LOCAL candidate count {len(candidates)} is smaller than required pilot count {k}."
        )
    selected_indexes = equal_spaced_indexes(len(candidates), k)
    selected = tuple(candidates[index] for index in selected_indexes)
    return PilotSelection(
        candidate_count=len(candidates),
        selected_count=len(selected),
        ordered_candidate_checksum=ordered_candidate_checksum(candidates),
        selected_candidates=selected,
        selected_indexes=selected_indexes,
    )


def equal_spaced_indexes(candidate_count: int, selected_count: int) -> tuple[int, ...]:
    if selected_count <= 0:
        return tuple()
    if candidate_count < selected_count:
        raise TWSEBackfillPilotError("Candidate count is smaller than selected count.")
    if selected_count == 1:
        return (0,)

    indexes = []
    selected = set()
    for i in range(selected_count):
        index = round(i * (candidate_count - 1) / (selected_count - 1))
        index = nearest_unselected_index(index, candidate_count, selected)
        indexes.append(index)
        selected.add(index)
    return tuple(indexes)


def nearest_unselected_index(target: int, candidate_count: int, selected: set[int]) -> int:
    if target not in selected:
        return target
    for offset in range(1, candidate_count):
        left = target - offset
        if left >= 0 and left not in selected:
            return left
        right = target + offset
        if right < candidate_count and right not in selected:
            return right
    raise TWSEBackfillPilotError("Unable to find a deterministic replacement index.")


def freeze_pilot_selection(
    selection: PilotSelection,
    *,
    generated_at: datetime | None = None,
    pilot_version: str = PILOT_VERSION,
) -> PilotSelectionFreeze:
    return PilotSelectionFreeze(
        pilot_version=pilot_version,
        selection_rule=selection.selection_rule,
        candidate_count=selection.candidate_count,
        selected_count=selection.selected_count,
        ordered_candidate_checksum=selection.ordered_candidate_checksum,
        selected_symbols=tuple(candidate.symbol for candidate in selection.selected_candidates),
        selected_indexes=selection.selected_indexes,
        generated_at=generated_at or datetime.now(UTC),
    )


def ordered_candidate_checksum(candidates: tuple[PilotCandidate, ...]) -> str:
    payload = [
        {
            "position": candidate.ordered_position,
            "symbol": candidate.symbol,
            "stock_code": candidate.stock_code,
            "exchange": candidate.exchange,
            "coverage_status": candidate.coverage_status,
        }
        for candidate in candidates
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_price_series_for_backfill(series: HistoricalPriceSeries) -> PriceSeriesQualityReport:
    duplicate_dates = 0
    missing_ohlcv = 0
    invalid_ohlc = 0
    mixed_symbol_rows = 0
    details = []
    seen_dates = set()
    previous_date = None

    for bar in series.bars:
        if bar.symbol != series.symbol:
            mixed_symbol_rows += 1
        if bar.trading_date in seen_dates:
            duplicate_dates += 1
        seen_dates.add(bar.trading_date)
        if previous_date is not None and bar.trading_date <= previous_date:
            details.append("trading_date is not strictly ascending")
        previous_date = bar.trading_date
        if _has_missing_ohlcv(bar):
            missing_ohlcv += 1
        if _has_invalid_ohlc(bar):
            invalid_ohlc += 1

    issues = []
    if duplicate_dates:
        issues.append(f"duplicate dates {duplicate_dates}")
    if missing_ohlcv:
        issues.append(f"missing OHLCV {missing_ohlcv}")
    if invalid_ohlc:
        issues.append(f"invalid OHLC {invalid_ohlc}")
    if mixed_symbol_rows:
        issues.append(f"mixed symbol rows {mixed_symbol_rows}")
    issues.extend(details)
    return PriceSeriesQualityReport(
        symbol=series.symbol,
        status="INVALID_DATA" if issues else COVERAGE_AVAILABLE_LOCAL,
        row_count=len(series.bars),
        duplicate_dates=duplicate_dates,
        missing_ohlcv=missing_ohlcv,
        invalid_ohlc=invalid_ohlc,
        mixed_symbol_rows=mixed_symbol_rows,
        detail="; ".join(issues) if issues else None,
    )


def assert_valid_price_series_for_backfill(series: HistoricalPriceSeries) -> None:
    report = validate_price_series_for_backfill(series)
    if report.status != COVERAGE_AVAILABLE_LOCAL:
        raise TWSEBackfillPilotError(report.detail or "Historical price series is invalid.")


def save_pilot_price_series_transaction(
    db_path: Path | str,
    series_list: tuple[HistoricalPriceSeries, ...],
) -> None:
    for series in series_list:
        assert_valid_price_series_for_backfill(series)

    connection = sqlite3.connect(Path(db_path))
    try:
        initialize_historical_price_tables(connection)
        with connection:
            for series in series_list:
                timestamp = (series.fetched_at or utc_now()).isoformat()
                for bar in series.bars:
                    connection.execute(
                        f"""
                        INSERT INTO historical_prices (
                            {", ".join(HISTORICAL_PRICE_COLUMNS)}
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(symbol, trading_date) DO UPDATE SET
                            open = excluded.open,
                            high = excluded.high,
                            low = excluded.low,
                            close = excluded.close,
                            adjusted_close = excluded.adjusted_close,
                            volume = excluded.volume,
                            dividends = excluded.dividends,
                            stock_splits = excluded.stock_splits,
                            currency = excluded.currency,
                            fetched_at = excluded.fetched_at
                        """,
                        (
                            bar.symbol,
                            bar.trading_date.isoformat(),
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.adjusted_close,
                            bar.volume,
                            bar.dividends,
                            bar.stock_splits,
                            series.currency,
                            timestamp,
                        ),
                    )
    finally:
        connection.close()


def create_sqlite_backup(
    source_db_path: Path | str,
    backup_path: Path | str,
) -> SQLiteBackupAudit:
    source = Path(source_db_path)
    backup = Path(backup_path)
    backup.parent.mkdir(parents=True, exist_ok=True)

    source_connection = sqlite3.connect(source)
    backup_connection = sqlite3.connect(backup)
    try:
        source_connection.backup(backup_connection)
        backup_connection.commit()
        integrity = backup_connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        backup_connection.close()
        source_connection.close()

    return SQLiteBackupAudit(
        source_path=str(source),
        backup_path=str(backup),
        size_bytes=backup.stat().st_size,
        sha256=file_sha256(backup),
        integrity_check=integrity,
    )


def verify_sqlite_backup_read_only(backup_path: Path | str) -> str:
    uri = Path(backup_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        return connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_missing_ohlcv(bar: HistoricalPriceBar) -> bool:
    return any(
        value is None
        for value in (bar.open, bar.high, bar.low, bar.close, bar.volume)
    )


def _has_invalid_ohlc(bar: HistoricalPriceBar) -> bool:
    values = (bar.open, bar.high, bar.low, bar.close)
    if any(value is None or not math.isfinite(float(value)) for value in values):
        return True
    if any(float(value) <= 0 for value in values):
        return True
    if bar.volume is not None and (not math.isfinite(float(bar.volume)) or bar.volume < 0):
        return True
    return (
        bar.high < bar.low
        or bar.high < bar.open
        or bar.high < bar.close
        or bar.low > bar.open
        or bar.low > bar.close
    )
