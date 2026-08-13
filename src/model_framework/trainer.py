from dataclasses import dataclass
from typing import Protocol

from model_framework.evaluation import EvaluationResult


@dataclass(frozen=True)
class BaselineAlgorithmSpec:
    model_type: str
    algorithms: tuple[str, ...]


@dataclass(frozen=True)
class TrainingResult:
    model_id: str
    algorithm: str
    fitted: bool
    metadata: dict[str, str]


class ModelTrainer(Protocol):
    """Interface for future baseline trainers.

    Phase 7I defines the contract only and does not train real models.
    """

    def train(self, dataset) -> TrainingResult:
        """Fit a model from a dataset artifact or adapter."""

    def predict(self, dataset) -> tuple:
        """Generate research predictions for evaluation, not production use."""

    def evaluate(self, dataset) -> EvaluationResult:
        """Evaluate model output against an approved dataset split."""


CLASSIFICATION_ALGORITHMS = BaselineAlgorithmSpec(
    model_type="classification",
    algorithms=("logistic_regression", "random_forest"),
)

REGRESSION_ALGORITHMS = BaselineAlgorithmSpec(
    model_type="regression",
    algorithms=("linear_regression", "gradient_boosting"),
)
