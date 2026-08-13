import hashlib
import json
from datetime import date
from datetime import datetime
from typing import Any

from evaluation.evaluation_artifact import EvaluationArtifact
from evaluation.evaluation_context import EvaluationContext


class EvaluationChecksumMismatchError(Exception):
    """Raised when reproduced evaluation checksum differs from expected value."""


class EvaluationChecksumGenerator:
    """Deterministic checksum generator for evaluation artifacts."""

    def generate(self, artifact: EvaluationArtifact, context: EvaluationContext) -> str:
        payload = {
            "model_identity": {
                "model_id": artifact.model_id,
                "model_version": context.model_version,
            },
            "dataset_identity": {
                "dataset_id": artifact.dataset_id,
            },
            "evaluation_configuration": {
                "evaluation_id": artifact.evaluation_id,
                "training_period": context.training_period,
                "validation_period": context.validation_period,
                "oos_period": artifact.oos_period,
                "experiment_id": context.experiment_id,
            },
            "metrics": artifact.metrics,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=self._json_default)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self, artifact: EvaluationArtifact, context: EvaluationContext, expected: str) -> None:
        actual = self.generate(artifact, context)
        if actual != expected:
            raise EvaluationChecksumMismatchError(f"Evaluation checksum mismatch: expected {expected}, got {actual}.")

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return value
