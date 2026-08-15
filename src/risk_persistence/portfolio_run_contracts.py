import hashlib
import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from enum import StrEnum
from typing import Any
from typing import Mapping
from typing import Protocol
from typing import runtime_checkable

from portfolio_generation import PortfolioRiskGenerationStatus


PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1 = "1"


class PortfolioRiskGenerationRunSaveStatus(StrEnum):
    """Append-only persistence outcome for a portfolio generation run record."""

    INSERTED = "INSERTED"
    IDEMPOTENT = "IDEMPOTENT"


class PortfolioRiskGenerationRunPersistenceError(ValueError):
    """Base error for portfolio generation run persistence contract failures."""


class PortfolioRiskGenerationRunConflictError(PortfolioRiskGenerationRunPersistenceError):
    """Raised when an existing calculation_id has a different run checksum."""

    def __init__(self, calculation_id: str, existing_checksum: str, incoming_checksum: str):
        self.calculation_id = _require_text(calculation_id, "calculation_id")
        self.existing_checksum = _require_text(existing_checksum, "existing_checksum")
        self.incoming_checksum = _require_text(incoming_checksum, "incoming_checksum")
        super().__init__(
            "PortfolioRiskGenerationRunRecord conflict for calculation_id "
            f"{self.calculation_id}: existing checksum differs from incoming checksum."
        )


class PortfolioRiskGenerationRunCorruptionError(PortfolioRiskGenerationRunPersistenceError):
    """Raised when a stored run record cannot pass integrity validation."""

    def __init__(self, calculation_id: str):
        self.calculation_id = _require_text(calculation_id, "calculation_id")
        super().__init__(f"Stored PortfolioRiskGenerationRunRecord is corrupted: {self.calculation_id}.")


@dataclass(frozen=True)
class PortfolioRiskGenerationRunArtifactRef:
    """Explicit position-to-RiskArtifact reference captured for a run."""

    position_id: str
    artifact_id: str
    artifact_checksum: str

    def __post_init__(self):
        _require_text(self.position_id, "position_id")
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.artifact_checksum, "artifact_checksum")


@dataclass(frozen=True)
class PortfolioRiskGenerationRunMonitoringArtifactRef:
    """Explicit position-to-monitoring-artifact reference captured for a run."""

    position_id: str
    artifact_id: str

    def __post_init__(self):
        _require_text(self.position_id, "position_id")
        _require_text(self.artifact_id, "artifact_id")


@dataclass(frozen=True)
class PortfolioRiskGenerationRunIssue:
    """Durable issue emitted by portfolio generation without exception internals."""

    stage: str
    message: str
    position_id: str | None = None

    def __post_init__(self):
        _require_text(self.stage, "stage")
        _require_text(self.message, "message")
        if self.position_id is not None:
            _require_text(self.position_id, "position_id")


@dataclass(frozen=True)
class PortfolioRiskGenerationRunWarning:
    """Durable warning emitted by portfolio generation."""

    stage: str
    message: str
    position_id: str | None = None

    def __post_init__(self):
        _require_text(self.stage, "stage")
        _require_text(self.message, "message")
        if self.position_id is not None:
            _require_text(self.position_id, "position_id")


@dataclass(frozen=True)
class PortfolioRiskGenerationRunRecord:
    """Immutable durable audit record for one PortfolioRiskGenerationService run."""

    calculation_id: str
    generation_key: str
    portfolio_id: str
    snapshot_id: str
    snapshot_checksum: str
    analysis_date: date
    valuation_date: date
    status: PortfolioRiskGenerationStatus | str
    attempted_position_ids: tuple[str, ...]
    risk_evaluated_position_ids: tuple[str, ...]
    succeeded_position_ids: tuple[str, ...]
    failed_position_ids: tuple[str, ...]
    risk_artifact_refs: tuple[PortfolioRiskGenerationRunArtifactRef, ...]
    monitoring_artifact_refs: tuple[PortfolioRiskGenerationRunMonitoringArtifactRef, ...]
    issues: tuple[PortfolioRiskGenerationRunIssue, ...]
    warnings: tuple[PortfolioRiskGenerationRunWarning, ...]
    created_at: datetime
    record_checksum: str | None = None

    def __post_init__(self):
        _require_text(self.calculation_id, "calculation_id")
        _require_text(self.generation_key, "generation_key")
        _require_text(self.portfolio_id, "portfolio_id")
        _require_text(self.snapshot_id, "snapshot_id")
        _require_text(self.snapshot_checksum, "snapshot_checksum")
        _require_exact_date(self.analysis_date, "analysis_date")
        _require_exact_date(self.valuation_date, "valuation_date")
        _require_timezone_aware_datetime(self.created_at, "created_at")
        try:
            status = PortfolioRiskGenerationStatus(self.status)
        except ValueError as exc:
            raise PortfolioRiskGenerationRunPersistenceError("status must be a valid PortfolioRiskGenerationStatus.") from exc
        object.__setattr__(self, "status", status)

        self._validate_tuple_fields()
        self._validate_position_lifecycle()
        self._validate_artifact_refs()
        expected_checksum = record_checksum(self)
        if self.record_checksum is None:
            object.__setattr__(self, "record_checksum", expected_checksum)
        elif self.record_checksum != expected_checksum:
            raise PortfolioRiskGenerationRunPersistenceError("record_checksum mismatch.")

    def _validate_tuple_fields(self) -> None:
        _require_text_tuple(self.attempted_position_ids, "attempted_position_ids")
        _require_text_tuple(self.risk_evaluated_position_ids, "risk_evaluated_position_ids")
        _require_text_tuple(self.succeeded_position_ids, "succeeded_position_ids")
        _require_text_tuple(self.failed_position_ids, "failed_position_ids")
        _require_unique(self.attempted_position_ids, "attempted_position_ids")
        _require_unique(self.risk_evaluated_position_ids, "risk_evaluated_position_ids")
        _require_unique(self.succeeded_position_ids, "succeeded_position_ids")
        _require_unique(self.failed_position_ids, "failed_position_ids")
        _require_typed_tuple(self.risk_artifact_refs, PortfolioRiskGenerationRunArtifactRef, "risk_artifact_refs")
        _require_typed_tuple(
            self.monitoring_artifact_refs,
            PortfolioRiskGenerationRunMonitoringArtifactRef,
            "monitoring_artifact_refs",
        )
        _require_typed_tuple(self.issues, PortfolioRiskGenerationRunIssue, "issues")
        _require_typed_tuple(self.warnings, PortfolioRiskGenerationRunWarning, "warnings")

    def _validate_position_lifecycle(self) -> None:
        attempted = set(self.attempted_position_ids)
        risk_evaluated = set(self.risk_evaluated_position_ids)
        succeeded = set(self.succeeded_position_ids)
        failed = set(self.failed_position_ids)
        if not risk_evaluated.issubset(attempted):
            raise PortfolioRiskGenerationRunPersistenceError("risk_evaluated_position_ids must be attempted.")
        if not succeeded.issubset(risk_evaluated):
            raise PortfolioRiskGenerationRunPersistenceError("succeeded_position_ids must be risk evaluated.")
        if not failed.issubset(attempted):
            raise PortfolioRiskGenerationRunPersistenceError("failed_position_ids must be attempted.")
        if succeeded.intersection(failed):
            raise PortfolioRiskGenerationRunPersistenceError("succeeded_position_ids and failed_position_ids must not overlap.")

    def _validate_artifact_refs(self) -> None:
        if len(self.risk_artifact_refs) != len(self.risk_evaluated_position_ids):
            raise PortfolioRiskGenerationRunPersistenceError("risk_artifact_refs must match risk_evaluated_position_ids.")
        for position_id, artifact_ref in zip(self.risk_evaluated_position_ids, self.risk_artifact_refs):
            if artifact_ref.position_id != position_id:
                raise PortfolioRiskGenerationRunPersistenceError("risk_artifact_refs position order mismatch.")
        if len({ref.artifact_id for ref in self.risk_artifact_refs}) != len(self.risk_artifact_refs):
            raise PortfolioRiskGenerationRunPersistenceError("risk_artifact_refs must not duplicate artifact_id.")

        if len(self.monitoring_artifact_refs) != len(self.succeeded_position_ids):
            raise PortfolioRiskGenerationRunPersistenceError("monitoring_artifact_refs must match succeeded_position_ids.")
        for position_id, artifact_ref in zip(self.succeeded_position_ids, self.monitoring_artifact_refs):
            if artifact_ref.position_id != position_id:
                raise PortfolioRiskGenerationRunPersistenceError("monitoring_artifact_refs position order mismatch.")
        if len({ref.artifact_id for ref in self.monitoring_artifact_refs}) != len(self.monitoring_artifact_refs):
            raise PortfolioRiskGenerationRunPersistenceError("monitoring_artifact_refs must not duplicate artifact_id.")


@dataclass(frozen=True)
class PortfolioRiskGenerationRunSaveResult:
    """Immutable result for one append-only run record save operation."""

    calculation_id: str
    record_checksum: str
    status: PortfolioRiskGenerationRunSaveStatus | str

    def __post_init__(self):
        _require_text(self.calculation_id, "calculation_id")
        _require_text(self.record_checksum, "record_checksum")
        try:
            status = PortfolioRiskGenerationRunSaveStatus(self.status)
        except ValueError as exc:
            raise PortfolioRiskGenerationRunPersistenceError("status must be a valid save status.") from exc
        object.__setattr__(self, "status", status)


@runtime_checkable
class PortfolioRiskGenerationRunRepository(Protocol):
    """DB-agnostic append-only repository contract for immutable run records.

    First save returns INSERTED. Saving the same calculation_id with the same
    record_checksum is idempotent. Saving the same calculation_id with a different
    record_checksum must raise PortfolioRiskGenerationRunConflictError. If stored
    data is corrupted, corruption takes precedence. Missing records return None.
    """

    def save(self, record: PortfolioRiskGenerationRunRecord) -> PortfolioRiskGenerationRunSaveResult:
        """Persist one immutable run record or return an idempotent save result."""
        ...

    def get_by_calculation_id(self, calculation_id: str) -> PortfolioRiskGenerationRunRecord | None:
        """Return a validated run record by calculation_id, or None when absent."""
        ...


def record_checksum(record: PortfolioRiskGenerationRunRecord) -> str:
    return _canonical_sha256(_record_checksum_payload(record))


def _record_checksum_payload(record: PortfolioRiskGenerationRunRecord) -> dict[str, Any]:
    return {
        "calculation_id": record.calculation_id,
        "generation_key": record.generation_key,
        "portfolio_id": record.portfolio_id,
        "snapshot_id": record.snapshot_id,
        "snapshot_checksum": record.snapshot_checksum,
        "analysis_date": record.analysis_date,
        "valuation_date": record.valuation_date,
        "status": record.status,
        "attempted_position_ids": record.attempted_position_ids,
        "risk_evaluated_position_ids": record.risk_evaluated_position_ids,
        "succeeded_position_ids": record.succeeded_position_ids,
        "failed_position_ids": record.failed_position_ids,
        "risk_artifact_refs": tuple(
            {
                "position_id": ref.position_id,
                "artifact_id": ref.artifact_id,
                "artifact_checksum": ref.artifact_checksum,
            }
            for ref in record.risk_artifact_refs
        ),
        "monitoring_artifact_refs": tuple(
            {
                "position_id": ref.position_id,
                "artifact_id": ref.artifact_id,
            }
            for ref in record.monitoring_artifact_refs
        ),
        "issues": tuple(
            {
                "stage": issue.stage,
                "message": issue.message,
                "position_id": issue.position_id,
            }
            for issue in record.issues
        ),
        "warnings": tuple(
            {
                "stage": warning.stage,
                "message": warning.message,
                "position_id": warning.position_id,
            }
            for warning in record.warnings
        ),
        "created_at": record.created_at,
        "schema_version": PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1,
    }


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_dumps(payload).encode("utf-8")).hexdigest()


def _canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        _stable_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _stable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_stable_value(item) for item in value]
    if isinstance(value, list):
        return [_stable_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    return value


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} must be a non-empty string.")
    return value


def _require_exact_date(value: object, field_name: str) -> date:
    if type(value) is not date:
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} must be a date.")
    return value


def _require_timezone_aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} must be timezone-aware.")
    return value


def _require_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} must be a tuple.")
    for item in value:
        _require_text(item, field_name)
    return value


def _require_unique(value: tuple[str, ...], field_name: str) -> None:
    if len(set(value)) != len(value):
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} must not contain duplicates.")


def _require_typed_tuple(value: object, expected_type: type, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} must be a tuple.")
    if not all(isinstance(item, expected_type) for item in value):
        raise PortfolioRiskGenerationRunPersistenceError(f"{field_name} has invalid items.")
