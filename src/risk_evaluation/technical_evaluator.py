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
from typing import Mapping

from risk import RiskSeverity
from risk_evaluation.evaluation_input import RiskSignalProductionInput
from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_ID
from risk_evaluation.feature_input import TECH_AS_OF_CLOSE_FEATURE_VERSION
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_ID
from risk_evaluation.feature_input import TECH_RSI14_FEATURE_VERSION
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA20_FEATURE_VERSION
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_ID
from risk_evaluation.feature_input import TECH_SMA60_FEATURE_VERSION
from risk_evaluation.feature_input import RiskFeatureInput
from risk_evaluation.technical_policy import ProductionTechnicalRiskPolicy
from risk_evaluation.technical_policy import ProductionTechnicalRiskPredicateId
from risk_evaluation.technical_policy import ProductionTechnicalRiskReasonCode
from risk_evaluation.technical_policy import ProductionTechnicalRiskRule
from risk_evaluation.technical_policy import ProductionTechnicalRiskThresholdDimension
from risk_evaluation.technical_policy import ProductionTechnicalRiskThresholdDimensionId
from risk_evaluation.technical_policy import ProductionTechnicalRiskThresholdOperator
from risk_evaluation.validation import RiskEvaluationContractError
from risk_evaluation.validation import require_non_empty_text


TECHNICAL_RISK_EVALUATOR_VERSION_V1 = "TECHNICAL_RISK_EVALUATOR_V1"
TECH_RISK_DERIVED_EVIDENCE_V1 = "TECH_RISK_DERIVED_EVIDENCE_V1"
TECH_RISK_DECIMAL_CONTEXT_V1 = "TECH_RISK_DECIMAL_CONTEXT_V1"
TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1 = 34
TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1 = ROUND_HALF_EVEN

FIXED_TECH_RISK_DECIMAL_CONTEXT = Context(
    prec=TECH_RISK_DECIMAL_CONTEXT_PRECISION_V1,
    rounding=TECH_RISK_DECIMAL_CONTEXT_ROUNDING_V1,
)

TECH_RISK_FEATURE_VERSIONS_V1: Mapping[str, str] = MappingProxyType(
    {
        TECH_AS_OF_CLOSE_FEATURE_ID: TECH_AS_OF_CLOSE_FEATURE_VERSION,
        TECH_SMA20_FEATURE_ID: TECH_SMA20_FEATURE_VERSION,
        TECH_SMA60_FEATURE_ID: TECH_SMA60_FEATURE_VERSION,
        TECH_RSI14_FEATURE_ID: TECH_RSI14_FEATURE_VERSION,
    }
)


class TechnicalRiskEvaluatorError(RiskEvaluationContractError):
    """Raised when deterministic Technical Risk evaluation cannot proceed."""


class TechnicalRiskEvaluationStatus(StrEnum):
    EVALUATED = "EVALUATED"


@dataclass(frozen=True)
class TechnicalRiskEvaluationInput:
    production_input: RiskSignalProductionInput
    policy: ProductionTechnicalRiskPolicy
    evaluator_version: str = TECHNICAL_RISK_EVALUATOR_VERSION_V1
    numeric_context_version: str = TECH_RISK_DECIMAL_CONTEXT_V1

    def __post_init__(self):
        if not isinstance(self.production_input, RiskSignalProductionInput):
            raise TechnicalRiskEvaluatorError("production_input must be RiskSignalProductionInput.")
        if not isinstance(self.policy, ProductionTechnicalRiskPolicy):
            raise TechnicalRiskEvaluatorError("policy must be ProductionTechnicalRiskPolicy.")
        if self.evaluator_version != TECHNICAL_RISK_EVALUATOR_VERSION_V1:
            raise TechnicalRiskEvaluatorError("Unsupported Technical Risk evaluator version.")
        if self.numeric_context_version != self.policy.numeric_context_version:
            raise TechnicalRiskEvaluatorError("numeric_context_version must match policy numeric_context_version.")
        if self.numeric_context_version != TECH_RISK_DECIMAL_CONTEXT_V1:
            raise TechnicalRiskEvaluatorError("Unsupported Technical Risk numeric context version.")
        if self.policy.derived_evidence_version != TECH_RISK_DERIVED_EVIDENCE_V1:
            raise TechnicalRiskEvaluatorError("Unsupported Technical Risk derived evidence version.")


@dataclass(frozen=True)
class TechnicalRiskDerivedEvidence:
    derived_evidence_version: str
    close_vs_sma20: Decimal
    close_vs_sma60: Decimal
    relative_sma_spread: Decimal

    def __post_init__(self):
        if self.derived_evidence_version != TECH_RISK_DERIVED_EVIDENCE_V1:
            raise TechnicalRiskEvaluatorError("Unsupported Technical Risk derived evidence version.")
        object.__setattr__(self, "close_vs_sma20", _canonical_decimal(self.close_vs_sma20, "close_vs_sma20"))
        object.__setattr__(self, "close_vs_sma60", _canonical_decimal(self.close_vs_sma60, "close_vs_sma60"))
        object.__setattr__(
            self,
            "relative_sma_spread",
            _canonical_decimal(self.relative_sma_spread, "relative_sma_spread"),
        )


@dataclass(frozen=True)
class TechnicalRiskPredicateState:
    predicate_id: ProductionTechnicalRiskPredicateId
    threshold_dimension_id: ProductionTechnicalRiskThresholdDimensionId
    operator: ProductionTechnicalRiskThresholdOperator
    evidence_value: Decimal
    threshold_value: Decimal
    is_triggered: bool

    def __post_init__(self):
        object.__setattr__(self, "predicate_id", _coerce_predicate(self.predicate_id))
        object.__setattr__(self, "threshold_dimension_id", _coerce_dimension(self.threshold_dimension_id))
        object.__setattr__(self, "operator", _coerce_operator(self.operator))
        object.__setattr__(self, "evidence_value", _canonical_decimal(self.evidence_value, "evidence_value"))
        object.__setattr__(self, "threshold_value", _canonical_decimal(self.threshold_value, "threshold_value"))
        if not isinstance(self.is_triggered, bool):
            raise TechnicalRiskEvaluatorError("is_triggered must be bool.")


@dataclass(frozen=True)
class TechnicalRiskFeatureReference:
    feature_id: str
    feature_version: str
    feature_value: Decimal
    source_artifact_id: str
    source_checksum: str
    calculation_id: str

    def __post_init__(self):
        require_non_empty_text(self.feature_id, "feature_id", TechnicalRiskEvaluatorError)
        require_non_empty_text(self.feature_version, "feature_version", TechnicalRiskEvaluatorError)
        require_non_empty_text(self.source_artifact_id, "source_artifact_id", TechnicalRiskEvaluatorError)
        require_non_empty_text(self.source_checksum, "source_checksum", TechnicalRiskEvaluatorError)
        require_non_empty_text(self.calculation_id, "calculation_id", TechnicalRiskEvaluatorError)
        object.__setattr__(self, "feature_value", _canonical_decimal(self.feature_value, "feature_value"))


@dataclass(frozen=True)
class TechnicalRiskEvaluationResult:
    evaluation_id: str | None
    evaluation_checksum: str | None
    evaluation_status: TechnicalRiskEvaluationStatus | str
    evaluator_version: str
    numeric_context_version: str
    policy_id: str
    policy_version: str
    policy_checksum: str
    portfolio_id: str
    position_id: str
    symbol: str
    as_of_date: object
    valuation_date: object
    calculation_id: str
    source_artifact_ids: tuple[str, ...]
    source_checksums: tuple[str, ...]
    feature_references: tuple[TechnicalRiskFeatureReference, ...]
    derived_evidence: TechnicalRiskDerivedEvidence
    predicate_states: tuple[TechnicalRiskPredicateState, ...]
    matched_rule_id: str | None
    matched_rule_priority: int | None
    severity: RiskSeverity | str
    reason_codes: tuple[ProductionTechnicalRiskReasonCode | str, ...]

    def __post_init__(self):
        status = (
            self.evaluation_status
            if isinstance(self.evaluation_status, TechnicalRiskEvaluationStatus)
            else TechnicalRiskEvaluationStatus(self.evaluation_status)
        )
        if status != TechnicalRiskEvaluationStatus.EVALUATED:
            raise TechnicalRiskEvaluatorError("Unsupported Technical Risk evaluation status.")
        if self.evaluator_version != TECHNICAL_RISK_EVALUATOR_VERSION_V1:
            raise TechnicalRiskEvaluatorError("Unsupported Technical Risk evaluator version.")
        if self.numeric_context_version != TECH_RISK_DECIMAL_CONTEXT_V1:
            raise TechnicalRiskEvaluatorError("Unsupported Technical Risk numeric context version.")
        for field_name in (
            "policy_id",
            "policy_version",
            "policy_checksum",
            "portfolio_id",
            "position_id",
            "symbol",
            "calculation_id",
        ):
            require_non_empty_text(getattr(self, field_name), field_name, TechnicalRiskEvaluatorError)
        source_artifact_ids = _normalize_text_tuple(self.source_artifact_ids, "source_artifact_ids")
        source_checksums = _normalize_text_tuple(self.source_checksums, "source_checksums")
        feature_references = _normalize_feature_references(self.feature_references)
        predicate_states = _normalize_predicate_states(self.predicate_states)
        severity = _coerce_severity(self.severity)
        if severity == RiskSeverity.CRITICAL:
            raise TechnicalRiskEvaluatorError("Technical Risk v1 evaluation cannot represent CRITICAL severity.")
        reason_codes = _normalize_reasons(self.reason_codes)
        if self.matched_rule_id is not None:
            require_non_empty_text(self.matched_rule_id, "matched_rule_id", TechnicalRiskEvaluatorError)
        if self.matched_rule_priority is not None and (
            not isinstance(self.matched_rule_priority, int) or self.matched_rule_priority <= 0
        ):
            raise TechnicalRiskEvaluatorError("matched_rule_priority must be a positive integer or None.")
        checksum = _evaluation_checksum(
            self,
            status,
            source_artifact_ids,
            source_checksums,
            feature_references,
            predicate_states,
            severity,
            reason_codes,
        )
        identity = _stable_id("technical_risk_evaluation", {"evaluation_checksum": checksum})
        if self.evaluation_id is not None and self.evaluation_id != identity:
            raise TechnicalRiskEvaluatorError("evaluation_id mismatch.")
        if self.evaluation_checksum is not None and self.evaluation_checksum != checksum:
            raise TechnicalRiskEvaluatorError("evaluation_checksum mismatch.")
        object.__setattr__(self, "evaluation_status", status)
        object.__setattr__(self, "source_artifact_ids", source_artifact_ids)
        object.__setattr__(self, "source_checksums", source_checksums)
        object.__setattr__(self, "feature_references", feature_references)
        object.__setattr__(self, "predicate_states", predicate_states)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "reason_codes", reason_codes)
        object.__setattr__(self, "evaluation_id", identity)
        object.__setattr__(self, "evaluation_checksum", checksum)


class TechnicalRiskEvaluator:
    def evaluate(self, evaluation_input: TechnicalRiskEvaluationInput) -> TechnicalRiskEvaluationResult:
        if not isinstance(evaluation_input, TechnicalRiskEvaluationInput):
            raise TechnicalRiskEvaluatorError("evaluate requires TechnicalRiskEvaluationInput.")
        production_input = evaluation_input.production_input
        policy = evaluation_input.policy
        features = _resolve_required_features(production_input, policy)
        feature_values = _canonical_feature_values(features)
        derived_evidence = _derive_evidence(feature_values, policy.derived_evidence_version)
        predicate_states = _evaluate_predicates(policy, derived_evidence, feature_values[TECH_RSI14_FEATURE_ID])
        matched_rule = _select_rule(policy.rules, predicate_states)
        severity, reason_codes = _severity_and_reasons(matched_rule)
        return TechnicalRiskEvaluationResult(
            evaluation_id=None,
            evaluation_checksum=None,
            evaluation_status=TechnicalRiskEvaluationStatus.EVALUATED,
            evaluator_version=evaluation_input.evaluator_version,
            numeric_context_version=evaluation_input.numeric_context_version,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            policy_checksum=policy.policy_checksum,
            portfolio_id=production_input.portfolio_id,
            position_id=production_input.position_id,
            symbol=production_input.symbol,
            as_of_date=production_input.as_of_date,
            valuation_date=production_input.valuation_date,
            calculation_id=production_input.calculation_id,
            source_artifact_ids=production_input.source_artifact_ids,
            source_checksums=production_input.source_checksums,
            feature_references=_feature_references(features, feature_values),
            derived_evidence=derived_evidence,
            predicate_states=predicate_states,
            matched_rule_id=matched_rule.rule_id if matched_rule is not None else None,
            matched_rule_priority=matched_rule.rule_priority if matched_rule is not None else None,
            severity=severity,
            reason_codes=reason_codes,
        )


def _resolve_required_features(
    production_input: RiskSignalProductionInput,
    policy: ProductionTechnicalRiskPolicy,
) -> Mapping[str, RiskFeatureInput]:
    required_ids = tuple(policy.required_feature_ids)
    if set(required_ids) != set(TECH_RISK_FEATURE_VERSIONS_V1):
        raise TechnicalRiskEvaluatorError("Unsupported Technical Risk required feature set.")
    by_id: dict[str, RiskFeatureInput] = {}
    for feature in production_input.feature_values:
        if feature.feature_id in required_ids:
            expected_version = TECH_RISK_FEATURE_VERSIONS_V1.get(feature.feature_id)
            if feature.feature_version != expected_version:
                raise TechnicalRiskEvaluatorError("Technical Risk feature version mismatch.")
            by_id[feature.feature_id] = feature
    missing = tuple(feature_id for feature_id in required_ids if feature_id not in by_id)
    if missing:
        raise TechnicalRiskEvaluatorError(f"Missing required Technical Risk feature: {', '.join(missing)}")
    return MappingProxyType(dict(sorted(by_id.items())))


def _canonical_feature_values(features: Mapping[str, RiskFeatureInput]) -> Mapping[str, Decimal]:
    values = {
        feature_id: _canonical_decimal(feature.value, f"{feature_id} value")
        for feature_id, feature in features.items()
    }
    for feature_id in (TECH_AS_OF_CLOSE_FEATURE_ID, TECH_SMA20_FEATURE_ID, TECH_SMA60_FEATURE_ID):
        if values[feature_id] <= 0:
            raise TechnicalRiskEvaluatorError(f"{feature_id} must be positive.")
    return MappingProxyType(values)


def _derive_evidence(
    values: Mapping[str, Decimal],
    derived_evidence_version: str,
) -> TechnicalRiskDerivedEvidence:
    close = values[TECH_AS_OF_CLOSE_FEATURE_ID]
    sma20 = values[TECH_SMA20_FEATURE_ID]
    sma60 = values[TECH_SMA60_FEATURE_ID]
    with localcontext(FIXED_TECH_RISK_DECIMAL_CONTEXT):
        return TechnicalRiskDerivedEvidence(
            derived_evidence_version=derived_evidence_version,
            close_vs_sma20=(close - sma20) / sma20,
            close_vs_sma60=(close - sma60) / sma60,
            relative_sma_spread=(sma20 - sma60) / sma60,
        )


def _evaluate_predicates(
    policy: ProductionTechnicalRiskPolicy,
    evidence: TechnicalRiskDerivedEvidence,
    rsi14: Decimal,
) -> tuple[TechnicalRiskPredicateState, ...]:
    dimensions = policy.threshold_dimensions_by_id
    evidence_by_predicate: dict[
        ProductionTechnicalRiskPredicateId,
        tuple[ProductionTechnicalRiskThresholdDimensionId, Decimal],
    ] = {
        ProductionTechnicalRiskPredicateId.SHORT_PRICE_WEAKNESS: (
            ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA20_WEAKNESS_CUTOFF,
            evidence.close_vs_sma20,
        ),
        ProductionTechnicalRiskPredicateId.MEDIUM_PRICE_WEAKNESS: (
            ProductionTechnicalRiskThresholdDimensionId.CLOSE_VS_SMA60_WEAKNESS_CUTOFF,
            evidence.close_vs_sma60,
        ),
        ProductionTechnicalRiskPredicateId.TREND_STRUCTURE_WEAKNESS: (
            ProductionTechnicalRiskThresholdDimensionId.RELATIVE_SMA_SPREAD_WEAKNESS_CUTOFF,
            evidence.relative_sma_spread,
        ),
        ProductionTechnicalRiskPredicateId.MOMENTUM_WEAKNESS_CONFIRMATION: (
            ProductionTechnicalRiskThresholdDimensionId.RSI14_WEAKNESS_CONFIRMATION_CUTOFF,
            rsi14,
        ),
    }
    states: list[TechnicalRiskPredicateState] = []
    with localcontext(FIXED_TECH_RISK_DECIMAL_CONTEXT):
        for predicate in sorted(evidence_by_predicate, key=lambda item: item.value):
            dimension_id, evidence_value = evidence_by_predicate[predicate]
            dimension = dimensions.get(dimension_id)
            if dimension is None:
                raise TechnicalRiskEvaluatorError("Missing Technical Risk threshold dimension.")
            if dimension.operator != ProductionTechnicalRiskThresholdOperator.LESS_THAN_OR_EQUAL:
                raise TechnicalRiskEvaluatorError("Unsupported Technical Risk predicate operator.")
            states.append(
                TechnicalRiskPredicateState(
                    predicate_id=predicate,
                    threshold_dimension_id=dimension_id,
                    operator=dimension.operator,
                    evidence_value=evidence_value,
                    threshold_value=dimension.canonical_value,
                    is_triggered=evidence_value <= dimension.canonical_value,
                )
            )
    return tuple(states)


def _select_rule(
    rules: tuple[ProductionTechnicalRiskRule, ...],
    predicate_states: tuple[TechnicalRiskPredicateState, ...],
) -> ProductionTechnicalRiskRule | None:
    triggered = {state.predicate_id for state in predicate_states if state.is_triggered}
    matched = tuple(
        rule
        for rule in rules
        if all(predicate in triggered for predicate in rule.required_predicates)
    )
    if not matched:
        return None
    for severity in (RiskSeverity.HIGH, RiskSeverity.MEDIUM, RiskSeverity.LOW):
        same_severity = tuple(rule for rule in matched if rule.severity == severity)
        if same_severity:
            return min(same_severity, key=lambda rule: rule.rule_priority)
    raise TechnicalRiskEvaluatorError("Matched rule has unsupported severity.")


def _severity_and_reasons(
    matched_rule: ProductionTechnicalRiskRule | None,
) -> tuple[RiskSeverity, tuple[ProductionTechnicalRiskReasonCode, ...]]:
    if matched_rule is None:
        return (
            RiskSeverity.LOW,
            (ProductionTechnicalRiskReasonCode.NO_ELEVATED_TECHNICAL_DOWNSIDE_EVIDENCE,),
        )
    if matched_rule.severity == RiskSeverity.CRITICAL:
        raise TechnicalRiskEvaluatorError("Technical Risk v1 evaluation cannot emit CRITICAL severity.")
    return matched_rule.severity, matched_rule.reason_codes


def _feature_references(
    features: Mapping[str, RiskFeatureInput],
    feature_values: Mapping[str, Decimal],
) -> tuple[TechnicalRiskFeatureReference, ...]:
    return tuple(
        TechnicalRiskFeatureReference(
            feature_id=feature.feature_id,
            feature_version=feature.feature_version,
            feature_value=feature_values[feature.feature_id],
            source_artifact_id=feature.source_artifact_id,
            source_checksum=feature.source_checksum,
            calculation_id=feature.calculation_id,
        )
        for feature in sorted(features.values(), key=lambda item: (item.feature_id, item.feature_version))
    )


def _canonical_decimal(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, Real, str)):
        raise TechnicalRiskEvaluatorError(f"{field_name} must be Decimal-compatible numeric.")
    try:
        if isinstance(value, Decimal):
            candidate = value
        elif isinstance(value, Real):
            candidate = Decimal(str(value))
        else:
            candidate = Decimal(value.strip())
    except (AttributeError, InvalidOperation, ValueError) as exc:
        raise TechnicalRiskEvaluatorError(f"{field_name} must be finite Decimal-compatible numeric.") from exc
    if not candidate.is_finite():
        raise TechnicalRiskEvaluatorError(f"{field_name} must be finite.")
    return Decimal(_canonical_decimal_string(candidate))


def _canonical_decimal_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _coerce_predicate(value: ProductionTechnicalRiskPredicateId | str) -> ProductionTechnicalRiskPredicateId:
    try:
        return value if isinstance(value, ProductionTechnicalRiskPredicateId) else ProductionTechnicalRiskPredicateId(value)
    except ValueError as exc:
        raise TechnicalRiskEvaluatorError("Unsupported Technical Risk predicate.") from exc


def _coerce_dimension(
    value: ProductionTechnicalRiskThresholdDimensionId | str,
) -> ProductionTechnicalRiskThresholdDimensionId:
    try:
        return value if isinstance(value, ProductionTechnicalRiskThresholdDimensionId) else ProductionTechnicalRiskThresholdDimensionId(value)
    except ValueError as exc:
        raise TechnicalRiskEvaluatorError("Unsupported Technical Risk threshold dimension.") from exc


def _coerce_operator(value: ProductionTechnicalRiskThresholdOperator | str) -> ProductionTechnicalRiskThresholdOperator:
    try:
        return value if isinstance(value, ProductionTechnicalRiskThresholdOperator) else ProductionTechnicalRiskThresholdOperator(value)
    except ValueError as exc:
        raise TechnicalRiskEvaluatorError("Unsupported Technical Risk threshold operator.") from exc


def _coerce_severity(value: RiskSeverity | str) -> RiskSeverity:
    try:
        return value if isinstance(value, RiskSeverity) else RiskSeverity(value)
    except ValueError as exc:
        raise TechnicalRiskEvaluatorError("Unsupported Technical Risk severity.") from exc


def _normalize_reasons(
    values: tuple[ProductionTechnicalRiskReasonCode | str, ...],
) -> tuple[ProductionTechnicalRiskReasonCode, ...]:
    if not isinstance(values, tuple) or not values:
        raise TechnicalRiskEvaluatorError("reason_codes must be a non-empty tuple.")
    reasons = tuple(
        value if isinstance(value, ProductionTechnicalRiskReasonCode) else ProductionTechnicalRiskReasonCode(value)
        for value in values
    )
    if len(set(reasons)) != len(reasons):
        raise TechnicalRiskEvaluatorError("Duplicate Technical Risk reason code.")
    return reasons


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TechnicalRiskEvaluatorError(f"{field_name} must be a tuple.")
    if any(not isinstance(value, str) or not value for value in values):
        raise TechnicalRiskEvaluatorError(f"{field_name} must contain non-empty strings.")
    if len(set(values)) != len(values):
        raise TechnicalRiskEvaluatorError(f"{field_name} must not contain duplicates.")
    return tuple(sorted(values))


def _normalize_feature_references(
    values: tuple[TechnicalRiskFeatureReference, ...],
) -> tuple[TechnicalRiskFeatureReference, ...]:
    if not isinstance(values, tuple):
        raise TechnicalRiskEvaluatorError("feature_references must be a tuple.")
    if any(not isinstance(value, TechnicalRiskFeatureReference) for value in values):
        raise TechnicalRiskEvaluatorError("feature_references must contain TechnicalRiskFeatureReference.")
    identities = tuple((value.feature_id, value.feature_version) for value in values)
    if len(set(identities)) != len(identities):
        raise TechnicalRiskEvaluatorError("Duplicate Technical Risk feature reference.")
    return tuple(sorted(values, key=lambda item: (item.feature_id, item.feature_version)))


def _normalize_predicate_states(
    values: tuple[TechnicalRiskPredicateState, ...],
) -> tuple[TechnicalRiskPredicateState, ...]:
    if not isinstance(values, tuple):
        raise TechnicalRiskEvaluatorError("predicate_states must be a tuple.")
    if any(not isinstance(value, TechnicalRiskPredicateState) for value in values):
        raise TechnicalRiskEvaluatorError("predicate_states must contain TechnicalRiskPredicateState.")
    predicate_ids = tuple(value.predicate_id for value in values)
    if len(set(predicate_ids)) != len(predicate_ids):
        raise TechnicalRiskEvaluatorError("Duplicate Technical Risk predicate state.")
    return tuple(sorted(values, key=lambda item: item.predicate_id.value))


def _evaluation_checksum(
    result: TechnicalRiskEvaluationResult,
    status: TechnicalRiskEvaluationStatus,
    source_artifact_ids: tuple[str, ...],
    source_checksums: tuple[str, ...],
    feature_references: tuple[TechnicalRiskFeatureReference, ...],
    predicate_states: tuple[TechnicalRiskPredicateState, ...],
    severity: RiskSeverity,
    reason_codes: tuple[ProductionTechnicalRiskReasonCode, ...],
) -> str:
    return _stable_hash(
        {
            "evaluation_status": status.value,
            "evaluator_version": result.evaluator_version,
            "numeric_context_version": result.numeric_context_version,
            "policy_id": result.policy_id,
            "policy_version": result.policy_version,
            "policy_checksum": result.policy_checksum,
            "portfolio_id": result.portfolio_id,
            "position_id": result.position_id,
            "symbol": result.symbol,
            "as_of_date": result.as_of_date,
            "valuation_date": result.valuation_date,
            "calculation_id": result.calculation_id,
            "source_artifact_ids": source_artifact_ids,
            "source_checksums": source_checksums,
            "feature_references": [_feature_reference_payload(reference) for reference in feature_references],
            "derived_evidence": _derived_evidence_payload(result.derived_evidence),
            "predicate_states": [_predicate_state_payload(state) for state in predicate_states],
            "matched_rule_id": result.matched_rule_id,
            "matched_rule_priority": result.matched_rule_priority,
            "severity": severity.value,
            "reason_codes": [reason.value for reason in reason_codes],
        }
    )


def _feature_reference_payload(reference: TechnicalRiskFeatureReference) -> dict[str, object]:
    return {
        "feature_id": reference.feature_id,
        "feature_version": reference.feature_version,
        "feature_value": reference.feature_value,
        "source_artifact_id": reference.source_artifact_id,
        "source_checksum": reference.source_checksum,
        "calculation_id": reference.calculation_id,
    }


def _derived_evidence_payload(evidence: TechnicalRiskDerivedEvidence) -> dict[str, object]:
    return {
        "derived_evidence_version": evidence.derived_evidence_version,
        "close_vs_sma20": evidence.close_vs_sma20,
        "close_vs_sma60": evidence.close_vs_sma60,
        "relative_sma_spread": evidence.relative_sma_spread,
    }


def _predicate_state_payload(state: TechnicalRiskPredicateState) -> dict[str, object]:
    return {
        "predicate_id": state.predicate_id.value,
        "threshold_dimension_id": state.threshold_dimension_id.value,
        "operator": state.operator.value,
        "evidence_value": state.evidence_value,
        "threshold_value": state.threshold_value,
        "is_triggered": state.is_triggered,
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
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, MappingProxyType):
        return dict(value)
    return value
