from dataclasses import dataclass
from enum import StrEnum


class PortfolioRiskGenerationStatus(StrEnum):
    """Application-level status for portfolio risk generation orchestration."""

    SUCCESS = "SUCCESS"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    RISK_EVALUATION_FAILED = "RISK_EVALUATION_FAILED"
    MONITORING_FAILED = "MONITORING_FAILED"
    ALREADY_GENERATED = "ALREADY_GENERATED"


@dataclass(frozen=True)
class PortfolioPositionGenerationResult:
    """Position-level generation diagnostic result."""

    position_id: str
    symbol: str
    risk_artifact_id: str
    monitoring_artifact_id: str
    status: PortfolioRiskGenerationStatus | str
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.position_id:
            raise ValueError("PortfolioPositionGenerationResult requires position_id.")
        if not self.symbol:
            raise ValueError("PortfolioPositionGenerationResult requires symbol.")
        if not self.risk_artifact_id:
            raise ValueError("PortfolioPositionGenerationResult requires risk_artifact_id.")
        if not self.monitoring_artifact_id:
            raise ValueError("PortfolioPositionGenerationResult requires monitoring_artifact_id.")
        if not isinstance(self.warnings, tuple):
            raise ValueError("PortfolioPositionGenerationResult warnings must be a tuple.")
        if not isinstance(self.diagnostics, tuple):
            raise ValueError("PortfolioPositionGenerationResult diagnostics must be a tuple.")
        object.__setattr__(self, "status", PortfolioRiskGenerationStatus(self.status))


@dataclass(frozen=True)
class PortfolioRiskGenerationResult:
    """Immutable generation service result envelope."""

    status: PortfolioRiskGenerationStatus | str
    generation_key: str
    calculation_id: str
    portfolio_id: str
    snapshot_id: str
    attempted_position_ids: tuple[str, ...]
    succeeded_position_ids: tuple[str, ...]
    failed_position_ids: tuple[str, ...]
    position_results: tuple[PortfolioPositionGenerationResult, ...]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        required = {
            "generation_key": self.generation_key,
            "calculation_id": self.calculation_id,
            "portfolio_id": self.portfolio_id,
            "snapshot_id": self.snapshot_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"PortfolioRiskGenerationResult missing required fields: {', '.join(missing)}")
        tuple_fields = {
            "attempted_position_ids": self.attempted_position_ids,
            "succeeded_position_ids": self.succeeded_position_ids,
            "failed_position_ids": self.failed_position_ids,
            "position_results": self.position_results,
            "errors": self.errors,
            "warnings": self.warnings,
        }
        for name, value in tuple_fields.items():
            if not isinstance(value, tuple):
                raise ValueError(f"PortfolioRiskGenerationResult {name} must be a tuple.")
        object.__setattr__(self, "status", PortfolioRiskGenerationStatus(self.status))
