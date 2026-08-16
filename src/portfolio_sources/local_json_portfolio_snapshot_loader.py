from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from pathlib import Path
from typing import Any

from portfolio_state import PortfolioPositionState
from portfolio_state import PortfolioSnapshot
from portfolio_state import PortfolioStateValidationError


LOCAL_JSON_PORTFOLIO_SOURCE_SCHEMA_VERSION = "1"
LOCAL_JSON_PORTFOLIO_SOURCE_TYPE = "local_json_portfolio_snapshot"
LOCAL_JSON_PORTFOLIO_MAX_BYTES = 1024 * 1024

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "portfolio_id",
        "snapshot_id",
        "as_of_date",
        "valuation_date",
        "snapshot_created_at",
        "source_lineage",
        "positions",
    }
)

_POSITION_FIELDS = frozenset(
    {
        "position_id",
        "symbol",
        "shares",
        "average_cost",
        "currency",
        "position_status",
        "holding_type",
        "acquisition_date",
    }
)

_SOURCE_LINEAGE_FIELDS = frozenset({"source_type", "source_version"})


class PortfolioSourceError(ValueError):
    """Raised when a production portfolio source cannot be loaded."""


class PortfolioSourceFormatError(PortfolioSourceError):
    """Raised when a production portfolio source document is invalid."""


@dataclass(frozen=True)
class LocalJsonPortfolioSnapshotLoader:
    """Load a strict local JSON portfolio snapshot into the portfolio_state domain contract."""

    max_bytes: int = LOCAL_JSON_PORTFOLIO_MAX_BYTES

    def __post_init__(self) -> None:
        if isinstance(self.max_bytes, bool) or not isinstance(self.max_bytes, int) or self.max_bytes <= 0:
            raise PortfolioSourceError("max_bytes must be a positive integer.")

    def load(self, path: str | Path) -> PortfolioSnapshot:
        source_path = self._resolve_source_path(path)
        source_bytes = self._read_source_bytes(source_path)
        payload = self._parse_json(source_bytes)
        return self._build_snapshot(payload)

    def _resolve_source_path(self, path: str | Path) -> Path:
        if isinstance(path, str) and not path:
            raise PortfolioSourceError("portfolio source path must be non-empty.")
        try:
            source_path = Path(path).expanduser().resolve()
        except (TypeError, RuntimeError, OSError) as exc:
            raise PortfolioSourceError("portfolio source path must be path-like.") from exc
        if not source_path.exists():
            raise PortfolioSourceError("portfolio source file does not exist.")
        if not source_path.is_file():
            raise PortfolioSourceError("portfolio source path must be a file.")
        try:
            if source_path.stat().st_size > self.max_bytes:
                raise PortfolioSourceFormatError("portfolio source file exceeds maximum size.")
        except OSError as exc:
            raise PortfolioSourceError("portfolio source file cannot be inspected.") from exc
        return source_path

    def _read_source_bytes(self, source_path: Path) -> bytes:
        try:
            return source_path.read_bytes()
        except OSError as exc:
            raise PortfolioSourceError("portfolio source file cannot be read.") from exc

    def _parse_json(self, source_bytes: bytes) -> dict[str, Any]:
        if len(source_bytes) > self.max_bytes:
            raise PortfolioSourceFormatError("portfolio source file exceeds maximum size.")
        try:
            text = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PortfolioSourceFormatError("portfolio source file must be UTF-8.") from exc
        try:
            payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except PortfolioSourceFormatError:
            raise
        except json.JSONDecodeError as exc:
            raise PortfolioSourceFormatError("portfolio source file must contain valid JSON.") from exc
        if not isinstance(payload, dict):
            raise PortfolioSourceFormatError("portfolio source document must be a JSON object.")
        return payload

    def _build_snapshot(self, payload: dict[str, Any]) -> PortfolioSnapshot:
        _require_exact_fields(payload, _TOP_LEVEL_FIELDS, "portfolio source document")
        schema_version = _require_text(payload["schema_version"], "schema_version")
        if schema_version != LOCAL_JSON_PORTFOLIO_SOURCE_SCHEMA_VERSION:
            raise PortfolioSourceFormatError("unsupported portfolio source schema_version.")
        portfolio_id = _require_text(payload["portfolio_id"], "portfolio_id")
        positions_payload = payload["positions"]
        if not isinstance(positions_payload, list):
            raise PortfolioSourceFormatError("positions must be a JSON array.")
        positions = tuple(
            self._build_position(portfolio_id, position_payload, index)
            for index, position_payload in enumerate(positions_payload)
        )
        try:
            return PortfolioSnapshot(
                snapshot_id=_require_text(payload["snapshot_id"], "snapshot_id"),
                portfolio_id=portfolio_id,
                as_of_date=_parse_date(payload["as_of_date"], "as_of_date"),
                valuation_date=_parse_date(payload["valuation_date"], "valuation_date"),
                positions=positions,
                created_at=_parse_datetime(payload["snapshot_created_at"], "snapshot_created_at"),
                source_lineage=_parse_source_lineage(payload["source_lineage"]),
            )
        except PortfolioStateValidationError as exc:
            raise PortfolioSourceFormatError(f"portfolio snapshot domain validation failed: {exc}") from exc

    def _build_position(
        self,
        portfolio_id: str,
        payload: object,
        index: int,
    ) -> PortfolioPositionState:
        if not isinstance(payload, dict):
            raise PortfolioSourceFormatError(f"position[{index}] must be a JSON object.")
        _require_exact_fields(payload, _POSITION_FIELDS, f"position[{index}]")
        position_id = _require_text(payload["position_id"], f"position[{index}].position_id")
        try:
            return PortfolioPositionState(
                portfolio_id=portfolio_id,
                position_id=position_id,
                symbol=_require_text(payload["symbol"], f"position[{index}].symbol"),
                shares=_parse_decimal_string(payload["shares"], f"position[{index}].shares"),
                average_cost=_parse_decimal_string(payload["average_cost"], f"position[{index}].average_cost"),
                currency=_require_text(payload["currency"], f"position[{index}].currency"),
                position_status=_require_text(payload["position_status"], f"position[{index}].position_status"),
                holding_type=_require_text(payload["holding_type"], f"position[{index}].holding_type"),
                acquisition_date=_parse_date(payload["acquisition_date"], f"position[{index}].acquisition_date"),
            )
        except PortfolioStateValidationError as exc:
            raise PortfolioSourceFormatError(f"position[{index}] domain validation failed: {exc}") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    duplicates: list[str] = []
    for key, value in pairs:
        if key in result:
            duplicates.append(key)
        result[key] = value
    if duplicates:
        raise PortfolioSourceFormatError(f"duplicate JSON key: {duplicates[0]}")
    return result


def _require_exact_fields(payload: dict[str, Any], expected_fields: frozenset[str], label: str) -> None:
    actual_fields = set(payload)
    missing = sorted(expected_fields - actual_fields)
    if missing:
        raise PortfolioSourceFormatError(f"{label} missing required field: {missing[0]}")
    unknown = sorted(actual_fields - expected_fields)
    if unknown:
        raise PortfolioSourceFormatError(f"{label} contains unknown field: {unknown[0]}")


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PortfolioSourceFormatError(f"{field_name} must be a non-empty string.")
    return value


def _parse_decimal_string(value: object, field_name: str) -> Decimal:
    if not isinstance(value, str) or not value:
        raise PortfolioSourceFormatError(f"{field_name} must be a non-empty decimal string.")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise PortfolioSourceFormatError(f"{field_name} must be a valid decimal string.") from exc


def _parse_date(value: object, field_name: str) -> date:
    text = _require_text(value, field_name)
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        raise PortfolioSourceFormatError(f"{field_name} must be an ISO date string.")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise PortfolioSourceFormatError(f"{field_name} must be a valid ISO date.") from exc
    if parsed.isoformat() != text:
        raise PortfolioSourceFormatError(f"{field_name} must be an exact ISO date.")
    return parsed


def _parse_datetime(value: object, field_name: str) -> datetime:
    text = _require_text(value, field_name)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PortfolioSourceFormatError(f"{field_name} must be a valid ISO datetime.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortfolioSourceFormatError(f"{field_name} must be timezone-aware.")
    return parsed


def _parse_source_lineage(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise PortfolioSourceFormatError("source_lineage must be a JSON object.")
    _require_exact_fields(value, _SOURCE_LINEAGE_FIELDS, "source_lineage")
    source_type = _require_text(value["source_type"], "source_lineage.source_type")
    source_version = _require_text(value["source_version"], "source_lineage.source_version")
    if source_type != LOCAL_JSON_PORTFOLIO_SOURCE_TYPE:
        raise PortfolioSourceFormatError("source_lineage.source_type is unsupported.")
    if source_version != LOCAL_JSON_PORTFOLIO_SOURCE_SCHEMA_VERSION:
        raise PortfolioSourceFormatError("source_lineage.source_version is unsupported.")
    return {
        "source_type": source_type,
        "source_version": source_version,
    }
