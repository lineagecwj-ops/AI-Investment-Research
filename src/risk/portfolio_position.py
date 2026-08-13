from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from decimal import InvalidOperation
from enum import StrEnum


class HoldingType(StrEnum):
    """Supported portfolio holding granularity."""

    WHOLE_SHARE = "whole_share"
    FRACTIONAL_SHARE = "fractional_share"


class PortfolioPositionError(ValueError):
    """Raised when a portfolio position is invalid."""


@dataclass(frozen=True)
class PortfolioPosition:
    """Metadata-only position model for portfolio risk assessment."""

    symbol: str
    shares: Decimal | int | str
    average_cost: Decimal | int | str
    holding_type: HoldingType | str
    acquisition_date: date
    currency: str

    def __post_init__(self):
        if not self.symbol:
            raise PortfolioPositionError("PortfolioPosition requires symbol.")
        shares = self._coerce_decimal(self.shares, "shares")
        average_cost = self._coerce_decimal(self.average_cost, "average_cost")

        if shares <= Decimal("0"):
            raise PortfolioPositionError("PortfolioPosition shares must be positive.")
        if average_cost < Decimal("0"):
            raise PortfolioPositionError("PortfolioPosition average_cost cannot be negative.")
        if not self.currency:
            raise PortfolioPositionError("PortfolioPosition requires currency.")
        if not isinstance(self.acquisition_date, date):
            raise PortfolioPositionError("PortfolioPosition acquisition_date must be a date.")

        holding_type = HoldingType(self.holding_type)
        if holding_type == HoldingType.WHOLE_SHARE and shares != shares.to_integral_value():
            raise PortfolioPositionError("Whole-share position requires integer shares.")

        object.__setattr__(self, "holding_type", holding_type)
        object.__setattr__(self, "shares", shares)
        object.__setattr__(self, "average_cost", average_cost)

    @property
    def identity(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "shares": self.shares,
            "average_cost": self.average_cost,
            "holding_type": self.holding_type.value,
            "acquisition_date": self.acquisition_date.isoformat(),
            "currency": self.currency,
        }

    def _coerce_decimal(self, value: Decimal | int | str, field_name: str) -> Decimal:
        if isinstance(value, bool):
            raise PortfolioPositionError(f"PortfolioPosition {field_name} must use Decimal-compatible precision.")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation as exc:
                raise PortfolioPositionError(f"PortfolioPosition {field_name} must be Decimal-compatible.") from exc
        raise PortfolioPositionError(f"PortfolioPosition {field_name} must use Decimal.")
