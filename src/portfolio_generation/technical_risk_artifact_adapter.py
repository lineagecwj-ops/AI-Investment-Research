from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import datetime

from risk import PortfolioPosition
from risk import RiskArtifact
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskChecksumGenerator
from risk import RiskContext
from risk import RiskSeverity
from risk_evaluation import ProducedRiskSignal
from risk_evaluation import TechnicalRiskProductionResult


class TechnicalRiskArtifactAdapterError(ValueError):
    """Raised when Technical Risk production output cannot become a RiskArtifact."""


@dataclass(frozen=True)
class TechnicalRiskArtifactAdapter:
    """Adapt one Technical Risk production result into the existing RiskArtifact contract."""

    checksum_generator: RiskChecksumGenerator = field(default_factory=RiskChecksumGenerator)

    def build(
        self,
        result: TechnicalRiskProductionResult,
        context: RiskContext,
        position: PortfolioPosition,
        artifact_id: str,
        created_at: datetime,
    ) -> RiskArtifact:
        self._validate_inputs(result, context, position, artifact_id, created_at)
        produced_signal = result.produced_signal
        assessment = result.risk_assessment

        artifact = RiskArtifact(
            artifact_id=artifact_id,
            position_identity=position.identity,
            risk_assessment=assessment,
            signals=assessment.signals,
            feature_lineage=self._feature_lineage(context, produced_signal),
            calculation_metadata=self._calculation_metadata(context, produced_signal),
            created_at=created_at,
        )
        try:
            checksum = self.checksum_generator.generate(artifact, context)
        except Exception as exc:
            raise TechnicalRiskArtifactAdapterError("Technical Risk artifact checksum generation failed.") from exc
        return replace(artifact, checksum=checksum)

    def _validate_inputs(
        self,
        result: object,
        context: object,
        position: object,
        artifact_id: object,
        created_at: object,
    ) -> None:
        if not isinstance(result, TechnicalRiskProductionResult):
            raise TechnicalRiskArtifactAdapterError("TechnicalRiskArtifactAdapter requires TechnicalRiskProductionResult.")
        if not isinstance(context, RiskContext):
            raise TechnicalRiskArtifactAdapterError("TechnicalRiskArtifactAdapter requires RiskContext.")
        if not isinstance(position, PortfolioPosition):
            raise TechnicalRiskArtifactAdapterError("TechnicalRiskArtifactAdapter requires PortfolioPosition.")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise TechnicalRiskArtifactAdapterError("TechnicalRiskArtifactAdapter requires artifact_id.")
        self._require_timezone_aware_created_at(created_at)

        produced_signal = result.produced_signal
        assessment = result.risk_assessment
        if not isinstance(produced_signal, ProducedRiskSignal):
            raise TechnicalRiskArtifactAdapterError("Technical Risk result requires ProducedRiskSignal.")
        if not isinstance(assessment, RiskAssessment):
            raise TechnicalRiskArtifactAdapterError("Technical Risk result requires RiskAssessment.")
        if assessment.signals != (produced_signal.signal,):
            raise TechnicalRiskArtifactAdapterError("RiskAssessment must contain the produced RiskSignal exactly once.")
        if produced_signal.signal.category != RiskCategory.TECHNICAL:
            raise TechnicalRiskArtifactAdapterError("Technical Risk artifact requires TECHNICAL signal category.")
        if produced_signal.signal.severity == RiskSeverity.CRITICAL:
            raise TechnicalRiskArtifactAdapterError("Technical Risk v1 artifact cannot preserve CRITICAL severity.")

        self._validate_required_lineage(produced_signal)
        if produced_signal.portfolio_id != context.portfolio_id:
            raise TechnicalRiskArtifactAdapterError("Technical Risk portfolio_id mismatch.")
        if produced_signal.signal.symbol != context.symbol:
            raise TechnicalRiskArtifactAdapterError("Technical Risk symbol mismatch.")
        if produced_signal.signal.symbol != position.symbol:
            raise TechnicalRiskArtifactAdapterError("Technical Risk position symbol mismatch.")
        if produced_signal.calculation_id != context.calculation_id:
            raise TechnicalRiskArtifactAdapterError("Technical Risk calculation_id mismatch.")
        if produced_signal.as_of_date != context.analysis_date:
            raise TechnicalRiskArtifactAdapterError("Technical Risk as_of_date must match RiskContext analysis_date.")
        if assessment.portfolio_id != context.portfolio_id:
            raise TechnicalRiskArtifactAdapterError("Technical Risk assessment portfolio_id mismatch.")
        if assessment.symbol != context.symbol:
            raise TechnicalRiskArtifactAdapterError("Technical Risk assessment symbol mismatch.")
        if assessment.assessment_date != context.analysis_date:
            raise TechnicalRiskArtifactAdapterError("Technical Risk assessment_date mismatch.")
        if assessment.overall_risk_level != produced_signal.signal.severity:
            raise TechnicalRiskArtifactAdapterError("Technical Risk assessment severity mismatch.")

    def _validate_required_lineage(self, produced_signal: ProducedRiskSignal) -> None:
        required_text_fields = (
            "policy_id",
            "policy_version",
            "policy_checksum",
            "evaluation_id",
            "evaluation_checksum",
            "producer_version",
            "portfolio_id",
            "position_id",
            "calculation_id",
        )
        for field_name in required_text_fields:
            value = getattr(produced_signal, field_name)
            if not isinstance(value, str) or not value:
                raise TechnicalRiskArtifactAdapterError(f"Technical Risk produced signal missing {field_name}.")
        if produced_signal.as_of_date is None:
            raise TechnicalRiskArtifactAdapterError("Technical Risk produced signal missing as_of_date.")
        if produced_signal.valuation_date is None:
            raise TechnicalRiskArtifactAdapterError("Technical Risk produced signal missing valuation_date.")
        if not produced_signal.source_feature_ids:
            raise TechnicalRiskArtifactAdapterError("Technical Risk produced signal missing source_feature_ids.")
        if not produced_signal.source_checksums:
            raise TechnicalRiskArtifactAdapterError("Technical Risk produced signal missing source_checksums.")
        if len(produced_signal.source_feature_ids) != len(produced_signal.source_checksums):
            raise TechnicalRiskArtifactAdapterError("Technical Risk source feature/checksum lineage mismatch.")

    def _feature_lineage(self, context: RiskContext, produced_signal: ProducedRiskSignal) -> dict[str, object]:
        return {
            "feature_version": context.feature_version,
            "model_version": context.model_version,
            "technical_source_feature_ids": produced_signal.source_feature_ids,
            "technical_source_checksums": produced_signal.source_checksums,
        }

    def _calculation_metadata(self, context: RiskContext, produced_signal: ProducedRiskSignal) -> dict[str, object]:
        return {
            "portfolio_id": context.portfolio_id,
            "symbol": context.symbol,
            "analysis_date": context.analysis_date.isoformat(),
            "calculation_id": context.calculation_id,
            "technical_policy_id": produced_signal.policy_id,
            "technical_policy_version": produced_signal.policy_version,
            "technical_policy_checksum": produced_signal.policy_checksum,
            "technical_evaluation_id": produced_signal.evaluation_id,
            "technical_evaluation_checksum": produced_signal.evaluation_checksum,
            "technical_position_id": produced_signal.position_id,
            "technical_as_of_date": produced_signal.as_of_date.isoformat(),
            "technical_valuation_date": produced_signal.valuation_date.isoformat(),
            "technical_calculation_id": produced_signal.calculation_id,
            "technical_producer_version": produced_signal.producer_version,
        }

    def _require_timezone_aware_created_at(self, created_at: object) -> None:
        if not isinstance(created_at, datetime):
            raise TechnicalRiskArtifactAdapterError("TechnicalRiskArtifactAdapter created_at must be a datetime.")
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise TechnicalRiskArtifactAdapterError("TechnicalRiskArtifactAdapter created_at must be timezone-aware.")
