from risk import HoldingType as RiskHoldingType
from risk import PortfolioPosition

from portfolio_generation.validation import PositionAdapterError
from portfolio_state import HoldingType as PortfolioHoldingType
from portfolio_state import PortfolioPositionState
from portfolio_state import PortfolioSnapshot
from portfolio_state import PositionStatus
from portfolio_state import RiskEvaluationInput


HOLDING_TYPE_MAPPING = {
    PortfolioHoldingType.WHOLE_SHARE: RiskHoldingType.WHOLE_SHARE,
    PortfolioHoldingType.FRACTIONAL_SHARE: RiskHoldingType.FRACTIONAL_SHARE,
}


def resolve_active_position(
    snapshot: PortfolioSnapshot,
    evaluation_input: RiskEvaluationInput,
    position_id: str,
) -> PortfolioPositionState:
    """Resolve a caller-selected ACTIVE position without recalculating scope."""

    _validate_snapshot_input_pair(snapshot, evaluation_input)
    if position_id not in evaluation_input.active_position_ids:
        raise PositionAdapterError(f"Position is not in RiskEvaluationInput active scope: {position_id}")

    matches = tuple(position for position in snapshot.positions if position.position_id == position_id)
    if not matches:
        raise PositionAdapterError(f"Active position missing from snapshot: {position_id}")
    if len(matches) > 1:
        raise PositionAdapterError(f"Duplicate position_id in snapshot: {position_id}")
    return matches[0]


def adapt_position_state(
    position: PortfolioPositionState,
    evaluation_input: RiskEvaluationInput,
) -> PortfolioPosition:
    """Adapt explicit portfolio state into the existing Risk Engine position model."""

    _validate_position_for_evaluation(position, evaluation_input)
    if not isinstance(position.holding_type, PortfolioHoldingType):
        raise PositionAdapterError(f"Unsupported portfolio holding_type: {position.holding_type}")
    try:
        risk_holding_type = HOLDING_TYPE_MAPPING[position.holding_type]
    except KeyError as exc:
        raise PositionAdapterError(f"Unsupported portfolio holding_type: {position.holding_type}") from exc

    try:
        return PortfolioPosition(
            symbol=position.symbol,
            shares=position.shares,
            average_cost=position.average_cost,
            holding_type=risk_holding_type,
            acquisition_date=position.acquisition_date,
            currency=position.currency,
        )
    except ValueError as exc:
        raise PositionAdapterError(str(exc)) from exc


def _validate_snapshot_input_pair(snapshot: PortfolioSnapshot, evaluation_input: RiskEvaluationInput) -> None:
    if not isinstance(snapshot, PortfolioSnapshot):
        raise PositionAdapterError("Position adapter requires PortfolioSnapshot input.")
    if not isinstance(evaluation_input, RiskEvaluationInput):
        raise PositionAdapterError("Position adapter requires RiskEvaluationInput input.")
    if snapshot.portfolio_id != evaluation_input.portfolio_id:
        raise PositionAdapterError("PortfolioSnapshot portfolio_id does not match RiskEvaluationInput.")
    if snapshot.snapshot_id != evaluation_input.snapshot_id:
        raise PositionAdapterError("PortfolioSnapshot snapshot_id does not match RiskEvaluationInput.")
    if snapshot.checksum != evaluation_input.snapshot_checksum:
        raise PositionAdapterError("PortfolioSnapshot checksum does not match RiskEvaluationInput.")


def _validate_position_for_evaluation(
    position: PortfolioPositionState,
    evaluation_input: RiskEvaluationInput,
) -> None:
    if not isinstance(position, PortfolioPositionState):
        raise PositionAdapterError("Position adapter requires PortfolioPositionState input.")
    if not isinstance(evaluation_input, RiskEvaluationInput):
        raise PositionAdapterError("Position adapter requires RiskEvaluationInput input.")
    if position.portfolio_id != evaluation_input.portfolio_id:
        raise PositionAdapterError("PortfolioPositionState portfolio_id does not match RiskEvaluationInput.")
    if position.position_id not in evaluation_input.active_position_ids:
        raise PositionAdapterError("PortfolioPositionState position_id is not in active evaluation scope.")
    if position.position_status != PositionStatus.ACTIVE:
        raise PositionAdapterError("PortfolioPositionState must be ACTIVE for risk evaluation.")
