from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.portfolio_run_codec import PortfolioRiskGenerationRunRecordCodec
from risk_persistence.portfolio_run_codec import PortfolioRiskGenerationRunRecordCodecError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunConflictError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunCorruptionError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunPersistenceError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunRecord
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunRepository
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunSaveResult
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunSaveStatus
from risk_persistence.sqlite_schema import PORTFOLIO_RISK_GENERATION_RUNS_TABLE
from risk_persistence.sqlite_schema import initialize_or_verify_schema
from risk_persistence.sqlite_storage import configure_sqlite_write_connection
from risk_persistence.sqlite_storage import validate_sqlite_db_path


_DEFAULT_BUSY_TIMEOUT_MS = 5000


@dataclass(frozen=True)
class SQLitePortfolioRiskGenerationRunRepository(PortfolioRiskGenerationRunRepository):
    """SQLite implementation of the append-only portfolio generation run repository."""

    db_path: str | Path
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        try:
            path = validate_sqlite_db_path(self.db_path)
        except RiskArtifactPersistenceError as exc:
            raise PortfolioRiskGenerationRunPersistenceError(str(exc)) from exc
        if not isinstance(self.busy_timeout_ms, int) or self.busy_timeout_ms <= 0:
            raise PortfolioRiskGenerationRunPersistenceError("busy_timeout_ms must be a positive integer.")
        object.__setattr__(self, "db_path", path)
        self._with_connection(lambda connection: None)

    def save(self, record: PortfolioRiskGenerationRunRecord) -> PortfolioRiskGenerationRunSaveResult:
        if not isinstance(record, PortfolioRiskGenerationRunRecord):
            raise PortfolioRiskGenerationRunPersistenceError(
                "SQLitePortfolioRiskGenerationRunRepository.save requires PortfolioRiskGenerationRunRecord."
            )
        payload_json = _encode_and_self_validate_run_record(record)

        def operation(connection: sqlite3.Connection) -> PortfolioRiskGenerationRunSaveResult:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = _load_run_record_row(connection, record.calculation_id)
                if row is None:
                    connection.execute(
                        f"""
                        INSERT INTO {PORTFOLIO_RISK_GENERATION_RUNS_TABLE} (
                            calculation_id,
                            record_checksum,
                            payload_json
                        )
                        VALUES (?, ?, ?)
                        """,
                        (record.calculation_id, record.record_checksum, payload_json),
                    )
                    connection.commit()
                    return PortfolioRiskGenerationRunSaveResult(
                        calculation_id=record.calculation_id,
                        record_checksum=record.record_checksum or "",
                        status=PortfolioRiskGenerationRunSaveStatus.INSERTED,
                    )

                existing = _decode_run_record_row(row)
                if existing.record_checksum == record.record_checksum:
                    connection.commit()
                    return PortfolioRiskGenerationRunSaveResult(
                        calculation_id=record.calculation_id,
                        record_checksum=record.record_checksum or "",
                        status=PortfolioRiskGenerationRunSaveStatus.IDEMPOTENT,
                    )
                raise PortfolioRiskGenerationRunConflictError(
                    calculation_id=record.calculation_id,
                    existing_checksum=existing.record_checksum or "",
                    incoming_checksum=record.record_checksum or "",
                )
            except (
                PortfolioRiskGenerationRunConflictError,
                PortfolioRiskGenerationRunCorruptionError,
                PortfolioRiskGenerationRunPersistenceError,
            ):
                if connection.in_transaction:
                    connection.rollback()
                raise
            except sqlite3.DatabaseError as exc:
                if connection.in_transaction:
                    connection.rollback()
                raise PortfolioRiskGenerationRunPersistenceError(
                    "SQLite portfolio generation run save failed."
                ) from exc

        return self._with_connection(operation)

    def get_by_calculation_id(self, calculation_id: str) -> PortfolioRiskGenerationRunRecord | None:
        if not isinstance(calculation_id, str) or not calculation_id:
            raise PortfolioRiskGenerationRunPersistenceError("calculation_id must be a non-empty string.")

        def operation(connection: sqlite3.Connection) -> PortfolioRiskGenerationRunRecord | None:
            row = _load_run_record_row(connection, calculation_id)
            if row is None:
                return None
            return _decode_run_record_row(row)

        return self._with_connection(operation)

    def _with_connection(self, operation):
        try:
            connection = sqlite3.connect(self.db_path)
            try:
                configure_sqlite_write_connection(connection, self.busy_timeout_ms)
                initialize_or_verify_schema(connection)
                return operation(connection)
            finally:
                connection.close()
        except (
            PortfolioRiskGenerationRunConflictError,
            PortfolioRiskGenerationRunCorruptionError,
            PortfolioRiskGenerationRunPersistenceError,
        ):
            raise
        except RiskArtifactPersistenceError as exc:
            raise PortfolioRiskGenerationRunPersistenceError(str(exc)) from exc
        except sqlite3.DatabaseError as exc:
            raise PortfolioRiskGenerationRunPersistenceError(
                "SQLite portfolio generation run repository operation failed."
            ) from exc


def _encode_and_self_validate_run_record(record: PortfolioRiskGenerationRunRecord) -> str:
    try:
        payload_json = PortfolioRiskGenerationRunRecordCodec().encode(record)
        decoded = PortfolioRiskGenerationRunRecordCodec().decode(payload_json)
    except PortfolioRiskGenerationRunRecordCodecError as exc:
        raise PortfolioRiskGenerationRunPersistenceError("Run record codec validation failed.") from exc
    if decoded != record:
        raise PortfolioRiskGenerationRunPersistenceError("Run record codec round trip mismatch.")
    return payload_json


def _load_run_record_row(
    connection: sqlite3.Connection,
    calculation_id: str,
) -> sqlite3.Row | tuple | None:
    try:
        return connection.execute(
            f"""
            SELECT calculation_id, record_checksum, payload_json
            FROM {PORTFOLIO_RISK_GENERATION_RUNS_TABLE}
            WHERE calculation_id = ?
            """,
            (calculation_id,),
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise PortfolioRiskGenerationRunPersistenceError("SQLite portfolio generation run read failed.") from exc


def _decode_run_record_row(row: sqlite3.Row | tuple) -> PortfolioRiskGenerationRunRecord:
    calculation_id = row[0]
    record_checksum = row[1]
    payload_json = row[2]
    if not isinstance(calculation_id, str) or not calculation_id:
        raise PortfolioRiskGenerationRunCorruptionError(str(calculation_id or "unknown"))
    if not isinstance(record_checksum, str) or not record_checksum:
        raise PortfolioRiskGenerationRunCorruptionError(calculation_id)
    if not isinstance(payload_json, str) or not payload_json:
        raise PortfolioRiskGenerationRunCorruptionError(calculation_id)
    try:
        record = PortfolioRiskGenerationRunRecordCodec().decode(payload_json)
    except PortfolioRiskGenerationRunRecordCodecError as exc:
        raise PortfolioRiskGenerationRunCorruptionError(calculation_id) from exc
    if record.calculation_id != calculation_id:
        raise PortfolioRiskGenerationRunCorruptionError(calculation_id)
    if record.record_checksum != record_checksum:
        raise PortfolioRiskGenerationRunCorruptionError(calculation_id)
    return record
