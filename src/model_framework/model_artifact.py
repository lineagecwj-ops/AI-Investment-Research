from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ModelArtifact:
    """Metadata-only artifact for a baseline model experiment."""

    model_id: str
    version: str
    dataset_id: str
    algorithm: str
    training_metadata: dict[str, Any]
    evaluation_summary: dict[str, float]
    created_at: datetime
    checksum: str | None = None

    def __post_init__(self):
        required = {
            "model_id": self.model_id,
            "version": self.version,
            "dataset_id": self.dataset_id,
            "algorithm": self.algorithm,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"ModelArtifact missing required fields: {', '.join(missing)}")
