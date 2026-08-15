from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.production_config import RiskPersistenceBackupError
from risk_persistence.production_config import RiskPersistenceProductionConfig
from risk_persistence.production_config import RiskPersistenceProductionError
from risk_persistence.sqlite_schema import APPLICATION_ID
from risk_persistence.sqlite_schema import SCHEMA_VERSION
from risk_persistence.sqlite_schema import SCHEMA_VERSION_V1
from risk_persistence.sqlite_schema import SCHEMA_VERSION_V2
from risk_persistence.sqlite_schema import SQLiteRiskArtifactSchemaInspection
from risk_persistence.sqlite_schema import SQLiteRiskArtifactSchemaState
from risk_persistence.sqlite_schema import initialize_or_verify_schema
from risk_persistence.sqlite_schema import inspect_schema_state
from risk_persistence.sqlite_schema import validate_current_schema_readonly
from risk_persistence.sqlite_schema import validate_schema_v1_readonly
from risk_persistence.sqlite_schema import validate_schema_v2_readonly
from risk_persistence.sqlite_storage import configure_sqlite_write_connection


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RiskPersistenceBootstrapStatus(StrEnum):
    """Successful production RiskArtifact persistence bootstrap outcomes."""

    CREATED = "CREATED"
    ALREADY_READY = "ALREADY_READY"
    MIGRATED = "MIGRATED"


@dataclass(frozen=True)
class RiskPersistenceBootstrapResult:
    """Structured result for production RiskArtifact persistence bootstrap."""

    status: RiskPersistenceBootstrapStatus
    schema_before: int | None
    schema_after: int
    backup_identifier: str | None = None

    def __post_init__(self) -> None:
        try:
            status = RiskPersistenceBootstrapStatus(self.status)
        except ValueError as exc:
            raise RiskPersistenceProductionError("status must be a valid bootstrap status.") from exc
        if self.schema_before is not None and not isinstance(self.schema_before, int):
            raise RiskPersistenceProductionError("schema_before must be int or None.")
        if not isinstance(self.schema_after, int):
            raise RiskPersistenceProductionError("schema_after must be an int.")
        if self.backup_identifier is not None and (
            not isinstance(self.backup_identifier, str) or not self.backup_identifier
        ):
            raise RiskPersistenceProductionError("backup_identifier must be None or non-empty string.")
        object.__setattr__(self, "status", status)


@dataclass(frozen=True)
class SQLiteRiskPersistenceBootstrapper:
    """SQLite production bootstrapper for local RiskArtifact persistence storage.

    This component owns creation of the canonical production parent directory and
    backup directory. It does not persist RiskArtifacts, run portfolio generation,
    activate policies, schedule jobs, or provide a health-check command.
    """

    config: RiskPersistenceProductionConfig
    clock: Callable[[], datetime] = _utc_now

    def __post_init__(self) -> None:
        if not isinstance(self.config, RiskPersistenceProductionConfig):
            raise RiskPersistenceProductionError("config must be RiskPersistenceProductionConfig.")
        if not callable(self.clock):
            raise RiskPersistenceProductionError("clock must be callable.")

    def bootstrap(self) -> RiskPersistenceBootstrapResult:
        production_dir = self.config.db_path.parent
        backup_dir = self.config.backup_directory
        if self.config.db_path.exists() and self.config.db_path.is_dir():
            raise RiskPersistenceProductionError("production DB path must not be a directory.")
        if backup_dir.exists() and not backup_dir.is_dir():
            raise RiskPersistenceProductionError("backup_directory must be a directory.")

        production_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir(parents=True, exist_ok=True)

        inspection = self._inspect_existing_db()
        if inspection is None or inspection.state == SQLiteRiskArtifactSchemaState.EMPTY:
            self._initialize_or_migrate()
            self._verify_current()
            return RiskPersistenceBootstrapResult(
                status=RiskPersistenceBootstrapStatus.CREATED,
                schema_before=None if inspection is None else inspection.user_version,
                schema_after=SCHEMA_VERSION,
            )

        if inspection.state == SQLiteRiskArtifactSchemaState.CURRENT:
            self._verify_current()
            return RiskPersistenceBootstrapResult(
                status=RiskPersistenceBootstrapStatus.ALREADY_READY,
                schema_before=inspection.user_version,
                schema_after=SCHEMA_VERSION,
            )

        if inspection.state in (SQLiteRiskArtifactSchemaState.V1, SQLiteRiskArtifactSchemaState.V2):
            backup_identifier = self._backup_before_migration(inspection.user_version)
            try:
                self._initialize_or_migrate()
                self._verify_current()
            except (RiskArtifactPersistenceError, sqlite3.DatabaseError) as exc:
                raise RiskPersistenceProductionError("production schema migration failed.") from exc
            return RiskPersistenceBootstrapResult(
                status=RiskPersistenceBootstrapStatus.MIGRATED,
                schema_before=inspection.user_version,
                schema_after=SCHEMA_VERSION,
                backup_identifier=backup_identifier,
            )

        raise RiskPersistenceProductionError("production DB schema is not safe to bootstrap.")

    def _inspect_existing_db(self) -> SQLiteRiskArtifactSchemaInspection | None:
        if not self.config.db_path.exists():
            return None
        connection = sqlite3.connect(_readonly_uri(self.config.db_path), uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            return inspect_schema_state(connection)
        except sqlite3.DatabaseError as exc:
            raise RiskPersistenceProductionError("production DB schema inspection failed.") from exc
        finally:
            connection.close()

    def _initialize_or_migrate(self) -> None:
        connection = sqlite3.connect(self.config.db_path)
        try:
            configure_sqlite_write_connection(connection, self.config.busy_timeout_ms)
            initialize_or_verify_schema(connection)
        except RiskArtifactPersistenceError:
            raise
        except sqlite3.DatabaseError as exc:
            raise RiskPersistenceProductionError("production DB bootstrap failed.") from exc
        finally:
            connection.close()

    def _verify_current(self) -> None:
        connection = sqlite3.connect(_readonly_uri(self.config.db_path), uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            validate_current_schema_readonly(connection)
        except RiskArtifactPersistenceError:
            raise
        except sqlite3.DatabaseError as exc:
            raise RiskPersistenceProductionError("production DB verification failed.") from exc
        finally:
            connection.close()

    def _backup_before_migration(self, source_version: int) -> str:
        return _create_verified_backup(
            source_db_path=self.config.db_path,
            backup_directory=self.config.backup_directory,
            source_version=source_version,
            timestamp=_backup_timestamp(self.clock()),
        )


def _create_verified_backup(
    *,
    source_db_path: Path,
    backup_directory: Path,
    source_version: int,
    timestamp: str,
) -> str:
    backup_identifier = f"risk_artifacts.schema-v{source_version}.{timestamp}.db"
    final_path = backup_directory / backup_identifier
    temp_path = backup_directory / f".{backup_identifier}.tmp"
    if final_path.exists():
        raise RiskPersistenceBackupError("production backup already exists.")
    if temp_path.exists():
        raise RiskPersistenceBackupError("temporary production backup already exists.")

    try:
        _sqlite_backup(source_db_path, temp_path)
        _verify_backup(temp_path, source_version)
        if final_path.exists():
            raise RiskPersistenceBackupError("production backup already exists.")
        os.link(temp_path, final_path)
        temp_path.unlink()
    except RiskPersistenceBackupError:
        _unlink_temp_backup(temp_path)
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        _unlink_temp_backup(temp_path)
        raise RiskPersistenceBackupError("production backup failed.") from exc
    return backup_identifier


def _sqlite_backup(source_db_path: Path, backup_path: Path) -> None:
    source_connection = sqlite3.connect(_readonly_uri(source_db_path), uri=True)
    backup_connection = sqlite3.connect(backup_path)
    try:
        source_connection.execute("PRAGMA query_only=ON")
        source_connection.backup(backup_connection)
        backup_connection.commit()
    finally:
        backup_connection.close()
        source_connection.close()


def _verify_backup(backup_path: Path, source_version: int) -> None:
    connection = sqlite3.connect(_readonly_uri(backup_path), uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        if _pragma_int(connection, "application_id") != APPLICATION_ID:
            raise RiskPersistenceBackupError("production backup application_id mismatch.")
        if _pragma_int(connection, "user_version") != source_version:
            raise RiskPersistenceBackupError("production backup schema version mismatch.")
        if source_version == SCHEMA_VERSION_V1:
            validate_schema_v1_readonly(connection)
        elif source_version == SCHEMA_VERSION_V2:
            validate_schema_v2_readonly(connection)
        else:
            raise RiskPersistenceBackupError("production backup source version is not migratable.")
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        if quick_check != "ok":
            raise RiskPersistenceBackupError("production backup quick_check failed.")
    except RiskPersistenceBackupError:
        raise
    except (RiskArtifactPersistenceError, sqlite3.DatabaseError) as exc:
        raise RiskPersistenceBackupError("production backup verification failed.") from exc
    finally:
        connection.close()


def _backup_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise RiskPersistenceBackupError("backup timestamp clock must return datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise RiskPersistenceBackupError("backup timestamp must be timezone-aware.")
    utc_value = value.astimezone(UTC)
    return utc_value.strftime("%Y%m%dT%H%M%S.%fZ")


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path))}?mode=ro"


def _pragma_int(connection: sqlite3.Connection, name: str) -> int:
    return int(connection.execute(f"PRAGMA {name}").fetchone()[0])


def _unlink_temp_backup(temp_path: Path) -> None:
    try:
        if temp_path.exists():
            temp_path.unlink()
    except OSError:
        pass
