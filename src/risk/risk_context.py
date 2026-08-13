from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RiskContext:
    """Reproducibility context for portfolio risk assessment."""

    portfolio_id: str
    symbol: str
    analysis_date: date
    feature_version: str
    calculation_id: str
    model_version: str | None = None

    def __post_init__(self):
        required = {
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "feature_version": self.feature_version,
            "calculation_id": self.calculation_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"RiskContext missing required fields: {', '.join(missing)}")
        if not isinstance(self.analysis_date, date):
            raise ValueError("RiskContext analysis_date must be a date.")
