from __future__ import annotations

import inspect
import sys
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos.systematic_negative_evidence_control as control_module
from risk_oos.systematic_negative_evidence_control import (
    SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE,
    SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT,
    SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW,
    SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1,
    SystematicNegativeEvidenceAIStatus,
    SystematicNegativeEvidenceBusinessCoverage,
    SystematicNegativeEvidenceConflictStatus,
    SystematicNegativeEvidenceControlError,
    SystematicNegativeEvidenceControlInput,
    SystematicNegativeEvidenceControlReviewState,
    SystematicNegativeEvidenceEcosystemStatus,
    SystematicNegativeEvidenceReviewCompleteness,
    SystematicNegativeEvidenceSourceClass,
    SystematicNegativeEvidenceSourceReview,
    SystematicNegativeEvidenceSourceReviewState,
    assess_systematic_negative_evidence_control,
)


def _review(
    source_class: SystematicNegativeEvidenceSourceClass,
    review_state: SystematicNegativeEvidenceSourceReviewState,
    *,
    publication_date: date | None = None,
    publication_date_verified: bool = False,
    publication_date_is_synthetic_fallback: bool = False,
    audit_reason: str | None = None,
    supports_broad_business_coverage: bool = False,
) -> SystematicNegativeEvidenceSourceReview:
    return SystematicNegativeEvidenceSourceReview(
        source_class=source_class,
        review_state=review_state,
        publication_date=publication_date,
        publication_date_verified=publication_date_verified,
        publication_date_is_synthetic_fallback=publication_date_is_synthetic_fallback,
        audit_reason=audit_reason,
        supports_broad_business_coverage=supports_broad_business_coverage,
    )


def _eligible_review(
    source_class: SystematicNegativeEvidenceSourceClass,
    publication_date: date,
) -> SystematicNegativeEvidenceSourceReview:
    return _review(
        source_class,
        SystematicNegativeEvidenceSourceReviewState.REVIEWED_ELIGIBLE,
        publication_date=publication_date,
        publication_date_verified=True,
        supports_broad_business_coverage=True,
    )


def _complete_reviews() -> tuple[SystematicNegativeEvidenceSourceReview, ...]:
    return (
        _eligible_review(SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS, date(2021, 3, 1)),
        _eligible_review(SystematicNegativeEvidenceSourceClass.COMPREHENSIVE_BUSINESS_REPORT, date(2022, 4, 1)),
        _review(
            SystematicNegativeEvidenceSourceClass.INVESTOR_MATERIAL,
            SystematicNegativeEvidenceSourceReviewState.SEARCHED_NOT_FOUND,
        ),
        _eligible_review(SystematicNegativeEvidenceSourceClass.OFFICIAL_COMPANY_DISCLOSURE, date(2023, 6, 1)),
        _review(
            SystematicNegativeEvidenceSourceClass.APPROVED_OFFICIAL_ECOSYSTEM_SOURCE,
            SystematicNegativeEvidenceSourceReviewState.SEARCHED_NOT_FOUND,
        ),
    )


def _control_input(
    *,
    source_class_reviews: tuple[SystematicNegativeEvidenceSourceReview, ...] | None = None,
    historical_business_identity_supported: bool = True,
    business_coverage_quality: SystematicNegativeEvidenceBusinessCoverage = SystematicNegativeEvidenceBusinessCoverage.BROAD,
    ai_high_evidence_status: SystematicNegativeEvidenceAIStatus = (
        SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_NOT_FOUND_UNDER_COMPLETED_REVIEW
    ),
    ai_adjacent_evidence_status: SystematicNegativeEvidenceAIStatus = (
        SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_NOT_FOUND_UNDER_COMPLETED_REVIEW
    ),
    ecosystem_evidence_status: SystematicNegativeEvidenceEcosystemStatus = (
        SystematicNegativeEvidenceEcosystemStatus.NO_ELIGIBLE_ECOSYSTEM_AI_EVIDENCE
    ),
    conflict_status: SystematicNegativeEvidenceConflictStatus = SystematicNegativeEvidenceConflictStatus.NO_CONFLICT,
    review_completeness: SystematicNegativeEvidenceReviewCompleteness = (
        SystematicNegativeEvidenceReviewCompleteness.CONTROL_REVIEW_COMPLETE
    ),
) -> SystematicNegativeEvidenceControlInput:
    return SystematicNegativeEvidenceControlInput(
        symbol="2330",
        source_class_reviews=source_class_reviews or _complete_reviews(),
        historical_business_identity_supported=historical_business_identity_supported,
        business_coverage_quality=business_coverage_quality,
        ai_high_evidence_status=ai_high_evidence_status,
        ai_adjacent_evidence_status=ai_adjacent_evidence_status,
        ecosystem_evidence_status=ecosystem_evidence_status,
        conflict_status=conflict_status,
        review_completeness=review_completeness,
        reviewer_notes="completed systematic negative evidence review",
    )


class SystematicNegativeEvidenceControlContractTest(unittest.TestCase):
    def test_protocol_identity_is_draft_for_post_holdout_method_review(self) -> None:
        control_input = _control_input()

        self.assertEqual(control_input.protocol_version, SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_V1)
        self.assertEqual(
            control_input.protocol_status,
            SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_STATUS_DRAFT_FOR_METHOD_REVIEW,
        )
        self.assertEqual(control_input.governance_scope, SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_GOVERNANCE_POST_HOLDOUT)
        self.assertEqual(control_input.evidence_cutoff_date, SYSTEMATIC_NEGATIVE_EVIDENCE_CONTROL_CUTOFF_DATE)

    def test_configured_source_classes_are_explicit_and_closed(self) -> None:
        self.assertEqual(
            {source_class.value for source_class in SystematicNegativeEvidenceSourceClass},
            {
                "REGULATORY_MOPS",
                "COMPREHENSIVE_BUSINESS_REPORT",
                "INVESTOR_MATERIAL",
                "OFFICIAL_COMPANY_DISCLOSURE",
                "APPROVED_OFFICIAL_ECOSYSTEM_SOURCE",
            },
        )

    def test_source_review_states_are_explicit_and_closed(self) -> None:
        self.assertEqual(
            {state.value for state in SystematicNegativeEvidenceSourceReviewState},
            {
                "REVIEWED_ELIGIBLE",
                "SEARCHED_NOT_FOUND",
                "UNAVAILABLE_OR_UNRECOVERABLE",
                "NOT_APPLICABLE",
                "NOT_REVIEWED",
            },
        )
        with self.assertRaises(ValueError):
            _review(SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS, "UNKNOWN_STATE")  # type: ignore[arg-type]

    def test_duplicate_source_class_is_rejected(self) -> None:
        duplicate = _complete_reviews() + (
            _eligible_review(SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS, date(2020, 1, 1)),
        )

        with self.assertRaisesRegex(SystematicNegativeEvidenceControlError, "duplicate source_class"):
            _control_input(source_class_reviews=duplicate)

    def test_missing_configured_source_class_is_rejected(self) -> None:
        reviews = tuple(
            review
            for review in _complete_reviews()
            if review.source_class != SystematicNegativeEvidenceSourceClass.INVESTOR_MATERIAL
        )

        with self.assertRaisesRegex(SystematicNegativeEvidenceControlError, "Every configured source_class"):
            _control_input(source_class_reviews=reviews)

    def test_eligible_source_requires_verified_non_sentinel_pre_cutoff_date(self) -> None:
        with self.assertRaisesRegex(SystematicNegativeEvidenceControlError, "sentinel"):
            _eligible_review(SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS, date(1, 1, 1))
        with self.assertRaisesRegex(SystematicNegativeEvidenceControlError, "verified"):
            _review(
                SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS,
                SystematicNegativeEvidenceSourceReviewState.REVIEWED_ELIGIBLE,
                publication_date=date(2022, 1, 1),
                publication_date_verified=False,
            )
        with self.assertRaisesRegex(SystematicNegativeEvidenceControlError, "cutoff"):
            _eligible_review(SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS, date(2024, 1, 1))

    def test_synthetic_fallback_publication_date_is_forbidden(self) -> None:
        with self.assertRaisesRegex(SystematicNegativeEvidenceControlError, "synthetic fallback"):
            _review(
                SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS,
                SystematicNegativeEvidenceSourceReviewState.REVIEWED_ELIGIBLE,
                publication_date=date(2023, 12, 31),
                publication_date_verified=True,
                publication_date_is_synthetic_fallback=True,
            )

    def test_genuine_verified_cutoff_date_is_allowed_when_not_synthetic(self) -> None:
        review = _eligible_review(SystematicNegativeEvidenceSourceClass.REGULATORY_MOPS, date(2023, 12, 31))

        self.assertEqual(review.publication_date, date(2023, 12, 31))
        self.assertTrue(review.publication_date_verified)
        self.assertFalse(review.publication_date_is_synthetic_fallback)

    def test_unavailable_and_not_applicable_sources_require_audit_reason(self) -> None:
        for state in (
            SystematicNegativeEvidenceSourceReviewState.UNAVAILABLE_OR_UNRECOVERABLE,
            SystematicNegativeEvidenceSourceReviewState.NOT_APPLICABLE,
        ):
            with self.assertRaisesRegex(SystematicNegativeEvidenceControlError, "audit_reason"):
                _review(SystematicNegativeEvidenceSourceClass.INVESTOR_MATERIAL, state)

    def test_complete_systematic_negative_review_is_control_eligible(self) -> None:
        assessment = assess_systematic_negative_evidence_control(_control_input())

        self.assertTrue(assessment.control_eligibility)
        self.assertEqual(
            assessment.control_review_state,
            SystematicNegativeEvidenceControlReviewState.CONTROL_ELIGIBLE_UNDER_SYSTEMATIC_NEGATIVE_EVIDENCE,
        )
        self.assertIsNone(assessment.unknown_reason)

    def test_partial_or_insufficient_business_coverage_fails_closed(self) -> None:
        for coverage in (
            SystematicNegativeEvidenceBusinessCoverage.PARTIAL,
            SystematicNegativeEvidenceBusinessCoverage.INSUFFICIENT,
        ):
            assessment = assess_systematic_negative_evidence_control(_control_input(business_coverage_quality=coverage))

            self.assertFalse(assessment.control_eligibility)
            self.assertEqual(assessment.unknown_reason, "BROAD_BUSINESS_COVERAGE_REQUIRED")

    def test_historical_business_identity_gap_fails_closed(self) -> None:
        assessment = assess_systematic_negative_evidence_control(
            _control_input(historical_business_identity_supported=False)
        )

        self.assertFalse(assessment.control_eligibility)
        self.assertEqual(assessment.unknown_reason, "HISTORICAL_BUSINESS_IDENTITY_NOT_SUPPORTED")

    def test_required_source_not_reviewed_fails_closed(self) -> None:
        reviews = tuple(
            replace(
                review,
                review_state=SystematicNegativeEvidenceSourceReviewState.NOT_REVIEWED,
                publication_date=None,
                publication_date_verified=False,
                supports_broad_business_coverage=False,
            )
            if review.source_class == SystematicNegativeEvidenceSourceClass.INVESTOR_MATERIAL
            else review
            for review in _complete_reviews()
        )
        assessment = assess_systematic_negative_evidence_control(_control_input(source_class_reviews=reviews))

        self.assertFalse(assessment.control_eligibility)
        self.assertEqual(assessment.unknown_reason, "REQUIRED_SOURCE_CLASS_NOT_REVIEWED")

    def test_search_not_found_without_any_eligible_evidence_fails_closed(self) -> None:
        reviews = tuple(
            _review(source_class, SystematicNegativeEvidenceSourceReviewState.SEARCHED_NOT_FOUND)
            for source_class in SystematicNegativeEvidenceSourceClass
        )
        assessment = assess_systematic_negative_evidence_control(_control_input(source_class_reviews=reviews))

        self.assertFalse(assessment.control_eligibility)
        self.assertEqual(assessment.unknown_reason, "AT_LEAST_ONE_ELIGIBLE_SOURCE_REQUIRED")

    def test_unavailable_source_with_audit_reason_can_remain_in_completed_review(self) -> None:
        reviews = tuple(
            _review(
                SystematicNegativeEvidenceSourceClass.INVESTOR_MATERIAL,
                SystematicNegativeEvidenceSourceReviewState.UNAVAILABLE_OR_UNRECOVERABLE,
                audit_reason="archived investor material unavailable before cutoff",
            )
            if review.source_class == SystematicNegativeEvidenceSourceClass.INVESTOR_MATERIAL
            else review
            for review in _complete_reviews()
        )
        assessment = assess_systematic_negative_evidence_control(_control_input(source_class_reviews=reviews))

        self.assertTrue(assessment.control_eligibility)

    def test_multiple_broad_eligible_sources_can_satisfy_route_b_without_comprehensive_report(self) -> None:
        reviews = tuple(
            _review(
                SystematicNegativeEvidenceSourceClass.COMPREHENSIVE_BUSINESS_REPORT,
                SystematicNegativeEvidenceSourceReviewState.SEARCHED_NOT_FOUND,
            )
            if review.source_class == SystematicNegativeEvidenceSourceClass.COMPREHENSIVE_BUSINESS_REPORT
            else review
            for review in _complete_reviews()
        )
        assessment = assess_systematic_negative_evidence_control(_control_input(source_class_reviews=reviews))

        self.assertTrue(assessment.control_eligibility)

    def test_broad_coverage_alone_cannot_bypass_source_review_completeness(self) -> None:
        reviews = tuple(
            _review(source_class, SystematicNegativeEvidenceSourceReviewState.SEARCHED_NOT_FOUND)
            for source_class in SystematicNegativeEvidenceSourceClass
        )
        assessment = assess_systematic_negative_evidence_control(
            _control_input(
                source_class_reviews=reviews,
                business_coverage_quality=SystematicNegativeEvidenceBusinessCoverage.BROAD,
            )
        )

        self.assertFalse(assessment.control_eligibility)
        self.assertEqual(assessment.unknown_reason, "AT_LEAST_ONE_ELIGIBLE_SOURCE_REQUIRED")

    def test_ai_high_or_ai_adjacent_evidence_disqualifies_control(self) -> None:
        cases = (
            (
                "AI_HIGH_EVIDENCE_DISQUALIFIES_CONTROL",
                {"ai_high_evidence_status": SystematicNegativeEvidenceAIStatus.AI_HIGH_EVIDENCE_FOUND},
            ),
            (
                "AI_ADJACENT_EVIDENCE_DISQUALIFIES_CONTROL",
                {"ai_adjacent_evidence_status": SystematicNegativeEvidenceAIStatus.AI_ADJACENT_EVIDENCE_FOUND},
            ),
        )
        for expected_reason, kwargs in cases:
            assessment = assess_systematic_negative_evidence_control(_control_input(**kwargs))

            self.assertFalse(assessment.control_eligibility)
            self.assertEqual(assessment.control_review_state, SystematicNegativeEvidenceControlReviewState.CONTROL_AI_EVIDENCE_FOUND)
            self.assertEqual(assessment.unknown_reason, expected_reason)

    def test_ambiguous_or_incomplete_ai_review_fails_closed(self) -> None:
        cases = (
            (
                "AI_HIGH_REVIEW_NOT_SYSTEMATIC_NEGATIVE",
                {"ai_high_evidence_status": SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_AMBIGUOUS},
            ),
            (
                "AI_HIGH_REVIEW_NOT_SYSTEMATIC_NEGATIVE",
                {"ai_high_evidence_status": SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_REVIEW_INCOMPLETE},
            ),
            (
                "AI_ADJACENT_REVIEW_NOT_SYSTEMATIC_NEGATIVE",
                {"ai_adjacent_evidence_status": SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_AMBIGUOUS},
            ),
            (
                "AI_ADJACENT_REVIEW_NOT_SYSTEMATIC_NEGATIVE",
                {"ai_adjacent_evidence_status": SystematicNegativeEvidenceAIStatus.AI_EVIDENCE_REVIEW_INCOMPLETE},
            ),
        )
        for expected_reason, kwargs in cases:
            assessment = assess_systematic_negative_evidence_control(_control_input(**kwargs))

            self.assertFalse(assessment.control_eligibility)
            self.assertEqual(assessment.unknown_reason, expected_reason)

    def test_ecosystem_ai_evidence_or_ambiguous_review_fails_closed(self) -> None:
        cases = (
            (
                SystematicNegativeEvidenceEcosystemStatus.ELIGIBLE_ECOSYSTEM_AI_EVIDENCE_FOUND,
                "ECOSYSTEM_AI_EVIDENCE_DISQUALIFIES_CONTROL",
            ),
            (
                SystematicNegativeEvidenceEcosystemStatus.ECOSYSTEM_EVIDENCE_AMBIGUOUS,
                "ECOSYSTEM_REVIEW_NOT_SYSTEMATIC_NEGATIVE",
            ),
        )
        for ecosystem_status, expected_reason in cases:
            assessment = assess_systematic_negative_evidence_control(
                _control_input(ecosystem_evidence_status=ecosystem_status)
            )

            self.assertFalse(assessment.control_eligibility)
            self.assertEqual(assessment.unknown_reason, expected_reason)

    def test_conflict_status_fails_closed(self) -> None:
        for conflict_status in (
            SystematicNegativeEvidenceConflictStatus.AI_EVIDENCE_CONFLICT,
            SystematicNegativeEvidenceConflictStatus.UNRESOLVED_EVIDENCE_CONFLICT,
        ):
            assessment = assess_systematic_negative_evidence_control(
                _control_input(conflict_status=conflict_status)
            )

            self.assertFalse(assessment.control_eligibility)
            self.assertEqual(
                assessment.control_review_state,
                SystematicNegativeEvidenceControlReviewState.CONTROL_CONFLICT_FOUND,
            )
            self.assertEqual(assessment.unknown_reason, "UNRESOLVED_OR_AI_EVIDENCE_CONFLICT")

    def test_all_individual_gate_failures_block_eligibility(self) -> None:
        cases = (
            _control_input(historical_business_identity_supported=False),
            _control_input(business_coverage_quality=SystematicNegativeEvidenceBusinessCoverage.PARTIAL),
            _control_input(review_completeness=SystematicNegativeEvidenceReviewCompleteness.CONTROL_REVIEW_INCOMPLETE),
            _control_input(ai_high_evidence_status=SystematicNegativeEvidenceAIStatus.AI_HIGH_EVIDENCE_FOUND),
            _control_input(ai_adjacent_evidence_status=SystematicNegativeEvidenceAIStatus.AI_ADJACENT_EVIDENCE_FOUND),
            _control_input(
                ecosystem_evidence_status=SystematicNegativeEvidenceEcosystemStatus.ELIGIBLE_ECOSYSTEM_AI_EVIDENCE_FOUND
            ),
            _control_input(conflict_status=SystematicNegativeEvidenceConflictStatus.AI_EVIDENCE_CONFLICT),
        )
        for control_input in cases:
            self.assertFalse(assess_systematic_negative_evidence_control(control_input).control_eligibility)

    def test_incomplete_review_state_fails_closed(self) -> None:
        assessment = assess_systematic_negative_evidence_control(
            _control_input(review_completeness=SystematicNegativeEvidenceReviewCompleteness.CONTROL_REVIEW_INCOMPLETE)
        )

        self.assertFalse(assessment.control_eligibility)
        self.assertEqual(assessment.unknown_reason, "CONTROL_REVIEW_COMPLETE_REQUIRED")

    def test_assessment_does_not_create_or_mutate_cohort_labels(self) -> None:
        assessment = assess_systematic_negative_evidence_control(_control_input())

        self.assertFalse(hasattr(assessment, "ai_exposure_category"))
        self.assertFalse(hasattr(assessment, "final_cohort"))
        self.assertFalse(hasattr(assessment, "production_policy"))

    def test_assessment_is_deterministic(self) -> None:
        control_input = _control_input()

        self.assertEqual(
            assess_systematic_negative_evidence_control(control_input),
            assess_systematic_negative_evidence_control(control_input),
        )

    def test_source_module_has_no_holdout_production_or_network_dependency(self) -> None:
        source = inspect.getsource(control_module)

        forbidden_tokens = (
            "Candidate C",
            "HoldoutRegionEvaluator",
            "MAE",
            "risk separation",
            "yfinance",
            "requests",
            "sqlite3",
            "data/production",
            "production_runtime",
            "selected_threshold",
            "selected_candidate",
            "weighted",
            "probability",
            "APPROVED_FOR_USE",
            "PRODUCTION_READY",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
