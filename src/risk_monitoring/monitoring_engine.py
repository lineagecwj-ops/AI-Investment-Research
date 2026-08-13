from dataclasses import replace
from datetime import datetime

from risk.risk_artifact import RiskArtifact
from risk_monitoring.alert_candidate import AlertCandidate
from risk_monitoring.checksum import RiskMonitoringChecksumGenerator
from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact
from risk_monitoring.monitoring_artifact import RiskMonitoringArtifactGenerator
from risk_monitoring.monitoring_context import RiskMonitoringContext
from risk_monitoring.monitoring_event import RiskMonitoringEvent
from risk_monitoring.monitoring_policy import MonitoringPolicy
from risk_monitoring.monitoring_types import MonitoringState
from risk_monitoring.validation import RiskMonitoringValidator


class RiskMonitoringEngineError(ValueError):
    """Raised when risk monitoring integration cannot be completed."""


class RiskMonitoringEngine:
    """Integrate RiskArtifact into metadata-only monitoring artifacts."""

    def __init__(
        self,
        policy: MonitoringPolicy,
        validator: RiskMonitoringValidator | None = None,
        checksum_generator: RiskMonitoringChecksumGenerator | None = None,
    ):
        self.policy = policy
        self.validator = validator or RiskMonitoringValidator()
        self.checksum_generator = checksum_generator or RiskMonitoringChecksumGenerator()
        self.artifact_generator = RiskMonitoringArtifactGenerator()

    def evaluate(
        self,
        risk_artifact: RiskArtifact,
        context: RiskMonitoringContext,
        created_at: datetime,
        artifact_id: str | None = None,
    ) -> RiskMonitoringArtifact:
        self._validate_inputs(risk_artifact, context, created_at)
        monitoring_state = self.policy.state_for_severity(risk_artifact.risk_assessment.overall_risk_level)
        events = self._build_events(risk_artifact, context, created_at)
        alert_candidates = self._build_alert_candidates(events, context, created_at)
        artifact = self.artifact_generator.generate(
            artifact_id=artifact_id or f"{context.calculation_id}_artifact",
            risk_artifact=risk_artifact,
            context=context,
            monitoring_state=monitoring_state,
            events=events,
            alert_candidates=alert_candidates,
            created_at=created_at,
        )
        checksum = self.checksum_generator.generate(artifact, context)
        completed_artifact = replace(artifact, checksum=checksum)
        self.validator.validate_all(completed_artifact, context)
        self.checksum_generator.verify(completed_artifact, context, checksum)
        return completed_artifact

    def _validate_inputs(self, risk_artifact: RiskArtifact, context: RiskMonitoringContext, created_at: datetime) -> None:
        if not isinstance(risk_artifact, RiskArtifact):
            raise RiskMonitoringEngineError("RiskMonitoringEngine requires RiskArtifact input.")
        if not isinstance(context, RiskMonitoringContext):
            raise RiskMonitoringEngineError("RiskMonitoringEngine requires RiskMonitoringContext input.")
        if not isinstance(created_at, datetime):
            raise RiskMonitoringEngineError("RiskMonitoringEngine created_at must be a datetime.")
        if risk_artifact.artifact_id != context.source_risk_artifact_id:
            raise RiskMonitoringEngineError("RiskArtifact id does not match monitoring context source.")
        if risk_artifact.risk_assessment.portfolio_id != context.portfolio_id:
            raise RiskMonitoringEngineError("RiskArtifact portfolio_id does not match monitoring context.")
        if risk_artifact.risk_assessment.symbol != context.symbol:
            raise RiskMonitoringEngineError("RiskArtifact symbol does not match monitoring context.")

    def _build_events(
        self,
        risk_artifact: RiskArtifact,
        context: RiskMonitoringContext,
        created_at: datetime,
    ) -> tuple[RiskMonitoringEvent, ...]:
        events = [
            RiskMonitoringEvent(
                event_id=f"{context.calculation_id}_event_{index:03d}_{signal.risk_id}",
                portfolio_id=context.portfolio_id,
                symbol=context.symbol,
                source_risk_id=signal.risk_id,
                risk_category=signal.category,
                risk_severity=signal.severity,
                monitoring_state=self.policy.state_for_severity(signal.severity),
                reason=signal.trigger_reason,
                created_at=created_at,
            )
            for index, signal in enumerate(
                sorted(risk_artifact.signals, key=lambda item: (item.risk_id, item.created_at.isoformat())),
                start=1,
            )
        ]
        return tuple(events)

    def _build_alert_candidates(
        self,
        events: tuple[RiskMonitoringEvent, ...],
        context: RiskMonitoringContext,
        created_at: datetime,
    ) -> tuple[AlertCandidate, ...]:
        candidates: list[AlertCandidate] = []
        for index, event in enumerate(events, start=1):
            alert_level = self.policy.alert_level_for_state(event.monitoring_state)
            alert_type = self.policy.alert_type_for_state(event.monitoring_state)
            if alert_level is None or alert_type is None:
                continue
            candidates.append(
                AlertCandidate(
                    alert_id=f"{context.calculation_id}_alert_{index:03d}_{event.source_risk_id}",
                    portfolio_id=context.portfolio_id,
                    symbol=context.symbol,
                    alert_level=alert_level,
                    alert_type=alert_type,
                    reason=f"Risk monitoring metadata review for {event.source_risk_id}",
                    source_event_ids=(event.event_id,),
                    created_at=created_at,
                )
            )
        return tuple(candidates)
