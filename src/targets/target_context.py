from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TargetCalculationContext:
    """Reproducibility context for a target calculation."""

    snapshot_id: str
    symbol: str
    reference_date: date
    evaluation_window: int
    target_version: str
    calculation_id: str

    def __post_init__(self):
        required = {
            "snapshot_id": self.snapshot_id,
            "symbol": self.symbol,
            "target_version": self.target_version,
            "calculation_id": self.calculation_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"TargetCalculationContext missing required fields: {', '.join(missing)}")
        if self.evaluation_window <= 0:
            raise ValueError("TargetCalculationContext evaluation_window must be positive.")
