from dataclasses import dataclass
from datetime import date
from datetime import datetime


TARGET_ARTIFACT_SCHEMA_VERSION = "v2"
TARGET_CHECKSUM_CONTRACT_VERSION = "target_checksum_v2"


@dataclass(frozen=True)
class TargetWindowLineage:
    """Actual future trading-observation window used by a target calculation."""

    target_start_date: date
    target_end_date: date
    observations_used: int

    def __post_init__(self):
        if not isinstance(self.target_start_date, date):
            raise ValueError("TargetWindowLineage target_start_date must be a date.")
        if not isinstance(self.target_end_date, date):
            raise ValueError("TargetWindowLineage target_end_date must be a date.")
        if self.observations_used <= 0:
            raise ValueError("TargetWindowLineage observations_used must be positive.")
        if self.target_start_date > self.target_end_date:
            raise ValueError("TargetWindowLineage target_start_date cannot be after target_end_date.")


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
    window_lineage: TargetWindowLineage | None = None
    schema_version: str = TARGET_ARTIFACT_SCHEMA_VERSION
    checksum_contract_version: str = TARGET_CHECKSUM_CONTRACT_VERSION

    def __post_init__(self):
        required = {
            "target_id": self.target_id,
            "target_version": self.target_version,
            "symbol": self.symbol,
            "calculation_id": self.calculation_id,
            "schema_version": self.schema_version,
            "checksum_contract_version": self.checksum_contract_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"TargetArtifact missing required fields: {', '.join(missing)}")
