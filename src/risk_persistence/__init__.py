"""DB-agnostic RiskArtifact persistence contracts."""

from risk_persistence.contracts import RiskArtifactConflictError
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.contracts import RiskArtifactRepository
from risk_persistence.contracts import RiskArtifactSaveResult
from risk_persistence.contracts import RiskArtifactSaveStatus

__all__ = [
    "RiskArtifactConflictError",
    "RiskArtifactCorruptionError",
    "RiskArtifactPersistenceError",
    "RiskArtifactRepository",
    "RiskArtifactSaveResult",
    "RiskArtifactSaveStatus",
]
