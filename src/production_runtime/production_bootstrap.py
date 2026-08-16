from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from portfolio_sources import LocalJsonPortfolioSnapshotLoader
from portfolio_sources import PortfolioSourceError
from production_runtime.policy_pin import ProductionPolicyPinError
from production_runtime.policy_pin import load_production_policy_pin
from production_runtime.production_config import ProductionRuntimeConfig
from production_runtime.production_config import ProductionRuntimeConfigError
from production_runtime.symbol_mapping import ProviderSymbolMappingError
from production_runtime.symbol_mapping import load_provider_symbol_mapping
from risk_persistence import RiskPersistenceHealthStatus
from risk_persistence import SQLiteRiskPersistenceBootstrapper
from risk_persistence import SQLiteRiskPersistenceHealthChecker


class ProductionEnvironmentComponentStatus(StrEnum):
    READY = "READY"
    MISSING = "MISSING"
    INVALID = "INVALID"
    ERROR = "ERROR"


class ProductionBootstrapStatus(StrEnum):
    CREATED = "CREATED"
    ALREADY_READY = "ALREADY_READY"
    MIGRATED = "MIGRATED"


class ProductionEnvironmentBootstrapError(ValueError):
    """Raised when explicit production environment bootstrap cannot proceed safely."""


@dataclass(frozen=True)
class ProductionEnvironmentStatus:
    production_root: ProductionEnvironmentComponentStatus
    portfolio_source: ProductionEnvironmentComponentStatus
    database: ProductionEnvironmentComponentStatus
    database_health: RiskPersistenceHealthStatus
    market_artifact_root: ProductionEnvironmentComponentStatus
    symbol_mapping: ProductionEnvironmentComponentStatus
    policy_pin: ProductionEnvironmentComponentStatus

    @property
    def ready_for_runtime(self) -> bool:
        return (
            self.production_root is ProductionEnvironmentComponentStatus.READY
            and self.portfolio_source is ProductionEnvironmentComponentStatus.READY
            and self.database is ProductionEnvironmentComponentStatus.READY
            and self.database_health is RiskPersistenceHealthStatus.READY
            and self.market_artifact_root is ProductionEnvironmentComponentStatus.READY
            and self.symbol_mapping is ProductionEnvironmentComponentStatus.READY
            and self.policy_pin is ProductionEnvironmentComponentStatus.READY
        )


@dataclass(frozen=True)
class ProductionBootstrapResult:
    status: ProductionBootstrapStatus
    persistence_status: str
    environment_status: ProductionEnvironmentStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ProductionBootstrapStatus(self.status))


@dataclass(frozen=True)
class ProductionEnvironmentInspector:
    config: ProductionRuntimeConfig

    def __post_init__(self) -> None:
        if not isinstance(self.config, ProductionRuntimeConfig):
            raise ProductionRuntimeConfigError("config must be ProductionRuntimeConfig.")

    def inspect(self) -> ProductionEnvironmentStatus:
        health = SQLiteRiskPersistenceHealthChecker(self.config.risk_persistence_config).check()
        return ProductionEnvironmentStatus(
            production_root=_directory_status(self.config.production_root),
            portfolio_source=_portfolio_status(self.config),
            database=_database_status(self.config),
            database_health=health.status,
            market_artifact_root=_directory_status(self.config.market_artifact_root),
            symbol_mapping=_symbol_mapping_status(self.config),
            policy_pin=_policy_pin_status(self.config),
        )


@dataclass(frozen=True)
class ProductionEnvironmentBootstrapper:
    config: ProductionRuntimeConfig

    def __post_init__(self) -> None:
        if not isinstance(self.config, ProductionRuntimeConfig):
            raise ProductionRuntimeConfigError("config must be ProductionRuntimeConfig.")

    def bootstrap(self) -> ProductionBootstrapResult:
        for directory in (
            self.config.production_root,
            self.config.portfolio_root,
            self.config.config_root,
            self.config.market_artifact_root,
        ):
            if directory.exists() and not directory.is_dir():
                raise ProductionEnvironmentBootstrapError("production bootstrap path conflicts with a file.")
        if self.config.db_path.exists() and self.config.db_path.is_dir():
            raise ProductionEnvironmentBootstrapError("production DB path conflicts with a directory.")
        self.config.production_root.mkdir(parents=True, exist_ok=True)
        self.config.portfolio_root.mkdir(parents=True, exist_ok=True)
        self.config.config_root.mkdir(parents=True, exist_ok=True)
        self.config.market_artifact_root.mkdir(parents=True, exist_ok=True)
        persistence_result = SQLiteRiskPersistenceBootstrapper(self.config.risk_persistence_config).bootstrap()
        status = ProductionEnvironmentInspector(self.config).inspect()
        bootstrap_status = ProductionBootstrapStatus(persistence_result.status.value)
        return ProductionBootstrapResult(
            status=bootstrap_status,
            persistence_status=persistence_result.status.value,
            environment_status=status,
        )


def _directory_status(path) -> ProductionEnvironmentComponentStatus:
    if not path.exists():
        return ProductionEnvironmentComponentStatus.MISSING
    if not path.is_dir():
        return ProductionEnvironmentComponentStatus.INVALID
    return ProductionEnvironmentComponentStatus.READY


def _database_status(config: ProductionRuntimeConfig) -> ProductionEnvironmentComponentStatus:
    if not config.db_path.exists():
        return ProductionEnvironmentComponentStatus.MISSING
    if config.db_path.is_dir():
        return ProductionEnvironmentComponentStatus.INVALID
    return ProductionEnvironmentComponentStatus.READY


def _portfolio_status(config: ProductionRuntimeConfig) -> ProductionEnvironmentComponentStatus:
    if not config.portfolio_source_path.exists():
        return ProductionEnvironmentComponentStatus.MISSING
    if not config.portfolio_source_path.is_file():
        return ProductionEnvironmentComponentStatus.INVALID
    try:
        LocalJsonPortfolioSnapshotLoader().load(config.portfolio_source_path)
    except PortfolioSourceError:
        return ProductionEnvironmentComponentStatus.INVALID
    return ProductionEnvironmentComponentStatus.READY


def _symbol_mapping_status(config: ProductionRuntimeConfig) -> ProductionEnvironmentComponentStatus:
    if not config.symbol_mapping_path.exists():
        return ProductionEnvironmentComponentStatus.MISSING
    if not config.symbol_mapping_path.is_file():
        return ProductionEnvironmentComponentStatus.INVALID
    try:
        load_provider_symbol_mapping(config.symbol_mapping_path)
    except ProviderSymbolMappingError:
        return ProductionEnvironmentComponentStatus.INVALID
    return ProductionEnvironmentComponentStatus.READY


def _policy_pin_status(config: ProductionRuntimeConfig) -> ProductionEnvironmentComponentStatus:
    if not config.policy_pin_path.exists():
        return ProductionEnvironmentComponentStatus.MISSING
    if not config.policy_pin_path.is_file():
        return ProductionEnvironmentComponentStatus.INVALID
    try:
        load_production_policy_pin(config.policy_pin_path)
    except ProductionPolicyPinError:
        return ProductionEnvironmentComponentStatus.INVALID
    return ProductionEnvironmentComponentStatus.READY
