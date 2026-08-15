from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from typing import runtime_checkable

from risk import RiskArtifact


class RiskArtifactSaveStatus(StrEnum):
    """Append-only persistence outcome for a RiskArtifact save request."""

    INSERTED = "INSERTED"
    IDEMPOTENT = "IDEMPOTENT"


class RiskArtifactPersistenceError(ValueError):
    """Base error for DB-agnostic RiskArtifact persistence contract failures."""


class RiskArtifactConflictError(RiskArtifactPersistenceError):
    """Raised when an existing artifact_id has a different checksum."""

    def __init__(self, artifact_id: str, existing_checksum: str, incoming_checksum: str):
        self.artifact_id = _require_text(artifact_id, "artifact_id")
        self.existing_checksum = _require_text(existing_checksum, "existing_checksum")
        self.incoming_checksum = _require_text(incoming_checksum, "incoming_checksum")
        super().__init__(
            "RiskArtifact conflict for artifact_id "
            f"{self.artifact_id}: existing checksum differs from incoming checksum."
        )


class RiskArtifactCorruptionError(RiskArtifactPersistenceError):
    """Raised when a stored RiskArtifact cannot pass integrity validation."""

    def __init__(self, artifact_id: str):
        self.artifact_id = _require_text(artifact_id, "artifact_id")
        super().__init__(f"Stored RiskArtifact is corrupted: {self.artifact_id}.")


@dataclass(frozen=True)
class RiskArtifactSaveResult:
    """Immutable result for one append-only RiskArtifact save operation."""

    artifact_id: str
    checksum: str
    status: RiskArtifactSaveStatus | str

    def __post_init__(self):
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.checksum, "checksum")
        try:
            status = RiskArtifactSaveStatus(self.status)
        except ValueError as exc:
            raise RiskArtifactPersistenceError("status must be a valid save status.") from exc
        object.__setattr__(self, "status", status)


@runtime_checkable
class RiskArtifactRepository(Protocol):
    """DB-agnostic append-only repository contract for immutable RiskArtifact objects.

    Implementations save and return domain RiskArtifact instances only. A repeated
    save of the same artifact_id and checksum is idempotent. The same artifact_id
    with a different checksum must raise RiskArtifactConflictError. If an existing
    stored artifact is corrupted, corruption takes precedence over idempotency or
    conflict. Missing artifacts return None from get_by_artifact_id.
    """

    def save(self, artifact: RiskArtifact) -> RiskArtifactSaveResult:
        """Persist one immutable RiskArtifact or return an idempotent save result."""
        ...

    def get_by_artifact_id(self, artifact_id: str) -> RiskArtifact | None:
        """Return a validated RiskArtifact by artifact_id, or None when absent."""
        ...


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RiskArtifactPersistenceError(f"{field_name} must be a non-empty string.")
    return value
