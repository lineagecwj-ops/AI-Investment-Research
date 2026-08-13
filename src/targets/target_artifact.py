from dataclasses import dataclass
from datetime import date
from datetime import datetime


@dataclass(frozen=True)
class TargetArtifact:
    """Metadata for a target generation result."""

    target_id: str
    target_version: str
    symbol: str
    reference_date: date
    target_value: float | str
    calculation_id: str
    created_at: datetime
    checksum: str | None = None
    validation_status: str = "PENDING"

    def __post_init__(self):
        required = {
            "target_id": self.target_id,
            "target_version": self.target_version,
            "symbol": self.symbol,
            "calculation_id": self.calculation_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"TargetArtifact missing required fields: {', '.join(missing)}")
