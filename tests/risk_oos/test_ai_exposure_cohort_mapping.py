import inspect
import sys
import unittest
from dataclasses import fields
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos
import risk_oos.ai_exposure_cohort_mapping as spec_module
from risk_oos import TECH_RISK_AI_COHORT_DIFFERENCE_IN_DIFFERENCES_STYLE_V1
from risk_oos import TECH_RISK_AI_COHORT_CLASSIFICATION_AS_OF_DATE_SEMANTICS_V1
from risk_oos import TECH_RISK_AI_COHORT_FEATURES_V1
from risk_oos import TECH_RISK_AI_COHORT_POST_HOLDOUT_DIAGNOSTIC
from risk_oos import TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE
from risk_oos import TECH_RISK_AI_COHORT_PRIMARY_COMPARISON_V1
from risk_oos import TECH_RISK_AI_COHORT_REQUIRED_MAPPING_FIELDS_V1
from risk_oos import TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1
from risk_oos import TECH_RISK_TECH_CONTROL_INDUSTRIES_V1
from risk_oos import TechnicalRiskAIExposureCategory
from risk_oos import TechnicalRiskAIExposureCohortMappingError
from risk_oos import TechnicalRiskAIExposureCohortMappingRecord
from risk_oos import TechnicalRiskAIExposureEvidenceSourceType
from risk_oos import TechnicalRiskAIExposureMappingReviewStatus
from risk_oos import build_technical_risk_v1_post_holdout_ai_exposure_cohort_mapping_specification


class TechnicalRiskAIExposureCohortMappingSpecificationTestCase(unittest.TestCase):
    def setUp(self):
        self.specification = build_technical_risk_v1_post_holdout_ai_exposure_cohort_mapping_specification()

    def test_exact_version_scope_and_cutoff(self):
        self.assertEqual(
            self.specification.specification_version,
            TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1,
        )
        self.assertEqual(self.specification.diagnostic_scope, TECH_RISK_AI_COHORT_POST_HOLDOUT_DIAGNOSTIC)
        self.assertEqual(self.specification.classification_cutoff_date, date(2023, 12, 31))
        self.assertEqual(self.specification.classification_cutoff_date, TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE)

    def test_required_cohorts_are_complete_and_unknown_is_preserved(self):
        self.assertEqual(
            self.specification.cohorts,
            (
                TechnicalRiskAIExposureCategory.AI_HIGH,
                TechnicalRiskAIExposureCategory.AI_ADJACENT,
                TechnicalRiskAIExposureCategory.NON_AI_TECH_CONTROL,
                TechnicalRiskAIExposureCategory.NON_TECH_CONTROL,
                TechnicalRiskAIExposureCategory.UNKNOWN,
            ),
        )
        self.assertIn("UNKNOWN", {cohort.value for cohort in self.specification.cohorts})
        self.assertIn("AI_ADJACENT", self.specification.ambiguous_company_policy)
        self.assertIn("UNKNOWN", self.specification.ambiguous_company_policy)

    def test_evidence_hierarchy_is_pre_holdout_and_forbids_performance_evidence(self):
        self.assertEqual(
            self.specification.evidence_hierarchy,
            (
                TechnicalRiskAIExposureEvidenceSourceType.COMPANY_ANNUAL_REPORT,
                TechnicalRiskAIExposureEvidenceSourceType.COMPANY_INVESTOR_PRESENTATION_OR_DISCLOSURE,
                TechnicalRiskAIExposureEvidenceSourceType.EXCHANGE_OR_REGULATORY_INDUSTRY_CLASSIFICATION,
                TechnicalRiskAIExposureEvidenceSourceType.COMPANY_PRODUCT_OR_BUSINESS_DISCLOSURE,
                TechnicalRiskAIExposureEvidenceSourceType.OTHER_EXPLICITLY_APPROVED_SOURCE,
            ),
        )
        forbidden = " ".join(self.specification.forbidden_evidence)
        self.assertIn("2024-2025 stock return", forbidden)
        self.assertIn("technical indicator performance", forbidden)
        self.assertIn("Candidate C performance", forbidden)
        self.assertIn("Holdout risk separation", forbidden)

    def test_mapping_schema_fields_are_fixed_without_populating_mapping(self):
        self.assertEqual(
            self.specification.required_mapping_fields,
            TECH_RISK_AI_COHORT_REQUIRED_MAPPING_FIELDS_V1,
        )
        self.assertEqual(
            tuple(field.name for field in fields(TechnicalRiskAIExposureCohortMappingRecord)),
            TECH_RISK_AI_COHORT_REQUIRED_MAPPING_FIELDS_V1,
        )
        self.assertFalse(self.specification.mapping_population_allowed)

    def test_classification_as_of_date_is_evidence_validity_not_review_execution_date(self):
        self.assertEqual(
            self.specification.classification_as_of_date_semantics,
            TECH_RISK_AI_COHORT_CLASSIFICATION_AS_OF_DATE_SEMANTICS_V1,
        )
        self.assertIn("EVIDENCE_VALIDITY_DATE", self.specification.classification_as_of_date_semantics)
        self.assertIn("NOT_REVIEW_EXECUTION_DATE", self.specification.classification_as_of_date_semantics)

    def test_ai_high_requires_explicit_exposure_and_semiconductor_is_not_enough(self):
        criteria = " ".join(self.specification.ai_high_criteria)
        self.assertIn("AI computing", criteria)
        self.assertIn("AI servers", criteria)
        self.assertIn("data-center infrastructure", criteria)
        self.assertIn("advanced packaging for AI/HPC", criteria)
        self.assertEqual(
            self.specification.semiconductor_policy,
            "Semiconductor or electronics membership alone must not imply AI_HIGH.",
        )

    def test_primary_control_group_is_non_ai_tech_control(self):
        self.assertEqual(self.specification.primary_comparison, TECH_RISK_AI_COHORT_PRIMARY_COMPARISON_V1)
        self.assertEqual(
            self.specification.primary_control_group,
            TechnicalRiskAIExposureCategory.NON_AI_TECH_CONTROL,
        )
        self.assertEqual(
            self.specification.secondary_control_group,
            TechnicalRiskAIExposureCategory.NON_TECH_CONTROL,
        )
        self.assertEqual(self.specification.tech_control_industries, TECH_RISK_TECH_CONTROL_INDUSTRIES_V1)

    def test_future_diagnostic_design_is_descriptive_and_period_locked(self):
        self.assertEqual(self.specification.future_diagnostic_features, TECH_RISK_AI_COHORT_FEATURES_V1)
        self.assertEqual(
            dict(self.specification.future_diagnostic_periods),
            {
                "VALIDATION": (date(2022, 1, 1), date(2023, 12, 31)),
                "HOLDOUT": (date(2024, 1, 1), date(2025, 12, 31)),
            },
        )
        self.assertIn(TECH_RISK_AI_COHORT_DIFFERENCE_IN_DIFFERENCES_STYLE_V1, self.specification.future_comparisons)
        self.assertFalse(self.specification.causal_claim_allowed)

    def test_post_holdout_governance_blocks_v1_retuning_and_production_policy(self):
        self.assertFalse(self.specification.future_returns_allowed_for_classification)
        self.assertFalse(self.specification.retune_v1_allowed)
        self.assertFalse(self.specification.production_policy_allowed)
        with self.assertRaisesRegex(TechnicalRiskAIExposureCohortMappingError, "retune Technical Risk v1"):
            _specification(retune_v1_allowed=True)
        with self.assertRaisesRegex(TechnicalRiskAIExposureCohortMappingError, "production policy"):
            _specification(production_policy_allowed=True)

    def test_mapping_record_rejects_post_cutoff_evidence_dates(self):
        record = _mapping_record()
        self.assertEqual(record.ai_exposure_category, TechnicalRiskAIExposureCategory.AI_ADJACENT)
        self.assertEqual(record.review_status, TechnicalRiskAIExposureMappingReviewStatus.NEEDS_REVIEW)
        with self.assertRaisesRegex(TechnicalRiskAIExposureCohortMappingError, "evidence_publication_date"):
            _mapping_record(evidence_publication_date=date(2024, 1, 2))
        with self.assertRaisesRegex(TechnicalRiskAIExposureCohortMappingError, "classification_as_of_date"):
            _mapping_record(classification_as_of_date=date(2024, 1, 2))

    def test_identity_and_checksum_are_deterministic(self):
        first = build_technical_risk_v1_post_holdout_ai_exposure_cohort_mapping_specification()
        second = build_technical_risk_v1_post_holdout_ai_exposure_cohort_mapping_specification()
        self.assertEqual(first.specification_id, second.specification_id)
        self.assertEqual(first.specification_checksum, second.specification_checksum)
        self.assertRegex(first.specification_id, r"^technical_risk_post_holdout_ai_exposure_cohort_mapping_spec_[0-9a-f]{16}$")
        self.assertRegex(first.specification_checksum, r"^[0-9a-f]{64}$")

    def test_no_evaluation_holdout_fetch_or_production_dependency(self):
        source = inspect.getsource(spec_module)
        forbidden_tokens = (
            "TechnicalRiskHoldoutRegionEvaluator",
            "TechnicalRiskCandidateEvaluator",
            "load_holdout_region_evidence_artifact",
            "sqlite3",
            "yfinance",
            "requests",
            "data/production",
            "production_runtime",
            "selected_threshold",
            "selected_candidate",
            "ranking",
            "score",
        )
        for token in forbidden_tokens:
            self.assertNotIn(token, source)

    def test_public_api_exports_specification_without_executor(self):
        self.assertIn("TechnicalRiskPostHoldoutAIExposureCohortMappingSpecification", risk_oos.__all__)
        self.assertIn(
            "build_technical_risk_v1_post_holdout_ai_exposure_cohort_mapping_specification",
            risk_oos.__all__,
        )
        self.assertNotIn("TechnicalRiskAIExposureCohortEvaluator", risk_oos.__all__)


def _mapping_record(**overrides):
    values = {
        "symbol": "2330.TW",
        "company_name": "Example Co",
        "broad_industry": "Semiconductor",
        "industry_source": "official exchange classification",
        "industry_source_version": "2023",
        "ai_exposure_category": TechnicalRiskAIExposureCategory.AI_ADJACENT,
        "classification_as_of_date": date(2023, 12, 31),
        "evidence_source_type": TechnicalRiskAIExposureEvidenceSourceType.COMPANY_PRODUCT_OR_BUSINESS_DISCLOSURE,
        "evidence_source_reference": "pre-2024 disclosure",
        "evidence_publication_date": date(2023, 12, 30),
        "classification_reason": "Relevant supply-chain disclosure requires reviewer confirmation.",
        "review_status": TechnicalRiskAIExposureMappingReviewStatus.NEEDS_REVIEW,
        "mapping_methodology_version": TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1,
        "source_checksum": "abc123",
    }
    values.update(overrides)
    return TechnicalRiskAIExposureCohortMappingRecord(**values)


def _specification(**overrides):
    base = build_technical_risk_v1_post_holdout_ai_exposure_cohort_mapping_specification()
    values = {
        field.name: getattr(base, field.name)
        for field in fields(type(base))
        if field.name not in {"specification_id", "specification_checksum"}
    }
    values.update(overrides)
    return type(base)(specification_id=None, specification_checksum=None, **values)


if __name__ == "__main__":
    unittest.main()
