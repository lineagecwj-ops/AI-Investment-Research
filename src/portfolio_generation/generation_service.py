from dataclasses import dataclass

from portfolio_generation.artifact_identity import build_monitoring_artifact_id
from portfolio_generation.artifact_identity import build_risk_artifact_id
from portfolio_generation.evaluator import RiskEvaluationOutput
from portfolio_generation.evaluator import RiskEvaluator
from portfolio_generation.generation_result import PortfolioPositionGenerationResult
from portfolio_generation.generation_result import PortfolioRiskGenerationResult
from portfolio_generation.generation_result import PortfolioRiskGenerationStatus
from portfolio_generation.monitoring_context_builder import build_monitoring_context
from portfolio_generation.monitoring_evaluator import MonitoringEvaluationOutput
from portfolio_generation.monitoring_evaluator import MonitoringEvaluator
from portfolio_generation.policy_resolver import ExactVersionPolicyResolver
from portfolio_generation.position_adapter import adapt_position_state
from portfolio_generation.position_adapter import resolve_active_position
from portfolio_generation.risk_context_builder import build_risk_context
from portfolio_generation.validation import MonitoringContextBuilderError
from portfolio_generation.validation import PolicyResolverError
from portfolio_generation.validation import PortfolioGenerationValidationError
from portfolio_generation.validation import PositionAdapterError
from portfolio_generation.validation import RiskContextBuilderError
from portfolio_state import PortfolioSnapshot
from portfolio_state import RiskEvaluationInput


@dataclass(frozen=True)
class PortfolioRiskGenerationService:
    """Orchestrate deterministic generation flow without real engine or writer coupling."""

    risk_evaluator: RiskEvaluator
    monitoring_evaluator: MonitoringEvaluator
    policy_resolver: ExactVersionPolicyResolver
    risk_definition_ids: tuple[str, ...] = ()

    def generate(
        self,
        snapshot: PortfolioSnapshot,
        evaluation_input: RiskEvaluationInput,
    ) -> PortfolioRiskGenerationResult:
        if not isinstance(snapshot, PortfolioSnapshot) or not isinstance(evaluation_input, RiskEvaluationInput):
            return self._failure_result(
                evaluation_input=evaluation_input,
                status=PortfolioRiskGenerationStatus.VALIDATION_FAILED,
                errors=("PortfolioRiskGenerationService requires PortfolioSnapshot and RiskEvaluationInput.",),
            )

        policy_error = self._validate_policies(evaluation_input)
        if policy_error is not None:
            return self._failure_result(
                evaluation_input=evaluation_input,
                status=PortfolioRiskGenerationStatus.VALIDATION_FAILED,
                errors=(policy_error,),
            )

        attempted: list[str] = []
        succeeded: list[str] = []
        position_results: list[PortfolioPositionGenerationResult] = []
        warnings: list[str] = []

        for position_id in self._position_processing_order(snapshot, evaluation_input):
            attempted.append(position_id)
            risk_artifact_id = build_risk_artifact_id(evaluation_input.calculation_id, position_id)
            monitoring_artifact_id = build_monitoring_artifact_id(evaluation_input.calculation_id, position_id)
            try:
                position = resolve_active_position(snapshot, evaluation_input, position_id)
                risk_position = adapt_position_state(position, evaluation_input)
                risk_context = build_risk_context(evaluation_input, position)
            except (PositionAdapterError, RiskContextBuilderError) as exc:
                return self._position_failure_result(
                    evaluation_input=evaluation_input,
                    status=PortfolioRiskGenerationStatus.VALIDATION_FAILED,
                    attempted=tuple(attempted),
                    succeeded=tuple(succeeded),
                    failed_position_id=position_id,
                    position_results=tuple(position_results),
                    symbol=self._symbol_for_position(snapshot, position_id),
                    risk_artifact_id=risk_artifact_id,
                    monitoring_artifact_id=monitoring_artifact_id,
                    error=str(exc),
                )

            try:
                risk_output = getattr(self.risk_evaluator, "evaluate")(risk_position, risk_context, risk_artifact_id)
                self._validate_risk_output(risk_output, position_id, position.symbol)
            except Exception as exc:
                return self._position_failure_result(
                    evaluation_input=evaluation_input,
                    status=PortfolioRiskGenerationStatus.RISK_EVALUATION_FAILED,
                    attempted=tuple(attempted),
                    succeeded=tuple(succeeded),
                    failed_position_id=position_id,
                    position_results=tuple(position_results),
                    symbol=position.symbol,
                    risk_artifact_id=risk_artifact_id,
                    monitoring_artifact_id=monitoring_artifact_id,
                    error=str(exc),
                )

            try:
                monitoring_context = build_monitoring_context(risk_output.risk_artifact, evaluation_input, position)
                monitoring_output = getattr(self.monitoring_evaluator, "evaluate")(
                    risk_output.risk_artifact,
                    monitoring_context,
                    monitoring_artifact_id,
                )
                self._validate_monitoring_output(monitoring_output, position_id, position.symbol)
            except Exception as exc:
                return self._position_failure_result(
                    evaluation_input=evaluation_input,
                    status=PortfolioRiskGenerationStatus.MONITORING_FAILED,
                    attempted=tuple(attempted),
                    succeeded=tuple(succeeded),
                    failed_position_id=position_id,
                    position_results=tuple(position_results),
                    symbol=position.symbol,
                    risk_artifact_id=risk_artifact_id,
                    monitoring_artifact_id=monitoring_artifact_id,
                    error=str(exc),
                )

            succeeded.append(position_id)
            position_warnings = risk_output.warnings + monitoring_output.warnings
            warnings.extend(position_warnings)
            position_results.append(
                PortfolioPositionGenerationResult(
                    position_id=position_id,
                    symbol=position.symbol,
                    risk_artifact_id=risk_artifact_id,
                    monitoring_artifact_id=monitoring_artifact_id,
                    status=PortfolioRiskGenerationStatus.SUCCESS,
                    warnings=position_warnings,
                )
            )

        return PortfolioRiskGenerationResult(
            status=PortfolioRiskGenerationStatus.SUCCESS,
            generation_key=evaluation_input.generation_key,
            calculation_id=evaluation_input.calculation_id,
            portfolio_id=evaluation_input.portfolio_id,
            snapshot_id=evaluation_input.snapshot_id,
            attempted_position_ids=tuple(attempted),
            succeeded_position_ids=tuple(succeeded),
            failed_position_ids=(),
            position_results=tuple(position_results),
            errors=(),
            warnings=tuple(warnings),
        )

    def _validate_policies(self, evaluation_input: RiskEvaluationInput) -> str | None:
        try:
            self.policy_resolver.resolve_risk_policy_version(evaluation_input.risk_policy_version)
            self.policy_resolver.resolve_monitoring_policy_version(evaluation_input.monitoring_policy_version)
            for risk_definition_id in self.risk_definition_ids:
                self.policy_resolver.resolve_risk_definition(
                    risk_definition_id,
                    evaluation_input.risk_definition_version,
                )
        except PolicyResolverError as exc:
            return str(exc)
        return None

    def _position_processing_order(
        self,
        snapshot: PortfolioSnapshot,
        evaluation_input: RiskEvaluationInput,
    ) -> tuple[str, ...]:
        position_lookup = {position.position_id: position for position in snapshot.positions}
        return tuple(
            position_id
            for position_id, _symbol in sorted(
                (
                    (position_id, position_lookup[position_id].symbol if position_id in position_lookup else "")
                    for position_id in evaluation_input.active_position_ids
                ),
                key=lambda item: (item[0], item[1]),
            )
        )

    def _position_failure_result(
        self,
        *,
        evaluation_input: RiskEvaluationInput,
        status: PortfolioRiskGenerationStatus,
        attempted: tuple[str, ...],
        succeeded: tuple[str, ...],
        failed_position_id: str,
        position_results: tuple[PortfolioPositionGenerationResult, ...],
        symbol: str,
        risk_artifact_id: str,
        monitoring_artifact_id: str,
        error: str,
    ) -> PortfolioRiskGenerationResult:
        failed_result = PortfolioPositionGenerationResult(
            position_id=failed_position_id,
            symbol=symbol or "UNKNOWN",
            risk_artifact_id=risk_artifact_id,
            monitoring_artifact_id=monitoring_artifact_id,
            status=status,
            diagnostics=(error,),
        )
        return PortfolioRiskGenerationResult(
            status=status,
            generation_key=evaluation_input.generation_key,
            calculation_id=evaluation_input.calculation_id,
            portfolio_id=evaluation_input.portfolio_id,
            snapshot_id=evaluation_input.snapshot_id,
            attempted_position_ids=attempted,
            succeeded_position_ids=succeeded,
            failed_position_ids=(failed_position_id,),
            position_results=position_results + (failed_result,),
            errors=(error,),
            warnings=(),
        )

    def _failure_result(
        self,
        *,
        evaluation_input: object,
        status: PortfolioRiskGenerationStatus,
        errors: tuple[str, ...],
    ) -> PortfolioRiskGenerationResult:
        if isinstance(evaluation_input, RiskEvaluationInput):
            generation_key = evaluation_input.generation_key
            calculation_id = evaluation_input.calculation_id
            portfolio_id = evaluation_input.portfolio_id
            snapshot_id = evaluation_input.snapshot_id
        else:
            generation_key = "UNKNOWN"
            calculation_id = "UNKNOWN"
            portfolio_id = "UNKNOWN"
            snapshot_id = "UNKNOWN"
        return PortfolioRiskGenerationResult(
            status=status,
            generation_key=generation_key,
            calculation_id=calculation_id,
            portfolio_id=portfolio_id,
            snapshot_id=snapshot_id,
            attempted_position_ids=(),
            succeeded_position_ids=(),
            failed_position_ids=(),
            position_results=(),
            errors=errors,
            warnings=(),
        )

    def _validate_risk_output(self, output: object, position_id: str, symbol: str) -> None:
        if not isinstance(output, RiskEvaluationOutput):
            raise PortfolioGenerationValidationError("Risk evaluator returned invalid output.")
        if output.position_id != position_id:
            raise PortfolioGenerationValidationError("Risk evaluator position_id mismatch.")
        if output.symbol != symbol:
            raise PortfolioGenerationValidationError("Risk evaluator symbol mismatch.")

    def _validate_monitoring_output(self, output: object, position_id: str, symbol: str) -> None:
        if not isinstance(output, MonitoringEvaluationOutput):
            raise MonitoringContextBuilderError("Monitoring evaluator returned invalid output.")
        if output.position_id != position_id:
            raise MonitoringContextBuilderError("Monitoring evaluator position_id mismatch.")
        if output.symbol != symbol:
            raise MonitoringContextBuilderError("Monitoring evaluator symbol mismatch.")

    def _symbol_for_position(self, snapshot: PortfolioSnapshot, position_id: str) -> str:
        for position in snapshot.positions:
            if position.position_id == position_id:
                return position.symbol
        return ""
