from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from numbers import Real
from typing import Mapping

from features import FeatureCalculationContext
from features import FeatureCalculationOutput
from features.calculators import PriceVolumePoint
from features.calculators import RSI14Calculator
from features.calculators import SMA20Calculator
from features.calculators import SMA60Calculator
from market_inputs.technical_close_observation import TechnicalCloseObservation
from market_inputs.technical_close_observation import TechnicalCloseObservationSeries
from market_inputs.technical_feature_bundle import PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1
from market_inputs.technical_feature_bundle import TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1
from market_inputs.technical_feature_bundle import TechnicalFeatureBundle
from market_inputs.technical_feature_bundle import TechnicalFeatureMaterializationError
from market_inputs.technical_feature_bundle import effective_observation_checksum
from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_ID


REQUIRED_TECHNICAL_FEATURE_OBSERVATIONS_V1 = 60


@dataclass(frozen=True)
class ProductionTechnicalFeatureMaterializer:
    """Pure production materializer from canonical close observations to Technical Risk v1 features."""

    feature_materializer_version: str = PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1

    def __post_init__(self) -> None:
        if self.feature_materializer_version != PRODUCTION_TECHNICAL_FEATURE_MATERIALIZER_V1:
            raise TechnicalFeatureMaterializationError("Unsupported technical feature materializer version.")

    def materialize(self, series: TechnicalCloseObservationSeries) -> TechnicalFeatureBundle:
        if not isinstance(series, TechnicalCloseObservationSeries):
            raise TechnicalFeatureMaterializationError("materialize requires TechnicalCloseObservationSeries.")
        effective_window = _effective_window(series)
        effective_checksum = effective_observation_checksum(
            symbol=series.symbol,
            valuation_date=series.valuation_date,
            observations=_effective_observation_material(effective_window),
        )
        price_points = _price_points(series.symbol, effective_window)
        context = FeatureCalculationContext(
            snapshot_id=series.market_revision_id,
            snapshot_version=effective_checksum,
            universe_id="production_technical_feature_bundle_v1",
            as_of_date=series.valuation_date,
            calculation_id=f"technical_feature_materializer_{series.market_revision_id}",
            data_source=series.producer_version,
            lineage={"market_revision_id": series.market_revision_id},
        )
        features = {
            TECH_AS_OF_CLOSE_FEATURE_ID: _as_of_close(series.valuation_date, effective_window),
            TECH_SMA20_FEATURE_ID: _calculator_value(SMA20Calculator(price_points), context, TECH_SMA20_FEATURE_ID),
            TECH_SMA60_FEATURE_ID: _calculator_value(SMA60Calculator(price_points), context, TECH_SMA60_FEATURE_ID),
            TECH_RSI14_FEATURE_ID: _calculator_value(RSI14Calculator(price_points), context, TECH_RSI14_FEATURE_ID),
        }
        return TechnicalFeatureBundle(
            schema_version=TECHNICAL_FEATURE_BUNDLE_SCHEMA_VERSION_V1,
            feature_materializer_version=self.feature_materializer_version,
            symbol=series.symbol,
            valuation_date=series.valuation_date,
            market_revision_id=series.market_revision_id,
            effective_observation_checksum=effective_checksum,
            features=features,
        )


def _effective_window(series: TechnicalCloseObservationSeries) -> tuple[TechnicalCloseObservation, ...]:
    observations = tuple(
        observation
        for observation in series.observations
        if observation.market_session_date <= series.valuation_date
    )
    if len(observations) < REQUIRED_TECHNICAL_FEATURE_OBSERVATIONS_V1:
        raise TechnicalFeatureMaterializationError("insufficient observations for Technical Risk v1 feature bundle.")
    window = observations[-REQUIRED_TECHNICAL_FEATURE_OBSERVATIONS_V1:]
    if window[-1].market_session_date != series.valuation_date:
        raise TechnicalFeatureMaterializationError("effective observation window must end at valuation_date.")
    return window


def _effective_observation_material(
    observations: tuple[TechnicalCloseObservation, ...],
) -> tuple[Mapping[str, str], ...]:
    return tuple(
        {
            "market_session_date": observation.market_session_date.isoformat(),
            "technical_close": observation.technical_close.hex(),
        }
        for observation in observations
    )


def _price_points(
    symbol: str,
    observations: tuple[TechnicalCloseObservation, ...],
) -> tuple[PriceVolumePoint, ...]:
    return tuple(
        PriceVolumePoint(
            symbol=symbol,
            trading_date=observation.market_session_date,
            close=observation.technical_close,
        )
        for observation in observations
    )


def _as_of_close(
    valuation_date: date,
    observations: tuple[TechnicalCloseObservation, ...],
) -> float:
    for observation in reversed(observations):
        if observation.market_session_date == valuation_date:
            return observation.technical_close
    raise TechnicalFeatureMaterializationError("valuation_date observation is required for TECH_AS_OF_CLOSE_V1.")


def _calculator_value(
    calculator: object,
    context: FeatureCalculationContext,
    expected_feature_id: str,
) -> float:
    output = getattr(calculator, "calculate")(context)
    if not isinstance(output, FeatureCalculationOutput):
        raise TechnicalFeatureMaterializationError("calculator returned invalid output.")
    if output.feature_id != expected_feature_id:
        raise TechnicalFeatureMaterializationError("calculator feature_id mismatch.")
    if not getattr(calculator, "validate")(output):
        raise TechnicalFeatureMaterializationError(f"{expected_feature_id} calculation failed.")
    if len(output.values) != 1:
        raise TechnicalFeatureMaterializationError("calculator output must contain exactly one feature row.")
    row = output.values[0]
    if row.get("feature_id") != expected_feature_id:
        raise TechnicalFeatureMaterializationError("calculator output feature_id mismatch.")
    if row.get("date") != context.as_of_date:
        raise TechnicalFeatureMaterializationError("calculator output date mismatch.")
    try:
        value = row["feature_value"]
    except (KeyError, TypeError, ValueError) as exc:
        raise TechnicalFeatureMaterializationError("calculator output feature_value must be finite float.") from exc
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TechnicalFeatureMaterializationError("calculator output feature_value must be finite float.")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise TechnicalFeatureMaterializationError("calculator output feature_value must be finite float.")
    return numeric
