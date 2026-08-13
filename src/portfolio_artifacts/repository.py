import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact

from portfolio_artifacts.serialization import RiskMonitoringArtifactSerializationError
from portfolio_artifacts.serialization import deserialize_risk_monitoring_artifact


class RiskMonitoringArtifactRepositoryError(ValueError):
    """Raised when read-only risk monitoring artifact repository loading fails."""


@dataclass(frozen=True)
class ArtifactRef:
    """Read-only filesystem reference to a serialized monitoring artifact."""

    artifact_id: str
    portfolio_id: str
    symbol: str
    path: Path
    schema_version: str


class RiskMonitoringArtifactRepository:
    """Read-only filesystem repository for serialized risk monitoring artifacts."""

    def __init__(self, artifact_root: Path | str):
        self.artifact_root = Path(artifact_root)

    def list_artifacts(self, portfolio_id: str | None = None) -> tuple[ArtifactRef, ...]:
        entries = self._load_entries(portfolio_id=portfolio_id)
        return tuple(entry.ref for entry in entries)

    def load_portfolio_artifacts(self, portfolio_id: str | None = None) -> tuple[RiskMonitoringArtifact, ...]:
        entries = self._load_entries(portfolio_id=portfolio_id)
        return tuple(entry.artifact for entry in entries)

    def _load_entries(self, portfolio_id: str | None = None) -> tuple["_ArtifactEntry", ...]:
        files = self._artifact_files()
        entries = tuple(self._load_entry(path) for path in files)
        self._validate_duplicate_artifact_ids(entries)
        filtered = (
            entry
            for entry in entries
            if portfolio_id is None or entry.ref.portfolio_id == portfolio_id
        )
        return tuple(sorted(filtered, key=lambda entry: (entry.ref.portfolio_id, entry.ref.symbol, entry.ref.artifact_id)))

    def _artifact_files(self) -> tuple[Path, ...]:
        artifacts_dir = self.artifact_root / "artifacts"
        if not self.artifact_root.exists() or not artifacts_dir.exists():
            return ()
        if not artifacts_dir.is_dir():
            raise RiskMonitoringArtifactRepositoryError("Risk monitoring artifact root artifacts path must be a directory.")

        root = self.artifact_root.resolve()
        files: list[Path] = []
        for path in artifacts_dir.rglob("*.json"):
            if not self._is_supported_artifact_file(path, root):
                continue
            files.append(path)
        return tuple(sorted(files, key=lambda item: item.as_posix()))

    def _is_supported_artifact_file(self, path: Path, root: Path) -> bool:
        if (
            path.name.startswith(".")
            or path.name.endswith(".tmp")
            or path.name.endswith(".temp")
            or path.name.endswith(".tmp.json")
            or path.name.endswith(".temp.json")
        ):
            return False
        if path.is_symlink() or not path.is_file():
            return False
        try:
            path.resolve().relative_to(root)
        except ValueError:
            return False
        return True

    def _load_entry(self, path: Path) -> "_ArtifactEntry":
        payload = self._read_payload(path)
        try:
            artifact = deserialize_risk_monitoring_artifact(payload)
        except RiskMonitoringArtifactSerializationError as error:
            raise RiskMonitoringArtifactRepositoryError(f"Invalid serialized artifact payload: {path}") from error
        ref = ArtifactRef(
            artifact_id=artifact.artifact_id,
            portfolio_id=artifact.portfolio_id,
            symbol=artifact.symbol,
            path=path,
            schema_version=str(payload.get("schema_version", "")),
        )
        return _ArtifactEntry(ref=ref, artifact=artifact)

    def _read_payload(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as artifact_file:
                payload = json.load(artifact_file)
        except json.JSONDecodeError as error:
            raise RiskMonitoringArtifactRepositoryError(f"Invalid artifact JSON: {path}") from error
        except OSError as error:
            raise RiskMonitoringArtifactRepositoryError(f"Unable to read artifact JSON: {path}") from error
        if not isinstance(payload, dict):
            raise RiskMonitoringArtifactRepositoryError(f"Artifact JSON payload must be an object: {path}")
        return payload

    def _validate_duplicate_artifact_ids(self, entries: tuple["_ArtifactEntry", ...]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for entry in entries:
            artifact_id = entry.ref.artifact_id
            if artifact_id in seen:
                duplicates.add(artifact_id)
            seen.add(artifact_id)
        if duplicates:
            raise RiskMonitoringArtifactRepositoryError(
                f"Duplicate risk monitoring artifact_id: {', '.join(sorted(duplicates))}"
            )


@dataclass(frozen=True)
class _ArtifactEntry:
    ref: ArtifactRef
    artifact: RiskMonitoringArtifact
