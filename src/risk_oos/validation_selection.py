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
TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1 = "TECH_RISK_VALIDATION_SELECTION_CRITERIA_V1"


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
