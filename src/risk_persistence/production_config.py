from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


_DEFAULT_BUSY_TIMEOUT_MS = 5000


class RiskPersistenceProductionError(ValueError):
    """Base error for production RiskArtifact persistence setup failures."""


class RiskPersistenceConfigurationError(RiskPersistenceProductionError):
    """Raised when production persistence configuration is invalid."""


class RiskPersistenceBackupError(RiskPersistenceProductionError):
    """Raised when a mandatory production persistence backup cannot be trusted."""


class RiskPersistenceEnvironment(StrEnum):
    """Supported production persistence environment."""

    PRODUCTION = "PRODUCTION"


@dataclass(frozen=True)
class RiskPersistenceProductionConfig:
    """Immutable local-filesystem production RiskArtifact persistence config.

    Production v1 supports only a local filesystem SQLite deployment. The
    canonical DB and backup paths are derived from an explicit project root so
    callers cannot redirect production bootstrap to an arbitrary DB path.
    """

    project_root: Path
    environment: RiskPersistenceEnvironment
    db_path: Path
    backup_directory: Path
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        root = _resolve_existing_project_root(self.project_root)
        environment = _require_production_environment(self.environment)
        _validate_busy_timeout(self.busy_timeout_ms)
        expected_db_path = root / "data" / "production" / "risk_artifacts.db"
        expected_backup_directory = root / "data" / "production" / "backups"
        db_path = _resolve_path(self.db_path)
        backup_directory = _resolve_path(self.backup_directory)
        if db_path != expected_db_path:
            raise RiskPersistenceConfigurationError("db_path must be derived from project_root.")
        if backup_directory != expected_backup_directory:
            raise RiskPersistenceConfigurationError("backup_directory must be derived from project_root.")
        object.__setattr__(self, "project_root", root)
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "db_path", db_path)
        object.__setattr__(self, "backup_directory", backup_directory)

    @classmethod
    def from_project_root(
        cls,
        project_root: str | Path,
        *,
        busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
    ) -> "RiskPersistenceProductionConfig":
        root = _resolve_existing_project_root(project_root)
        return cls(
            project_root=root,
            environment=RiskPersistenceEnvironment.PRODUCTION,
            db_path=root / "data" / "production" / "risk_artifacts.db",
            backup_directory=root / "data" / "production" / "backups",
            busy_timeout_ms=busy_timeout_ms,
        )


def _resolve_existing_project_root(project_root: str | Path) -> Path:
    if isinstance(project_root, str) and not project_root:
        raise RiskPersistenceConfigurationError("project_root must be a non-empty path.")
    try:
        root = Path(project_root).expanduser().resolve()
    except (RuntimeError, TypeError, OSError) as exc:
        raise RiskPersistenceConfigurationError("project_root must be a path-like value.") from exc
    if not root.exists():
        raise RiskPersistenceConfigurationError("project_root must exist.")
    if not root.is_dir():
        raise RiskPersistenceConfigurationError("project_root must be a directory.")
    return root


def _resolve_path(path: str | Path) -> Path:
    if isinstance(path, str) and not path:
        raise RiskPersistenceConfigurationError("path must be a non-empty path.")
    try:
        return Path(path).expanduser().resolve()
    except (RuntimeError, TypeError, OSError) as exc:
        raise RiskPersistenceConfigurationError("path must be path-like.") from exc


def _require_production_environment(environment: object) -> RiskPersistenceEnvironment:
    try:
        value = RiskPersistenceEnvironment(environment)
    except ValueError as exc:
        raise RiskPersistenceConfigurationError("environment must be PRODUCTION.") from exc
    if value != RiskPersistenceEnvironment.PRODUCTION:
        raise RiskPersistenceConfigurationError("environment must be PRODUCTION.")
    return value


def _validate_busy_timeout(busy_timeout_ms: object) -> None:
    if isinstance(busy_timeout_ms, bool) or not isinstance(busy_timeout_ms, int):
        raise RiskPersistenceConfigurationError("busy_timeout_ms must be a positive integer.")
    if busy_timeout_ms <= 0:
        raise RiskPersistenceConfigurationError("busy_timeout_ms must be a positive integer.")
