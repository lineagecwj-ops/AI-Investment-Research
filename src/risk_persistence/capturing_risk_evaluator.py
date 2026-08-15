from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from portfolio_generation import RiskEvaluationOutput
from portfolio_generation import RiskEvaluator
from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskContext


class CapturingRiskEvaluatorError(ValueError):
    """Raised when a capturing evaluator is constructed with an invalid delegate."""


@dataclass
class CapturingRiskEvaluator(RiskEvaluator):
    """Run-scoped wrapper that records successful RiskArtifact outputs."""

    delegate: RiskEvaluator
    _captured_artifacts: list[RiskArtifact] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not hasattr(self.delegate, "evaluate"):
            raise CapturingRiskEvaluatorError("CapturingRiskEvaluator requires a RiskEvaluator delegate.")

    @property
    def captured_artifacts(self) -> tuple[RiskArtifact, ...]:
        return tuple(self._captured_artifacts)

    def evaluate(
        self,
        position: PortfolioPosition,
        context: RiskContext,
        risk_artifact_id: str,
    ) -> RiskEvaluationOutput:
        output = self.delegate.evaluate(position, context, risk_artifact_id)
        if not isinstance(output, RiskEvaluationOutput):
            raise CapturingRiskEvaluatorError("CapturingRiskEvaluator delegate returned invalid output.")
        self._captured_artifacts.append(output.risk_artifact)
        return output
