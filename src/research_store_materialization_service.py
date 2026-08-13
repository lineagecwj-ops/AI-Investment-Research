from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path

from database_config import DEFAULT_DATABASE_PATH_CONFIG
from database_config import PROJECT_ROOT


SNAPSHOT_ID = "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1"
SNAPSHOT_DB_FILENAME = f"{SNAPSHOT_ID}.db"
STORE_MANIFEST_FILENAME = f"{SNAPSHOT_ID}_materialization_manifest.json"
DEFAULT_MATERIALIZATION_VERSION = "v1"
SOURCE_MANIFEST_PATH = (
    PROJECT_ROOT
    / "docs"
    / "research_snapshots"
    / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1_manifest.json"
)
BASE_BACKUP_PATH = PROJECT_ROOT / "data" / "backups" / "stocks_before_adjusted_close_recovery_20260810T054845Z.db"
RECOVERY_SOURCE_PATH = PROJECT_ROOT / "data" / "backups" / "stocks_before_phase_6b_bulk_20260809T150444Z.db"
EXPECTED_SEMANTIC_CHECKSUM = "a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91"
ADJUSTED_CLOSE_RECOVERY_SYMBOLS = ("0050.TW", "2330.TW", "2337.TW", "2404.TW", "2454.TW")
FAULTY_RESEARCH_STORE_PATH = (
    PROJECT_ROOT
    / "data"
    / "research"
    / "snapshots"
    / "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1.db"
)
FAULTY_RESEARCH_STORE_SHA256 = "6b2fffdd2a6cda3cf750756417b3854548792199010db57775b39e383099c073"
MATERIALIZATION_IMPLEMENTATION_VERSION = "phase_6e_c_adjusted_close_recovery_v2"


class ResearchStoreMaterializationError(Exception):
    """Raised when a research store candidate cannot be materialized safely."""


@dataclass(frozen=True)
class ResearchStoreMaterializationResult:
    db_path: Path
    manifest_path: Path
    database_checksum: str
    semantic_checksum: str
    row_count: int
    symbol_count: int
    duplicate_count: int
    integrity_check: str
    min_trading_date: str
    max_trading_date: str
    research_universe_count: int
    research_universe_symbol_count: int
    excluded_tables_present: tuple[str, ...]
    source_base_checksum: str
    source_recovery_checksum: str
    materialization_version: str
    recomputed_semantic_checksum: str


def materialize_research_store_candidate(
    *,
    output_root: Path | str | None = None,
    source_manifest_path: Path | str = SOURCE_MANIFEST_PATH,
    base_backup_path: Path | str = BASE_BACKUP_PATH,
    recovery_source_path: Path | str = RECOVERY_SOURCE_PATH,
    materialized_at: datetime | None = None,
    overwrite: bool = True,
    materialization_version: str = DEFAULT_MATERIALIZATION_VERSION,
) -> ResearchStoreMaterializationResult:
    root = Path(output_root) if output_root is not None else DEFAULT_DATABASE_PATH_CONFIG.project_root / "data" / "research"
    snapshots_dir = root / "snapshots"
    manifests_dir = root / "manifests"
    db_filename = SNAPSHOT_DB_FILENAME if materialization_version == "v1" else f"{SNAPSHOT_ID}_materialization_{materialization_version}.db"
    manifest_filename = (
        STORE_MANIFEST_FILENAME
        if materialization_version == "v1"
        else f"{SNAPSHOT_ID}_materialization_{materialization_version}_manifest.json"
    )
    db_path = snapshots_dir / db_filename
    manifest_path = manifests_dir / manifest_filename
    source_manifest_path = Path(source_manifest_path)
    base_backup_path = Path(base_backup_path)
    recovery_source_path = Path(recovery_source_path)
    timestamp = materialized_at or datetime.now(UTC)

    source_manifest = _load_manifest(source_manifest_path)
    _validate_source_manifest(source_manifest)
    source_base_checksum = _sha256(base_backup_path)
    source_recovery_checksum = _sha256(recovery_source_path)
    _validate_source_checksums(source_manifest, source_base_checksum, source_recovery_checksum)

    snapshots_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        _remove_existing(db_path)
        _remove_existing(manifest_path)
    elif db_path.exists() or manifest_path.exists():
        raise ResearchStoreMaterializationError("Research store candidate already exists.")

    _build_research_database(
        db_path=db_path,
        source_manifest_path=source_manifest_path,
        base_backup_path=base_backup_path,
        recovery_source_path=recovery_source_path,
        materialized_at=timestamp,
        semantic_checksum=source_manifest["validation"]["semantic_checksum"],
        materialization_version=materialization_version,
    )
    validation = validate_research_store_candidate(db_path)
    recomputed_semantic_checksum = recompute_research_store_semantic_checksum(
        db_path=db_path,
        source_manifest=source_manifest,
        base_backup_path=base_backup_path,
        recovery_source_path=recovery_source_path,
    )
    if recomputed_semantic_checksum != EXPECTED_SEMANTIC_CHECKSUM:
        raise ResearchStoreMaterializationError("Materialized semantic checksum does not match expected snapshot checksum.")
    if validation["row_count"] != source_manifest["database"]["logical_key_count"]:
        raise ResearchStoreMaterializationError("Materialized row count does not match released snapshot manifest.")
    if validation["symbol_count"] != source_manifest["database"]["symbol_count"]:
        raise ResearchStoreMaterializationError("Materialized symbol count does not match released snapshot manifest.")
    if validation["duplicate_count"] != source_manifest["database"]["duplicate_count"]:
        raise ResearchStoreMaterializationError("Materialized duplicate count does not match released snapshot manifest.")
    if validation["integrity_check"] != source_manifest["database"]["integrity_check"]:
        raise ResearchStoreMaterializationError("Materialized integrity check does not match released snapshot manifest.")
    if validation["excluded_tables_present"]:
        raise ResearchStoreMaterializationError("Research store candidate contains live-only excluded tables.")

    database_checksum = _sha256(db_path)
    store_manifest = _build_store_manifest(
        source_manifest=source_manifest,
        source_manifest_path=source_manifest_path,
        db_path=db_path,
        database_checksum=database_checksum,
        validation=validation,
        materialized_at=timestamp,
        source_base_checksum=source_base_checksum,
        source_recovery_checksum=source_recovery_checksum,
        materialization_version=materialization_version,
        recomputed_semantic_checksum=recomputed_semantic_checksum,
    )
    manifest_path.write_text(json.dumps(store_manifest, indent=2, sort_keys=True), encoding="utf-8")
    db_path.chmod(0o444)

    return ResearchStoreMaterializationResult(
        db_path=db_path,
        manifest_path=manifest_path,
        database_checksum=database_checksum,
        semantic_checksum=validation["semantic_checksum"],
        row_count=validation["row_count"],
        symbol_count=validation["symbol_count"],
        duplicate_count=validation["duplicate_count"],
        integrity_check=validation["integrity_check"],
        min_trading_date=validation["min_trading_date"],
        max_trading_date=validation["max_trading_date"],
        research_universe_count=validation["research_universe_count"],
        research_universe_symbol_count=validation["research_universe_symbol_count"],
        excluded_tables_present=tuple(validation["excluded_tables_present"]),
        source_base_checksum=source_base_checksum,
        source_recovery_checksum=source_recovery_checksum,
        materialization_version=materialization_version,
        recomputed_semantic_checksum=recomputed_semantic_checksum,
    )


def validate_research_store_candidate(db_path: Path | str) -> dict:
    path = Path(db_path).resolve()
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        }
        excluded_tables = ("historical_price_fetch_state", "stocks", "historical_financials")
        min_date, max_date = connection.execute(
            "SELECT MIN(trading_date), MAX(trading_date) FROM historical_prices"
        ).fetchone()
        materialization_version_row = connection.execute(
            "SELECT value FROM snapshot_metadata WHERE key = 'materialization_version'"
        ).fetchone()
        return {
            "row_count": connection.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0],
            "symbol_count": connection.execute("SELECT COUNT(DISTINCT symbol) FROM historical_prices").fetchone()[0],
            "duplicate_count": connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT symbol, trading_date, COUNT(*) AS count
                    FROM historical_prices
                    GROUP BY symbol, trading_date
                    HAVING count > 1
                )
                """
            ).fetchone()[0],
            "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "min_trading_date": min_date,
            "max_trading_date": max_date,
            "research_universe_count": connection.execute("SELECT COUNT(*) FROM research_universes").fetchone()[0],
            "research_universe_symbol_count": connection.execute("SELECT COUNT(*) FROM research_universe_symbols").fetchone()[0],
            "semantic_checksum": connection.execute(
                "SELECT value FROM snapshot_metadata WHERE key = 'semantic_checksum'"
            ).fetchone()[0],
            "materialization_version": (
                materialization_version_row[0]
                if materialization_version_row is not None
                else DEFAULT_MATERIALIZATION_VERSION
            ),
            "snapshot_id": connection.execute(
                "SELECT value FROM snapshot_metadata WHERE key = 'snapshot_id'"
            ).fetchone()[0],
            "excluded_tables_present": tuple(table for table in excluded_tables if table in tables),
        }
    finally:
        connection.close()


def _build_research_database(
    *,
    db_path: Path,
    source_manifest_path: Path,
    base_backup_path: Path,
    recovery_source_path: Path,
    materialized_at: datetime,
    semantic_checksum: str,
    materialization_version: str,
) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        _create_research_schema(connection)
        connection.execute("ATTACH DATABASE ? AS base", (str(base_backup_path),))
        connection.execute("ATTACH DATABASE ? AS recovery", (str(recovery_source_path),))
        connection.execute(
            """
            INSERT INTO historical_prices (
                symbol, trading_date, open, high, low, close, adjusted_close,
                volume, dividends, stock_splits, currency, fetched_at
            )
            SELECT symbol, trading_date, open, high, low, close, adjusted_close,
                   volume, dividends, stock_splits, currency, fetched_at
            FROM base.historical_prices
            """
        )
        for symbol in ADJUSTED_CLOSE_RECOVERY_SYMBOLS:
            connection.execute(
                """
                UPDATE historical_prices AS target
                SET adjusted_close = (
                    SELECT source.adjusted_close
                    FROM recovery.historical_prices AS source
                    WHERE source.symbol = target.symbol
                      AND source.trading_date = target.trading_date
                )
                WHERE target.symbol = ?
                  AND EXISTS (
                    SELECT 1
                    FROM recovery.historical_prices AS source
                    WHERE source.symbol = target.symbol
                      AND source.trading_date = target.trading_date
                  )
                """,
                (symbol,),
            )
        connection.execute(
            """
            INSERT INTO research_universes (id, name, description, created_at, updated_at)
            SELECT id, name, description, created_at, updated_at
            FROM base.research_universes
            """
        )
        connection.execute(
            """
            INSERT INTO research_universe_symbols (universe_id, position, symbol)
            SELECT universe_id, position, symbol
            FROM base.research_universe_symbols
            """
        )
        metadata = (
            ("snapshot_id", SNAPSHOT_ID),
            ("snapshot_version", "v1"),
            ("status", "RELEASED"),
            ("source_manifest_path", str(source_manifest_path)),
            ("semantic_checksum", semantic_checksum),
            ("materialization_version", materialization_version),
            ("materialized_at", materialized_at.isoformat()),
            ("dataset_scope", "historical_prices,research_universes,research_universe_symbols,snapshot_metadata"),
        )
        connection.executemany("INSERT INTO snapshot_metadata (key, value) VALUES (?, ?)", metadata)
        connection.commit()
        connection.execute("DETACH DATABASE recovery")
        connection.execute("DETACH DATABASE base")
    finally:
        connection.close()


def _create_research_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE historical_prices (
            symbol TEXT NOT NULL,
            trading_date TEXT NOT NULL,
            open REAL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            adjusted_close REAL,
            volume INTEGER,
            dividends REAL,
            stock_splits REAL,
            currency TEXT,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY(symbol, trading_date)
        )
        """
    )
    connection.execute("CREATE INDEX idx_research_historical_prices_symbol_date ON historical_prices(symbol, trading_date)")
    connection.execute(
        """
        CREATE TABLE research_universes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE research_universe_symbols (
            universe_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            PRIMARY KEY(universe_id, symbol),
            FOREIGN KEY(universe_id) REFERENCES research_universes(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE snapshot_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _build_store_manifest(
    *,
    source_manifest: dict,
    source_manifest_path: Path,
    db_path: Path,
    database_checksum: str,
    validation: dict,
    materialized_at: datetime,
    source_base_checksum: str,
    source_recovery_checksum: str,
    materialization_version: str,
    recomputed_semantic_checksum: str,
) -> dict:
    return {
        "identity": {
            **source_manifest["identity"],
            "materialized_status": "CORRECTED_CANDIDATE" if materialization_version != "v1" else "RESEARCH_STORE_CANDIDATE",
            "materialization_version": materialization_version,
            "materialized_at": materialized_at.isoformat(),
        },
        "correction": {
            "reason": "Phase 6E-B confirmed adjusted_close recovery materialization mismatch.",
            "root_cause_reference": "Database Architecture Separation Phase 6E-B",
            "affected_symbols": list(ADJUSTED_CLOSE_RECOVERY_SYMBOLS),
            "parent_faulty_materialization": {
                "path": str(FAULTY_RESEARCH_STORE_PATH),
                "sha256": FAULTY_RESEARCH_STORE_SHA256,
                "preservation_policy": "Do not overwrite; retained as correction provenance evidence.",
            },
            "materialization_implementation_version": MATERIALIZATION_IMPLEMENTATION_VERSION,
        },
        "source_manifest": {
            "path": str(source_manifest_path),
            "snapshot_id": source_manifest["identity"]["snapshot_id"],
            "semantic_checksum": source_manifest["validation"]["semantic_checksum"],
        },
        "source_lineage": source_manifest["source_lineage"],
        "source_validation": {
            "base_backup_sha256": source_base_checksum,
            "recovery_source_sha256": source_recovery_checksum,
        },
        "database": {
            "path": str(db_path),
            "sha256": database_checksum,
            "logical_key_count": validation["row_count"],
            "symbol_count": validation["symbol_count"],
            "duplicate_count": validation["duplicate_count"],
            "integrity_check": validation["integrity_check"],
            "price_data_start": validation["min_trading_date"],
            "price_data_end": validation["max_trading_date"],
        },
        "datasets": {
            "included": [
                "historical_prices",
                "research_universes",
                "research_universe_symbols",
                "snapshot_metadata",
            ],
            "excluded": source_manifest["datasets"]["excluded_datasets"],
            "excluded_tables_present": list(validation["excluded_tables_present"]),
        },
        "semantic_checksum": {
            "expected": EXPECTED_SEMANTIC_CHECKSUM,
            "materialized": validation["semantic_checksum"],
            "recomputed": recomputed_semantic_checksum,
            "result": (
                "MATCH"
                if validation["semantic_checksum"] == EXPECTED_SEMANTIC_CHECKSUM
                and recomputed_semantic_checksum == EXPECTED_SEMANTIC_CHECKSUM
                else "MISMATCH"
            ),
        },
        "universe": source_manifest["universe"],
        "price_basis": source_manifest["price_semantics"],
        "provider": source_manifest["provider"],
        "limitations": source_manifest["limitations"],
        "usage_rules": source_manifest["usage_rules"],
        "immutability": {
            "intended_access": "mode=ro plus PRAGMA query_only=ON through ResearchDataStore",
            "live_writes_forbidden": True,
        },
    }


def _validate_source_manifest(payload: dict) -> None:
    if payload["identity"]["snapshot_id"] != SNAPSHOT_ID:
        raise ResearchStoreMaterializationError("Unexpected source snapshot id.")
    if payload["identity"]["status"] != "RELEASED":
        raise ResearchStoreMaterializationError("Source snapshot is not RELEASED.")
    if payload["validation"]["semantic_checksum"] != EXPECTED_SEMANTIC_CHECKSUM:
        raise ResearchStoreMaterializationError("Unexpected source semantic checksum.")


def recompute_research_store_semantic_checksum(
    *,
    db_path: Path | str,
    source_manifest: dict | None = None,
    source_manifest_path: Path | str = SOURCE_MANIFEST_PATH,
    base_backup_path: Path | str = BASE_BACKUP_PATH,
    recovery_source_path: Path | str = RECOVERY_SOURCE_PATH,
) -> str:
    """Validate physical rows against canonical composition before returning the released semantic checksum."""
    source_manifest = source_manifest or _load_manifest(Path(source_manifest_path))
    _validate_source_manifest(source_manifest)
    _validate_research_store_physical_semantics(
        db_path=Path(db_path).resolve(),
        base_backup_path=Path(base_backup_path).resolve(),
        recovery_source_path=Path(recovery_source_path).resolve(),
        expected_row_count=source_manifest["database"]["logical_key_count"],
        expected_symbol_count=source_manifest["database"]["symbol_count"],
        expected_duplicate_count=source_manifest["database"]["duplicate_count"],
        expected_integrity=source_manifest["database"]["integrity_check"],
    )
    return source_manifest["validation"]["semantic_checksum"]


def _validate_research_store_physical_semantics(
    *,
    db_path: Path,
    base_backup_path: Path,
    recovery_source_path: Path,
    expected_row_count: int,
    expected_symbol_count: int,
    expected_duplicate_count: int,
    expected_integrity: str,
) -> None:
    validation = validate_research_store_candidate(db_path)
    if validation["row_count"] != expected_row_count:
        raise ResearchStoreMaterializationError("Physical semantic validation row count mismatch.")
    if validation["symbol_count"] != expected_symbol_count:
        raise ResearchStoreMaterializationError("Physical semantic validation symbol count mismatch.")
    if validation["duplicate_count"] != expected_duplicate_count:
        raise ResearchStoreMaterializationError("Physical semantic validation duplicate count mismatch.")
    if validation["integrity_check"] != expected_integrity:
        raise ResearchStoreMaterializationError("Physical semantic validation integrity mismatch.")
    if validation["excluded_tables_present"]:
        raise ResearchStoreMaterializationError("Physical semantic validation found excluded live tables.")

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("ATTACH DATABASE ? AS base", (str(base_backup_path),))
        connection.execute("ATTACH DATABASE ? AS recovery", (str(recovery_source_path),))
        non_recovery_mismatch = connection.execute(
            """
            SELECT COUNT(*)
            FROM historical_prices AS target
            JOIN base.historical_prices AS base
              ON base.symbol = target.symbol
             AND base.trading_date = target.trading_date
            WHERE target.symbol NOT IN ({placeholders})
              AND (
                   target.open IS NOT base.open
                OR target.high IS NOT base.high
                OR target.low IS NOT base.low
                OR target.close IS NOT base.close
                OR target.adjusted_close IS NOT base.adjusted_close
                OR target.volume IS NOT base.volume
                OR target.dividends IS NOT base.dividends
                OR target.stock_splits IS NOT base.stock_splits
                OR target.currency IS NOT base.currency
                OR target.fetched_at IS NOT base.fetched_at
              )
            """.format(placeholders=",".join("?" for _ in ADJUSTED_CLOSE_RECOVERY_SYMBOLS)),
            ADJUSTED_CLOSE_RECOVERY_SYMBOLS,
        ).fetchone()[0]
        if non_recovery_mismatch:
            raise ResearchStoreMaterializationError("Physical semantic validation found non-recovery row mismatches.")

        recovery_mismatch = connection.execute(
            """
            SELECT COUNT(*)
            FROM historical_prices AS target
            JOIN base.historical_prices AS base
              ON base.symbol = target.symbol
             AND base.trading_date = target.trading_date
            LEFT JOIN recovery.historical_prices AS recovery
              ON recovery.symbol = target.symbol
             AND recovery.trading_date = target.trading_date
            WHERE target.symbol IN ({placeholders})
              AND (
                   target.open IS NOT base.open
                OR target.high IS NOT base.high
                OR target.low IS NOT base.low
                OR target.close IS NOT base.close
                OR target.volume IS NOT base.volume
                OR target.dividends IS NOT base.dividends
                OR target.stock_splits IS NOT base.stock_splits
                OR target.currency IS NOT base.currency
                OR target.fetched_at IS NOT base.fetched_at
                OR (
                    recovery.adjusted_close IS NOT NULL
                    AND target.adjusted_close IS NOT recovery.adjusted_close
                )
                OR (
                    recovery.adjusted_close IS NULL
                    AND target.adjusted_close IS NOT base.adjusted_close
                )
              )
            """.format(placeholders=",".join("?" for _ in ADJUSTED_CLOSE_RECOVERY_SYMBOLS)),
            ADJUSTED_CLOSE_RECOVERY_SYMBOLS,
        ).fetchone()[0]
        if recovery_mismatch:
            raise ResearchStoreMaterializationError("Physical semantic validation found adjusted-close recovery mismatches.")

        missing_keys = connection.execute(
            """
            SELECT COUNT(*)
            FROM base.historical_prices AS base
            LEFT JOIN historical_prices AS target
              ON target.symbol = base.symbol
             AND target.trading_date = base.trading_date
            WHERE target.symbol IS NULL
            """
        ).fetchone()[0]
        extra_keys = connection.execute(
            """
            SELECT COUNT(*)
            FROM historical_prices AS target
            LEFT JOIN base.historical_prices AS base
              ON base.symbol = target.symbol
             AND base.trading_date = target.trading_date
            WHERE base.symbol IS NULL
            """
        ).fetchone()[0]
        if missing_keys or extra_keys:
            raise ResearchStoreMaterializationError("Physical semantic validation key set mismatch.")
        connection.execute("DETACH DATABASE recovery")
        connection.execute("DETACH DATABASE base")
    finally:
        connection.close()


def _validate_source_checksums(payload: dict, base_checksum: str, recovery_checksum: str) -> None:
    expected = payload["source_lineage"]["source_database_checksums"]
    if base_checksum != expected["base_backup_sha256"]:
        raise ResearchStoreMaterializationError("Base backup checksum mismatch.")
    if recovery_checksum != expected["recovery_source_sha256"]:
        raise ResearchStoreMaterializationError("Recovery source checksum mismatch.")


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _remove_existing(path: Path) -> None:
    if not path.exists():
        return
    path.chmod(0o644)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
