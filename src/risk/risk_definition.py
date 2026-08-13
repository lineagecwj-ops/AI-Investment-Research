from dataclasses import dataclass
from enum import StrEnum


class RiskCategory(StrEnum):
    """Risk categories supported by the portfolio risk framework."""

    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MARKET = "market"
    PORTFOLIO = "portfolio"


class RiskSeverity(StrEnum):
    """Ordered risk severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SEVERITY_ORDER = {
    RiskSeverity.LOW: 1,
    RiskSeverity.MEDIUM: 2,
    RiskSeverity.HIGH: 3,
    RiskSeverity.CRITICAL: 4,
}


class RiskDefinitionError(ValueError):
    """Raised when a risk definition is invalid."""


@dataclass(frozen=True)
class RiskDefinition:
    """Metadata-only definition for a risk signal family."""

    risk_id: str
    risk_name: str
    category: RiskCategory | str
    version: str
    description: str
    severity_rule: str

    def __post_init__(self):
        required = {
            "risk_id": self.risk_id,
            "risk_name": self.risk_name,
            "version": self.version,
            "description": self.description,
            "severity_rule": self.severity_rule,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RiskDefinitionError(f"RiskDefinition missing required fields: {', '.join(missing)}")

        object.__setattr__(self, "category", RiskCategory(self.category))
