from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ModelDefinition:
    """Versioned metadata for a baseline model research configuration."""

    model_id: str
    model_name: str
    model_type: str
    version: str
    algorithm: str
    feature_set_version: str
    target_version: str
    created_at: datetime

    def __post_init__(self):
        required = {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "version": self.version,
            "algorithm": self.algorithm,
            "feature_set_version": self.feature_set_version,
            "target_version": self.target_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"ModelDefinition missing required fields: {', '.join(missing)}")
        if self.model_type not in {"classification", "regression", "ranking", "risk"}:
            raise ValueError(f"Unsupported model_type: {self.model_type}")
