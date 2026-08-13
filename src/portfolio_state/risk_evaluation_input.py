from dataclasses import dataclass
from datetime import date

from portfolio_state.generation_identity import GENERATION_IDENTITY_SCHEMA_VERSION
from portfolio_state.generation_identity import build_generation_identity_material
from portfolio_state.generation_identity import generate_calculation_id
from portfolio_state.generation_identity import generate_generation_key
from portfolio_state.portfolio_snapshot import PortfolioSnapshot
from portfolio_state.validation import GenerationIdentityMismatchError
from portfolio_state.validation import PortfolioStateValidationError


class RiskEvaluationInputError(PortfolioStateValidationError):
    """Raised when deterministic risk evaluation input is invalid."""


@dataclass(frozen=True)
class RiskEvaluationInput:
    """Deterministic upstream contract for future risk generation."""

    portfolio_id: str
    snapshot_id: str
    snapshot_checksum: str
    as_of_date: date
    valuation_date: date
    active_position_ids: tuple[str, ...]
    feature_version: str
    model_version: str | None
    risk_definition_version: str
    risk_policy_version: str
    monitoring_policy_version: str
    generation_key: str | None = None
    calculation_id: str | None = None
    generation_schema_version: str = GENERATION_IDENTITY_SCHEMA_VERSION

    def __post_init__(self):
        required = {
            "portfolio_id": self.portfolio_id,
            "snapshot_id": self.snapshot_id,
            "snapshot_checksum": self.snapshot_checksum,
            "feature_version": self.feature_version,
            "risk_definition_version": self.risk_definition_version,
            "risk_policy_version": self.risk_policy_version,
            "monitoring_policy_version": self.monitoring_policy_version,
            "generation_schema_version": self.generation_schema_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RiskEvaluationInputError(f"RiskEvaluationInput missing required fields: {', '.join(missing)}")
        if self.generation_schema_version != GENERATION_IDENTITY_SCHEMA_VERSION:
            raise RiskEvaluationInputError(
                f"Unsupported RiskEvaluationInput generation_schema_version: {self.generation_schema_version}."
            )
        if not isinstance(self.as_of_date, date):
            raise RiskEvaluationInputError("RiskEvaluationInput as_of_date must be a date.")
        if not isinstance(self.valuation_date, date):
            raise RiskEvaluationInputError("RiskEvaluationInput valuation_date must be a date.")
        if not isinstance(self.active_position_ids, tuple):
            raise RiskEvaluationInputError("RiskEvaluationInput active_position_ids must be a tuple.")
        if not all(isinstance(position_id, str) and position_id for position_id in self.active_position_ids):
            raise RiskEvaluationInputError("RiskEvaluationInput active_position_ids must contain non-empty strings.")

        active_position_ids = tuple(sorted(self.active_position_ids))
        object.__setattr__(self, "active_position_ids", active_position_ids)

        expected_generation_key = generate_generation_key(self.identity_material)
        expected_calculation_id = generate_calculation_id(expected_generation_key)
        if self.generation_key is not None and self.generation_key != expected_generation_key:
            raise GenerationIdentityMismatchError(
                f"RiskEvaluationInput generation_key mismatch: expected {expected_generation_key}, got {self.generation_key}."
            )
        if self.calculation_id is not None and self.calculation_id != expected_calculation_id:
            raise GenerationIdentityMismatchError(
                f"RiskEvaluationInput calculation_id mismatch: expected {expected_calculation_id}, got {self.calculation_id}."
            )
        object.__setattr__(self, "generation_key", expected_generation_key)
        object.__setattr__(self, "calculation_id", expected_calculation_id)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: PortfolioSnapshot,
        *,
        feature_version: str,
        model_version: str | None,
        risk_definition_version: str,
        risk_policy_version: str,
        monitoring_policy_version: str,
    ) -> "RiskEvaluationInput":
        if not isinstance(snapshot, PortfolioSnapshot):
            raise RiskEvaluationInputError("RiskEvaluationInput requires PortfolioSnapshot input.")
        return cls(
            portfolio_id=snapshot.portfolio_id,
            snapshot_id=snapshot.snapshot_id,
            snapshot_checksum=snapshot.checksum,
            as_of_date=snapshot.as_of_date,
            valuation_date=snapshot.valuation_date,
            active_position_ids=snapshot.active_position_ids,
            feature_version=feature_version,
            model_version=model_version,
            risk_definition_version=risk_definition_version,
            risk_policy_version=risk_policy_version,
            monitoring_policy_version=monitoring_policy_version,
        )

    @property
    def identity_material(self) -> dict[str, object]:
        return build_generation_identity_material(
            portfolio_id=self.portfolio_id,
            snapshot_id=self.snapshot_id,
            snapshot_checksum=self.snapshot_checksum,
            as_of_date=self.as_of_date,
            valuation_date=self.valuation_date,
            feature_version=self.feature_version,
            model_version=self.model_version,
            risk_definition_version=self.risk_definition_version,
            risk_policy_version=self.risk_policy_version,
            monitoring_policy_version=self.monitoring_policy_version,
            generation_schema_version=self.generation_schema_version,
        )
