from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from risk_evaluation import PRODUCTION_TECHNICAL_RISK_POLICY_V1


PRODUCTION_POLICY_PIN_SCHEMA_VERSION = "1"


class ProductionPolicyPinError(ValueError):
    """Raised when controlled production policy pinning is invalid."""


@dataclass(frozen=True)
class ProductionPolicyPin:
    schema_version: str
    policy_pin_version: str
    policy_version: str
    policy_source_key: str

    def __post_init__(self) -> None:
        if self.schema_version != PRODUCTION_POLICY_PIN_SCHEMA_VERSION:
            raise ProductionPolicyPinError("unsupported production policy pin schema_version.")
        object.__setattr__(self, "policy_pin_version", _require_text(self.policy_pin_version, "policy_pin_version"))
        object.__setattr__(self, "policy_version", _require_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "policy_source_key", _require_text(self.policy_source_key, "policy_source_key"))
        if self.policy_version != PRODUCTION_TECHNICAL_RISK_POLICY_V1:
            raise ProductionPolicyPinError("unsupported production technical risk policy version.")


def load_production_policy_pin(path: str | Path) -> ProductionPolicyPin:
    payload = _read_json(path)
    _require_exact_fields(
        payload,
        frozenset({"schema_version", "policy_pin_version", "policy_version", "policy_source_key"}),
        "production policy pin",
    )
    return ProductionPolicyPin(
        schema_version=_require_text(payload["schema_version"], "schema_version"),
        policy_pin_version=_require_text(payload["policy_pin_version"], "policy_pin_version"),
        policy_version=_require_text(payload["policy_version"], "policy_version"),
        policy_source_key=_require_text(payload["policy_source_key"], "policy_source_key"),
    )


def _read_json(path: str | Path) -> dict[str, Any]:
    source_path = Path(path)
    if not source_path.exists():
        raise ProductionPolicyPinError("production policy pin file does not exist.")
    if not source_path.is_file():
        raise ProductionPolicyPinError("production policy pin path must be a file.")
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except ProductionPolicyPinError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionPolicyPinError("production policy pin file cannot be loaded.") from exc
    if not isinstance(payload, dict):
        raise ProductionPolicyPinError("production policy pin document must be a JSON object.")
    return payload


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProductionPolicyPinError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_exact_fields(payload: dict[str, Any], expected_fields: frozenset[str], label: str) -> None:
    actual_fields = set(payload)
    missing = sorted(expected_fields - actual_fields)
    if missing:
        raise ProductionPolicyPinError(f"{label} missing required field: {missing[0]}")
    unknown = sorted(actual_fields - expected_fields)
    if unknown:
        raise ProductionPolicyPinError(f"{label} contains unknown field: {unknown[0]}")


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ProductionPolicyPinError(f"{field_name} must be a non-empty single-line string.")
    return value
