from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from typing import Iterable

from targets.target_artifact import TargetArtifact
from targets.target_context import TargetCalculationContext
from targets.target_definition import TargetDefinition
from targets.target_generator import TargetGenerationOutput


VALIDATION_PASS = "PASS"
VALIDATION_INSUFFICIENT_FUTURE_DATA = "INSUFFICIENT_FUTURE_DATA"
VALIDATION_INVALID_PRICE = "INVALID_PRICE"


@dataclass(frozen=True)
class TargetPricePoint:
    symbol: str
    trading_date: date
    price: float | None


class _FutureReturnBase:
    target_id: str
    target_name: str
    target_type: str
    calculation_window: int
    formula_version: str
    description: str

    def __init__(self, price_series: Iterable[TargetPricePoint]):
        self._price_series = tuple(sorted(price_series, key=lambda point: (point.symbol, point.trading_date)))

    def get_definition(self) -> TargetDefinition:
        return TargetDefinition(
            target_id=self.target_id,
            target_name=self.target_name,
            target_type=self.target_type,
            version="v1",
            calculation_window=self.calculation_window,
            formula_version=self.formula_version,
            description=self.description,
        )

    def calculate(self, context: TargetCalculationContext) -> TargetGenerationOutput:
        if context.evaluation_window != self.calculation_window:
            return self._output(context, None, VALIDATION_INSUFFICIENT_FUTURE_DATA, {"reason": "window mismatch"})
        symbol_prices = tuple(point for point in self._price_series if point.symbol == context.symbol)
        reference_index = self._find_reference_index(symbol_prices, context.reference_date)
        if reference_index is None:
            return self._output(context, None, VALIDATION_INSUFFICIENT_FUTURE_DATA, {"reason": "missing reference price"})
        future_index = reference_index + self.calculation_window
        if future_index >= len(symbol_prices):
            return self._output(context, None, VALIDATION_INSUFFICIENT_FUTURE_DATA, {"reason": "missing future window"})
        reference = symbol_prices[reference_index]
        future = symbol_prices[future_index]
        if reference.price is None or future.price is None or reference.price <= 0 or future.price < 0:
            return self._output(context, None, VALIDATION_INVALID_PRICE, {"reason": "invalid price"})
        return_value = (future.price - reference.price) / reference.price
        target_value = self._target_value(return_value)
        return self._output(
            context,
            target_value,
            VALIDATION_PASS,
            {
                "reference_price": reference.price,
                "future_price": future.price,
                "future_date": future.trading_date.isoformat(),
                "return_value": return_value,
            },
        )

    def validate(self, output: TargetGenerationOutput) -> bool:
        return output.metadata is not None and output.metadata.get("validation_status") == VALIDATION_PASS

    def _target_value(self, return_value: float) -> float | str:
        return return_value

    def _find_reference_index(self, prices: tuple[TargetPricePoint, ...], reference_date: date) -> int | None:
        for index, point in enumerate(prices):
            if point.trading_date == reference_date:
                return index
        return None

    def _artifact(
        self,
        context: TargetCalculationContext,
        target_value: float | str | None,
        validation_status: str,
    ) -> TargetArtifact | None:
        if target_value is None:
            return None
        return TargetArtifact(
            target_id=self.target_id,
            target_version="v1",
            symbol=context.symbol,
            reference_date=context.reference_date,
            target_value=target_value,
            calculation_id=context.calculation_id,
            created_at=datetime.combine(context.reference_date, time.min, tzinfo=UTC),
            checksum=None,
            validation_status=validation_status,
        )

    def _output(
        self,
        context: TargetCalculationContext,
        target_value: float | str | None,
        validation_status: str,
        metadata: dict[str, object] | None = None,
    ) -> TargetGenerationOutput:
        output_metadata = {
            "snapshot_id": context.snapshot_id,
            "reference_date": context.reference_date.isoformat(),
            "calculation_id": context.calculation_id,
            "validation_status": validation_status,
        }
        if metadata:
            output_metadata.update(metadata)
        return TargetGenerationOutput(
            target_id=self.target_id,
            target_version="v1",
            symbol=context.symbol,
            reference_date=context.reference_date,
            target_value=target_value,
            metadata=output_metadata,
            artifact=self._artifact(context, target_value, validation_status),
        )


class FutureReturn20DRegressionGenerator(_FutureReturnBase):
    target_id = "TARGET_RETURN_20D_REG_V1"
    target_name = "20D Future Return"
    target_type = "Regression"
    calculation_window = 20
    formula_version = "future_return_20d_v1"
    description = "20 trading day future return calculated as (price_T20 - price_T0) / price_T0."


class FutureReturn60DRegressionGenerator(_FutureReturnBase):
    target_id = "TARGET_RETURN_60D_REG_V1"
    target_name = "60D Future Return"
    target_type = "Regression"
    calculation_window = 60
    formula_version = "future_return_60d_v1"
    description = "60 trading day future return calculated as (price_T60 - price_T0) / price_T0."


class FutureReturn60DClassificationGenerator(_FutureReturnBase):
    target_id = "TARGET_RETURN_60D_CLASS_V1"
    target_name = "60D Future Return Classification"
    target_type = "Classification"
    calculation_window = 60
    formula_version = "future_return_60d_class_v1"
    description = "60 trading day return class using fixed +/-5% thresholds."
    positive_threshold = 0.05
    negative_threshold = -0.05

    def _target_value(self, return_value: float) -> str:
        if return_value > self.positive_threshold:
            return "Positive"
        if return_value < self.negative_threshold:
            return "Negative"
        return "Neutral"
