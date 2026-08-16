"""DB-agnostic RiskArtifact persistence contracts."""

from risk_persistence.contracts import RiskArtifactConflictError
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError
from risk_persistence.contracts import RiskArtifactRepository
from risk_persistence.contracts import RiskArtifactSaveResult
from risk_persistence.contracts import RiskArtifactSaveStatus
from risk_persistence.capturing_risk_evaluator import CapturingRiskEvaluator
from risk_persistence.portfolio_run_codec import PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1
from risk_persistence.portfolio_run_codec import PORTFOLIO_RUN_RECORD_CODEC_VERSION_V2
from risk_persistence.portfolio_run_codec import PortfolioRiskGenerationRunRecordCodec
from risk_persistence.portfolio_run_codec import PortfolioRiskGenerationRunRecordCodecError
from risk_persistence.portfolio_run_contracts import PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1
from risk_persistence.portfolio_run_contracts import PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V2
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunArtifactRef
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunConflictError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunCorruptionError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunIssue
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunMonitoringArtifactRef
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunPersistenceError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunRecord
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunRepository
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunSaveResult
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunSaveStatus
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunWarning
from risk_persistence.production_config import RiskPersistenceBackupError
from risk_persistence.production_config import RiskPersistenceConfigurationError
from risk_persistence.production_config import RiskPersistenceEnvironment
from risk_persistence.production_config import RiskPersistenceProductionConfig
from risk_persistence.production_config import RiskPersistenceProductionError
from risk_persistence.sqlite_portfolio_run_repository import SQLitePortfolioRiskGenerationRunRepository
from risk_persistence.sqlite_production_health import RiskPersistenceHealthResult
from risk_persistence.sqlite_production_health import RiskPersistenceHealthStatus
from risk_persistence.sqlite_production_health import SQLiteRiskPersistenceHealthChecker
from risk_persistence.sqlite_production_bootstrap import RiskPersistenceBootstrapResult
from risk_persistence.sqlite_production_bootstrap import RiskPersistenceBootstrapStatus
from risk_persistence.sqlite_production_bootstrap import SQLiteRiskPersistenceBootstrapper
from risk_persistence.sqlite_repository import SQLiteRiskArtifactRepository
from risk_persistence.sqlite_technical_artifact_persistence import SQLiteTechnicalRiskArtifactPersistenceCoordinator
from risk_persistence.sqlite_technical_portfolio_persistence import SQLiteTechnicalPortfolioRiskPersistenceCoordinator
from risk_persistence.sqlite_technical_portfolio_persistence import TechnicalPortfolioRiskPersistenceError
from risk_persistence.sqlite_technical_portfolio_persistence import TechnicalPortfolioRiskPersistenceResult
from risk_persistence.sqlite_technical_query_repository import SQLiteTechnicalRiskArtifactQueryRepository
from risk_persistence.technical_query_contracts import RiskArtifactIndexCorruptionError
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactIndexRecord
from risk_persistence.technical_query_contracts import TechnicalRiskArtifactQueryRepository

__all__ = [
    "PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1",
    "PORTFOLIO_RUN_RECORD_CODEC_VERSION_V2",
    "PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1",
    "PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V2",
    "CapturingRiskEvaluator",
    "PortfolioRiskGenerationRunArtifactRef",
    "PortfolioRiskGenerationRunConflictError",
    "PortfolioRiskGenerationRunCorruptionError",
    "PortfolioRiskGenerationRunIssue",
    "PortfolioRiskGenerationRunMonitoringArtifactRef",
    "PortfolioRiskGenerationRunPersistenceError",
    "PortfolioRiskGenerationRunRecord",
    "PortfolioRiskGenerationRunRecordCodec",
    "PortfolioRiskGenerationRunRecordCodecError",
    "PortfolioRiskGenerationRunRepository",
    "PortfolioRiskGenerationRunSaveResult",
    "PortfolioRiskGenerationRunSaveStatus",
    "PortfolioRiskGenerationRunWarning",
    "RiskPersistenceBackupError",
    "RiskPersistenceBootstrapResult",
    "RiskPersistenceBootstrapStatus",
    "RiskPersistenceConfigurationError",
    "RiskPersistenceEnvironment",
    "RiskPersistenceHealthResult",
    "RiskPersistenceHealthStatus",
    "RiskPersistenceProductionConfig",
    "RiskPersistenceProductionError",
    "RiskArtifactIndexCorruptionError",
    "RiskArtifactConflictError",
    "RiskArtifactCorruptionError",
    "RiskArtifactPersistenceError",
    "RiskArtifactRepository",
    "RiskArtifactSaveResult",
    "RiskArtifactSaveStatus",
    "SQLitePortfolioRiskGenerationRunRepository",
    "SQLiteRiskPersistenceHealthChecker",
    "SQLiteRiskPersistenceBootstrapper",
    "SQLiteRiskArtifactRepository",
    "SQLiteTechnicalRiskArtifactPersistenceCoordinator",
    "SQLiteTechnicalPortfolioRiskPersistenceCoordinator",
    "SQLiteTechnicalRiskArtifactQueryRepository",
    "TechnicalPortfolioRiskPersistenceError",
    "TechnicalPortfolioRiskPersistenceResult",
    "TechnicalRiskArtifactIndexRecord",
    "TechnicalRiskArtifactQueryRepository",
]
