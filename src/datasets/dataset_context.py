from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetContext:
    """Reproducibility context for dataset building."""

    dataset_id: str
    snapshot_id: str
    feature_set_version: str
    target_version: str
    universe_id: str
    calculation_id: str
    universe_version: str | None = None
    split_policy: str | None = None

    def __post_init__(self):
        required = {
            "dataset_id": self.dataset_id,
            "snapshot_id": self.snapshot_id,
            "feature_set_version": self.feature_set_version,
            "target_version": self.target_version,
            "universe_id": self.universe_id,
            "calculation_id": self.calculation_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"DatasetContext missing required fields: {', '.join(missing)}")
