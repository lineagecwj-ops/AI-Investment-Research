import hashlib
import json
from typing import Any
from typing import Mapping


ARTIFACT_IDENTITY_SCHEMA_VERSION = "1"


def position_identity_digest(position_id: str) -> str:
    """Return a filesystem-safe deterministic digest for a raw position_id."""

    if not isinstance(position_id, str) or not position_id:
        raise ValueError("position_id must be a non-empty string.")
    return hashlib.sha256(position_id.encode("utf-8")).hexdigest()


def build_risk_artifact_id(calculation_id: str, position_id: str) -> str:
    return _build_artifact_id(calculation_id, position_id, "risk")


def build_monitoring_artifact_id(calculation_id: str, position_id: str) -> str:
    return _build_artifact_id(calculation_id, position_id, "monitoring")


def _build_artifact_id(calculation_id: str, position_id: str, artifact_type: str) -> str:
    if not isinstance(calculation_id, str) or not calculation_id:
        raise ValueError("calculation_id must be a non-empty string.")
    digest = hashlib.sha256(
        _canonical_json_dumps(
            {
                "schema_version": ARTIFACT_IDENTITY_SCHEMA_VERSION,
                "calculation_id": calculation_id,
                "artifact_type": artifact_type,
                "position_identity_digest": position_identity_digest(position_id),
            }
        ).encode("utf-8")
    ).hexdigest()
    return f"portfolio_{artifact_type}_artifact_{digest}"


def _canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
