from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import urlopen

from database_config import PROJECT_ROOT
from frozen_twse_research_universe_service import FrozenTWSEResearchUniverse
from frozen_twse_research_universe_service import load_frozen_twse_research_universe
from research_data_store import ResearchDataStore


TWSE_INSTITUTIONAL_FLOW_ARTIFACT_ID_V1 = "TWSE_INSTITUTIONAL_FLOW_2018_2024_V1"
TWSE_T86_NORMALIZATION_V1 = "TWSE_T86_NORMALIZATION_V1"
TWSE_T86_AVAILABILITY_V1 = "TWSE_T86_AVAILABILITY_V1"
CONSERVATIVE_NEXT_SESSION_PROXY = "CONSERVATIVE_NEXT_SESSION_PROXY"
REVISION_SEMANTICS_PRESENT_BUT_DEFINED = "REVISION_SEMANTICS_PRESENT_BUT_DEFINED"
TWSE_T86_ENDPOINT = "https://www.twse.com.tw/rwd/zh/fund/T86"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "research" / "institutional_flow"
DEFAULT_DATABASE_PATH = DEFAULT_OUTPUT_DIR / "twse_institutional_flow_2018_2024_v1.sqlite"
DEFAULT_MANIFEST_PATH = DEFAULT_OUTPUT_DIR / "twse_institutional_flow_2018_2024_v1_manifest.json"

T86_FIELDS_V1 = (
    "證券代號",
    "證券名稱",
    "外陸資買進股數(不含外資自營商)",
    "外陸資賣出股數(不含外資自營商)",
    "外陸資買賣超股數(不含外資自營商)",
    "外資自營商買進股數",
    "外資自營商賣出股數",
    "外資自營商買賣超股數",
    "投信買進股數",
    "投信賣出股數",
    "投信買賣超股數",
    "自營商買賣超股數",
    "自營商買進股數(自行買賣)",
    "自營商賣出股數(自行買賣)",
    "自營商買賣超股數(自行買賣)",
    "自營商買進股數(避險)",
    "自營商賣出股數(避險)",
    "自營商買賣超股數(避險)",
    "三大法人買賣超股數",
)


class TWSEInstitutionalFlowMaterializationError(Exception):
    """Raised when immutable T86 materialization cannot continue safely."""


@dataclass(frozen=True)
class TWSEInstitutionalFlowMaterializationResult:
    database_path: Path
    manifest_path: Path
    requested_dates: int
    successful_dates: int
    audited_no_data_dates: int
    normalized_rows: int
    unique_symbols: int
    exact_price_date_matches: int
    missing_price_date_pairs: int
    request_count: int
    retry_count: int
    database_sha256: str
    normalized_data_sha256: str
    is_complete: bool


class TWSEInstitutionalFlowMaterializer:
    """Small, resumable, official-TWSE-only materializer for historical T86 rows."""

    def __init__(
        self,
        *,
        fetch_payload: Callable[[str], bytes] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._fetch_payload = fetch_payload or _fetch_official_payload
        self._sleep = sleep

    def materialize(
        self,
        *,
        research_store: ResearchDataStore | None = None,
        output_database_path: Path | str = DEFAULT_DATABASE_PATH,
        output_manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
        retrieval_timestamp: datetime | None = None,
        retry_limit: int = 2,
        request_pause_seconds: float = 0.10,
        max_dates_per_run: int | None = None,
    ) -> TWSEInstitutionalFlowMaterializationResult:
        if retry_limit < 0 or request_pause_seconds < 0 or (max_dates_per_run is not None and max_dates_per_run <= 0):
            raise TWSEInstitutionalFlowMaterializationError("retry_limit, request_pause_seconds, and max_dates_per_run are invalid.")
        database_path = _research_path(output_database_path, "output_database_path")
        manifest_path = _research_path(output_manifest_path, "output_manifest_path")
        store = research_store or ResearchDataStore()
        universe = load_frozen_twse_research_universe(research_store=store)
        calendar = _load_calendar(store)
        requested_dates, available_dates = _requested_and_available_dates(calendar)
        timestamp = retrieval_timestamp or datetime.now(UTC)

        database_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        try:
            _initialize_schema(connection)
            _verify_existing_metadata(connection, universe, requested_dates)
            _record_metadata(connection, universe, requested_dates, available_dates)
            request_count, retry_count = self._resume_dates(
                connection=connection,
                requested_dates=requested_dates,
                available_dates=available_dates,
                universe=universe,
                timestamp=timestamp,
                retry_limit=retry_limit,
                request_pause_seconds=request_pause_seconds,
                max_dates_per_run=max_dates_per_run,
            )
            validation = _validate_database(connection, universe, store.resolved_db_path)
        finally:
            connection.close()

        database_sha256 = _sha256_file(database_path)
        is_complete = not _remaining_dates(database_path, requested_dates)
        if is_complete:
            manifest = _build_manifest(
                database_path=database_path,
                database_sha256=database_sha256,
                universe=universe,
                requested_dates=requested_dates,
                validation=validation,
                request_count=request_count,
                retry_count=retry_count,
            )
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return TWSEInstitutionalFlowMaterializationResult(
            database_path=database_path,
            manifest_path=manifest_path,
            requested_dates=len(requested_dates),
            successful_dates=validation["successful_dates"],
            audited_no_data_dates=validation["audited_no_data_dates"],
            normalized_rows=validation["normalized_rows"],
            unique_symbols=validation["unique_symbols"],
            exact_price_date_matches=validation["exact_price_date_matches"],
            missing_price_date_pairs=validation["missing_price_date_pairs"],
            request_count=request_count,
            retry_count=retry_count,
            database_sha256=database_sha256,
            normalized_data_sha256=validation["normalized_data_sha256"],
            is_complete=is_complete,
        )

    def _resume_dates(
        self,
        *,
        connection: sqlite3.Connection,
        requested_dates: tuple[date, ...],
        available_dates: dict[date, date],
        universe: FrozenTWSEResearchUniverse,
        timestamp: datetime,
        retry_limit: int,
        request_pause_seconds: float,
        max_dates_per_run: int | None,
    ) -> tuple[int, int]:
        request_count = 0
        retry_count = 0
        completed = _completed_dates(connection)
        completed_this_run = 0
        for trade_date in requested_dates:
            if trade_date in completed:
                continue
            if max_dates_per_run is not None and completed_this_run >= max_dates_per_run:
                break
            source_url = _source_url(trade_date)
            payload = None
            last_error = None
            for attempt in range(retry_limit + 1):
                request_count += 1
                try:
                    payload = self._fetch_payload(source_url)
                    break
                except Exception as exc:  # Network failures must leave partial state resumable.
                    last_error = exc
                    if attempt == retry_limit:
                        _record_failure(connection, trade_date, "FAILED_TRANSIENT", type(exc).__name__, attempt + 1, timestamp)
                        connection.commit()
                        raise TWSEInstitutionalFlowMaterializationError(
                            f"Official T86 retrieval failed for {trade_date.isoformat()} after {attempt + 1} attempts."
                        ) from exc
                    retry_count += 1
                    self._sleep(request_pause_seconds)
            assert payload is not None
            try:
                _persist_payload(
                    connection=connection,
                    trade_date=trade_date,
                    available_date=available_dates[trade_date],
                    source_url=source_url,
                    payload=payload,
                    retrieved_at=timestamp,
                    universe=universe,
                )
            except TWSEInstitutionalFlowMaterializationError as exc:
                _record_failure(connection, trade_date, "FAILED_PERMANENT", type(exc).__name__, 1, timestamp)
                connection.commit()
                raise
            connection.execute("DELETE FROM retrieval_failures WHERE trade_date = ?", (trade_date.isoformat(),))
            connection.commit()
            completed_this_run += 1
            if request_pause_seconds:
                self._sleep(request_pause_seconds)
        return request_count, retry_count


def _fetch_official_payload(source_url: str) -> bytes:
    with urlopen(source_url, timeout=30) as response:
        return response.read()


def _source_url(trade_date: date) -> str:
    return f"{TWSE_T86_ENDPOINT}?{urlencode({'date': trade_date.strftime('%Y%m%d'), 'selectType': 'ALLBUT0999', 'response': 'json'})}"


def _research_path(value: Path | str, field_name: str) -> Path:
    path = Path(value).resolve()
    production_root = (PROJECT_ROOT / "data" / "production").resolve()
    if path == production_root or production_root in path.parents:
        raise TWSEInstitutionalFlowMaterializationError(f"{field_name} cannot target data/production.")
    return path


def _load_calendar(store: ResearchDataStore) -> tuple[date, ...]:
    series = store.load_historical_price_series("0050.TW")
    dates = tuple(sorted(bar.trading_date for bar in series.bars if bar.trading_date <= date(2025, 1, 31)))
    if len(dates) != len(set(dates)):
        raise TWSEInstitutionalFlowMaterializationError("0050.TW calendar contains duplicate trading dates.")
    return dates


def _requested_and_available_dates(calendar: tuple[date, ...]) -> tuple[tuple[date, ...], dict[date, date]]:
    requested = tuple(day for day in calendar if date(2018, 1, 1) <= day <= date(2024, 12, 31))
    if not requested:
        raise TWSEInstitutionalFlowMaterializationError("No requested 2018-2024 trading dates in immutable calendar.")
    available: dict[date, date] = {}
    for index, trade_date in enumerate(requested):
        next_dates = tuple(day for day in calendar if day > trade_date)
        if not next_dates:
            raise TWSEInstitutionalFlowMaterializationError(f"Missing next trading session for {trade_date.isoformat()}.")
        available[trade_date] = next_dates[0]
    if any(day.year > 2024 for day in requested):
        raise TWSEInstitutionalFlowMaterializationError("2025 T86 values are forbidden.")
    return requested, available


def _initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS source_payloads (
            trade_date TEXT PRIMARY KEY,
            available_date TEXT NOT NULL,
            source_url TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            raw_row_count INTEGER NOT NULL,
            schema_signature TEXT NOT NULL,
            fields_json TEXT NOT NULL,
            source_status TEXT NOT NULL,
            raw_payload BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS normalized_flows (
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            foreign_ex_dealer_buy INTEGER NOT NULL,
            foreign_ex_dealer_sell INTEGER NOT NULL,
            foreign_ex_dealer_net INTEGER NOT NULL,
            foreign_dealer_buy INTEGER NOT NULL,
            foreign_dealer_sell INTEGER NOT NULL,
            foreign_dealer_net INTEGER NOT NULL,
            trust_buy INTEGER NOT NULL,
            trust_sell INTEGER NOT NULL,
            trust_net INTEGER NOT NULL,
            dealer_proprietary_buy INTEGER NOT NULL,
            dealer_proprietary_sell INTEGER NOT NULL,
            dealer_proprietary_net INTEGER NOT NULL,
            dealer_hedge_buy INTEGER NOT NULL,
            dealer_hedge_sell INTEGER NOT NULL,
            dealer_hedge_net INTEGER NOT NULL,
            dealer_total_net INTEGER NOT NULL,
            total_institutional_net INTEGER NOT NULL,
            available_date TEXT NOT NULL,
            availability_semantics TEXT NOT NULL,
            source_payload_sha256 TEXT NOT NULL,
            PRIMARY KEY (trade_date, symbol)
        );
        CREATE TABLE IF NOT EXISTS daily_symbol_coverage (
            trade_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            source_coverage_status TEXT NOT NULL,
            PRIMARY KEY (trade_date, symbol)
        );
        CREATE TABLE IF NOT EXISTS retrieval_failures (
            trade_date TEXT PRIMARY KEY,
            failure_status TEXT NOT NULL,
            error_type TEXT NOT NULL,
            attempts INTEGER NOT NULL,
            last_attempt_at TEXT NOT NULL
        );
        """
    )


def _verify_existing_metadata(connection: sqlite3.Connection, universe: FrozenTWSEResearchUniverse, requested_dates: tuple[date, ...]) -> None:
    rows = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
    if not rows:
        return
    expected = {
        "artifact_id": TWSE_INSTITUTIONAL_FLOW_ARTIFACT_ID_V1,
        "normalization_version": TWSE_T86_NORMALIZATION_V1,
        "universe_id": universe.universe_id,
        "requested_dates_sha256": _sha256_text("\n".join(day.isoformat() for day in requested_dates)),
    }
    for key, value in expected.items():
        if rows.get(key) != value:
            raise TWSEInstitutionalFlowMaterializationError(f"Existing partial artifact metadata mismatch: {key}.")


def _record_metadata(connection: sqlite3.Connection, universe: FrozenTWSEResearchUniverse, requested_dates: tuple[date, ...], available_dates: dict[date, date]) -> None:
    records = {
        "artifact_id": TWSE_INSTITUTIONAL_FLOW_ARTIFACT_ID_V1,
        "normalization_version": TWSE_T86_NORMALIZATION_V1,
        "availability_semantics": TWSE_T86_AVAILABILITY_V1,
        "availability_quality": CONSERVATIVE_NEXT_SESSION_PROXY,
        "revision_risk_classification": REVISION_SEMANTICS_PRESENT_BUT_DEFINED,
        "universe_id": universe.universe_id,
        "universe_version": universe.universe_version,
        "requested_dates_sha256": _sha256_text("\n".join(day.isoformat() for day in requested_dates)),
        "available_dates_sha256": _sha256_text("\n".join(f"{day.isoformat()}:{available_dates[day].isoformat()}" for day in requested_dates)),
    }
    connection.executemany("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", records.items())
    connection.commit()


def _persist_payload(
    *,
    connection: sqlite3.Connection,
    trade_date: date,
    available_date: date,
    source_url: str,
    payload: bytes,
    retrieved_at: datetime,
    universe: FrozenTWSEResearchUniverse,
) -> None:
    decoded = _decode_payload(payload, trade_date)
    fields = tuple(decoded["fields"])
    schema_signature = _schema_signature(fields)
    status = "SUCCESS" if decoded.get("stat") == "OK" else "EXPLICITLY_AUDITED_NO_DATA"
    if status == "SUCCESS" and fields != T86_FIELDS_V1:
        raise TWSEInstitutionalFlowMaterializationError(
            f"SCHEMA_VERSION_REVIEW_REQUIRED for {trade_date.isoformat()}: {schema_signature}."
        )
    rows = decoded["data"]
    if not isinstance(rows, list):
        raise TWSEInstitutionalFlowMaterializationError(f"Official T86 rows are invalid for {trade_date.isoformat()}.")
    if status == "EXPLICITLY_AUDITED_NO_DATA" and rows:
        raise TWSEInstitutionalFlowMaterializationError("Non-OK T86 response unexpectedly contains rows.")
    payload_sha = hashlib.sha256(payload).hexdigest()
    connection.execute(
        """
        INSERT INTO source_payloads (
            trade_date, available_date, source_url, retrieved_at, payload_sha256, raw_row_count,
            schema_signature, fields_json, source_status, raw_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_date.isoformat(), available_date.isoformat(), source_url, retrieved_at.astimezone(UTC).isoformat(), payload_sha,
            len(rows), schema_signature, json.dumps(fields, ensure_ascii=False), status, payload,
        ),
    )
    source_codes: set[str] = set()
    universe_codes = {symbol.removesuffix(".TW") for symbol in universe.symbols}
    if status == "SUCCESS":
        for raw_row in rows:
            normalized = _normalize_row(raw_row, fields, trade_date, available_date, payload_sha)
            code = normalized["symbol"].removesuffix(".TW")
            if code in universe_codes:
                source_codes.add(code)
                connection.execute(
                    """
                    INSERT INTO normalized_flows VALUES (
                        :trade_date, :symbol, :foreign_ex_dealer_buy, :foreign_ex_dealer_sell, :foreign_ex_dealer_net,
                        :foreign_dealer_buy, :foreign_dealer_sell, :foreign_dealer_net, :trust_buy, :trust_sell, :trust_net,
                        :dealer_proprietary_buy, :dealer_proprietary_sell, :dealer_proprietary_net,
                        :dealer_hedge_buy, :dealer_hedge_sell, :dealer_hedge_net, :dealer_total_net,
                        :total_institutional_net, :available_date, :availability_semantics, :source_payload_sha256
                    )
                    """,
                    normalized,
                )
    coverage_rows = [
        (
            trade_date.isoformat(),
            symbol,
            "PRESENT" if symbol.removesuffix(".TW") in source_codes else (
                "NOT_IN_SOURCE_RESPONSE" if status == "SUCCESS" else "EXPLICITLY_AUDITED_NO_DATA"
            ),
        )
        for symbol in universe.symbols
    ]
    connection.executemany("INSERT INTO daily_symbol_coverage VALUES (?, ?, ?)", coverage_rows)


def _decode_payload(payload: bytes, trade_date: date) -> dict:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TWSEInstitutionalFlowMaterializationError(f"Official T86 payload is not strict UTF-8 JSON for {trade_date.isoformat()}.") from exc
    if not isinstance(decoded, dict) or not isinstance(decoded.get("fields"), list):
        raise TWSEInstitutionalFlowMaterializationError(f"Official T86 payload is missing fields for {trade_date.isoformat()}.")
    return decoded


def _normalize_row(raw_row: object, fields: tuple[str, ...], trade_date: date, available_date: date, payload_sha: str) -> dict[str, object]:
    if not isinstance(raw_row, list) or len(raw_row) != len(fields):
        raise TWSEInstitutionalFlowMaterializationError(f"Official T86 row width mismatch for {trade_date.isoformat()}.")
    values = dict(zip(fields, raw_row, strict=True))
    code = values["證券代號"]
    if not isinstance(code, str) or not code.isdigit() or len(code) != 4:
        return {"symbol": f"NON_CANDIDATE:{code}"}
    result = {
        "trade_date": trade_date.isoformat(),
        "symbol": f"{code}.TW",
        "foreign_ex_dealer_buy": _integer(values, T86_FIELDS_V1[2]),
        "foreign_ex_dealer_sell": _integer(values, T86_FIELDS_V1[3]),
        "foreign_ex_dealer_net": _integer(values, T86_FIELDS_V1[4]),
        "foreign_dealer_buy": _integer(values, T86_FIELDS_V1[5]),
        "foreign_dealer_sell": _integer(values, T86_FIELDS_V1[6]),
        "foreign_dealer_net": _integer(values, T86_FIELDS_V1[7]),
        "trust_buy": _integer(values, T86_FIELDS_V1[8]),
        "trust_sell": _integer(values, T86_FIELDS_V1[9]),
        "trust_net": _integer(values, T86_FIELDS_V1[10]),
        "dealer_total_net": _integer(values, T86_FIELDS_V1[11]),
        "dealer_proprietary_buy": _integer(values, T86_FIELDS_V1[12]),
        "dealer_proprietary_sell": _integer(values, T86_FIELDS_V1[13]),
        "dealer_proprietary_net": _integer(values, T86_FIELDS_V1[14]),
        "dealer_hedge_buy": _integer(values, T86_FIELDS_V1[15]),
        "dealer_hedge_sell": _integer(values, T86_FIELDS_V1[16]),
        "dealer_hedge_net": _integer(values, T86_FIELDS_V1[17]),
        "total_institutional_net": _integer(values, T86_FIELDS_V1[18]),
        "available_date": available_date.isoformat(),
        "availability_semantics": TWSE_T86_AVAILABILITY_V1,
        "source_payload_sha256": payload_sha,
    }
    _validate_invariants(result)
    return result


def _integer(values: dict[str, object], field: str) -> int:
    value = values[field]
    if not isinstance(value, str):
        raise TWSEInstitutionalFlowMaterializationError(f"Official T86 {field} is not a string integer.")
    normalized = value.replace(",", "").strip()
    try:
        return int(normalized)
    except ValueError as exc:
        raise TWSEInstitutionalFlowMaterializationError(f"Official T86 {field} is not an integer.") from exc


def _validate_invariants(row: dict[str, object]) -> None:
    pairs = (
        ("foreign_ex_dealer",), ("foreign_dealer",), ("trust",), ("dealer_proprietary",), ("dealer_hedge",),
    )
    for (prefix,) in pairs:
        if row[f"{prefix}_net"] != row[f"{prefix}_buy"] - row[f"{prefix}_sell"]:
            raise TWSEInstitutionalFlowMaterializationError(f"Official T86 arithmetic invariant failed: {prefix}_net.")
    if row["dealer_total_net"] != row["dealer_proprietary_net"] + row["dealer_hedge_net"]:
        raise TWSEInstitutionalFlowMaterializationError("Official T86 arithmetic invariant failed: dealer_total_net.")
    if row["total_institutional_net"] != row["foreign_ex_dealer_net"] + row["trust_net"] + row["dealer_total_net"]:
        raise TWSEInstitutionalFlowMaterializationError("Official T86 arithmetic invariant failed: total_institutional_net.")


def _completed_dates(connection: sqlite3.Connection) -> set[date]:
    return {date.fromisoformat(row[0]) for row in connection.execute("SELECT trade_date FROM source_payloads")}


def _record_failure(
    connection: sqlite3.Connection,
    trade_date: date,
    failure_status: str,
    error_type: str,
    attempts: int,
    timestamp: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO retrieval_failures VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(trade_date) DO UPDATE SET
            failure_status = excluded.failure_status,
            error_type = excluded.error_type,
            attempts = excluded.attempts,
            last_attempt_at = excluded.last_attempt_at
        """,
        (trade_date.isoformat(), failure_status, error_type, attempts, timestamp.astimezone(UTC).isoformat()),
    )


def _remaining_dates(database_path: Path, requested_dates: tuple[date, ...]) -> tuple[date, ...]:
    connection = sqlite3.connect(database_path)
    try:
        completed = _completed_dates(connection)
    finally:
        connection.close()
    return tuple(day for day in requested_dates if day not in completed)


def _validate_database(
    connection: sqlite3.Connection,
    universe: FrozenTWSEResearchUniverse,
    research_db_path: Path,
) -> dict[str, object]:
    source_rows = connection.execute("SELECT source_status, schema_signature FROM source_payloads").fetchall()
    normalized_rows = connection.execute("SELECT * FROM normalized_flows ORDER BY trade_date, symbol").fetchall()
    for row in normalized_rows:
        _validate_invariants(dict(zip((column[0] for column in connection.execute("SELECT * FROM normalized_flows LIMIT 0").description), row)))
    exact_price_matches, missing_price_pairs = _exact_price_date_coverage(connection, research_db_path)
    per_year = {}
    for year, raw_rows, normalized_count, symbols in connection.execute(
        """
        SELECT substr(source_payloads.trade_date, 1, 4), SUM(source_payloads.raw_row_count), COUNT(normalized_flows.symbol),
               COUNT(DISTINCT normalized_flows.symbol)
        FROM source_payloads LEFT JOIN normalized_flows USING (trade_date)
        GROUP BY substr(source_payloads.trade_date, 1, 4) ORDER BY 1
        """
    ):
        per_year[year] = {"raw_source_rows": raw_rows or 0, "normalized_rows": normalized_count, "unique_symbols": symbols}
    digest_lines = ["|".join(str(value) for value in row) for row in normalized_rows]
    return {
        "successful_dates": sum(status == "SUCCESS" for status, _ in source_rows),
        "audited_no_data_dates": sum(status == "EXPLICITLY_AUDITED_NO_DATA" for status, _ in source_rows),
        "failed_dates": connection.execute("SELECT COUNT(*) FROM retrieval_failures").fetchone()[0],
        "raw_source_rows": sum(row[0] for row in connection.execute("SELECT raw_row_count FROM source_payloads")),
        "normalized_rows": len(normalized_rows),
        "unique_symbols": connection.execute("SELECT COUNT(DISTINCT symbol) FROM normalized_flows").fetchone()[0],
        "unique_schema_signatures": sorted({signature for _, signature in source_rows}),
        "normalized_data_sha256": _sha256_text("\n".join(digest_lines)),
        "exact_price_date_matches": exact_price_matches,
        "missing_price_date_pairs": missing_price_pairs,
        "per_year": per_year,
        "candidate_universe_size": len(universe.symbols),
    }


def _exact_price_date_coverage(connection: sqlite3.Connection, research_db_path: Path) -> tuple[int, int]:
    # The institutional-flow artifact remains independent; attach the immutable price store only for exact coverage audit.
    uri = research_db_path.resolve().as_uri() + "?mode=ro"
    connection.execute("ATTACH DATABASE ? AS research_prices", (uri,))
    try:
        matches = connection.execute(
            """
            SELECT COUNT(*)
            FROM normalized_flows AS flow
            JOIN research_prices.historical_prices AS price
              ON price.symbol = flow.symbol AND price.trading_date = flow.trade_date
            """
        ).fetchone()[0]
        total = connection.execute("SELECT COUNT(*) FROM normalized_flows").fetchone()[0]
        return matches, total - matches
    finally:
        connection.execute("DETACH DATABASE research_prices")


def _build_manifest(*, database_path: Path, database_sha256: str, universe: FrozenTWSEResearchUniverse, requested_dates: tuple[date, ...], validation: dict[str, object], request_count: int, retry_count: int) -> dict[str, object]:
    return {
        "artifact_identity": TWSE_INSTITUTIONAL_FLOW_ARTIFACT_ID_V1,
        "normalization_version": TWSE_T86_NORMALIZATION_V1,
        "availability": {
            "semantics": TWSE_T86_AVAILABILITY_V1,
            "quality": CONSERVATIVE_NEXT_SESSION_PROXY,
            "flow_date_rule": "TWSE T86 trade date",
            "available_date_rule": "next valid local 0050.TW trading session",
        },
        "source": {"identity": "OFFICIAL_TWSE_T86", "endpoint": TWSE_T86_ENDPOINT},
        "revision_risk_classification": REVISION_SEMANTICS_PRESENT_BUT_DEFINED,
        "coverage": {
            "start": requested_dates[0].isoformat(), "end": requested_dates[-1].isoformat(),
            "requested_dates": len(requested_dates), "successful_dates": validation["successful_dates"],
            "audited_no_data_dates": validation["audited_no_data_dates"], "failed_dates": validation["failed_dates"],
            "per_year": validation["per_year"],
        },
        "schema_signatures": validation["unique_schema_signatures"],
        "candidate_universe": {"id": universe.universe_id, "version": universe.universe_version, "size": len(universe.symbols)},
        "counts": {"raw_source_rows": validation["raw_source_rows"], "normalized_rows": validation["normalized_rows"], "unique_symbols": validation["unique_symbols"]},
        "exact_price_date_coverage": {"matches": validation["exact_price_date_matches"], "missing_pairs": validation["missing_price_date_pairs"]},
        "payload_lineage": {"database_sha256": database_sha256, "normalized_data_sha256": validation["normalized_data_sha256"]},
        "request_statistics": {"request_count": request_count, "retry_count": retry_count},
        "location": _display_path(database_path),
        "known_limitations": [
            "Historical revision semantics are defined as same-day original trade statistics, excluding later broker error/account corrections.",
            "Availability is a conservative next-session proxy; no intraday publication timestamp is claimed.",
            "Missing source rows are coverage observations, never zero-flow records.",
        ],
    }


def _schema_signature(fields: tuple[str, ...]) -> str:
    return _sha256_text("\u001f".join(fields))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
