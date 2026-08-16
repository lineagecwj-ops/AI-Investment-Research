from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re
from typing import Mapping

from market_inputs.technical_close_observation import MarketInputValidationError
from market_inputs.technical_feature_bundle import TechnicalFeatureBundle


TECHNICAL_FEATURE_SET_SCHEMA_VERSION_V1 = "1"
TECHNICAL_FEATURE_SET_PREFIX = "technical_feature_set"

_TECHNICAL_FEATURE_SET_CHECKSUM_PATTERN = re.compile(r"^technical_feature_set_[0-9a-f]{64}$")


@dataclass(frozen=True)
class TechnicalFeatureSet:
    """Immutable deterministic set of symbol-level Technical Risk feature bundles."""

    bundles: tuple[TechnicalFeatureBundle, ...]
    technical_feature_set_checksum: str | None = None
    schema_version: str = TECHNICAL_FEATURE_SET_SCHEMA_VERSION_V1
    feature_materializer_version: str | None = None
    valuation_date: date | None = None

    def __post_init__(self) -> None:
        if self.schema_version != TECHNICAL_FEATURE_SET_SCHEMA_VERSION_V1:
            raise MarketInputValidationError("Unsupported TechnicalFeatureSet schema_version.")
        bundles = _normalize_bundles(self.bundles)
        shared_materializer_version = _shared_materializer_version(bundles)
        shared_valuation_date = _shared_valuation_date(bundles)
        _require_shared_bundle_schema(bundles)
        if self.feature_materializer_version is not None and self.feature_materializer_version != shared_materializer_version:
            raise MarketInputValidationError("TechnicalFeatureSet feature_materializer_version mismatch.")
        if self.valuation_date is not None and self.valuation_date != shared_valuation_date:
            raise MarketInputValidationError("TechnicalFeatureSet valuation_date mismatch.")

        checksum = _technical_feature_set_checksum(
            schema_version=self.schema_version,
            feature_materializer_version=shared_materializer_version,
            valuation_date=shared_valuation_date,
            bundles=bundles,
        )
        if self.technical_feature_set_checksum is not None:
            _require_feature_set_checksum(self.technical_feature_set_checksum)
            if self.technical_feature_set_checksum != checksum:
                raise MarketInputValidationError("technical_feature_set_checksum mismatch.")

        object.__setattr__(self, "bundles", bundles)
        object.__setattr__(self, "feature_materializer_version", shared_materializer_version)
        object.__setattr__(self, "valuation_date", shared_valuation_date)
        object.__setattr__(self, "technical_feature_set_checksum", checksum)

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(bundle.symbol for bundle in self.bundles)


def _normalize_bundles(bundles: object) -> tuple[TechnicalFeatureBundle, ...]:
    if not isinstance(bundles, tuple):
        raise MarketInputValidationError("TechnicalFeatureSet bundles must be a tuple.")
    if not bundles:
        raise MarketInputValidationError("TechnicalFeatureSet bundles cannot be empty.")
    seen_symbols: set[str] = set()
    duplicate_symbols: set[str] = set()
    for bundle in bundles:
        if not isinstance(bundle, TechnicalFeatureBundle):
            raise MarketInputValidationError("TechnicalFeatureSet bundles must contain TechnicalFeatureBundle.")
        if bundle.symbol in seen_symbols:
            duplicate_symbols.add(bundle.symbol)
        seen_symbols.add(bundle.symbol)
    if duplicate_symbols:
        raise MarketInputValidationError(f"Duplicate TechnicalFeatureSet symbol: {', '.join(sorted(duplicate_symbols))}.")
    return tuple(sorted(bundles, key=lambda bundle: bundle.symbol))


def _shared_materializer_version(bundles: tuple[TechnicalFeatureBundle, ...]) -> str:
    versions = {bundle.feature_materializer_version for bundle in bundles}
    if len(versions) != 1:
        raise MarketInputValidationError("TechnicalFeatureSet bundles must share feature_materializer_version.")
    return next(iter(versions))


def _shared_valuation_date(bundles: tuple[TechnicalFeatureBundle, ...]) -> date:
    valuation_dates = {bundle.valuation_date for bundle in bundles}
    if len(valuation_dates) != 1:
        raise MarketInputValidationError("TechnicalFeatureSet bundles must share valuation_date.")
    return next(iter(valuation_dates))


def _require_shared_bundle_schema(bundles: tuple[TechnicalFeatureBundle, ...]) -> str:
    schema_versions = {bundle.schema_version for bundle in bundles}
    if len(schema_versions) != 1:
        raise MarketInputValidationError("TechnicalFeatureSet bundles must share bundle schema_version.")
    return next(iter(schema_versions))


def _technical_feature_set_checksum(
    *,
    schema_version: str,
    feature_materializer_version: str,
    valuation_date: date,
    bundles: tuple[TechnicalFeatureBundle, ...],
) -> str:
    material = {
        "schema_version": schema_version,
        "feature_materializer_version": feature_materializer_version,
        "valuation_date": valuation_date.isoformat(),
        "bundles": tuple(
            {
                "symbol": bundle.symbol,
                "feature_bundle_checksum": bundle.feature_bundle_checksum,
            }
            for bundle in bundles
        ),
    }
    return f"{TECHNICAL_FEATURE_SET_PREFIX}_{_sha256(material)}"


def _require_feature_set_checksum(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise MarketInputValidationError("technical_feature_set_checksum must be a non-empty string.")
    if _TECHNICAL_FEATURE_SET_CHECKSUM_PATTERN.fullmatch(value) is None:
        raise MarketInputValidationError("technical_feature_set_checksum must match technical_feature_set_<sha256>.")
    return value


def _sha256(material: Mapping[str, object]) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
