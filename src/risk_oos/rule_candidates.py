from dataclasses import dataclass
from decimal import Context
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_EVEN
from decimal import localcontext
from enum import StrEnum
import hashlib
import json
from numbers import Real
from types import MappingProxyType
from typing import Iterable
from typing import Mapping

from risk_oos.aligned_dataset import AlignedTechnicalRiskOOSRow
from risk_oos.historical_features import HISTORICAL_RISK_FEATURE_SET_V1


TECH_RISK_DERIVED_EVIDENCE_V1 = "TECH_RISK_DERIVED_EVIDENCE_V1"
TECH_RISK_NUMERIC_REPRESENTATION_V1 = "TECH_RISK_DECIMAL_CANONICAL_V1"
TECH_RISK_DECIMAL_CONTEXT_V1 = "TECH_RISK_DECIMAL_CONTEXT_V1"
TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1 = 34
TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1 = ROUND_HALF_EVEN
TECH_RISK_TRIGGER_VOCABULARY_V1 = "TECH_RISK_TRIGGER_VOCABULARY_V1"
TECH_RISK_EVIDENCE_VOCABULARY_V1 = "TECH_RISK_EVIDENCE_VOCABULARY_V1"

FIXED_TECH_RISK_DECIMAL_CONTEXT = Context(
    prec=TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1,
    rounding=TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1,
)


class TechnicalRiskRuleCandidateError(Exception):
    """Raised when Technical Risk rule candidate contracts are invalid."""


class TechnicalRiskCandidateSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TechnicalRiskCandidateFamily(StrEnum):
    MEDIUM_TERM_TREND_CENTRIC = "MEDIUM_TERM_TREND_CENTRIC"
    STRUCTURE_FIRST = "STRUCTURE_FIRST"
    EARLY_WARNING_WITH_GUARDRAIL = "EARLY_WARNING_WITH_GUARDRAIL"
    STRICT_MULTI_EVIDENCE = "STRICT_MULTI_EVIDENCE"


class TechnicalRiskPredicateId(StrEnum):
    SHORT_PRICE_WEAKNESS = "SHORT_PRICE_WEAKNESS"
    MEDIUM_PRICE_WEAKNESS = "MEDIUM_PRICE_WEAKNESS"
    TREND_STRUCTURE_WEAKNESS = "TREND_STRUCTURE_WEAKNESS"
    MOMENTUM_WEAKNESS_CONFIRMATION = "MOMENTUM_WEAKNESS_CONFIRMATION"


class TechnicalRiskReasonCode(StrEnum):
    PRICE_POSITION_SHORT_TERM_WEAKNESS = "PRICE_POSITION_SHORT_TERM_WEAKNESS"
    PRICE_POSITION_MEDIUM_TERM_WEAKNESS = "PRICE_POSITION_MEDIUM_TERM_WEAKNESS"
    TREND_STRUCTURE_WEAKNESS = "TREND_STRUCTURE_WEAKNESS"
    MOMENTUM_WEAKNESS_CONFIRMATION = "MOMENTUM_WEAKNESS_CONFIRMATION"
    MULTI_EVIDENCE_TECHNICAL_DETERIORATION = "MULTI_EVIDENCE_TECHNICAL_DETERIORATION"


class TechnicalRiskThresholdDimensionId(StrEnum):
    CLOSE_VS_SMA20_WEAKNESS_CUTOFF = "close_vs_sma20_weakness_cutoff"
    CLOSE_VS_SMA60_WEAKNESS_CUTOFF = "close_vs_sma60_weakness_cutoff"
    RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF = "relative_sma_spread_weakness_cutoff"
    RSI14_WEAKNESS_CONFIRMATION_CUTOFF = "rsi14_weakness_confirmation_cutoff"


class TechnicalRiskThresholdOperator(StrEnum):
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"


REQUIRED_THRESHOLD_DIMENSIONS_V1 = (
    TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF,
    TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF,
)

ALLOWED_CANDIDATE_SEVERITIES_V1 = (
    TechnicalRiskCandidateSeverity.LOW,
    TechnicalRiskCandidateSeverity.MEDIUM,
    TechnicalRiskCandidateSeverity.HIGH,
)

ALLOWED_PREDICATES_V1 = tuple(TechnicalRiskPredicateId)


@dataclass(frozen=True)
class TechnicalRiskDerivedEvidence:
    """Deterministic current-state technical evidence derived from an aligned OOS row."""

    derived_evidence_version: str
    close_vs_sma20: Decimal
    close_vs_sma60: Decimal
    relative_sma_spread: Decimal

    def __post_init__(self):
        if self.derived_evidence_version != TECH_RISK_DERIVED_EVIDENCE_V1:
            raise TechnicalRiskRuleCandidateError("Unsupported derived evidence version.")
        object.__setattr__(self, "close_vs_sma20", _canonical_decimal(self.close_vs_sma20))
        object.__setattr__(self, "close_vs_sma60", _canonical_decimal(self.close_vs_sma60))
        object.__setattr__(self, "relative_sma_spread", _canonical_decimal(self.relative_sma_spread))


@dataclass(frozen=True)
class TechnicalRiskThresholdDimension:
    """One canonical Decimal threshold dimension for Technical Risk v1 predicates."""

    dimension_id: TechnicalRiskThresholdDimensionId
    operator: TechnicalRiskThresholdOperator
    canonical_value: str

    def __post_init__(self):
        if not isinstance(self.dimension_id, TechnicalRiskThresholdDimensionId):
            object.__setattr__(
                self,
                "dimension_id",
                _coerce_threshold_dimension_id(self.dimension_id),
            )
        if not isinstance(self.operator, TechnicalRiskThresholdOperator):
            object.__setattr__(self, "operator", _coerce_threshold_operator(self.operator))
        if self.operator != TechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL:
            raise TechnicalRiskRuleCandidateError("Unsupported threshold operator.")
        object.__setattr__(self, "canonical_value", _canonical_decimal_string(self.canonical_value))

    @property
    def decimal_value(self) -> Decimal:
        return Decimal(self.canonical_value)


@dataclass(frozen=True)
class TechnicalRiskThresholdSet:
    """Complete four-dimensional frozen threshold set for fair candidate comparison."""

    threshold_set_id: str
    threshold_set_version: str
    numeric_representation_version: str
    dimensions: tuple[TechnicalRiskThresholdDimension, ...]
    compatible_candidate_families: tuple[TechnicalRiskCandidateFamily, ...]
    threshold_set_checksum: str | None = None

    def __post_init__(self):
        _require_text(self.threshold_set_id, "threshold_set_id")
        _require_text(self.threshold_set_version, "threshold_set_version")
        if self.numeric_representation_version != TECH_RISK_NUMERIC_REPRESENTATION_V1:
            raise TechnicalRiskRuleCandidateError("Unsupported numeric representation version.")
        dimensions = tuple(self.dimensions)
        object.__setattr__(self, "dimensions", dimensions)
        _validate_threshold_dimensions(dimensions)
        families = tuple(
            family if isinstance(family, TechnicalRiskCandidateFamily) else TechnicalRiskCandidateFamily(family)
            for family in self.compatible_candidate_families
        )
        if not families:
            raise TechnicalRiskRuleCandidateError("compatible_candidate_families must not be empty.")
        object.__setattr__(self, "compatible_candidate_families", families)
        checksum = _threshold_set_checksum(self)
        if self.threshold_set_checksum is not None and self.threshold_set_checksum != checksum:
            raise TechnicalRiskRuleCandidateError("threshold_set_checksum mismatch.")
        object.__setattr__(self, "threshold_set_checksum", checksum)

    @property
    def dimensions_by_id(self) -> Mapping[TechnicalRiskThresholdDimensionId, TechnicalRiskThresholdDimension]:
        return MappingProxyType({dimension.dimension_id: dimension for dimension in self.dimensions})


@dataclass(frozen=True)
class TechnicalRiskPredicateState:
    """Deterministic TRUE/FALSE output for one evidence predicate."""

    predicate_id: TechnicalRiskPredicateId
    is_triggered: bool

    def __post_init__(self):
        if not isinstance(self.predicate_id, TechnicalRiskPredicateId):
            object.__setattr__(self, "predicate_id", _coerce_predicate_id(self.predicate_id))
        if not isinstance(self.is_triggered, bool):
            raise TechnicalRiskRuleCandidateError("predicate state must be boolean.")


@dataclass(frozen=True)
class TechnicalRiskCandidateRule:
    """One deterministic rule in a candidate hierarchy."""

    rule_id: str
    severity: TechnicalRiskCandidateSeverity
    required_predicates: tuple[TechnicalRiskPredicateId, ...]
    optional_confirmation_predicates: tuple[TechnicalRiskPredicateId, ...]
    rule_priority: int
    reason_codes: tuple[TechnicalRiskReasonCode, ...]

    def __post_init__(self):
        _require_text(self.rule_id, "rule_id")
        if not isinstance(self.severity, TechnicalRiskCandidateSeverity):
            object.__setattr__(self, "severity", _coerce_candidate_severity(self.severity))
        required = _normalize_predicates(self.required_predicates)
        optional = _normalize_predicates(self.optional_confirmation_predicates)
        reasons = _normalize_reasons(self.reason_codes)
        if self.rule_priority <= 0:
            raise TechnicalRiskRuleCandidateError("rule_priority must be positive.")
        if self.severity == TechnicalRiskCandidateSeverity.LOW:
            raise TechnicalRiskRuleCandidateError("LOW is implicit and must not be represented as a candidate rule.")
        if not required:
            raise TechnicalRiskRuleCandidateError("Candidate rule requires at least one predicate.")
        object.__setattr__(self, "required_predicates", required)
        object.__setattr__(self, "optional_confirmation_predicates", optional)
        object.__setattr__(self, "reason_codes", reasons)


@dataclass(frozen=True)
class TechnicalRiskRuleCandidateSpec:
    """Threshold-independent structural identity for a Technical Risk rule candidate."""

    policy_candidate_id: str
    candidate_version: str
    candidate_family: TechnicalRiskCandidateFamily
    rule_hierarchy_id: str
    required_feature_ids: tuple[str, ...]
    derived_evidence_version: str
    allowed_predicate_ids: tuple[TechnicalRiskPredicateId, ...]
    allowed_severities: tuple[TechnicalRiskCandidateSeverity, ...]
    trigger_vocabulary_version: str
    evidence_vocabulary_version: str
    rules: tuple[TechnicalRiskCandidateRule, ...]
    candidate_structural_checksum: str | None = None

    def __post_init__(self):
        _require_text(self.policy_candidate_id, "policy_candidate_id")
        _require_text(self.candidate_version, "candidate_version")
        _require_text(self.rule_hierarchy_id, "rule_hierarchy_id")
        if not isinstance(self.candidate_family, TechnicalRiskCandidateFamily):
            object.__setattr__(self, "candidate_family", _coerce_candidate_family(self.candidate_family))
        if tuple(self.required_feature_ids) != HISTORICAL_RISK_FEATURE_SET_V1:
            raise TechnicalRiskRuleCandidateError("Technical Risk v1 candidate requires the exact feature set.")
        if self.derived_evidence_version != TECH_RISK_DERIVED_EVIDENCE_V1:
            raise TechnicalRiskRuleCandidateError("Unsupported derived evidence version.")
        if self.trigger_vocabulary_version != TECH_RISK_TRIGGER_VOCABULARY_V1:
            raise TechnicalRiskRuleCandidateError("Unsupported trigger vocabulary version.")
        if self.evidence_vocabulary_version != TECH_RISK_EVIDENCE_VOCABULARY_V1:
            raise TechnicalRiskRuleCandidateError("Unsupported evidence vocabulary version.")
        predicates = _normalize_predicates(self.allowed_predicate_ids)
        severities = _normalize_severities(self.allowed_severities)
        rules = tuple(self.rules)
        _validate_candidate_rules(rules, predicates, severities)
        object.__setattr__(self, "allowed_predicate_ids", predicates)
        object.__setattr__(self, "allowed_severities", severities)
        object.__setattr__(self, "rules", rules)
        checksum = _candidate_structural_checksum(self)
        if self.candidate_structural_checksum is not None and self.candidate_structural_checksum != checksum:
            raise TechnicalRiskRuleCandidateError("candidate_structural_checksum mismatch.")
        object.__setattr__(self, "candidate_structural_checksum", checksum)


def derive_technical_risk_evidence(row: AlignedTechnicalRiskOOSRow) -> TechnicalRiskDerivedEvidence:
    as_of_close = _canonical_decimal(row.as_of_close)
    sma20 = _canonical_decimal(row.sma20)
    sma60 = _canonical_decimal(row.sma60)
    if sma20 <= 0:
        raise TechnicalRiskRuleCandidateError("sma20 must be positive for derived evidence.")
    if sma60 <= 0:
        raise TechnicalRiskRuleCandidateError("sma60 must be positive for derived evidence.")
    with localcontext(FIXED_TECH_RISK_DECIMAL_CONTEXT):
        close_vs_sma20 = (as_of_close - sma20) / sma20
        close_vs_sma60 = (as_of_close - sma60) / sma60
        relative_sma_spread = (sma20 - sma60) / sma60
    return TechnicalRiskDerivedEvidence(
        derived_evidence_version=TECH_RISK_DERIVED_EVIDENCE_V1,
        close_vs_sma20=close_vs_sma20,
        close_vs_sma60=close_vs_sma60,
        relative_sma_spread=relative_sma_spread,
    )


def evaluate_technical_risk_predicates(
    evidence: TechnicalRiskDerivedEvidence,
    rsi14: object,
    threshold_set: TechnicalRiskThresholdSet,
) -> tuple[TechnicalRiskPredicateState, ...]:
    thresholds = threshold_set.dimensions_by_id
    rsi = _canonical_decimal(rsi14)
    return (
        TechnicalRiskPredicateState(
            TechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,
            evidence.close_vs_sma20 <= thresholds[TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF].decimal_value,
        ),
        TechnicalRiskPredicateState(
            TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
            evidence.close_vs_sma60 <= thresholds[TechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF].decimal_value,
        ),
        TechnicalRiskPredicateState(
            TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
            evidence.relative_sma_spread <= thresholds[TechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF].decimal_value,
        ),
        TechnicalRiskPredicateState(
            TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
            rsi <= thresholds[TechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF].decimal_value,
        ),
    )


def technical_risk_candidate_a_spec() -> TechnicalRiskRuleCandidateSpec:
    return _candidate_spec(
        policy_candidate_id="TECH_POLICY_CANDIDATE_A",
        family=TechnicalRiskCandidateFamily.MEDIUM_TERM_TREND_CENTRIC,
        hierarchy_id="medium_term_trend_centric_hierarchy_v1",
        rules=(
            TechnicalRiskCandidateRule(
                "A_HIGH_MULTI_EVIDENCE",
                TechnicalRiskCandidateSeverity.HIGH,
                (
                    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                ),
                (),
                10,
                (
                    TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,
                    TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskReasonCode.MOMENTUM_WEAKNESS_CONFIRMATION,
                    TechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,
                ),
            ),
            TechnicalRiskCandidateRule(
                "A_MEDIUM_MEDIUM_PRICE_WEAKNESS",
                TechnicalRiskCandidateSeverity.MEDIUM,
                (TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,),
                (
                    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                ),
                20,
                (TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,),
            ),
        ),
    )


def technical_risk_candidate_b_spec() -> TechnicalRiskRuleCandidateSpec:
    return _candidate_spec(
        policy_candidate_id="TECH_POLICY_CANDIDATE_B",
        family=TechnicalRiskCandidateFamily.STRUCTURE_FIRST,
        hierarchy_id="structure_first_hierarchy_v1",
        rules=(
            TechnicalRiskCandidateRule(
                "B_HIGH_STRUCTURE_WITH_CONFIRMATION",
                TechnicalRiskCandidateSeverity.HIGH,
                (
                    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                ),
                (),
                10,
                (
                    TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,
                    TechnicalRiskReasonCode.MOMENTUM_WEAKNESS_CONFIRMATION,
                    TechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,
                ),
            ),
            TechnicalRiskCandidateRule(
                "B_MEDIUM_TREND_STRUCTURE_WEAKNESS",
                TechnicalRiskCandidateSeverity.MEDIUM,
                (TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,),
                (
                    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                ),
                20,
                (TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS,),
            ),
        ),
    )


def technical_risk_candidate_c_spec() -> TechnicalRiskRuleCandidateSpec:
    return _candidate_spec(
        policy_candidate_id="TECH_POLICY_CANDIDATE_C",
        family=TechnicalRiskCandidateFamily.EARLY_WARNING_WITH_GUARDRAIL,
        hierarchy_id="early_warning_with_guardrail_hierarchy_v1",
        rules=(
            TechnicalRiskCandidateRule(
                "C_HIGH_PRIMARY_WITH_MOMENTUM",
                TechnicalRiskCandidateSeverity.HIGH,
                (
                    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                ),
                (TechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,),
                10,
                (
                    TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,
                    TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskReasonCode.MOMENTUM_WEAKNESS_CONFIRMATION,
                    TechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,
                ),
            ),
            TechnicalRiskCandidateRule(
                "C_MEDIUM_PRIMARY_PARTIAL",
                TechnicalRiskCandidateSeverity.MEDIUM,
                (
                    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                ),
                (TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,),
                20,
                (
                    TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,
                    TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS,
                ),
            ),
            TechnicalRiskCandidateRule(
                "C_MEDIUM_SHORT_PRICE_EARLY_WARNING",
                TechnicalRiskCandidateSeverity.MEDIUM,
                (TechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS,),
                (),
                30,
                (TechnicalRiskReasonCode.PRICE_POSITION_SHORT_TERM_WEAKNESS,),
            ),
        ),
    )


def technical_risk_candidate_d_spec() -> TechnicalRiskRuleCandidateSpec:
    return _candidate_spec(
        policy_candidate_id="TECH_POLICY_CANDIDATE_D",
        family=TechnicalRiskCandidateFamily.STRICT_MULTI_EVIDENCE,
        hierarchy_id="strict_multi_evidence_hierarchy_v1",
        rules=(
            TechnicalRiskCandidateRule(
                "D_HIGH_STRICT_MULTI_EVIDENCE",
                TechnicalRiskCandidateSeverity.HIGH,
                (
                    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION,
                ),
                (),
                10,
                (
                    TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,
                    TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS,
                    TechnicalRiskReasonCode.MOMENTUM_WEAKNESS_CONFIRMATION,
                    TechnicalRiskReasonCode.MULTI_EVIDENCE_TECHNICAL_DETERIORATION,
                ),
            ),
            TechnicalRiskCandidateRule(
                "D_MEDIUM_PARTIAL_PRIMARY_EVIDENCE",
                TechnicalRiskCandidateSeverity.MEDIUM,
                (
                    TechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS,
                    TechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS,
                ),
                (),
                20,
                (
                    TechnicalRiskReasonCode.PRICE_POSITION_MEDIUM_TERM_WEAKNESS,
                    TechnicalRiskReasonCode.TREND_STRUCTURE_WEAKNESS,
                ),
            ),
        ),
    )


def _candidate_spec(
    *,
    policy_candidate_id: str,
    family: TechnicalRiskCandidateFamily,
    hierarchy_id: str,
    rules: tuple[TechnicalRiskCandidateRule, ...],
) -> TechnicalRiskRuleCandidateSpec:
    return TechnicalRiskRuleCandidateSpec(
        policy_candidate_id=policy_candidate_id,
        candidate_version="v1",
        candidate_family=family,
        rule_hierarchy_id=hierarchy_id,
        required_feature_ids=HISTORICAL_RISK_FEATURE_SET_V1,
        derived_evidence_version=TECH_RISK_DERIVED_EVIDENCE_V1,
        allowed_predicate_ids=ALLOWED_PREDICATES_V1,
        allowed_severities=ALLOWED_CANDIDATE_SEVERITIES_V1,
        trigger_vocabulary_version=TECH_RISK_TRIGGER_VOCABULARY_V1,
        evidence_vocabulary_version=TECH_RISK_EVIDENCE_VOCABULARY_V1,
        rules=rules,
    )


def _validate_threshold_dimensions(dimensions: tuple[TechnicalRiskThresholdDimension, ...]) -> None:
    dimension_ids = tuple(dimension.dimension_id for dimension in dimensions)
    if len(set(dimension_ids)) != len(dimension_ids):
        raise TechnicalRiskRuleCandidateError("Duplicate threshold dimension.")
    if set(dimension_ids) != set(REQUIRED_THRESHOLD_DIMENSIONS_V1):
        raise TechnicalRiskRuleCandidateError("Threshold set must contain exact Technical Risk v1 dimensions.")


def _validate_candidate_rules(
    rules: tuple[TechnicalRiskCandidateRule, ...],
    allowed_predicates: tuple[TechnicalRiskPredicateId, ...],
    allowed_severities: tuple[TechnicalRiskCandidateSeverity, ...],
) -> None:
    if not rules:
        raise TechnicalRiskRuleCandidateError("Candidate requires at least one rule.")
    rule_ids = tuple(rule.rule_id for rule in rules)
    if len(set(rule_ids)) != len(rule_ids):
        raise TechnicalRiskRuleCandidateError("Duplicate candidate rule id.")
    priorities = tuple(rule.rule_priority for rule in rules)
    if len(set(priorities)) != len(priorities):
        raise TechnicalRiskRuleCandidateError("Duplicate rule priority creates ambiguous hierarchy.")
    allowed_predicate_set = set(allowed_predicates)
    allowed_severity_set = set(allowed_severities)
    if TechnicalRiskCandidateSeverity.HIGH not in allowed_severity_set or TechnicalRiskCandidateSeverity.MEDIUM not in allowed_severity_set:
        raise TechnicalRiskRuleCandidateError("Candidate must allow MEDIUM and HIGH severities.")
    for rule in rules:
        if rule.severity not in allowed_severity_set:
            raise TechnicalRiskRuleCandidateError("Rule severity is not allowed.")
        for predicate in (*rule.required_predicates, *rule.optional_confirmation_predicates):
            if predicate not in allowed_predicate_set:
                raise TechnicalRiskRuleCandidateError("Unsupported predicate in candidate rule.")


def _normalize_predicates(values: Iterable[TechnicalRiskPredicateId]) -> tuple[TechnicalRiskPredicateId, ...]:
    predicates = tuple(value if isinstance(value, TechnicalRiskPredicateId) else _coerce_predicate_id(value) for value in values)
    if len(set(predicates)) != len(predicates):
        raise TechnicalRiskRuleCandidateError("Duplicate predicate identity.")
    return predicates


def _normalize_reasons(values: Iterable[TechnicalRiskReasonCode]) -> tuple[TechnicalRiskReasonCode, ...]:
    reasons = tuple(value if isinstance(value, TechnicalRiskReasonCode) else _coerce_reason_code(value) for value in values)
    if not reasons:
        raise TechnicalRiskRuleCandidateError("Candidate rule requires reason codes.")
    if len(set(reasons)) != len(reasons):
        raise TechnicalRiskRuleCandidateError("Duplicate reason code.")
    return reasons


def _normalize_severities(values: Iterable[TechnicalRiskCandidateSeverity]) -> tuple[TechnicalRiskCandidateSeverity, ...]:
    severities = tuple(
        value if isinstance(value, TechnicalRiskCandidateSeverity) else _coerce_candidate_severity(value)
        for value in values
    )
    if len(set(severities)) != len(severities):
        raise TechnicalRiskRuleCandidateError("Duplicate severity.")
    if set(severities) != set(ALLOWED_CANDIDATE_SEVERITIES_V1):
        raise TechnicalRiskRuleCandidateError("Technical Risk v1 allowed severities must be LOW, MEDIUM, HIGH.")
    return severities


def _candidate_structural_checksum(candidate: TechnicalRiskRuleCandidateSpec) -> str:
    return _stable_hash(
        {
            "policy_candidate_id": candidate.policy_candidate_id,
            "candidate_version": candidate.candidate_version,
            "candidate_family": candidate.candidate_family.value,
            "rule_hierarchy_id": candidate.rule_hierarchy_id,
            "required_feature_ids": candidate.required_feature_ids,
            "derived_evidence_version": candidate.derived_evidence_version,
            "allowed_predicate_ids": [value.value for value in candidate.allowed_predicate_ids],
            "allowed_severities": [value.value for value in candidate.allowed_severities],
            "trigger_vocabulary_version": candidate.trigger_vocabulary_version,
            "evidence_vocabulary_version": candidate.evidence_vocabulary_version,
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "severity": rule.severity.value,
                    "required_predicates": [value.value for value in rule.required_predicates],
                    "optional_confirmation_predicates": [value.value for value in rule.optional_confirmation_predicates],
                    "rule_priority": rule.rule_priority,
                    "reason_codes": [value.value for value in rule.reason_codes],
                }
                for rule in sorted(candidate.rules, key=lambda item: item.rule_priority)
            ],
        }
    )


def _threshold_set_checksum(threshold_set: TechnicalRiskThresholdSet) -> str:
    return _stable_hash(
        {
            "threshold_set_version": threshold_set.threshold_set_version,
            "numeric_representation_version": threshold_set.numeric_representation_version,
            "dimensions": [
                {
                    "dimension_id": dimension.dimension_id.value,
                    "operator": dimension.operator.value,
                    "canonical_value": dimension.canonical_value,
                }
                for dimension in sorted(threshold_set.dimensions, key=lambda item: item.dimension_id.value)
            ],
            "compatible_candidate_families": sorted(family.value for family in threshold_set.compatible_candidate_families),
        }
    )


def _canonical_decimal(value: object) -> Decimal:
    decimal_value = _parse_decimal(value)
    return Decimal(_canonical_decimal_string(decimal_value))


def _coerce_candidate_family(value: object) -> TechnicalRiskCandidateFamily:
    try:
        return TechnicalRiskCandidateFamily(value)
    except ValueError as exc:
        raise TechnicalRiskRuleCandidateError("Unknown candidate family.") from exc


def _coerce_candidate_severity(value: object) -> TechnicalRiskCandidateSeverity:
    try:
        return TechnicalRiskCandidateSeverity(value)
    except ValueError as exc:
        raise TechnicalRiskRuleCandidateError("Unsupported candidate severity.") from exc


def _coerce_predicate_id(value: object) -> TechnicalRiskPredicateId:
    try:
        return TechnicalRiskPredicateId(value)
    except ValueError as exc:
        raise TechnicalRiskRuleCandidateError("Unsupported predicate identity.") from exc


def _coerce_reason_code(value: object) -> TechnicalRiskReasonCode:
    try:
        return TechnicalRiskReasonCode(value)
    except ValueError as exc:
        raise TechnicalRiskRuleCandidateError("Unsupported reason code.") from exc


def _coerce_threshold_dimension_id(value: object) -> TechnicalRiskThresholdDimensionId:
    try:
        return TechnicalRiskThresholdDimensionId(value)
    except ValueError as exc:
        raise TechnicalRiskRuleCandidateError("Unsupported threshold dimension.") from exc


def _coerce_threshold_operator(value: object) -> TechnicalRiskThresholdOperator:
    try:
        return TechnicalRiskThresholdOperator(value)
    except ValueError as exc:
        raise TechnicalRiskRuleCandidateError("Unsupported threshold operator.") from exc


def _canonical_decimal_string(value: object) -> str:
    decimal_value = _parse_decimal(value)
    if not decimal_value.is_finite():
        raise TechnicalRiskRuleCandidateError("Decimal value must be finite.")
    if decimal_value == 0:
        return "0"
    formatted = format(decimal_value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    if formatted == "-0":
        return "0"
    return formatted


def _parse_decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise TechnicalRiskRuleCandidateError("Boolean is not a valid numeric value.")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, Real):
        candidate = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise TechnicalRiskRuleCandidateError("Decimal string must not be empty.")
        try:
            candidate = Decimal(text)
        except InvalidOperation as exc:
            raise TechnicalRiskRuleCandidateError("Invalid Decimal representation.") from exc
    else:
        raise TechnicalRiskRuleCandidateError("Value must be numeric or a Decimal string.")
    if not candidate.is_finite():
        raise TechnicalRiskRuleCandidateError("Decimal value must be finite.")
    return candidate


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise TechnicalRiskRuleCandidateError(f"{field_name} must be a non-empty string.")


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
