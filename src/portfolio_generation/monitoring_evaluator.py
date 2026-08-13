from dataclasses import dataclass
from typing import Any
from typing import Protocol

from risk import RiskArtifact
from risk_monitoring import RiskMonitoringContext


@dataclass(frozen=True)
class MonitoringEvaluationOutput:
    """Monitoring evaluator output consumed by generation orchestration."""

    position_id: str
    symbol: str
    monitoring_artifact: Any
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.position_id:
            raise ValueError("MonitoringEvaluationOutput requires position_id.")
        if not self.symbol:
            raise ValueError("MonitoringEvaluationOutput requires symbol.")
        if self.monitoring_artifact is None:
            raise ValueError("MonitoringEvaluationOutput requires monitoring_artifact.")
        if not isinstance(self.warnings, tuple):
            raise ValueError("MonitoringEvaluationOutput warnings must be a tuple.")


class MonitoringEvaluator(Protocol):
    """Minimal monitoring evaluator interface for generation service framework."""

    def evaluate(
        self,
        risk_artifact: RiskArtifact,
        context: RiskMonitoringContext,
        monitoring_artifact_id: str,
    ) -> MonitoringEvaluationOutput:
        ...
