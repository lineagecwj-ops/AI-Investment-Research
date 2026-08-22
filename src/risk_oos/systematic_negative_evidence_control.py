from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1 = "SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1"
SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW = "DRAFT_FOR_METHOD_REVIEW"
SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT = "POST_HOLDOUT_DIAGNOSTIC_METHODOLOGY"
SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE = date(2023, 12, 31)
SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_SENTINEL_DATE = date(1, 1, 1)
SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_INDUSTRY_MATCHING_POLICY = "PREFERRED"


class SystematicNegativeEvidenceControlError(Exception):
    """Raised when systematic negative-evidence control inputs fail closed."""


class SystematicNegativeEvidenceSourceClass(StrEnum):
    REGULATORY_MOPS = "REGULATORY_MOPS"
    COMPREHENSIVE_BUSINESS_REPORT = "COMPREHENSIVE_BUSINESS_REPORT"
    INVESTOR_MATERIAL = "INVESTOR_MATERIAL"
    OFFICIAL_COMPANY_DISCLOSURE = "OFFICIAL_COMPANY_DISCLOSURE"
    APPROVED_OFFICIAL_ECOSYSTEM_SOURCE = "APPROVED_OFFICIAL_ECOSYSTEM_SOURCE"


class SystematicNegativeEvidenceSourceReviewState(StrEnum):
    REVIEWED_ELIGIBLE = "REVIEWED_ELIGIBLE"
    SEARCHED_NOT_FOUND = "SEARCHED_NOT_FOUND"
    UNAVAILABLE_OR_UNRECOVERABLE = "UNAVAILABLE_OR_UNRECOVERABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_REVIEWED = "NOT_REVIEWED"


class SystematicNegativeEvidenceBusinessCoverage(StrEnum):
    BROAD = "BROAD"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


class SystematicNegativeEvidenceAIStatus(StrEnum):
    AI_EVIDENCE_NOT_FOUND_UNDER_COMPLETED_REVIEW = "AI_EVIDENCE_NOT_FOUND_UNDER_COMPLETED_REVIEW"
    AI_HIGH_EVIDENCE_FOUND = "AI_HIGH_EVIDENCE_FOUND"
    AI_ADJACENT_EVIDENCE_FOUND = "AI_ADJACENT_EVIDENCE_FOUND"
    AI_EVIDENCE_AMBIGUOUS = "AI_EVIDENCE_AMBIGUOUS"
    AI_EVIDENCE_REVIEW_INCOMPLETE = "AI_EVIDENCE_REVIEW_INCOMPLETE"


class SystematicNegativeEvidenceEcosystemStatus(StrEnum):
    NO_ELIGIBLE_ECOSYSTEM_AI_EVIDENCE = "NO_ELIGIBLE_ECOSYSTEM_AI_EVIDENCE"
    ELIGIBLE_ECOSYSTEM_AI_EVIDENCE_FOUND = "ELIGIBLE_ECOSYSTEM_AI_EVIDENCE_FOUND"
    ECOSYSTEM_EVIDENCE_AMBIGUOUS = "ECOSYSTEM_EVIDENCE_AMBIGUOUS"
    ECOSYSTEM_REVIEW_INCOMPLETE = "ECOSYSTEM_REVIEW_INCOMPLETE"


class SystematicNegativeEvidenceConflictStatus(StrEnum):
    NO_CONFLICT = "NO_CONFLICT"
    AI_EVIDENCE_CONFLICT = "AI_EVIDENCE_CONFLICT"
    UNRESOLVED_EVIDENCE_CONFLICT = "UNRESOLVED_EVIDENCE_CONFLICT"


class SystematicNegativeEvidenceReviewCompleteness(StrEnum):
    CONTROL_REVIEW_COMPLETE = "CONTROL_REVIEW_COMPLETE"
    CONTROL_REVIEW_INCOMPLETE = "CONTROL_REVIEW_INCOMPLETE"


class SystematicNegativeEvidenceControlReviewState(StrEnum):
    CONTROL_REVIEW_COMPLETE = "CONTROL_REVIEW_COMPLETE"
    CONTROL_REVIEW_INCOMPLETE = "CONTROL_REVIEW_INCOMPLETE"
    CONTROL_CONFLICT_FOUND = "CONTROL_CONFLICT_FOUND"
    CONTROL_AI_EVIDENCE_FOUND = "CONTROL_AI_EVIDENCE_FOUND"
    CONTROL_ELIGIBLE_UNDER_SYSTEMATIC_NEGATIVE_EVIDENCE = (
        "CONTROL_ELIGIBLE_UNDER_SYSTEMATIC_NEGATIVE_EVIDENCE"
    )


@dataclass(frozen=True)
class SystematicNegativeEvidenceSourceReview:
    source_class: SystematicNegativeEvidenceSourceClass | str
    review_state: SystematicNegativeEvidenceSourceReviewState | str
    publication_date: date | None = None
    publication_date_verified: bool = False
    publication_date_is_synthetic_fallback: bool = False
    audit_reason: str | None = None
    supports_broad_business_coverage: bool = False
    is_required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_class", SystematicNegativeEvidenceSourceClass(self.source_class))
        object.__setattr__(
            self,
            "review_state",
            SystematicNegativeEvidenceSourceReviewState(self.review_state),
        )
        if not isinstance(self.publication_date_verified, bool):
            raise SystematicNegativeEvidenceControlError("publication_date_verified must be bool.")
        if not isinstance(self.publication_date_is_synthetic_fallback, bool):
            raise SystematicNegativeEvidenceControlError("publication_date_is_synthetic_fallback must be bool.")
        if self.publication_date_is_synthetic_fallback:
            raise SystematicNegativeEvidenceControlError("synthetic fallback publication_date is forbidden.")
        if not isinstance(self.supports_broad_business_coverage, bool):
            raise SystematicNegativeEvidenceControlError("supports_broad_business_coverage must be bool.")
        if not isinstance(self.is_required, bool):
            raise SystematicNegativeEvidenceControlError("is_required must be bool.")
        if self.review_state == SystematicNegativeEvidenceSourceReviewState.REVIEWED_ELIGIBLE:
            _require_eligible_publication_date(self.publication_date, self.publication_date_verified)
        elif self.publication_date_verified:
            raise SystematicNegativeEvidenceControlError("Only REVIEWED_ELIGIBLE sources may verify publication date.")
        if self.review_state in {
            SystematicNegativeEvidenceSourceReviewState.UNAVAILABLE_OR_UNRECOVERABLE,
            SystematicNegativeEvidenceSourceReviewState.NOT_APPLICABLE,
        }:
            _require_text(self.audit_reason, "audit_reason")
        if self.review_state == SystematicNegativeEvidenceSourceReviewState.NOT_REVIEWED and self.audit_reason:
            raise SystematicNegativeEvidenceControlError("NOT_REVIEWED source must not carry audit_reason.")


@dataclass(frozen=True)
class SystematicNegativeEvidenceControlInput:
    symbol: str
    source_class_reviews: tuple[SystematicNegativeEvidenceSourceReview, ...]
    historical_business_identity_supported: bool
    business_coverage_quality: SystematicNegativeEvidenceBusinessCoverage | str
    ai_high_evidence_status: SystematicNegativeEvidenceAIStatus | str
    ai_adjacent_evidence_status: SystematicNegativeEvidenceAIStatus | str
    ecosystem_evidence_status: SystematicNegativeEvidenceEcosystemStatus | str
    conflict_status: SystematicNegativeEvidenceConflictStatus | str
    review_completeness: SystematicNegativeEvidenceReviewCompleteness | str
    reviewer_notes: str | None = None
    protocol_version: str = SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1
    protocol_status: str = SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW
    governance_scope: str = SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT
    evidence_cutoff_date: date = SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE

    def __post_init__(self) -> None:
        _require_text(self.symbol, "symbol")
        _require_version(self.protocol_version, SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1, "protocol_version")
        _require_version(
            self.protocol_status,
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW,
            "protocol_status",
        )
        _require_version(
            self.governance_scope,
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT,
            "governance_scope",
        )
        if self.evidence_cutoff_date != SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE:
            raise SystematicNegativeEvidenceControlError("evidence_cutoff_date mismatch.")
        if not self.source_class_reviews:
            raise SystematicNegativeEvidenceControlError("source_class_reviews is required.")
        if not isinstance(self.historical_business_identity_supported, bool):
            raise SystematicNegativeEvidenceControlError("historical_business_identity_supported must be bool.")
        object.__setattr__(
            self,
            "source_class_reviews",
            tuple(_coerce_source_review(review) for review in self.source_class_reviews),
        )
        _reject_duplicate_source_classes(self.source_class_reviews)
        _require_all_source_classes(self.source_class_reviews)
        object.__setattr__(
            self,
            "business_coverage_quality",
            SystematicNegativeEvidenceBusinessCoverage(self.business_coverage_quality),
        )
        object.__setattr__(self, "ai_high_evidence_status", SystematicNegativeEvidenceAIStatus(self.ai_high_evidence_status))
        object.__setattr__(
            self,
            "ai_adjacent_evidence_status",
            SystematicNegativeEvidenceAIStatus(self.ai_adjacent_evidence_status),
        )
        object.__setattr__(
            self,
            "ecosystem_evidence_status",
            SystematicNegativeEvidenceEcosystemStatus(self.ecosystem_evidence_status),
        )
        object.__setattr__(
            self,
            "conflict_status",
            SystematicNegativeEvidenceConflictStatus(self.conflict_status),
        )
        object.__setattr__(
            self,
            "review_completeness",
            SystematicNegativeEvidenceReviewCompleteness(self.review_completeness),
        )
        if self.reviewer_notes is not None:
            _require_text(self.reviewer_notes, "reviewer_notes")


@dataclass(frozen=True)
class SystematicNegativeEvidenceControlAssessment:
    protocol_version: str
    protocol_status: str
    governance_scope: str
    evidence_cutoff_date: date
    symbol: str
    control_review_state: SystematicNegativeEvidenceControlReviewState
    control_eligibility: bool
    unknown_reason: str | None

    def __post_init__(self) -> None:
        _require_version(self.protocol_version, SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1, "protocol_version")
        _require_version(
            self.protocol_status,
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW,
            "protocol_status",
        )
        _require_version(
            self.governance_scope,
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT,
            "governance_scope",
        )
        if self.evidence_cutoff_date != SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE:
            raise SystematicNegativeEvidenceControlError("evidence_cutoff_date mismatch.")
        _require_text(self.symbol, "symbol")
        object.__setattr__(
            self,
            "control_review_state",
            SystematicNegativeEvidenceControlReviewState(self.control_review_state),
        )
        if not isinstance(self.control_eligibility, bool):
            raise SystematicNegativeEvidenceControlError("control_eligibility must be bool.")
        if self.unknown_reason is not None:
            _require_text(self.unknown_reason, "unknown_reason")
        if self.control_eligibility and self.unknown_reason is not None:
            raise SystematicNegativeEvidenceControlError("control eligible assessment must not carry unknown_reason.")


def assess_systematic_negative_evidence_control(
    control_input: SystematicNegativeEvidenceControlInput,
) -> SystematicNegativeEvidenceControlAssessment:
    """Apply deterministic fail-closed gates without changing any cohort label."""

    if not control_input.historical_business_identity_supported:
        return _assessment(control_input, False, "HISTORICAL_BUSINESS_IDENTITY_NOT_SUPPORTED")
    if control_input.business_coverage_quality != SystematicNegativeEvidenceBusinessCoverage.BROAD:
        return _assessment(control_input, False, "BROAD_BUSINESS_COVERAGE_REQUIRED")
    completeness_reason = _review_completeness_failure_reason(control_input)
    if completeness_reason is not None:
        return _assessment(control_input, False, completeness_reason)
    if control_input.ai_high_evidence_status == SystematicNegativeEvidenceAIStatus.AI_HIGH_EVIDENCE_FOUND:
        return _assessment(
            control_input,
            False,
            "AI_HIGH_EVIDENCE_DISQUALIFIES_CONTROL",
            SystematicNegativeEvidenceControlReviewState.CONTROL_AI_EVIDENCE_FOUND,
        )
    if control_input.ai_adjacent_evidence_status == SystematicNegativeEvidenceAIStatus.AI_ADJACENT_EVIDENCE_FOUND:
        return _assessment(
            control_input,
            False,
            "AI_ADJACENT_EVIDENCE_DISQUALIFIES_CONTROL",
            SystematicNegativeEvidenceControlReviewState.CONTROL_AI_EVIDENCE_FOUND,
        )
    if control_input.ai_high_evidence_status != SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_NOT_FOUND_UNDER_COMPLETED_REVIEW:
        return _assessment(control_input, False, "AI_HIGH_REVIEW_NOT_SYSTEMATIC_NEGATIVE")
    if (
        control_input.ai_adjacent_evidence_status
        != SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_NOT_FOUND_UNDER_COMPLETED_REVIEW
    ):
        return _assessment(control_input, False, "AI_ADJACENT_REVIEW_NOT_SYSTEMATIC_NEGATIVE")
    if (
        control_input.ecosystem_evidence_status
        == SystematicNegativeEvidenceEcosystemStatus.ELIGIBLE_ECOSYSTEM_AI_EVIDENCE_FOUND
    ):
        return _assessment(
            control_input,
            False,
            "ECOSYSTEM_AI_EVIDENCE_DISQUALIFIES_CONTROL",
            SystematicNegativeEvidenceControlReviewState.CONTROL_AI_EVIDENCE_FOUND,
        )
    if control_input.ecosystem_evidence_status != SystematicNegativeEvidenceEcosystemStatus.NO_ELIGIBLE_ECOSYSTEM_AI_EVIDENCE:
        return _assessment(control_input, False, "ECOSYSTEM_REVIEW_NOT_SYSTEMATIC_NEGATIVE")
    if control_input.conflict_status != SystematicNegativeEvidenceConflictStatus.NO_CONFLICT:
        return _assessment(
            control_input,
            False,
            "UNRESOLVED_OR_AI_EVIDENCE_CONFLICT",
            SystematicNegativeEvidenceControlReviewState.CONTROL_CONFLICT_FOUND,
        )
    return _assessment(
        control_input,
        True,
        None,
        SystematicNegativeEvidenceControlReviewState.CONTROL_ELIGIBLE_UNDER_SYSTEMATIC_NEGATIVE_EVIDENCE,
    )


def _assessment(
    control_input: SystematicNegativeEvidenceControlInput,
    control_eligibility: bool,
    unknown_reason: str | None,
    control_review_state: SystematicNegativeEvidenceControlReviewState = (
        SystematicNegativeEvidenceControlReviewState.CONTROL_REVIEW_INCOMPLETE
    ),
) -> SystematicNegativeEvidenceControlAssessment:
    return SystematicNegativeEvidenceControlAssessment(
        protocol_version=control_input.protocol_version,
        protocol_status=control_input.protocol_status,
        governance_scope=control_input.governance_scope,
        evidence_cutoff_date=control_input.evidence_cutoff_date,
        symbol=control_input.symbol,
        control_review_state=control_review_state,
        control_eligibility=control_eligibility,
        unknown_reason=unknown_reason,
    )


def _review_completeness_failure_reason(control_input: SystematicNegativeEvidenceControlInput) -> str | None:
    if control_input.review_completeness != SystematicNegativeEvidenceReviewCompleteness.CONTROL_REVIEW_COMPLETE:
        return "CONTROL_REVIEW_COMPLETE_REQUIRED"
    if not any(
        review.review_state == SystematicNegativeEvidenceSourceReviewState.REVIEWED_ELIGIBLE
        for review in control_input.source_class_reviews
    ):
        return "AT_LEAST_ONE_ELIGIBLE_SOURCE_REQUIRED"
    if not any(review.supports_broad_business_coverage for review in control_input.source_class_reviews):
        return "BROAD_COVERAGE_SOURCE_SUPPORT_REQUIRED"
    if not any(
        review.source_class == SystematicNegativeEvidenceSourceClass.COMPREHENSIVE_BUSINESS_REPORT
        and review.review_state == SystematicNegativeEvidenceSourceReviewState.REVIEWED_ELIGIBLE
        for review in control_input.source_class_reviews
    ):
        eligible_supporting_classes = {
            review.source_class
            for review in control_input.source_class_reviews
            if review.review_state == SystematicNegativeEvidenceSourceReviewState.REVIEWED_ELIGIBLE
            and review.supports_broad_business_coverage
        }
        if len(eligible_supporting_classes) < 2:
            return "COMPREHENSIVE_REPORT_OR_MULTIPLE_BROAD_SOURCES_REQUIRED"
    for review in control_input.source_class_reviews:
        if review.is_required and review.review_state == SystematicNegativeEvidenceSourceReviewState.NOT_REVIEWED:
            return "REQUIRED_SOURCE_CLASS_NOT_REVIEWED"
        if review.review_state == SystematicNegativeEvidenceSourceReviewState.SEARCHED_NOT_FOUND and len(
            control_input.source_class_reviews
        ) == 1:
            return "SEARCHED_NOT_FOUND_ALONE_INSUFFICIENT"
    return None


def _coerce_source_review(review: SystematicNegativeEvidenceSourceReview) -> SystematicNegativeEvidenceSourceReview:
    if isinstance(review, SystematicNegativeEvidenceSourceReview):
        return review
    raise SystematicNegativeEvidenceControlError("source_class_reviews must contain source review records.")


def _reject_duplicate_source_classes(reviews: tuple[SystematicNegativeEvidenceSourceReview, ...]) -> None:
    seen: set[SystematicNegativeEvidenceSourceClass] = set()
    for review in reviews:
        if review.source_class in seen:
            raise SystematicNegativeEvidenceControlError("duplicate source_class entries are not allowed.")
        seen.add(review.source_class)


def _require_all_source_classes(reviews: tuple[SystematicNegativeEvidenceSourceReview, ...]) -> None:
    actual = {review.source_class for review in reviews}
    expected = set(SystematicNegativeEvidenceSourceClass)
    if actual != expected:
        raise SystematicNegativeEvidenceControlError("Every configured source_class must have explicit review state.")


def _require_eligible_publication_date(publication_date: date | None, publication_date_verified: bool) -> None:
    if publication_date is None:
        raise SystematicNegativeEvidenceControlError("publication_date is required for eligible evidence.")
    if not publication_date_verified:
        raise SystematicNegativeEvidenceControlError("publication_date must be verified for eligible evidence.")
    if publication_date == SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_SENTINEL_DATE:
        raise SystematicNegativeEvidenceControlError("sentinel publication_date is never eligible.")
    if publication_date > SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE:
        raise SystematicNegativeEvidenceControlError("publication_date exceeds evidence cutoff.")


def _require_text(value: str | None, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SystematicNegativeEvidenceControlError(f"{field_name} is required.")


def _require_version(actual: str, expected: str, field_name: str) -> None:
    if actual != expected:
        raise SystematicNegativeEvidenceControlError(f"{field_name} mismatch.")
