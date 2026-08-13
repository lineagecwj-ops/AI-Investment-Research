import hashlib
import json
from datetime import date
from typing import Any
from typing import Mapping

from features.feature_calculator import FeatureCalculationOutput
from features.feature_context import FeatureCalculationContext


class ChecksumMismatchError(Exception):
    """Raised when a reproduced checksum does not match an expected checksum."""


class FeatureChecksumGenerator:
    """Deterministic checksum generator for feature calculation outputs."""

    def generate(self, output: FeatureCalculationOutput, context: FeatureCalculationContext) -> str:
        payload = {
            "feature_id": output.feature_id,
            "feature_version": output.feature_version,
            "snapshot_id": context.snapshot_id,
            "symbol_set": sorted({str(row["symbol"]) for row in output.values if "symbol" in row}),
            "date_range": self._date_range(output.values),
            "feature_values": self._normalized_values(output.values),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=self._json_default)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self, output: FeatureCalculationOutput, context: FeatureCalculationContext, expected: str) -> None:
        actual = self.generate(output, context)
        if actual != expected:
            raise ChecksumMismatchError(f"Feature checksum mismatch: expected {expected}, got {actual}.")

    def _date_range(self, values: tuple[Mapping[str, Any], ...]) -> tuple[str | None, str | None]:
        dates = sorted(self._json_default(row["date"]) for row in values if "date" in row)
        if not dates:
            return None, None
        return dates[0], dates[-1]

    def _normalized_values(self, values: tuple[Mapping[str, Any], ...]) -> tuple[dict[str, Any], ...]:
        return tuple(
            sorted(
                (
                    {
                        "symbol": str(row["symbol"]),
                        "date": self._json_default(row["date"]),
                        "feature_id": str(row["feature_id"]),
                        "feature_version": str(row["feature_version"]),
                        "value": row["value"],
                    }
                    for row in values
                ),
                key=lambda row: (row["symbol"], row["date"], row["feature_id"], row["feature_version"]),
            )
        )

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, date):
            return value.isoformat()
        return value
