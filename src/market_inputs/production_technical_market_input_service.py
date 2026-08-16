from __future__ import annotations

from dataclasses import dataclass

from market_inputs.production_market_contracts import MarketArtifactNotFoundError
from market_inputs.production_market_contracts import MarketArtifactSaveResult
from market_inputs.production_market_contracts import ProductionMarketInputMode
from market_inputs.production_market_contracts import TechnicalCloseSeriesArtifactIdentity
from market_inputs.production_market_contracts import TechnicalCloseSeriesRequest
from market_inputs.production_market_contracts import TechnicalCloseSeriesSource
from market_inputs.production_market_contracts import TechnicalCloseSeriesStore
from market_inputs.technical_close_observation import MarketInputValidationError
from market_inputs.technical_close_observation import TechnicalCloseObservationSeries


@dataclass(frozen=True)
class ProductionTechnicalMarketInputResult:
    """Resolved technical close market input for one explicit Fresh or Replay request."""

    mode: ProductionMarketInputMode
    series: TechnicalCloseObservationSeries
    artifact_identity: TechnicalCloseSeriesArtifactIdentity
    save_result: MarketArtifactSaveResult | None

    def __post_init__(self) -> None:
        _require_mode(self.mode)
        _require_series(self.series)
        _require_identity(self.artifact_identity)
        if TechnicalCloseSeriesArtifactIdentity.from_series(self.series) != self.artifact_identity:
            raise MarketInputValidationError("result series identity must match artifact_identity.")
        if self.mode is ProductionMarketInputMode.FRESH:
            if not isinstance(self.save_result, MarketArtifactSaveResult):
                raise MarketInputValidationError("Fresh result requires MarketArtifactSaveResult.")
            if self.save_result.identity != self.artifact_identity:
                raise MarketInputValidationError("Fresh save_result identity must match artifact_identity.")
        elif self.mode is ProductionMarketInputMode.REPLAY:
            if self.save_result is not None:
                raise MarketInputValidationError("Replay result must not include save_result.")


@dataclass(frozen=True)
class ProductionTechnicalMarketInputService:
    """Coordinate explicit Fresh or Replay resolution for one technical close series.

    Fresh performs one provider fetch followed by one immutable store save. It is
    not transactional: if the fetch succeeds but the save fails, the operation
    fails and no fallback or compensating action is attempted.
    """

    source: TechnicalCloseSeriesSource
    store: TechnicalCloseSeriesStore

    def __post_init__(self) -> None:
        if not isinstance(self.source, TechnicalCloseSeriesSource):
            raise MarketInputValidationError("source must implement TechnicalCloseSeriesSource.")
        if not isinstance(self.store, TechnicalCloseSeriesStore):
            raise MarketInputValidationError("store must implement TechnicalCloseSeriesStore.")

    def resolve_fresh(self, request: TechnicalCloseSeriesRequest) -> ProductionTechnicalMarketInputResult:
        if not isinstance(request, TechnicalCloseSeriesRequest):
            raise MarketInputValidationError("request must be TechnicalCloseSeriesRequest.")
        series = _require_series(self.source.fetch(request))
        _validate_series_matches_request(series, request)
        identity = TechnicalCloseSeriesArtifactIdentity.from_series(series)
        save_result = self.store.save(series)
        if not isinstance(save_result, MarketArtifactSaveResult):
            raise MarketInputValidationError("store.save must return MarketArtifactSaveResult.")
        if save_result.identity != identity:
            raise MarketInputValidationError("store.save identity must match fetched series identity.")
        return ProductionTechnicalMarketInputResult(
            mode=ProductionMarketInputMode.FRESH,
            series=series,
            artifact_identity=identity,
            save_result=save_result,
        )

    def resolve_replay(
        self,
        identity: TechnicalCloseSeriesArtifactIdentity,
    ) -> ProductionTechnicalMarketInputResult:
        if not isinstance(identity, TechnicalCloseSeriesArtifactIdentity):
            raise MarketInputValidationError("identity must be TechnicalCloseSeriesArtifactIdentity.")
        series = self.store.get(identity)
        if series is None:
            raise MarketArtifactNotFoundError("Replay market artifact was not found.")
        series = _require_series(series)
        if TechnicalCloseSeriesArtifactIdentity.from_series(series) != identity:
            raise MarketInputValidationError("Replay series identity must match requested identity.")
        return ProductionTechnicalMarketInputResult(
            mode=ProductionMarketInputMode.REPLAY,
            series=series,
            artifact_identity=identity,
            save_result=None,
        )


def _require_mode(value: object) -> ProductionMarketInputMode:
    if not isinstance(value, ProductionMarketInputMode):
        raise MarketInputValidationError("mode must be ProductionMarketInputMode.")
    return value


def _require_series(value: object) -> TechnicalCloseObservationSeries:
    if not isinstance(value, TechnicalCloseObservationSeries):
        raise MarketInputValidationError("series must be TechnicalCloseObservationSeries.")
    return value


def _require_identity(value: object) -> TechnicalCloseSeriesArtifactIdentity:
    if not isinstance(value, TechnicalCloseSeriesArtifactIdentity):
        raise MarketInputValidationError("artifact_identity must be TechnicalCloseSeriesArtifactIdentity.")
    return value


def _validate_series_matches_request(
    series: TechnicalCloseObservationSeries,
    request: TechnicalCloseSeriesRequest,
) -> None:
    if series.symbol != request.symbol:
        raise MarketInputValidationError("source output symbol mismatch.")
    if series.provider_symbol != request.provider_symbol:
        raise MarketInputValidationError("source output provider_symbol mismatch.")
    if series.provider != request.provider:
        raise MarketInputValidationError("source output provider mismatch.")
    if series.valuation_date != request.valuation_date:
        raise MarketInputValidationError("source output valuation_date mismatch.")
    if series.timezone != request.timezone:
        raise MarketInputValidationError("source output timezone mismatch.")
    if series.close_basis != request.close_basis:
        raise MarketInputValidationError("source output close_basis mismatch.")
