from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import hashlib
import re
from pathlib import Path
from typing import Protocol
from typing import runtime_checkable
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from market_inputs.technical_close_observation import MarketInputError
from market_inputs.technical_close_observation import MarketInputValidationError
from market_inputs.technical_close_observation import TechnicalCloseBasis
from market_inputs.technical_close_observation import TechnicalCloseObservationSeries


YAHOO_FINANCE_PROVIDER_ID_V1 = "YAHOO_FINANCE_V1"
MARKET_INPUT_ARTIFACT_ROOT_ALIAS = "data/production/market_inputs"

_MARKET_REVISION_PATTERN = re.compile(r"^market_revision_[0-9a-f]{64}$")
_SAFE_PROVIDER_KEYS = {
    YAHOO_FINANCE_PROVIDER_ID_V1: "yahoo_finance_v1",
}


class TechnicalMarketDataProvider(StrEnum):
    YAHOO_FINANCE_V1 = YAHOO_FINANCE_PROVIDER_ID_V1


class ProductionMarketInputMode(StrEnum):
    FRESH = "FRESH"
    REPLAY = "REPLAY"


class MarketArtifactSaveStatus(StrEnum):
    INSERTED = "INSERTED"
    IDEMPOTENT = "IDEMPOTENT"


class MarketSourceError(MarketInputError):
    """Raised when a market source cannot provide canonical market inputs."""


class MarketSourceUnavailableError(MarketSourceError):
    """Raised when a provider or transport is unavailable."""


class MarketArtifactStoreError(MarketInputError):
    """Raised when immutable market artifacts cannot be stored or loaded."""


class MarketArtifactConflictError(MarketArtifactStoreError):
    """Raised when an immutable artifact identity already has different content."""


class MarketArtifactCorruptionError(MarketArtifactStoreError):
    """Raised when a stored immutable artifact fails verification."""


@dataclass(frozen=True)
class TechnicalCloseSeriesRequest:
    """Provider request for one canonical technical close observation series."""

    symbol: str
    provider_symbol: str
    valuation_date: date
    start_date: date
    timezone: str
    close_basis: TechnicalCloseBasis | str
    provider: TechnicalMarketDataProvider | str

    def __post_init__(self) -> None:
        _require_non_empty_text(self.symbol, "symbol")
        _require_non_empty_text(self.provider_symbol, "provider_symbol")
        _require_exact_date(self.valuation_date, "valuation_date")
        _require_exact_date(self.start_date, "start_date")
        if self.start_date > self.valuation_date:
            raise MarketInputValidationError("start_date must be on or before valuation_date.")
        _require_valid_timezone(self.timezone)
        object.__setattr__(self, "close_basis", _coerce_close_basis(self.close_basis))
        object.__setattr__(self, "provider", _coerce_provider(self.provider))


@dataclass(frozen=True)
class TechnicalCloseSeriesArtifactIdentity:
    """Immutable lookup key for a canonical technical close series artifact."""

    provider: TechnicalMarketDataProvider | str
    symbol: str
    provider_symbol: str
    valuation_date: date
    market_revision_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _coerce_provider(self.provider))
        _require_non_empty_text(self.symbol, "symbol")
        _require_non_empty_text(self.provider_symbol, "provider_symbol")
        _require_exact_date(self.valuation_date, "valuation_date")
        _require_market_revision_id(self.market_revision_id)

    @classmethod
    def from_series(cls, series: TechnicalCloseObservationSeries) -> "TechnicalCloseSeriesArtifactIdentity":
        if not isinstance(series, TechnicalCloseObservationSeries):
            raise MarketInputValidationError("series must be TechnicalCloseObservationSeries.")
        return cls(
            provider=series.provider,
            symbol=series.symbol,
            provider_symbol=series.provider_symbol,
            valuation_date=series.valuation_date,
            market_revision_id=series.market_revision_id,
        )


@dataclass(frozen=True)
class ProductionMarketInputConfig:
    """Local production market input artifact path contract."""

    project_root: Path

    def __post_init__(self) -> None:
        root = Path(self.project_root).resolve()
        if not root.exists():
            raise MarketInputValidationError("project_root must exist.")
        if not root.is_dir():
            raise MarketInputValidationError("project_root must be a directory.")
        object.__setattr__(self, "project_root", root)

    @classmethod
    def from_project_root(cls, project_root: Path | str) -> "ProductionMarketInputConfig":
        return cls(project_root=Path(project_root))

    @property
    def artifact_root(self) -> Path:
        return self.project_root / MARKET_INPUT_ARTIFACT_ROOT_ALIAS

    @property
    def artifact_root_alias(self) -> str:
        return MARKET_INPUT_ARTIFACT_ROOT_ALIAS

    def artifact_relative_path(self, identity: TechnicalCloseSeriesArtifactIdentity) -> Path:
        identity = _require_artifact_identity(identity)
        return Path(
            _provider_path_key(identity.provider),
            _safe_symbol_key(identity.symbol, identity.provider_symbol),
            identity.valuation_date.isoformat(),
            f"{identity.market_revision_id}.json",
        )

    def artifact_path(self, identity: TechnicalCloseSeriesArtifactIdentity) -> Path:
        return self.artifact_root / self.artifact_relative_path(identity)


@dataclass(frozen=True)
class MarketArtifactSaveResult:
    status: MarketArtifactSaveStatus
    identity: TechnicalCloseSeriesArtifactIdentity
    relative_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _coerce_save_status(self.status))
        _require_artifact_identity(self.identity)
        if not isinstance(self.relative_path, Path):
            raise MarketInputValidationError("relative_path must be a Path.")
        if self.relative_path.is_absolute():
            raise MarketInputValidationError("relative_path must be relative.")


@runtime_checkable
class TechnicalCloseSeriesSource(Protocol):
    def fetch(self, request: TechnicalCloseSeriesRequest) -> TechnicalCloseObservationSeries:
        ...


@runtime_checkable
class TechnicalCloseSeriesStore(Protocol):
    def save(self, series: TechnicalCloseObservationSeries) -> MarketArtifactSaveResult:
        ...

    def get(self, identity: TechnicalCloseSeriesArtifactIdentity) -> TechnicalCloseObservationSeries | None:
        ...


def _coerce_provider(value: TechnicalMarketDataProvider | str) -> TechnicalMarketDataProvider:
    try:
        return value if isinstance(value, TechnicalMarketDataProvider) else TechnicalMarketDataProvider(value)
    except ValueError as exc:
        raise MarketInputValidationError("Unsupported provider.") from exc


def _coerce_close_basis(value: TechnicalCloseBasis | str) -> TechnicalCloseBasis:
    try:
        return value if isinstance(value, TechnicalCloseBasis) else TechnicalCloseBasis(value)
    except ValueError as exc:
        raise MarketInputValidationError("Unsupported close_basis.") from exc


def _coerce_save_status(value: MarketArtifactSaveStatus | str) -> MarketArtifactSaveStatus:
    try:
        return value if isinstance(value, MarketArtifactSaveStatus) else MarketArtifactSaveStatus(value)
    except ValueError as exc:
        raise MarketInputValidationError("Unsupported save status.") from exc


def _require_non_empty_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise MarketInputValidationError(f"{field_name} must be a non-empty string.")
    return value


def _require_exact_date(value: object, field_name: str) -> date:
    if type(value) is not date:
        raise MarketInputValidationError(f"{field_name} must be a date.")
    return value


def _require_valid_timezone(value: object) -> str:
    timezone = _require_non_empty_text(value, "timezone")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise MarketInputValidationError("timezone must be a valid IANA timezone.") from exc
    return timezone


def _require_market_revision_id(value: object) -> str:
    revision_id = _require_non_empty_text(value, "market_revision_id")
    if _MARKET_REVISION_PATTERN.fullmatch(revision_id) is None:
        raise MarketInputValidationError("market_revision_id must match market_revision_<sha256>.")
    return revision_id


def _require_artifact_identity(value: object) -> TechnicalCloseSeriesArtifactIdentity:
    if not isinstance(value, TechnicalCloseSeriesArtifactIdentity):
        raise MarketInputValidationError("identity must be TechnicalCloseSeriesArtifactIdentity.")
    return value


def _provider_path_key(provider: TechnicalMarketDataProvider) -> str:
    return _SAFE_PROVIDER_KEYS[provider.value]


def _safe_symbol_key(symbol: str, provider_symbol: str) -> str:
    combined = f"{symbol}\n{provider_symbol}"
    readable = _safe_slug(f"{symbol}--{provider_symbol}")[:48].strip("-._")
    if not readable:
        readable = "symbol"
    suffix = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:12]
    return f"{readable}--{suffix}"


def _safe_slug(value: str) -> str:
    chars = []
    previous_dash = False
    for character in value.lower():
        if character.isascii() and (character.isalnum() or character in "._-"):
            chars.append(character)
            previous_dash = False
        else:
            if not previous_dash:
                chars.append("-")
                previous_dash = True
    return "".join(chars)
