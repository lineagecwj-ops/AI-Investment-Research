from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from risk import RiskArtifact
from risk import RiskArtifactCodec
from risk import RiskArtifactCodecError
from risk_persistence.contracts import RiskArtifactConflictError
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.contracts import RiskArtifactRepository
from risk_persistence.contracts import RiskArtifactSaveResult
from risk_persistence.contracts import RiskArtifactSaveStatus


_APPLICATION_ID = 0x41494952
_SCHEMA_VERSION = 1
_DEFAULT_BUSY_TIMEOUT_MS = 5000

_CREATE_RISK_ARTIFACTS_TABLE_SQL = """
CREATE TABLE risk_artifacts (
    artifact_id TEXT PRIMARY KEY CHECK (artifact_id <> ''),
    artifact_checksum TEXT NOT NULL CHECK (artifact_checksum <> ''),
    payload_json TEXT NOT NULL CHECK (payload_json <> '')
)
"""

_EXPECTED_RISK_ARTIFACT_COLUMNS = {
    "artifact_id": {"type": "TEXT", "notnull": 0, "pk": 1},
    "artifact_checksum": {"type": "TEXT", "notnull": 1, "pk": 0},
    "payload_json": {"type": "TEXT", "notnull": 1, "pk": 0},
}


@dataclass(frozen=True)
class SQLiteRiskArtifactRepository(RiskArtifactRepository):
    """SQLite implementation of the append-only RiskArtifactRepository contract."""

    db_path: str | Path
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        path = _validate_db_path(self.db_path)
        if not isinstance(self.busy_timeout_ms, int) or self.busy_timeout_ms <= 0:
            raise RiskArtifactPersistenceError("busy_timeout_ms must be a positive integer.")
        object.__setattr__(self, "db_path", path)
        self._with_connection(lambda connection: None)

    def save(self, artifact: RiskArtifact) -> RiskArtifactSaveResult:
        if not isinstance(artifact, RiskArtifact):
            raise RiskArtifactPersistenceError("SQLiteRiskArtifactRepository.save requires RiskArtifact.")
        artifact_id = artifact.artifact_id
        checksum = artifact.checksum
        if not isinstance(checksum, str) or not checksum:
            raise RiskArtifactPersistenceError("RiskArtifact requires checksum before persistence.")
        payload_json = self._encode_and_self_validate(artifact)

        def operation(connection: sqlite3.Connection) -> RiskArtifactSaveResult:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT artifact_id, artifact_checksum, payload_json
                    FROM risk_artifacts
                    WHERE artifact_id = ?
                    """,
                    (artifact_id,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO risk_artifacts (
                            artifact_id,
                            artifact_checksum,
                            payload_json
                        )
                        VALUES (?, ?, ?)
                        """,
                        (artifact_id, checksum, payload_json),
                    )
                    connection.commit()
                    return RiskArtifactSaveResult(
                        artifact_id=artifact_id,
                        checksum=checksum,
                        status=RiskArtifactSaveStatus.INSERTED,
                    )

                existing = self._decode_row(row)
                if existing.checksum == checksum:
                    connection.commit()
                    return RiskArtifactSaveResult(
                        artifact_id=artifact_id,
                        checksum=checksum,
                        status=RiskArtifactSaveStatus.IDEMPOTENT,
                    )

                connection.rollback()
                raise RiskArtifactConflictError(
                    artifact_id=artifact_id,
                    existing_checksum=existing.checksum or "",
                    incoming_checksum=checksum,
                )
            except (RiskArtifactConflictError, RiskArtifactCorruptionError):
                if connection.in_transaction:
                    connection.rollback()
                raise
            except sqlite3.DatabaseError as exc:
                if connection.in_transaction:
                    connection.rollback()
                raise RiskArtifactPersistenceError("SQLite RiskArtifact save failed.") from exc

        return self._with_connection(operation)

    def get_by_artifact_id(self, artifact_id: str) -> RiskArtifact | None:
        if not isinstance(artifact_id, str) or not artifact_id:
            raise RiskArtifactPersistenceError("artifact_id must be a non-empty string.")

        def operation(connection: sqlite3.Connection) -> RiskArtifact | None:
            try:
                row = connection.execute(
                    """
                    SELECT artifact_id, artifact_checksum, payload_json
                    FROM risk_artifacts
                    WHERE artifact_id = ?
                    """,
                    (artifact_id,),
                ).fetchone()
            except sqlite3.DatabaseError as exc:
                raise RiskArtifactPersistenceError("SQLite RiskArtifact read failed.") from exc
            if row is None:
                return None
            return self._decode_row(row)

        return self._with_connection(operation)

    def _encode_and_self_validate(self, artifact: RiskArtifact) -> str:
        try:
            payload_json = RiskArtifactCodec().encode(artifact)
            decoded = RiskArtifactCodec().decode(payload_json)
        except RiskArtifactCodecError as exc:
            raise RiskArtifactPersistenceError("RiskArtifact codec validation failed.") from exc
        if decoded != artifact:
            raise RiskArtifactPersistenceError("RiskArtifact codec round trip mismatch.")
        return payload_json

    def _with_connection(self, operation):
        try:
            connection = sqlite3.connect(self.db_path)
            try:
                self._configure_connection(connection)
                self._initialize_or_verify_schema(connection)
                return operation(connection)
            finally:
                connection.close()
        except (RiskArtifactPersistenceError, RiskArtifactConflictError, RiskArtifactCorruptionError):
            raise
        except sqlite3.DatabaseError as exc:
            raise RiskArtifactPersistenceError("SQLite RiskArtifact repository operation failed.") from exc

    def _configure_connection(self, connection: sqlite3.Connection) -> None:
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")

    def _initialize_or_verify_schema(self, connection: sqlite3.Connection) -> None:
        application_id = _pragma_int(connection, "application_id")
        user_version = _pragma_int(connection, "user_version")
        user_tables = _user_tables(connection)

        if application_id == 0 and user_version == 0 and not user_tables:
            self._initialize_schema(connection)
            return

        if application_id != _APPLICATION_ID:
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB application_id mismatch.")
        if user_version > _SCHEMA_VERSION:
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema version is unsupported.")
        if user_version != _SCHEMA_VERSION:
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema version mismatch.")
        self._verify_schema_shape(connection)
        self._ensure_wal(connection)

    def _initialize_schema(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
            connection.execute(_CREATE_RISK_ARTIFACTS_TABLE_SQL)
            connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
            self._ensure_wal(connection)
            connection.commit()
        except sqlite3.DatabaseError as exc:
            connection.rollback()
            raise RiskArtifactPersistenceError("SQLite RiskArtifact schema initialization failed.") from exc
        self._verify_schema_shape(connection)

    def _ensure_wal(self, connection: sqlite3.Connection) -> None:
        journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if str(journal_mode).lower() != "wal":
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB requires WAL journal mode.")

    def _verify_schema_shape(self, connection: sqlite3.Connection) -> None:
        tables = _user_tables(connection)
        if tables != ("risk_artifacts",):
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema tables mismatch.")
        rows = connection.execute("PRAGMA table_info(risk_artifacts)").fetchall()
        columns = {
            row[1]: {
                "type": str(row[2]).upper(),
                "notnull": int(row[3]),
                "pk": int(row[5]),
            }
            for row in rows
        }
        if columns != _EXPECTED_RISK_ARTIFACT_COLUMNS:
            raise RiskArtifactPersistenceError("SQLite RiskArtifact DB schema columns mismatch.")

    def _decode_row(self, row: sqlite3.Row | tuple) -> RiskArtifact:
        artifact_id = row[0]
        artifact_checksum = row[1]
        payload_json = row[2]
        if not isinstance(artifact_id, str) or not artifact_id:
            raise RiskArtifactCorruptionError(str(artifact_id or "unknown"))
        if not isinstance(artifact_checksum, str) or not artifact_checksum:
            raise RiskArtifactCorruptionError(artifact_id)
        if not isinstance(payload_json, str) or not payload_json:
            raise RiskArtifactCorruptionError(artifact_id)
        try:
            artifact = RiskArtifactCodec().decode(payload_json)
        except RiskArtifactCodecError as exc:
            raise RiskArtifactCorruptionError(artifact_id) from exc
        if artifact.artifact_id != artifact_id:
            raise RiskArtifactCorruptionError(artifact_id)
        if artifact.checksum != artifact_checksum:
            raise RiskArtifactCorruptionError(artifact_id)
        return artifact


def _validate_db_path(db_path: str | Path) -> Path:
    if isinstance(db_path, str) and not db_path:
        raise RiskArtifactPersistenceError("db_path must be a non-empty path.")
    try:
        path = Path(db_path)
    except TypeError as exc:
        raise RiskArtifactPersistenceError("db_path must be a path-like value.") from exc
    if str(path) == "":
        raise RiskArtifactPersistenceError("db_path must be a non-empty path.")
    if path.exists() and path.is_dir():
        raise RiskArtifactPersistenceError("db_path must not be a directory.")
    if not path.parent.exists():
        raise RiskArtifactPersistenceError("db_path parent directory must exist.")
    return path


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
