from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import time

from targets.checksum import TargetChecksumGenerator
from targets.target_artifact import TargetArtifact
from targets.target_context import TargetCalculationContext
from targets.target_generator import TargetGenerationOutput
from targets.validation import TargetValidationError
from targets.validation import TargetValidator


class TargetArtifactGenerationError(Exception):
    """Raised when a valid target artifact cannot be generated."""


class TargetArtifactGenerator:
    """Generates metadata-only target artifacts after validation and checksum."""

    def __init__(
        self,
        validator: TargetValidator | None = None,
        checksum_generator: TargetChecksumGenerator | None = None,
    ):
        self.validator = validator or TargetValidator()
        self.checksum_generator = checksum_generator or TargetChecksumGenerator()

    def generate(self, output: TargetGenerationOutput, context: TargetCalculationContext) -> TargetArtifact:
        try:
            self.validator.validate(output, context)
        except TargetValidationError as exc:
            raise TargetArtifactGenerationError(f"Target output validation failed: {exc}") from exc

        checksum = self.checksum_generator.generate(output, context)
        created_at = datetime.combine(context.reference_date, time.min, tzinfo=UTC)
        if output.artifact is not None:
            return replace(output.artifact, checksum=checksum, validation_status="PASS", created_at=created_at)
        return TargetArtifact(
            target_id=output.target_id,
            target_version=output.target_version,
            symbol=output.symbol,
            reference_date=context.reference_date,
            target_value=output.target_value,
            calculation_id=context.calculation_id,
            created_at=created_at,
            checksum=checksum,
            validation_status="PASS",
        )
