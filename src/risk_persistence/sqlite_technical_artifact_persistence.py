from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from risk import RiskArtifact
from risk_persistence.contracts import RiskArtifactConflictError
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.contracts import RiskArtifactSaveResult
from risk_persistence.contracts import RiskArtifactSaveStatus
from risk_persistence.sqlite_schema import initialize_or_verify_schema
from risk_persistence.sqlite_storage import configure_sqlite_write_connection
from risk_persistence.sqlite_storage import encode_and_self_validate_artifact
from risk_persistence.sqlite_storage import load_core_artifact_row
from risk_persistence.sqlite_storage import persist_core_artifact_in_connection
from risk_persistence.sqlite_storage import validate_sqlite_db_path
from risk_persistence.sqlite_technical_index import insert_technical_index_record
from risk_persistence.sqlite_technical_index import load_technical_index_record
from risk_persistence.technical_query_contracts import RiskArtifactIndexCorruptionError
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord


_DEFAULT_BUSY_TIMEOUT_MS = 5000


@dataclass(frozen=True)
class SQLiteTechnicalRiskArtifactPersistenceCoordinator:
    """SQLite write coordinator for atomic Technical Risk artifact + index persistence."""

    db_path: str | Path
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        path = validate_sqlite_db_path(self.db_path)
        if not isinstance(self.busy_timeout_ms, int) or self.busy_timeout_ms <= 0:
            raise RiskArtifactPersistenceError("busy_timeout_ms must be a positive integer.")
        object.__setattr__(self, "db_path", path)
        self._with_connection(lambda connection: None)

    def save(self, artifact: RiskArtifact) -> RiskArtifactSaveResult:
        def operation(connection: sqlite3.Connection) -> RiskArtifactSaveResult:
            try:
                connection.execute("BEGIN IMMEDIATE")
                result = persist_technical_artifact_in_connection(connection, artifact)
                connection.commit()
                return result
            except (
                RiskArtifactConflictError,
                RiskArtifactCorruptionError,
                RiskArtifactIndexCorruptionError,
                RiskArtifactPersistenceError,
            ):
                if connection.in_transaction:
                    connection.rollback()
                raise
            except sqlite3.DatabaseError as exc:
                if connection.in_transaction:
                    connection.rollback()
                raise RiskArtifactPersistenceError("SQLite Technical Risk artifact persistence failed.") from exc

        return self._with_connection(operation)

    def _with_connection(self, operation):
        try:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            try:
                configure_sqlite_write_connection(connection, self.busy_timeout_ms)
                initialize_or_verify_schema(connection)
                return operation(connection)
            finally:
                connection.close()
        except (
            RiskArtifactConflictError,
            RiskArtifactCorruptionError,
            RiskArtifactIndexCorruptionError,
            RiskArtifactPersistenceError,
        ):
            raise
        except sqlite3.DatabaseError as exc:
            raise RiskArtifactPersistenceError("SQLite Technical Risk artifact persistence failed.") from exc


def persist_technical_artifact_in_connection(
    connection: sqlite3.Connection,
    artifact: RiskArtifact,
) -> RiskArtifactSaveResult:
    expected_record = TechnicalRiskArtifactIndexRecord.from_artifact(artifact)
    payload_json = encode_and_self_validate_artifact(artifact)
    core_row = load_core_artifact_row(connection, artifact.artifact_id)
    stored_record = load_technical_index_record(connection, artifact.artifact_id)
    if core_row is None and stored_record is not None:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)

    result = persist_core_artifact_in_connection(connection, artifact, payload_json)

    if stored_record is None:
        insert_technical_index_record(connection, expected_record)
        return result

    if stored_record != expected_record:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)

    return RiskArtifactSaveResult(
        artifact_id=artifact.artifact_id,
        checksum=artifact.checksum or "",
        status=RiskArtifactSaveStatus.IDEMPOTENT,
    )
