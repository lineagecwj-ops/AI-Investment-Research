from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
import re
from numbers import Real
from types import MappingProxyType
from typing import Mapping

from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_ID


TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1 = "1"
PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1 = "PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1"
TECHNICAL_EFFECTIVE_OBSERVATIONS_PREFIX = "technical_effective_observations"
TECHNICAL_FEATURE_BUNDLE_PREFIX = "technical_feature_bundle"
TECHNICAL_RISK_V1_FEATURE_IDS = (
    TECH_AS_OF_CLOSE_FEATURE_ID,
    TECH_RSI14_FEATURE_ID,
    TECH_SMA20_FEATURE_ID,
    TECH_SMA60_FEATURE_ID,
)

_MARKET_REVISION_PATTERN = re.compile(r"^market_revision_[0-9a-f]{64}$")
_EFFECTIVE_OBSERVATION_CHECKSUM_PATTERN = re.compile(r"^technical_effective_observations_[0-9a-f]{64}$")
_FEATURE_BUNDLE_CHECKSUM_PATTERN = re.compile(r"^technical_feature_bundle_[0-9a-f]{64}$")


class TechnicalFeatureMaterializationError(ValueError):
    """Raised when production technical feature materialization fails closed."""


@dataclass(frozen=True)
class TechnicalFeatureBundle:
    """Symbol-level deterministic Technical Risk v1 feature bundle."""

    schema_version: str
    feature_materializer_version: str
    symbol: str
    valuation_date: date
    market_revision_id: str
    effective_observation_checksum: str
    features: Mapping[str, float]
    feature_bundle_checksum: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1:
            raise TechnicalFeatureMaterializationError("Unsupported TechnicalFeatureBundle schema_version.")
        if self.feature_materializer_version != PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1:
            raise TechnicalFeatureMaterializationError("Unsupported technical feature materializer version.")
        _require_non_empty_text(self.symbol, "symbol")
        _require_exact_date(self.valuation_date, "valuation_date")
        _require_market_revision_id(self.market_revision_id)
        _require_effective_observation_checksum(self.effective_observation_checksum)
        features = _normalize_features(self.features)
        checksum = _feature_bundle_checksum(
            schema_version=self.schema_version,
            feature_materializer_version=self.feature_materializer_version,
            symbol=self.symbol,
            valuation_date=self.valuation_date,
            effective_observation_checksum=self.effective_observation_checksum,
            features=features,
        )
        if self.feature_bundle_checksum is not None:
            _require_feature_bundle_checksum(self.feature_bundle_checksum)
            if self.feature_bundle_checksum != checksum:
                raise TechnicalFeatureMaterializationError("feature_bundle_checksum mismatch.")
        object.__setattr__(self, "features", MappingProxyType(features))
        object.__setattr__(self, "feature_bundle_checksum", checksum)


def effective_observation_checksum(
    *,
    symbol: str,
    valuation_date: date,
    observations: tuple[Mapping[str, object], ...],
) -> str:
    _require_non_empty_text(symbol, "symbol")
    _require_exact_date(valuation_date, "valuation_date")
    material = {
        "schema_version": TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1,
        "symbol": symbol,
        "valuation_date": valuation_date.isoformat(),
        "observations": tuple(observations),
    }
    return f"{TECHNICAL_EFFECTIVE_OBSERVATIONS_PREFIX}_{_sha256(material)}"


def _normalize_features(features: Mapping[str, object]) -> dict[str, float]:
    if not isinstance(features, Mapping):
        raise TechnicalFeatureMaterializationError("features must be a mapping.")
    keys = tuple(features.keys())
    if any(not isinstance(key, str) for key in keys):
        raise TechnicalFeatureMaterializationError("features keys must be feature ids.")
    if set(keys) != set(TECHNICAL_RISK_V1_FEATURE_IDS) or len(keys) != len(TECHNICAL_RISK_V1_FEATURE_IDS):
        raise TechnicalFeatureMaterializationError("TechnicalFeatureBundle requires exact Technical Risk v1 feature set.")
    normalized: dict[str, float] = {}
    for feature_id in sorted(TECHNICAL_RISK_V1_FEATURE_IDS):
        normalized[feature_id] = _require_finite_float(features[feature_id], f"{feature_id} value")
    return normalized


def _feature_bundle_checksum(
    *,
    schema_version: str,
    feature_materializer_version: str,
    symbol: str,
    valuation_date: date,
    effective_observation_checksum: str,
    features: Mapping[str, float],
) -> str:
    material = {
        "schema_version": schema_version,
        "feature_materializer_version": feature_materializer_version,
        "symbol": symbol,
        "valuation_date": valuation_date.isoformat(),
        "effective_observation_checksum": effective_observation_checksum,
        "features": tuple(
            {
                "feature_id": feature_id,
                "value": _canonical_float(features[feature_id]),
            }
            for feature_id in sorted(features)
        ),
    }
    return f"{TECHNICAL_FEATURE_BUNDLE_PREFIX}_{_sha256(material)}"


def _require_non_empty_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TechnicalFeatureMaterializationError(f"{field_name} must be a non-empty string.")
    return value


def _require_exact_date(value: object, field_name: str) -> date:
    if type(value) is not date:
        raise TechnicalFeatureMaterializationError(f"{field_name} must be a date.")
    return value


def _require_market_revision_id(value: object) -> str:
    revision_id = _require_non_empty_text(value, "market_revision_id")
    if _MARKET_REVISION_PATTERN.fullmatch(revision_id) is None:
        raise TechnicalFeatureMaterializationError("market_revision_id must match market_revision_<sha256>.")
    return revision_id


def _require_effective_observation_checksum(value: object) -> str:
    checksum = _require_non_empty_text(value, "effective_observation_checksum")
    if _EFFECTIVE_OBSERVATION_CHECKSUM_PATTERN.fullmatch(checksum) is None:
        raise TechnicalFeatureMaterializationError(
            "effective_observation_checksum must match technical_effective_observations_<sha256>."
        )
    return checksum


def _require_feature_bundle_checksum(value: object) -> str:
    checksum = _require_non_empty_text(value, "feature_bundle_checksum")
    if _FEATURE_BUNDLE_CHECKSUM_PATTERN.fullmatch(checksum) is None:
        raise TechnicalFeatureMaterializationError("feature_bundle_checksum must match technical_feature_bundle_<sha256>.")
    return checksum


def _require_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TechnicalFeatureMaterializationError(f"{field_name} must be a finite float.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise TechnicalFeatureMaterializationError(f"{field_name} must be finite.")
    return numeric


def _canonical_float(value: float) -> str:
    return value.hex()


def _sha256(material: Mapping[str, object]) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
