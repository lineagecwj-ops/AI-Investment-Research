from dataclasses import dataclass
from typing import Any
from typing import Mapping
from typing import Protocol

from targets.target_artifact import TargetArtifact
from targets.target_context import TargetCalculationContext
from targets.target_definition import TargetDefinition


@dataclass(frozen=True)
class TargetGenerationOutput:
    """Output envelope for target generators."""

    target_id: str
    target_version: str
    symbol: str
    reference_date: object
    target_value: float | str | None
    metadata: Mapping[str, Any] | None = None
    artifact: TargetArtifact | None = None


class TargetGenerator(Protocol):
    """Protocol for target generators."""

    def get_definition(self) -> TargetDefinition:
        """Return the target definition handled by this generator."""

    def calculate(self, context: TargetCalculationContext) -> TargetGenerationOutput:
        """Generate target output for the supplied context."""

    def validate(self, output: TargetGenerationOutput) -> bool:
        """Validate a target generation output."""
