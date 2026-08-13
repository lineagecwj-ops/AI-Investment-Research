from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from typing import Iterable

from features.feature_artifact import FeatureArtifact
from features.feature_calculator import FeatureCalculationOutput
from features.feature_context import FeatureCalculationContext
from features.feature_definition import FeatureDefinition


VALIDATION_PASS = "PASS"
VALIDATION_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
VALIDATION_INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class PriceVolumePoint:
    """Deterministic input point for technical feature calculators."""

    symbol: str
    trading_date: date
    close: float | None = None
    volume: float | None = None


class _TechnicalCalculatorBase:
    feature_id: str
    feature_name: str
    formula_version: str
    description: str
    dependencies: tuple[str, ...]
    input_fields: tuple[str, ...]

    def __init__(self, series: Iterable[PriceVolumePoint]):
        self._series = tuple(sorted(series, key=lambda point: (point.symbol, point.trading_date)))

    def get_definition(self) -> FeatureDefinition:
        return FeatureDefinition(
            feature_id=self.feature_id,
            feature_name=self.feature_name,
            category="Technical",
            version="v1",
            description=self.description,
            formula_version=self.formula_version,
            dependencies=self.dependencies,
            input_fields=self.input_fields,
        )

    def _points_until_as_of(self, context: FeatureCalculationContext) -> tuple[PriceVolumePoint, ...]:
        return tuple(point for point in self._series if point.trading_date <= context.as_of_date)

    def _latest_symbol_points(
        self,
        context: FeatureCalculationContext,
        required_field: str,
    ) -> tuple[str, tuple[PriceVolumePoint, ...]] | None:
        filtered = self._points_until_as_of(context)
        if not filtered:
            return None
        latest_symbol = max(filtered, key=lambda point: point.trading_date).symbol
        symbol_points = tuple(point for point in filtered if point.symbol == latest_symbol)
        if required_field == "close":
            symbol_points = tuple(point for point in symbol_points if point.close is not None)
        if required_field == "volume":
            symbol_points = tuple(point for point in symbol_points if point.volume is not None)
        return latest_symbol, symbol_points

    def _artifact(
        self,
        context: FeatureCalculationContext,
        validation_status: str,
    ) -> FeatureArtifact:
        definition = self.get_definition()
        return FeatureArtifact(
            feature_id=definition.feature_id,
            feature_version=definition.version,
            snapshot_id=context.snapshot_id,
            calculation_id=context.calculation_id,
            created_at=datetime.combine(context.as_of_date, time.min, tzinfo=UTC),
            checksum=None,
            validation_status=validation_status,
        )

    def _output(
        self,
        context: FeatureCalculationContext,
        validation_status: str,
        values: tuple[dict[str, object], ...],
        metadata: dict[str, object] | None = None,
    ) -> FeatureCalculationOutput:
        definition = self.get_definition()
        output_metadata = {
            "snapshot_id": context.snapshot_id,
            "as_of_date": context.as_of_date.isoformat(),
            "calculation_id": context.calculation_id,
            "validation_status": validation_status,
        }
        if metadata:
            output_metadata.update(metadata)
        return FeatureCalculationOutput(
            feature_id=definition.feature_id,
            feature_version=definition.version,
            values=values,
            metadata=output_metadata,
            artifact=self._artifact(context, validation_status),
        )

    def validate(self, output: FeatureCalculationOutput) -> bool:
        return bool(output.values) and output.metadata is not None and output.metadata.get("validation_status") == VALIDATION_PASS


class _MovingAverageCalculator(_TechnicalCalculatorBase):
    window: int

    def calculate(self, context: FeatureCalculationContext) -> FeatureCalculationOutput:
        symbol_points = self._latest_symbol_points(context, "close")
        if symbol_points is None:
            return self._output(context, VALIDATION_INSUFFICIENT_HISTORY, (), {"reason": "no input rows"})
        symbol, points = symbol_points
        if len(points) < self.window:
            return self._output(
                context,
                VALIDATION_INSUFFICIENT_HISTORY,
                (),
                {"required_observations": self.window, "available_observations": len(points)},
            )
        window_points = points[-self.window :]
        value = sum(point.close for point in window_points if point.close is not None) / self.window
        return self._output(
            context,
            VALIDATION_PASS,
            (
                {
                    "symbol": symbol,
                    "date": window_points[-1].trading_date,
                    "feature_id": self.feature_id,
                    "feature_version": "v1",
                    "value": value,
                    "feature_value": value,
                },
            ),
            {"window": self.window},
        )


class SMA20Calculator(_MovingAverageCalculator):
    feature_id = "TECH_SMA20_V1"
    feature_name = "SMA20"
    formula_version = "SMA20_v1"
    description = "20 trading day simple moving average of historical close price."
    dependencies = ("historical_prices.close",)
    input_fields = ("symbol", "trading_date", "close")
    window = 20


class SMA60Calculator(_MovingAverageCalculator):
    feature_id = "TECH_SMA60_V1"
    feature_name = "SMA60"
    formula_version = "SMA60_v1"
    description = "60 trading day simple moving average of historical close price."
    dependencies = ("historical_prices.close",)
    input_fields = ("symbol", "trading_date", "close")
    window = 60


class RSI14Calculator(_TechnicalCalculatorBase):
    feature_id = "TECH_RSI14_V1"
    feature_name = "RSI14"
    formula_version = "RSI14_v1"
    description = "14 period relative strength index of historical close price."
    dependencies = ("historical_prices.close",)
    input_fields = ("symbol", "trading_date", "close")
    period = 14

    def calculate(self, context: FeatureCalculationContext) -> FeatureCalculationOutput:
        symbol_points = self._latest_symbol_points(context, "close")
        if symbol_points is None:
            return self._output(context, VALIDATION_INSUFFICIENT_HISTORY, (), {"reason": "no input rows"})
        symbol, points = symbol_points
        required = self.period + 1
        if len(points) < required:
            return self._output(
                context,
                VALIDATION_INSUFFICIENT_HISTORY,
                (),
                {"required_observations": required, "available_observations": len(points)},
            )
        window_points = points[-required:]
        deltas = [
            window_points[index].close - window_points[index - 1].close
            for index in range(1, len(window_points))
            if window_points[index].close is not None and window_points[index - 1].close is not None
        ]
        gains = [max(delta, 0.0) for delta in deltas]
        losses = [abs(min(delta, 0.0)) for delta in deltas]
        average_gain = sum(gains) / self.period
        average_loss = sum(losses) / self.period
        if average_loss == 0 and average_gain == 0:
            value = 50.0
        elif average_loss == 0:
            value = 100.0
        else:
            relative_strength = average_gain / average_loss
            value = 100.0 - (100.0 / (1.0 + relative_strength))
        return self._output(
            context,
            VALIDATION_PASS,
            (
                {
                    "symbol": symbol,
                    "date": window_points[-1].trading_date,
                    "feature_id": self.feature_id,
                    "feature_version": "v1",
                    "value": value,
                    "feature_value": value,
                },
            ),
            {"period": self.period},
        )

    def validate(self, output: FeatureCalculationOutput) -> bool:
        if not super().validate(output):
            return False
        return all(0.0 <= row["feature_value"] <= 100.0 for row in output.values)


class VolumeRatioCalculator(_TechnicalCalculatorBase):
    feature_id = "TECH_VOLUME_RATIO_V1"
    feature_name = "VolumeRatio"
    formula_version = "VolumeRatio_v1"
    description = "Current volume divided by average volume over the prior 20 trading days."
    dependencies = ("historical_prices.volume",)
    input_fields = ("symbol", "trading_date", "volume")
    baseline_window = 20

    def calculate(self, context: FeatureCalculationContext) -> FeatureCalculationOutput:
        symbol_points = self._latest_symbol_points(context, "volume")
        if symbol_points is None:
            return self._output(context, VALIDATION_INSUFFICIENT_HISTORY, (), {"reason": "no input rows"})
        symbol, points = symbol_points
        required = self.baseline_window + 1
        if len(points) < required:
            return self._output(
                context,
                VALIDATION_INSUFFICIENT_HISTORY,
                (),
                {"required_observations": required, "available_observations": len(points)},
            )
        current = points[-1]
        baseline_points = points[-required:-1]
        baseline_average = sum(point.volume for point in baseline_points if point.volume is not None) / self.baseline_window
        if baseline_average == 0:
            return self._output(context, VALIDATION_INVALID_INPUT, (), {"reason": "zero baseline volume"})
        value = current.volume / baseline_average
        return self._output(
            context,
            VALIDATION_PASS,
            (
                {
                    "symbol": symbol,
                    "date": current.trading_date,
                    "feature_id": self.feature_id,
                    "feature_version": "v1",
                    "value": value,
                    "feature_value": value,
                },
            ),
            {"baseline_window": self.baseline_window},
        )
