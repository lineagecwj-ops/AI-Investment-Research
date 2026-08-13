from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from numbers import Real
from typing import Iterable

from targets.target_artifact import TargetArtifact
from targets.target_artifact import TargetWindowLineage
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
    requires_window_lineage = True

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
            requires_window_lineage=self.requires_window_lineage,
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
        future_window = symbol_prices[reference_index + 1:future_index + 1]
        window_lineage = self._window_lineage(future_window)
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
                "future_window_start": window_lineage.target_start_date.isoformat(),
                "future_window_end": window_lineage.target_end_date.isoformat(),
                "window_observations": window_lineage.observations_used,
                "return_value": return_value,
            },
            window_lineage=window_lineage,
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
        window_lineage: TargetWindowLineage | None = None,
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
            window_lineage=window_lineage,
        )

    def _output(
        self,
        context: TargetCalculationContext,
        target_value: float | str | None,
        validation_status: str,
        metadata: dict[str, object] | None = None,
        window_lineage: TargetWindowLineage | None = None,
    ) -> TargetGenerationOutput:
        definition = self.get_definition()
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
            artifact=self._artifact(context, target_value, validation_status, window_lineage),
            window_lineage=window_lineage,
            requires_window_lineage=definition.requires_window_lineage,
            definition=definition,
        )

    def _window_lineage(self, future_window: tuple[TargetPricePoint, ...]) -> TargetWindowLineage:
        return TargetWindowLineage(
            target_start_date=future_window[0].trading_date,
            target_end_date=future_window[-1].trading_date,
            observations_used=len(future_window),
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


class _MaximumAdverseExcursionBase(_FutureReturnBase):
    def calculate(self, context: TargetCalculationContext) -> TargetGenerationOutput:
        if context.evaluation_window != self.calculation_window:
            return self._output(context, None, VALIDATION_INSUFFICIENT_FUTURE_DATA, {"reason": "window mismatch"})
        symbol_prices = tuple(point for point in self._price_series if point.symbol == context.symbol)
        duplicate_date = self._duplicate_date(symbol_prices)
        if duplicate_date is not None:
            return self._output(
                context,
                None,
                VALIDATION_INSUFFICIENT_FUTURE_DATA,
                {"reason": "duplicate trading_date", "duplicate_date": duplicate_date.isoformat()},
            )
        reference_index = self._find_reference_index(symbol_prices, context.reference_date)
        if reference_index is None:
            return self._output(context, None, VALIDATION_INSUFFICIENT_FUTURE_DATA, {"reason": "missing reference price"})
        reference = symbol_prices[reference_index]
        if not self._valid_price(reference.price):
            return self._output(context, None, VALIDATION_INVALID_PRICE, {"reason": "invalid reference price"})
        future_window = symbol_prices[reference_index + 1:reference_index + 1 + self.calculation_window]
        if len(future_window) != self.calculation_window:
            return self._output(context, None, VALIDATION_INSUFFICIENT_FUTURE_DATA, {"reason": "missing future window"})
        if any(point.price is None for point in future_window):
            return self._output(context, None, VALIDATION_INSUFFICIENT_FUTURE_DATA, {"reason": "missing future close"})
        invalid_future = next((point for point in future_window if not self._valid_price(point.price)), None)
        if invalid_future is not None:
            return self._output(
                context,
                None,
                VALIDATION_INVALID_PRICE,
                {"reason": "invalid future price", "future_date": invalid_future.trading_date.isoformat()},
            )
        future_returns = tuple(point.price / reference.price - 1 for point in future_window)
        raw_min_return = min(future_returns)
        target_value = min(0.0, raw_min_return)
        worst_index = future_returns.index(raw_min_return)
        worst_point = future_window[worst_index]
        window_lineage = self._window_lineage(future_window)
        return self._output(
            context,
            target_value,
            VALIDATION_PASS,
            {
                "reference_price": reference.price,
                "worst_future_price": worst_point.price,
                "worst_future_date": worst_point.trading_date.isoformat(),
                "future_window_start": window_lineage.target_start_date.isoformat(),
                "future_window_end": window_lineage.target_end_date.isoformat(),
                "window_observations": window_lineage.observations_used,
                "raw_min_return": raw_min_return,
                "formula": "min(0, min(future_close / reference_close - 1))",
            },
            window_lineage=window_lineage,
        )

    def _duplicate_date(self, prices: tuple[TargetPricePoint, ...]) -> date | None:
        seen: set[date] = set()
        for point in prices:
            if point.trading_date in seen:
                return point.trading_date
            seen.add(point.trading_date)
        return None

    def _valid_price(self, price: object) -> bool:
        return isinstance(price, Real) and not isinstance(price, bool) and price > 0


class MaximumAdverseExcursion20DRegressionGenerator(_MaximumAdverseExcursionBase):
    target_id = "TARGET_MAE_20D_REG_V1"
    target_name = "20D Maximum Adverse Excursion"
    target_type = "Regression"
    calculation_window = 20
    formula_version = "mae_20d_close_v1"
    description = "20 trading day close-based maximum adverse excursion calculated as min(0, min(future_close / reference_close - 1)), excluding the reference day."


class MaximumAdverseExcursion60DRegressionGenerator(_MaximumAdverseExcursionBase):
    target_id = "TARGET_MAE_60D_REG_V1"
    target_name = "60D Maximum Adverse Excursion"
    target_type = "Regression"
    calculation_window = 60
    formula_version = "mae_60d_close_v1"
    description = "60 trading day close-based maximum adverse excursion calculated as min(0, min(future_close / reference_close - 1)), excluding the reference day."
