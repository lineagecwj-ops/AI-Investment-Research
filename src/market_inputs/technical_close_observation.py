from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from enum import StrEnum
import hashlib
import json
import math
from numbers import Real
from typing import Any
from typing import Mapping


TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1 = "1"
TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSION_V1 = "TECHNICAL_CLOSE_OBSERVATION_PRODUCER_V1"
YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1 = "YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1"
SUPPORTED_TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSIONS = frozenset(
    {
        TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSION_V1,
        YAHOO_FINANCE_TECHNICAL_CLOSE_SOURCE_V1,
    }
)


class TechnicalCloseBasis(StrEnum):
    ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE = "TECHNICAL_CLOSE_ADJUSTED_FIRST_V1"


class MarketInputError(ValueError):
    """Raised when market input contracts cannot be constructed."""


class MarketInputValidationError(MarketInputError):
    """Raised when market input values violate deterministic validation rules."""


@dataclass(frozen=True)
class TechnicalCloseObservation:
    """One exchange market-session technical close observation."""

    market_session_date: date
    technical_close: float

    def __post_init__(self) -> None:
        _require_exact_date(self.market_session_date, "market_session_date")
        object.__setattr__(
            self,
            "technical_close",
            _require_positive_finite_float(self.technical_close, "technical_close"),
        )

    @property
    def revision_material(self) -> dict[str, str]:
        return {
            "market_session_date": self.market_session_date.isoformat(),
            "technical_close": _canonical_float(self.technical_close),
        }


@dataclass(frozen=True)
class TechnicalCloseObservationSeries:
    """Canonical technical close series used as production Technical Risk market input."""

    symbol: str
    provider: str
    provider_symbol: str
    timezone: str
    close_basis: TechnicalCloseBasis | str
    valuation_date: date
    observations: tuple[TechnicalCloseObservation, ...]
    fetched_at: datetime
    market_revision_id: str | None = None
    schema_version: str = TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1
    producer_version: str = TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSION_V1

    def __post_init__(self) -> None:
        _require_non_empty_text(self.symbol, "symbol")
        _require_non_empty_text(self.provider, "provider")
        _require_non_empty_text(self.provider_symbol, "provider_symbol")
        _require_non_empty_text(self.timezone, "timezone")
        close_basis = _coerce_close_basis(self.close_basis)
        _require_exact_date(self.valuation_date, "valuation_date")
        _require_timezone_aware_datetime(self.fetched_at, "fetched_at")
        if self.schema_version != TECHNICAL_CLOSE_OBSERVATION_SCHEMA_VERSION_V1:
            raise MarketInputValidationError("Unsupported TechnicalCloseObservationSeries schema_version.")
        if self.producer_version not in SUPPORTED_TECHNICAL_CLOSE_OBSERVATION_PRODUCER_VERSIONS:
            raise MarketInputValidationError("Unsupported TechnicalCloseObservationSeries producer_version.")
        if not isinstance(self.observations, tuple):
            raise MarketInputValidationError("observations must be a tuple.")
        if not self.observations:
            raise MarketInputValidationError("observations cannot be empty.")
        normalized = tuple(
            observation if isinstance(observation, TechnicalCloseObservation) else _invalid_observation()
            for observation in self.observations
        )
        ordered = tuple(sorted(normalized, key=lambda item: item.market_session_date))
        seen_dates: set[date] = set()
        for observation in ordered:
            if observation.market_session_date in seen_dates:
                raise MarketInputValidationError("duplicate market_session_date.")
            seen_dates.add(observation.market_session_date)
        if self.valuation_date not in seen_dates:
            raise MarketInputValidationError("valuation_date must exist in observations.")

        object.__setattr__(self, "close_basis", close_basis)
        object.__setattr__(self, "observations", ordered)
        expected_revision = _market_revision_id(self.revision_material)
        if self.market_revision_id is not None and self.market_revision_id != expected_revision:
            raise MarketInputValidationError("market_revision_id mismatch.")
        object.__setattr__(self, "market_revision_id", expected_revision)

    @property
    def revision_material(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "producer_version": self.producer_version,
            "symbol": self.symbol,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "timezone": self.timezone,
            "close_basis": self.close_basis.value,
            "valuation_date": self.valuation_date.isoformat(),
            "observations": [observation.revision_material for observation in self.observations],
        }


def _market_revision_id(material: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return "market_revision_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_float(value: float) -> str:
    return value.hex()


def _require_non_empty_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise MarketInputValidationError(f"{field_name} must be a non-empty string.")
    return value


def _require_exact_date(value: object, field_name: str) -> date:
    if type(value) is not date:
        raise MarketInputValidationError(f"{field_name} must be a date.")
    return value


def _require_timezone_aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise MarketInputValidationError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarketInputValidationError(f"{field_name} must be timezone-aware.")
    return value


def _require_positive_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise MarketInputValidationError(f"{field_name} must be a finite positive float.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise MarketInputValidationError(f"{field_name} must be finite.")
    if numeric <= 0:
        raise MarketInputValidationError(f"{field_name} must be positive.")
    return numeric


def _coerce_close_basis(value: TechnicalCloseBasis | str) -> TechnicalCloseBasis:
    try:
        return value if isinstance(value, TechnicalCloseBasis) else TechnicalCloseBasis(value)
    except ValueError as exc:
        raise MarketInputValidationError("Unsupported close_basis.") from exc


def _invalid_observation() -> TechnicalCloseObservation:
    raise MarketInputValidationError("observations must contain TechnicalCloseObservation.")
