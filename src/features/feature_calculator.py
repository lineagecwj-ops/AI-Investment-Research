from dataclasses import dataclass
from typing import Any
from typing import Mapping
from typing import Protocol

from features.feature_artifact import FeatureArtifact
from features.feature_context import FeatureCalculationContext
from features.feature_definition import FeatureDefinition


@dataclass(frozen=True)
class FeatureCalculationOutput:
    """Minimal output envelope for future calculator implementations."""

    feature_id: str
    feature_version: str
    values: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] | None = None
    artifact: FeatureArtifact | None = None


class FeatureCalculator(Protocol):
    """Protocol for future feature calculators.

    Phase 7D-1 defines the interface only. It intentionally contains no
    production feature formulas.
    """

    def get_definition(self) -> FeatureDefinition:
        """Return the versioned feature definition handled by this calculator."""

    def calculate(self, context: FeatureCalculationContext) -> FeatureCalculationOutput:
        """Calculate feature output for the supplied context."""

    def validate(self, output: FeatureCalculationOutput) -> bool:
        """Validate a calculator output envelope."""
