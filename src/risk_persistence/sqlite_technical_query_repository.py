from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from risk import RiskArtifact
from risk import RiskArtifactCodec
from risk import RiskArtifactCodecError
from risk import RiskSeverity
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.sqlite_schema import validate_current_schema_readonly
from risk_persistence.sqlite_technical_index import technical_index_record_from_row
from risk_persistence.sqlite_technical_index import technical_index_select_columns
from risk_persistence.technical_query_contracts import RiskArtifactIndexCorruptionError
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactQueryRepository


_DEFAULT_BUSY_TIMEOUT_MS = 5000

_INDEX_COLUMNS = technical_index_select_columns("idx")

_CORE_COLUMNS = """
core.artifact_id AS core_artifact_id,
core.artifact_checksum AS core_artifact_checksum,
core.payload_json AS core_payload_json
"""


@dataclass(frozen=True)
class SQLiteTechnicalRiskArtifactQueryRepository(TechnicalRiskArtifactQueryRepository):
    """Read-only SQLite implementation of the Technical Risk artifact query contract."""

    db_path: str | Path
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        path = _validate_existing_db_path(self.db_path)
        if not isinstance(self.busy_timeout_ms, int) or self.busy_timeout_ms <= 0:
            raise RiskArtifactPersistenceError("busy_timeout_ms must be a positive integer.")
        object.__setattr__(self, "db_path", path)
        self._with_connection(lambda connection: None)

    def get_latest_by_position(
        self,
        portfolio_id: str,
        position_id: str,
    ) -> RiskArtifact | None:
        _require_text(portfolio_id, "portfolio_id")
        _require_text(position_id, "position_id")

        def operation(connection: sqlite3.Connection) -> RiskArtifact | None:
            row = connection.execute(
                f"""
                SELECT
                    {_INDEX_COLUMNS},
                    {_CORE_COLUMNS}
                FROM technical_risk_artifact_index idx
                LEFT JOIN risk_artifacts core
                  ON core.artifact_id = idx.artifact_id
                WHERE idx.portfolio_id = ?
                  AND idx.position_id = ?
                ORDER BY
                    idx.analysis_date DESC,
                    idx.created_at DESC,
                    idx.artifact_id DESC
                LIMIT 1
                """,
                (portfolio_id, position_id),
            ).fetchone()
            if row is None:
                return None
            return self._materialize_row(row)

        return self._with_connection(operation)

    def list_history_by_position(
        self,
        portfolio_id: str,
        position_id: str,
        *,
        limit: int | None = None,
    ) -> tuple[RiskArtifact, ...]:
        _require_text(portfolio_id, "portfolio_id")
        _require_text(position_id, "position_id")
        _validate_limit(limit)
        limit_clause = ""
        parameters: tuple[object, ...] = (portfolio_id, position_id)
        if limit is not None:
            limit_clause = "LIMIT ?"
            parameters = (portfolio_id, position_id, limit)

        def operation(connection: sqlite3.Connection) -> tuple[RiskArtifact, ...]:
            rows = connection.execute(
                f"""
                SELECT
                    {_INDEX_COLUMNS},
                    {_CORE_COLUMNS}
                FROM technical_risk_artifact_index idx
                LEFT JOIN risk_artifacts core
                  ON core.artifact_id = idx.artifact_id
                WHERE idx.portfolio_id = ?
                  AND idx.position_id = ?
                ORDER BY
                    idx.analysis_date DESC,
                    idx.created_at DESC,
                    idx.artifact_id DESC
                {limit_clause}
                """,
                parameters,
            ).fetchall()
            return tuple(self._materialize_row(row) for row in rows)

        return self._with_connection(operation)

    def list_latest_by_portfolio(
        self,
        portfolio_id: str,
        *,
        severity: RiskSeverity | None = None,
    ) -> tuple[RiskArtifact, ...]:
        _require_text(portfolio_id, "portfolio_id")
        if severity is not None and not isinstance(severity, RiskSeverity):
            raise RiskArtifactPersistenceError("severity must be RiskSeverity or None.")
        severity_clause = ""
        parameters: tuple[object, ...] = (portfolio_id,)
        if severity is not None:
            severity_clause = "AND ranked.idx_severity = ?"
            parameters = (portfolio_id, severity.value)

        def operation(connection: sqlite3.Connection) -> tuple[RiskArtifact, ...]:
            rows = connection.execute(
                f"""
                WITH ranked AS (
                    SELECT
                        {_INDEX_COLUMNS},
                        ROW_NUMBER() OVER (
                            PARTITION BY idx.portfolio_id, idx.position_id
                            ORDER BY
                                idx.analysis_date DESC,
                                idx.created_at DESC,
                                idx.artifact_id DESC
                        ) AS rn
                    FROM technical_risk_artifact_index idx
                    WHERE idx.portfolio_id = ?
                )
                SELECT
                    ranked.idx_artifact_id,
                    ranked.idx_portfolio_id,
                    ranked.idx_position_id,
                    ranked.idx_symbol,
                    ranked.idx_severity,
                    ranked.idx_analysis_date,
                    ranked.idx_valuation_date,
                    ranked.idx_created_at,
                    ranked.idx_calculation_id,
                    ranked.idx_policy_id,
                    ranked.idx_policy_version,
                    ranked.idx_policy_checksum,
                    ranked.idx_evaluation_id,
                    ranked.idx_evaluation_checksum,
                    ranked.idx_producer_version,
                    {_CORE_COLUMNS}
                FROM ranked
                LEFT JOIN risk_artifacts core
                  ON core.artifact_id = ranked.idx_artifact_id
                WHERE ranked.rn = 1
                {severity_clause}
                ORDER BY
                    ranked.idx_position_id ASC,
                    ranked.idx_symbol ASC,
                    ranked.idx_artifact_id ASC
                """,
                parameters,
            ).fetchall()
            return tuple(self._materialize_row(row) for row in rows)

        return self._with_connection(operation)

    def _with_connection(self, operation):
        try:
            connection = sqlite3.connect(_readonly_uri(self.db_path), uri=True)
            connection.row_factory = sqlite3.Row
            try:
                self._configure_connection(connection)
                validate_current_schema_readonly(connection)
                try:
                    connection.execute("BEGIN")
                    result = operation(connection)
                    connection.commit()
                    return result
                except (
                    RiskArtifactPersistenceError,
                    RiskArtifactCorruptionError,
                    RiskArtifactIndexCorruptionError,
                ):
                    if connection.in_transaction:
                        connection.rollback()
                    raise
                except sqlite3.DatabaseError as exc:
                    if connection.in_transaction:
                        connection.rollback()
                    raise RiskArtifactPersistenceError("SQLite Technical Risk artifact query failed.") from exc
            finally:
                connection.close()
        except (
            RiskArtifactPersistenceError,
            RiskArtifactCorruptionError,
            RiskArtifactIndexCorruptionError,
        ):
            raise
        except sqlite3.DatabaseError as exc:
            raise RiskArtifactPersistenceError("SQLite Technical Risk artifact query failed.") from exc

    def _configure_connection(self, connection: sqlite3.Connection) -> None:
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA query_only=ON")

    def _materialize_row(self, row: sqlite3.Row) -> RiskArtifact:
        stored_record = technical_index_record_from_row(row)
        core_artifact_id = row["core_artifact_id"]
        core_checksum = row["core_artifact_checksum"]
        payload_json = row["core_payload_json"]
        if core_artifact_id is None or core_checksum is None or payload_json is None:
            raise RiskArtifactIndexCorruptionError(stored_record.artifact_id)
        if not isinstance(core_artifact_id, str) or not core_artifact_id:
            raise RiskArtifactCorruptionError(stored_record.artifact_id)
        if not isinstance(core_checksum, str) or not core_checksum:
            raise RiskArtifactCorruptionError(core_artifact_id)
        if not isinstance(payload_json, str) or not payload_json:
            raise RiskArtifactCorruptionError(core_artifact_id)
        try:
            artifact = RiskArtifactCodec().decode(payload_json)
        except RiskArtifactCodecError as exc:
            raise RiskArtifactCorruptionError(core_artifact_id) from exc
        if artifact.artifact_id != core_artifact_id:
            raise RiskArtifactCorruptionError(core_artifact_id)
        if artifact.checksum != core_checksum:
            raise RiskArtifactCorruptionError(core_artifact_id)
        try:
            rebuilt_record = TechnicalRiskArtifactIndexRecord.from_artifact(artifact)
        except RiskArtifactIndexCorruptionError:
            raise
        except RiskArtifactPersistenceError as exc:
            raise RiskArtifactIndexCorruptionError(stored_record.artifact_id) from exc
        if stored_record != rebuilt_record:
            raise RiskArtifactIndexCorruptionError(stored_record.artifact_id)
        return artifact


def _validate_existing_db_path(db_path: str | Path) -> Path:
    if isinstance(db_path, str) and not db_path:
        raise RiskArtifactPersistenceError("db_path must be a non-empty path.")
    try:
        path = Path(db_path)
    except TypeError as exc:
        raise RiskArtifactPersistenceError("db_path must be a path-like value.") from exc
    if str(path) == "":
        raise RiskArtifactPersistenceError("db_path must be a non-empty path.")
    if not path.exists():
        raise RiskArtifactPersistenceError("db_path must exist for read-only queries.")
    if path.is_dir():
        raise RiskArtifactPersistenceError("db_path must not be a directory.")
    if not path.parent.exists():
        raise RiskArtifactPersistenceError("db_path parent directory must exist.")
    if path.stat().st_size == 0:
        raise RiskArtifactPersistenceError("db_path must be an initialized SQLite RiskArtifact DB.")
    return path


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path))}?mode=ro"


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RiskArtifactPersistenceError(f"{field_name} must be a non-empty string.")
    return value


def _validate_limit(limit: int | None) -> None:
    if limit is None:
        return
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise RiskArtifactPersistenceError("limit must be None or a positive integer.")
