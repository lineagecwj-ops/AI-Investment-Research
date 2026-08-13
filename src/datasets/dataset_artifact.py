from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetArtifact:
    """Metadata-only artifact for a built training dataset."""

    dataset_id: str
    dataset_version: str
    snapshot_id: str
    feature_versions: tuple[str, ...]
    target_version: str
    row_count: int
    created_at: datetime
    checksum: str | None = None
    validation_status: str = "PENDING"

    def __post_init__(self):
        required = {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "snapshot_id": self.snapshot_id,
            "target_version": self.target_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"DatasetArtifact missing required fields: {', '.join(missing)}")
        if self.row_count < 0:
            raise ValueError("DatasetArtifact row_count cannot be negative.")
