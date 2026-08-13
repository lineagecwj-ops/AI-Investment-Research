from dataclasses import dataclass
from typing import Protocol

from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskContext


@dataclass(frozen=True)
class RiskEvaluationOutput:
    """Risk evaluator output consumed by generation orchestration."""

    position_id: str
    symbol: str
    risk_artifact: RiskArtifact
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.position_id:
            raise ValueError("RiskEvaluationOutput requires position_id.")
        if not self.symbol:
            raise ValueError("RiskEvaluationOutput requires symbol.")
        if not isinstance(self.risk_artifact, RiskArtifact):
            raise ValueError("RiskEvaluationOutput requires RiskArtifact.")
        if not isinstance(self.warnings, tuple):
            raise ValueError("RiskEvaluationOutput warnings must be a tuple.")


class RiskEvaluator(Protocol):
    """Minimal risk evaluator interface for generation service framework."""

    def evaluate(
        self,
        position: PortfolioPosition,
        context: RiskContext,
        risk_artifact_id: str,
    ) -> RiskEvaluationOutput:
        ...
