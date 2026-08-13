from dataclasses import dataclass
from datetime import datetime
from typing import Any

from risk.risk_artifact import RiskArtifact
from risk_monitoring.alert_candidate import AlertCandidate
from risk_monitoring.monitoring_context import RiskMonitoringContext
from risk_monitoring.monitoring_event import RiskMonitoringEvent
from risk_monitoring.monitoring_types import MonitoringState


@dataclass(frozen=True)
class RiskMonitoringArtifact:
    """Metadata-only artifact for downstream risk monitoring."""

    artifact_id: str
    portfolio_id: str
    symbol: str
    monitoring_state: MonitoringState | str
    overall_risk_level: str
    source_risk_artifact_id: str
    source_risk_checksum: str
    events: tuple[RiskMonitoringEvent, ...]
    alert_candidates: tuple[AlertCandidate, ...]
    policy_version: str
    lineage: dict[str, Any]
    calculation_metadata: dict[str, Any]
    created_at: datetime
    checksum: str | None = None

    def __post_init__(self):
        required = {
            "artifact_id": self.artifact_id,
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "overall_risk_level": self.overall_risk_level,
            "source_risk_artifact_id": self.source_risk_artifact_id,
            "source_risk_checksum": self.source_risk_checksum,
            "policy_version": self.policy_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"RiskMonitoringArtifact missing required fields: {', '.join(missing)}")
        if not isinstance(self.events, tuple):
            raise ValueError("RiskMonitoringArtifact events must be a tuple.")
        if not isinstance(self.alert_candidates, tuple):
            raise ValueError("RiskMonitoringArtifact alert_candidates must be a tuple.")
        if not self.lineage:
            raise ValueError("RiskMonitoringArtifact requires lineage.")
        if not self.calculation_metadata:
            raise ValueError("RiskMonitoringArtifact requires calculation_metadata.")
        if not isinstance(self.created_at, datetime):
            raise ValueError("RiskMonitoringArtifact created_at must be a datetime.")

        object.__setattr__(self, "monitoring_state", MonitoringState(self.monitoring_state))


class RiskMonitoringArtifactGenerator:
    """Build monitoring artifact metadata without persistence."""

    def generate(
        self,
        artifact_id: str,
        risk_artifact: RiskArtifact,
        context: RiskMonitoringContext,
        monitoring_state: MonitoringState,
        events: tuple[RiskMonitoringEvent, ...],
        alert_candidates: tuple[AlertCandidate, ...],
        created_at: datetime,
        checksum: str | None = None,
    ) -> RiskMonitoringArtifact:
        return RiskMonitoringArtifact(
            artifact_id=artifact_id,
            portfolio_id=context.portfolio_id,
            symbol=context.symbol,
            monitoring_state=monitoring_state,
            overall_risk_level=risk_artifact.risk_assessment.overall_risk_level.value,
            source_risk_artifact_id=context.source_risk_artifact_id,
            source_risk_checksum=context.risk_artifact_checksum,
            events=events,
            alert_candidates=alert_candidates,
            policy_version=context.monitoring_policy_version,
            lineage={
                "risk_artifact_id": risk_artifact.artifact_id,
                "risk_artifact_checksum": context.risk_artifact_checksum,
                "risk_assessment_date": risk_artifact.risk_assessment.assessment_date.isoformat(),
                "risk_engine_feature_version": risk_artifact.feature_lineage.get("feature_version"),
                "risk_engine_model_version": risk_artifact.feature_lineage.get("model_version"),
                "risk_overall_level": risk_artifact.risk_assessment.overall_risk_level.value,
            },
            calculation_metadata={
                "calculation_id": context.calculation_id,
                "event_count": len(events),
                "alert_candidate_count": len(alert_candidates),
            },
            created_at=created_at,
            checksum=checksum,
        )
