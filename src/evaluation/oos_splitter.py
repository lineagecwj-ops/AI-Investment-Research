from dataclasses import dataclass
from datetime import date

from evaluation.evaluation_context import EvaluationContext


class OOSSplitError(Exception):
    """Raised when OOS split rules are invalid."""


@dataclass(frozen=True)
class OOSSplit:
    training_period: tuple[str, str]
    validation_period: tuple[str, str]
    oos_period: tuple[str, str]


class OOSSplitter:
    """Validates deterministic train, validation, and frozen OOS periods."""

    def split(self, context: EvaluationContext) -> OOSSplit:
        self.validate_ordering(context.training_period, context.validation_period, context.oos_period)
        return OOSSplit(
            training_period=context.training_period,
            validation_period=context.validation_period,
            oos_period=context.oos_period,
        )

    def validate_ordering(
        self,
        training_period: tuple[str, str],
        validation_period: tuple[str, str],
        oos_period: tuple[str, str],
    ) -> None:
        train_start, train_end = self._period_dates("training_period", training_period)
        val_start, val_end = self._period_dates("validation_period", validation_period)
        oos_start, oos_end = self._period_dates("oos_period", oos_period)
        if not train_start <= train_end < val_start <= val_end < oos_start <= oos_end:
            raise OOSSplitError("Periods must be ordered as training < validation < frozen OOS without overlap.")

    def reject_oos_contamination(self, tuned_period: str) -> None:
        if tuned_period == "oos":
            raise OOSSplitError("Frozen OOS period cannot be used for tuning.")

    def _period_dates(self, name: str, period: tuple[str, str]) -> tuple[date, date]:
        if len(period) != 2:
            raise OOSSplitError(f"{name} must contain start and end dates.")
        return date.fromisoformat(period[0]), date.fromisoformat(period[1])
