from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from risk_evaluation.validation import RiskFeatureInputError
from risk_evaluation.validation import require_date
from risk_evaluation.validation import require_non_empty_text
from risk_evaluation.validation import require_numeric_value


@dataclass(frozen=True)
class RiskFeatureInput:
    """Frozen feature value consumed by production risk signal producers."""

    feature_id: str
    feature_version: str
    portfolio_id: str
    position_id: str
    symbol: str
    as_of_date: date
    feature_date: date
    value: Decimal | int | float
    source_artifact_id: str
    source_checksum: str
    calculation_id: str

    def __post_init__(self):
        require_non_empty_text(self.feature_id, "feature_id", RiskFeatureInputError)
        require_non_empty_text(self.feature_version, "feature_version", RiskFeatureInputError)
        require_non_empty_text(self.portfolio_id, "portfolio_id", RiskFeatureInputError)
        require_non_empty_text(self.position_id, "position_id", RiskFeatureInputError)
        require_non_empty_text(self.symbol, "symbol", RiskFeatureInputError)
        require_date(self.as_of_date, "as_of_date", RiskFeatureInputError)
        require_date(self.feature_date, "feature_date", RiskFeatureInputError)
        require_numeric_value(self.value, "value")
        require_non_empty_text(self.source_artifact_id, "source_artifact_id", RiskFeatureInputError)
        require_non_empty_text(self.source_checksum, "source_checksum", RiskFeatureInputError)
        require_non_empty_text(self.calculation_id, "calculation_id", RiskFeatureInputError)
        if self.feature_date > self.as_of_date:
            raise RiskFeatureInputError("feature_date cannot be after as_of_date.")

    @property
    def identity(self) -> tuple[str, str]:
        return self.feature_id, self.feature_version
