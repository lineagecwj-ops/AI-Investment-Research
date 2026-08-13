import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    model_type: str
    metrics: dict[str, float]


class ModelEvaluator:
    """Deterministic baseline metric calculations."""

    def evaluate_classification(
        self,
        y_true: tuple[int, ...],
        y_pred: tuple[int, ...],
        scores: tuple[float, ...] | None = None,
    ) -> EvaluationResult:
        self._validate_same_length(y_true, y_pred)
        if not y_true:
            raise ValueError("Classification evaluation requires at least one sample.")
        tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 1 and pred == 1)
        tn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 0 and pred == 0)
        fp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 0 and pred == 1)
        fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == 1 and pred == 0)
        accuracy = (tp + tn) / len(y_true)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        roc_auc = self._binary_auc(y_true, scores) if scores is not None else 0.0
        return EvaluationResult(
            model_type="classification",
            metrics={
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "roc_auc": roc_auc,
            },
        )

    def evaluate_regression(self, y_true: tuple[float, ...], y_pred: tuple[float, ...]) -> EvaluationResult:
        self._validate_same_length(y_true, y_pred)
        if not y_true:
            raise ValueError("Regression evaluation requires at least one sample.")
        errors = [truth - pred for truth, pred in zip(y_true, y_pred)]
        mae = sum(abs(error) for error in errors) / len(errors)
        rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
        mean_true = sum(y_true) / len(y_true)
        total_sum = sum((truth - mean_true) ** 2 for truth in y_true)
        residual_sum = sum(error * error for error in errors)
        r2 = 1.0 - residual_sum / total_sum if total_sum else 0.0
        return EvaluationResult(model_type="regression", metrics={"mae": mae, "rmse": rmse, "r2": r2})

    def _validate_same_length(self, y_true: tuple, y_pred: tuple) -> None:
        if len(y_true) != len(y_pred):
            raise ValueError("Evaluation input lengths must match.")

    def _binary_auc(self, y_true: tuple[int, ...], scores: tuple[float, ...]) -> float:
        self._validate_same_length(y_true, scores)
        positives = [score for truth, score in zip(y_true, scores) if truth == 1]
        negatives = [score for truth, score in zip(y_true, scores) if truth == 0]
        if not positives or not negatives:
            return 0.0
        wins = 0.0
        for positive in positives:
            for negative in negatives:
                if positive > negative:
                    wins += 1.0
                elif positive == negative:
                    wins += 0.5
        return wins / (len(positives) * len(negatives))
