from dataclasses import dataclass

from model_framework.evaluation import EvaluationResult
from model_framework.evaluation import ModelEvaluator


@dataclass(frozen=True)
class InvestmentEvaluationResult:
    metrics: dict[str, float]


class ModelEvaluatorExtension:
    """Evaluation wrapper with deterministic model and investment metrics."""

    def __init__(self, base_evaluator: ModelEvaluator | None = None):
        self.base_evaluator = base_evaluator or ModelEvaluator()

    def evaluate_classification(
        self,
        y_true: tuple[int, ...],
        y_pred: tuple[int, ...],
        scores: tuple[float, ...] | None = None,
    ) -> EvaluationResult:
        return self.base_evaluator.evaluate_classification(y_true, y_pred, scores)

    def evaluate_regression(self, y_true: tuple[float, ...], y_pred: tuple[float, ...]) -> EvaluationResult:
        return self.base_evaluator.evaluate_regression(y_true, y_pred)

    def evaluate_investment(
        self,
        model_scores: tuple[float, ...],
        realized_returns: tuple[float, ...],
        top_n: int,
    ) -> InvestmentEvaluationResult:
        if len(model_scores) != len(realized_returns):
            raise ValueError("Investment evaluation input lengths must match.")
        if top_n <= 0:
            raise ValueError("top_n must be positive.")
        if not model_scores:
            raise ValueError("Investment evaluation requires at least one sample.")
        return_correlation = self._pearson(model_scores, realized_returns)
        rank_correlation = self._pearson(self._ranks(model_scores), self._ranks(realized_returns))
        paired = sorted(zip(model_scores, realized_returns), key=lambda item: item[0], reverse=True)
        selected = paired[: min(top_n, len(paired))]
        top_n_performance = sum(return_value for _, return_value in selected) / len(selected)
        drawdown = min(realized_returns)
        stability = 1.0 / (1.0 + self._variance(realized_returns))
        return InvestmentEvaluationResult(
            metrics={
                "return_correlation": return_correlation,
                "rank_correlation": rank_correlation,
                "top_n_performance": top_n_performance,
                "drawdown": drawdown,
                "stability": stability,
            }
        )

    def _pearson(self, left: tuple[float, ...], right: tuple[float, ...]) -> float:
        if len(left) != len(right):
            raise ValueError("Correlation input lengths must match.")
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
        left_var = sum((x - left_mean) ** 2 for x in left)
        right_var = sum((y - right_mean) ** 2 for y in right)
        denominator = (left_var * right_var) ** 0.5
        return numerator / denominator if denominator else 0.0

    def _ranks(self, values: tuple[float, ...]) -> tuple[float, ...]:
        ordered = sorted((value, index) for index, value in enumerate(values))
        ranks = [0.0] * len(values)
        for rank, (_, index) in enumerate(ordered, start=1):
            ranks[index] = float(rank)
        return tuple(ranks)

    def _variance(self, values: tuple[float, ...]) -> float:
        mean = sum(values) / len(values)
        return sum((value - mean) ** 2 for value in values) / len(values)
