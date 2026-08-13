from dataclasses import dataclass
from datetime import datetime

from risk_monitoring.monitoring_types import AlertLevel
from risk_monitoring.monitoring_types import AlertType


class AlertCandidateError(ValueError):
    """Raised when alert candidate metadata is invalid."""


@dataclass(frozen=True)
class AlertCandidate:
    """Metadata-only alert candidate, not notification delivery."""

    alert_id: str
    portfolio_id: str
    symbol: str
    alert_level: AlertLevel | str
    alert_type: AlertType | str
    reason: str
    source_event_ids: tuple[str, ...]
    created_at: datetime

    def __post_init__(self):
        required = {
            "alert_id": self.alert_id,
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "reason": self.reason,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise AlertCandidateError(f"AlertCandidate missing required fields: {', '.join(missing)}")
        if not self.source_event_ids:
            raise AlertCandidateError("AlertCandidate requires source_event_ids.")
        if not isinstance(self.created_at, datetime):
            raise AlertCandidateError("AlertCandidate created_at must be a datetime.")

        object.__setattr__(self, "alert_level", AlertLevel(self.alert_level))
        object.__setattr__(self, "alert_type", AlertType(self.alert_type))
