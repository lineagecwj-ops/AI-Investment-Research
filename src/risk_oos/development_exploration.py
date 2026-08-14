from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from typing import Mapping

from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.candidate_evaluator import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos.candidate_evaluator import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1
from risk_oos.rule_candidates import TECH_RISK_NUMERIC_REPRESENTATION_V1
from risk_oos.rule_candidates import TechnicalRiskCandidateFamily
from risk_oos.rule_candidates import TechnicalRiskRuleCandidateSpec
from risk_oos.rule_candidates import TechnicalRiskThresholdSet


TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1 = "TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1"
TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1 = "TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1"
TECH_RISK_CANDIDATE_SET_CONTRACT_V1 = "TECH_RISK_CANDIDATE_SET_CONTRACT_V1"


class TechnicalRiskDevelopmentExplorationError(Exception):
    """Raised when Development exploration contracts are invalid."""


@dataclass(frozen=True)
class TechnicalRiskCandidateIdentity:
    """Threshold-independent identity echo for one Technical Risk candidate."""

    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str

    def __post_init__(self):
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.candidate_version, "candidate_version")
        _require_text(self.candidate_structural_checksum, "candidate_structural_checksum")

    @classmethod
    def from_candidate_spec(cls, candidate_spec: TechnicalRiskRuleCandidateSpec) -> "TechnicalRiskCandidateIdentity":
        return cls(
            candidate_id=candidate_spec.policy_candidate_id,
            candidate_version=candidate_spec.candidate_version,
            candidate_structural_checksum=candidate_spec.candidate_structural_checksum,
        )


@dataclass(frozen=True)
class TechnicalRiskThresholdIdentity:
    """Identity echo for one frozen Technical Risk threshold set."""

    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str

    def __post_init__(self):
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_version, "threshold_set_version")
        _require_text(self.threshold_set_checksum, "threshold_set_checksum")

    @classmethod
    def from_threshold_set(cls, threshold_set: TechnicalRiskThresholdSet) -> "TechnicalRiskThresholdIdentity":
        return cls(
            threshold_set_id=threshold_set.threshold_set_id,
            threshold_set_version=threshold_set.threshold_set_version,
            threshold_set_checksum=threshold_set.threshold_set_checksum,
        )


@dataclass(frozen=True)
class ThresholdCandidateGenerationContract:
    """Research metadata describing how threshold candidates were generated."""

    generation_id: str | None
    generation_version: str
    generation_method_id: str
    generation_method_version: str
    numeric_representation_version: str
    numeric_context_version: str
    candidate_family: TechnicalRiskCandidateFamily
    source_spec_version: str
    generated_threshold_set_ids: tuple[str, ...]
    generated_threshold_set_checksums: tuple[str, ...]
    generation_checksum: str | None = None
    created_at: datetime | None = None
    generated_at: datetime | None = None
    approved_at: datetime | None = None

    def __post_init__(self):
        _require_text(self.generation_version, "generation_version")
        _require_text(self.generation_method_id, "generation_method_id")
        _require_text(self.generation_method_version, "generation_method_version")
        _require_text(self.source_spec_version, "source_spec_version")
        _require_version(
            self.numeric_representation_version,
            TECH_RISK_NUMERIC_REPRESENTATION_V1,
            "numeric_representation_version",
        )
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        if not isinstance(self.candidate_family, TechnicalRiskCandidateFamily):
            object.__setattr__(self, "candidate_family", TechnicalRiskCandidateFamily(self.candidate_family))
        threshold_ids, threshold_checksums = _canonical_threshold_identity_parts(
            self.generated_threshold_set_ids,
            self.generated_threshold_set_checksums,
        )
        object.__setattr__(self, "generated_threshold_set_ids", threshold_ids)
        object.__setattr__(self, "generated_threshold_set_checksums", threshold_checksums)
        checksum = _threshold_generation_checksum(self)
        identity = _stable_id(
            "technical_risk_threshold_candidate_generation",
            {
                "generation_checksum": checksum,
            },
        )
        if self.generation_id is not None and self.generation_id != identity:
            raise TechnicalRiskDevelopmentExplorationError("generation_id mismatch.")
        if self.generation_checksum is not None and self.generation_checksum != checksum:
            raise TechnicalRiskDevelopmentExplorationError("generation_checksum mismatch.")
        object.__setattr__(self, "generation_id", identity)
        object.__setattr__(self, "generation_checksum", checksum)


@dataclass(frozen=True)
class TechnicalRiskCandidateSet:
    """Frozen set of Technical Risk candidate structures for Development exploration."""

    candidate_set_id: str | None
    candidate_set_version: str
    dataset_checksum: str
    generation_id: str
    candidate_ids: tuple[str, ...]
    candidate_structural_checksums: tuple[str, ...]
    candidate_set_checksum: str | None = None
    created_at: datetime | None = None
    generated_at: datetime | None = None

    def __post_init__(self):
        _require_text(self.candidate_set_version, "candidate_set_version")
        _require_text(self.dataset_checksum, "dataset_checksum")
        _require_text(self.generation_id, "generation_id")
        candidate_ids, candidate_checksums = _canonical_candidate_identity_parts(
            self.candidate_ids,
            self.candidate_structural_checksums,
        )
        object.__setattr__(self, "candidate_ids", candidate_ids)
        object.__setattr__(self, "candidate_structural_checksums", candidate_checksums)
        checksum = _candidate_set_checksum(self)
        identity = _stable_id(
            "technical_risk_candidate_set",
            {
                "candidate_set_checksum": checksum,
            },
        )
        if self.candidate_set_id is not None and self.candidate_set_id != identity:
            raise TechnicalRiskDevelopmentExplorationError("candidate_set_id mismatch.")
        if self.candidate_set_checksum is not None and self.candidate_set_checksum != checksum:
            raise TechnicalRiskDevelopmentExplorationError("candidate_set_checksum mismatch.")
        object.__setattr__(self, "candidate_set_id", identity)
        object.__setattr__(self, "candidate_set_checksum", checksum)


@dataclass(frozen=True)
class DevelopmentEvaluationContext:
    """Immutable Development-only experiment context for candidate evaluation."""

    development_experiment_id: str | None
    dataset_id: str
    dataset_checksum: str
    split_role: TechnicalRiskOOSSplitRole
    candidate_set_id: str
    threshold_candidate_set_id: str
    exploration_version: str
    evaluator_version: str
    metric_version: str
    numeric_context_version: str
    development_experiment_checksum: str | None = None
    created_at: datetime | None = None
    generated_at: datetime | None = None
    approved_at: datetime | None = None

    def __post_init__(self):
        _require_text(self.dataset_id, "dataset_id")
        _require_text(self.dataset_checksum, "dataset_checksum")
        _require_text(self.candidate_set_id, "candidate_set_id")
        _require_text(self.threshold_candidate_set_id, "threshold_candidate_set_id")
        _require_text(self.exploration_version, "exploration_version")
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        if not isinstance(self.split_role, TechnicalRiskOOSSplitRole):
            object.__setattr__(self, "split_role", TechnicalRiskOOSSplitRole(self.split_role))
        if self.split_role != TechnicalRiskOOSSplitRole.DEVELOPMENT:
            raise TechnicalRiskDevelopmentExplorationError("Development exploration requires DEVELOPMENT split_role.")
        checksum = _development_context_checksum(self)
        identity = _stable_id(
            "technical_risk_development_experiment",
            {
                "development_experiment_checksum": checksum,
            },
        )
        if self.development_experiment_id is not None and self.development_experiment_id != identity:
            raise TechnicalRiskDevelopmentExplorationError("development_experiment_id mismatch.")
        if self.development_experiment_checksum is not None and self.development_experiment_checksum != checksum:
            raise TechnicalRiskDevelopmentExplorationError("development_experiment_checksum mismatch.")
        object.__setattr__(self, "development_experiment_id", identity)
        object.__setattr__(self, "development_experiment_checksum", checksum)


def _canonical_candidate_identity_parts(
    candidate_ids: tuple[str, ...],
    candidate_structural_checksums: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ids = tuple(candidate_ids)
    checksums = tuple(candidate_structural_checksums)
    if not ids:
        raise TechnicalRiskDevelopmentExplorationError("candidate_ids must not be empty.")
    if len(ids) != len(checksums):
        raise TechnicalRiskDevelopmentExplorationError("candidate identity fields must have matching lengths.")
    for index, candidate_id in enumerate(ids):
        _require_text(candidate_id, f"candidate_ids[{index}]")
    for index, candidate_structural_checksum in enumerate(checksums):
        _require_text(candidate_structural_checksum, f"candidate_structural_checksums[{index}]")
    if len(set(ids)) != len(ids):
        raise TechnicalRiskDevelopmentExplorationError("Duplicate candidate identity.")
    if len(set(checksums)) != len(checksums):
        raise TechnicalRiskDevelopmentExplorationError("Duplicate candidate structural checksum.")
    pairs = tuple(sorted(zip(ids, checksums), key=lambda item: (item[0], item[1])))
    return tuple(item[0] for item in pairs), tuple(item[1] for item in pairs)


def _canonical_threshold_identity_parts(
    threshold_set_ids: tuple[str, ...],
    threshold_set_checksums: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ids = tuple(threshold_set_ids)
    checksums = tuple(threshold_set_checksums)
    if not ids:
        raise TechnicalRiskDevelopmentExplorationError("generated_threshold_set_ids must not be empty.")
    if len(ids) != len(checksums):
        raise TechnicalRiskDevelopmentExplorationError("threshold identity fields must have matching lengths.")
    for index, threshold_set_id in enumerate(ids):
        _require_text(threshold_set_id, f"generated_threshold_set_ids[{index}]")
    for index, threshold_set_checksum in enumerate(checksums):
        _require_text(threshold_set_checksum, f"generated_threshold_set_checksums[{index}]")
    if len(set(ids)) != len(ids):
        raise TechnicalRiskDevelopmentExplorationError("Duplicate threshold identity.")
    if len(set(checksums)) != len(checksums):
        raise TechnicalRiskDevelopmentExplorationError("Duplicate threshold checksum.")
    pairs = tuple(sorted(zip(ids, checksums), key=lambda item: (item[0], item[1])))
    return tuple(item[0] for item in pairs), tuple(item[1] for item in pairs)


def _threshold_generation_checksum(contract: ThresholdCandidateGenerationContract) -> str:
    return _stable_hash(
        {
            "generation_contract_version": TECH_RISK_THRESHOLD_CANDIDATE_GENERATION_CONTRACT_V1,
            "generation_version": contract.generation_version,
            "generation_method_id": contract.generation_method_id,
            "generation_method_version": contract.generation_method_version,
            "numeric_representation_version": contract.numeric_representation_version,
            "numeric_context_version": contract.numeric_context_version,
            "candidate_family": contract.candidate_family.value,
            "source_spec_version": contract.source_spec_version,
            "generated_thresholds": [
                {
                    "threshold_set_id": threshold_set_id,
                    "threshold_set_checksum": threshold_set_checksum,
                }
                for threshold_set_id, threshold_set_checksum in zip(
                    contract.generated_threshold_set_ids,
                    contract.generated_threshold_set_checksums,
                )
            ],
        }
    )


def _candidate_set_checksum(candidate_set: TechnicalRiskCandidateSet) -> str:
    return _stable_hash(
        {
            "candidate_set_contract_version": TECH_RISK_CANDIDATE_SET_CONTRACT_V1,
            "candidate_set_version": candidate_set.candidate_set_version,
            "dataset_checksum": candidate_set.dataset_checksum,
            "generation_id": candidate_set.generation_id,
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "candidate_structural_checksum": candidate_structural_checksum,
                }
                for candidate_id, candidate_structural_checksum in zip(
                    candidate_set.candidate_ids,
                    candidate_set.candidate_structural_checksums,
                )
            ],
        }
    )


def _development_context_checksum(context: DevelopmentEvaluationContext) -> str:
    return _stable_hash(
        {
            "development_context_version": TECH_RISK_DEVELOPMENT_EVALUATION_CONTEXT_V1,
            "dataset_id": context.dataset_id,
            "dataset_checksum": context.dataset_checksum,
            "split_role": context.split_role.value,
            "candidate_set_id": context.candidate_set_id,
            "threshold_candidate_set_id": context.threshold_candidate_set_id,
            "exploration_version": context.exploration_version,
            "evaluator_version": context.evaluator_version,
            "metric_version": context.metric_version,
            "numeric_context_version": context.numeric_context_version,
        }
    )


def _require_version(value: object, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskDevelopmentExplorationError(f"Unsupported {field_name}.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskDevelopmentExplorationError(f"{field_name} must be a non-empty string.")


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    return value
