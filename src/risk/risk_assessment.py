from dataclasses import dataclass
from datetime import date

from risk.risk_definition import SEVERITY_ORDER
from risk.risk_definition import RiskSeverity
from risk.risk_signal import RiskSignal


class RiskAssessmentError(ValueError):
    """Base class for deterministic risk assessment failures."""


class MissingFeatureError(RiskAssessmentError):
    """Raised when required synthetic feature input is absent."""


class InvalidSeverityError(RiskAssessmentError):
    """Raised when a severity value is invalid."""


def aggregate_risk_level(signals: tuple[RiskSignal, ...]) -> RiskSeverity:
    """Aggregate signals by the highest ordered severity."""

    if not signals:
        return RiskSeverity.LOW
    severities = tuple(RiskSeverity(signal.severity) for signal in signals)
    return max(severities, key=lambda severity: SEVERITY_ORDER[severity])


@dataclass(frozen=True)
class RiskAssessment:
    """Portfolio risk assessment for one symbol and portfolio."""

    portfolio_id: str
    symbol: str
    overall_risk_level: RiskSeverity | str
    signals: tuple[RiskSignal, ...]
    assessment_date: date
    checksum: str | None = None

    def __post_init__(self):
        if not self.portfolio_id:
            raise RiskAssessmentError("RiskAssessment requires portfolio_id.")
        if not self.symbol:
            raise RiskAssessmentError("RiskAssessment requires symbol.")
        if not isinstance(self.assessment_date, date):
            raise RiskAssessmentError("RiskAssessment assessment_date must be a date.")
        if not isinstance(self.signals, tuple):
            raise RiskAssessmentError("RiskAssessment signals must be a tuple.")

        try:
            severity = RiskSeverity(self.overall_risk_level)
        except ValueError as exc:
            raise InvalidSeverityError(f"Invalid severity: {self.overall_risk_level}") from exc

        for signal in self.signals:
            if not isinstance(signal, RiskSignal):
                raise RiskAssessmentError("RiskAssessment signals must contain RiskSignal instances.")
            if signal.symbol != self.symbol:
                raise RiskAssessmentError("RiskAssessment signal symbol mismatch.")

        object.__setattr__(self, "overall_risk_level", severity)

    @classmethod
    def from_signals(
        cls,
        portfolio_id: str,
        symbol: str,
        signals: tuple[RiskSignal, ...],
        assessment_date: date,
        checksum: str | None = None,
    ) -> "RiskAssessment":
        return cls(
            portfolio_id=portfolio_id,
            symbol=symbol,
            overall_risk_level=aggregate_risk_level(signals),
            signals=signals,
            assessment_date=assessment_date,
            checksum=checksum,
        )
