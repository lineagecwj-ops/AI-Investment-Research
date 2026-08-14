from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from typing import Mapping

from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.candidate_evaluator import TECH_RISK_CANDIDATE_EVALUATOR_V1
from risk_oos.candidate_evaluator import TECH_RISK_CONTINUOUS_MAE_METRIC_V1
from risk_oos.candidate_evaluator import TECH_RISK_QUANTILE_NEAREST_RANK_V1
from risk_oos.candidate_evaluator import TechnicalRiskCandidateEvaluationResult
from risk_oos.development_exploration import DevelopmentEvaluationContext
from risk_oos.development_exploration import TechnicalRiskCandidateIdentity
from risk_oos.development_exploration import TechnicalRiskCandidateSet
from risk_oos.development_exploration import TechnicalRiskThresholdIdentity
from risk_oos.development_exploration import ThresholdCandidateGenerationContract
from risk_oos.rule_candidates import TECH_RISK_DECIMAL_CONTEXT_V1


DEVELOPMENT_SHORTLIST_ARTIFACT_V1 = "DEVELOPMENT_SHORTLIST_ARTIFACT_V1"
TECH_RISK_VALIDATION_SELECTION_ARTIFACT_V1 = "TECH_RISK_VALIDATION_SELECTION_ARTIFACT_V1"
TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1 = "TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1"
TECH_RISK_VALIDATION_SELECTION_INPUT_V1 = "TECH_RISK_VALIDATION_SELECTION_INPUT_V1"


class TechnicalRiskValidationSelectionError(Exception):
    """Raised when Technical Risk validation-selection contracts are invalid."""


class TechnicalRiskMonotonicityPreference(StrEnum):
    PREFER_PASS = "PREFER_PASS"
    ALLOW_WARNING = "ALLOW_WARNING"
    REQUIRE_EVALUABLE = "REQUIRE_EVALUABLE"


class TechnicalRiskMedianSeparationPreference(StrEnum):
    COMPARE_MAE20_AND_MAE60_MEDIANS = "COMPARE_MAE20_AND_MAE60_MEDIANS"
    PREFER_STRONGER_MAE20_AND_MAE60_SEPARATION = "PREFER_STRONGER_MAE20_AND_MAE60_SEPARATION"


class TechnicalRiskCoveragePreference(StrEnum):
    PREFER_EVALUABLE_LOW_MEDIUM_HIGH_COVERAGE = "PREFER_EVALUABLE_LOW_MEDIUM_HIGH_COVERAGE"
    REQUIRE_SEVERITY_METRICS_PRESENT = "REQUIRE_SEVERITY_METRICS_PRESENT"


class TechnicalRiskEmptyBucketPolicy(StrEnum):
    FLAG_METHOD_WARNING = "FLAG_METHOD_WARNING"
    REQUIRE_METHOD_REVIEW = "REQUIRE_METHOD_REVIEW"


class TechnicalRiskMethodologyWarningPolicy(StrEnum):
    RETAIN_STRUCTURED_WARNINGS = "RETAIN_STRUCTURED_WARNINGS"
    REQUIRE_EXPLICIT_REVIEW = "REQUIRE_EXPLICIT_REVIEW"


class TechnicalRiskTiePolicy(StrEnum):
    TIE_REQUIRES_METHOD_DECISION = "TIE_REQUIRES_METHOD_DECISION"


class TechnicalRiskValidationSelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    NO_VALID_SELECTION = "NO_VALID_SELECTION"
    TIE_REQUIRES_METHOD_DECISION = "TIE_REQUIRES_METHOD_DECISION"


class TechnicalRiskValidationCombinationOutcome(StrEnum):
    SELECTED = "SELECTED"
    NOT_SELECTED = "NOT_SELECTED"
    UNRESOLVED_TIE = "UNRESOLVED_TIE"


class TechnicalRiskValidationSelectionReasonCode(StrEnum):
    SELECTED_METHOD_REVIEW = "SELECTED_METHOD_REVIEW"
    NOT_SELECTED_MONOTONICITY_CONCERN = "NOT_SELECTED_MONOTONICITY_CONCERN"
    NOT_SELECTED_COVERAGE_CONCERN = "NOT_SELECTED_COVERAGE_CONCERN"
    NOT_SELECTED_SEPARATION_CONCERN = "NOT_SELECTED_SEPARATION_CONCERN"
    NOT_SELECTED_METHOD_PREFERENCE = "NOT_SELECTED_METHOD_PREFERENCE"
    NO_VALID_SELECTION_EVIDENCE = "NO_VALID_SELECTION_EVIDENCE"
    TIE_REQUIRES_METHOD_DECISION = "TIE_REQUIRES_METHOD_DECISION"
    TIE_RESOLVED_BY_METHOD_DECISION = "TIE_RESOLVED_BY_METHOD_DECISION"


@dataclass(frozen=True)
class DevelopmentEvaluationReference:
    """Frozen Development evaluation identity used as shortlist evidence."""

    evaluation_id: str
    evaluation_checksum: str
    dataset_checksum: str
    candidate_id: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_checksum: str
    evaluated_split_roles: tuple[TechnicalRiskOOSSplitRole, ...]
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str

    def __post_init__(self):
        _require_text(self.evaluation_id, "evaluation_id")
        _require_text(self.evaluation_checksum, "evaluation_checksum")
        _require_text(self.dataset_checksum, "dataset_checksum")
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.candidate_structural_checksum, "candidate_structural_checksum")
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_checksum, "threshold_set_checksum")
        roles = _canonical_split_roles(self.evaluated_split_roles)
        if roles != (TechnicalRiskOOSSplitRole.DEVELOPMENT,):
            raise TechnicalRiskValidationSelectionError("Development shortlist evidence must be DEVELOPMENT only.")
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        object.__setattr__(self, "evaluated_split_roles", roles)

    @classmethod
    def from_evaluation_result(cls, evaluation_result: TechnicalRiskCandidateEvaluationResult) -> "DevelopmentEvaluationReference":
        return cls(
            evaluation_id=evaluation_result.evaluation_id,
            evaluation_checksum=evaluation_result.evaluation_checksum,
            dataset_checksum=evaluation_result.dataset_checksum,
            candidate_id=evaluation_result.candidate_id,
            candidate_structural_checksum=evaluation_result.candidate_structural_checksum,
            threshold_set_id=evaluation_result.threshold_set_id,
            threshold_set_checksum=evaluation_result.threshold_set_checksum,
            evaluated_split_roles=evaluation_result.evaluated_split_roles,
            evaluator_version=evaluation_result.evaluator_version,
            metric_version=evaluation_result.metric_version,
            quantile_version=evaluation_result.quantile_version,
            numeric_context_version=evaluation_result.numeric_context_version,
        )


@dataclass(frozen=True)
class DevelopmentShortlistEligiblePair:
    """One candidate-threshold pair authorized by matching Development evidence."""

    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    development_evaluation_id: str
    development_evaluation_checksum: str

    def __post_init__(self):
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.candidate_version, "candidate_version")
        _require_text(self.candidate_structural_checksum, "candidate_structural_checksum")
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_version, "threshold_set_version")
        _require_text(self.threshold_set_checksum, "threshold_set_checksum")
        _require_text(self.development_evaluation_id, "development_evaluation_id")
        _require_text(self.development_evaluation_checksum, "development_evaluation_checksum")

    @classmethod
    def from_lineage(
        cls,
        *,
        candidate: TechnicalRiskCandidateIdentity,
        threshold: TechnicalRiskThresholdIdentity,
        evaluation_reference: DevelopmentEvaluationReference,
    ) -> "DevelopmentShortlistEligiblePair":
        if candidate.candidate_id != evaluation_reference.candidate_id:
            raise TechnicalRiskValidationSelectionError("Eligible pair candidate_id mismatch.")
        if candidate.candidate_structural_checksum != evaluation_reference.candidate_structural_checksum:
            raise TechnicalRiskValidationSelectionError("Eligible pair candidate checksum mismatch.")
        if threshold.threshold_set_id != evaluation_reference.threshold_set_id:
            raise TechnicalRiskValidationSelectionError("Eligible pair threshold_set_id mismatch.")
        if threshold.threshold_set_checksum != evaluation_reference.threshold_set_checksum:
            raise TechnicalRiskValidationSelectionError("Eligible pair threshold checksum mismatch.")
        return cls(
            candidate_id=candidate.candidate_id,
            candidate_version=candidate.candidate_version,
            candidate_structural_checksum=candidate.candidate_structural_checksum,
            threshold_set_id=threshold.threshold_set_id,
            threshold_set_version=threshold.threshold_set_version,
            threshold_set_checksum=threshold.threshold_set_checksum,
            development_evaluation_id=evaluation_reference.evaluation_id,
            development_evaluation_checksum=evaluation_reference.evaluation_checksum,
        )


@dataclass(frozen=True)
class DevelopmentShortlistArtifact:
    """Frozen Development shortlist that defines what may enter Validation."""

    shortlist_id: str | None
    shortlist_version: str
    development_experiment_id: str
    development_experiment_checksum: str
    candidate_set_id: str
    candidate_set_checksum: str
    threshold_candidate_generation_id: str
    threshold_candidate_generation_checksum: str
    eligible_pairs: tuple[DevelopmentShortlistEligiblePair, ...]
    eligible_candidates: tuple[TechnicalRiskCandidateIdentity, ...]
    eligible_threshold_sets: tuple[TechnicalRiskThresholdIdentity, ...]
    development_evaluations: tuple[DevelopmentEvaluationReference, ...]
    shortlist_checksum: str | None = None
    created_at: datetime | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    human_note: str | None = None

    def __post_init__(self):
        _require_text(self.shortlist_version, "shortlist_version")
        _require_text(self.development_experiment_id, "development_experiment_id")
        _require_text(self.development_experiment_checksum, "development_experiment_checksum")
        _require_text(self.candidate_set_id, "candidate_set_id")
        _require_text(self.candidate_set_checksum, "candidate_set_checksum")
        _require_text(self.threshold_candidate_generation_id, "threshold_candidate_generation_id")
        _require_text(self.threshold_candidate_generation_checksum, "threshold_candidate_generation_checksum")
        candidates = _canonical_candidates(self.eligible_candidates)
        thresholds = _canonical_thresholds(self.eligible_threshold_sets)
        evaluations = _canonical_development_evaluations(self.development_evaluations)
        pairs = _canonical_pairs(self.eligible_pairs)
        _validate_development_evaluation_references(candidates, thresholds, evaluations)
        _validate_pair_projection(candidates, thresholds, pairs)
        _validate_pair_evidence(pairs, evaluations)
        object.__setattr__(self, "eligible_pairs", pairs)
        object.__setattr__(self, "eligible_candidates", candidates)
        object.__setattr__(self, "eligible_threshold_sets", thresholds)
        object.__setattr__(self, "development_evaluations", evaluations)
        checksum = _shortlist_checksum(self)
        identity = _stable_id("technical_risk_development_shortlist", {"shortlist_checksum": checksum})
        if self.shortlist_id is not None and self.shortlist_id != identity:
            raise TechnicalRiskValidationSelectionError("shortlist_id mismatch.")
        if self.shortlist_checksum is not None and self.shortlist_checksum != checksum:
            raise TechnicalRiskValidationSelectionError("shortlist_checksum mismatch.")
        object.__setattr__(self, "shortlist_id", identity)
        object.__setattr__(self, "shortlist_checksum", checksum)

    @classmethod
    def from_development_contracts(
        cls,
        *,
        development_context: DevelopmentEvaluationContext,
        candidate_set: TechnicalRiskCandidateSet,
        threshold_generation: ThresholdCandidateGenerationContract,
        eligible_candidates: tuple[TechnicalRiskCandidateIdentity, ...],
        eligible_threshold_sets: tuple[TechnicalRiskThresholdIdentity, ...],
        development_evaluation_results: tuple[TechnicalRiskCandidateEvaluationResult, ...],
        shortlist_id: str | None = None,
        shortlist_version: str = DEVELOPMENT_SHORTLIST_ARTIFACT_V1,
        shortlist_checksum: str | None = None,
        created_at: datetime | None = None,
        approved_at: datetime | None = None,
        approved_by: str | None = None,
        human_note: str | None = None,
    ) -> "DevelopmentShortlistArtifact":
        _validate_source_lineage(development_context, candidate_set, threshold_generation)
        _validate_candidate_subset(eligible_candidates, candidate_set)
        _validate_threshold_subset(eligible_threshold_sets, threshold_generation)
        references = tuple(DevelopmentEvaluationReference.from_evaluation_result(result) for result in development_evaluation_results)
        _validate_evaluation_lineage(development_context, eligible_candidates, eligible_threshold_sets, references)
        pairs = _eligible_pairs_from_references(eligible_candidates, eligible_threshold_sets, references)
        return cls(
            shortlist_id=shortlist_id,
            shortlist_version=shortlist_version,
            development_experiment_id=development_context.development_experiment_id,
            development_experiment_checksum=development_context.development_experiment_checksum,
            candidate_set_id=candidate_set.candidate_set_id,
            candidate_set_checksum=candidate_set.candidate_set_checksum,
            threshold_candidate_generation_id=threshold_generation.generation_id,
            threshold_candidate_generation_checksum=threshold_generation.generation_checksum,
            eligible_pairs=pairs,
            eligible_candidates=eligible_candidates,
            eligible_threshold_sets=eligible_threshold_sets,
            development_evaluations=references,
            shortlist_checksum=shortlist_checksum,
            created_at=created_at,
            approved_at=approved_at,
            approved_by=approved_by,
            human_note=human_note,
        )


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionCriteria:
    """Frozen research criteria for later Validation selection review."""

    criteria_id: str | None
    criteria_version: str
    monotonicity_preference: TechnicalRiskMonotonicityPreference
    median_separation_preference: TechnicalRiskMedianSeparationPreference
    coverage_preference: TechnicalRiskCoveragePreference
    empty_bucket_policy: TechnicalRiskEmptyBucketPolicy
    methodology_warning_policy: TechnicalRiskMethodologyWarningPolicy
    tie_policy: TechnicalRiskTiePolicy
    numeric_context_version: str
    metric_version: str
    quantile_version: str
    criteria_checksum: str | None = None
    created_at: datetime | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    human_note: str | None = None

    def __post_init__(self):
        _require_text(self.criteria_version, "criteria_version")
        object.__setattr__(
            self,
            "monotonicity_preference",
            _coerce_enum(self.monotonicity_preference, TechnicalRiskMonotonicityPreference, "monotonicity_preference"),
        )
        object.__setattr__(
            self,
            "median_separation_preference",
            _coerce_enum(self.median_separation_preference, TechnicalRiskMedianSeparationPreference, "median_separation_preference"),
        )
        object.__setattr__(
            self,
            "coverage_preference",
            _coerce_enum(self.coverage_preference, TechnicalRiskCoveragePreference, "coverage_preference"),
        )
        object.__setattr__(
            self,
            "empty_bucket_policy",
            _coerce_enum(self.empty_bucket_policy, TechnicalRiskEmptyBucketPolicy, "empty_bucket_policy"),
        )
        object.__setattr__(
            self,
            "methodology_warning_policy",
            _coerce_enum(self.methodology_warning_policy, TechnicalRiskMethodologyWarningPolicy, "methodology_warning_policy"),
        )
        object.__setattr__(self, "tie_policy", _coerce_enum(self.tie_policy, TechnicalRiskTiePolicy, "tie_policy"))
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        checksum = _criteria_checksum(self)
        identity = _stable_id("technical_risk_validation_selection_criteria", {"criteria_checksum": checksum})
        if self.criteria_id is not None and self.criteria_id != identity:
            raise TechnicalRiskValidationSelectionError("criteria_id mismatch.")
        if self.criteria_checksum is not None and self.criteria_checksum != checksum:
            raise TechnicalRiskValidationSelectionError("criteria_checksum mismatch.")
        object.__setattr__(self, "criteria_id", identity)
        object.__setattr__(self, "criteria_checksum", checksum)


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionInput:
    """Integrity echo for one frozen Validation selection handoff."""

    selection_input_version: str
    validation_dataset_id: str
    validation_dataset_checksum: str
    development_shortlist_id: str
    development_shortlist_checksum: str
    selection_criteria_id: str
    selection_criteria_version: str
    selection_criteria_checksum: str
    validation_evaluation_ids: tuple[str, ...]
    validation_evaluation_checksums: tuple[str, ...]
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str

    def __post_init__(self):
        _require_version(self.selection_input_version, TECH_RISK_VALIDATION_SELECTION_INPUT_V1, "selection_input_version")
        _require_text(self.validation_dataset_id, "validation_dataset_id")
        _require_text(self.validation_dataset_checksum, "validation_dataset_checksum")
        _require_text(self.development_shortlist_id, "development_shortlist_id")
        _require_text(self.development_shortlist_checksum, "development_shortlist_checksum")
        _require_text(self.selection_criteria_id, "selection_criteria_id")
        _require_version(self.selection_criteria_version, TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1, "selection_criteria_version")
        _require_text(self.selection_criteria_checksum, "selection_criteria_checksum")
        ids, checksums = _canonical_identity_parts(
            self.validation_evaluation_ids,
            self.validation_evaluation_checksums,
            "validation_evaluation_ids",
            "validation_evaluation_checksums",
        )
        object.__setattr__(self, "validation_evaluation_ids", ids)
        object.__setattr__(self, "validation_evaluation_checksums", checksums)
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")

    @classmethod
    def from_contracts(
        cls,
        *,
        validation_dataset,
        development_shortlist: DevelopmentShortlistArtifact,
        selection_criteria: TechnicalRiskValidationSelectionCriteria,
        validation_evaluations: tuple[TechnicalRiskCandidateEvaluationResult, ...],
    ) -> "TechnicalRiskValidationSelectionInput":
        return cls(
            selection_input_version=TECH_RISK_VALIDATION_SELECTION_INPUT_V1,
            validation_dataset_id=validation_dataset.dataset_id,
            validation_dataset_checksum=validation_dataset.dataset_checksum,
            development_shortlist_id=development_shortlist.shortlist_id,
            development_shortlist_checksum=development_shortlist.shortlist_checksum,
            selection_criteria_id=selection_criteria.criteria_id,
            selection_criteria_version=selection_criteria.criteria_version,
            selection_criteria_checksum=selection_criteria.criteria_checksum,
            validation_evaluation_ids=tuple(evaluation.evaluation_id for evaluation in validation_evaluations),
            validation_evaluation_checksums=tuple(evaluation.evaluation_checksum for evaluation in validation_evaluations),
            evaluator_version=TECH_RISK_CANDIDATE_EVALUATOR_V1,
            metric_version=selection_criteria.metric_version,
            quantile_version=selection_criteria.quantile_version,
            numeric_context_version=selection_criteria.numeric_context_version,
        )


@dataclass(frozen=True)
class TechnicalRiskValidationConsideredCombination:
    """One exact Validation candidate-threshold pair considered for selection."""

    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    validation_evaluation_id: str
    validation_evaluation_checksum: str
    selection_outcome: TechnicalRiskValidationCombinationOutcome
    structured_reason_codes: tuple[TechnicalRiskValidationSelectionReasonCode, ...]

    def __post_init__(self):
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.candidate_version, "candidate_version")
        _require_text(self.candidate_structural_checksum, "candidate_structural_checksum")
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_version, "threshold_set_version")
        _require_text(self.threshold_set_checksum, "threshold_set_checksum")
        _require_text(self.validation_evaluation_id, "validation_evaluation_id")
        _require_text(self.validation_evaluation_checksum, "validation_evaluation_checksum")
        object.__setattr__(
            self,
            "selection_outcome",
            _coerce_enum(self.selection_outcome, TechnicalRiskValidationCombinationOutcome, "selection_outcome"),
        )
        object.__setattr__(
            self,
            "structured_reason_codes",
            _canonical_reason_codes(self.structured_reason_codes),
        )

    @classmethod
    def from_evaluation(
        cls,
        *,
        evaluation: TechnicalRiskCandidateEvaluationResult,
        selection_outcome: TechnicalRiskValidationCombinationOutcome,
        structured_reason_codes: tuple[TechnicalRiskValidationSelectionReasonCode, ...],
    ) -> "TechnicalRiskValidationConsideredCombination":
        return cls(
            candidate_id=evaluation.candidate_id,
            candidate_version=evaluation.candidate_version,
            candidate_structural_checksum=evaluation.candidate_structural_checksum,
            threshold_set_id=evaluation.threshold_set_id,
            threshold_set_version=evaluation.threshold_set_version,
            threshold_set_checksum=evaluation.threshold_set_checksum,
            validation_evaluation_id=evaluation.evaluation_id,
            validation_evaluation_checksum=evaluation.evaluation_checksum,
            selection_outcome=selection_outcome,
            structured_reason_codes=structured_reason_codes,
        )


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionDecision:
    """Explicit methodology decision supplied by caller or human review."""

    selection_status: TechnicalRiskValidationSelectionStatus
    selected_candidate_id: str | None = None
    selected_candidate_structural_checksum: str | None = None
    selected_threshold_set_id: str | None = None
    selected_threshold_set_checksum: str | None = None
    accepted_validation_evaluation_id: str | None = None
    accepted_validation_evaluation_checksum: str | None = None
    structured_selection_reason_codes: tuple[TechnicalRiskValidationSelectionReasonCode, ...] = ()
    approved_by: str | None = None
    approved_at: datetime | None = None
    human_rationale: str | None = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "selection_status",
            _coerce_enum(self.selection_status, TechnicalRiskValidationSelectionStatus, "selection_status"),
        )
        object.__setattr__(
            self,
            "structured_selection_reason_codes",
            _canonical_reason_codes(self.structured_selection_reason_codes),
        )
        selected_fields = (
            self.selected_candidate_id,
            self.selected_candidate_structural_checksum,
            self.selected_threshold_set_id,
            self.selected_threshold_set_checksum,
            self.accepted_validation_evaluation_id,
            self.accepted_validation_evaluation_checksum,
        )
        if self.selection_status == TechnicalRiskValidationSelectionStatus.SELECTED:
            for index, value in enumerate(selected_fields):
                _require_text(value, f"selected_fields[{index}]")
        elif any(value is not None for value in selected_fields):
            raise TechnicalRiskValidationSelectionError("Non-selected status cannot include selected pair fields.")


@dataclass(frozen=True)
class TechnicalRiskValidationSelectionArtifact:
    """Frozen research methodology artifact for Validation selection."""

    selection_id: str | None
    selection_version: str
    validation_dataset_id: str
    validation_dataset_checksum: str
    development_shortlist_id: str
    development_shortlist_checksum: str
    selection_criteria_id: str
    selection_criteria_version: str
    selection_criteria_checksum: str
    selection_status: TechnicalRiskValidationSelectionStatus
    selected_candidate_id: str | None
    selected_candidate_structural_checksum: str | None
    selected_threshold_set_id: str | None
    selected_threshold_set_checksum: str | None
    accepted_validation_evaluation_id: str | None
    accepted_validation_evaluation_checksum: str | None
    considered_combinations: tuple[TechnicalRiskValidationConsideredCombination, ...]
    structured_selection_reason_codes: tuple[TechnicalRiskValidationSelectionReasonCode, ...]
    evaluator_version: str
    metric_version: str
    quantile_version: str
    numeric_context_version: str
    selection_checksum: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    human_rationale: str | None = None

    def __post_init__(self):
        _require_version(self.selection_version, TECH_RISK_VALIDATION_SELECTION_ARTIFACT_V1, "selection_version")
        _require_text(self.validation_dataset_id, "validation_dataset_id")
        _require_text(self.validation_dataset_checksum, "validation_dataset_checksum")
        _require_text(self.development_shortlist_id, "development_shortlist_id")
        _require_text(self.development_shortlist_checksum, "development_shortlist_checksum")
        _require_text(self.selection_criteria_id, "selection_criteria_id")
        _require_version(self.selection_criteria_version, TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1, "selection_criteria_version")
        _require_text(self.selection_criteria_checksum, "selection_criteria_checksum")
        object.__setattr__(
            self,
            "selection_status",
            _coerce_enum(self.selection_status, TechnicalRiskValidationSelectionStatus, "selection_status"),
        )
        object.__setattr__(
            self,
            "considered_combinations",
            _canonical_considered_combinations(self.considered_combinations),
        )
        object.__setattr__(
            self,
            "structured_selection_reason_codes",
            _canonical_reason_codes(self.structured_selection_reason_codes),
        )
        _require_version(self.evaluator_version, TECH_RISK_CANDIDATE_EVALUATOR_V1, "evaluator_version")
        _require_version(self.metric_version, TECH_RISK_CONTINUOUS_MAE_METRIC_V1, "metric_version")
        _require_version(self.quantile_version, TECH_RISK_QUANTILE_NEAREST_RANK_V1, "quantile_version")
        _require_version(self.numeric_context_version, TECH_RISK_DECIMAL_CONTEXT_V1, "numeric_context_version")
        _validate_selection_state(self)
        checksum = _selection_checksum(self)
        identity = _stable_id("technical_risk_validation_selection", {"selection_checksum": checksum})
        if self.selection_id is not None and self.selection_id != identity:
            raise TechnicalRiskValidationSelectionError("selection_id mismatch.")
        if self.selection_checksum is not None and self.selection_checksum != checksum:
            raise TechnicalRiskValidationSelectionError("selection_checksum mismatch.")
        object.__setattr__(self, "selection_id", identity)
        object.__setattr__(self, "selection_checksum", checksum)

    @classmethod
    def from_validation_contracts(
        cls,
        *,
        validation_dataset,
        development_shortlist: DevelopmentShortlistArtifact,
        selection_criteria: TechnicalRiskValidationSelectionCriteria,
        selection_input: TechnicalRiskValidationSelectionInput,
        validation_evaluations: tuple[TechnicalRiskCandidateEvaluationResult, ...],
        selection_decision: TechnicalRiskValidationSelectionDecision,
        considered_combinations: tuple[TechnicalRiskValidationConsideredCombination, ...],
        selection_id: str | None = None,
        selection_version: str = TECH_RISK_VALIDATION_SELECTION_ARTIFACT_V1,
        selection_checksum: str | None = None,
    ) -> "TechnicalRiskValidationSelectionArtifact":
        evaluations = _canonical_validation_evaluations(validation_evaluations)
        _validate_selection_input_echo(selection_input, validation_dataset, development_shortlist, selection_criteria, evaluations)
        _validate_validation_evaluations(validation_dataset, development_shortlist, selection_criteria, selection_input, evaluations)
        _validate_considered_combinations(development_shortlist, evaluations, considered_combinations)
        return cls(
            selection_id=selection_id,
            selection_version=selection_version,
            validation_dataset_id=validation_dataset.dataset_id,
            validation_dataset_checksum=validation_dataset.dataset_checksum,
            development_shortlist_id=development_shortlist.shortlist_id,
            development_shortlist_checksum=development_shortlist.shortlist_checksum,
            selection_criteria_id=selection_criteria.criteria_id,
            selection_criteria_version=selection_criteria.criteria_version,
            selection_criteria_checksum=selection_criteria.criteria_checksum,
            selection_status=selection_decision.selection_status,
            selected_candidate_id=selection_decision.selected_candidate_id,
            selected_candidate_structural_checksum=selection_decision.selected_candidate_structural_checksum,
            selected_threshold_set_id=selection_decision.selected_threshold_set_id,
            selected_threshold_set_checksum=selection_decision.selected_threshold_set_checksum,
            accepted_validation_evaluation_id=selection_decision.accepted_validation_evaluation_id,
            accepted_validation_evaluation_checksum=selection_decision.accepted_validation_evaluation_checksum,
            considered_combinations=considered_combinations,
            structured_selection_reason_codes=selection_decision.structured_selection_reason_codes,
            evaluator_version=selection_input.evaluator_version,
            metric_version=selection_input.metric_version,
            quantile_version=selection_input.quantile_version,
            numeric_context_version=selection_input.numeric_context_version,
            selection_checksum=selection_checksum,
            approved_by=selection_decision.approved_by,
            approved_at=selection_decision.approved_at,
            human_rationale=selection_decision.human_rationale,
        )


def _validate_source_lineage(
    development_context: DevelopmentEvaluationContext,
    candidate_set: TechnicalRiskCandidateSet,
    threshold_generation: ThresholdCandidateGenerationContract,
) -> None:
    if development_context.split_role != TechnicalRiskOOSSplitRole.DEVELOPMENT:
        raise TechnicalRiskValidationSelectionError("Development context must be DEVELOPMENT.")
    if development_context.dataset_checksum != candidate_set.dataset_checksum:
        raise TechnicalRiskValidationSelectionError("candidate set dataset_checksum mismatch.")
    if development_context.candidate_set_id != candidate_set.candidate_set_id:
        raise TechnicalRiskValidationSelectionError("candidate_set_id mismatch.")
    if development_context.threshold_candidate_set_id != threshold_generation.generation_id:
        raise TechnicalRiskValidationSelectionError("threshold generation id mismatch.")
    if candidate_set.generation_id != threshold_generation.generation_id:
        raise TechnicalRiskValidationSelectionError("candidate set generation_id mismatch.")


def _validate_candidate_subset(
    eligible_candidates: tuple[TechnicalRiskCandidateIdentity, ...],
    candidate_set: TechnicalRiskCandidateSet,
) -> None:
    source = set(zip(candidate_set.candidate_ids, candidate_set.candidate_structural_checksums))
    for candidate in _canonical_candidates(eligible_candidates):
        if (candidate.candidate_id, candidate.candidate_structural_checksum) not in source:
            raise TechnicalRiskValidationSelectionError("Eligible candidate is outside candidate set.")


def _validate_threshold_subset(
    eligible_threshold_sets: tuple[TechnicalRiskThresholdIdentity, ...],
    threshold_generation: ThresholdCandidateGenerationContract,
) -> None:
    source = set(
        zip(
            threshold_generation.generated_threshold_set_ids,
            threshold_generation.generated_threshold_set_checksums,
        )
    )
    for threshold in _canonical_thresholds(eligible_threshold_sets):
        if (threshold.threshold_set_id, threshold.threshold_set_checksum) not in source:
            raise TechnicalRiskValidationSelectionError("Eligible threshold is outside threshold generation universe.")


def _validate_evaluation_lineage(
    development_context: DevelopmentEvaluationContext,
    eligible_candidates: tuple[TechnicalRiskCandidateIdentity, ...],
    eligible_threshold_sets: tuple[TechnicalRiskThresholdIdentity, ...],
    references: tuple[DevelopmentEvaluationReference, ...],
) -> None:
    candidates = _candidate_map(eligible_candidates)
    thresholds = _threshold_map(eligible_threshold_sets)
    for reference in references:
        if reference.dataset_checksum != development_context.dataset_checksum:
            raise TechnicalRiskValidationSelectionError("Development evaluation dataset_checksum mismatch.")
        if candidates.get(reference.candidate_id) != reference.candidate_structural_checksum:
            raise TechnicalRiskValidationSelectionError("Development evaluation candidate mismatch.")
        if thresholds.get(reference.threshold_set_id) != reference.threshold_set_checksum:
            raise TechnicalRiskValidationSelectionError("Development evaluation threshold mismatch.")


def _validate_development_evaluation_references(
    eligible_candidates: tuple[TechnicalRiskCandidateIdentity, ...],
    eligible_threshold_sets: tuple[TechnicalRiskThresholdIdentity, ...],
    references: tuple[DevelopmentEvaluationReference, ...],
) -> None:
    if not references:
        raise TechnicalRiskValidationSelectionError("development_evaluations must not be empty.")
    candidates = _candidate_map(eligible_candidates)
    thresholds = _threshold_map(eligible_threshold_sets)
    seen = set()
    for reference in references:
        key = (reference.candidate_id, reference.threshold_set_id, reference.evaluation_id)
        if key in seen:
            raise TechnicalRiskValidationSelectionError("Duplicate Development evaluation reference.")
        seen.add(key)
        if candidates.get(reference.candidate_id) != reference.candidate_structural_checksum:
            raise TechnicalRiskValidationSelectionError("Development evaluation candidate is outside eligible universe.")
        if thresholds.get(reference.threshold_set_id) != reference.threshold_set_checksum:
            raise TechnicalRiskValidationSelectionError("Development evaluation threshold is outside eligible universe.")


def _eligible_pairs_from_references(
    eligible_candidates: tuple[TechnicalRiskCandidateIdentity, ...],
    eligible_threshold_sets: tuple[TechnicalRiskThresholdIdentity, ...],
    references: tuple[DevelopmentEvaluationReference, ...],
) -> tuple[DevelopmentShortlistEligiblePair, ...]:
    candidates = {candidate.candidate_id: candidate for candidate in _canonical_candidates(eligible_candidates)}
    thresholds = {threshold.threshold_set_id: threshold for threshold in _canonical_thresholds(eligible_threshold_sets)}
    pairs = []
    for reference in _canonical_development_evaluations(references):
        candidate = candidates.get(reference.candidate_id)
        threshold = thresholds.get(reference.threshold_set_id)
        if candidate is None:
            raise TechnicalRiskValidationSelectionError("Development evaluation candidate is outside eligible universe.")
        if threshold is None:
            raise TechnicalRiskValidationSelectionError("Development evaluation threshold is outside eligible universe.")
        pairs.append(
            DevelopmentShortlistEligiblePair.from_lineage(
                candidate=candidate,
                threshold=threshold,
                evaluation_reference=reference,
            )
        )
    return _canonical_pairs(tuple(pairs))


def _validate_pair_projection(
    eligible_candidates: tuple[TechnicalRiskCandidateIdentity, ...],
    eligible_threshold_sets: tuple[TechnicalRiskThresholdIdentity, ...],
    pairs: tuple[DevelopmentShortlistEligiblePair, ...],
) -> None:
    projected_candidates = _candidate_projection_from_pairs(pairs)
    projected_thresholds = _threshold_projection_from_pairs(pairs)
    if projected_candidates != _canonical_candidates(eligible_candidates):
        raise TechnicalRiskValidationSelectionError("Eligible candidate summary must equal eligible pair projection.")
    if projected_thresholds != _canonical_thresholds(eligible_threshold_sets):
        raise TechnicalRiskValidationSelectionError("Eligible threshold summary must equal eligible pair projection.")


def _validate_pair_evidence(
    pairs: tuple[DevelopmentShortlistEligiblePair, ...],
    references: tuple[DevelopmentEvaluationReference, ...],
) -> None:
    reference_keys = {
        (
            reference.candidate_id,
            reference.candidate_structural_checksum,
            reference.threshold_set_id,
            reference.threshold_set_checksum,
            reference.evaluation_id,
            reference.evaluation_checksum,
        )
        for reference in references
    }
    pair_keys = {
        (
            pair.candidate_id,
            pair.candidate_structural_checksum,
            pair.threshold_set_id,
            pair.threshold_set_checksum,
            pair.development_evaluation_id,
            pair.development_evaluation_checksum,
        )
        for pair in pairs
    }
    if pair_keys != reference_keys:
        raise TechnicalRiskValidationSelectionError("Eligible pairs must match Development evaluation evidence.")


def _canonical_pairs(
    pairs: tuple[DevelopmentShortlistEligiblePair, ...],
) -> tuple[DevelopmentShortlistEligiblePair, ...]:
    normalized = tuple(
        pair if isinstance(pair, DevelopmentShortlistEligiblePair) else DevelopmentShortlistEligiblePair(**pair)
        for pair in pairs
    )
    if not normalized:
        raise TechnicalRiskValidationSelectionError("eligible_pairs must not be empty.")
    pair_keys = tuple((pair.candidate_structural_checksum, pair.threshold_set_checksum) for pair in normalized)
    if len(set(pair_keys)) != len(pair_keys):
        raise TechnicalRiskValidationSelectionError("Duplicate eligible candidate-threshold pair.")
    return tuple(
        sorted(
            normalized,
            key=lambda item: (
                item.candidate_id,
                item.threshold_set_id,
                item.development_evaluation_id,
                item.development_evaluation_checksum,
            ),
        )
    )


def _candidate_projection_from_pairs(
    pairs: tuple[DevelopmentShortlistEligiblePair, ...],
) -> tuple[TechnicalRiskCandidateIdentity, ...]:
    candidates = {
        (pair.candidate_id, pair.candidate_structural_checksum): TechnicalRiskCandidateIdentity(
            pair.candidate_id,
            pair.candidate_version,
            pair.candidate_structural_checksum,
        )
        for pair in pairs
    }
    return _canonical_candidates(tuple(candidates.values()))


def _threshold_projection_from_pairs(
    pairs: tuple[DevelopmentShortlistEligiblePair, ...],
) -> tuple[TechnicalRiskThresholdIdentity, ...]:
    thresholds = {
        (pair.threshold_set_id, pair.threshold_set_checksum): TechnicalRiskThresholdIdentity(
            pair.threshold_set_id,
            pair.threshold_set_version,
            pair.threshold_set_checksum,
        )
        for pair in pairs
    }
    return _canonical_thresholds(tuple(thresholds.values()))


def _validate_selection_input_echo(
    selection_input: TechnicalRiskValidationSelectionInput,
    validation_dataset,
    development_shortlist: DevelopmentShortlistArtifact,
    selection_criteria: TechnicalRiskValidationSelectionCriteria,
    evaluations: tuple[TechnicalRiskCandidateEvaluationResult, ...],
) -> None:
    if selection_input.validation_dataset_id != validation_dataset.dataset_id:
        raise TechnicalRiskValidationSelectionError("validation_dataset_id echo mismatch.")
    if selection_input.validation_dataset_checksum != validation_dataset.dataset_checksum:
        raise TechnicalRiskValidationSelectionError("validation_dataset_checksum echo mismatch.")
    if selection_input.development_shortlist_id != development_shortlist.shortlist_id:
        raise TechnicalRiskValidationSelectionError("development_shortlist_id echo mismatch.")
    if selection_input.development_shortlist_checksum != development_shortlist.shortlist_checksum:
        raise TechnicalRiskValidationSelectionError("development_shortlist_checksum echo mismatch.")
    if selection_input.selection_criteria_id != selection_criteria.criteria_id:
        raise TechnicalRiskValidationSelectionError("selection_criteria_id echo mismatch.")
    if selection_input.selection_criteria_version != selection_criteria.criteria_version:
        raise TechnicalRiskValidationSelectionError("selection_criteria_version echo mismatch.")
    if selection_input.selection_criteria_checksum != selection_criteria.criteria_checksum:
        raise TechnicalRiskValidationSelectionError("selection_criteria_checksum echo mismatch.")
    ids = tuple(evaluation.evaluation_id for evaluation in evaluations)
    checksums = tuple(evaluation.evaluation_checksum for evaluation in evaluations)
    expected_ids, expected_checksums = _canonical_identity_parts(
        ids,
        checksums,
        "validation_evaluation_ids",
        "validation_evaluation_checksums",
    )
    if selection_input.validation_evaluation_ids != expected_ids:
        raise TechnicalRiskValidationSelectionError("validation_evaluation_ids echo mismatch.")
    if selection_input.validation_evaluation_checksums != expected_checksums:
        raise TechnicalRiskValidationSelectionError("validation_evaluation_checksums echo mismatch.")


def _validate_validation_evaluations(
    validation_dataset,
    development_shortlist: DevelopmentShortlistArtifact,
    selection_criteria: TechnicalRiskValidationSelectionCriteria,
    selection_input: TechnicalRiskValidationSelectionInput,
    evaluations: tuple[TechnicalRiskCandidateEvaluationResult, ...],
) -> None:
    if not evaluations:
        raise TechnicalRiskValidationSelectionError("validation_evaluations must not be empty.")
    shortlist_pairs = {
        _pair_identity(pair): pair
        for pair in development_shortlist.eligible_pairs
    }
    development_refs = {
        _pair_identity_from_development_reference(reference): reference
        for reference in development_shortlist.development_evaluations
    }
    evaluation_pairs = []
    for evaluation in evaluations:
        if evaluation.dataset_id != validation_dataset.dataset_id:
            raise TechnicalRiskValidationSelectionError("Validation evaluation dataset_id mismatch.")
        if evaluation.dataset_checksum != validation_dataset.dataset_checksum:
            raise TechnicalRiskValidationSelectionError("Validation evaluation dataset_checksum mismatch.")
        if _canonical_split_roles(evaluation.evaluated_split_roles) != (TechnicalRiskOOSSplitRole.VALIDATION,):
            raise TechnicalRiskValidationSelectionError("Validation evaluation evidence must be VALIDATION only.")
        key = _pair_identity_from_evaluation(evaluation)
        if key not in shortlist_pairs:
            raise TechnicalRiskValidationSelectionError("Validation evaluation pair is outside Development shortlist.")
        reference = development_refs.get(key)
        if reference is None:
            raise TechnicalRiskValidationSelectionError("Matching Development evaluation reference missing.")
        if evaluation.evaluator_version != reference.evaluator_version:
            raise TechnicalRiskValidationSelectionError("Validation evaluator_version mismatch.")
        if evaluation.metric_version != reference.metric_version:
            raise TechnicalRiskValidationSelectionError("Validation metric_version mismatch.")
        if evaluation.quantile_version != reference.quantile_version:
            raise TechnicalRiskValidationSelectionError("Validation quantile_version mismatch.")
        if evaluation.numeric_context_version != reference.numeric_context_version:
            raise TechnicalRiskValidationSelectionError("Validation numeric_context_version mismatch.")
        if evaluation.evaluator_version != selection_input.evaluator_version:
            raise TechnicalRiskValidationSelectionError("Selection input evaluator_version mismatch.")
        if evaluation.metric_version != selection_criteria.metric_version:
            raise TechnicalRiskValidationSelectionError("Selection criteria metric_version mismatch.")
        if evaluation.quantile_version != selection_criteria.quantile_version:
            raise TechnicalRiskValidationSelectionError("Selection criteria quantile_version mismatch.")
        if evaluation.numeric_context_version != selection_criteria.numeric_context_version:
            raise TechnicalRiskValidationSelectionError("Selection criteria numeric_context_version mismatch.")
        evaluation_pairs.append(key)
    if len(set(evaluation_pairs)) != len(evaluation_pairs):
        raise TechnicalRiskValidationSelectionError("Duplicate Validation evaluation pair.")
    if set(evaluation_pairs) != set(shortlist_pairs):
        raise TechnicalRiskValidationSelectionError("Validation evaluation coverage must equal Development shortlist eligible pairs.")


def _validate_considered_combinations(
    development_shortlist: DevelopmentShortlistArtifact,
    evaluations: tuple[TechnicalRiskCandidateEvaluationResult, ...],
    considered_combinations: tuple[TechnicalRiskValidationConsideredCombination, ...],
) -> None:
    considered = _canonical_considered_combinations(considered_combinations)
    evaluation_keys = {_considered_identity_from_evaluation(evaluation) for evaluation in evaluations}
    considered_keys = {_considered_identity(combination) for combination in considered}
    if considered_keys != evaluation_keys:
        raise TechnicalRiskValidationSelectionError("considered_combinations must retain every Validation evaluation.")
    shortlist_keys = {_pair_identity(pair) for pair in development_shortlist.eligible_pairs}
    for combination in considered:
        if _pair_identity_from_considered(combination) not in shortlist_keys:
            raise TechnicalRiskValidationSelectionError("Considered combination is outside Development shortlist.")


def _validate_selection_state(artifact: TechnicalRiskValidationSelectionArtifact) -> None:
    selected = tuple(
        combination
        for combination in artifact.considered_combinations
        if combination.selection_outcome == TechnicalRiskValidationCombinationOutcome.SELECTED
    )
    not_selected = tuple(
        combination
        for combination in artifact.considered_combinations
        if combination.selection_outcome == TechnicalRiskValidationCombinationOutcome.NOT_SELECTED
    )
    ties = tuple(
        combination
        for combination in artifact.considered_combinations
        if combination.selection_outcome == TechnicalRiskValidationCombinationOutcome.UNRESOLVED_TIE
    )
    selected_fields = (
        artifact.selected_candidate_id,
        artifact.selected_candidate_structural_checksum,
        artifact.selected_threshold_set_id,
        artifact.selected_threshold_set_checksum,
        artifact.accepted_validation_evaluation_id,
        artifact.accepted_validation_evaluation_checksum,
    )
    if artifact.selection_status == TechnicalRiskValidationSelectionStatus.SELECTED:
        if len(selected) != 1:
            raise TechnicalRiskValidationSelectionError("SELECTED status requires exactly one selected combination.")
        for index, value in enumerate(selected_fields):
            _require_text(value, f"selected_fields[{index}]")
        selected_combination = selected[0]
        if _selected_identity(artifact) != _considered_identity(selected_combination):
            raise TechnicalRiskValidationSelectionError("Selected fields must match the selected considered combination.")
        if len(not_selected) != len(artifact.considered_combinations) - 1:
            raise TechnicalRiskValidationSelectionError("SELECTED status requires all other combinations to be NOT_SELECTED.")
        if ties:
            raise TechnicalRiskValidationSelectionError("SELECTED status cannot contain unresolved tie combinations.")
        return
    if any(value is not None for value in selected_fields):
        raise TechnicalRiskValidationSelectionError("Non-selected status cannot include selected pair fields.")
    if selected:
        raise TechnicalRiskValidationSelectionError("Non-selected status cannot contain selected combinations.")
    if artifact.selection_status == TechnicalRiskValidationSelectionStatus.NO_VALID_SELECTION:
        if len(not_selected) != len(artifact.considered_combinations):
            raise TechnicalRiskValidationSelectionError("NO_VALID_SELECTION requires all combinations to be NOT_SELECTED.")
        if TechnicalRiskValidationSelectionReasonCode.NO_VALID_SELECTION_EVIDENCE not in artifact.structured_selection_reason_codes:
            raise TechnicalRiskValidationSelectionError("NO_VALID_SELECTION requires structured rationale.")
        return
    if artifact.selection_status == TechnicalRiskValidationSelectionStatus.TIE_REQUIRES_METHOD_DECISION:
        if len(ties) < 2:
            raise TechnicalRiskValidationSelectionError("TIE_REQUIRES_METHOD_DECISION requires at least two unresolved combinations.")
        if TechnicalRiskValidationSelectionReasonCode.TIE_REQUIRES_METHOD_DECISION not in artifact.structured_selection_reason_codes:
            raise TechnicalRiskValidationSelectionError("Tie status requires structured rationale.")


def _canonical_considered_combinations(
    combinations: tuple[TechnicalRiskValidationConsideredCombination, ...],
) -> tuple[TechnicalRiskValidationConsideredCombination, ...]:
    normalized = tuple(
        combination
        if isinstance(combination, TechnicalRiskValidationConsideredCombination)
        else TechnicalRiskValidationConsideredCombination(**combination)
        for combination in combinations
    )
    if not normalized:
        raise TechnicalRiskValidationSelectionError("considered_combinations must not be empty.")
    keys = tuple(_considered_identity(combination) for combination in normalized)
    if len(set(keys)) != len(keys):
        raise TechnicalRiskValidationSelectionError("Duplicate considered combination.")
    return tuple(sorted(normalized, key=_considered_sort_key))


def _canonical_validation_evaluations(
    evaluations: tuple[TechnicalRiskCandidateEvaluationResult, ...],
) -> tuple[TechnicalRiskCandidateEvaluationResult, ...]:
    return tuple(
        sorted(
            tuple(evaluations),
            key=lambda item: (
                item.candidate_id,
                item.candidate_structural_checksum,
                item.threshold_set_id,
                item.threshold_set_checksum,
                item.evaluation_id,
            ),
        )
    )


def _canonical_reason_codes(
    reason_codes: tuple[TechnicalRiskValidationSelectionReasonCode, ...],
) -> tuple[TechnicalRiskValidationSelectionReasonCode, ...]:
    try:
        normalized = tuple(
            code if isinstance(code, TechnicalRiskValidationSelectionReasonCode) else TechnicalRiskValidationSelectionReasonCode(code)
            for code in reason_codes
        )
    except ValueError as exc:
        raise TechnicalRiskValidationSelectionError("Unsupported structured reason code.") from exc
    if not normalized:
        raise TechnicalRiskValidationSelectionError("structured reason codes must not be empty.")
    if len(set(normalized)) != len(normalized):
        raise TechnicalRiskValidationSelectionError("Duplicate structured reason code.")
    return tuple(sorted(normalized, key=lambda code: code.value))


def _canonical_identity_parts(
    ids: tuple[str, ...],
    checksums: tuple[str, ...],
    id_field_name: str,
    checksum_field_name: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    id_values = tuple(ids)
    checksum_values = tuple(checksums)
    if not id_values:
        raise TechnicalRiskValidationSelectionError(f"{id_field_name} must not be empty.")
    if len(id_values) != len(checksum_values):
        raise TechnicalRiskValidationSelectionError("identity fields must have matching lengths.")
    for index, value in enumerate(id_values):
        _require_text(value, f"{id_field_name}[{index}]")
    for index, value in enumerate(checksum_values):
        _require_text(value, f"{checksum_field_name}[{index}]")
    if len(set(id_values)) != len(id_values):
        raise TechnicalRiskValidationSelectionError(f"Duplicate {id_field_name}.")
    pairs = tuple(sorted(zip(id_values, checksum_values), key=lambda item: (item[0], item[1])))
    return tuple(item[0] for item in pairs), tuple(item[1] for item in pairs)


def _pair_identity(pair: DevelopmentShortlistEligiblePair) -> tuple[str, str, str, str, str, str]:
    return (
        pair.candidate_id,
        pair.candidate_version,
        pair.candidate_structural_checksum,
        pair.threshold_set_id,
        pair.threshold_set_version,
        pair.threshold_set_checksum,
    )


def _pair_identity_from_evaluation(evaluation: TechnicalRiskCandidateEvaluationResult) -> tuple[str, str, str, str, str, str]:
    return (
        evaluation.candidate_id,
        evaluation.candidate_version,
        evaluation.candidate_structural_checksum,
        evaluation.threshold_set_id,
        evaluation.threshold_set_version,
        evaluation.threshold_set_checksum,
    )


def _pair_identity_from_development_reference(reference: DevelopmentEvaluationReference) -> tuple[str, str, str, str, str, str]:
    return (
        reference.candidate_id,
        _candidate_version_for_reference(reference),
        reference.candidate_structural_checksum,
        reference.threshold_set_id,
        _threshold_version_for_reference(reference),
        reference.threshold_set_checksum,
    )


def _pair_identity_from_considered(combination: TechnicalRiskValidationConsideredCombination) -> tuple[str, str, str, str, str, str]:
    return (
        combination.candidate_id,
        combination.candidate_version,
        combination.candidate_structural_checksum,
        combination.threshold_set_id,
        combination.threshold_set_version,
        combination.threshold_set_checksum,
    )


def _considered_identity(combination: TechnicalRiskValidationConsideredCombination) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        combination.candidate_id,
        combination.candidate_version,
        combination.candidate_structural_checksum,
        combination.threshold_set_id,
        combination.threshold_set_version,
        combination.threshold_set_checksum,
        combination.validation_evaluation_id,
        combination.validation_evaluation_checksum,
    )


def _considered_identity_from_evaluation(evaluation: TechnicalRiskCandidateEvaluationResult) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        evaluation.candidate_id,
        evaluation.candidate_version,
        evaluation.candidate_structural_checksum,
        evaluation.threshold_set_id,
        evaluation.threshold_set_version,
        evaluation.threshold_set_checksum,
        evaluation.evaluation_id,
        evaluation.evaluation_checksum,
    )


def _selected_identity(artifact: TechnicalRiskValidationSelectionArtifact) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        artifact.selected_candidate_id,
        _candidate_version_for_selected(artifact),
        artifact.selected_candidate_structural_checksum,
        artifact.selected_threshold_set_id,
        _threshold_version_for_selected(artifact),
        artifact.selected_threshold_set_checksum,
        artifact.accepted_validation_evaluation_id,
        artifact.accepted_validation_evaluation_checksum,
    )


def _candidate_version_for_reference(reference: DevelopmentEvaluationReference) -> str:
    return "v1"


def _threshold_version_for_reference(reference: DevelopmentEvaluationReference) -> str:
    return "v1"


def _candidate_version_for_selected(artifact: TechnicalRiskValidationSelectionArtifact) -> str:
    matches = tuple(
        combination.candidate_version
        for combination in artifact.considered_combinations
        if combination.candidate_id == artifact.selected_candidate_id
        and combination.candidate_structural_checksum == artifact.selected_candidate_structural_checksum
    )
    return matches[0] if matches else ""


def _threshold_version_for_selected(artifact: TechnicalRiskValidationSelectionArtifact) -> str:
    matches = tuple(
        combination.threshold_set_version
        for combination in artifact.considered_combinations
        if combination.threshold_set_id == artifact.selected_threshold_set_id
        and combination.threshold_set_checksum == artifact.selected_threshold_set_checksum
    )
    return matches[0] if matches else ""


def _considered_sort_key(combination: TechnicalRiskValidationConsideredCombination) -> tuple[str, str, str, str, str]:
    return (
        combination.candidate_id,
        combination.candidate_structural_checksum,
        combination.threshold_set_id,
        combination.threshold_set_checksum,
        combination.validation_evaluation_id,
    )


def _canonical_candidates(
    candidates: tuple[TechnicalRiskCandidateIdentity, ...],
) -> tuple[TechnicalRiskCandidateIdentity, ...]:
    normalized = tuple(
        candidate if isinstance(candidate, TechnicalRiskCandidateIdentity) else TechnicalRiskCandidateIdentity(**candidate)
        for candidate in candidates
    )
    if not normalized:
        raise TechnicalRiskValidationSelectionError("eligible_candidates must not be empty.")
    keys = tuple((candidate.candidate_id, candidate.candidate_structural_checksum) for candidate in normalized)
    if len(set(keys)) != len(keys):
        raise TechnicalRiskValidationSelectionError("Duplicate eligible candidate.")
    return tuple(sorted(normalized, key=lambda item: (item.candidate_id, item.candidate_structural_checksum)))


def _canonical_thresholds(
    thresholds: tuple[TechnicalRiskThresholdIdentity, ...],
) -> tuple[TechnicalRiskThresholdIdentity, ...]:
    normalized = tuple(
        threshold if isinstance(threshold, TechnicalRiskThresholdIdentity) else TechnicalRiskThresholdIdentity(**threshold)
        for threshold in thresholds
    )
    if not normalized:
        raise TechnicalRiskValidationSelectionError("eligible_threshold_sets must not be empty.")
    keys = tuple((threshold.threshold_set_id, threshold.threshold_set_checksum) for threshold in normalized)
    if len(set(keys)) != len(keys):
        raise TechnicalRiskValidationSelectionError("Duplicate eligible threshold.")
    return tuple(sorted(normalized, key=lambda item: (item.threshold_set_id, item.threshold_set_checksum)))


def _canonical_development_evaluations(
    references: tuple[DevelopmentEvaluationReference, ...],
) -> tuple[DevelopmentEvaluationReference, ...]:
    normalized = tuple(
        reference if isinstance(reference, DevelopmentEvaluationReference) else DevelopmentEvaluationReference(**reference)
        for reference in references
    )
    return tuple(
        sorted(
            normalized,
            key=lambda item: (
                item.candidate_id,
                item.threshold_set_id,
                item.evaluation_id,
                item.evaluation_checksum,
            ),
        )
    )


def _candidate_map(candidates: tuple[TechnicalRiskCandidateIdentity, ...]) -> dict[str, str]:
    return {candidate.candidate_id: candidate.candidate_structural_checksum for candidate in _canonical_candidates(candidates)}


def _threshold_map(thresholds: tuple[TechnicalRiskThresholdIdentity, ...]) -> dict[str, str]:
    return {threshold.threshold_set_id: threshold.threshold_set_checksum for threshold in _canonical_thresholds(thresholds)}


def _canonical_split_roles(values: tuple[TechnicalRiskOOSSplitRole, ...]) -> tuple[TechnicalRiskOOSSplitRole, ...]:
    roles = tuple(value if isinstance(value, TechnicalRiskOOSSplitRole) else TechnicalRiskOOSSplitRole(value) for value in values)
    if len(set(roles)) != len(roles):
        raise TechnicalRiskValidationSelectionError("Duplicate split role.")
    return tuple(sorted(roles, key=lambda role: role.value))


def _shortlist_checksum(shortlist: DevelopmentShortlistArtifact) -> str:
    return _stable_hash(
        {
            "shortlist_version": shortlist.shortlist_version,
            "development_experiment_id": shortlist.development_experiment_id,
            "development_experiment_checksum": shortlist.development_experiment_checksum,
            "candidate_set_id": shortlist.candidate_set_id,
            "candidate_set_checksum": shortlist.candidate_set_checksum,
            "threshold_candidate_generation_id": shortlist.threshold_candidate_generation_id,
            "threshold_candidate_generation_checksum": shortlist.threshold_candidate_generation_checksum,
            "eligible_pairs": [
                {
                    "candidate_id": pair.candidate_id,
                    "candidate_version": pair.candidate_version,
                    "candidate_structural_checksum": pair.candidate_structural_checksum,
                    "threshold_set_id": pair.threshold_set_id,
                    "threshold_set_version": pair.threshold_set_version,
                    "threshold_set_checksum": pair.threshold_set_checksum,
                    "development_evaluation_id": pair.development_evaluation_id,
                    "development_evaluation_checksum": pair.development_evaluation_checksum,
                }
                for pair in shortlist.eligible_pairs
            ],
            "eligible_candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "candidate_version": candidate.candidate_version,
                    "candidate_structural_checksum": candidate.candidate_structural_checksum,
                }
                for candidate in shortlist.eligible_candidates
            ],
            "eligible_threshold_sets": [
                {
                    "threshold_set_id": threshold.threshold_set_id,
                    "threshold_set_version": threshold.threshold_set_version,
                    "threshold_set_checksum": threshold.threshold_set_checksum,
                }
                for threshold in shortlist.eligible_threshold_sets
            ],
            "development_evaluations": [_development_evaluation_payload(reference) for reference in shortlist.development_evaluations],
        }
    )


def _development_evaluation_payload(reference: DevelopmentEvaluationReference) -> dict[str, object]:
    return {
        "evaluation_id": reference.evaluation_id,
        "evaluation_checksum": reference.evaluation_checksum,
        "dataset_checksum": reference.dataset_checksum,
        "candidate_id": reference.candidate_id,
        "candidate_structural_checksum": reference.candidate_structural_checksum,
        "threshold_set_id": reference.threshold_set_id,
        "threshold_set_checksum": reference.threshold_set_checksum,
        "evaluated_split_roles": [role.value for role in reference.evaluated_split_roles],
        "evaluator_version": reference.evaluator_version,
        "metric_version": reference.metric_version,
        "quantile_version": reference.quantile_version,
        "numeric_context_version": reference.numeric_context_version,
    }


def _criteria_checksum(criteria: TechnicalRiskValidationSelectionCriteria) -> str:
    return _stable_hash(
        {
            "criteria_version": criteria.criteria_version,
            "monotonicity_preference": criteria.monotonicity_preference.value,
            "median_separation_preference": criteria.median_separation_preference.value,
            "coverage_preference": criteria.coverage_preference.value,
            "empty_bucket_policy": criteria.empty_bucket_policy.value,
            "methodology_warning_policy": criteria.methodology_warning_policy.value,
            "tie_policy": criteria.tie_policy.value,
            "numeric_context_version": criteria.numeric_context_version,
            "metric_version": criteria.metric_version,
            "quantile_version": criteria.quantile_version,
        }
    )


def _selection_checksum(artifact: TechnicalRiskValidationSelectionArtifact) -> str:
    return _stable_hash(
        {
            "selection_version": artifact.selection_version,
            "validation_dataset_id": artifact.validation_dataset_id,
            "validation_dataset_checksum": artifact.validation_dataset_checksum,
            "development_shortlist_id": artifact.development_shortlist_id,
            "development_shortlist_checksum": artifact.development_shortlist_checksum,
            "selection_criteria_id": artifact.selection_criteria_id,
            "selection_criteria_version": artifact.selection_criteria_version,
            "selection_criteria_checksum": artifact.selection_criteria_checksum,
            "selection_status": artifact.selection_status.value,
            "selected_candidate_id": artifact.selected_candidate_id,
            "selected_candidate_structural_checksum": artifact.selected_candidate_structural_checksum,
            "selected_threshold_set_id": artifact.selected_threshold_set_id,
            "selected_threshold_set_checksum": artifact.selected_threshold_set_checksum,
            "accepted_validation_evaluation_id": artifact.accepted_validation_evaluation_id,
            "accepted_validation_evaluation_checksum": artifact.accepted_validation_evaluation_checksum,
            "considered_combinations": [
                {
                    "candidate_id": combination.candidate_id,
                    "candidate_version": combination.candidate_version,
                    "candidate_structural_checksum": combination.candidate_structural_checksum,
                    "threshold_set_id": combination.threshold_set_id,
                    "threshold_set_version": combination.threshold_set_version,
                    "threshold_set_checksum": combination.threshold_set_checksum,
                    "validation_evaluation_id": combination.validation_evaluation_id,
                    "validation_evaluation_checksum": combination.validation_evaluation_checksum,
                    "selection_outcome": combination.selection_outcome.value,
                    "structured_reason_codes": [code.value for code in combination.structured_reason_codes],
                }
                for combination in artifact.considered_combinations
            ],
            "structured_selection_reason_codes": [code.value for code in artifact.structured_selection_reason_codes],
            "evaluator_version": artifact.evaluator_version,
            "metric_version": artifact.metric_version,
            "quantile_version": artifact.quantile_version,
            "numeric_context_version": artifact.numeric_context_version,
        }
    )


def _coerce_enum(value: object, enum_type: type[StrEnum], field_name: str) -> StrEnum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        raise TechnicalRiskValidationSelectionError(f"Unsupported {field_name}.") from exc


def _require_version(value: object, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskValidationSelectionError(f"Unsupported {field_name}.")


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskValidationSelectionError(f"{field_name} must be a non-empty string.")


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
