import hashlib
import json
from datetime import date
from datetime import datetime
from enum import StrEnum
from typing import Any
from typing import Mapping

from risk.risk_definition import RiskCategory
from risk.risk_definition import RiskSeverity
from risk_monitoring.alert_candidate import AlertCandidate
from risk_monitoring.monitoring_artifact import RiskMonitoringArtifact
from risk_monitoring.monitoring_event import RiskMonitoringEvent
from risk_monitoring.monitoring_types import AlertLevel
from risk_monitoring.monitoring_types import AlertType
from risk_monitoring.monitoring_types import MonitoringState


RISK_MONITORING_ARTIFACT_SCHEMA_VERSION = "1"

_REQUIRED_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_id",
        "portfolio_id",
        "symbol",
        "monitoring_date",
        "source_risk_artifact_id",
        "source_risk_checksum",
        "monitoring_state",
        "overall_risk_level",
        "events",
        "alert_candidates",
        "lineage",
        "calculation_metadata",
        "policy_version",
        "created_at",
        "checksum",
        "serialization_checksum",
    }
)


class RiskMonitoringArtifactSerializationError(ValueError):
    """Raised when risk monitoring artifact serialization payloads are invalid."""


def serialize_risk_monitoring_artifact(artifact: RiskMonitoringArtifact) -> dict[str, Any]:
    """Return a deterministic JSON-compatible payload for a monitoring artifact."""

    if not isinstance(artifact, RiskMonitoringArtifact):
        raise RiskMonitoringArtifactSerializationError("Expected RiskMonitoringArtifact.")

    payload = {
        "schema_version": RISK_MONITORING_ARTIFACT_SCHEMA_VERSION,
        "artifact_id": artifact.artifact_id,
        "portfolio_id": artifact.portfolio_id,
        "symbol": artifact.symbol,
        "monitoring_date": _monitoring_date_for_payload(artifact),
        "source_risk_artifact_id": artifact.source_risk_artifact_id,
        "source_risk_checksum": artifact.source_risk_checksum,
        "monitoring_state": _stable_value(artifact.monitoring_state),
        "overall_risk_level": artifact.overall_risk_level,
        "events": [_event_payload(event) for event in sorted(artifact.events, key=lambda item: item.event_id)],
        "alert_candidates": [
            _alert_candidate_payload(alert) for alert in sorted(artifact.alert_candidates, key=lambda item: item.alert_id)
        ],
        "lineage": _stable_value(artifact.lineage),
        "calculation_metadata": _stable_value(artifact.calculation_metadata),
        "policy_version": artifact.policy_version,
        "created_at": _datetime_to_iso(artifact.created_at),
        "checksum": artifact.checksum,
    }
    payload["serialization_checksum"] = serialized_payload_checksum(payload)
    return dict(sorted(payload.items()))


def deserialize_risk_monitoring_artifact(payload: Mapping[str, Any]) -> RiskMonitoringArtifact:
    """Restore a monitoring artifact from a validated JSON-compatible payload."""

    if not isinstance(payload, Mapping):
        raise RiskMonitoringArtifactSerializationError("Serialized artifact payload must be a mapping.")
    _validate_required_fields(payload)
    _validate_schema_version(payload["schema_version"])
    _verify_serialization_checksum(payload)

    try:
        _parse_date(payload["monitoring_date"], "monitoring_date")
        events = tuple(_deserialize_event(event) for event in _require_sequence(payload["events"], "events"))
        alert_candidates = tuple(
            _deserialize_alert_candidate(alert)
            for alert in _require_sequence(payload["alert_candidates"], "alert_candidates")
        )
        lineage = _require_mapping(payload["lineage"], "lineage")
        calculation_metadata = _require_mapping(payload["calculation_metadata"], "calculation_metadata")
        return RiskMonitoringArtifact(
            artifact_id=_require_string(payload["artifact_id"], "artifact_id"),
            portfolio_id=_require_string(payload["portfolio_id"], "portfolio_id"),
            symbol=_require_string(payload["symbol"], "symbol"),
            monitoring_state=MonitoringState(_require_string(payload["monitoring_state"], "monitoring_state")),
            overall_risk_level=_require_string(payload["overall_risk_level"], "overall_risk_level"),
            source_risk_artifact_id=_require_string(payload["source_risk_artifact_id"], "source_risk_artifact_id"),
            source_risk_checksum=_require_string(payload["source_risk_checksum"], "source_risk_checksum"),
            events=events,
            alert_candidates=alert_candidates,
            policy_version=_require_string(payload["policy_version"], "policy_version"),
            lineage=lineage,
            calculation_metadata=calculation_metadata,
            created_at=_parse_datetime(payload["created_at"], "created_at"),
            checksum=payload["checksum"],
        )
    except (TypeError, ValueError) as error:
        raise RiskMonitoringArtifactSerializationError(str(error)) from error


def serialized_payload_checksum(payload: Mapping[str, Any]) -> str:
    """Return serialization integrity checksum excluding checksum carrier fields."""

    checksum_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"checksum", "serialization_checksum"}
    }
    encoded = canonical_json_dumps(checksum_payload)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    """Encode JSON with stable key ordering and compact separators."""

    return json.dumps(_stable_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validate_required_fields(payload: Mapping[str, Any]) -> None:
    missing = sorted(_REQUIRED_PAYLOAD_FIELDS.difference(payload.keys()))
    if missing:
        raise RiskMonitoringArtifactSerializationError(
            f"RiskMonitoringArtifact payload missing required fields: {', '.join(missing)}"
        )


def _validate_schema_version(value: Any) -> None:
    if value != RISK_MONITORING_ARTIFACT_SCHEMA_VERSION:
        raise RiskMonitoringArtifactSerializationError(f"Unsupported RiskMonitoringArtifact schema_version: {value}.")


def _verify_serialization_checksum(payload: Mapping[str, Any]) -> None:
    expected = _require_string(payload["serialization_checksum"], "serialization_checksum")
    actual = serialized_payload_checksum(payload)
    if actual != expected:
        raise RiskMonitoringArtifactSerializationError(
            f"RiskMonitoringArtifact serialization checksum mismatch: expected {expected}, got {actual}."
        )


def _event_payload(event: RiskMonitoringEvent) -> dict[str, Any]:
    if not isinstance(event, RiskMonitoringEvent):
        raise RiskMonitoringArtifactSerializationError("RiskMonitoringArtifact events must contain RiskMonitoringEvent.")
    return dict(
        sorted(
            {
                "event_id": event.event_id,
                "portfolio_id": event.portfolio_id,
                "symbol": event.symbol,
                "source_risk_id": event.source_risk_id,
                "risk_category": _stable_value(event.risk_category),
                "risk_severity": _stable_value(event.risk_severity),
                "monitoring_state": _stable_value(event.monitoring_state),
                "reason": event.reason,
                "created_at": _datetime_to_iso(event.created_at),
            }.items()
        )
    )


def _alert_candidate_payload(alert: AlertCandidate) -> dict[str, Any]:
    if not isinstance(alert, AlertCandidate):
        raise RiskMonitoringArtifactSerializationError(
            "RiskMonitoringArtifact alert_candidates must contain AlertCandidate."
        )
    return dict(
        sorted(
            {
                "alert_id": alert.alert_id,
                "portfolio_id": alert.portfolio_id,
                "symbol": alert.symbol,
                "alert_level": _stable_value(alert.alert_level),
                "alert_type": _stable_value(alert.alert_type),
                "reason": alert.reason,
                "source_event_ids": list(alert.source_event_ids),
                "created_at": _datetime_to_iso(alert.created_at),
            }.items()
        )
    )


def _deserialize_event(payload: Any) -> RiskMonitoringEvent:
    event_payload = _require_mapping(payload, "event")
    return RiskMonitoringEvent(
        event_id=_require_string(event_payload.get("event_id"), "event_id"),
        portfolio_id=_require_string(event_payload.get("portfolio_id"), "event.portfolio_id"),
        symbol=_require_string(event_payload.get("symbol"), "event.symbol"),
        source_risk_id=_require_string(event_payload.get("source_risk_id"), "source_risk_id"),
        risk_category=RiskCategory(_require_string(event_payload.get("risk_category"), "risk_category")),
        risk_severity=RiskSeverity(_require_string(event_payload.get("risk_severity"), "risk_severity")),
        monitoring_state=MonitoringState(_require_string(event_payload.get("monitoring_state"), "monitoring_state")),
        reason=_require_string(event_payload.get("reason"), "event.reason"),
        created_at=_parse_datetime(event_payload.get("created_at"), "event.created_at"),
    )


def _deserialize_alert_candidate(payload: Any) -> AlertCandidate:
    alert_payload = _require_mapping(payload, "alert_candidate")
    return AlertCandidate(
        alert_id=_require_string(alert_payload.get("alert_id"), "alert_id"),
        portfolio_id=_require_string(alert_payload.get("portfolio_id"), "alert_candidate.portfolio_id"),
        symbol=_require_string(alert_payload.get("symbol"), "alert_candidate.symbol"),
        alert_level=AlertLevel(_require_string(alert_payload.get("alert_level"), "alert_level")),
        alert_type=AlertType(_require_string(alert_payload.get("alert_type"), "alert_type")),
        reason=_require_string(alert_payload.get("reason"), "alert_candidate.reason"),
        source_event_ids=tuple(_require_sequence(alert_payload.get("source_event_ids"), "source_event_ids")),
        created_at=_parse_datetime(alert_payload.get("created_at"), "alert_candidate.created_at"),
    )


def _stable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _datetime_to_iso(value)
    if isinstance(value, date):
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


def _monitoring_date_for_payload(artifact: RiskMonitoringArtifact) -> str:
    monitoring_date = artifact.calculation_metadata.get("monitoring_date")
    if isinstance(monitoring_date, date):
        return monitoring_date.isoformat()
    if isinstance(monitoring_date, str):
        return _parse_date(monitoring_date, "calculation_metadata.monitoring_date").isoformat()
    return artifact.created_at.date().isoformat()


def _datetime_to_iso(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise RiskMonitoringArtifactSerializationError("Expected datetime value.")
    return value.isoformat()


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise RiskMonitoringArtifactSerializationError(f"{field_name} must be an ISO-8601 datetime string.")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise RiskMonitoringArtifactSerializationError(f"{field_name} must be a valid ISO-8601 datetime.") from error


def _parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise RiskMonitoringArtifactSerializationError(f"{field_name} must be an ISO date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise RiskMonitoringArtifactSerializationError(f"{field_name} must be a valid ISO date.") from error


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RiskMonitoringArtifactSerializationError(f"{field_name} must be a mapping.")
    return dict(value)


def _require_sequence(value: Any, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, list):
        raise RiskMonitoringArtifactSerializationError(f"{field_name} must be a JSON array.")
    return tuple(value)


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RiskMonitoringArtifactSerializationError(f"{field_name} must be a non-empty string.")
    return value
