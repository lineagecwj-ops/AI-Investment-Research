from dataclasses import dataclass

from risk.risk_definition import RiskSeverity
from risk_monitoring.monitoring_types import AlertLevel
from risk_monitoring.monitoring_types import AlertType
from risk_monitoring.monitoring_types import MonitoringState


class MonitoringPolicyError(ValueError):
    """Raised when monitoring policy metadata is invalid."""


@dataclass(frozen=True)
class MonitoringPolicy:
    """Deterministic metadata-only mapping from risk level to monitoring state."""

    policy_id: str
    policy_name: str
    version: str
    description: str

    def __post_init__(self):
        required = {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "version": self.version,
            "description": self.description,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise MonitoringPolicyError(f"MonitoringPolicy missing required fields: {', '.join(missing)}")

    def state_for_severity(self, severity: RiskSeverity | str) -> MonitoringState:
        severity_value = RiskSeverity(severity)
        return {
            RiskSeverity.LOW: MonitoringState.NORMAL,
            RiskSeverity.MEDIUM: MonitoringState.WATCH,
            RiskSeverity.HIGH: MonitoringState.REVIEW_REQUIRED,
            RiskSeverity.CRITICAL: MonitoringState.ESCALATED_REVIEW,
        }[severity_value]

    def alert_level_for_state(self, state: MonitoringState | str) -> AlertLevel | None:
        state_value = MonitoringState(state)
        return {
            MonitoringState.NORMAL: None,
            MonitoringState.WATCH: AlertLevel.NOTICE,
            MonitoringState.REVIEW_REQUIRED: AlertLevel.REVIEW,
            MonitoringState.ESCALATED_REVIEW: AlertLevel.ESCALATED,
        }[state_value]

    def alert_type_for_state(self, state: MonitoringState | str) -> AlertType | None:
        state_value = MonitoringState(state)
        return {
            MonitoringState.NORMAL: None,
            MonitoringState.WATCH: AlertType.RISK_MONITORING,
            MonitoringState.REVIEW_REQUIRED: AlertType.RISK_REVIEW,
            MonitoringState.ESCALATED_REVIEW: AlertType.ESCALATED_RISK_REVIEW,
        }[state_value]
