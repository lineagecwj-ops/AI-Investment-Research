from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Any
from typing import Mapping

from market_inputs.technical_close_observation import MarketInputValidationError
from market_inputs.technical_close_observation import TechnicalCloseBasis
from market_inputs.technical_close_observation import TechnicalCloseObservation
from market_inputs.technical_close_observation import TechnicalCloseObservationSeries
from market_inputs.technical_close_observation import TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1


TECHNICAL_CLOSE_OBSERVATION_CODEC_VERSION_V1 = "1"

_ENVELOPE_FIELDS = frozenset({"schema_version", "codec_version", "series"})
_SERIES_FIELDS = frozenset(
    {
        "symbol",
        "provider",
        "provider_symbol",
        "timezone",
        "close_basis",
        "valuation_date",
        "observations",
        "fetched_at",
        "market_revision_id",
        "producer_version",
    }
)
_OBSERVATION_FIELDS = frozenset({"market_session_date", "technical_close"})


class TechnicalCloseObservationSeriesCodecError(ValueError):
    """Raised when TechnicalCloseObservationSeries codec validation fails closed."""


@dataclass(frozen=True)
class TechnicalCloseObservationSeriesCodec:
    """Encode and decode TechnicalCloseObservationSeries through canonical JSON."""

    def encode(self, series: TechnicalCloseObservationSeries) -> str:
        if not isinstance(series, TechnicalCloseObservationSeries):
            raise TechnicalCloseObservationSeriesCodecError("encode requires TechnicalCloseObservationSeries.")
        envelope = {
            "schema_version": TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1,
            "codec_version": TECHNICAL_CLOSE_OBSERVATION_CODEC_VERSION_V1,
            "series": _series_payload(series),
        }
        return canonical_json_dumps(envelope)

    def decode(self, payload: str) -> TechnicalCloseObservationSeries:
        if not isinstance(payload, str):
            raise TechnicalCloseObservationSeriesCodecError("decode requires JSON string payload.")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TechnicalCloseObservationSeriesCodecError("payload must be valid JSON.") from exc
        envelope = _require_exact_mapping(decoded, _ENVELOPE_FIELDS, "envelope")
        _validate_version(
            envelope["schema_version"],
            TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1,
            "schema_version",
        )
        _validate_version(
            envelope["codec_version"],
            TECHNICAL_CLOSE_OBSERVATION_CODEC_VERSION_V1,
            "codec_version",
        )
        series_payload = _require_exact_mapping(envelope["series"], _SERIES_FIELDS, "series")
        try:
            observations = tuple(
                _decode_observation(item)
                for item in _require_list(series_payload["observations"], "series.observations")
            )
            return TechnicalCloseObservationSeries(
                symbol=_require_string(series_payload["symbol"], "series.symbol"),
                provider=_require_string(series_payload["provider"], "series.provider"),
                provider_symbol=_require_string(series_payload["provider_symbol"], "series.provider_symbol"),
                timezone=_require_string(series_payload["timezone"], "series.timezone"),
                close_basis=TechnicalCloseBasis(_require_string(series_payload["close_basis"], "series.close_basis")),
                valuation_date=_parse_date(series_payload["valuation_date"], "series.valuation_date"),
                observations=observations,
                fetched_at=_parse_datetime(series_payload["fetched_at"], "series.fetched_at"),
                market_revision_id=_require_string(series_payload["market_revision_id"], "series.market_revision_id"),
                producer_version=_require_string(series_payload["producer_version"], "series.producer_version"),
            )
        except (MarketInputValidationError, ValueError, TypeError) as exc:
            raise TechnicalCloseObservationSeriesCodecError(str(exc)) from exc


def canonical_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _series_payload(series: TechnicalCloseObservationSeries) -> dict[str, Any]:
    return {
        "symbol": series.symbol,
        "provider": series.provider,
        "provider_symbol": series.provider_symbol,
        "timezone": series.timezone,
        "close_basis": series.close_basis.value,
        "valuation_date": series.valuation_date.isoformat(),
        "observations": [_observation_payload(observation) for observation in series.observations],
        "fetched_at": series.fetched_at.isoformat(),
        "market_revision_id": series.market_revision_id,
        "producer_version": series.producer_version,
    }


def _observation_payload(observation: TechnicalCloseObservation) -> dict[str, str]:
    return {
        "market_session_date": observation.market_session_date.isoformat(),
        "technical_close": observation.technical_close.hex(),
    }


def _decode_observation(payload: object) -> TechnicalCloseObservation:
    observation = _require_exact_mapping(payload, _OBSERVATION_FIELDS, "observation")
    return TechnicalCloseObservation(
        market_session_date=_parse_date(observation["market_session_date"], "observation.market_session_date"),
        technical_close=_parse_float_hex(observation["technical_close"], "observation.technical_close"),
    )


def _require_exact_mapping(value: object, expected_fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TechnicalCloseObservationSeriesCodecError(f"{label} must be a JSON object.")
    actual = set(value)
    missing = sorted(expected_fields - actual)
    if missing:
        raise TechnicalCloseObservationSeriesCodecError(f"{label} missing required field: {missing[0]}")
    unknown = sorted(actual - expected_fields)
    if unknown:
        raise TechnicalCloseObservationSeriesCodecError(f"{label} contains unknown field: {unknown[0]}")
    return value


def _require_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be a list.")
    return value


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be a non-empty string.")
    return value


def _validate_version(value: object, expected: str, field_name: str) -> None:
    actual = _require_string(value, field_name)
    if actual != expected:
        raise TechnicalCloseObservationSeriesCodecError(f"Unsupported {field_name}.")


def _parse_date(value: object, field_name: str) -> date:
    text = _require_string(value, field_name)
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be an ISO date.")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be a valid ISO date.") from exc
    if parsed.isoformat() != text:
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be an exact ISO date.")
    return parsed


def _parse_datetime(value: object, field_name: str) -> datetime:
    text = _require_string(value, field_name)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be a valid ISO datetime.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be timezone-aware.")
    return parsed


def _parse_float_hex(value: object, field_name: str) -> float:
    text = _require_string(value, field_name)
    try:
        return float.fromhex(text)
    except ValueError as exc:
        raise TechnicalCloseObservationSeriesCodecError(f"{field_name} must be a float hex string.") from exc
