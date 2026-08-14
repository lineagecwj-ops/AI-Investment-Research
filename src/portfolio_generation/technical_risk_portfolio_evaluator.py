from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from portfolio_generation.artifact_identity import build_risk_artifact_id
from portfolio_generation.evaluator import RiskEvaluationOutput
from portfolio_generation.technical_risk_artifact_adapter import TechnicalRiskArtifactAdapter
from risk import PortfolioPosition
from risk import RiskContext
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import TechnicalRiskProductionService


class TechnicalRiskPortfolioEvaluatorError(ValueError):
    """Raised when Technical Risk cannot be evaluated through the portfolio seam."""


@runtime_checkable
class TechnicalRiskProductionInputProvider(Protocol):
    """Resolve caller-prepared Technical Risk production input without fetching or calculating data."""

    def resolve(
        self,
        position: PortfolioPosition,
        context: RiskContext,
        risk_artifact_id: str,
    ) -> RiskSignalProductionInput:
        ...


@dataclass(frozen=True)
class TechnicalRiskPortfolioEvaluator:
    """Bridge existing portfolio generation RiskEvaluator seam into Technical Risk production."""

    input_provider: TechnicalRiskProductionInputProvider
    policy: ProductionTechnicalRiskPolicy
    created_at: datetime
    production_service: TechnicalRiskProductionService = field(default_factory=TechnicalRiskProductionService)
    artifact_adapter: TechnicalRiskArtifactAdapter = field(default_factory=TechnicalRiskArtifactAdapter)

    def __post_init__(self):
        if not isinstance(self.policy, ProductionTechnicalRiskPolicy):
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator requires ProductionTechnicalRiskPolicy.")
        self._require_timezone_aware_created_at(self.created_at)
        if not hasattr(self.input_provider, "resolve"):
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator requires input provider.")
        if not hasattr(self.production_service, "run"):
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator requires production service.")
        if not hasattr(self.artifact_adapter, "build"):
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator requires artifact adapter.")

    def evaluate(
        self,
        position: PortfolioPosition,
        context: RiskContext,
        risk_artifact_id: str,
    ) -> RiskEvaluationOutput:
        self._validate_evaluate_inputs(position, context, risk_artifact_id)
        production_input = self._resolve_input(position, context, risk_artifact_id)
        self._validate_production_input(production_input, position, context, risk_artifact_id)

        try:
            production_result = self.production_service.run(
                input=production_input,
                policy=self.policy,
                created_at=self.created_at,
            )
        except Exception as exc:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production service failed.") from exc

        try:
            risk_artifact = self.artifact_adapter.build(
                result=production_result,
                context=context,
                position=position,
                artifact_id=risk_artifact_id,
                created_at=self.created_at,
            )
        except Exception as exc:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk artifact adapter failed.") from exc

        try:
            return RiskEvaluationOutput(
                position_id=production_input.position_id,
                symbol=production_input.symbol,
                risk_artifact=risk_artifact,
            )
        except Exception as exc:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk RiskEvaluationOutput construction failed.") from exc

    def _resolve_input(
        self,
        position: PortfolioPosition,
        context: RiskContext,
        risk_artifact_id: str,
    ) -> RiskSignalProductionInput:
        try:
            production_input = self.input_provider.resolve(position, context, risk_artifact_id)
        except Exception as exc:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input provider failed.") from exc
        if not isinstance(production_input, RiskSignalProductionInput):
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input provider returned invalid output.")
        return production_input

    def _validate_evaluate_inputs(
        self,
        position: object,
        context: object,
        risk_artifact_id: object,
    ) -> None:
        if not isinstance(position, PortfolioPosition):
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator requires PortfolioPosition.")
        if not isinstance(context, RiskContext):
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator requires RiskContext.")
        if not isinstance(risk_artifact_id, str) or not risk_artifact_id:
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator requires risk_artifact_id.")

    def _validate_production_input(
        self,
        production_input: RiskSignalProductionInput,
        position: PortfolioPosition,
        context: RiskContext,
        risk_artifact_id: str,
    ) -> None:
        if production_input.portfolio_id != context.portfolio_id:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input portfolio_id mismatch.")
        if production_input.symbol != context.symbol or production_input.symbol != position.symbol:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input symbol mismatch.")
        if production_input.calculation_id != context.calculation_id:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input calculation_id mismatch.")
        if production_input.as_of_date != context.analysis_date:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input as_of_date mismatch.")
        if production_input.feature_version != context.feature_version:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input feature_version mismatch.")
        if production_input.model_version != context.model_version:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input model_version mismatch.")
        expected_artifact_id = build_risk_artifact_id(context.calculation_id, production_input.position_id)
        if expected_artifact_id != risk_artifact_id:
            raise TechnicalRiskPortfolioEvaluatorError("Technical Risk production input position_id artifact mismatch.")

    def _require_timezone_aware_created_at(self, created_at: object) -> None:
        if not isinstance(created_at, datetime):
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator created_at must be a datetime.")
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise TechnicalRiskPortfolioEvaluatorError("TechnicalRiskPortfolioEvaluator created_at must be timezone-aware.")
