from dataclasses import dataclass


@dataclass(frozen=True)
class ModelContext:
    """Reproducibility context for a model research experiment."""

    model_id: str
    dataset_id: str
    feature_version: str
    target_version: str
    training_period: tuple[str, str]
    validation_period: tuple[str, str]
    oos_period: tuple[str, str]
    experiment_id: str

    def __post_init__(self):
        required = {
            "model_id": self.model_id,
            "dataset_id": self.dataset_id,
            "feature_version": self.feature_version,
            "target_version": self.target_version,
            "experiment_id": self.experiment_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"ModelContext missing required fields: {', '.join(missing)}")
        self._validate_period("training_period", self.training_period)
        self._validate_period("validation_period", self.validation_period)
        self._validate_period("oos_period", self.oos_period)

    def _validate_period(self, name: str, period: tuple[str, str]) -> None:
        if len(period) != 2 or not period[0] or not period[1]:
            raise ValueError(f"ModelContext {name} must contain start and end.")
