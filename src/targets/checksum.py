import hashlib
import json
from datetime import date
from typing import Any

from targets.target_artifact import TARGET_ARTIFACT_SCHEMA_VERSION
from targets.target_artifact import TARGET_CHECKSUM_CONTRACT_VERSION
from targets.target_artifact import TargetWindowLineage
from targets.target_context import TargetCalculationContext
from targets.target_generator import TargetGenerationOutput


class TargetChecksumMismatchError(Exception):
    """Raised when reproduced target checksum differs from the expected value."""


class TargetChecksumGenerator:
    """Deterministic checksum generator for target outputs."""

    def generate(self, output: TargetGenerationOutput, context: TargetCalculationContext) -> str:
        artifact_schema_version = (
            output.artifact.schema_version
            if output.artifact is not None
            else TARGET_ARTIFACT_SCHEMA_VERSION
        )
        payload = {
            "checksum_contract_version": TARGET_CHECKSUM_CONTRACT_VERSION,
            "artifact_schema_version": artifact_schema_version,
            "target_id": output.target_id,
            "target_version": output.target_version,
            "symbol": output.symbol,
            "reference_date": self._json_default(output.reference_date),
            "window": context.evaluation_window,
            "target_value": output.target_value,
            "calculation_id": context.calculation_id,
            "window_lineage": self._window_lineage_payload(output.window_lineage),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=self._json_default)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self, output: TargetGenerationOutput, context: TargetCalculationContext, expected: str) -> None:
        actual = self.generate(output, context)
        if actual != expected:
            raise TargetChecksumMismatchError(f"Target checksum mismatch: expected {expected}, got {actual}.")

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _window_lineage_payload(self, lineage: TargetWindowLineage | None) -> dict[str, Any] | None:
        if lineage is None:
            return None
        return {
            "target_start_date": self._json_default(lineage.target_start_date),
            "target_end_date": self._json_default(lineage.target_end_date),
            "observations_used": lineage.observations_used,
        }
