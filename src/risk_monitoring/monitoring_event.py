from dataclasses import dataclass
from datetime import datetime

from risk.risk_definition import RiskCategory
from risk.risk_definition import RiskSeverity
from risk_monitoring.monitoring_types import MonitoringState


class RiskMonitoringEventError(ValueError):
    """Raised when monitoring event metadata is invalid."""


@dataclass(frozen=True)
class RiskMonitoringEvent:
    """Metadata-only monitoring event derived from a risk assessment."""

    event_id: str
    portfolio_id: str
    symbol: str
    source_risk_id: str
    risk_category: RiskCategory | str
    risk_severity: RiskSeverity | str
    monitoring_state: MonitoringState | str
    reason: str
    created_at: datetime

    def __post_init__(self):
        required = {
            "event_id": self.event_id,
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "source_risk_id": self.source_risk_id,
            "reason": self.reason,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RiskMonitoringEventError(f"RiskMonitoringEvent missing required fields: {', '.join(missing)}")
        if not isinstance(self.created_at, datetime):
            raise RiskMonitoringEventError("RiskMonitoringEvent created_at must be a datetime.")

        object.__setattr__(self, "risk_category", RiskCategory(self.risk_category))
        object.__setattr__(self, "risk_severity", RiskSeverity(self.risk_severity))
        object.__setattr__(self, "monitoring_state", MonitoringState(self.monitoring_state))
