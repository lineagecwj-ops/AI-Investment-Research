from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact

from portfolio_dashboard.projection import build_portfolio_risk_dashboard_projection
from portfolio_dashboard.validation import PortfolioDashboardValidationError
from portfolio_dashboard.validation import PortfolioDashboardValidator
from portfolio_dashboard.view_model import PortfolioRiskDashboardProjection


class PortfolioArtifactInputErrorCode(StrEnum):
    DUPLICATE_ARTIFACT = "DUPLICATE_ARTIFACT"
    INCOMPATIBLE_ARTIFACT = "INCOMPATIBLE_ARTIFACT"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    EVENT_REFERENCE_MISMATCH = "EVENT_REFERENCE_MISMATCH"
    FORBIDDEN_WORDING = "FORBIDDEN_WORDING"
    VALIDATION_ERROR = "VALIDATION_ERROR"


@dataclass(frozen=True)
class PortfolioArtifactInputRequest:
    """In-memory dashboard artifact input request."""

    artifacts: tuple[RiskMonitoringArtifact, ...]
    reference_time: datetime | None = None
    stale_warning_days: int | None = None


@dataclass(frozen=True)
class PortfolioArtifactInputResult:
    """Structured result for dashboard input preparation."""

    success: bool
    projection: PortfolioRiskDashboardProjection | None
    validation_error: str | None
    validation_error_code: PortfolioArtifactInputErrorCode | None
    warning_metadata: Mapping[str, object]


def build_portfolio_dashboard_input(
    request: PortfolioArtifactInputRequest,
    validator: PortfolioDashboardValidator | None = None,
) -> PortfolioArtifactInputResult:
    """Validate in-memory monitoring artifacts and build a dashboard projection."""

    warning_metadata = _build_warning_metadata(request)
    active_validator = validator or PortfolioDashboardValidator()
    try:
        projection = build_portfolio_risk_dashboard_projection(
            request.artifacts,
            validator=active_validator,
        )
    except PortfolioDashboardValidationError as error:
        return PortfolioArtifactInputResult(
            success=False,
            projection=None,
            validation_error=str(error),
            validation_error_code=_classify_validation_error(str(error)),
            warning_metadata=warning_metadata,
        )
    return PortfolioArtifactInputResult(
        success=True,
        projection=projection,
        validation_error=None,
        validation_error_code=None,
        warning_metadata=warning_metadata,
    )


def _classify_validation_error(message: str) -> PortfolioArtifactInputErrorCode:
    lowered = message.lower()
    if "duplicate artifact_id" in lowered:
        return PortfolioArtifactInputErrorCode.DUPLICATE_ARTIFACT
    if "lineage checksum mismatch" in lowered:
        return PortfolioArtifactInputErrorCode.CHECKSUM_MISMATCH
    if "lineage risk artifact mismatch" in lowered:
        return PortfolioArtifactInputErrorCode.LINEAGE_MISMATCH
    if "unknown monitoring event" in lowered:
        return PortfolioArtifactInputErrorCode.EVENT_REFERENCE_MISMATCH
    if "forbidden term" in lowered:
        return PortfolioArtifactInputErrorCode.FORBIDDEN_WORDING
    if "missing required" in lowered or "expected riskmonitoringartifact" in lowered:
        return PortfolioArtifactInputErrorCode.INCOMPATIBLE_ARTIFACT
    return PortfolioArtifactInputErrorCode.VALIDATION_ERROR


def _build_warning_metadata(request: PortfolioArtifactInputRequest) -> Mapping[str, object]:
    artifacts = request.artifacts if isinstance(request.artifacts, tuple) else ()
    created_at_values = tuple(
        artifact.created_at
        for artifact in artifacts
        if isinstance(getattr(artifact, "created_at", None), datetime)
    )
    if not created_at_values:
        return MappingProxyType(
            {
                "artifact_count": len(artifacts),
                "latest_created_at": None,
                "oldest_created_at": None,
                "reference_time": _format_datetime(request.reference_time),
                "max_artifact_age_days": None,
                "min_artifact_age_days": None,
                "stale_warning": False,
                "stale_artifact_ids": (),
            }
        )

    latest_created_at = max(created_at_values)
    oldest_created_at = min(created_at_values)
    ages = (
        tuple(
            _age_days(request.reference_time, artifact.created_at)
            for artifact in artifacts
            if isinstance(getattr(artifact, "created_at", None), datetime)
            and request.reference_time is not None
        )
    )
    stale_artifact_ids = _stale_artifact_ids(request)
    return MappingProxyType(
        {
            "artifact_count": len(artifacts),
            "latest_created_at": latest_created_at.isoformat(),
            "oldest_created_at": oldest_created_at.isoformat(),
            "reference_time": _format_datetime(request.reference_time),
            "max_artifact_age_days": max(ages) if ages else None,
            "min_artifact_age_days": min(ages) if ages else None,
            "stale_warning": bool(stale_artifact_ids),
            "stale_artifact_ids": stale_artifact_ids,
        }
    )


def _stale_artifact_ids(request: PortfolioArtifactInputRequest) -> tuple[str, ...]:
    if request.reference_time is None or request.stale_warning_days is None:
        return ()
    return tuple(
        artifact.artifact_id
        for artifact in sorted(
            request.artifacts,
            key=lambda item: getattr(item, "artifact_id", ""),
        )
        if isinstance(getattr(artifact, "created_at", None), datetime)
        and _age_days(request.reference_time, artifact.created_at) > request.stale_warning_days
    )


def _age_days(reference_time: datetime, created_at: datetime) -> int:
    return max((reference_time - created_at).days, 0)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
