from __future__ import annotations

import sqlite3
from pathlib import Path

from risk import RiskArtifact
from risk import RiskArtifactCodec
from risk import RiskArtifactCodecError
from risk_persistence.contracts import RiskArtifactConflictError
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.contracts import RiskArtifactSaveResult
from risk_persistence.contracts import RiskArtifactSaveStatus


def validate_sqlite_db_path(db_path: str | Path) -> Path:
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


def configure_sqlite_write_connection(connection: sqlite3.Connection, busy_timeout_ms: int) -> None:
    connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    connection.execute("PRAGMA foreign_keys=ON")


def encode_and_self_validate_artifact(artifact: RiskArtifact) -> str:
    if not isinstance(artifact, RiskArtifact):
        raise RiskArtifactPersistenceError("RiskArtifact persistence requires RiskArtifact.")
    if not isinstance(artifact.checksum, str) or not artifact.checksum:
        raise RiskArtifactPersistenceError("RiskArtifact requires checksum before persistence.")
    try:
        payload_json = RiskArtifactCodec().encode(artifact)
        decoded = RiskArtifactCodec().decode(payload_json)
    except RiskArtifactCodecError as exc:
        raise RiskArtifactPersistenceError("RiskArtifact codec validation failed.") from exc
    if decoded != artifact:
        raise RiskArtifactPersistenceError("RiskArtifact codec round trip mismatch.")
    return payload_json


def load_core_artifact_row(connection: sqlite3.Connection, artifact_id: str) -> sqlite3.Row | tuple | None:
    try:
        return connection.execute(
            """
            SELECT artifact_id, artifact_checksum, payload_json
            FROM risk_artifacts
            WHERE artifact_id = ?
            """,
            (artifact_id,),
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise RiskArtifactPersistenceError("SQLite RiskArtifact read failed.") from exc


def decode_core_artifact_row(row: sqlite3.Row | tuple) -> RiskArtifact:
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


def persist_core_artifact_in_connection(
    connection: sqlite3.Connection,
    artifact: RiskArtifact,
    payload_json: str,
) -> RiskArtifactSaveResult:
    artifact_id = artifact.artifact_id
    checksum = artifact.checksum
    row = load_core_artifact_row(connection, artifact_id)
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
        return RiskArtifactSaveResult(
            artifact_id=artifact_id,
            checksum=checksum,
            status=RiskArtifactSaveStatus.INSERTED,
        )

    existing = decode_core_artifact_row(row)
    if existing.checksum == checksum:
        return RiskArtifactSaveResult(
            artifact_id=artifact_id,
            checksum=checksum,
            status=RiskArtifactSaveStatus.IDEMPOTENT,
        )

    raise RiskArtifactConflictError(
        artifact_id=artifact_id,
        existing_checksum=existing.checksum or "",
        incoming_checksum=checksum or "",
    )
