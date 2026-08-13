from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetDefinition:
    """Versioned metadata describing a training dataset recipe."""

    dataset_id: str
    dataset_name: str
    dataset_version: str
    feature_versions: tuple[str, ...]
    target_versions: tuple[str, ...]
    snapshot_id: str
    universe_id: str
    created_at: datetime

    def __post_init__(self):
        required = {
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "snapshot_id": self.snapshot_id,
            "universe_id": self.universe_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"DatasetDefinition missing required fields: {', '.join(missing)}")
        if not self.feature_versions:
            raise ValueError("DatasetDefinition requires at least one feature version.")
        if not self.target_versions:
            raise ValueError("DatasetDefinition requires at least one target version.")
