from risk import RiskContext

from portfolio_generation.validation import RiskContextBuilderError
from portfolio_state import PortfolioPositionState
from portfolio_state import PositionStatus
from portfolio_state import RiskEvaluationInput


def build_risk_context(
    evaluation_input: RiskEvaluationInput,
    position: PortfolioPositionState,
) -> RiskContext:
    """Build deterministic RiskContext metadata without loading feature or market data."""

    if not isinstance(evaluation_input, RiskEvaluationInput):
        raise RiskContextBuilderError("RiskContext builder requires RiskEvaluationInput.")
    if not isinstance(position, PortfolioPositionState):
        raise RiskContextBuilderError("RiskContext builder requires PortfolioPositionState.")
    if position.portfolio_id != evaluation_input.portfolio_id:
        raise RiskContextBuilderError("PortfolioPositionState portfolio_id does not match RiskEvaluationInput.")
    if position.position_id not in evaluation_input.active_position_ids:
        raise RiskContextBuilderError("PortfolioPositionState position_id is not in active evaluation scope.")
    if position.position_status != PositionStatus.ACTIVE:
        raise RiskContextBuilderError("PortfolioPositionState must be ACTIVE for RiskContext.")

    try:
        return RiskContext(
            portfolio_id=evaluation_input.portfolio_id,
            symbol=position.symbol,
            analysis_date=evaluation_input.as_of_date,
            feature_version=evaluation_input.feature_version,
            calculation_id=evaluation_input.calculation_id,
            model_version=evaluation_input.model_version,
        )
    except ValueError as exc:
        raise RiskContextBuilderError(str(exc)) from exc
