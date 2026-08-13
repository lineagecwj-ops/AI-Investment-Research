from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import time

from features.checksum import FeatureChecksumGenerator
from features.feature_artifact import FeatureArtifact
from features.feature_calculator import FeatureCalculationOutput
from features.feature_context import FeatureCalculationContext
from features.validation import FeatureValidationError
from features.validation import FeatureValidator


class ArtifactGenerationError(Exception):
    """Raised when a valid feature artifact cannot be generated."""


class FeatureArtifactGenerator:
    """Generates metadata-only feature artifacts after validation and checksum."""

    def __init__(
        self,
        validator: FeatureValidator | None = None,
        checksum_generator: FeatureChecksumGenerator | None = None,
    ):
        self.validator = validator or FeatureValidator()
        self.checksum_generator = checksum_generator or FeatureChecksumGenerator()

    def generate(
        self,
        output: FeatureCalculationOutput,
        context: FeatureCalculationContext,
        expected_symbols: tuple[str, ...] = (),
    ) -> FeatureArtifact:
        try:
            self.validator.validate_all(output, context, expected_symbols=expected_symbols)
        except FeatureValidationError as exc:
            raise ArtifactGenerationError(f"Feature output validation failed: {exc}") from exc

        checksum = self.checksum_generator.generate(output, context)
        created_at = datetime.combine(context.as_of_date, time.min, tzinfo=UTC)
        source_artifact = output.artifact
        if source_artifact is not None:
            return replace(source_artifact, checksum=checksum, validation_status="PASS", created_at=created_at)
        return FeatureArtifact(
            feature_id=output.feature_id,
            feature_version=output.feature_version,
            snapshot_id=context.snapshot_id,
            calculation_id=context.calculation_id,
            created_at=created_at,
            checksum=checksum,
            validation_status="PASS",
        )
