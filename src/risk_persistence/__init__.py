"""DB-agnostic RiskArtifact persistence contracts."""

from risk_persistence.contracts import RiskArtifactConflictError
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.contracts import RiskArtifactRepository
from risk_persistence.contracts import RiskArtifactSaveResult
from risk_persistence.contracts import RiskArtifactSaveStatus
from risk_persistence.sqlite_repository import SQLiteRiskArtifactRepository
from risk_persistence.sqlite_technical_query_repository import SQLiteTechnicalRiskArtifactQueryRepository
from risk_persistence.technical_query_contracts import RiskArtifactIndexCorruptionError
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactQueryRepository

__all__ = [
    "RiskArtifactIndexCorruptionError",
    "RiskArtifactConflictError",
    "RiskArtifactCorruptionError",
    "RiskArtifactPersistenceError",
    "RiskArtifactRepository",
    "RiskArtifactSaveResult",
    "RiskArtifactSaveStatus",
    "SQLiteRiskArtifactRepository",
    "SQLiteTechnicalRiskArtifactQueryRepository",
    "TechnicalRiskArtifactIndexRecord",
    "TechnicalRiskArtifactQueryRepository",
]
