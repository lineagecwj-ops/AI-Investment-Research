from risk import RiskArtifact
from risk_monitoring import RiskMonitoringContext

from portfolio_generation.validation import MonitoringContextBuilderError
from portfolio_state import PortfolioPositionState
from portfolio_state import PositionStatus
from portfolio_state import RiskEvaluationInput


def build_monitoring_context(
    risk_artifact: RiskArtifact,
    evaluation_input: RiskEvaluationInput,
    position: PortfolioPositionState,
) -> RiskMonitoringContext:
    """Build monitoring context with business monitoring_date from evaluation as_of_date."""

    _validate_inputs(risk_artifact, evaluation_input, position)
    try:
        return RiskMonitoringContext(
            portfolio_id=evaluation_input.portfolio_id,
            symbol=position.symbol,
            monitoring_date=evaluation_input.as_of_date,
            source_risk_artifact_id=risk_artifact.artifact_id,
            risk_artifact_checksum=risk_artifact.checksum,
            monitoring_policy_version=evaluation_input.monitoring_policy_version,
            calculation_id=evaluation_input.calculation_id,
        )
    except ValueError as exc:
        raise MonitoringContextBuilderError(str(exc)) from exc


def _validate_inputs(
    risk_artifact: RiskArtifact,
    evaluation_input: RiskEvaluationInput,
    position: PortfolioPositionState,
) -> None:
    if not isinstance(risk_artifact, RiskArtifact):
        raise MonitoringContextBuilderError("MonitoringContext builder requires RiskArtifact.")
    if not isinstance(evaluation_input, RiskEvaluationInput):
        raise MonitoringContextBuilderError("MonitoringContext builder requires RiskEvaluationInput.")
    if not isinstance(position, PortfolioPositionState):
        raise MonitoringContextBuilderError("MonitoringContext builder requires PortfolioPositionState.")
    if position.portfolio_id != evaluation_input.portfolio_id:
        raise MonitoringContextBuilderError("PortfolioPositionState portfolio_id does not match RiskEvaluationInput.")
    if position.position_id not in evaluation_input.active_position_ids:
        raise MonitoringContextBuilderError("PortfolioPositionState position_id is not in active evaluation scope.")
    if position.position_status != PositionStatus.ACTIVE:
        raise MonitoringContextBuilderError("PortfolioPositionState must be ACTIVE for monitoring context.")
    if risk_artifact.risk_assessment.portfolio_id != evaluation_input.portfolio_id:
        raise MonitoringContextBuilderError("RiskArtifact portfolio_id does not match RiskEvaluationInput.")
    if risk_artifact.risk_assessment.symbol != position.symbol:
        raise MonitoringContextBuilderError("RiskArtifact symbol does not match PortfolioPositionState.")
    if risk_artifact.calculation_metadata.get("calculation_id") != evaluation_input.calculation_id:
        raise MonitoringContextBuilderError("RiskArtifact calculation_id does not match RiskEvaluationInput.")
    if not risk_artifact.checksum:
        raise MonitoringContextBuilderError("RiskArtifact checksum is required for monitoring context.")
