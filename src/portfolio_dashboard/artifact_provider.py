from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from portfolio_artifacts import RiskMonitoringArtifactRepository
from portfolio_artifacts import RiskMonitoringArtifactRepositoryError
from portfolio_dashboard.artifact_input import PortfolioArtifactInputResult
from portfolio_dashboard.artifact_input import PortfolioArtifactInputRequest
from portfolio_dashboard.artifact_input import build_portfolio_dashboard_input
from portfolio_dashboard.view_model import PortfolioRiskDashboardProjection


DEFAULT_RISK_MONITORING_ARTIFACT_ROOT = Path("data/portfolio_artifacts/risk_monitoring")


@dataclass(frozen=True)
class PortfolioDashboardProviderResult:
    """Application-level result for read-only persisted portfolio dashboard input."""

    success: bool
    projection: PortfolioRiskDashboardProjection | None
    error: str | None
    warning_metadata: Mapping[str, object]

    @property
    def is_empty(self) -> bool:
        return self.success and (
            self.projection is None or self.projection.overview.artifact_count == 0
        )

    @property
    def has_warning(self) -> bool:
        return bool(self.warning_metadata.get("stale_warning"))


def load_portfolio_risk_dashboard(
    artifact_root: Path | str = DEFAULT_RISK_MONITORING_ARTIFACT_ROOT,
) -> PortfolioDashboardProviderResult:
    """Load persisted monitoring artifacts and prepare a dashboard projection."""

    repository = RiskMonitoringArtifactRepository(artifact_root)
    try:
        artifacts = repository.load_portfolio_artifacts()
    except RiskMonitoringArtifactRepositoryError as error:
        return PortfolioDashboardProviderResult(
            success=False,
            projection=None,
            error=str(error),
            warning_metadata=MappingProxyType({}),
        )

    input_result = build_portfolio_dashboard_input(
        PortfolioArtifactInputRequest(artifacts=artifacts)
    )
    return _provider_result_from_input(input_result)


def _provider_result_from_input(
    input_result: PortfolioArtifactInputResult,
) -> PortfolioDashboardProviderResult:
    if not input_result.success:
        return PortfolioDashboardProviderResult(
            success=False,
            projection=None,
            error=input_result.validation_error,
            warning_metadata=input_result.warning_metadata,
        )
    return PortfolioDashboardProviderResult(
        success=True,
        projection=input_result.projection,
        error=None,
        warning_metadata=input_result.warning_metadata,
    )
