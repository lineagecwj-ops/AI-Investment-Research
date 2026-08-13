from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvaluationArtifact:
    """Metadata-only artifact for OOS evaluation results."""

    evaluation_id: str
    model_id: str
    dataset_id: str
    metrics: dict[str, float]
    oos_period: tuple[str, str]
    created_at: datetime
    checksum: str | None = None
    validation_status: str = "PENDING"

    def __post_init__(self):
        required = {
            "evaluation_id": self.evaluation_id,
            "model_id": self.model_id,
            "dataset_id": self.dataset_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"EvaluationArtifact missing required fields: {', '.join(missing)}")
        if not self.metrics:
            raise ValueError("EvaluationArtifact requires metrics.")
