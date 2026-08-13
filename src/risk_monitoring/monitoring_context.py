from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RiskMonitoringContext:
    """Reproducibility context for risk monitoring artifacts."""

    portfolio_id: str
    symbol: str
    monitoring_date: date
    source_risk_artifact_id: str
    risk_artifact_checksum: str
    monitoring_policy_version: str
    calculation_id: str

    def __post_init__(self):
        required = {
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "source_risk_artifact_id": self.source_risk_artifact_id,
            "risk_artifact_checksum": self.risk_artifact_checksum,
            "monitoring_policy_version": self.monitoring_policy_version,
            "calculation_id": self.calculation_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"RiskMonitoringContext missing required fields: {', '.join(missing)}")
        if not isinstance(self.monitoring_date, date):
            raise ValueError("RiskMonitoringContext monitoring_date must be a date.")
