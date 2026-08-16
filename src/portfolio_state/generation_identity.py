import hashlib
import json
from datetime import date
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from typing import Mapping


GENERATION_IDENTITY_SCHEMA_VERSION = "2"


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    """Encode generation identity material with stable ordering."""

    return json.dumps(_stable_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_dumps(payload).encode("utf-8")).hexdigest()


def build_generation_identity_material(
    *,
    portfolio_id: str,
    snapshot_id: str,
    snapshot_checksum: str,
    as_of_date: date,
    valuation_date: date,
    feature_version: str,
    feature_set_checksum: str,
    model_version: str | None,
    risk_definition_version: str,
    risk_policy_version: str,
    monitoring_policy_version: str,
    generation_schema_version: str = GENERATION_IDENTITY_SCHEMA_VERSION,
) -> dict[str, Any]:
    return {
        "generation_schema_version": generation_schema_version,
        "portfolio_id": portfolio_id,
        "snapshot_id": snapshot_id,
        "snapshot_checksum": snapshot_checksum,
        "as_of_date": as_of_date,
        "valuation_date": valuation_date,
        "feature_version": feature_version,
        "feature_set_checksum": feature_set_checksum,
        "model_version": _nullable_text(model_version),
        "risk_definition_version": risk_definition_version,
        "risk_policy_version": risk_policy_version,
        "monitoring_policy_version": monitoring_policy_version,
    }


def generate_generation_key(identity_material: Mapping[str, Any]) -> str:
    return f"portfolio_risk_generation_{canonical_sha256(identity_material)}"


def generate_calculation_id(generation_key: str) -> str:
    digest = hashlib.sha256(generation_key.encode("utf-8")).hexdigest()
    return f"portfolio_risk_calc_{digest}"


def _stable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_stable_value(item) for item in value]
    if isinstance(value, list):
        return [_stable_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    return value


def _nullable_text(value: str | None) -> str:
    return "<none>" if value is None else value
