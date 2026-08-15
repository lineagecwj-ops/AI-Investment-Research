from __future__ import annotations

import sqlite3
from datetime import date
from datetime import datetime

from risk import RiskSeverity
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.technical_query_contracts import RiskArtifactIndexCorruptionError
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord


TECHNICAL_INDEX_COLUMNS = (
    "artifact_id",
    "portfolio_id",
    "position_id",
    "symbol",
    "severity",
    "analysis_date",
    "valuation_date",
    "created_at",
    "calculation_id",
    "policy_id",
    "policy_version",
    "policy_checksum",
    "evaluation_id",
    "evaluation_checksum",
    "producer_version",
)


def technical_index_select_columns(table_alias: str, *, prefix: str = "idx_") -> str:
    return ",\n".join(f"{table_alias}.{column} AS {prefix}{column}" for column in TECHNICAL_INDEX_COLUMNS)


def technical_index_record_values(record: TechnicalRiskArtifactIndexRecord) -> tuple[object, ...]:
    return (
        record.artifact_id,
        record.portfolio_id,
        record.position_id,
        record.symbol,
        record.severity.value,
        record.analysis_date.isoformat(),
        record.valuation_date.isoformat(),
        record.created_at.isoformat(),
        record.calculation_id,
        record.policy_id,
        record.policy_version,
        record.policy_checksum,
        record.evaluation_id,
        record.evaluation_checksum,
        record.producer_version,
    )


def insert_technical_index_record(
    connection: sqlite3.Connection,
    record: TechnicalRiskArtifactIndexRecord,
) -> None:
    connection.execute(
        """
        INSERT INTO technical_risk_artifact_index (
            artifact_id,
            portfolio_id,
            position_id,
            symbol,
            severity,
            analysis_date,
            valuation_date,
            created_at,
            calculation_id,
            policy_id,
            policy_version,
            policy_checksum,
            evaluation_id,
            evaluation_checksum,
            producer_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        technical_index_record_values(record),
    )


def load_technical_index_record(
    connection: sqlite3.Connection,
    artifact_id: str,
) -> TechnicalRiskArtifactIndexRecord | None:
    try:
        row = connection.execute(
            f"""
            SELECT
                {technical_index_select_columns("idx")}
            FROM technical_risk_artifact_index idx
            WHERE idx.artifact_id = ?
            """,
            (artifact_id,),
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise RiskArtifactPersistenceError("SQLite Technical Risk artifact index read failed.") from exc
    if row is None:
        return None
    return technical_index_record_from_row(row)


def technical_index_record_from_row(
    row: sqlite3.Row | dict[str, object],
    *,
    prefix: str = "idx_",
) -> TechnicalRiskArtifactIndexRecord:
    artifact_id = _optional_artifact_id(row, prefix)
    try:
        created_at = datetime.fromisoformat(_require_text(row[f"{prefix}created_at"], "created_at"))
        record = TechnicalRiskArtifactIndexRecord(
            artifact_id=_require_text(row[f"{prefix}artifact_id"], "artifact_id"),
            portfolio_id=_require_text(row[f"{prefix}portfolio_id"], "portfolio_id"),
            position_id=_require_text(row[f"{prefix}position_id"], "position_id"),
            symbol=_require_text(row[f"{prefix}symbol"], "symbol"),
            severity=RiskSeverity(_require_text(row[f"{prefix}severity"], "severity")),
            analysis_date=date.fromisoformat(_require_text(row[f"{prefix}analysis_date"], "analysis_date")),
            valuation_date=date.fromisoformat(_require_text(row[f"{prefix}valuation_date"], "valuation_date")),
            created_at=created_at,
            calculation_id=_require_text(row[f"{prefix}calculation_id"], "calculation_id"),
            policy_id=_require_text(row[f"{prefix}policy_id"], "policy_id"),
            policy_version=_require_text(row[f"{prefix}policy_version"], "policy_version"),
            policy_checksum=_require_text(row[f"{prefix}policy_checksum"], "policy_checksum"),
            evaluation_id=_require_text(row[f"{prefix}evaluation_id"], "evaluation_id"),
            evaluation_checksum=_require_text(row[f"{prefix}evaluation_checksum"], "evaluation_checksum"),
            producer_version=_require_text(row[f"{prefix}producer_version"], "producer_version"),
        )
    except (RiskArtifactPersistenceError, ValueError, TypeError) as exc:
        raise RiskArtifactIndexCorruptionError(artifact_id) from exc
    return record


def _optional_artifact_id(row: sqlite3.Row | dict[str, object], prefix: str) -> str:
    try:
        value = row[f"{prefix}artifact_id"]
    except (KeyError, IndexError):
        return "unknown"
    return value if isinstance(value, str) and value else "unknown"


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RiskArtifactPersistenceError(f"{field_name} must be a non-empty string.")
    return value
