from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FeatureArtifact:
    """Metadata for a future feature result artifact.

    Phase 7D-1 stores only metadata shape. It does not store feature values.
    """

    feature_id: str
    feature_version: str
    snapshot_id: str
    calculation_id: str
    created_at: datetime
    checksum: str | None = None
    validation_status: str = "PENDING"

    def __post_init__(self):
        required = {
            "feature_id": self.feature_id,
            "feature_version": self.feature_version,
            "snapshot_id": self.snapshot_id,
            "calculation_id": self.calculation_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"FeatureArtifact missing required fields: {', '.join(missing)}")
