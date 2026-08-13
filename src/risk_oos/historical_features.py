from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import hashlib
import json
from numbers import Real
from types import MappingProxyType
from typing import Iterable
from typing import Mapping

from features import FeatureCalculationContext
from features.calculators import PriceVolumePoint
from features.calculators import RSI14Calculator
from features.calculators import SMA20Calculator
from features.calculators import SMA60Calculator
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_VERSION


FEATURE_SMA20 = "TECH_SMA20_V1"
FEATURE_SMA60 = "TECH_SMA60_V1"
FEATURE_RSI14 = "TECH_RSI14_V1"
HISTORICAL_RISK_FEATURE_SET_V1 = (
    TECH_AS_OF_CLOSE_FEATURE_ID,
    FEATURE_SMA20,
    FEATURE_SMA60,
    FEATURE_RSI14,
)

EXCLUSION_MISSING_AS_OF_CLOSE = "EXCLUDED_MISSING_AS_OF_CLOSE"
EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY = "EXCLUDED_INSUFFICIENT_REQUIRED_FEATURE_HISTORY"
EXCLUSION_INVALID_PRICE = "EXCLUDED_INVALID_PRICE"
EXCLUSION_FEATURE_CALCULATION_FAILED = "EXCLUDED_FEATURE_CALCULATION_FAILED"


class HistoricalRiskFeatureMaterializationError(Exception):
    """Raised when historical risk feature materialization contracts are invalid."""


class HistoricalRiskFeatureStatus(StrEnum):
    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class HistoricalRiskFeatureMaterializationContext:
    """Identity and lineage for one symbol/date historical risk feature observation."""

    symbol: str
    evaluation_date: date
    source_snapshot_id: str
    source_snapshot_checksum: str
    feature_set_id: str
    calculation_id: str
    requested_features: tuple[str, ...] = HISTORICAL_RISK_FEATURE_SET_V1

    def __post_init__(self):
        _require_text(self.symbol, "symbol")
        _require_date(self.evaluation_date, "evaluation_date")
        _require_text(self.source_snapshot_id, "source_snapshot_id")
        _require_text(self.source_snapshot_checksum, "source_snapshot_checksum")
        _require_text(self.feature_set_id, "feature_set_id")
        _require_text(self.calculation_id, "calculation_id")
        requested = _normalize_requested_features(self.requested_features)
        object.__setattr__(self, "requested_features", requested)


@dataclass(frozen=True)
class HistoricalRiskFeatureObservation:
    """Frozen symbol/date technical inputs for OOS methodology evaluation."""

    observation_id: str
    observation_checksum: str
    symbol: str
    evaluation_date: date
    feature_set_id: str
    source_snapshot_id: str
    source_snapshot_checksum: str
    calculation_id: str
    feature_ids: tuple[str, ...]
    feature_versions: Mapping[str, str]
    formula_versions: Mapping[str, str]
    as_of_close: float
    sma20: float
    sma60: float
    rsi14: float

    def __post_init__(self):
        object.__setattr__(self, "feature_versions", MappingProxyType(dict(self.feature_versions)))
        object.__setattr__(self, "formula_versions", MappingProxyType(dict(self.formula_versions)))

    @property
    def feature_values(self) -> Mapping[str, float]:
        return MappingProxyType(
            {
                TECH_AS_OF_CLOSE_FEATURE_ID: self.as_of_close,
                FEATURE_SMA20: self.sma20,
                FEATURE_SMA60: self.sma60,
                FEATURE_RSI14: self.rsi14,
            }
        )


@dataclass(frozen=True)
class HistoricalRiskFeatureExclusion:
    """Explicit exclusion for a symbol/date that cannot form a complete observation."""

    exclusion_id: str
    symbol: str
    evaluation_date: date
    feature_set_id: str
    source_snapshot_id: str
    source_snapshot_checksum: str
    calculation_id: str
    reason: str
    feature_id: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class HistoricalRiskFeatureMaterializationResult:
    """Result envelope that unambiguously separates included and excluded observations."""

    status: HistoricalRiskFeatureStatus
    observation: HistoricalRiskFeatureObservation | None = None
    exclusion: HistoricalRiskFeatureExclusion | None = None

    def __post_init__(self):
        if self.status == HistoricalRiskFeatureStatus.INCLUDED and self.observation is None:
            raise HistoricalRiskFeatureMaterializationError("Included materialization result requires observation.")
        if self.status == HistoricalRiskFeatureStatus.EXCLUDED and self.exclusion is None:
            raise HistoricalRiskFeatureMaterializationError("Excluded materialization result requires exclusion.")
        if self.observation is not None and self.exclusion is not None:
            raise HistoricalRiskFeatureMaterializationError("Materialization result cannot contain both observation and exclusion.")


class HistoricalRiskFeatureMaterializer:
    """Materializes frozen technical inputs from caller-provided historical price observations."""

    def __init__(self, price_points: Iterable[PriceVolumePoint]):
        self._price_points = tuple(sorted(price_points, key=lambda point: (point.symbol, point.trading_date)))

    def materialize(
        self,
        context: HistoricalRiskFeatureMaterializationContext,
    ) -> HistoricalRiskFeatureMaterializationResult:
        symbol_points = tuple(
            point
            for point in self._price_points
            if point.symbol == context.symbol and point.trading_date <= context.evaluation_date
        )
        duplicate = self._duplicate_date(symbol_points)
        if duplicate is not None:
            return self._exclude(context, EXCLUSION_FEATURE_CALCULATION_FAILED, detail=f"duplicate trading_date: {duplicate.isoformat()}")
        as_of_points = tuple(point for point in symbol_points if point.trading_date == context.evaluation_date)
        if not as_of_points or as_of_points[0].close is None:
            return self._exclude(context, EXCLUSION_MISSING_AS_OF_CLOSE, feature_id=TECH_AS_OF_CLOSE_FEATURE_ID)
        as_of_close = as_of_points[0].close
        if not _is_positive_number(as_of_close):
            return self._exclude(context, EXCLUSION_INVALID_PRICE, feature_id=TECH_AS_OF_CLOSE_FEATURE_ID)
        invalid_price = next((point for point in symbol_points if point.close is not None and not _is_positive_number(point.close)), None)
        if invalid_price is not None:
            return self._exclude(
                context,
                EXCLUSION_INVALID_PRICE,
                detail=f"invalid close at {invalid_price.trading_date.isoformat()}",
            )

        calculation_context = FeatureCalculationContext(
            snapshot_id=context.source_snapshot_id,
            snapshot_version=context.source_snapshot_checksum,
            universe_id=context.feature_set_id,
            as_of_date=context.evaluation_date,
            calculation_id=context.calculation_id,
        )
        calculators = (
            RSI14Calculator(symbol_points),
            SMA20Calculator(symbol_points),
            SMA60Calculator(symbol_points),
        )
        values: dict[str, float] = {TECH_AS_OF_CLOSE_FEATURE_ID: float(as_of_close)}
        formula_versions = {TECH_AS_OF_CLOSE_FEATURE_ID: TECH_AS_OF_CLOSE_FEATURE_VERSION}
        for calculator in calculators:
            definition = calculator.get_definition()
            output = calculator.calculate(calculation_context)
            if not calculator.validate(output):
                status = str((output.metadata or {}).get("validation_status", ""))
                reason = (
                    EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY
                    if status == "INSUFFICIENT_HISTORY"
                    else EXCLUSION_FEATURE_CALCULATION_FAILED
                )
                return self._exclude(context, reason, feature_id=definition.feature_id)
            try:
                value = output.values[0]["feature_value"]
            except (IndexError, KeyError, TypeError):
                return self._exclude(context, EXCLUSION_FEATURE_CALCULATION_FAILED, feature_id=definition.feature_id)
            if not _is_number(value):
                return self._exclude(context, EXCLUSION_FEATURE_CALCULATION_FAILED, feature_id=definition.feature_id)
            values[definition.feature_id] = float(value)
            formula_versions[definition.feature_id] = definition.formula_version

        observation_id = _stable_id(
            "historical_risk_feature_observation",
            {
                "symbol": context.symbol,
                "evaluation_date": context.evaluation_date.isoformat(),
                "feature_set_id": context.feature_set_id,
                "source_snapshot_id": context.source_snapshot_id,
                "source_snapshot_checksum": context.source_snapshot_checksum,
                "calculation_id": context.calculation_id,
                "feature_ids": context.requested_features,
            },
        )
        checksum = _stable_id(
            "historical_risk_feature_checksum",
            {
                "observation_id": observation_id,
                "feature_values": values,
                "formula_versions": formula_versions,
            },
        )
        observation = HistoricalRiskFeatureObservation(
            observation_id=observation_id,
            observation_checksum=checksum,
            symbol=context.symbol,
            evaluation_date=context.evaluation_date,
            feature_set_id=context.feature_set_id,
            source_snapshot_id=context.source_snapshot_id,
            source_snapshot_checksum=context.source_snapshot_checksum,
            calculation_id=context.calculation_id,
            feature_ids=context.requested_features,
            feature_versions={feature_id: "v1" for feature_id in context.requested_features},
            formula_versions=formula_versions,
            as_of_close=values[TECH_AS_OF_CLOSE_FEATURE_ID],
            sma20=values[FEATURE_SMA20],
            sma60=values[FEATURE_SMA60],
            rsi14=values[FEATURE_RSI14],
        )
        return HistoricalRiskFeatureMaterializationResult(
            status=HistoricalRiskFeatureStatus.INCLUDED,
            observation=observation,
        )

    def _exclude(
        self,
        context: HistoricalRiskFeatureMaterializationContext,
        reason: str,
        *,
        feature_id: str | None = None,
        detail: str | None = None,
    ) -> HistoricalRiskFeatureMaterializationResult:
        exclusion_id = _stable_id(
            "historical_risk_feature_exclusion",
            {
                "symbol": context.symbol,
                "evaluation_date": context.evaluation_date.isoformat(),
                "feature_set_id": context.feature_set_id,
                "source_snapshot_id": context.source_snapshot_id,
                "source_snapshot_checksum": context.source_snapshot_checksum,
                "calculation_id": context.calculation_id,
                "reason": reason,
                "feature_id": feature_id,
                "detail": detail,
            },
        )
        return HistoricalRiskFeatureMaterializationResult(
            status=HistoricalRiskFeatureStatus.EXCLUDED,
            exclusion=HistoricalRiskFeatureExclusion(
                exclusion_id=exclusion_id,
                symbol=context.symbol,
                evaluation_date=context.evaluation_date,
                feature_set_id=context.feature_set_id,
                source_snapshot_id=context.source_snapshot_id,
                source_snapshot_checksum=context.source_snapshot_checksum,
                calculation_id=context.calculation_id,
                reason=reason,
                feature_id=feature_id,
                detail=detail,
            ),
        )

    def _duplicate_date(self, points: tuple[PriceVolumePoint, ...]) -> date | None:
        seen: set[date] = set()
        for point in points:
            if point.trading_date in seen:
                return point.trading_date
            seen.add(point.trading_date)
        return None


def _normalize_requested_features(features: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(features, tuple):
        raise HistoricalRiskFeatureMaterializationError("requested_features must be a tuple.")
    if set(features) != set(HISTORICAL_RISK_FEATURE_SET_V1) or len(features) != len(HISTORICAL_RISK_FEATURE_SET_V1):
        raise HistoricalRiskFeatureMaterializationError("requested_features must exactly match Technical Risk v1 feature set.")
    return HISTORICAL_RISK_FEATURE_SET_V1


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise HistoricalRiskFeatureMaterializationError(f"{field_name} must be a non-empty string.")


def _require_date(value: object, field_name: str) -> None:
    if not isinstance(value, date):
        raise HistoricalRiskFeatureMaterializationError(f"{field_name} must be a date.")


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _is_positive_number(value: object) -> bool:
    return _is_number(value) and value > 0


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return f"{prefix}_{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"


def _json_default(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, MappingProxyType):
        return dict(value)
    return value
