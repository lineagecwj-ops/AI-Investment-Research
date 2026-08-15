import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Any
from typing import Mapping

from portfolio_generation import PortfolioRiskGenerationStatus
from risk_persistence.portfolio_run_contracts import PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunArtifactRef
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunIssue
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunMonitoringArtifactRef
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunPersistenceError
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunRecord
from risk_persistence.portfolio_run_contracts import PortfolioRiskGenerationRunWarning


PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1 = "1"

_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "codec_version",
        "record",
    }
)

_RECORD_FIELDS = frozenset(
    {
        "calculation_id",
        "generation_key",
        "portfolio_id",
        "snapshot_id",
        "snapshot_checksum",
        "analysis_date",
        "valuation_date",
        "status",
        "attempted_position_ids",
        "risk_evaluated_position_ids",
        "succeeded_position_ids",
        "failed_position_ids",
        "risk_artifact_refs",
        "monitoring_artifact_refs",
        "issues",
        "warnings",
        "created_at",
        "record_checksum",
    }
)

_RISK_REF_FIELDS = frozenset({"position_id", "artifact_id", "artifact_checksum"})
_MONITORING_REF_FIELDS = frozenset({"position_id", "artifact_id"})
_ISSUE_FIELDS = frozenset({"stage", "message", "position_id"})


class PortfolioRiskGenerationRunRecordCodecError(ValueError):
    """Raised when run record persistence encoding or decoding fails closed."""


@dataclass(frozen=True)
class PortfolioRiskGenerationRunRecordCodec:
    """Encode and decode PortfolioRiskGenerationRunRecord through canonical JSON."""

    def encode(self, record: PortfolioRiskGenerationRunRecord) -> str:
        if not isinstance(record, PortfolioRiskGenerationRunRecord):
            raise PortfolioRiskGenerationRunRecordCodecError(
                "PortfolioRiskGenerationRunRecordCodec.encode requires PortfolioRiskGenerationRunRecord."
            )
        try:
            envelope = {
                "schema_version": PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1,
                "codec_version": PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1,
                "record": _record_payload(record),
            }
            return canonical_json_dumps(envelope)
        except PortfolioRiskGenerationRunRecordCodecError:
            raise
        except (TypeError, ValueError) as exc:
            raise PortfolioRiskGenerationRunRecordCodecError(str(exc)) from exc

    def decode(self, payload: str) -> PortfolioRiskGenerationRunRecord:
        if not isinstance(payload, str):
            raise PortfolioRiskGenerationRunRecordCodecError("Run record payload must be a JSON string.")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PortfolioRiskGenerationRunRecordCodecError("Run record payload must be valid JSON.") from exc
        if not isinstance(decoded, Mapping):
            raise PortfolioRiskGenerationRunRecordCodecError("Run record envelope must be a JSON object.")

        envelope = _require_exact_mapping(decoded, _ENVELOPE_FIELDS, "run record envelope")
        _validate_version(
            envelope["schema_version"],
            PORTFOLIO_RUN_RECORD_SCHEMA_VERSION_V1,
            "run record schema_version",
        )
        _validate_version(
            envelope["codec_version"],
            PORTFOLIO_RUN_RECORD_CODEC_VERSION_V1,
            "run record codec_version",
        )
        record_payload = _require_exact_mapping(envelope["record"], _RECORD_FIELDS, "run record payload")
        try:
            return PortfolioRiskGenerationRunRecord(
                calculation_id=_require_string(record_payload["calculation_id"], "calculation_id"),
                generation_key=_require_string(record_payload["generation_key"], "generation_key"),
                portfolio_id=_require_string(record_payload["portfolio_id"], "portfolio_id"),
                snapshot_id=_require_string(record_payload["snapshot_id"], "snapshot_id"),
                snapshot_checksum=_require_string(record_payload["snapshot_checksum"], "snapshot_checksum"),
                analysis_date=_parse_date(record_payload["analysis_date"], "analysis_date"),
                valuation_date=_parse_date(record_payload["valuation_date"], "valuation_date"),
                status=PortfolioRiskGenerationStatus(_require_string(record_payload["status"], "status")),
                attempted_position_ids=_string_tuple(record_payload["attempted_position_ids"], "attempted_position_ids"),
                risk_evaluated_position_ids=_string_tuple(
                    record_payload["risk_evaluated_position_ids"],
                    "risk_evaluated_position_ids",
                ),
                succeeded_position_ids=_string_tuple(record_payload["succeeded_position_ids"], "succeeded_position_ids"),
                failed_position_ids=_string_tuple(record_payload["failed_position_ids"], "failed_position_ids"),
                risk_artifact_refs=tuple(
                    _risk_ref(item) for item in _require_list(record_payload["risk_artifact_refs"], "risk_artifact_refs")
                ),
                monitoring_artifact_refs=tuple(
                    _monitoring_ref(item)
                    for item in _require_list(record_payload["monitoring_artifact_refs"], "monitoring_artifact_refs")
                ),
                issues=tuple(_issue(item) for item in _require_list(record_payload["issues"], "issues")),
                warnings=tuple(_warning(item) for item in _require_list(record_payload["warnings"], "warnings")),
                created_at=_parse_datetime(record_payload["created_at"], "created_at"),
                record_checksum=_require_string(record_payload["record_checksum"], "record_checksum"),
            )
        except PortfolioRiskGenerationRunPersistenceError as exc:
            raise PortfolioRiskGenerationRunRecordCodecError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise PortfolioRiskGenerationRunRecordCodecError(str(exc)) from exc


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _record_payload(record: PortfolioRiskGenerationRunRecord) -> dict[str, Any]:
    return {
        "calculation_id": record.calculation_id,
        "generation_key": record.generation_key,
        "portfolio_id": record.portfolio_id,
        "snapshot_id": record.snapshot_id,
        "snapshot_checksum": record.snapshot_checksum,
        "analysis_date": record.analysis_date.isoformat(),
        "valuation_date": record.valuation_date.isoformat(),
        "status": record.status.value,
        "attempted_position_ids": list(record.attempted_position_ids),
        "risk_evaluated_position_ids": list(record.risk_evaluated_position_ids),
        "succeeded_position_ids": list(record.succeeded_position_ids),
        "failed_position_ids": list(record.failed_position_ids),
        "risk_artifact_refs": [
            {
                "position_id": ref.position_id,
                "artifact_id": ref.artifact_id,
                "artifact_checksum": ref.artifact_checksum,
            }
            for ref in record.risk_artifact_refs
        ],
        "monitoring_artifact_refs": [
            {
                "position_id": ref.position_id,
                "artifact_id": ref.artifact_id,
            }
            for ref in record.monitoring_artifact_refs
        ],
        "issues": [
            {
                "stage": issue.stage,
                "message": issue.message,
                "position_id": issue.position_id,
            }
            for issue in record.issues
        ],
        "warnings": [
            {
                "stage": warning.stage,
                "message": warning.message,
                "position_id": warning.position_id,
            }
            for warning in record.warnings
        ],
        "created_at": record.created_at.isoformat(),
        "record_checksum": record.record_checksum,
    }


def _risk_ref(payload: Any) -> PortfolioRiskGenerationRunArtifactRef:
    value = _require_exact_mapping(payload, _RISK_REF_FIELDS, "risk_artifact_ref")
    return PortfolioRiskGenerationRunArtifactRef(
        position_id=_require_string(value["position_id"], "risk_artifact_ref.position_id"),
        artifact_id=_require_string(value["artifact_id"], "risk_artifact_ref.artifact_id"),
        artifact_checksum=_require_string(value["artifact_checksum"], "risk_artifact_ref.artifact_checksum"),
    )


def _monitoring_ref(payload: Any) -> PortfolioRiskGenerationRunMonitoringArtifactRef:
    value = _require_exact_mapping(payload, _MONITORING_REF_FIELDS, "monitoring_artifact_ref")
    return PortfolioRiskGenerationRunMonitoringArtifactRef(
        position_id=_require_string(value["position_id"], "monitoring_artifact_ref.position_id"),
        artifact_id=_require_string(value["artifact_id"], "monitoring_artifact_ref.artifact_id"),
    )


def _issue(payload: Any) -> PortfolioRiskGenerationRunIssue:
    value = _require_exact_mapping(payload, _ISSUE_FIELDS, "issue")
    return PortfolioRiskGenerationRunIssue(
        stage=_require_string(value["stage"], "issue.stage"),
        message=_require_string(value["message"], "issue.message"),
        position_id=_optional_string(value["position_id"], "issue.position_id"),
    )


def _warning(payload: Any) -> PortfolioRiskGenerationRunWarning:
    value = _require_exact_mapping(payload, _ISSUE_FIELDS, "warning")
    return PortfolioRiskGenerationRunWarning(
        stage=_require_string(value["stage"], "warning.stage"),
        message=_require_string(value["message"], "warning.message"),
        position_id=_optional_string(value["position_id"], "warning.position_id"),
    )


def _require_exact_mapping(value: Any, expected_fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PortfolioRiskGenerationRunRecordCodecError(f"{label} must be a JSON object.")
    actual_fields = set(value.keys())
    if actual_fields != set(expected_fields):
        raise PortfolioRiskGenerationRunRecordCodecError(f"{label} fields mismatch.")
    return value


def _validate_version(value: Any, expected: str, label: str) -> None:
    if value != expected:
        raise PortfolioRiskGenerationRunRecordCodecError(f"Unsupported {label}: {value}.")


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PortfolioRiskGenerationRunRecordCodecError(f"{field_name} must be a non-empty string.")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name)


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PortfolioRiskGenerationRunRecordCodecError(f"{field_name} must be a JSON array.")
    return value


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    return tuple(_require_string(item, field_name) for item in _require_list(value, field_name))


def _parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise PortfolioRiskGenerationRunRecordCodecError(f"{field_name} must be an ISO date string.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PortfolioRiskGenerationRunRecordCodecError(f"{field_name} must be an ISO date string.") from exc
    return parsed


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise PortfolioRiskGenerationRunRecordCodecError(f"{field_name} must be an ISO datetime string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PortfolioRiskGenerationRunRecordCodecError(f"{field_name} must be an ISO datetime string.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortfolioRiskGenerationRunRecordCodecError(f"{field_name} must be timezone-aware.")
    return parsed
