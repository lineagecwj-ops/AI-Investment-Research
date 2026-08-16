from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from market_inputs import FilesystemTechnicalCloseSeriesStore
from market_inputs import ProductionMarketInputConfig
from market_inputs import ProductionMarketInputMode
from market_inputs import ProductionTechnicalFeatureMaterializer
from market_inputs import ProductionTechnicalMarketInputService
from market_inputs import TechnicalCloseBasis
from market_inputs import TechnicalCloseSeriesArtifactIdentity
from market_inputs import TechnicalCloseSeriesRequest
from market_inputs import TechnicalCloseSeriesSource
from market_inputs import TechnicalCloseSeriesStore
from market_inputs import TechnicalFeatureBundle
from market_inputs import TechnicalFeatureSet
from market_inputs import TechnicalMarketDataProvider
from market_inputs import YahooFinanceTechnicalCloseSeriesSource
from portfolio_generation import ExactVersionPolicyResolver
from portfolio_generation import MonitoringEvaluationOutput
from portfolio_generation import TechnicalRiskPortfolioEvaluator
from portfolio_generation import TechnicalRiskProductionInputProvider
from portfolio_generation import build_risk_artifact_id
from portfolio_sources import LocalJsonPortfolioSnapshotLoader
from portfolio_state import PortfolioSnapshot
from portfolio_state import RiskEvaluationInput
from risk import RiskArtifact
from risk import RiskRegistry
from risk_evaluation import ProductionTechnicalRiskPolicy
from risk_evaluation import RiskFeatureInput
from risk_evaluation import RiskSignalProductionInput
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation import TECH_AS_OF_CLOSE_FEATURE_VERSION
from risk_evaluation import TECH_RSI14_FEATURE_ID
from risk_evaluation import TECH_RSI14_FEATURE_VERSION
from risk_evaluation import TECH_SMA20_FEATURE_ID
from risk_evaluation import TECH_SMA20_FEATURE_VERSION
from risk_evaluation import TECH_SMA60_FEATURE_ID
from risk_evaluation import TECH_SMA60_FEATURE_VERSION
from risk_persistence import SQLiteTechnicalPortfolioRiskPersistenceCoordinator
from risk_persistence import TechnicalPortfolioRiskPersistenceResult


TECHNICAL_RISK_FEATURE_SET_VERSION_V1 = "technical_risk_feature_set_v1"
TECHNICAL_RISK_DEFINITION_VERSION_V1 = "technical_risk_v1"
TECHNICAL_RISK_MONITORING_POLICY_VERSION_V1 = "technical_risk_monitoring_v1"
TECHNICAL_RISK_OBSERVATION_LOOKBACK_DAYS_V1 = 120

_FEATURE_VERSIONS = {
    TECH_AS_OF_CLOSE_FEATURE_ID: TECH_AS_OF_CLOSE_FEATURE_VERSION,
    TECH_RSI14_FEATURE_ID: TECH_RSI14_FEATURE_VERSION,
    TECH_SMA20_FEATURE_ID: TECH_SMA20_FEATURE_VERSION,
    TECH_SMA60_FEATURE_ID: TECH_SMA60_FEATURE_VERSION,
}


class ProductionTechnicalRiskRuntimeError(ValueError):
    """Raised when the manual Technical Risk runtime fails closed."""


@dataclass(frozen=True)
class ProductionTechnicalRiskRuntimeRequest:
    portfolio_source_path: str | Path
    as_of_date: date
    valuation_date: date
    market_mode: ProductionMarketInputMode | str
    created_at: datetime
    policy: ProductionTechnicalRiskPolicy
    policy_version: str
    db_path: str | Path
    project_root: str | Path
    replay_identities: Mapping[str, TechnicalCloseSeriesArtifactIdentity] | None = None
    provider_symbol_by_symbol: Mapping[str, str] | None = None
    feature_version: str = TECHNICAL_RISK_FEATURE_SET_VERSION_V1
    model_version: str | None = None
    risk_definition_version: str = TECHNICAL_RISK_DEFINITION_VERSION_V1
    monitoring_policy_version: str = TECHNICAL_RISK_MONITORING_POLICY_VERSION_V1
    timezone: str = "Asia/Taipei"
    close_basis: TechnicalCloseBasis | str = TechnicalCloseBasis.ADJUSTED_CLOSE_IF_AVAILABLE_ELSE_CLOSE
    provider: TechnicalMarketDataProvider | str = TechnicalMarketDataProvider.YAHOO_FINANCE_V1

    def __post_init__(self) -> None:
        if not isinstance(self.policy, ProductionTechnicalRiskPolicy):
            raise ProductionTechnicalRiskRuntimeError("request requires ProductionTechnicalRiskPolicy.")
        if self.policy_version != self.policy.policy_version:
            raise ProductionTechnicalRiskRuntimeError("policy_version must exactly match pinned policy.")
        if type(self.as_of_date) is not date or type(self.valuation_date) is not date:
            raise ProductionTechnicalRiskRuntimeError("as_of_date and valuation_date must be dates.")
        if self.as_of_date != self.valuation_date:
            raise ProductionTechnicalRiskRuntimeError("Technical Risk v1 runtime requires as_of_date equal valuation_date.")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ProductionTechnicalRiskRuntimeError("created_at must be timezone-aware.")
        object.__setattr__(self, "market_mode", ProductionMarketInputMode(self.market_mode))
        object.__setattr__(self, "close_basis", TechnicalCloseBasis(self.close_basis))
        object.__setattr__(self, "provider", TechnicalMarketDataProvider(self.provider))
        object.__setattr__(self, "portfolio_source_path", Path(self.portfolio_source_path))
        object.__setattr__(self, "db_path", Path(self.db_path))
        object.__setattr__(self, "project_root", Path(self.project_root))
        object.__setattr__(self, "replay_identities", MappingProxyType(dict(self.replay_identities or {})))
        object.__setattr__(self, "provider_symbol_by_symbol", MappingProxyType(dict(self.provider_symbol_by_symbol or {})))


@dataclass(frozen=True)
class ProductionTechnicalRiskRuntimeResult:
    calculation_id: str
    generation_key: str
    feature_set_checksum: str
    portfolio_id: str
    snapshot_id: str
    snapshot_checksum: str
    valuation_date: date
    active_position_ids: tuple[str, ...]
    active_symbols: tuple[str, ...]
    market_revision_ids_by_symbol: Mapping[str, str]
    persistence_result: TechnicalPortfolioRiskPersistenceResult

    def __post_init__(self) -> None:
        object.__setattr__(self, "market_revision_ids_by_symbol", MappingProxyType(dict(self.market_revision_ids_by_symbol)))

    @property
    def run_record(self):
        return self.persistence_result.run_record

    @property
    def run_save_result(self):
        return self.persistence_result.run_save_result


@dataclass(frozen=True)
class ProductionTechnicalRiskRuntime:
    market_source: TechnicalCloseSeriesSource | None = None
    market_store: TechnicalCloseSeriesStore | None = None
    portfolio_loader: LocalJsonPortfolioSnapshotLoader = LocalJsonPortfolioSnapshotLoader()
    feature_materializer: ProductionTechnicalFeatureMaterializer = ProductionTechnicalFeatureMaterializer()

    def run(self, request: ProductionTechnicalRiskRuntimeRequest) -> ProductionTechnicalRiskRuntimeResult:
        if not isinstance(request, ProductionTechnicalRiskRuntimeRequest):
            raise ProductionTechnicalRiskRuntimeError("run requires ProductionTechnicalRiskRuntimeRequest.")
        snapshot = self._load_snapshot(request)
        active_positions = tuple(position for position in snapshot.positions if position.position_id in snapshot.active_position_ids)
        if not active_positions:
            raise ProductionTechnicalRiskRuntimeError("portfolio snapshot has zero active positions.")
        active_symbols = tuple(sorted({position.symbol for position in active_positions}))
        if request.market_mode is ProductionMarketInputMode.FRESH:
            _validate_provider_symbol_mappings(request, active_symbols)

        bundles = tuple(self._materialize_symbol(request, symbol) for symbol in active_symbols)
        feature_set = TechnicalFeatureSet(bundles=bundles)
        if feature_set.valuation_date != request.valuation_date:
            raise ProductionTechnicalRiskRuntimeError("TechnicalFeatureSet valuation_date mismatch.")
        if feature_set.symbols != active_symbols:
            raise ProductionTechnicalRiskRuntimeError("TechnicalFeatureSet symbols must exactly match active symbols.")

        evaluation_input = RiskEvaluationInput.from_snapshot(
            snapshot,
            feature_version=request.feature_version,
            feature_set_checksum=feature_set.technical_feature_set_checksum,
            model_version=request.model_version,
            risk_definition_version=request.risk_definition_version,
            risk_policy_version=request.policy_version,
            monitoring_policy_version=request.monitoring_policy_version,
        )
        provider = _FeatureSetProductionInputProvider(feature_set=feature_set, evaluation_input=evaluation_input)
        evaluator = TechnicalRiskPortfolioEvaluator(
            input_provider=provider,
            policy=request.policy,
            created_at=request.created_at,
        )
        resolver = ExactVersionPolicyResolver(
            risk_registry=RiskRegistry(),
            allowed_risk_policy_versions=(request.policy_version,),
            allowed_monitoring_policy_versions=(request.monitoring_policy_version,),
        )
        coordinator = SQLiteTechnicalPortfolioRiskPersistenceCoordinator(
            db_path=request.db_path,
            risk_evaluator=evaluator,
            monitoring_evaluator=_NoOpMonitoringEvaluator(),
            policy_resolver=resolver,
        )
        persistence_result = coordinator.generate_and_persist(
            snapshot,
            evaluation_input,
            created_at=request.created_at,
        )
        return ProductionTechnicalRiskRuntimeResult(
            calculation_id=evaluation_input.calculation_id,
            generation_key=evaluation_input.generation_key,
            feature_set_checksum=feature_set.technical_feature_set_checksum,
            portfolio_id=snapshot.portfolio_id,
            snapshot_id=snapshot.snapshot_id,
            snapshot_checksum=snapshot.checksum,
            valuation_date=request.valuation_date,
            active_position_ids=evaluation_input.active_position_ids,
            active_symbols=active_symbols,
            market_revision_ids_by_symbol={bundle.symbol: bundle.market_revision_id for bundle in feature_set.bundles},
            persistence_result=persistence_result,
        )

    def _load_snapshot(self, request: ProductionTechnicalRiskRuntimeRequest) -> PortfolioSnapshot:
        try:
            snapshot = self.portfolio_loader.load(request.portfolio_source_path)
        except Exception as exc:
            raise ProductionTechnicalRiskRuntimeError("portfolio snapshot load failed.") from exc
        if snapshot.as_of_date != request.as_of_date:
            raise ProductionTechnicalRiskRuntimeError("portfolio snapshot as_of_date mismatch.")
        if snapshot.valuation_date != request.valuation_date:
            raise ProductionTechnicalRiskRuntimeError("portfolio snapshot valuation_date mismatch.")
        return snapshot

    def _materialize_symbol(self, request: ProductionTechnicalRiskRuntimeRequest, symbol: str) -> TechnicalFeatureBundle:
        service = ProductionTechnicalMarketInputService(
            source=self.market_source or YahooFinanceTechnicalCloseSeriesSource(),
            store=self.market_store or FilesystemTechnicalCloseSeriesStore(
                ProductionMarketInputConfig.from_project_root(request.project_root)
            ),
        )
        try:
            if request.market_mode is ProductionMarketInputMode.FRESH:
                market_result = service.resolve_fresh(_technical_close_request(request, symbol))
            else:
                identity = request.replay_identities.get(symbol)
                if identity is None:
                    raise ProductionTechnicalRiskRuntimeError(f"Replay identity missing for active symbol: {symbol}.")
                market_result = service.resolve_replay(identity)
        except ProductionTechnicalRiskRuntimeError:
            raise
        except Exception as exc:
            raise ProductionTechnicalRiskRuntimeError(f"market input resolution failed for {symbol}.") from exc
        try:
            bundle = self.feature_materializer.materialize(market_result.series)
        except Exception as exc:
            raise ProductionTechnicalRiskRuntimeError(f"feature materialization failed for {symbol}.") from exc
        if bundle.symbol != symbol:
            raise ProductionTechnicalRiskRuntimeError("feature bundle symbol mismatch.")
        if bundle.valuation_date != request.valuation_date:
            raise ProductionTechnicalRiskRuntimeError("feature bundle valuation_date mismatch.")
        return bundle


def _technical_close_request(request: ProductionTechnicalRiskRuntimeRequest, symbol: str) -> TechnicalCloseSeriesRequest:
    return TechnicalCloseSeriesRequest(
        symbol=symbol,
        provider_symbol=request.provider_symbol_by_symbol[symbol],
        valuation_date=request.valuation_date,
        start_date=request.valuation_date - timedelta(days=TECHNICAL_RISK_OBSERVATION_LOOKBACK_DAYS_V1),
        timezone=request.timezone,
        close_basis=request.close_basis,
        provider=request.provider,
    )


def _validate_provider_symbol_mappings(
    request: ProductionTechnicalRiskRuntimeRequest,
    active_symbols: tuple[str, ...],
) -> None:
    for symbol in active_symbols:
        if symbol not in request.provider_symbol_by_symbol:
            raise ProductionTechnicalRiskRuntimeError(f"provider symbol mapping missing for active symbol: {symbol}.")
        provider_symbol = request.provider_symbol_by_symbol[symbol]
        if type(provider_symbol) is not str or not provider_symbol.strip() or "\n" in provider_symbol or "\r" in provider_symbol:
            raise ProductionTechnicalRiskRuntimeError(f"provider symbol mapping invalid for active symbol: {symbol}.")


@dataclass(frozen=True)
class _FeatureSetProductionInputProvider(TechnicalRiskProductionInputProvider):
    feature_set: TechnicalFeatureSet
    evaluation_input: RiskEvaluationInput

    def resolve(self, position, context, risk_artifact_id: str) -> RiskSignalProductionInput:
        position_id = self._position_id_for_artifact(risk_artifact_id)
        bundle = self._bundle_for_symbol(position.symbol)
        features = tuple(
            RiskFeatureInput(
                feature_id=feature_id,
                feature_version=_FEATURE_VERSIONS[feature_id],
                portfolio_id=self.evaluation_input.portfolio_id,
                position_id=position_id,
                symbol=position.symbol,
                as_of_date=self.evaluation_input.as_of_date,
                feature_date=self.evaluation_input.as_of_date,
                value=value,
                source_artifact_id=bundle.market_revision_id,
                source_checksum=_feature_source_checksum(bundle, feature_id),
                calculation_id=self.evaluation_input.calculation_id,
            )
            for feature_id, value in bundle.features.items()
        )
        return RiskSignalProductionInput(
            portfolio_id=self.evaluation_input.portfolio_id,
            position_id=position_id,
            symbol=position.symbol,
            as_of_date=self.evaluation_input.as_of_date,
            valuation_date=self.evaluation_input.valuation_date,
            feature_version=self.evaluation_input.feature_version,
            feature_values=features,
            model_version=self.evaluation_input.model_version,
            model_metadata={"technical_feature_set_checksum": self.evaluation_input.feature_set_checksum},
            exposure_metadata={},
            source_artifact_ids=(bundle.market_revision_id,),
            source_checksums=tuple(_feature_source_checksum(bundle, feature_id) for feature_id in bundle.features),
            calculation_id=self.evaluation_input.calculation_id,
        )

    def _position_id_for_artifact(self, risk_artifact_id: str) -> str:
        matches = tuple(
            position_id
            for position_id in self.evaluation_input.active_position_ids
            if build_risk_artifact_id(self.evaluation_input.calculation_id, position_id) == risk_artifact_id
        )
        if len(matches) != 1:
            raise ProductionTechnicalRiskRuntimeError("risk_artifact_id does not map to exactly one active position.")
        return matches[0]

    def _bundle_for_symbol(self, symbol: str) -> TechnicalFeatureBundle:
        matches = tuple(bundle for bundle in self.feature_set.bundles if bundle.symbol == symbol)
        if len(matches) != 1:
            raise ProductionTechnicalRiskRuntimeError(f"feature bundle missing for symbol: {symbol}.")
        return matches[0]


@dataclass(frozen=True)
class _NoOpMonitoringArtifact:
    artifact_id: str


@dataclass(frozen=True)
class _NoOpMonitoringEvaluator:
    def evaluate(self, risk_artifact: RiskArtifact, context, monitoring_artifact_id: str) -> MonitoringEvaluationOutput:
        return MonitoringEvaluationOutput(
            position_id=risk_artifact.calculation_metadata["technical_position_id"],
            symbol=context.symbol,
            monitoring_artifact=_NoOpMonitoringArtifact(monitoring_artifact_id),
        )


def _feature_source_checksum(bundle: TechnicalFeatureBundle, feature_id: str) -> str:
    return f"{bundle.feature_bundle_checksum}:{feature_id}"
