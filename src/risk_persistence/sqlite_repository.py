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
from risk_persistence.sqlite_schema import initialize_or_verify_schema
from risk_persistence.sqlite_storage import configure_sqlite_write_connection
from risk_persistence.sqlite_storage import decode_core_artifact_row
from risk_persistence.sqlite_storage import encode_and_self_validate_artifact
from risk_persistence.sqlite_storage import load_core_artifact_row
from risk_persistence.sqlite_storage import persist_core_artifact_in_connection
from risk_persistence.sqlite_storage import validate_sqlite_db_path


_DEFAULT_BUSY_TIMEOUT_MS = 5000


@dataclass(frozen=True)
class SQLiteRiskArtifactRepository(RiskArtifactRepository):
    """SQLite implementation of the append-only RiskArtifactRepository contract."""

    db_path: str | Path
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        path = validate_sqlite_db_path(self.db_path)
        if not isinstance(self.busy_timeout_ms, int) or self.busy_timeout_ms <= 0:
            raise RiskArtifactPersistenceError("busy_timeout_ms must be a positive integer.")
        object.__setattr__(self, "db_path", path)
        self._with_connection(lambda connection: None)

    def save(self, artifact: RiskArtifact) -> RiskArtifactSaveResult:
        if not isinstance(artifact, RiskArtifact):
            raise RiskArtifactPersistenceError("SQLiteRiskArtifactRepository.save requires RiskArtifact.")
        payload_json = encode_and_self_validate_artifact(artifact)

        def operation(connection: sqlite3.Connection) -> RiskArtifactSaveResult:
            try:
                connection.execute("BEGIN IMMEDIATE")
                result = persist_core_artifact_in_connection(connection, artifact, payload_json)
                connection.commit()
                return result
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
            row = load_core_artifact_row(connection, artifact_id)
            if row is None:
                return None
            return decode_core_artifact_row(row)

        return self._with_connection(operation)

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
        configure_sqlite_write_connection(connection, self.busy_timeout_ms)

    def _initialize_or_verify_schema(self, connection: sqlite3.Connection) -> None:
        initialize_or_verify_schema(connection)
