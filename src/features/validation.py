from dataclasses import dataclass
from datetime import date
from numbers import Real
from typing import Any
from typing import Mapping

from features.feature_calculator import FeatureCalculationOutput
from features.feature_context import FeatureCalculationContext


class FeatureValidationError(Exception):
    """Base class for deterministic feature validation failures."""


class SchemaError(FeatureValidationError):
    """Raised when feature output schema is invalid."""


class RangeValidationError(FeatureValidationError):
    """Raised when feature output values are outside the allowed range."""


class LeakageValidationError(FeatureValidationError):
    """Raised when feature output includes data after the as-of date."""


@dataclass(frozen=True)
class CompletenessResult:
    expected_count: int
    actual_count: int
    coverage_ratio: float
    missing_symbols: tuple[str, ...]


class FeatureValidator:
    """Validation layer for feature calculation outputs."""

    required_fields = frozenset(("feature_id", "feature_version", "symbol", "date", "value"))

    def validate_schema(self, output: FeatureCalculationOutput) -> None:
        for index, row in enumerate(output.values):
            missing = sorted(self.required_fields - set(row.keys()))
            if missing:
                raise SchemaError(f"Feature output row {index} missing required fields: {', '.join(missing)}")

    def validate_range(self, output: FeatureCalculationOutput) -> None:
        for index, row in enumerate(output.values):
            value = row.get("value")
            if not isinstance(value, Real):
                raise RangeValidationError(f"Feature output row {index} value is not numeric.")
            feature_id = str(row.get("feature_id", output.feature_id))
            if feature_id == "TECH_RSI14_V1" and not 0.0 <= float(value) <= 100.0:
                raise RangeValidationError(f"RSI14 value out of range at row {index}: {value}")
            if feature_id == "TECH_VOLUME_RATIO_V1" and float(value) < 0.0:
                raise RangeValidationError(f"Volume ratio value must be non-negative at row {index}: {value}")

    def validate_completeness(
        self,
        expected_symbols: tuple[str, ...],
        output: FeatureCalculationOutput,
    ) -> CompletenessResult:
        expected = tuple(dict.fromkeys(expected_symbols))
        actual_symbols = tuple(dict.fromkeys(str(row["symbol"]) for row in output.values if "symbol" in row))
        missing = tuple(symbol for symbol in expected if symbol not in actual_symbols)
        coverage = 1.0 if not expected else (len(expected) - len(missing)) / len(expected)
        return CompletenessResult(
            expected_count=len(expected),
            actual_count=len(actual_symbols),
            coverage_ratio=coverage,
            missing_symbols=missing,
        )

    def validate_leakage(self, output: FeatureCalculationOutput, context: FeatureCalculationContext) -> None:
        for index, row in enumerate(output.values):
            feature_date = self._coerce_date(row.get("date"))
            if feature_date > context.as_of_date:
                raise LeakageValidationError(
                    f"Feature output row {index} date {feature_date.isoformat()} is after "
                    f"as_of_date {context.as_of_date.isoformat()}."
                )

    def validate_all(
        self,
        output: FeatureCalculationOutput,
        context: FeatureCalculationContext,
        expected_symbols: tuple[str, ...] = (),
    ) -> CompletenessResult:
        self.validate_schema(output)
        self.validate_range(output)
        self.validate_leakage(output, context)
        return self.validate_completeness(expected_symbols, output)

    def _coerce_date(self, value: Any) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise LeakageValidationError(f"Feature output date is invalid: {value!r}")
