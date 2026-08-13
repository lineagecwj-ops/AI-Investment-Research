from dataclasses import dataclass
from datetime import datetime
from typing import Any

from risk.portfolio_position import PortfolioPosition
from risk.risk_assessment import RiskAssessment
from risk.risk_context import RiskContext
from risk.risk_signal import RiskSignal


@dataclass(frozen=True)
class RiskArtifact:
    """Metadata-only portfolio risk artifact."""

    artifact_id: str
    position_identity: dict[str, object]
    risk_assessment: RiskAssessment
    signals: tuple[RiskSignal, ...]
    feature_lineage: dict[str, Any]
    calculation_metadata: dict[str, Any]
    created_at: datetime
    checksum: str | None = None

    def __post_init__(self):
        if not self.artifact_id:
            raise ValueError("RiskArtifact requires artifact_id.")
        if not self.position_identity:
            raise ValueError("RiskArtifact requires position_identity.")
        if not isinstance(self.risk_assessment, RiskAssessment):
            raise ValueError("RiskArtifact requires risk_assessment.")
        if not isinstance(self.signals, tuple):
            raise ValueError("RiskArtifact signals must be a tuple.")
        if not self.feature_lineage:
            raise ValueError("RiskArtifact requires feature_lineage.")
        if not self.calculation_metadata:
            raise ValueError("RiskArtifact requires calculation_metadata.")
        if not isinstance(self.created_at, datetime):
            raise ValueError("RiskArtifact created_at must be a datetime.")


class RiskArtifactGenerator:
    """Build reproducible risk artifact metadata without persistence."""

    def generate(
        self,
        artifact_id: str,
        position: PortfolioPosition,
        context: RiskContext,
        assessment: RiskAssessment,
        created_at: datetime,
        checksum: str | None = None,
    ) -> RiskArtifact:
        return RiskArtifact(
            artifact_id=artifact_id,
            position_identity=position.identity,
            risk_assessment=assessment,
            signals=assessment.signals,
            feature_lineage={
                "feature_version": context.feature_version,
                "model_version": context.model_version,
            },
            calculation_metadata={
                "portfolio_id": context.portfolio_id,
                "symbol": context.symbol,
                "analysis_date": context.analysis_date.isoformat(),
                "calculation_id": context.calculation_id,
            },
            created_at=created_at,
            checksum=checksum,
        )
