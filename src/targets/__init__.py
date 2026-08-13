"""Target generation framework for Long-Term Growth research."""

from targets.artifact_generator import TargetArtifactGenerationError
from targets.artifact_generator import TargetArtifactGenerator
from targets.checksum import TargetChecksumGenerator
from targets.checksum import TargetChecksumMismatchError
from targets.generators import FutureReturn20DRegressionGenerator
from targets.generators import FutureReturn60DClassificationGenerator
from targets.generators import FutureReturn60DRegressionGenerator
from targets.generators import TargetPricePoint
from targets.target_artifact import TargetArtifact
from targets.target_context import TargetCalculationContext
from targets.target_definition import TargetDefinition
from targets.target_generator import TargetGenerationOutput
from targets.target_generator import TargetGenerator
from targets.target_registry import TargetRegistry
from targets.target_registry import TargetRegistryError
from targets.validation import TargetValidationError
from targets.validation import TargetValidator

__all__ = [
    "FutureReturn20DRegressionGenerator",
    "FutureReturn60DClassificationGenerator",
    "FutureReturn60DRegressionGenerator",
    "TargetArtifact",
    "TargetArtifactGenerationError",
    "TargetArtifactGenerator",
    "TargetCalculationContext",
    "TargetChecksumGenerator",
    "TargetChecksumMismatchError",
    "TargetDefinition",
    "TargetGenerationOutput",
    "TargetGenerator",
    "TargetPricePoint",
    "TargetRegistry",
    "TargetRegistryError",
    "TargetValidationError",
    "TargetValidator",
]
