from dataclasses import dataclass
from datetime import datetime

from risk.risk_definition import RiskCategory
from risk.risk_definition import RiskSeverity


class RiskSignalError(ValueError):
    """Raised when a risk signal is invalid."""


@dataclass(frozen=True)
class RiskSignal:
    """Single deterministic risk signal, not a trading signal."""

    risk_id: str
    symbol: str
    category: RiskCategory | str
    severity: RiskSeverity | str
    trigger_reason: str
    created_at: datetime

    def __post_init__(self):
        required = {
            "risk_id": self.risk_id,
            "symbol": self.symbol,
            "trigger_reason": self.trigger_reason,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RiskSignalError(f"RiskSignal missing required fields: {', '.join(missing)}")
        if not isinstance(self.created_at, datetime):
            raise RiskSignalError("RiskSignal created_at must be a datetime.")

        object.__setattr__(self, "category", RiskCategory(self.category))
        object.__setattr__(self, "severity", RiskSeverity(self.severity))
