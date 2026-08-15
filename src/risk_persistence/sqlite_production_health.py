from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.production_config import RiskPersistenceProductionConfig
from risk_persistence.production_config import RiskPersistenceProductionError
from risk_persistence.sqlite_schema import SCHEMA_VERSION
from risk_persistence.sqlite_schema import SQLiteRiskArtifactSchemaInspection
from risk_persistence.sqlite_schema import SQLiteRiskArtifactSchemaState
from risk_persistence.sqlite_schema import inspect_schema_state
from risk_persistence.sqlite_schema import validate_current_schema_readonly


_DB_PATH_ALIAS = "data/production/risk_artifacts.db"
_CHECK_PATH = "path"
_CHECK_SCHEMA = "schema"
_CHECK_QUICK_CHECK = "quick_check"


class RiskPersistenceHealthStatus(StrEnum):
    """Read-only production persistence health classifications."""

    READY = "READY"
    MISSING = "MISSING"
    MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
    INVALID = "INVALID"
    UNHEALTHY = "UNHEALTHY"


@dataclass(frozen=True)
class RiskPersistenceHealthResult:
    """Sanitized read-only health result for production RiskArtifact storage."""

    status: RiskPersistenceHealthStatus
    schema_version: int | None
    db_path_alias: str
    quick_check_result: str | None
    checks: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            status = RiskPersistenceHealthStatus(self.status)
        except ValueError as exc:
            raise RiskPersistenceProductionError("status must be a valid health status.") from exc
        if self.schema_version is not None and (
            isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int)
        ):
            raise RiskPersistenceProductionError("schema_version must be int or None.")
        if not isinstance(self.db_path_alias, str) or not self.db_path_alias:
            raise RiskPersistenceProductionError("db_path_alias must be a non-empty string.")
        if self.quick_check_result is not None and (
            not isinstance(self.quick_check_result, str) or not self.quick_check_result
        ):
            raise RiskPersistenceProductionError("quick_check_result must be None or non-empty string.")
        if not isinstance(self.checks, tuple) or not all(isinstance(item, str) and item for item in self.checks):
            raise RiskPersistenceProductionError("checks must be a tuple of non-empty strings.")
        if not isinstance(self.warnings, tuple) or not all(
            isinstance(item, str) and item for item in self.warnings
        ):
            raise RiskPersistenceProductionError("warnings must be a tuple of non-empty strings.")
        object.__setattr__(self, "status", status)


@dataclass(frozen=True)
class SQLiteRiskPersistenceHealthChecker:
    """Read-only health checker for canonical production RiskArtifact storage."""

    config: RiskPersistenceProductionConfig

    def __post_init__(self) -> None:
        if not isinstance(self.config, RiskPersistenceProductionConfig):
            raise RiskPersistenceProductionError("config must be RiskPersistenceProductionConfig.")

    def check(self) -> RiskPersistenceHealthResult:
        db_path = self.config.db_path
        if not db_path.parent.exists():
            return _result(RiskPersistenceHealthStatus.MISSING, None, checks=(_CHECK_PATH,))
        if not db_path.exists():
            return _result(RiskPersistenceHealthStatus.MISSING, None, checks=(_CHECK_PATH,))
        if db_path.is_dir():
            return _result(RiskPersistenceHealthStatus.INVALID, None, checks=(_CHECK_PATH,))
        try:
            if db_path.stat().st_size == 0:
                return _result(RiskPersistenceHealthStatus.MISSING, 0, checks=(_CHECK_PATH, _CHECK_SCHEMA))
        except OSError:
            return _result(RiskPersistenceHealthStatus.UNHEALTHY, None, checks=(_CHECK_PATH,))

        try:
            connection = sqlite3.connect(_readonly_uri(db_path), uri=True)
        except sqlite3.DatabaseError:
            return _result(RiskPersistenceHealthStatus.UNHEALTHY, None, checks=(_CHECK_PATH,))
        try:
            try:
                _configure_readonly_connection(connection, self.config.busy_timeout_ms)
                inspection = inspect_schema_state(connection)
                mapped = _map_inspection(inspection)
                if mapped != RiskPersistenceHealthStatus.READY:
                    return _result(mapped, inspection.user_version, checks=(_CHECK_PATH, _CHECK_SCHEMA))

                validate_current_schema_readonly(connection)
                quick_check_result = _run_quick_check(connection)
                if quick_check_result != "ok":
                    return _result(
                        RiskPersistenceHealthStatus.UNHEALTHY,
                        SCHEMA_VERSION,
                        quick_check_result=quick_check_result,
                        checks=(_CHECK_PATH, _CHECK_SCHEMA, _CHECK_QUICK_CHECK),
                    )
                return _result(
                    RiskPersistenceHealthStatus.READY,
                    SCHEMA_VERSION,
                    quick_check_result=quick_check_result,
                    checks=(_CHECK_PATH, _CHECK_SCHEMA, _CHECK_QUICK_CHECK),
                    warnings=_warnings_for_ready(self.config),
                )
            except (RiskArtifactPersistenceError, sqlite3.DatabaseError, OSError):
                return _result(
                    RiskPersistenceHealthStatus.UNHEALTHY,
                    None,
                    checks=(_CHECK_PATH, _CHECK_SCHEMA),
                )
        finally:
            connection.close()


def _map_inspection(inspection: SQLiteRiskArtifactSchemaInspection) -> RiskPersistenceHealthStatus:
    if inspection.state == SQLiteRiskArtifactSchemaState.EMPTY:
        return RiskPersistenceHealthStatus.MISSING
    if inspection.state in (SQLiteRiskArtifactSchemaState.V1, SQLiteRiskArtifactSchemaState.V2):
        return RiskPersistenceHealthStatus.MIGRATION_REQUIRED
    if inspection.state == SQLiteRiskArtifactSchemaState.CURRENT:
        return RiskPersistenceHealthStatus.READY
    if inspection.state in (
        SQLiteRiskArtifactSchemaState.WRONG_APPLICATION,
        SQLiteRiskArtifactSchemaState.FUTURE,
        SQLiteRiskArtifactSchemaState.MALFORMED,
    ):
        return RiskPersistenceHealthStatus.INVALID
    return RiskPersistenceHealthStatus.INVALID


def _configure_readonly_connection(connection: sqlite3.Connection, busy_timeout_ms: int) -> None:
    connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA query_only=ON")


def _run_quick_check(connection: sqlite3.Connection) -> str:
    row = connection.execute("PRAGMA quick_check").fetchone()
    if row is None or not isinstance(row[0], str):
        return "failed"
    return row[0]


def _warnings_for_ready(config: RiskPersistenceProductionConfig) -> tuple[str, ...]:
    backup_directory = config.backup_directory
    if not backup_directory.exists():
        return ("backup_directory_missing",)
    if not backup_directory.is_dir():
        return ("backup_directory_not_directory",)
    return ()


def _result(
    status: RiskPersistenceHealthStatus,
    schema_version: int | None,
    *,
    quick_check_result: str | None = None,
    checks: tuple[str, ...],
    warnings: tuple[str, ...] = (),
) -> RiskPersistenceHealthResult:
    return RiskPersistenceHealthResult(
        status=status,
        schema_version=schema_version,
        db_path_alias=_DB_PATH_ALIAS,
        quick_check_result=quick_check_result,
        checks=checks,
        warnings=warnings,
    )


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path))}?mode=ro"
