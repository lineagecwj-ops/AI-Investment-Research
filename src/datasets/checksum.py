import hashlib
import json
from datetime import date
from typing import Any

from datasets.dataset_context import DatasetContext


class DatasetChecksumMismatchError(Exception):
    """Raised when reproduced dataset checksum differs from expected value."""


class DatasetChecksumGenerator:
    """Deterministic checksum generator for metadata-only dataset rows."""

    def generate(self, context: DatasetContext, rows: tuple[Any, ...]) -> str:
        payload = {
            "dataset_id": context.dataset_id,
            "feature_version": context.feature_set_version,
            "target_version": context.target_version,
            "snapshot_id": context.snapshot_id,
            "symbol_set": sorted({row.symbol for row in rows}),
            "row_content": self._normalized_rows(rows),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=self._json_default)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def verify(self, context: DatasetContext, rows: tuple[Any, ...], expected: str) -> None:
        actual = self.generate(context, rows)
        if actual != expected:
            raise DatasetChecksumMismatchError(f"Dataset checksum mismatch: expected {expected}, got {actual}.")

    def _normalized_rows(self, rows: tuple[Any, ...]) -> tuple[dict[str, Any], ...]:
        return tuple(
            sorted(
                (
                    {
                        "symbol": row.symbol,
                        "reference_date": self._json_default(row.reference_date),
                        "features": row.features,
                        "target": row.target,
                        "target_value": row.metadata.get("target_value"),
                        "feature_checksums": row.metadata.get("feature_checksums"),
                        "target_checksum": row.metadata.get("target_checksum"),
                    }
                    for row in rows
                ),
                key=lambda row: (row["symbol"], row["reference_date"], row["target"]),
            )
        )

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, date):
            return value.isoformat()
        return value
