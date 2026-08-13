from dataclasses import dataclass
from datetime import date
from typing import Mapping


@dataclass(frozen=True)
class FeatureCalculationContext:
    """Reproducibility context for a future feature calculation run."""

    snapshot_id: str
    snapshot_version: str
    universe_id: str
    as_of_date: date
    calculation_id: str
    data_source: str | None = None
    lineage: Mapping[str, str] | None = None

    def __post_init__(self):
        required = {
            "snapshot_id": self.snapshot_id,
            "snapshot_version": self.snapshot_version,
            "universe_id": self.universe_id,
            "calculation_id": self.calculation_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"FeatureCalculationContext missing required fields: {', '.join(missing)}")
