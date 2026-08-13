from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationContext:
    """Reproducibility context for model evaluation."""

    model_id: str
    model_version: str
    dataset_id: str
    training_period: tuple[str, str]
    validation_period: tuple[str, str]
    oos_period: tuple[str, str]
    experiment_id: str

    def __post_init__(self):
        required = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"EvaluationContext missing required fields: {', '.join(missing)}")
