from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from market_inputs import ProductionMarketInputConfig
from risk_persistence import RiskPersistenceProductionConfig


PRODUCTION_RUNTIME_CONFIG_VERSION = "1"
PRODUCTION_ROOT_ALIAS = "data/production"
PRODUCTION_PORTFOLIO_SOURCE_ALIAS = "data/production/portfolio/portfolio.json"
PRODUCTION_CONFIG_ROOT_ALIAS = "data/production/config"
PRODUCTION_SYMBOL_MAPPING_ALIAS = "data/production/config/provider_symbol_mapping.json"
PRODUCTION_POLICY_PIN_ALIAS = "data/production/config/policy_pin.json"


class ProductionRuntimeConfigError(ValueError):
    """Raised when controlled production runtime configuration is invalid."""


@dataclass(frozen=True)
class ProductionRuntimeConfig:
    """Controlled production runtime paths derived from one explicit project root."""

    project_root: Path
    config_version: str = PRODUCTION_RUNTIME_CONFIG_VERSION

    def __post_init__(self) -> None:
        if self.config_version != PRODUCTION_RUNTIME_CONFIG_VERSION:
            raise ProductionRuntimeConfigError("unsupported production runtime config_version.")
        root = _resolve_existing_project_root(self.project_root)
        object.__setattr__(self, "project_root", root)

    @classmethod
    def from_project_root(cls, project_root: str | Path) -> "ProductionRuntimeConfig":
        return cls(project_root=Path(project_root))

    @property
    def production_root(self) -> Path:
        return self.project_root / PRODUCTION_ROOT_ALIAS

    @property
    def portfolio_root(self) -> Path:
        return self.production_root / "portfolio"

    @property
    def portfolio_source_path(self) -> Path:
        return self.project_root / PRODUCTION_PORTFOLIO_SOURCE_ALIAS

    @property
    def db_path(self) -> Path:
        return self.risk_persistence_config.db_path

    @property
    def backup_directory(self) -> Path:
        return self.risk_persistence_config.backup_directory

    @property
    def config_root(self) -> Path:
        return self.project_root / PRODUCTION_CONFIG_ROOT_ALIAS

    @property
    def symbol_mapping_path(self) -> Path:
        return self.project_root / PRODUCTION_SYMBOL_MAPPING_ALIAS

    @property
    def policy_pin_path(self) -> Path:
        return self.project_root / PRODUCTION_POLICY_PIN_ALIAS

    @property
    def market_input_config(self) -> ProductionMarketInputConfig:
        return ProductionMarketInputConfig.from_project_root(self.project_root)

    @property
    def market_artifact_root(self) -> Path:
        return self.market_input_config.artifact_root

    @property
    def risk_persistence_config(self) -> RiskPersistenceProductionConfig:
        return RiskPersistenceProductionConfig.from_project_root(self.project_root)


def _resolve_existing_project_root(project_root: str | Path) -> Path:
    if isinstance(project_root, str) and not project_root:
        raise ProductionRuntimeConfigError("project_root must be a non-empty path.")
    try:
        root = Path(project_root).expanduser().resolve()
    except (RuntimeError, TypeError, OSError) as exc:
        raise ProductionRuntimeConfigError("project_root must be path-like.") from exc
    if not root.exists():
        raise ProductionRuntimeConfigError("project_root must exist.")
    if not root.is_dir():
        raise ProductionRuntimeConfigError("project_root must be a directory.")
    return root
