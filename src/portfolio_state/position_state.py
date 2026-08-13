from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from decimal import InvalidOperation
from enum import StrEnum

from portfolio_state.validation import PortfolioStateValidationError


class HoldingType(StrEnum):
    """Supported portfolio state holding granularity."""

    WHOLE_SHARE = "whole_share"
    FRACTIONAL_SHARE = "fractional_share"


class PositionStatus(StrEnum):
    """Portfolio position lifecycle state preserved by snapshots."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    IGNORED = "IGNORED"


class PortfolioPositionStateError(PortfolioStateValidationError):
    """Raised when portfolio position state is invalid."""


@dataclass(frozen=True)
class PortfolioPositionState:
    """Immutable portfolio state contract for one position."""

    portfolio_id: str
    position_id: str
    symbol: str
    shares: Decimal | int | str
    average_cost: Decimal | int | str
    currency: str
    position_status: PositionStatus | str
    holding_type: HoldingType | str
    acquisition_date: date

    def __post_init__(self):
        required = {
            "portfolio_id": self.portfolio_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "currency": self.currency,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise PortfolioPositionStateError(
                f"PortfolioPositionState missing required fields: {', '.join(missing)}"
            )

        shares = self._coerce_decimal(self.shares, "shares")
        average_cost = self._coerce_decimal(self.average_cost, "average_cost")
        if shares <= Decimal("0"):
            raise PortfolioPositionStateError("PortfolioPositionState shares must be positive.")
        if average_cost < Decimal("0"):
            raise PortfolioPositionStateError("PortfolioPositionState average_cost cannot be negative.")
        if not isinstance(self.acquisition_date, date):
            raise PortfolioPositionStateError("PortfolioPositionState acquisition_date must be a date.")

        currency = self.currency.upper()
        if len(currency) != 3 or not currency.isalpha():
            raise PortfolioPositionStateError("PortfolioPositionState currency must be a three-letter code.")

        try:
            position_status = PositionStatus(self.position_status)
        except ValueError as exc:
            raise PortfolioPositionStateError(
                f"Invalid PortfolioPositionState position_status: {self.position_status}"
            ) from exc
        try:
            holding_type = HoldingType(self.holding_type)
        except ValueError as exc:
            raise PortfolioPositionStateError(
                f"Invalid PortfolioPositionState holding_type: {self.holding_type}"
            ) from exc

        if holding_type == HoldingType.WHOLE_SHARE and shares != shares.to_integral_value():
            raise PortfolioPositionStateError("Whole-share position requires integer shares.")

        object.__setattr__(self, "shares", shares)
        object.__setattr__(self, "average_cost", average_cost)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "position_status", position_status)
        object.__setattr__(self, "holding_type", holding_type)

    @property
    def identity(self) -> dict[str, object]:
        return {
            "portfolio_id": self.portfolio_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "shares": self._decimal_text(self.shares),
            "average_cost": self._decimal_text(self.average_cost),
            "currency": self.currency,
            "position_status": self.position_status.value,
            "holding_type": self.holding_type.value,
            "acquisition_date": self.acquisition_date.isoformat(),
        }

    def _coerce_decimal(self, value: Decimal | int | str, field_name: str) -> Decimal:
        if isinstance(value, bool):
            raise PortfolioPositionStateError(
                f"PortfolioPositionState {field_name} must use Decimal-compatible precision."
            )
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation as exc:
                raise PortfolioPositionStateError(
                    f"PortfolioPositionState {field_name} must be Decimal-compatible."
                ) from exc
        raise PortfolioPositionStateError(f"PortfolioPositionState {field_name} must use Decimal.")

    def _decimal_text(self, value: Decimal) -> str:
        return format(value, "f")
