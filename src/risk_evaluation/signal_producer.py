from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol

from risk import RiskCategory
from risk import RiskSignal
from risk_evaluation.evaluation_input import RiskSignalProductionInput
from risk_evaluation.policy import RiskEvaluationPolicy
from risk_evaluation.validation import RiskSignalProducerError
from risk_evaluation.validation import normalize_text_tuple
from risk_evaluation.validation import require_date
from risk_evaluation.validation import require_non_empty_text
from risk_evaluation.validation import require_timezone_aware_datetime


@dataclass(frozen=True)
class ProducedRiskSignal:
    """RiskSignal plus production lineage, without changing Phase 7K RiskSignal."""

    signal: RiskSignal
    policy_id: str
    policy_version: str
    producer_version: str
    source_feature_ids: tuple[str, ...]
    source_checksums: tuple[str, ...]
    calculation_id: str
    policy_checksum: str | None = None
    evaluation_id: str | None = None
    evaluation_checksum: str | None = None
    portfolio_id: str | None = None
    position_id: str | None = None
    as_of_date: date | None = None
    valuation_date: date | None = None

    def __post_init__(self):
        if not isinstance(self.signal, RiskSignal):
            raise RiskSignalProducerError("ProducedRiskSignal requires RiskSignal.")
        require_non_empty_text(self.policy_id, "policy_id", RiskSignalProducerError)
        require_non_empty_text(self.policy_version, "policy_version", RiskSignalProducerError)
        require_non_empty_text(self.producer_version, "producer_version", RiskSignalProducerError)
        require_non_empty_text(self.calculation_id, "calculation_id", RiskSignalProducerError)
        for field_name in (
            "policy_checksum",
            "evaluation_id",
            "evaluation_checksum",
            "portfolio_id",
            "position_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_non_empty_text(value, field_name, RiskSignalProducerError)
        if self.as_of_date is not None:
            require_date(self.as_of_date, "as_of_date", RiskSignalProducerError)
        if self.valuation_date is not None:
            require_date(self.valuation_date, "valuation_date", RiskSignalProducerError)
        object.__setattr__(
            self,
            "source_feature_ids",
            normalize_text_tuple(self.source_feature_ids, "source_feature_ids", RiskSignalProducerError),
        )
        object.__setattr__(
            self,
            "source_checksums",
            normalize_text_tuple(self.source_checksums, "source_checksums", RiskSignalProducerError),
        )


class RiskSignalProducer(Protocol):
    """Category-specific deterministic risk signal producer contract."""

    category: RiskCategory
    producer_version: str

    def produce(
        self,
        input: RiskSignalProductionInput,
        policy: RiskEvaluationPolicy,
        created_at: datetime,
    ) -> tuple[ProducedRiskSignal, ...]:
        ...


def validate_producer_created_at(created_at: datetime) -> None:
    require_timezone_aware_datetime(created_at, "created_at", RiskSignalProducerError)
