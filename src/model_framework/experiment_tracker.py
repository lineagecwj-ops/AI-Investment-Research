from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    model_version: str
    dataset_version: str
    parameters: dict[str, Any]
    metrics: dict[str, float]
    created_at: datetime


class ExperimentTracker:
    """In-memory tracker for deterministic model experiment metadata."""

    def __init__(self):
        self._records: dict[str, ExperimentRecord] = {}

    def record(self, record: ExperimentRecord) -> None:
        if record.experiment_id in self._records:
            raise ValueError(f"Experiment already recorded: {record.experiment_id}")
        self._records[record.experiment_id] = record

    def get(self, experiment_id: str) -> ExperimentRecord:
        try:
            return self._records[experiment_id]
        except KeyError as exc:
            raise KeyError(f"Experiment not recorded: {experiment_id}") from exc

    def list_experiments(self) -> tuple[str, ...]:
        return tuple(sorted(self._records.keys()))
