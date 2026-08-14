import hashlib
import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from enum import StrEnum
from math import isfinite
from typing import Any
from typing import Mapping

from risk.checksum import RiskChecksumGenerator
from risk.checksum import RiskChecksumMismatchError
from risk.risk_artifact import RiskArtifact
from risk.risk_assessment import RiskAssessment
from risk.risk_context import RiskContext
from risk.risk_definition import RiskCategory
from risk.risk_definition import RiskSeverity
from risk.risk_signal import RiskSignal


RISK_ARTIFACT_SCHEMA_VERSION_V1 = "1"
RISK_ARTIFACT_CODEC_VERSION_V1 = "1"

_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "codec_version",
        "artifact",
        "serialization_checksum",
    }
)

_ARTIFACT_FIELDS = frozenset(
    {
        "artifact_id",
        "position_identity",
        "risk_assessment",
        "signals",
        "feature_lineage",
        "calculation_metadata",
        "created_at",
        "checksum",
    }
)

_ASSESSMENT_FIELDS = frozenset(
    {
        "portfolio_id",
        "symbol",
        "overall_risk_level",
        "signals",
        "assessment_date",
        "checksum",
    }
)

_SIGNAL_FIELDS = frozenset(
    {
        "risk_id",
        "symbol",
        "category",
        "severity",
        "trigger_reason",
        "created_at",
    }
)


class RiskArtifactCodecError(ValueError):
    """Raised when RiskArtifact persistence encoding or decoding fails closed."""


@dataclass(frozen=True)
class RiskArtifactCodec:
    """Encode and decode RiskArtifact objects through a canonical JSON envelope."""

    checksum_generator: RiskChecksumGenerator = RiskChecksumGenerator()

    def encode(self, artifact: RiskArtifact) -> str:
        if not isinstance(artifact, RiskArtifact):
            raise RiskArtifactCodecError("RiskArtifactCodec.encode requires RiskArtifact.")
        if not isinstance(artifact.checksum, str) or not artifact.checksum:
            raise RiskArtifactCodecError("RiskArtifactCodec requires artifact checksum.")
        try:
            envelope = {
                "schema_version": RISK_ARTIFACT_SCHEMA_VERSION_V1,
                "codec_version": RISK_ARTIFACT_CODEC_VERSION_V1,
                "artifact": _artifact_payload(artifact),
            }
            envelope["serialization_checksum"] = serialization_checksum(envelope)
            return canonical_json_dumps(envelope)
        except RiskArtifactCodecError:
            raise
        except (TypeError, ValueError) as exc:
            raise RiskArtifactCodecError(str(exc)) from exc

    def decode(self, payload: str) -> RiskArtifact:
        if not isinstance(payload, str):
            raise RiskArtifactCodecError("RiskArtifactCodec.decode requires JSON string payload.")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RiskArtifactCodecError("RiskArtifact payload must be valid JSON.") from exc
        if not isinstance(decoded, Mapping):
            raise RiskArtifactCodecError("RiskArtifact envelope must be a JSON object.")

        envelope = _require_exact_mapping(decoded, _ENVELOPE_FIELDS, "RiskArtifact envelope")
        _validate_version(
            envelope["schema_version"],
            RISK_ARTIFACT_SCHEMA_VERSION_V1,
            "RiskArtifact schema_version",
        )
        _validate_version(
            envelope["codec_version"],
            RISK_ARTIFACT_CODEC_VERSION_V1,
            "RiskArtifact codec_version",
        )
        _verify_serialization_checksum(envelope)

        artifact_payload = _require_exact_mapping(envelope["artifact"], _ARTIFACT_FIELDS, "RiskArtifact payload")
        try:
            artifact_signals = tuple(
                _deserialize_signal(item)
                for item in _require_list(artifact_payload["signals"], "artifact.signals")
            )
            assessment_payload = _require_exact_mapping(
                artifact_payload["risk_assessment"],
                _ASSESSMENT_FIELDS,
                "risk_assessment",
            )
            assessment_signals = tuple(
                _deserialize_signal(item)
                for item in _require_list(assessment_payload["signals"], "risk_assessment.signals")
            )
            if artifact_signals != assessment_signals:
                raise RiskArtifactCodecError("RiskArtifact signals must match RiskAssessment signals.")

            assessment = RiskAssessment.from_signals(
                portfolio_id=_require_string(assessment_payload["portfolio_id"], "risk_assessment.portfolio_id"),
                symbol=_require_string(assessment_payload["symbol"], "risk_assessment.symbol"),
                signals=assessment_signals,
                assessment_date=_parse_date(assessment_payload["assessment_date"], "risk_assessment.assessment_date"),
                checksum=_optional_string(assessment_payload["checksum"], "risk_assessment.checksum"),
            )
            persisted_severity = RiskSeverity(
                _require_string(assessment_payload["overall_risk_level"], "risk_assessment.overall_risk_level")
            )
            if assessment.overall_risk_level != persisted_severity:
                raise RiskArtifactCodecError("RiskAssessment persisted severity mismatch.")

            artifact = RiskArtifact(
                artifact_id=_require_string(artifact_payload["artifact_id"], "artifact_id"),
                position_identity=_decode_mapping(artifact_payload["position_identity"], "position_identity"),
                risk_assessment=assessment,
                signals=artifact_signals,
                feature_lineage=_decode_mapping(artifact_payload["feature_lineage"], "feature_lineage"),
                calculation_metadata=_decode_mapping(
                    artifact_payload["calculation_metadata"],
                    "calculation_metadata",
                ),
                created_at=_parse_datetime(artifact_payload["created_at"], "created_at"),
                checksum=_require_string(artifact_payload["checksum"], "checksum"),
            )
            _validate_reconstructed_invariants(artifact)
            context = _build_checksum_context(artifact)
            self.checksum_generator.verify(artifact, context, artifact.checksum)
            return artifact
        except RiskArtifactCodecError:
            raise
        except (TypeError, ValueError, RiskChecksumMismatchError) as exc:
            raise RiskArtifactCodecError(str(exc)) from exc


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    """Return canonical JSON for persisted RiskArtifact envelopes."""

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def serialization_checksum(envelope: Mapping[str, Any]) -> str:
    checksum_payload = {
        key: envelope[key]
        for key in sorted(envelope)
        if key != "serialization_checksum"
    }
    encoded = canonical_json_dumps(checksum_payload)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _artifact_payload(artifact: RiskArtifact) -> dict[str, Any]:
    if artifact.signals != artifact.risk_assessment.signals:
        raise RiskArtifactCodecError("RiskArtifact signals must match RiskAssessment signals.")
    return {
        "artifact_id": artifact.artifact_id,
        "position_identity": _encode_mapping(artifact.position_identity, "position_identity"),
        "risk_assessment": _assessment_payload(artifact.risk_assessment),
        "signals": [_signal_payload(signal) for signal in artifact.signals],
        "feature_lineage": _encode_mapping(artifact.feature_lineage, "feature_lineage"),
        "calculation_metadata": _encode_mapping(artifact.calculation_metadata, "calculation_metadata"),
        "created_at": _datetime_to_iso(artifact.created_at, "created_at"),
        "checksum": artifact.checksum,
    }


def _assessment_payload(assessment: RiskAssessment) -> dict[str, Any]:
    if not isinstance(assessment, RiskAssessment):
        raise RiskArtifactCodecError("RiskArtifact requires RiskAssessment.")
    return {
        "portfolio_id": assessment.portfolio_id,
        "symbol": assessment.symbol,
        "overall_risk_level": assessment.overall_risk_level.value,
        "signals": [_signal_payload(signal) for signal in assessment.signals],
        "assessment_date": assessment.assessment_date.isoformat(),
        "checksum": assessment.checksum,
    }


def _signal_payload(signal: RiskSignal) -> dict[str, Any]:
    if not isinstance(signal, RiskSignal):
        raise RiskArtifactCodecError("RiskArtifact signals must contain RiskSignal.")
    return {
        "risk_id": signal.risk_id,
        "symbol": signal.symbol,
        "category": signal.category.value,
        "severity": signal.severity.value,
        "trigger_reason": signal.trigger_reason,
        "created_at": _datetime_to_iso(signal.created_at, "signal.created_at"),
    }


def _deserialize_signal(payload: Any) -> RiskSignal:
    signal_payload = _require_exact_mapping(payload, _SIGNAL_FIELDS, "RiskSignal payload")
    return RiskSignal(
        risk_id=_require_string(signal_payload["risk_id"], "risk_id"),
        symbol=_require_string(signal_payload["symbol"], "symbol"),
        category=RiskCategory(_require_string(signal_payload["category"], "category")),
        severity=RiskSeverity(_require_string(signal_payload["severity"], "severity")),
        trigger_reason=_require_string(signal_payload["trigger_reason"], "trigger_reason"),
        created_at=_parse_datetime(signal_payload["created_at"], "signal.created_at"),
    )


def _encode_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RiskArtifactCodecError(f"{field_name} must be a mapping.")
    encoded: dict[str, Any] = {}
    for key in sorted(value):
        if not isinstance(key, str):
            raise RiskArtifactCodecError(f"{field_name} keys must be strings.")
        encoded[key] = _encode_metadata_value(value[key], f"{field_name}.{key}")
    return encoded


def _decode_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RiskArtifactCodecError(f"{field_name} must be a mapping.")
    decoded: dict[str, Any] = {}
    for key in sorted(value):
        if not isinstance(key, str):
            raise RiskArtifactCodecError(f"{field_name} keys must be strings.")
        decoded[key] = _decode_metadata_value(value[key], f"{field_name}.{key}")
    return decoded


def _encode_metadata_value(value: Any, field_name: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise RiskArtifactCodecError(f"{field_name} must be finite.")
        return {"__type__": "float", "value": value}
    if isinstance(value, Decimal):
        return {"__type__": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"__type__": "datetime", "value": _datetime_to_iso(value, field_name)}
    if isinstance(value, date):
        return {"__type__": "date", "value": value.isoformat()}
    if isinstance(value, StrEnum):
        return {"__type__": "enum", "value": value.value}
    if isinstance(value, tuple):
        return {"__type__": "tuple", "value": [_encode_metadata_value(item, field_name) for item in value]}
    if isinstance(value, list):
        return {"__type__": "list", "value": [_encode_metadata_value(item, field_name) for item in value]}
    if isinstance(value, Mapping):
        return {"__type__": "mapping", "value": _encode_mapping(value, field_name)}
    raise RiskArtifactCodecError(f"{field_name} has unsupported metadata type.")


def _decode_metadata_value(value: Any, field_name: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise RiskArtifactCodecError(f"{field_name} must be finite.")
        return value
    if not isinstance(value, Mapping):
        raise RiskArtifactCodecError(f"{field_name} has unsupported metadata type.")
    type_name = _require_string(value.get("__type__"), f"{field_name}.__type__")
    if set(value.keys()) != {"__type__", "value"}:
        raise RiskArtifactCodecError(f"{field_name} typed value has unknown fields.")
    raw_value = value["value"]
    if type_name == "float":
        if not isinstance(raw_value, (float, int)) or isinstance(raw_value, bool) or not isfinite(float(raw_value)):
            raise RiskArtifactCodecError(f"{field_name} float value must be finite.")
        return float(raw_value)
    if type_name == "decimal":
        if not isinstance(raw_value, str):
            raise RiskArtifactCodecError(f"{field_name} decimal value must be a string.")
        try:
            return Decimal(raw_value)
        except InvalidOperation as exc:
            raise RiskArtifactCodecError(f"{field_name} decimal value must be valid.") from exc
    if type_name == "datetime":
        return _parse_datetime(raw_value, field_name)
    if type_name == "date":
        return _parse_date(raw_value, field_name)
    if type_name == "tuple":
        return tuple(_decode_metadata_value(item, field_name) for item in _require_list(raw_value, field_name))
    if type_name == "list":
        return [_decode_metadata_value(item, field_name) for item in _require_list(raw_value, field_name)]
    if type_name == "mapping":
        return _decode_mapping(raw_value, field_name)
    if type_name == "enum":
        raise RiskArtifactCodecError(f"{field_name} enum metadata type is not reconstructable.")
    raise RiskArtifactCodecError(f"{field_name} has unsupported metadata type.")


def _build_checksum_context(artifact: RiskArtifact) -> RiskContext:
    feature_version = artifact.feature_lineage.get("feature_version")
    model_version = artifact.feature_lineage.get("model_version")
    portfolio_id = artifact.calculation_metadata.get("portfolio_id")
    symbol = artifact.calculation_metadata.get("symbol")
    analysis_date = artifact.calculation_metadata.get("analysis_date")
    calculation_id = artifact.calculation_metadata.get("calculation_id")

    return RiskContext(
        portfolio_id=_require_string(portfolio_id, "calculation_metadata.portfolio_id"),
        symbol=_require_string(symbol, "calculation_metadata.symbol"),
        analysis_date=_metadata_date(analysis_date, "calculation_metadata.analysis_date"),
        feature_version=_require_string(feature_version, "feature_lineage.feature_version"),
        model_version=_optional_string(model_version, "feature_lineage.model_version"),
        calculation_id=_require_string(calculation_id, "calculation_metadata.calculation_id"),
    )


def _validate_reconstructed_invariants(artifact: RiskArtifact) -> None:
    if artifact.signals != artifact.risk_assessment.signals:
        raise RiskArtifactCodecError("RiskArtifact signals must match RiskAssessment signals.")
    context = _build_checksum_context(artifact)
    if artifact.risk_assessment.portfolio_id != context.portfolio_id:
        raise RiskArtifactCodecError("RiskArtifact portfolio_id mismatch.")
    if artifact.risk_assessment.symbol != context.symbol:
        raise RiskArtifactCodecError("RiskArtifact symbol mismatch.")
    position_symbol = artifact.position_identity.get("symbol")
    if position_symbol is not None and position_symbol != context.symbol:
        raise RiskArtifactCodecError("RiskArtifact position symbol mismatch.")
    for signal in artifact.signals:
        if signal.symbol != context.symbol:
            raise RiskArtifactCodecError("RiskArtifact signal symbol mismatch.")


def _verify_serialization_checksum(envelope: Mapping[str, Any]) -> None:
    expected = _require_string(envelope["serialization_checksum"], "serialization_checksum")
    actual = serialization_checksum(envelope)
    if actual != expected:
        raise RiskArtifactCodecError(
            f"RiskArtifact serialization checksum mismatch: expected {expected}, got {actual}."
        )


def _validate_version(value: Any, expected: str, field_name: str) -> None:
    if value != expected:
        raise RiskArtifactCodecError(f"Unsupported {field_name}: {value}.")


def _require_exact_mapping(value: Any, expected_fields: frozenset[str], field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RiskArtifactCodecError(f"{field_name} must be a mapping.")
    actual_fields = set(value.keys())
    missing = sorted(expected_fields.difference(actual_fields))
    unknown = sorted(actual_fields.difference(expected_fields))
    if missing:
        raise RiskArtifactCodecError(f"{field_name} missing required fields: {', '.join(missing)}.")
    if unknown:
        raise RiskArtifactCodecError(f"{field_name} contains unknown fields: {', '.join(unknown)}.")
    return dict(value)


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise RiskArtifactCodecError(f"{field_name} must be a JSON array.")
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RiskArtifactCodecError(f"{field_name} must be a non-empty string.")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, field_name)


def _metadata_date(value: Any, field_name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return _parse_date(value, field_name)


def _datetime_to_iso(value: datetime, field_name: str) -> str:
    if not isinstance(value, datetime):
        raise RiskArtifactCodecError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise RiskArtifactCodecError(f"{field_name} must be timezone-aware.")
    return value.isoformat()


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise RiskArtifactCodecError(f"{field_name} must be an ISO-8601 datetime string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RiskArtifactCodecError(f"{field_name} must be a valid ISO-8601 datetime.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RiskArtifactCodecError(f"{field_name} must be timezone-aware.")
    return parsed


def _parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise RiskArtifactCodecError(f"{field_name} must be an ISO date string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RiskArtifactCodecError(f"{field_name} must be a valid ISO date.") from exc
