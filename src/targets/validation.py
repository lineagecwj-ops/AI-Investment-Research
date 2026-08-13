from numbers import Real

from targets.target_context import TargetCalculationContext
from targets.target_generator import TargetGenerationOutput


class TargetValidationError(Exception):
    """Raised when target generation output is invalid."""


class TargetValidator:
    """Validation for target generation output envelopes."""

    def validate(self, output: TargetGenerationOutput, context: TargetCalculationContext) -> None:
        metadata = output.metadata or {}
        status = metadata.get("validation_status")
        if status != "PASS":
            reason = metadata.get("reason", "target output did not pass validation")
            raise TargetValidationError(str(reason))
        if output.symbol != context.symbol:
            raise TargetValidationError(f"Target symbol mismatch: expected {context.symbol}, got {output.symbol}.")
        if output.reference_date != context.reference_date:
            raise TargetValidationError("Target reference_date mismatch.")
        if output.target_value is None:
            raise TargetValidationError("Target value is missing.")
        if output.target_id.endswith("_REG_V1") and not isinstance(output.target_value, Real):
            raise TargetValidationError("Regression target value must be numeric.")
        if output.target_id.endswith("_CLASS_V1") and output.target_value not in {"Positive", "Neutral", "Negative"}:
            raise TargetValidationError(f"Unexpected classification label: {output.target_value}")
