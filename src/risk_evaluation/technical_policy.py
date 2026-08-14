from dataclasses import dataclass
from decimal import Decimal
from decimal import InvalidOperation
from enum import StrEnum
import hashlib
import json
from types import MappingProxyType
from typing import Iterable
from typing import Mapping

from risk import RiskSeverity
from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_ID
from risk_evaluation.validation import RiskEvaluationPolicyError
from risk_evaluation.validation import require_non_empty_text


PRODUCTION_TECHNICAL_RISK_POLICY_V1 = "PRODUCTION_TECHNICAL_RISK_POLICY_V1"
TECH_RISK_SEVERITY_MAPPING_V1 = "TECH_RISK_SEVERITY_MAPPING_V1"
TECH_RISK_REASON_MAPPING_V1 = "TECH_RISK_REASON_MAPPING_V1"
TECH_RISK_REQUIRED_FEATURE_IDS_V1 = (
    TECH_AS_OF_CLOSE_FEATURE_ID,
    TECH_RSI14_FEATURE_ID,
    TECH_SMA20_FEATURE_ID,
    TECH_SMA60_FEATURE_ID,
)


class ProductionTechnicalRiskPredicateId(StrEnum):
    SHORT_PRICE_WEAKNESS = "SHORT_PRICE_WEAKNESS"
    MEDIUM_PRICE_WEAKNESS = "MEDIUM_PRICE_WEAKNESS"
    TREND_STRUCTURE_WEAKNESS = "TREND_STRUCTURE_WEAKNESS"
    MOMENTUM_WEAKNESS_CONFIRMATION = "MOMENTUM_WEAKNESS_CONFIRMATION"


class ProductionTechnicalRiskThresholdDimensionId(StrEnum):
    CLOSE_VS_SMA20_WEAKNESS_CUTOFF = "close_vs_sma20_weakness_cutoff"
    CLOSE_VS_SMA60_WEAKNESS_CUTOFF = "close_vs_sma60_weakness_cutoff"
    RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF = "relative_sma_spread_weakness_cutoff"
    RSI14_WEAKNESS_CONFIRMATION_CUTOFF = "rsi14_weakness_confirmation_cutoff"


class ProductionTechnicalRiskThresholdOperator(StrEnum):
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"


class ProductionTechnicalRiskReasonCode(StrEnum):
    NO_ELEVATED_TECHNICAL_DOWNSIDE_EVIDENCE = "NO_ELEVATED_TECHNICAL_DOWNSIDE_EVIDENCE"
    PRICE_POSITION_SHORT_TERM_WEAKNESS = "PRICE_POSITION_SHORT_TERM_WEAKNESS"
    PRICE_POSITION_MEDIUM_TERM_WEAKNESS = "PRICE_POSITION_MEDIUM_TERM_WEAKNESS"
    TREND_STRUCTURE_WEAKNESS = "TREND_STRUCTURE_WEAKNESS"
    MOMENTUM_WEAKNESS_CONFIRMATION = "MOMENTUM_WEAKNESS_CONFIRMATION"
    MULTI_EVIDENCE_TECHNICAL_DETERIORATION = "MULTI_EVIDENCE_TECHNICAL_DETERIORATION"


REQUIRED_TECHNICAL_RISK_THRESHOLD_DIMENSIONS_V1 = (
    ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
    ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF,
    ProductionTechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF,
    ProductionTechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF,
)


@dataclass(frozen=True)
class ProductionTechnicalRiskRule:
    rule_id: str
    rule_priority: int
    severity: RiskSeverity | str
    required_predicates: tuple[ProductionTechnicalRiskPredicateId | str, ...]
    optional_confirmation_predicates: tuple[ProductionTechnicalRiskPredicateId | str, ...]
    reason_codes: tuple[ProductionTechnicalRiskReasonCode | str, ...]

    def __post_init__(self):
        require_non_empty_text(self.rule_id, "rule_id", RiskEvaluationPolicyError)
        if not isinstance(self.rule_priority, int) or self.rule_priority <= 0:
            raise RiskEvaluationPolicyError("rule_priority must be a positive integer.")
        severity = _coerce_severity(self.severity)
        if severity == RiskSeverity.CRITICAL:
            raise RiskEvaluationPolicyError("Technical Risk v1 production policy cannot contain CRITICAL severity.")
        required = _normalize_predicates(self.required_predicates)
        optional = _normalize_predicates(self.optional_confirmation_predicates)
        reasons = _normalize_reasons(self.reason_codes)
        if not required:
            raise RiskEvaluationPolicyError("Production technical risk rule requires at least one predicate.")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "required_predicates", required)
        object.__setattr__(self, "optional_confirmation_predicates", optional)
        object.__setattr__(self, "reason_codes", reasons)


@dataclass(frozen=True)
class ProductionTechnicalRiskThresholdDimension:
    dimension_id: ProductionTechnicalRiskThresholdDimensionId | str
    operator: ProductionTechnicalRiskThresholdOperator | str
    canonical_value: Decimal | str

    def __post_init__(self):
        dimension_id = _coerce_dimension(self.dimension_id)
        operator = _coerce_operator(self.operator)
        if operator != ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL:
            raise RiskEvaluationPolicyError("Unsupported Technical Risk threshold operator.")
        value = _canonical_decimal(self.canonical_value)
        object.__setattr__(self, "dimension_id", dimension_id)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "canonical_value", value)

    @property
    def canonical_decimal_string(self) -> str:
        return _canonical_decimal_string(self.canonical_value)


@dataclass(frozen=True)
class ProductionTechnicalRiskPolicy:
    policy_id: str | None
    policy_version: str
    policy_checksum: str | None
    technical_policy_version: str
    source_research_freeze_id: str
    source_research_freeze_checksum: str
    candidate_id: str
    candidate_version: str
    candidate_structural_checksum: str
    rules: tuple[ProductionTechnicalRiskRule, ...]
    threshold_set_id: str
    threshold_set_version: str
    threshold_set_checksum: str
    threshold_dimensions: tuple[ProductionTechnicalRiskThresholdDimension, ...]
    required_feature_ids: tuple[str, ...]
    derived_evidence_version: str
    numeric_context_version: str
    severity_mapping_version: str
    reason_mapping_version: str

    def __post_init__(self):
        require_non_empty_text(self.policy_version, "policy_version", RiskEvaluationPolicyError)
        if self.policy_version != PRODUCTION_TECHNICAL_RISK_POLICY_V1:
            raise RiskEvaluationPolicyError("Unsupported production technical risk policy version.")
        for field_name in (
            "technical_policy_version",
            "source_research_freeze_id",
            "source_research_freeze_checksum",
            "candidate_id",
            "candidate_version",
            "candidate_structural_checksum",
            "threshold_set_id",
            "threshold_set_version",
            "threshold_set_checksum",
            "derived_evidence_version",
            "numeric_context_version",
            "severity_mapping_version",
            "reason_mapping_version",
        ):
            require_non_empty_text(getattr(self, field_name), field_name, RiskEvaluationPolicyError)
        if self.severity_mapping_version != TECH_RISK_SEVERITY_MAPPING_V1:
            raise RiskEvaluationPolicyError("Unsupported Technical Risk severity mapping version.")
        if self.reason_mapping_version != TECH_RISK_REASON_MAPPING_V1:
            raise RiskEvaluationPolicyError("Unsupported Technical Risk reason mapping version.")
        rules = _canonical_rules(self.rules)
        dimensions = _canonical_dimensions(self.threshold_dimensions)
        required_feature_ids = tuple(sorted(self.required_feature_ids))
        if required_feature_ids != TECH_RISK_REQUIRED_FEATURE_IDS_V1:
            raise RiskEvaluationPolicyError("Production Technical Risk v1 requires the exact required feature set.")
        checksum = _policy_checksum(self, rules, dimensions, required_feature_ids)
        identity = _stable_id("production_technical_risk_policy", {"policy_checksum": checksum})
        if self.policy_id is not None and self.policy_id != identity:
            raise RiskEvaluationPolicyError("policy_id mismatch.")
        if self.policy_checksum is not None and self.policy_checksum != checksum:
            raise RiskEvaluationPolicyError("policy_checksum mismatch.")
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "threshold_dimensions", dimensions)
        object.__setattr__(self, "required_feature_ids", required_feature_ids)
        object.__setattr__(self, "policy_id", identity)
        object.__setattr__(self, "policy_checksum", checksum)

    @property
    def threshold_dimensions_by_id(self) -> Mapping[ProductionTechnicalRiskThresholdDimensionId, ProductionTechnicalRiskThresholdDimension]:
        return MappingProxyType({dimension.dimension_id: dimension for dimension in self.threshold_dimensions})


def _canonical_rules(rules: tuple[ProductionTechnicalRiskRule, ...]) -> tuple[ProductionTechnicalRiskRule, ...]:
    if not isinstance(rules, tuple) or not rules:
        raise RiskEvaluationPolicyError("Production Technical Risk policy requires rules.")
    normalized = tuple(rule if isinstance(rule, ProductionTechnicalRiskRule) else ProductionTechnicalRiskRule(**rule) for rule in rules)
    rule_ids = tuple(rule.rule_id for rule in normalized)
    if len(set(rule_ids)) != len(rule_ids):
        raise RiskEvaluationPolicyError("Duplicate production technical risk rule id.")
    priorities = tuple(rule.rule_priority for rule in normalized)
    if len(set(priorities)) != len(priorities):
        raise RiskEvaluationPolicyError("Duplicate production technical risk rule priority.")
    return tuple(sorted(normalized, key=lambda rule: rule.rule_priority))


def _canonical_dimensions(
    dimensions: tuple[ProductionTechnicalRiskThresholdDimension, ...],
) -> tuple[ProductionTechnicalRiskThresholdDimension, ...]:
    if not isinstance(dimensions, tuple):
        raise RiskEvaluationPolicyError("threshold_dimensions must be a tuple.")
    normalized = tuple(
        dimension
        if isinstance(dimension, ProductionTechnicalRiskThresholdDimension)
        else ProductionTechnicalRiskThresholdDimension(**dimension)
        for dimension in dimensions
    )
    dimension_ids = tuple(dimension.dimension_id for dimension in normalized)
    if len(set(dimension_ids)) != len(dimension_ids):
        raise RiskEvaluationPolicyError("Duplicate Technical Risk threshold dimension.")
    if set(dimension_ids) != set(REQUIRED_TECHNICAL_RISK_THRESHOLD_DIMENSIONS_V1):
        raise RiskEvaluationPolicyError("Production Technical Risk policy requires exact threshold dimensions.")
    return tuple(sorted(normalized, key=lambda dimension: dimension.dimension_id.value))


def _normalize_predicates(values: Iterable[ProductionTechnicalRiskPredicateId | str]) -> tuple[ProductionTechnicalRiskPredicateId, ...]:
    predicates = tuple(_coerce_predicate(value) for value in values)
    if len(set(predicates)) != len(predicates):
        raise RiskEvaluationPolicyError("Duplicate Technical Risk predicate.")
    return predicates


def _normalize_reasons(values: Iterable[ProductionTechnicalRiskReasonCode | str]) -> tuple[ProductionTechnicalRiskReasonCode, ...]:
    reasons = tuple(_coerce_reason(value) for value in values)
    if not reasons:
        raise RiskEvaluationPolicyError("Production technical risk rule requires reason codes.")
    if len(set(reasons)) != len(reasons):
        raise RiskEvaluationPolicyError("Duplicate Technical Risk reason code.")
    return reasons


def _coerce_severity(value: RiskSeverity | str) -> RiskSeverity:
    try:
        return RiskSeverity(value)
    except ValueError as exc:
        raise RiskEvaluationPolicyError("Unsupported Technical Risk severity.") from exc


def _coerce_predicate(value: ProductionTechnicalRiskPredicateId | str) -> ProductionTechnicalRiskPredicateId:
    try:
        return value if isinstance(value, ProductionTechnicalRiskPredicateId) else ProductionTechnicalRiskPredicateId(value)
    except ValueError as exc:
        raise RiskEvaluationPolicyError("Unsupported Technical Risk predicate.") from exc


def _coerce_reason(value: ProductionTechnicalRiskReasonCode | str) -> ProductionTechnicalRiskReasonCode:
    try:
        return value if isinstance(value, ProductionTechnicalRiskReasonCode) else ProductionTechnicalRiskReasonCode(value)
    except ValueError as exc:
        raise RiskEvaluationPolicyError("Unsupported Technical Risk reason code.") from exc


def _coerce_dimension(value: ProductionTechnicalRiskThresholdDimensionId | str) -> ProductionTechnicalRiskThresholdDimensionId:
    try:
        return value if isinstance(value, ProductionTechnicalRiskThresholdDimensionId) else ProductionTechnicalRiskThresholdDimensionId(value)
    except ValueError as exc:
        raise RiskEvaluationPolicyError("Unsupported Technical Risk threshold dimension.") from exc


def _coerce_operator(value: ProductionTechnicalRiskThresholdOperator | str) -> ProductionTechnicalRiskThresholdOperator:
    try:
        return value if isinstance(value, ProductionTechnicalRiskThresholdOperator) else ProductionTechnicalRiskThresholdOperator(value)
    except ValueError as exc:
        raise RiskEvaluationPolicyError("Unsupported Technical Risk threshold operator.") from exc


def _canonical_decimal(value: Decimal | str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, str)):
        raise RiskEvaluationPolicyError("Technical Risk threshold value must be Decimal or canonical Decimal string.")
    try:
        candidate = value if isinstance(value, Decimal) else Decimal(value.strip())
    except (AttributeError, InvalidOperation) as exc:
        raise RiskEvaluationPolicyError("Invalid Technical Risk threshold Decimal value.") from exc
    if not candidate.is_finite():
        raise RiskEvaluationPolicyError("Technical Risk threshold Decimal value must be finite.")
    return Decimal(_canonical_decimal_string(candidate))


def _canonical_decimal_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _policy_checksum(
    policy: ProductionTechnicalRiskPolicy,
    rules: tuple[ProductionTechnicalRiskRule, ...],
    dimensions: tuple[ProductionTechnicalRiskThresholdDimension, ...],
    required_feature_ids: tuple[str, ...],
) -> str:
    return _stable_hash(
        {
            "policy_version": policy.policy_version,
            "technical_policy_version": policy.technical_policy_version,
            "source_research_freeze_id": policy.source_research_freeze_id,
            "source_research_freeze_checksum": policy.source_research_freeze_checksum,
            "candidate_id": policy.candidate_id,
            "candidate_version": policy.candidate_version,
            "candidate_structural_checksum": policy.candidate_structural_checksum,
            "rules": [_rule_payload(rule) for rule in rules],
            "threshold_set_id": policy.threshold_set_id,
            "threshold_set_version": policy.threshold_set_version,
            "threshold_set_checksum": policy.threshold_set_checksum,
            "threshold_dimensions": [_threshold_payload(dimension) for dimension in dimensions],
            "required_feature_ids": required_feature_ids,
            "derived_evidence_version": policy.derived_evidence_version,
            "numeric_context_version": policy.numeric_context_version,
            "severity_mapping_version": policy.severity_mapping_version,
            "reason_mapping_version": policy.reason_mapping_version,
            "severity_mapping": {
                "LOW": RiskSeverity.LOW.value,
                "MEDIUM": RiskSeverity.MEDIUM.value,
                "HIGH": RiskSeverity.HIGH.value,
            },
            "reason_vocabulary": sorted(reason.value for reason in ProductionTechnicalRiskReasonCode),
        }
    )


def _rule_payload(rule: ProductionTechnicalRiskRule) -> dict[str, object]:
    return {
        "rule_id": rule.rule_id,
        "rule_priority": rule.rule_priority,
        "severity": rule.severity.value,
        "required_predicates": [predicate.value for predicate in rule.required_predicates],
        "optional_confirmation_predicates": [predicate.value for predicate in rule.optional_confirmation_predicates],
        "reason_codes": [reason.value for reason in rule.reason_codes],
    }


def _threshold_payload(dimension: ProductionTechnicalRiskThresholdDimension) -> dict[str, str]:
    return {
        "dimension_id": dimension.dimension_id.value,
        "operator": dimension.operator.value,
        "canonical_value": dimension.canonical_decimal_string,
    }


def _stable_id(prefix: str, payload: Mapping[str, object]) -> str:
    return f"{prefix}_{_stable_hash(payload)[:16]}"


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return _canonical_decimal_string(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, MappingProxyType):
        return dict(value)
    return value
