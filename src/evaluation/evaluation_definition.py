from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvaluationDefinition:
    """Versioned metadata describing an evaluation configuration."""

    evaluation_id: str
    evaluation_type: str
    metrics: tuple[str, ...]
    dataset_version: str
    model_version: str
    created_at: datetime

    def __post_init__(self):
        required = {
            "evaluation_id": self.evaluation_id,
            "evaluation_type": self.evaluation_type,
            "dataset_version": self.dataset_version,
            "model_version": self.model_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"EvaluationDefinition missing required fields: {', '.join(missing)}")
        if not self.metrics:
            raise ValueError("EvaluationDefinition requires at least one metric.")
