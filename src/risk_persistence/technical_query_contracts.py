from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from risk import RiskArtifact
from risk import RiskCategory
from risk import RiskSeverity
from risk_persistence.contracts import RiskArtifactCorruptionError
from risk_persistence.contracts import RiskArtifactPersistenceError


class RiskArtifactIndexCorruptionError(RiskArtifactCorruptionError):
    """Raised when a persisted query projection disagrees with its RiskArtifact."""


@dataclass(frozen=True)
class TechnicalRiskArtifactIndexRecord:
    """Technical Risk query projection; the RiskArtifact payload remains source-of-truth.

    Future query implementations must treat missing core artifacts or duplicated
    index fields that disagree with verified artifacts as RiskArtifactIndexCorruptionError.
    Missing projection rows for existing core artifacts require a separate
    population/reconciliation boundary and are not detected by ordinary queries.
    """

    artifact_id: str
    portfolio_id: str
    position_id: str
    symbol: str
    severity: RiskSeverity | str
    analysis_date: date
    valuation_date: date
    created_at: datetime
    calculation_id: str
    policy_id: str
    policy_version: str
    policy_checksum: str
    evaluation_id: str
    evaluation_checksum: str
    producer_version: str

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.portfolio_id, "portfolio_id")
        _require_text(self.position_id, "position_id")
        _require_text(self.symbol, "symbol")
        severity = _require_technical_v1_severity(self.severity)
        object.__setattr__(self, "severity", severity)
        _require_exact_date(self.analysis_date, "analysis_date")
        _require_exact_date(self.valuation_date, "valuation_date")
        _require_timezone_aware_datetime(self.created_at, "created_at")
        _require_text(self.calculation_id, "calculation_id")
        _require_text(self.policy_id, "policy_id")
        _require_text(self.policy_version, "policy_version")
        _require_text(self.policy_checksum, "policy_checksum")
        _require_text(self.evaluation_id, "evaluation_id")
        _require_text(self.evaluation_checksum, "evaluation_checksum")
        _require_text(self.producer_version, "producer_version")

    @classmethod
    def from_artifact(cls, artifact: RiskArtifact) -> "TechnicalRiskArtifactIndexRecord":
        """Extract a verified Technical Risk projection without DB, codec, or policy lookup."""

        if not isinstance(artifact, RiskArtifact):
            raise RiskArtifactPersistenceError("Technical Risk index projection requires RiskArtifact.")
        artifact_id = artifact.artifact_id if isinstance(artifact.artifact_id, str) and artifact.artifact_id else "unknown"
        try:
            _validate_technical_artifact_shape(artifact)
            metadata = artifact.calculation_metadata
            portfolio_id = _metadata_text(metadata, "portfolio_id", artifact_id)
            symbol = _metadata_text(metadata, "symbol", artifact_id)
            analysis_date = _metadata_date(metadata, "analysis_date", artifact_id)
            calculation_id = _metadata_text(metadata, "calculation_id", artifact_id)
            position_id = _metadata_text(metadata, "technical_position_id", artifact_id)
            as_of_date = _metadata_date(metadata, "technical_as_of_date", artifact_id)
            valuation_date = _metadata_date(metadata, "technical_valuation_date", artifact_id)
            if analysis_date != as_of_date:
                raise RiskArtifactIndexCorruptionError(artifact_id)
            if artifact.risk_assessment.portfolio_id != portfolio_id:
                raise RiskArtifactIndexCorruptionError(artifact_id)
            if artifact.risk_assessment.symbol != symbol:
                raise RiskArtifactIndexCorruptionError(artifact_id)
            if artifact.position_identity.get("symbol") != symbol:
                raise RiskArtifactIndexCorruptionError(artifact_id)
            if _metadata_text(metadata, "technical_calculation_id", artifact_id) != calculation_id:
                raise RiskArtifactIndexCorruptionError(artifact_id)
            return cls(
                artifact_id=artifact.artifact_id,
                portfolio_id=portfolio_id,
                position_id=position_id,
                symbol=symbol,
                severity=artifact.risk_assessment.overall_risk_level,
                analysis_date=analysis_date,
                valuation_date=valuation_date,
                created_at=artifact.created_at,
                calculation_id=calculation_id,
                policy_id=_metadata_text(metadata, "technical_policy_id", artifact_id),
                policy_version=_metadata_text(metadata, "technical_policy_version", artifact_id),
                policy_checksum=_metadata_text(metadata, "technical_policy_checksum", artifact_id),
                evaluation_id=_metadata_text(metadata, "technical_evaluation_id", artifact_id),
                evaluation_checksum=_metadata_text(metadata, "technical_evaluation_checksum", artifact_id),
                producer_version=_metadata_text(metadata, "technical_producer_version", artifact_id),
            )
        except RiskArtifactIndexCorruptionError:
            raise
        except (RiskArtifactPersistenceError, ValueError, TypeError) as exc:
            raise RiskArtifactIndexCorruptionError(artifact_id) from exc


@runtime_checkable
class TechnicalRiskArtifactQueryRepository(Protocol):
    """Read-side contract for Technical Risk artifacts.

    Generic RiskArtifact has no first-class position_id. Implementations must use
    portfolio_id plus calculation_metadata["technical_position_id"] as the
    Technical position key, return verified RiskArtifact domain objects, and treat
    index rows only as query projections.
    """

    def get_latest_by_position(
        self,
        portfolio_id: str,
        position_id: str,
    ) -> RiskArtifact | None:
        """Return latest by analysis_date DESC, created_at DESC, artifact_id DESC."""
        ...

    def list_history_by_position(
        self,
        portfolio_id: str,
        position_id: str,
        *,
        limit: int | None = None,
    ) -> tuple[RiskArtifact, ...]:
        """Return newest first; limit must be None or a positive integer."""
        ...

    def list_latest_by_portfolio(
        self,
        portfolio_id: str,
        *,
        severity: RiskSeverity | None = None,
    ) -> tuple[RiskArtifact, ...]:
        """Return one latest artifact per position, then optionally filter by latest severity."""
        ...


def _validate_technical_artifact_shape(artifact: RiskArtifact) -> None:
    if not isinstance(artifact.checksum, str) or not artifact.checksum:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)
    if artifact.risk_assessment.signals != artifact.signals:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)
    if len(artifact.signals) != 1:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)
    signal = artifact.signals[0]
    if signal.category != RiskCategory.TECHNICAL:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)
    if signal.symbol != artifact.risk_assessment.symbol:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)
    if signal.severity != artifact.risk_assessment.overall_risk_level:
        raise RiskArtifactIndexCorruptionError(artifact.artifact_id)
    _require_technical_v1_severity(artifact.risk_assessment.overall_risk_level)


def _require_technical_v1_severity(value: object) -> RiskSeverity:
    try:
        severity = RiskSeverity(value)
    except ValueError as exc:
        raise RiskArtifactPersistenceError("severity must be a valid RiskSeverity.") from exc
    if severity == RiskSeverity.CRITICAL:
        raise RiskArtifactPersistenceError("Technical Risk v1 index projection cannot use CRITICAL.")
    return severity


def _metadata_text(metadata: dict[str, object], key: str, artifact_id: str) -> str:
    try:
        return _require_text(metadata[key], key)
    except KeyError as exc:
        raise RiskArtifactIndexCorruptionError(artifact_id) from exc


def _metadata_date(metadata: dict[str, object], key: str, artifact_id: str) -> date:
    value = _metadata_text(metadata, key, artifact_id)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RiskArtifactIndexCorruptionError(artifact_id) from exc


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RiskArtifactPersistenceError(f"{field_name} must be a non-empty string.")
    return value


def _require_exact_date(value: object, field_name: str) -> date:
    if type(value) is not date:
        raise RiskArtifactPersistenceError(f"{field_name} must be a date.")
    return value


def _require_timezone_aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise RiskArtifactPersistenceError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise RiskArtifactPersistenceError(f"{field_name} must be timezone-aware.")
    return value
