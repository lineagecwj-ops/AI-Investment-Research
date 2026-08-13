import hashlib
import json
from datetime import date
from datetime import datetime
from typing import Any

from model_framework.model_artifact import ModelArtifact
from model_framework.model_context import ModelContext


class ModelChecksumMismatchError(Exception):
    """Raised when reproduced model checksum differs from expected value."""


class ModelChecksumGenerator:
    """Deterministic checksum generator for model artifact metadata."""

    def generate(self, artifact: ModelArtifact, context: ModelContext) -> str:
        payload = {
            "model_identity": {
                "model_id": artifact.model_id,
                "version": artifact.version,
                "algorithm": artifact.algorithm,
            },
            "dataset_identity": {
                "dataset_id": artifact.dataset_id,
                "context_dataset_id": context.dataset_id,
                "feature_version": context.feature_version,
                "target_version": context.target_version,
            },
            "configuration": artifact.training_metadata,
            "evaluation_result": artifact.evaluation_summary,
            "experiment_id": context.experiment_id,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=self._json_default)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self, artifact: ModelArtifact, context: ModelContext, expected: str) -> None:
        actual = self.generate(artifact, context)
        if actual != expected:
            raise ModelChecksumMismatchError(f"Model checksum mismatch: expected {expected}, got {actual}.")

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return value
