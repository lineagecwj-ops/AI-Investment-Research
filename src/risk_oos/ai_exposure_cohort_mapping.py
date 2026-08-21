from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import hashlib
import json
from typing import Mapping


TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1 = (
    "TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1"
)
TECH_RISK_AI_COHORT_POST_HOLDOUT_DIAGNOSTIC = "POST_HOLDOUT_DIAGNOSTIC"
TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE = date(2023, 12, 31)
TECH_RISK_AI_COHORT_CLASSIFICATION_AS_OF_DATE_SEMANTICS_V1 = (
    "CLASSIFICATION_AS_OF_DATE_IS_EVIDENCE_VALIDITY_DATE_NOT_REVIEW_EXECUTION_DATE"
)
TECH_RISK_AI_COHORT_PRIMARY_COMPARISON_V1 = "AI_HIGH_VS_NON_AI_TECH_CONTROL"
TECH_RISK_AI_COHORT_DIFFERENCE_IN_DIFFERENCES_STYLE_V1 = "DESCRIPTIVE_DIFFERENCE_IN_DIFFERENCES_STYLE"

TECH_RISK_AI_COHORT_FEATURES_V1 = (
    "close_vs_sma20",
    "close_vs_sma60",
    "relative_sma_spread",
    "rsi14",
)

TECH_RISK_AI_COHORT_REQUIRED_MAPPING_FIELDS_V1 = (
    "symbol",
    "company_name",
    "broad_industry",
    "industry_source",
    "industry_source_version",
    "ai_exposure_category",
    "classification_as_of_date",
    "evidence_source_type",
    "evidence_source_reference",
    "evidence_publication_date",
    "classification_reason",
    "review_status",
    "mapping_methodology_version",
    "source_checksum",
)

TECH_RISK_AI_HIGH_CRITERIA_V1 = (
    "AI computing",
    "HPC",
    "AI servers",
    "data-center infrastructure",
    "AI accelerators",
    "advanced packaging for AI/HPC",
    "high-speed interconnect directly supporting AI systems",
    "cooling / power infrastructure explicitly serving AI/data centers",
)

TECH_RISK_TECH_CONTROL_INDUSTRIES_V1 = (
    "Semiconductor",
    "Computer & Peripheral Equipment",
    "Electronic Components",
    "Communications / Networking",
    "Other Electronics",
)


class TechnicalRiskAIExposureCohortMappingError(Exception):
    """Raised when AI exposure cohort mapping governance contracts fail closed."""


class TechnicalRiskAIExposureCategory(StrEnum):
    AI_HIGH = "AI_HIGH"
    AI_ADJACENT = "AI_ADJACENT"
    NON_AI_TECH_CONTROL = "NON_AI_TECH_CONTROL"
    NON_TECH_CONTROL = "NON_TECH_CONTROL"
    UNKNOWN = "UNKNOWN"


class TechnicalRiskAIExposureEvidenceSourceType(StrEnum):
    COMPANY_ANNUAL_REPORT = "COMPANY_ANNUAL_REPORT"
    COMPANY_INVESTOR_PRESENTATION_OR_DISCLOSURE = "COMPANY_INVESTOR_PRESENTATION_OR_DISCLOSURE"
    EXCHANGE_OR_REGULATORY_INDUSTRY_CLASSIFICATION = "EXCHANGE_OR_REGULATORY_INDUSTRY_CLASSIFICATION"
    COMPANY_PRODUCT_OR_BUSINESS_DISCLOSURE = "COMPANY_PRODUCT_OR_BUSINESS_DISCLOSURE"
    OTHER_EXPLICITLY_APPROVED_SOURCE = "OTHER_EXPLICITLY_APPROVED_SOURCE"


class TechnicalRiskAIExposureMappingReviewStatus(StrEnum):
    SPECIFICATION_ONLY = "SPECIFICATION_ONLY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REVIEWED = "REVIEWED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TechnicalRiskAIExposureCohortMappingRecord:
    """Future one-symbol mapping record; this Sprint does not populate the 218-symbol mapping.

    classification_as_of_date is the evidence validity date for the primary
    pre-2024 cohort definition, not the analyst's later review execution date.
    """

    symbol: str
    company_name: str
    broad_industry: str
    industry_source: str
    industry_source_version: str
    ai_exposure_category: TechnicalRiskAIExposureCategory | str
    classification_as_of_date: date
    evidence_source_type: TechnicalRiskAIExposureEvidenceSourceType | str
    evidence_source_reference: str
    evidence_publication_date: date
    classification_reason: str
    review_status: TechnicalRiskAIExposureMappingReviewStatus | str
    mapping_methodology_version: str
    source_checksum: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "symbol",
            "company_name",
            "broad_industry",
            "industry_source",
            "industry_source_version",
            "evidence_source_reference",
            "classification_reason",
            "mapping_methodology_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "ai_exposure_category",
            TechnicalRiskAIExposureCategory(self.ai_exposure_category),
        )
        object.__setattr__(
            self,
            "evidence_source_type",
            TechnicalRiskAIExposureEvidenceSourceType(self.evidence_source_type),
        )
        object.__setattr__(
            self,
            "review_status",
            TechnicalRiskAIExposureMappingReviewStatus(self.review_status),
        )
        _require_version(
            self.mapping_methodology_version,
            TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1,
            "mapping_methodology_version",
        )
        if self.classification_as_of_date > TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE:
            raise TechnicalRiskAIExposureCohortMappingError("classification_as_of_date must not exceed cutoff.")
        if self.evidence_publication_date > TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE:
            raise TechnicalRiskAIExposureCohortMappingError("evidence_publication_date must not exceed cutoff.")
        if self.source_checksum is not None:
            _require_text(self.source_checksum, "source_checksum")


@dataclass(frozen=True)
class TechnicalRiskPostHoldoutAIExposureCohortMappingSpecification:
    """Research-governance specification for future AI exposure cohort diagnostics."""

    specification_id: str | None
    specification_version: str
    diagnostic_scope: str
    classification_cutoff_date: date
    cohorts: tuple[TechnicalRiskAIExposureCategory | str, ...]
    primary_comparison: str
    primary_control_group: TechnicalRiskAIExposureCategory | str
    secondary_control_group: TechnicalRiskAIExposureCategory | str
    evidence_hierarchy: tuple[TechnicalRiskAIExposureEvidenceSourceType | str, ...]
    forbidden_evidence: tuple[str, ...]
    required_mapping_fields: tuple[str, ...]
    ai_high_criteria: tuple[str, ...]
    tech_control_industries: tuple[str, ...]
    ambiguous_company_policy: str
    semiconductor_policy: str
    classification_as_of_date_semantics: str
    future_diagnostic_features: tuple[str, ...]
    future_diagnostic_periods: Mapping[str, tuple[date, date]]
    future_comparisons: tuple[str, ...]
    mapping_population_allowed: bool
    future_returns_allowed_for_classification: bool
    retune_v1_allowed: bool
    production_policy_allowed: bool
    causal_claim_allowed: bool
    specification_checksum: str | None = None

    def __post_init__(self) -> None:
        _require_version(
            self.specification_version,
            TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1,
            "specification_version",
        )
        _require_version(self.diagnostic_scope, TECH_RISK_AI_COHORT_POST_HOLDOUT_DIAGNOSTIC, "diagnostic_scope")
        if self.classification_cutoff_date != TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE:
            raise TechnicalRiskAIExposureCohortMappingError("classification_cutoff_date mismatch.")
        cohorts = tuple(TechnicalRiskAIExposureCategory(cohort) for cohort in self.cohorts)
        if cohorts != tuple(TechnicalRiskAIExposureCategory):
            raise TechnicalRiskAIExposureCohortMappingError("cohorts mismatch.")
        object.__setattr__(self, "cohorts", cohorts)
        _require_version(self.primary_comparison, TECH_RISK_AI_COHORT_PRIMARY_COMPARISON_V1, "primary_comparison")
        object.__setattr__(
            self,
            "primary_control_group",
            TechnicalRiskAIExposureCategory(self.primary_control_group),
        )
        if self.primary_control_group != TechnicalRiskAIExposureCategory.NON_AI_TECH_CONTROL:
            raise TechnicalRiskAIExposureCohortMappingError("primary_control_group mismatch.")
        object.__setattr__(
            self,
            "secondary_control_group",
            TechnicalRiskAIExposureCategory(self.secondary_control_group),
        )
        if self.secondary_control_group != TechnicalRiskAIExposureCategory.NON_TECH_CONTROL:
            raise TechnicalRiskAIExposureCohortMappingError("secondary_control_group mismatch.")
        evidence_hierarchy = tuple(
            TechnicalRiskAIExposureEvidenceSourceType(source_type) for source_type in self.evidence_hierarchy
        )
        if evidence_hierarchy != tuple(TechnicalRiskAIExposureEvidenceSourceType):
            raise TechnicalRiskAIExposureCohortMappingError("evidence_hierarchy mismatch.")
        object.__setattr__(self, "evidence_hierarchy", evidence_hierarchy)
        if tuple(self.required_mapping_fields) != TECH_RISK_AI_COHORT_REQUIRED_MAPPING_FIELDS_V1:
            raise TechnicalRiskAIExposureCohortMappingError("required_mapping_fields mismatch.")
        if tuple(self.ai_high_criteria) != TECH_RISK_AI_HIGH_CRITERIA_V1:
            raise TechnicalRiskAIExposureCohortMappingError("ai_high_criteria mismatch.")
        if tuple(self.tech_control_industries) != TECH_RISK_TECH_CONTROL_INDUSTRIES_V1:
            raise TechnicalRiskAIExposureCohortMappingError("tech_control_industries mismatch.")
        _require_text(self.ambiguous_company_policy, "ambiguous_company_policy")
        _require_text(self.semiconductor_policy, "semiconductor_policy")
        _require_version(
            self.classification_as_of_date_semantics,
            TECH_RISK_AI_COHORT_CLASSIFICATION_AS_OF_DATE_SEMANTICS_V1,
            "classification_as_of_date_semantics",
        )
        if tuple(self.future_diagnostic_features) != TECH_RISK_AI_COHORT_FEATURES_V1:
            raise TechnicalRiskAIExposureCohortMappingError("future_diagnostic_features mismatch.")
        _require_periods(self.future_diagnostic_periods)
        _require_future_comparisons(self.future_comparisons)
        if self.mapping_population_allowed:
            raise TechnicalRiskAIExposureCohortMappingError("This Sprint must not populate the 218-symbol mapping.")
        if self.future_returns_allowed_for_classification:
            raise TechnicalRiskAIExposureCohortMappingError("Future returns must not classify cohorts.")
        if self.retune_v1_allowed:
            raise TechnicalRiskAIExposureCohortMappingError("Post-Holdout diagnostics must not retune Technical Risk v1.")
        if self.production_policy_allowed:
            raise TechnicalRiskAIExposureCohortMappingError("This specification must not create production policy.")
        if self.causal_claim_allowed:
            raise TechnicalRiskAIExposureCohortMappingError("This specification supports association analysis only.")
        checksum = _specification_checksum(self)
        identity = _stable_id("technical_risk_post_holdout_ai_exposure_cohort_mapping_spec", {"checksum": checksum})
        if self.specification_id is not None and self.specification_id != identity:
            raise TechnicalRiskAIExposureCohortMappingError("specification_id mismatch.")
        if self.specification_checksum is not None and self.specification_checksum != checksum:
            raise TechnicalRiskAIExposureCohortMappingError("specification_checksum mismatch.")
        object.__setattr__(self, "specification_id", identity)
        object.__setattr__(self, "specification_checksum", checksum)


def build_technical_risk_v1_post_holdout_ai_exposure_cohort_mapping_specification() -> (
    TechnicalRiskPostHoldoutAIExposureCohortMappingSpecification
):
    return TechnicalRiskPostHoldoutAIExposureCohortMappingSpecification(
        specification_id=None,
        specification_version=TECH_RISK_POST_HOLDOUT_AI_EXPOSURE_COHORT_MAPPING_SPEC_V1,
        diagnostic_scope=TECH_RISK_AI_COHORT_POST_HOLDOUT_DIAGNOSTIC,
        classification_cutoff_date=TECH_RISK_AI_COHORT_PRE_HOLDOUT_CUTOFF_DATE,
        cohorts=tuple(TechnicalRiskAIExposureCategory),
        primary_comparison=TECH_RISK_AI_COHORT_PRIMARY_COMPARISON_V1,
        primary_control_group=TechnicalRiskAIExposureCategory.NON_AI_TECH_CONTROL,
        secondary_control_group=TechnicalRiskAIExposureCategory.NON_TECH_CONTROL,
        evidence_hierarchy=tuple(TechnicalRiskAIExposureEvidenceSourceType),
        forbidden_evidence=(
            "2024-2025 stock return",
            "technical indicator performance",
            "Candidate C performance",
            "Holdout risk separation",
            "analyst classification created after observing Holdout results",
        ),
        required_mapping_fields=TECH_RISK_AI_COHORT_REQUIRED_MAPPING_FIELDS_V1,
        ai_high_criteria=TECH_RISK_AI_HIGH_CRITERIA_V1,
        tech_control_industries=TECH_RISK_TECH_CONTROL_INDUSTRIES_V1,
        ambiguous_company_policy="Prefer AI_ADJACENT or UNKNOWN over forced AI_HIGH classification.",
        semiconductor_policy="Semiconductor or electronics membership alone must not imply AI_HIGH.",
        classification_as_of_date_semantics=TECH_RISK_AI_COHORT_CLASSIFICATION_AS_OF_DATE_SEMANTICS_V1,
        future_diagnostic_features=TECH_RISK_AI_COHORT_FEATURES_V1,
        future_diagnostic_periods={
            "VALIDATION": (date(2022, 1, 1), date(2023, 12, 31)),
            "HOLDOUT": (date(2024, 1, 1), date(2025, 12, 31)),
        },
        future_comparisons=(
            "technical_feature_shift",
            "market_breadth_shift",
            "candidate_c_risk_separation_shift",
            "candidate_c_monotonicity_shift",
            TECH_RISK_AI_COHORT_DIFFERENCE_IN_DIFFERENCES_STYLE_V1,
        ),
        mapping_population_allowed=False,
        future_returns_allowed_for_classification=False,
        retune_v1_allowed=False,
        production_policy_allowed=False,
        causal_claim_allowed=False,
    )


def _specification_checksum(specification: TechnicalRiskPostHoldoutAIExposureCohortMappingSpecification) -> str:
    return _stable_hash(
        {
            "specification_version": specification.specification_version,
            "diagnostic_scope": specification.diagnostic_scope,
            "classification_cutoff_date": specification.classification_cutoff_date.isoformat(),
            "cohorts": tuple(cohort.value for cohort in specification.cohorts),
            "primary_comparison": specification.primary_comparison,
            "primary_control_group": specification.primary_control_group.value,
            "secondary_control_group": specification.secondary_control_group.value,
            "evidence_hierarchy": tuple(source_type.value for source_type in specification.evidence_hierarchy),
            "forbidden_evidence": specification.forbidden_evidence,
            "required_mapping_fields": specification.required_mapping_fields,
            "ai_high_criteria": specification.ai_high_criteria,
            "tech_control_industries": specification.tech_control_industries,
            "ambiguous_company_policy": specification.ambiguous_company_policy,
            "semiconductor_policy": specification.semiconductor_policy,
            "classification_as_of_date_semantics": specification.classification_as_of_date_semantics,
            "future_diagnostic_features": specification.future_diagnostic_features,
            "future_diagnostic_periods": {
                name: (period[0].isoformat(), period[1].isoformat())
                for name, period in sorted(specification.future_diagnostic_periods.items())
            },
            "future_comparisons": specification.future_comparisons,
            "mapping_population_allowed": specification.mapping_population_allowed,
            "future_returns_allowed_for_classification": specification.future_returns_allowed_for_classification,
            "retune_v1_allowed": specification.retune_v1_allowed,
            "production_policy_allowed": specification.production_policy_allowed,
            "causal_claim_allowed": specification.causal_claim_allowed,
        }
    )


def _require_periods(periods: Mapping[str, tuple[date, date]]) -> None:
    expected = {
        "VALIDATION": (date(2022, 1, 1), date(2023, 12, 31)),
        "HOLDOUT": (date(2024, 1, 1), date(2025, 12, 31)),
    }
    if dict(periods) != expected:
        raise TechnicalRiskAIExposureCohortMappingError("future_diagnostic_periods mismatch.")


def _require_future_comparisons(comparisons: tuple[str, ...]) -> None:
    expected = (
        "technical_feature_shift",
        "market_breadth_shift",
        "candidate_c_risk_separation_shift",
        "candidate_c_monotonicity_shift",
        TECH_RISK_AI_COHORT_DIFFERENCE_IN_DIFFERENCES_STYLE_V1,
    )
    if tuple(comparisons) != expected:
        raise TechnicalRiskAIExposureCohortMappingError("future_comparisons mismatch.")


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskAIExposureCohortMappingError(f"{field_name} must be a non-empty string.")


def _require_version(value: str, expected: str, field_name: str) -> None:
    if value != expected:
        raise TechnicalRiskAIExposureCohortMappingError(f"{field_name} mismatch.")
