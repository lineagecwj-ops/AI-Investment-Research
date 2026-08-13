from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PerformanceRecord:
    model_id: str
    dataset_id: str
    evaluation_version: str
    metrics: dict[str, float]
    created_at: datetime


class PerformanceTracker:
    """In-memory performance tracker for evaluation results."""

    def __init__(self):
        self._records: dict[tuple[str, str, str], PerformanceRecord] = {}

    def record(self, record: PerformanceRecord) -> None:
        key = (record.model_id, record.dataset_id, record.evaluation_version)
        if key in self._records:
            raise ValueError(
                f"Performance already recorded: {record.model_id} {record.dataset_id} {record.evaluation_version}"
            )
        self._records[key] = record

    def list_records(self) -> tuple[PerformanceRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records.keys()))
