from numbers import Real

from targets.target_context import TargetCalculationContext
from targets.target_definition import TargetDefinition
from targets.target_generator import TargetGenerationOutput


class TargetValidationError(Exception):
    """Raised when target generation output is invalid."""


class TargetValidator:
    """Validation for target generation output envelopes."""

    def validate(
        self,
        output: TargetGenerationOutput,
        context: TargetCalculationContext,
        definition: TargetDefinition | None = None,
    ) -> None:
        resolved_definition = self._resolve_definition(output, definition)
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
        self._validate_definition_alignment(output, context, resolved_definition)
        if output.requires_window_lineage != resolved_definition.requires_window_lineage:
            raise TargetValidationError("Target window lineage requirement echo mismatch.")
        if resolved_definition.requires_window_lineage:
            self._validate_window_lineage(output, context, resolved_definition)

    def _resolve_definition(
        self,
        output: TargetGenerationOutput,
        definition: TargetDefinition | None,
    ) -> TargetDefinition:
        resolved = definition or output.definition
        if resolved is None:
            raise TargetValidationError("Target definition is required for artifact validation.")
        return resolved

    def _validate_definition_alignment(
        self,
        output: TargetGenerationOutput,
        context: TargetCalculationContext,
        definition: TargetDefinition,
    ) -> None:
        if output.target_id != definition.target_id:
            raise TargetValidationError("Target definition target_id mismatch.")
        if output.target_version != definition.version:
            raise TargetValidationError("Target definition target_version mismatch.")
        if context.evaluation_window != definition.calculation_window:
            raise TargetValidationError("Target definition calculation_window mismatch.")

    def _validate_window_lineage(
        self,
        output: TargetGenerationOutput,
        context: TargetCalculationContext,
        definition: TargetDefinition,
    ) -> None:
        lineage = output.window_lineage
        if lineage is None:
            raise TargetValidationError("Future-window target requires window lineage.")
        if lineage.observations_used != definition.calculation_window:
            raise TargetValidationError(
                f"Target window observations mismatch: expected {definition.calculation_window}, got {lineage.observations_used}."
            )
        if not context.reference_date < lineage.target_start_date <= lineage.target_end_date:
            raise TargetValidationError("Target window lineage date ordering is invalid.")
        if output.artifact is not None and output.artifact.window_lineage != lineage:
            raise TargetValidationError("Target artifact window lineage mismatch.")
