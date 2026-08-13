from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact
from risk_monitoring.monitoring_context import RiskMonitoringContext
from risk_monitoring.monitoring_types import MonitoringState


class RiskMonitoringValidationError(Exception):
    """Base class for monitoring validation failures."""


class ForbiddenMonitoringActionError(RiskMonitoringValidationError):
    """Raised when monitoring metadata contains trading semantics."""


FORBIDDEN_ACTION_TERMS = (
    "buy",
    "sell",
    "hold",
    "entry",
    "exit",
    "take profit",
    "stop loss",
)


class RiskMonitoringValidator:
    """Validation layer for risk monitoring artifacts."""

    def validate_schema(self, artifact: RiskMonitoringArtifact) -> None:
        if not isinstance(artifact, RiskMonitoringArtifact):
            raise RiskMonitoringValidationError("Expected RiskMonitoringArtifact.")
        if artifact.calculation_metadata.get("event_count") != len(artifact.events):
            raise RiskMonitoringValidationError("Monitoring artifact event_count mismatch.")
        if artifact.calculation_metadata.get("alert_candidate_count") != len(artifact.alert_candidates):
            raise RiskMonitoringValidationError("Monitoring artifact alert_candidate_count mismatch.")
        MonitoringState(artifact.monitoring_state)

    def validate_lineage(self, artifact: RiskMonitoringArtifact, context: RiskMonitoringContext) -> None:
        if artifact.source_risk_artifact_id != context.source_risk_artifact_id:
            raise RiskMonitoringValidationError("Monitoring artifact source risk artifact mismatch.")
        if artifact.source_risk_checksum != context.risk_artifact_checksum:
            raise RiskMonitoringValidationError("Monitoring artifact source risk checksum mismatch.")
        if artifact.lineage.get("risk_artifact_id") != context.source_risk_artifact_id:
            raise RiskMonitoringValidationError("Monitoring artifact lineage risk artifact mismatch.")
        if artifact.lineage.get("risk_artifact_checksum") != context.risk_artifact_checksum:
            raise RiskMonitoringValidationError("Monitoring artifact lineage checksum mismatch.")

    def validate_events(self, artifact: RiskMonitoringArtifact) -> None:
        event_ids = tuple(event.event_id for event in artifact.events)
        if event_ids != tuple(sorted(event_ids)):
            raise RiskMonitoringValidationError("Monitoring events must be deterministically ordered.")
        if len(set(event_ids)) != len(event_ids):
            raise RiskMonitoringValidationError("Monitoring events must have unique event_id values.")
        for event in artifact.events:
            if event.portfolio_id != artifact.portfolio_id:
                raise RiskMonitoringValidationError("Monitoring event portfolio_id mismatch.")
            if event.symbol != artifact.symbol:
                raise RiskMonitoringValidationError("Monitoring event symbol mismatch.")

    def validate_alert_candidates(self, artifact: RiskMonitoringArtifact) -> None:
        event_ids = {event.event_id for event in artifact.events}
        alert_ids = tuple(alert.alert_id for alert in artifact.alert_candidates)
        if alert_ids != tuple(sorted(alert_ids)):
            raise RiskMonitoringValidationError("Alert candidates must be deterministically ordered.")
        if len(set(alert_ids)) != len(alert_ids):
            raise RiskMonitoringValidationError("Alert candidates must have unique alert_id values.")
        for alert in artifact.alert_candidates:
            if alert.portfolio_id != artifact.portfolio_id:
                raise RiskMonitoringValidationError("Alert candidate portfolio_id mismatch.")
            if alert.symbol != artifact.symbol:
                raise RiskMonitoringValidationError("Alert candidate symbol mismatch.")
            if not set(alert.source_event_ids).issubset(event_ids):
                raise RiskMonitoringValidationError("Alert candidate references unknown monitoring event.")

    def validate_no_trading_semantics(self, artifact: RiskMonitoringArtifact) -> None:
        text_parts = [artifact.monitoring_state.value]
        text_parts.extend(event.reason for event in artifact.events)
        text_parts.extend(alert.reason for alert in artifact.alert_candidates)
        text = " ".join(text_parts).lower()
        for term in FORBIDDEN_ACTION_TERMS:
            if term in text:
                raise ForbiddenMonitoringActionError(f"Risk monitoring metadata contains forbidden term: {term}")

    def validate_all(self, artifact: RiskMonitoringArtifact, context: RiskMonitoringContext) -> None:
        self.validate_schema(artifact)
        self.validate_lineage(artifact, context)
        self.validate_events(artifact)
        self.validate_alert_candidates(artifact)
        self.validate_no_trading_semantics(artifact)
