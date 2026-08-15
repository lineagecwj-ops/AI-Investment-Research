from __future__ import annotations

import sqlite3

from risk import RiskArtifact
from risk import RiskCategory
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.sqlite_storage import decode_core_artifact_row
from risk_persistence.sqlite_technical_index import insert_technical_index_record
from risk_persistence.technical_query_contracts import RiskArtifactIndexCorruptionError
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord


APPLICATION_ID = 0x41494952
SCHEMA_VERSION = 2
SCHEMA_VERSION_V1 = 1

RISK_ARTIFACTS_TABLE = "risk_artifacts"
TECHNICAL_RISK_ARTIFACT_INDEX_TABLE = "technical_risk_artifact_index"
TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX = "idx_technical_risk_artifact_position_latest"

CREATE_RISK_ARTIFACTS_TABLE_SQL = """
CREATE TABLE risk_artifacts (
    artifact_id TEXT PRIMARY KEY CHECK (artifact_id <> ''),
    artifact_checksum TEXT NOT NULL CHECK (artifact_checksum <> ''),
    payload_json TEXT NOT NULL CHECK (payload_json <> '')
)
"""

CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL = """
CREATE TABLE technical_risk_artifact_index (
    artifact_id TEXT PRIMARY KEY CHECK (artifact_id <> ''),
    portfolio_id TEXT NOT NULL CHECK (portfolio_id <> ''),
    position_id TEXT NOT NULL CHECK (position_id <> ''),
    symbol TEXT NOT NULL CHECK (symbol <> ''),
    severity TEXT NOT NULL CHECK (severity <> ''),
    analysis_date TEXT NOT NULL CHECK (analysis_date <> ''),
    valuation_date TEXT NOT NULL CHECK (valuation_date <> ''),
    created_at TEXT NOT NULL CHECK (created_at <> ''),
    calculation_id TEXT NOT NULL CHECK (calculation_id <> ''),
    policy_id TEXT NOT NULL CHECK (policy_id <> ''),
    policy_version TEXT NOT NULL CHECK (policy_version <> ''),
    policy_checksum TEXT NOT NULL CHECK (policy_checksum <> ''),
    evaluation_id TEXT NOT NULL CHECK (evaluation_id <> ''),
    evaluation_checksum TEXT NOT NULL CHECK (evaluation_checksum <> ''),
    producer_version TEXT NOT NULL CHECK (producer_version <> ''),
    FOREIGN KEY (artifact_id) REFERENCES risk_artifacts(artifact_id)
)
"""

CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL = """
CREATE INDEX idx_technical_risk_artifact_position_latest
ON technical_risk_artifact_index (
    portfolio_id,
    position_id,
    analysis_date DESC,
    created_at DESC,
    artifact_id DESC
)
"""

EXPECTED_RISK_ARTIFACT_COLUMNS = {
    "artifact_id": {"type": "TEXT", "notnull": 0, "pk": 1},
    "artifact_checksum": {"type": "TEXT", "notnull": 1, "pk": 0},
    "payload_json": {"type": "TEXT", "notnull": 1, "pk": 0},
}

EXPECTED_TECHNICAL_RISK_ARTIFACT_INDEX_COLUMNS = {
    "artifact_id": {"type": "TEXT", "notnull": 0, "pk": 1},
    "portfolio_id": {"type": "TEXT", "notnull": 1, "pk": 0},
    "position_id": {"type": "TEXT", "notnull": 1, "pk": 0},
    "symbol": {"type": "TEXT", "notnull": 1, "pk": 0},
    "severity": {"type": "TEXT", "notnull": 1, "pk": 0},
    "analysis_date": {"type": "TEXT", "notnull": 1, "pk": 0},
    "valuation_date": {"type": "TEXT", "notnull": 1, "pk": 0},
    "created_at": {"type": "TEXT", "notnull": 1, "pk": 0},
    "calculation_id": {"type": "TEXT", "notnull": 1, "pk": 0},
    "policy_id": {"type": "TEXT", "notnull": 1, "pk": 0},
    "policy_version": {"type": "TEXT", "notnull": 1, "pk": 0},
    "policy_checksum": {"type": "TEXT", "notnull": 1, "pk": 0},
    "evaluation_id": {"type": "TEXT", "notnull": 1, "pk": 0},
    "evaluation_checksum": {"type": "TEXT", "notnull": 1, "pk": 0},
    "producer_version": {"type": "TEXT", "notnull": 1, "pk": 0},
}

_TECHNICAL_METADATA_KEYS = frozenset(
    {
        "technical_policy_id",
        "technical_policy_version",
        "technical_policy_checksum",
        "technical_evaluation_id",
        "technical_evaluation_checksum",
        "technical_position_id",
        "technical_as_of_date",
        "technical_valuation_date",
        "technical_calculation_id",
        "technical_producer_version",
    }
)
_TECHNICAL_FEATURE_LINEAGE_KEYS = frozenset(
    {
        "technical_source_feature_ids",
        "technical_source_checksums",
    }
)


def initialize_or_verify_schema(connection: sqlite3.Connection) -> None:
    application_id = _pragma_int(connection, "application_id")
    user_version = _pragma_int(connection, "user_version")
    user_tables = _user_tables(connection)

    if application_id == 0 and user_version == 0 and not user_tables:
        _initialize_schema_v2(connection)
        return

    if application_id != APPLICATION_ID:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB application_id mismatch.")
    if user_version > SCHEMA_VERSION:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema version is unsupported.")
    if user_version == SCHEMA_VERSION_V1:
        _migrate_v1_to_v2(connection)
        return
    if user_version != SCHEMA_VERSION:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema version mismatch.")
    verify_schema_v2(connection)
    ensure_wal(connection)


def verify_schema_v2(connection: sqlite3.Connection) -> None:
    tables = _user_tables(connection)
    if tables != (RISK_ARTIFACTS_TABLE, TECHNICAL_RISK_ARTIFACT_INDEX_TABLE):
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema tables mismatch.")
    _verify_table_shape(connection, RISK_ARTIFACTS_TABLE, EXPECTED_RISK_ARTIFACT_COLUMNS)
    _verify_table_shape(
        connection,
        TECHNICAL_RISK_ARTIFACT_INDEX_TABLE,
        EXPECTED_TECHNICAL_RISK_ARTIFACT_INDEX_COLUMNS,
    )
    _verify_foreign_key(connection)
    _verify_position_latest_index(connection)
    _verify_required_checks(connection)


def validate_schema_v2_readonly(connection: sqlite3.Connection) -> None:
    if _pragma_int(connection, "application_id") != APPLICATION_ID:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB application_id mismatch.")
    if _pragma_int(connection, "user_version") != SCHEMA_VERSION:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema version mismatch.")
    verify_schema_v2(connection)


def ensure_wal(connection: sqlite3.Connection) -> None:
    journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if str(journal_mode).lower() != "wal":
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB requires WAL journal mode.")


def _initialize_schema_v2(connection: sqlite3.Connection) -> None:
    try:
        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        connection.execute(CREATE_RISK_ARTIFACTS_TABLE_SQL)
        connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL)
        connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL)
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        ensure_wal(connection)
        connection.commit()
    except sqlite3.DatabaseError as exc:
        connection.rollback()
        raise RiskArtifactPersistenceError("SQLite RiskArtifact schema initialization failed.") from exc
    verify_schema_v2(connection)


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    if _user_tables(connection) != (RISK_ARTIFACTS_TABLE,):
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema tables mismatch.")
    _verify_table_shape(connection, RISK_ARTIFACTS_TABLE, EXPECTED_RISK_ARTIFACT_COLUMNS)
    _verify_required_checks(connection, version=SCHEMA_VERSION_V1)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if _pragma_int(connection, "application_id") != APPLICATION_ID:
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB application_id mismatch.")
        if _pragma_int(connection, "user_version") != SCHEMA_VERSION_V1:
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema version mismatch.")
        if _user_tables(connection) != (RISK_ARTIFACTS_TABLE,):
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema tables mismatch.")
        connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_INDEX_TABLE_SQL)
        connection.execute(CREATE_TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX_SQL)
        _backfill_technical_index(connection)
        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        connection.commit()
    except (sqlite3.DatabaseError, RiskArtifactPersistenceError) as exc:
        if connection.in_transaction:
            connection.rollback()
        if isinstance(exc, RiskArtifactPersistenceError):
            raise
        raise RiskArtifactPersistenceError("SQLite RiskArtifact schema migration failed.") from exc
    verify_schema_v2(connection)
    ensure_wal(connection)


def _backfill_technical_index(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT artifact_id, artifact_checksum, payload_json
        FROM risk_artifacts
        ORDER BY artifact_id
        """
    ).fetchall()
    for row in rows:
        artifact = decode_core_artifact_row(row)
        classification = _classify_artifact(artifact)
        if classification == "VALID_NON_TECHNICAL":
            continue
        record = TechnicalRiskArtifactIndexRecord.from_artifact(artifact)
        insert_technical_index_record(connection, record)


def _classify_artifact(artifact: RiskArtifact) -> str:
    has_technical_signal = any(signal.category == RiskCategory.TECHNICAL for signal in artifact.signals)
    has_technical_metadata = any(key in artifact.calculation_metadata for key in _TECHNICAL_METADATA_KEYS)
    has_technical_lineage = any(key in artifact.feature_lineage for key in _TECHNICAL_FEATURE_LINEAGE_KEYS)
    if not has_technical_signal and not has_technical_metadata and not has_technical_lineage:
        return "VALID_NON_TECHNICAL"
    if has_technical_signal:
        return "VALID_TECHNICAL"
    raise RiskArtifactIndexCorruptionError(artifact.artifact_id)


def _verify_table_shape(connection: sqlite3.Connection, table_name: str, expected_columns: dict[str, dict[str, int | str]]) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = {
        row[1]: {
            "type": str(row[2]).upper(),
            "notnull": int(row[3]),
            "pk": int(row[5]),
        }
        for row in rows
    }
    if columns != expected_columns:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema columns mismatch.")


def _verify_foreign_key(connection: sqlite3.Connection) -> None:
    rows = connection.execute(f"PRAGMA foreign_key_list({TECHNICAL_RISK_ARTIFACT_INDEX_TABLE})").fetchall()
    expected = (
        RISK_ARTIFACTS_TABLE,
        "artifact_id",
        "artifact_id",
        "NO ACTION",
        "NO ACTION",
    )
    observed = tuple((row[2], row[3], row[4], row[5], row[6]) for row in rows)
    if observed != (expected,):
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema foreign key mismatch.")


def _verify_position_latest_index(connection: sqlite3.Connection) -> None:
    rows = connection.execute(f"PRAGMA index_xinfo({TECHNICAL_RISK_ARTIFACT_POSITION_LATEST_INDEX})").fetchall()
    key_columns = tuple((row[2], int(row[3]), int(row[5])) for row in rows if int(row[5]) == 1)
    expected = (
        ("portfolio_id", 0, 1),
        ("position_id", 0, 1),
        ("analysis_date", 1, 1),
        ("created_at", 1, 1),
        ("artifact_id", 1, 1),
    )
    if key_columns != expected:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema index mismatch.")


def _verify_required_checks(connection: sqlite3.Connection, *, version: int = SCHEMA_VERSION) -> None:
    table_names = [RISK_ARTIFACTS_TABLE]
    if version == SCHEMA_VERSION:
        table_names.append(TECHNICAL_RISK_ARTIFACT_INDEX_TABLE)
    for table_name in table_names:
        sql = _schema_sql(connection, table_name)
        for column_name in _expected_check_columns(table_name):
            expected = f"CHECK ({column_name} <> '')"
            if expected not in sql:
                raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema CHECK constraints mismatch.")


def _expected_check_columns(table_name: str) -> tuple[str, ...]:
    if table_name == RISK_ARTIFACTS_TABLE:
        return ("artifact_id", "artifact_checksum", "payload_json")
    if table_name == TECHNICAL_RISK_ARTIFACT_INDEX_TABLE:
        return tuple(EXPECTED_TECHNICAL_RISK_ARTIFACT_INDEX_COLUMNS)
    raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema table mismatch.")


def _schema_sql(connection: sqlite3.Connection, name: str) -> str:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE name = ?
        """,
        (name,),
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema object missing.")
    return row[0]


def _pragma_int(connection: sqlite3.Connection, name: str) -> int:
    return int(connection.execute(f"PRAGMA {name}").fetchone()[0])


def _user_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return tuple(row[0] for row in rows)
